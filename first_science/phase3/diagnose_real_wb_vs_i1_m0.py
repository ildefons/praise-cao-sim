"""Real-trace diagnostic for white-box sigma versus the I1-M0 baseline.

Scientific inputs
-----------------
* White-box truth: frozen Phase-1 v2 fresh-confirmation top-level ledgers.
* Provider information: frozen Phase-2 provider-local acquisition ledgers T_i.
* I1 A_i calibration: frozen coordinate-wise 0.95-at-120 first-crossing rule.
* M0 probability rule: rho_i = rho_G and product_i sigma_i(A_i,H;rho_G).
* M0 applicability: full frozen G0 boundary, including deterministic network,
  Fpre and Fpost terms, must be contained in the exogenous A_G.

There is no external A_i input. Phase 2 derives each rectangular A_i from its
own T_i. The resulting I1 cards are the same cards used at every evaluated rho.
The raw M0 probability product is retained for diagnostics, but it is reported
as an M0 prediction only when the full induced boundary A_G^M0 is contained in
the requested white-box A_G. Otherwise the case is explicitly NOT_APPLICABLE.
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
    boundary_is_sufficient_for_query,
    independent_product_probability,
    same_rho_as_global,
)
from m0_phase1_benchmark_adapter import (  # noqa: E402
    build_phase1_g0_full_m0_boundary,
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
    *,
    m0_applicable: bool = True,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Align WB/M0 points and suppress M0 prediction when not applicable."""
    comparison = whitebox_curve.merge(m0_curve, on="horizon", how="inner", validate="one_to_one")
    if comparison.empty or len(comparison) != len(m0_curve):
        raise RuntimeError("white-box and I1-M0 horizon supports do not align")

    comparison["sigma_i1_m0_raw_probability_component"] = comparison["sigma_i1_m0"].astype(float)
    if not m0_applicable:
        comparison["sigma_i1_m0"] = np.nan
        comparison["error_m0_minus_wb"] = np.nan
        return comparison, {
            "mae": float("nan"),
            "rmse": float("nan"),
            "bias": float("nan"),
            "max_abs_error": float("nan"),
        }

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


def _containment_failure_summary(
    induced: AdmissibilityBoundary,
    requested: AdmissibilityBoundary,
) -> str:
    """Return a compact explanation of failed M0 boundary containment."""
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
    """Write one minimalist real-trace diagnostic plot with applicability."""
    figure, axis = plt.subplots(figsize=(8.2, 5.1))
    axis.plot(
        comparison["horizon"],
        comparison["sigma_whitebox"],
        linewidth=2.0,
        label=r"White-box $\sigma_G$",
    )
    if m0_applicable:
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
    status_line = "M0 applicable" if m0_applicable else "M0 NOT APPLICABLE"
    axis.set_title(
        f"{ROLE_TITLES.get(role, role)}: white-box vs I1-M0\n"
        f"$\\rho_G={rho_global:g}$, {status_line}"
    )
    axis.grid(True, alpha=0.22)
    axis.legend(frameon=False)
    if m0_applicable:
        axis.text(
            0.02,
            0.04,
            f"MAE={metrics['mae']:.3f}   bias={metrics['bias']:+.3f}",
            transform=axis.transAxes,
            fontsize=9,
            alpha=0.75,
        )
    else:
        axis.text(
            0.02,
            0.04,
            f"I1-M0 not defined for this query\ncontainment failure: {containment_failure}",
            transform=axis.transAxes,
            fontsize=9,
            alpha=0.8,
        )
    figure.tight_layout()
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _snapshot_rows(comparison_table: pd.DataFrame) -> pd.DataFrame:
    """Return WB/I1-M0 values at five diagnostic horizons."""
    mask = np.zeros(len(comparison_table), dtype=bool)
    horizons = comparison_table["horizon"].astype(float).to_numpy()
    for target in SNAPSHOT_HORIZONS:
        mask |= np.isclose(horizons, target, atol=EVENT_TOLERANCE)
    columns = [
        "selection_role",
        "m0_status",
        "horizon",
        "sigma_whitebox",
        "sigma_i1_m0",
        "sigma_i1_m0_raw_probability_component",
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
    phase1_physical_config_path: Path,
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
    phase1_physical_config = _read_json(phase1_physical_config_path)
    if phase1_physical_config.get("configuration_status") != "SCIENTIFIC_DISCOVERY_V1_FROZEN":
        raise ValueError("unexpected Phase-1 frozen physical configuration")

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
    raw_m0_curve = build_same_rho_m0_curve(provider_surfaces, rho_global, horizons)

    provider_boundaries = {
        provider: AdmissibilityBoundary(
            l_max=float(local_regions[provider]["l_max"]),
            c_max=float(local_regions[provider]["c_max"]),
            q_min=float(local_regions[provider]["q_min"]),
        )
        for provider in PROVIDERS
    }
    induced_global_boundary, boundary_breakdown = build_phase1_g0_full_m0_boundary(
        phase1_physical_config,
        provider_boundaries,
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    region_table.to_csv(output_directory / "derived_local_A_i.csv", index=False)
    pd.concat(
        [provider_surfaces[provider] for provider in PROVIDERS], ignore_index=True
    ).to_csv(output_directory / "real_i1_provider_surfaces.csv", index=False)
    raw_m0_curve.to_csv(output_directory / "real_i1_m0_raw_probability_curve.csv", index=False)

    all_comparisons: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    applicability_manifest: dict[str, object] = {}
    by_role = {
        str(whitebox["selection_role"]): whitebox
        for whitebox in whitebox_manifest["whiteboxes"]
    }

    for role in ROLE_ORDER:
        if role not in by_role:
            raise RuntimeError(f"frozen white-box manifest lacks role {role}")
        whitebox = by_role[role]
        requested_boundary = AdmissibilityBoundary(
            l_max=float(whitebox["l_max"]),
            c_max=float(whitebox["c_max"]),
            q_min=float(whitebox["q_min"]),
        )
        applicable = boundary_is_sufficient_for_query(
            induced_global_boundary,
            requested_boundary,
        )
        status = "PREDICTED" if applicable else "NOT_APPLICABLE"
        containment_failure = _containment_failure_summary(
            induced_global_boundary,
            requested_boundary,
        )

        whitebox_curve = build_real_whitebox_curve(
            all_top_level_ledgers,
            whitebox,
            rho_global,
            horizons,
            stop_time,
        )
        comparison, metrics = compare_curves(
            whitebox_curve,
            raw_m0_curve,
            m0_applicable=applicable,
        )
        comparison.insert(0, "m0_status", status)
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
            m0_applicable=applicable,
            containment_failure=containment_failure,
        )
        summary_rows.append(
            {
                "case_id": str(whitebox["case_id"]),
                "selection_role": role,
                "rho_global": float(rho_global),
                "m0_status": status,
                "containment_failure": containment_failure,
                "induced_l_max": induced_global_boundary.l_max,
                "induced_c_max": induced_global_boundary.c_max,
                "induced_q_min": induced_global_boundary.q_min,
                "requested_l_max": requested_boundary.l_max,
                "requested_c_max": requested_boundary.c_max,
                "requested_q_min": requested_boundary.q_min,
                **metrics,
                "plot": plot_name,
            }
        )
        applicability_manifest[str(whitebox["case_id"])] = {
            "selection_role": role,
            "status": status,
            "containment_failure": containment_failure,
            "requested_A_G": {
                "l_max": requested_boundary.l_max,
                "c_max": requested_boundary.c_max,
                "q_min": requested_boundary.q_min,
            },
        }

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
        "phase1_physical_config": str(phase1_physical_config_path),
        "derived_local_regions": {
            provider: {
                "l_max": float(local_regions[provider]["l_max"]),
                "c_max": float(local_regions[provider]["c_max"]),
                "q_min": float(local_regions[provider]["q_min"]),
            }
            for provider in PROVIDERS
        },
        "full_M0_induced_boundary": {
            "l_max": induced_global_boundary.l_max,
            "c_max": induced_global_boundary.c_max,
            "q_min": induced_global_boundary.q_min,
        },
        "deterministic_boundary_breakdown": {
            "root_network_latency": boundary_breakdown.root_network_latency,
            "pre_service_latency": boundary_breakdown.pre_service_latency,
            "branch_network_latency": boundary_breakdown.branch_network_latency,
            "join_network_latency": boundary_breakdown.join_network_latency,
            "post_service_latency": boundary_breakdown.post_service_latency,
            "fixed_latency_outside_provider": boundary_breakdown.fixed_latency_outside_provider,
            "pre_service_cost": boundary_breakdown.pre_service_cost,
            "post_service_cost": boundary_breakdown.post_service_cost,
            "fixed_cost_outside_provider": boundary_breakdown.fixed_cost_outside_provider,
        },
        "full_M0_boundary_applicability_asserted": True,
        "case_applicability": applicability_manifest,
        "raw_probability_component_retained_when_not_applicable": True,
        "raw_probability_component_is_not_a_prediction_when_not_applicable": True,
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
    print("full_M0_boundary_applicability_asserted=true")
    print("\nDERIVED_LOCAL_A_I")
    print(region_table.to_string(index=False))
    print("\nFULL_M0_BOUNDARY")
    print(
        f"A_G_M0=(L<={induced_global_boundary.l_max:.15g}, "
        f"C<={induced_global_boundary.c_max:.15g}, "
        f"Q>={induced_global_boundary.q_min:.15g})"
    )
    print(
        f"fixed_latency_outside_provider={boundary_breakdown.fixed_latency_outside_provider:.15g} "
        f"fixed_cost_outside_provider={boundary_breakdown.fixed_cost_outside_provider:.15g}"
    )
    print("\nAPPLICABILITY")
    print(
        summary_table[
            [
                "case_id",
                "selection_role",
                "m0_status",
                "containment_failure",
                "requested_l_max",
                "requested_c_max",
                "requested_q_min",
            ]
        ].to_string(index=False)
    )
    print("\nSIGMA_SNAPSHOT")
    print(snapshot.to_string(index=False))
    print("\nERROR_SUMMARY")
    print(summary_table.to_string(index=False))
    print(f"\noutput={output_directory.resolve()}")
    return summary_table


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compute real Phase-1 white-box sigma and applicable I1-M0 sigma using "
            "the frozen Phase-2 A_i calibration and full Phase-1 G0 boundary."
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
        "--phase1-physical-config",
        type=Path,
        default=PHASE1_DIRECTORY / "config_phase1_discovery_v1.json",
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
        phase1_physical_config_path=args.phase1_physical_config.resolve(),
        provider_root=args.provider_root.resolve(),
        i1_contract_path=args.i1_contract.resolve(),
        rho_global=float(args.rho),
        output_directory=output.resolve(),
    )


if __name__ == "__main__":
    main()
