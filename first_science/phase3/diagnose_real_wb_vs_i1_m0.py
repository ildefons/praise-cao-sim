"""Real-trace diagnostic for white-box sigma versus the I1-M0 baseline.

Scientific inputs
-----------------
* White-box truth: frozen Phase-1 v2 fresh-confirmation top-level ledgers.
* Provider information: frozen Phase-2 provider-local acquisition ledgers T_i.
* I1 A_i calibration: frozen coordinate-wise 0.95-at-120 rule.
* M0 probability rule: rho_i = rho_G and product_i sigma_i(A_i,H;rho_G).

There is no external A_i input. Phase 2 derives each rectangular A_i from its
own T_i.  Under the current cumulative-admissibility semantics the recovered
anchor calibration uses rho_anchor=0.95, H*=120 s and sigma_target=0.95.  Each
coordinate is calibrated separately by the first sigma crossing rule and the
three thresholds are then combined.  The resulting joint local sigma is a
measured outcome, not another calibration target.

The plotted probability curve is the real M0 probability-composition component.
This diagnostic does not claim the separate full-graph boundary-applicability
check, which also requires deterministic pre/post/network boundary terms.
"""
from __future__ import annotations

import argparse
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

from i1_local_region import derive_local_regions_from_traces  # noqa: E402
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
SNAPSHOT_HORIZONS = (0.0, 60.0, 120.0, 180.0, 240.0)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rho_tag(rho: float) -> str:
    return f"{float(rho):.6f}".rstrip("0").rstrip(".").replace(".", "p")


def load_i1_contract_support(
    contract_path: Path,
    rho_global: float,
) -> tuple[list[float], list[float], dict[str, object], dict[str, object]]:
    """Return frozen I1 H/R support, workload, and A_i calibration contract."""
    contract = _read_json(contract_path)
    if contract.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_TRACE":
        raise ValueError("unexpected Phase-2 I1 card contract status")
    horizons = [float(value) for value in contract["H"]["values"]]
    rho_support = [float(value) for value in contract["R"]["values"]]
    if not any(abs(float(rho_global) - rho) <= EVENT_TOLERANCE for rho in rho_support):
        raise ValueError(
            f"rho_G={rho_global:g} is not present in frozen I1 support {rho_support}"
        )
    ai_contract = contract["A_i"]
    if ai_contract.get("status") != "FROZEN_TRACE_COORDINATE_SIGMA_CALIBRATION_V1":
        raise ValueError("unexpected frozen A_i calibration rule")
    calibration = dict(ai_contract["calibration"])
    return horizons, rho_support, dict(contract["workload_contract"]), calibration


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
    local_regions: dict[str, dict[str, object]],
    rho_support: list[float],
    horizons: list[float],
    workload_contract: dict[str, object],
) -> dict[str, pd.DataFrame]:
    """Build in-memory I1 surfaces from real provider traces and derived A_i."""
    stop_time = float(workload_contract["horizon_max"])
    workload = {
        "period": float(workload_contract["period"]),
        "accounting_origin": float(workload_contract["accounting_origin"]),
        "horizon_max": stop_time,
    }
    surfaces: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        _, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=provider_ledgers[provider],
            local_regions=[local_regions[provider]],
            rho_values=rho_support,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract=workload,
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
                    f"expected one I1 point for {provider}, H={horizon:g}, rho={rho_global:g}"
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
    """Recompute one Phase-1 white-box sigma curve on the common H grid."""
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
    return sigma[["horizon", "sigma"]].rename(columns={"sigma": "sigma_whitebox"})


def compare_curves(
    whitebox_curve: pd.DataFrame,
    m0_curve: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Align WB/M0 points and compute pointwise diagnostic errors."""
    comparison = whitebox_curve.merge(m0_curve, on="horizon", how="inner", validate="one_to_one")
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
    """Write one minimalist real-trace diagnostic plot."""
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
    axis.set_xlim(float(comparison["horizon"].min()), float(comparison["horizon"].max()))
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel("Horizon H (s)")
    axis.set_ylabel("Admissibility probability")
    axis.set_title(
        f"{ROLE_TITLES.get(role, role)}: white-box vs I1-M0\n"
        f"Real frozen trace banks, $\\rho_G={rho_global:g}$"
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


def _snapshot_rows(comparison_table: pd.DataFrame) -> pd.DataFrame:
    """Return WB/I1-M0 sigma values at five diagnostic horizons."""
    mask = np.zeros(len(comparison_table), dtype=bool)
    horizons = comparison_table["horizon"].astype(float).to_numpy()
    for target in SNAPSHOT_HORIZONS:
        mask |= np.isclose(horizons, target, atol=EVENT_TOLERANCE)
    columns = [
        "selection_role",
        "horizon",
        "sigma_whitebox",
        "sigma_i1_m0",
        "sigma_ProviderA",
        "sigma_ProviderB",
        "sigma_ProviderC",
        "error_m0_minus_wb",
    ]
    return comparison_table.loc[mask, columns].sort_values(
        ["selection_role", "horizon"]
    )


def _add_joint_anchor_sigma_diagnostic(
    region_table: pd.DataFrame,
    provider_surfaces: dict[str, pd.DataFrame],
    rho_anchor: float,
    anchor_horizon: float,
) -> pd.DataFrame:
    """Attach the resulting joint-card sigma at the calibration anchor."""
    table = region_table.copy()
    values: dict[str, float] = {}
    for provider in PROVIDERS:
        surface = provider_surfaces[provider]
        selected = surface[
            np.isclose(surface["rho"].astype(float), float(rho_anchor), atol=EVENT_TOLERANCE)
            & np.isclose(surface["horizon"].astype(float), float(anchor_horizon), atol=EVENT_TOLERANCE)
        ]
        if len(selected) != 1:
            raise RuntimeError(f"missing joint anchor sigma for {provider}")
        values[provider] = float(selected.iloc[0]["sigma_hat"])
    table["joint_sigma_at_H_star"] = table["provider"].map(values)
    return table


def run_real_trace_diagnostic(
    *,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    provider_root: Path,
    i1_contract_path: Path,
    rho_global: float,
    output_directory: Path,
) -> pd.DataFrame:
    """Run the complete real-data WB versus I1-M0 diagnostic."""
    horizons, rho_support, workload, ai_calibration = load_i1_contract_support(
        i1_contract_path, rho_global
    )
    stop_time = float(workload["horizon_max"])
    rho_anchor = float(ai_calibration["rho_anchor"])
    anchor_horizon = float(ai_calibration["H_star"])
    sigma_target = float(ai_calibration["sigma_target"])

    if not whitebox_ledger_path.exists():
        raise FileNotFoundError(f"missing white-box ledger: {whitebox_ledger_path}")
    all_top_level_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(all_top_level_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("white-box diagnostic expects exactly 100 trajectories")

    whitebox_manifest = _read_json(whitebox_manifest_path)
    if whitebox_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")

    provider_ledgers = load_provider_evidence(provider_root)
    local_regions, region_table = derive_local_regions_from_traces(
        provider_ledgers,
        rho_anchor=rho_anchor,
        horizons=horizons,
        stop_time=stop_time,
        anchor_horizon=anchor_horizon,
        sigma_target=sigma_target,
    )

    provider_surfaces = build_real_i1_surfaces(
        provider_ledgers,
        local_regions,
        rho_support,
        horizons,
        workload,
    )
    region_table = _add_joint_anchor_sigma_diagnostic(
        region_table,
        provider_surfaces,
        rho_anchor,
        anchor_horizon,
    )
    m0_curve = build_same_rho_m0_curve(provider_surfaces, rho_global, horizons)

    provider_only_boundaries = {
        provider: AdmissibilityBoundary(
            l_max=float(local_regions[provider]["l_max"]),
            c_max=float(local_regions[provider]["c_max"]),
            q_min=float(local_regions[provider]["q_min"]),
        )
        for provider in PROVIDERS
    }
    provider_only_boundary = compose_parallel_all(
        [provider_only_boundaries[provider] for provider in PROVIDERS]
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    region_table.to_csv(output_directory / "derived_local_A_i.csv", index=False)
    pd.concat(
        [provider_surfaces[provider] for provider in PROVIDERS], ignore_index=True
    ).to_csv(output_directory / "real_i1_provider_surfaces.csv", index=False)
    m0_curve.to_csv(output_directory / "real_i1_m0_probability_curve.csv", index=False)

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

        plot_name = f"real_wb_vs_i1_m0_{role}_rho_{_rho_tag(rho_global)}.png"
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
                **metrics,
                "plot": plot_name,
            }
        )

    comparison_table = pd.concat(all_comparisons, ignore_index=True)
    summary_table = pd.DataFrame(summary_rows)
    comparison_table.to_csv(output_directory / "real_wb_vs_i1_m0_curves.csv", index=False)
    summary_table.to_csv(output_directory / "real_wb_vs_i1_m0_summary.csv", index=False)
    snapshot = _snapshot_rows(comparison_table)
    snapshot.to_csv(output_directory / "real_wb_vs_i1_m0_sigma_snapshot.csv", index=False)

    diagnostic_manifest = {
        "status": "REAL_TRACE_DIAGNOSTIC_NOT_A_FREEZE_ARTIFACT",
        "rho_global_evaluated": float(rho_global),
        "A_i_rule": {
            "inputs": ["provider-local trace bank T_i", "frozen anchor rho_G=0.95"],
            "rho_anchor": rho_anchor,
            "H_star": anchor_horizon,
            "sigma_target": sigma_target,
            "coordinate_selection": "first sigma crossing below target closest to H_star",
            "combine": "independently calibrated L/C/Q thresholds form the joint rectangle",
            "joint_sigma_forced_to_target": False,
            "external_A_i_input": False,
            "request_level_percentile_target": False,
        },
        "rho_policy": "M0 reads rho_i=rho_G for all providers at evaluation time",
        "m0_probability_rule": "product_i sigma_i(A_i,H;rho_G)",
        "whitebox_source": str(whitebox_ledger_path),
        "provider_source_root": str(provider_root),
        "derived_local_regions": {
            provider: {
                "l_max": float(local_regions[provider]["l_max"]),
                "c_max": float(local_regions[provider]["c_max"]),
                "q_min": float(local_regions[provider]["q_min"]),
            }
            for provider in PROVIDERS
        },
        "provider_only_parallel_boundary": {
            "l_max": provider_only_boundary.l_max,
            "c_max": provider_only_boundary.c_max,
            "q_min": provider_only_boundary.q_min,
        },
        "full_M0_boundary_applicability_asserted": False,
    }
    (output_directory / "real_wb_vs_i1_m0_diagnostic_manifest.json").write_text(
        json.dumps(diagnostic_manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_PASS")
    print("all_sigma_values_from_real_frozen_trace_banks=true")
    print("A_i_external_input=false")
    print(
        "A_i_rule=coordinate_first_sigma_crossing_below_0p95_closest_to_H120_"
        "using_anchor_rho_G_0p95"
    )
    print(f"A_i_calibration_rho_anchor={rho_anchor:g}")
    print(f"A_i_calibration_H_star={anchor_horizon:g}")
    print(f"A_i_calibration_sigma_target={sigma_target:g}")
    print("rho_policy=M0_rho_i_equals_evaluated_rho_G")
    print("\nDERIVED_LOCAL_A_I")
    print(region_table.to_string(index=False))
    print("\nSIGMA_SNAPSHOT")
    print(snapshot.to_string(index=False))
    print("\nERROR_SUMMARY")
    print(summary_table.to_string(index=False))
    print(f"\noutput={output_directory.resolve()}")
    return summary_table


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compute real Phase-1 white-box sigma and real I1-M0 sigma using "
            "the frozen Phase-2 coordinate-wise H*=120 A_i calibration."
        )
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
        rho_global=float(args.rho),
        output_directory=output.resolve(),
    )


if __name__ == "__main__":
    main()
