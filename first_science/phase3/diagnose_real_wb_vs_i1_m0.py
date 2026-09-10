"""Real-trace white-box versus materialized-I1 M0 diagnostic.

Phase 3 never reads private provider traces. It consumes only the public,
hash-frozen Phase-2 I1 card instances plus the public composition graph and
frozen deterministic benchmark terms. White-box truth is used only for external
evaluation of the already-computed M0 prediction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PHASE3_DIRECTORY = Path(__file__).resolve().parent
FIRST_SCIENCE_DIRECTORY = PHASE3_DIRECTORY.parent
PHASE1_DIRECTORY = FIRST_SCIENCE_DIRECTORY / "phase1"
PHASE2_DIRECTORY = FIRST_SCIENCE_DIRECTORY / "phase2"
for module_directory in (PHASE1_DIRECTORY, PHASE2_DIRECTORY):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from i1_provider_card import load_i1_provider_card  # noqa: E402
from m0_analytic_composition import (  # noqa: E402
    AdmissibilityBoundary,
    boundary_is_sufficient_for_query,
    independent_product_probability,
    same_rho_as_global,
)
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary  # noqa: E402
from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    calculate_empirical_sla_sigma_from_ledgers,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
ROLE_ORDER = ("latency", "cost", "mixed")
ROLE_TITLES = {
    "latency": "Latency-dominant",
    "cost": "Cost-dominant",
    "mixed": "Mixed L/C",
}
EVENT_TOLERANCE = 1e-12
SNAPSHOT_HORIZONS = (0.0, 60.0, 120.0, 180.0, 240.0)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rho_tag(rho: float) -> str:
    return f"{float(rho):.6f}".rstrip("0").rstrip(".").replace(".", "p")


def load_hash_frozen_i1_cards(
    card_root: Path,
    card_manifest_path: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, pd.DataFrame], dict[str, Any]]:
    """Load only public I1 cards and verify every frozen card hash."""
    manifest = _read_json(card_manifest_path)
    if manifest.get("status") != "FROZEN_PHASE2_I1_CARD_INSTANCES_V1":
        raise ValueError("unexpected I1 card-instance manifest status")
    cards = manifest.get("cards", {})
    if set(cards) != set(PROVIDERS):
        raise ValueError("I1 card-instance manifest must contain ProviderA/B/C")

    metadata_by_provider: dict[str, dict[str, object]] = {}
    surfaces: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        record = cards[provider]
        directory = card_root / str(record["directory"])
        card_json = directory / "card.json"
        surface_csv = directory / "sigma_surface.csv"
        if _sha256_file(card_json) != str(record["card_json_sha256"]):
            raise RuntimeError(f"{provider} public card.json hash mismatch")
        if _sha256_file(surface_csv) != str(record["sigma_surface_sha256"]):
            raise RuntimeError(f"{provider} public sigma surface hash mismatch")
        metadata, surface = load_i1_provider_card(directory)
        if str(metadata.get("provider_id")) != provider:
            raise RuntimeError(f"{provider} card provider_id mismatch")
        metadata_by_provider[provider] = metadata
        surfaces[provider] = surface
    return metadata_by_provider, surfaces, manifest


def extract_provider_boundaries_from_public_cards(
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
) -> dict[str, AdmissibilityBoundary]:
    """Extract the unique public A_i already frozen inside each card."""
    boundaries: dict[str, AdmissibilityBoundary] = {}
    for provider in PROVIDERS:
        metadata = metadata_by_provider[provider]
        ai = metadata.get("A_i")
        if isinstance(ai, dict):
            boundary = AdmissibilityBoundary(
                l_max=float(ai["l_max"]),
                c_max=float(ai["c_max"]),
                q_min=float(ai["q_min"]),
            )
        else:
            surface = surfaces[provider]
            triples = surface[["l_max", "c_max", "q_min"]].drop_duplicates()
            if len(triples) != 1:
                raise RuntimeError(f"{provider} public card does not contain one fixed A_i")
            row = triples.iloc[0]
            boundary = AdmissibilityBoundary(
                l_max=float(row["l_max"]),
                c_max=float(row["c_max"]),
                q_min=float(row["q_min"]),
            )
        boundaries[provider] = boundary
    return boundaries


def _common_horizon_support(metadata_by_provider: dict[str, dict[str, object]]) -> list[float]:
    supports = [
        tuple(float(value) for value in metadata_by_provider[p]["supported_horizons"])
        for p in PROVIDERS
    ]
    if len(set(supports)) != 1:
        raise RuntimeError("provider I1 horizon supports differ")
    return list(supports[0])


def _assert_rho_is_publicly_exposed(
    metadata_by_provider: dict[str, dict[str, object]], rho_global: float
) -> None:
    for provider in PROVIDERS:
        support = [float(value) for value in metadata_by_provider[provider]["supported_rho_values"]]
        if not any(abs(float(rho_global) - value) <= EVENT_TOLERANCE for value in support):
            raise ValueError(f"rho_G={rho_global:g} is not exposed by {provider} I1 card")


def build_same_rho_m0_curve(
    provider_surfaces: dict[str, pd.DataFrame],
    rho_global: float,
    horizons: list[float],
) -> pd.DataFrame:
    """Compose public I1 points with the frozen same-rho independent product."""
    rho_map = same_rho_as_global(rho_global, PROVIDERS)
    if any(abs(rho - float(rho_global)) > EVENT_TOLERANCE for rho in rho_map.values()):
        raise RuntimeError("M0 same-rho contract was violated")

    rows: list[dict[str, float]] = []
    for horizon in horizons:
        provider_sigma: dict[str, float] = {}
        for provider in PROVIDERS:
            surface = provider_surfaces[provider]
            selected = surface[
                np.isclose(surface["rho"].astype(float), float(rho_global), atol=EVENT_TOLERANCE)
                & np.isclose(surface["horizon"].astype(float), float(horizon), atol=EVENT_TOLERANCE)
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"expected one public I1 point for {provider}, H={horizon:g}, rho={rho_global:g}"
                )
            provider_sigma[provider] = float(selected.iloc[0]["sigma_hat"])
        rows.append(
            {
                "horizon": float(horizon),
                "rho_global": float(rho_global),
                "sigma_i1_m0": independent_product_probability(provider_sigma),
                "sigma_ProviderA": provider_sigma["ProviderA"],
                "sigma_ProviderB": provider_sigma["ProviderB"],
                "sigma_ProviderC": provider_sigma["ProviderC"],
            }
        )
    return pd.DataFrame(rows)


def build_real_whitebox_curve(
    all_top_level_ledgers: pd.DataFrame,
    whitebox: dict[str, object],
    rho_global: float,
    horizons: list[float],
    stop_time: float,
) -> pd.DataFrame:
    """Recompute one Phase-1 white-box sigma curve for external evaluation."""
    definition = SlaComplianceDefinition(
        rho=float(rho_global), accounting_origin=0.0, zero_decision_compliance=1.0
    )
    sigma, _, _ = calculate_empirical_sla_sigma_from_ledgers(
        all_top_level_ledgers,
        latency_threshold=float(whitebox["l_max"]),
        cost_threshold=float(whitebox["c_max"]),
        quality_threshold=float(whitebox["q_min"]),
        horizons=horizons,
        stop_time=float(stop_time),
        sla_definition=definition,
    )
    return sigma[["horizon", "sigma"]].rename(columns={"sigma": "sigma_whitebox"})


def compare_curves(
    whitebox_curve: pd.DataFrame,
    m0_curve: pd.DataFrame,
    *,
    m0_applicable: bool = True,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Align WB/M0 and suppress prediction/error when M0 is not applicable."""
    comparison = whitebox_curve.merge(m0_curve, on="horizon", how="inner", validate="one_to_one")
    comparison["sigma_i1_m0_raw_probability_component"] = comparison["sigma_i1_m0"].astype(float)
    if not m0_applicable:
        comparison["sigma_i1_m0"] = np.nan
        comparison["error_m0_minus_wb"] = np.nan
        nan = float("nan")
        return comparison, {"mae": nan, "rmse": nan, "bias": nan, "max_abs_error": nan}
    comparison["error_m0_minus_wb"] = comparison["sigma_i1_m0"] - comparison["sigma_whitebox"]
    error = comparison["error_m0_minus_wb"].to_numpy(dtype=float)
    return comparison, {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def _containment_failure_summary(induced: AdmissibilityBoundary, requested: AdmissibilityBoundary) -> str:
    failures: list[str] = []
    if induced.l_max > requested.l_max + EVENT_TOLERANCE:
        failures.append(f"L {induced.l_max:.4f}>{requested.l_max:.4f}")
    if induced.c_max > requested.c_max + EVENT_TOLERANCE:
        failures.append(f"C {induced.c_max:.4f}>{requested.c_max:.4f}")
    if induced.q_min + EVENT_TOLERANCE < requested.q_min:
        failures.append(f"Q {induced.q_min:.4f}<{requested.q_min:.4f}")
    return ", ".join(failures) if failures else "none"


def plot_one_comparison(
    comparison: pd.DataFrame,
    role: str,
    rho_global: float,
    metrics: dict[str, float],
    output_path: Path,
    *,
    m0_applicable: bool,
    containment_failure: str,
) -> None:
    figure, axis = plt.subplots(figsize=(8.2, 5.1))
    axis.plot(comparison["horizon"], comparison["sigma_whitebox"], linewidth=2.0,
              label=r"White-box $\sigma_G$")
    if m0_applicable:
        axis.plot(comparison["horizon"], comparison["sigma_i1_m0"], linewidth=2.0,
                  linestyle="--", label=r"I1-M0 $\hat{\sigma}_G$")
    axis.set_xlim(float(comparison["horizon"].min()), float(comparison["horizon"].max()))
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel("Horizon H (s)")
    axis.set_ylabel("Admissibility probability")
    status = "M0 applicable" if m0_applicable else "M0 NOT APPLICABLE"
    axis.set_title(f"{ROLE_TITLES.get(role, role)}: white-box vs I1-M0\n$\\rho_G={rho_global:g}$, {status}")
    axis.grid(True, alpha=0.22)
    axis.legend(frameon=False)
    note = (
        f"MAE={metrics['mae']:.3f}   bias={metrics['bias']:+.3f}"
        if m0_applicable
        else f"I1-M0 not defined for this query\ncontainment failure: {containment_failure}"
    )
    axis.text(0.02, 0.04, note, transform=axis.transAxes, fontsize=9, alpha=0.8)
    figure.tight_layout()
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _snapshot_rows(comparison_table: pd.DataFrame) -> pd.DataFrame:
    horizons = comparison_table["horizon"].astype(float).to_numpy()
    mask = np.zeros(len(comparison_table), dtype=bool)
    for target in SNAPSHOT_HORIZONS:
        mask |= np.isclose(horizons, target, atol=EVENT_TOLERANCE)
    columns = [
        "selection_role", "m0_status", "horizon", "sigma_whitebox", "sigma_i1_m0",
        "sigma_i1_m0_raw_probability_component", "sigma_ProviderA", "sigma_ProviderB",
        "sigma_ProviderC", "error_m0_minus_wb",
    ]
    return comparison_table.loc[mask, columns].sort_values(["selection_role", "horizon"])


def run_real_trace_diagnostic(
    *,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    phase1_physical_config_path: Path,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
    rho_global: float,
    output_directory: Path,
) -> pd.DataFrame:
    """Evaluate M0 from public I1 only, then compare with independent WB truth."""
    metadata_by_provider, provider_surfaces, card_manifest = load_hash_frozen_i1_cards(
        i1_card_root, i1_card_manifest_path
    )
    _assert_rho_is_publicly_exposed(metadata_by_provider, rho_global)
    horizons = _common_horizon_support(metadata_by_provider)
    stop_time = max(horizons)
    provider_boundaries = extract_provider_boundaries_from_public_cards(
        metadata_by_provider, provider_surfaces
    )

    phase1_physical_config = _read_json(phase1_physical_config_path)
    induced_global_boundary, boundary_breakdown = build_phase1_g0_full_m0_boundary(
        phase1_physical_config, provider_boundaries
    )
    raw_m0_curve = build_same_rho_m0_curve(provider_surfaces, rho_global, horizons)

    all_top_level_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(all_top_level_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("white-box diagnostic expects exactly 100 trajectories")
    whitebox_manifest = _read_json(whitebox_manifest_path)
    if whitebox_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")

    output_directory.mkdir(parents=True, exist_ok=True)
    raw_m0_curve.to_csv(output_directory / "real_i1_m0_raw_probability_curve.csv", index=False)

    by_role = {str(item["selection_role"]): item for item in whitebox_manifest["whiteboxes"]}
    all_comparisons: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    applicability_manifest: dict[str, object] = {}
    for role in ROLE_ORDER:
        whitebox = by_role[role]
        requested = AdmissibilityBoundary(
            float(whitebox["l_max"]), float(whitebox["c_max"]), float(whitebox["q_min"])
        )
        applicable = boundary_is_sufficient_for_query(induced_global_boundary, requested)
        status = "PREDICTED" if applicable else "NOT_APPLICABLE"
        failure = _containment_failure_summary(induced_global_boundary, requested)
        wb_curve = build_real_whitebox_curve(
            all_top_level_ledgers, whitebox, rho_global, horizons, stop_time
        )
        comparison, metrics = compare_curves(wb_curve, raw_m0_curve, m0_applicable=applicable)
        comparison.insert(0, "m0_status", status)
        comparison.insert(0, "selection_role", role)
        comparison.insert(0, "case_id", str(whitebox["case_id"]))
        all_comparisons.append(comparison)
        plot_name = f"real_wb_vs_i1_m0_{role}_rho_{_rho_tag(rho_global)}.png"
        plot_one_comparison(
            comparison, role, rho_global, metrics, output_directory / plot_name,
            m0_applicable=applicable, containment_failure=failure
        )
        summary_rows.append({
            "case_id": str(whitebox["case_id"]),
            "selection_role": role,
            "rho_global": float(rho_global),
            "m0_status": status,
            "containment_failure": failure,
            "induced_l_max": induced_global_boundary.l_max,
            "induced_c_max": induced_global_boundary.c_max,
            "induced_q_min": induced_global_boundary.q_min,
            "requested_l_max": requested.l_max,
            "requested_c_max": requested.c_max,
            "requested_q_min": requested.q_min,
            **metrics,
            "plot": plot_name,
        })
        applicability_manifest[str(whitebox["case_id"])] = {
            "selection_role": role,
            "status": status,
            "containment_failure": failure,
        }

    comparison_table = pd.concat(all_comparisons, ignore_index=True)
    summary_table = pd.DataFrame(summary_rows)
    snapshot = _snapshot_rows(comparison_table)
    comparison_table.to_csv(output_directory / "real_wb_vs_i1_m0_curves.csv", index=False)
    summary_table.to_csv(output_directory / "real_wb_vs_i1_m0_summary.csv", index=False)
    snapshot.to_csv(output_directory / "real_wb_vs_i1_m0_sigma_snapshot.csv", index=False)

    manifest = {
        "status": "REAL_TRACE_DIAGNOSTIC_FROM_FROZEN_PUBLIC_I1",
        "rho_global_evaluated": float(rho_global),
        "phase3_reads_private_provider_traces": False,
        "i1_card_manifest_sha256": _sha256_file(i1_card_manifest_path),
        "i1_card_hashes": {
            provider: {
                "card_json_sha256": card_manifest["cards"][provider]["card_json_sha256"],
                "sigma_surface_sha256": card_manifest["cards"][provider]["sigma_surface_sha256"],
            }
            for provider in PROVIDERS
        },
        "rho_policy": "rho_i=rho_G for all providers at evaluation time",
        "m0_probability_rule": "product_i sigma_i(A_i,H;rho_G)",
        "full_M0_induced_boundary": {
            "l_max": induced_global_boundary.l_max,
            "c_max": induced_global_boundary.c_max,
            "q_min": induced_global_boundary.q_min,
        },
        "deterministic_boundary_breakdown": {
            "fixed_latency_outside_provider": boundary_breakdown.fixed_latency_outside_provider,
            "fixed_cost_outside_provider": boundary_breakdown.fixed_cost_outside_provider,
        },
        "case_applicability": applicability_manifest,
    }
    (output_directory / "real_wb_vs_i1_m0_diagnostic_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_PASS")
    print("i1_source=materialized_hash_frozen_public_cards_only")
    print("phase3_reads_private_provider_traces=false")
    print("rho_policy=M0_rho_i_equals_evaluated_rho_G")
    print("full_M0_boundary_applicability_asserted=true")
    print("\nFULL_M0_BOUNDARY")
    print(
        f"A_G_M0=(L<={induced_global_boundary.l_max:.15g}, "
        f"C<={induced_global_boundary.c_max:.15g}, Q>={induced_global_boundary.q_min:.15g})"
    )
    print("\nAPPLICABILITY")
    print(summary_table[["case_id", "selection_role", "m0_status", "containment_failure"]].to_string(index=False))
    print("\nSIGMA_SNAPSHOT")
    print(snapshot.to_string(index=False))
    print("\nERROR_SUMMARY")
    print(summary_table.to_string(index=False))
    print(f"\noutput={output_directory.resolve()}")
    return summary_table


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate WB versus M0 from frozen public I1 cards")
    parser.add_argument("--rho", type=float, default=0.95)
    parser.add_argument(
        "--whitebox-ledgers", type=Path,
        default=PHASE1_DIRECTORY / "results" / "phase1_v2_fresh_confirmation_v1" / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--whitebox-manifest", type=Path,
        default=PHASE1_DIRECTORY / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--phase1-physical-config", type=Path,
        default=PHASE1_DIRECTORY / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--i1-card-root", type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_cards_v1" / "public",
    )
    parser.add_argument(
        "--i1-card-manifest", type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_cards_v1" / "public" / "i1_card_instances_manifest_v1.json",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or (
        PHASE3_DIRECTORY / "results" / f"real_wb_vs_i1_m0_rho_{_rho_tag(float(args.rho))}"
    )
    run_real_trace_diagnostic(
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        whitebox_manifest_path=args.whitebox_manifest.resolve(),
        phase1_physical_config_path=args.phase1_physical_config.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_card_manifest_path=args.i1_card_manifest.resolve(),
        rho_global=float(args.rho),
        output_directory=output.resolve(),
    )


if __name__ == "__main__":
    main()
