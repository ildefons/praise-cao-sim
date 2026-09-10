"""Real-trace diagnostic for white-box sigma versus the I1-M0 baseline.

Scientific inputs
-----------------
* White-box truth: frozen Phase-1 v2 fresh-confirmation top-level ledgers.
* Provider information: frozen Phase-2 provider-local acquisition ledgers.
* M0 probability rule: rho_i = rho_G and product_i sigma_i(A_i,H;rho_G).

This diagnostic never derives or tunes A_i. The caller must supply the three
explicit provider-local rectangular regions. Therefore plotting cannot silently
solve the separate Phase-2 T_i -> A_i design problem.

All plotted sigma values are recomputed from the real frozen trace banks. The
I1-M0 curve is the real probability-composition component of M0. This script
intentionally does not claim the separate full-graph boundary-applicability
check because the final numerical adapter for deterministic graph/network terms
must be frozen independently.
"""
from __future__ import annotations

import argparse
import json
import math
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

from i1_provider_card import build_i1_provider_card  # noqa: E402
from m0_analytic_composition import (  # noqa: E402
    AdmissibilityBoundary,
    compose_parallel_all,
    independent_product_probability,
    same_rho_as_global,
)
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


def _read_json(path: Path) -> dict[str, Any]:
    """Read one UTF-8 JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def _rho_tag(rho: float) -> str:
    """Return a filesystem-safe rho label without altering filename suffixes."""
    return f"{float(rho):.6f}".rstrip("0").rstrip(".").replace(".", "p")


def load_explicit_local_regions(path: Path) -> dict[str, AdmissibilityBoundary]:
    """Load caller-supplied A_i values without deriving or tuning thresholds.

    Expected minimal format::

        {
          "regions": {
            "ProviderA": {"l_max": ..., "c_max": ..., "q_min": ...},
            "ProviderB": {"l_max": ..., "c_max": ..., "q_min": ...},
            "ProviderC": {"l_max": ..., "c_max": ..., "q_min": ...}
          }
        }

    ``rho`` and ``rho_i`` are rejected. A_i construction is independent of the
    later M0 same-rho slice selection.
    """
    document = _read_json(path)
    if "rho" in document or "rho_i" in document:
        raise ValueError("local-region input must not select rho or rho_i")
    regions = document.get("regions")
    if not isinstance(regions, dict):
        raise ValueError("local-region JSON must contain an object named 'regions'")
    if set(regions) != set(PROVIDERS):
        raise ValueError(
            "local-region JSON must contain exactly ProviderA, ProviderB and ProviderC"
        )

    parsed: dict[str, AdmissibilityBoundary] = {}
    for provider in PROVIDERS:
        region = regions[provider]
        if not isinstance(region, dict):
            raise ValueError(f"{provider} region must be a JSON object")
        if "rho" in region or "rho_i" in region:
            raise ValueError(f"{provider} A_i must not contain rho or rho_i")
        missing = {"l_max", "c_max", "q_min"}.difference(region)
        if missing:
            raise ValueError(
                f"{provider} region missing fields: {', '.join(sorted(missing))}"
            )
        values = (
            float(region["l_max"]),
            float(region["c_max"]),
            float(region["q_min"]),
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"{provider} region values must be finite")
        parsed[provider] = AdmissibilityBoundary(*values)
    return parsed


def load_i1_contract_support(
    contract_path: Path,
    rho_global: float,
) -> tuple[list[float], list[float], dict[str, object]]:
    """Return frozen I1 H/R support and workload context."""
    contract = _read_json(contract_path)
    if contract.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_TRACE":
        raise ValueError("unexpected Phase-2 I1 card contract status")
    horizons = [float(value) for value in contract["H"]["values"]]
    rho_support = [float(value) for value in contract["R"]["values"]]
    if not any(
        abs(float(rho_global) - rho) <= EVENT_TOLERANCE for rho in rho_support
    ):
        raise ValueError(
            f"rho_G={rho_global:g} is not present in frozen I1 support {rho_support}"
        )
    return horizons, rho_support, dict(contract["workload_contract"])


def load_provider_evidence(provider_root: Path) -> dict[str, pd.DataFrame]:
    """Load the three frozen private provider-ledger corpora."""
    ledgers: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        path = provider_root / provider / "provider_request_ledgers.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing provider evidence: {path}")
        ledger = pd.read_csv(path)
        if int(ledger["trajectory"].nunique()) != 100:
            raise ValueError(f"{provider} diagnostic expects exactly 100 trajectories")
        ledgers[provider] = ledger
    return ledgers


def build_real_i1_surfaces(
    provider_ledgers: dict[str, pd.DataFrame],
    local_regions: dict[str, AdmissibilityBoundary],
    rho_support: list[float],
    horizons: list[float],
    workload_contract: dict[str, object],
) -> dict[str, pd.DataFrame]:
    """Build in-memory I1 surfaces from the frozen real provider traces."""
    stop_time = float(workload_contract["horizon_max"])
    surfaces: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        boundary = local_regions[provider]
        _, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=provider_ledgers[provider],
            local_regions=[
                {
                    "region_id": f"{provider}_explicit_diagnostic_A_i",
                    "l_max": boundary.l_max,
                    "c_max": boundary.c_max,
                    "q_min": boundary.q_min,
                }
            ],
            rho_values=rho_support,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract=workload_contract,
        )
        surfaces[provider] = surface
    return surfaces


def build_same_rho_m0_curve(
    provider_surfaces: dict[str, pd.DataFrame],
    rho_global: float,
    horizons: list[float],
) -> pd.DataFrame:
    """Compose real I1 points with the frozen M0 same-rho product rule."""
    rho_map = same_rho_as_global(rho_global, PROVIDERS)
    if any(
        abs(rho - float(rho_global)) > EVENT_TOLERANCE
        for rho in rho_map.values()
    ):
        raise RuntimeError("M0 same-rho contract was violated")

    rows: list[dict[str, float]] = []
    for horizon in horizons:
        provider_sigma: dict[str, float] = {}
        for provider in PROVIDERS:
            surface = provider_surfaces[provider]
            selected = surface[
                np.isclose(
                    surface["rho"].astype(float),
                    float(rho_global),
                    atol=EVENT_TOLERANCE,
                )
                & np.isclose(
                    surface["horizon"].astype(float),
                    float(horizon),
                    atol=EVENT_TOLERANCE,
                )
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"expected one I1 point for {provider}, "
                    f"H={horizon:g}, rho={rho_global:g}"
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
    """Recompute one real Phase-1 white-box sigma curve on the common H grid."""
    definition = SlaComplianceDefinition(
        rho=float(rho_global),
        accounting_origin=0.0,
        zero_decision_compliance=1.0,
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
    return sigma[["horizon", "sigma"]].rename(
        columns={"sigma": "sigma_whitebox"}
    )


def compare_curves(
    whitebox_curve: pd.DataFrame,
    m0_curve: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Align WB/M0 points and compute simple pointwise diagnostic errors."""
    comparison = whitebox_curve.merge(
        m0_curve,
        on="horizon",
        how="inner",
        validate="one_to_one",
    )
    if comparison.empty or len(comparison) != len(m0_curve):
        raise RuntimeError("white-box and I1-M0 horizon supports do not align")
    comparison["error_m0_minus_wb"] = (
        comparison["sigma_i1_m0"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
    )
    error = comparison["error_m0_minus_wb"].to_numpy(dtype=float)
    metrics = {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }
    return comparison, metrics


def plot_one_comparison(
    comparison: pd.DataFrame,
    role: str,
    rho_global: float,
    metrics: dict[str, float],
    output_path: Path,
) -> None:
    """Write one minimalist publication-style real-trace diagnostic plot."""
    figure, axis = plt.subplots(figsize=(8.2, 5.1))
    axis.plot(
        comparison["horizon"],
        comparison["sigma_whitebox"],
        linewidth=2.0,
        label=r"White-box $\sigma_G$",
    )
    axis.plot(
        comparison["horizon"],
        comparison["sigma_i1_m0"],
        linewidth=2.0,
        linestyle="--",
        label=r"I1-M0 $\hat{\sigma}_G$",
    )
    axis.set_xlim(
        float(comparison["horizon"].min()),
        float(comparison["horizon"].max()),
    )
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel("Horizon H (s)")
    axis.set_ylabel("Admissibility probability")
    role_title = ROLE_TITLES.get(role, role)
    axis.set_title(
        f"{role_title}: white-box vs I1-M0\n"
        f"Frozen real trace banks, $\\rho_G={rho_global:g}$"
    )
    axis.grid(True, alpha=0.22)
    axis.legend(frameon=False)
    axis.text(
        0.02,
        0.04,
        f"MAE={metrics['mae']:.3f}   bias={metrics['bias']:+.3f}",
        transform=axis.transAxes,
        fontsize=9,
        alpha=0.75,
    )
    figure.tight_layout()
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run_real_trace_diagnostic(
    *,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    provider_root: Path,
    i1_contract_path: Path,
    local_regions_path: Path,
    rho_global: float,
    output_directory: Path,
) -> pd.DataFrame:
    """Run the complete real-data probability-composition diagnostic."""
    horizons, rho_support, workload = load_i1_contract_support(
        i1_contract_path, rho_global
    )
    stop_time = float(workload["horizon_max"])

    if not whitebox_ledger_path.exists():
        raise FileNotFoundError(f"missing white-box ledger: {whitebox_ledger_path}")
    all_top_level_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(all_top_level_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("white-box diagnostic expects exactly 100 trajectories")

    whitebox_manifest = _read_json(whitebox_manifest_path)
    if whitebox_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")

    local_regions = load_explicit_local_regions(local_regions_path)
    provider_ledgers = load_provider_evidence(provider_root)
    provider_surfaces = build_real_i1_surfaces(
        provider_ledgers,
        local_regions,
        rho_support,
        horizons,
        workload,
    )
    m0_curve = build_same_rho_m0_curve(
        provider_surfaces, rho_global, horizons
    )

    # Provider-only boundary is useful bookkeeping but is not the full graph
    # A_G^M0. This diagnostic never invents deterministic stage/network terms.
    provider_only_boundary = compose_parallel_all(
        [local_regions[provider] for provider in PROVIDERS]
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    provider_surface_table = pd.concat(
        [provider_surfaces[provider] for provider in PROVIDERS],
        ignore_index=True,
    )
    provider_surface_table.to_csv(
        output_directory / "real_i1_provider_surfaces.csv", index=False
    )
    m0_curve.to_csv(
        output_directory / "real_i1_m0_probability_curve.csv", index=False
    )

    all_comparisons: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    by_role = {
        str(whitebox["selection_role"]): whitebox
        for whitebox in whitebox_manifest["whiteboxes"]
    }

    for role in ROLE_ORDER:
        if role not in by_role:
            raise RuntimeError(f"frozen white-box manifest lacks role {role}")
        whitebox = by_role[role]
        whitebox_curve = build_real_whitebox_curve(
            all_top_level_ledgers,
            whitebox,
            rho_global,
            horizons,
            stop_time,
        )
        comparison, metrics = compare_curves(whitebox_curve, m0_curve)
        comparison.insert(0, "selection_role", role)
        comparison.insert(0, "case_id", str(whitebox["case_id"]))
        all_comparisons.append(comparison)

        plot_name = (
            f"real_wb_vs_i1_m0_{role}_rho_{_rho_tag(rho_global)}.png"
        )
        plot_one_comparison(
            comparison,
            role,
            rho_global,
            metrics,
            output_directory / plot_name,
        )
        summary_rows.append(
            {
                "case_id": str(whitebox["case_id"]),
                "selection_role": role,
                "rho_global": float(rho_global),
                "whitebox_l_max": float(whitebox["l_max"]),
                "whitebox_c_max": float(whitebox["c_max"]),
                "whitebox_q_min": float(whitebox["q_min"]),
                **metrics,
                "plot": plot_name,
            }
        )

    comparison_table = pd.concat(all_comparisons, ignore_index=True)
    summary_table = pd.DataFrame(summary_rows)
    comparison_table.to_csv(
        output_directory / "real_wb_vs_i1_m0_curves.csv", index=False
    )
    summary_table.to_csv(
        output_directory / "real_wb_vs_i1_m0_summary.csv", index=False
    )

    diagnostic_manifest = {
        "status": "REAL_TRACE_DIAGNOSTIC_NOT_A_FREEZE_ARTIFACT",
        "rho_global": float(rho_global),
        "rho_policy": "rho_i=rho_G for all providers",
        "m0_probability_rule": "product_i sigma_i(A_i,H;rho_G)",
        "whitebox_source": str(whitebox_ledger_path),
        "provider_source_root": str(provider_root),
        "local_regions_source": str(local_regions_path),
        "local_regions": {
            provider: {
                "l_max": local_regions[provider].l_max,
                "c_max": local_regions[provider].c_max,
                "q_min": local_regions[provider].q_min,
            }
            for provider in PROVIDERS
        },
        "provider_only_parallel_boundary": {
            "l_max": provider_only_boundary.l_max,
            "c_max": provider_only_boundary.c_max,
            "q_min": provider_only_boundary.q_min,
        },
        "full_M0_boundary_applicability_asserted": False,
        "note": (
            "All sigma values are computed from real frozen trace banks. "
            "A_i values are caller-supplied and are not selected by this script. "
            "The plotted I1-M0 curve is the real probability-composition component; "
            "full numerical M0 additionally requires the separately frozen "
            "deterministic stage/network boundary adapter."
        ),
    }
    (output_directory / "real_wb_vs_i1_m0_diagnostic_manifest.json").write_text(
        json.dumps(diagnostic_manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_PASS")
    print("all_sigma_values_from_real_frozen_trace_banks=true")
    print("A_i_selected_by_diagnostic=false")
    print("rho_policy=rho_i_equals_rho_G")
    print("full_M0_boundary_applicability_asserted=false")
    print(summary_table.to_string(index=False))
    print(f"output={output_directory.resolve()}")
    return summary_table


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plot real Phase-1 white-box sigma against real I1-M0 "
            "same-rho probability composition."
        )
    )
    parser.add_argument(
        "--local-regions-json",
        type=Path,
        required=True,
        help="Explicit ProviderA/B/C A_i values. This script never derives A_i.",
    )
    parser.add_argument("--rho", type=float, default=0.95)
    parser.add_argument(
        "--whitebox-ledgers",
        type=Path,
        default=PHASE1_DIRECTORY
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--whitebox-manifest",
        type=Path,
        default=PHASE1_DIRECTORY / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--provider-root",
        type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_acquisition_v1" / "private",
    )
    parser.add_argument(
        "--i1-contract",
        type=Path,
        default=PHASE2_DIRECTORY / "config_phase2_i1_provider_card_v2.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Default is rho-specific under phase3/results.",
    )
    args = parser.parse_args()

    output = args.output
    if output is None:
        output = (
            PHASE3_DIRECTORY
            / "results"
            / f"real_wb_vs_i1_m0_rho_{_rho_tag(float(args.rho))}"
        )

    run_real_trace_diagnostic(
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        whitebox_manifest_path=args.whitebox_manifest.resolve(),
        provider_root=args.provider_root.resolve(),
        i1_contract_path=args.i1_contract.resolve(),
        local_regions_path=args.local_regions_json.resolve(),
        rho_global=float(args.rho),
        output_directory=output.resolve(),
    )


if __name__ == "__main__":
    main()
