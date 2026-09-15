"""Run native graph-level M1-v2 prediction and compare with M0/WB.

Scientific ordering is enforced explicitly:

1. load only public I1, selected M1-v2 provider lifts, public G0 fixed terms;
2. run the native composed M1 graph and extract top-level request traces;
3. materialize sigma_G^M1 predictions for the same-rho diagonal;
4. only then, if requested, open the frozen Phase-1 graph-level white-box
   ledger and evaluate WB, I1-M0, and I1-M1 on the same induced A_G(rho).

The white-box ledger never participates in M1 parameter fitting or graph
prediction construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
for module_directory in (PHASE1, PHASE2):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    PROVIDERS,
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m1_graph_simulator_v2 import (  # noqa: E402
    GraphProviderSurrogate,
    execute_one_m1_graph_trajectory,
)
from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    calculate_empirical_sla_sigma_from_ledgers,
)

EXPECTED_GRAPH_CONTRACT_STATUS = (
    "IMPLEMENTATION_CANDIDATE_PHASE3_M1_GRAPH_PREDICTION_V2_NOT_FROZEN"
)
EXPECTED_M1_CONTRACT_STATUS = "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V2_NOT_FROZEN"
EXPECTED_M0_CONTRACT_STATUS = "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO"
EXPECTED_LIFT_STATUS = "M1_V2_JOINT_LOCAL_FIT_COMPLETE_NOT_FROZEN"
TOLERANCE = 1e-12


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
        ).strip()
    except Exception:
        return None


def _common_workload_contract(
    metadata_by_provider: dict[str, dict[str, object]],
) -> dict[str, float]:
    values: list[tuple[float, float, float]] = []
    for provider in PROVIDERS:
        workload = metadata_by_provider[provider].get("workload_contract")
        if not isinstance(workload, dict):
            raise ValueError(f"{provider} public I1 lacks workload_contract")
        values.append(
            (
                float(workload["period"]),
                float(workload["accounting_origin"]),
                float(workload["horizon_max"]),
            )
        )
    if len(set(values)) != 1:
        raise RuntimeError("public I1 provider workload contracts differ")
    period, accounting_origin, horizon_max = values[0]
    if period <= 0.0 or horizon_max <= 0.0:
        raise ValueError("public workload period/horizon must be positive")
    return {
        "period": period,
        "accounting_origin": accounting_origin,
        "horizon_max": horizon_max,
    }


def load_selected_provider_surrogates(
    lift_root: Path,
) -> tuple[dict[str, GraphProviderSurrogate], dict[str, dict[str, Any]], dict[str, str]]:
    """Load all three selected non-smoke M1-v2 lifts without any WB input."""
    surrogates: dict[str, GraphProviderSurrogate] = {}
    records: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for provider in PROVIDERS:
        path = lift_root / provider / "m1_v2_best.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {provider} full M1-v2 lift: {path}. "
                "Run the non-smoke provider lift before graph prediction."
            )
        record = _read_json(path)
        if record.get("status") != EXPECTED_LIFT_STATUS:
            raise ValueError(f"{provider} unexpected M1-v2 lift status")
        if bool(record.get("smoke_mode")):
            raise ValueError(f"{provider} graph prediction cannot use a smoke lift")
        if bool(record.get("graph_level_whitebox_used")):
            raise ValueError(f"{provider} lift violates the graph-WB firewall")
        boundary = record.get("boundary_diagnostics")
        if not isinstance(boundary, dict):
            raise ValueError(f"{provider} lift lacks boundary diagnostics")
        if bool(boundary.get("any_near_boundary")):
            raise ValueError(
                f"{provider} selected lift is near a search boundary; do not compose it yet"
            )
        parameters = record.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError(f"{provider} lift lacks parameters")
        surrogates[provider] = GraphProviderSurrogate(
            mean_service_time=float(parameters["mean_service_time"]),
            cost_rate=float(parameters["cost_rate"]),
            service_cv=float(parameters["service_cv"]),
        )
        records[provider] = record
        hashes[provider] = _sha256(path)
    return surrogates, records, hashes


def build_public_induced_global_boundary(
    provider_boundaries: dict[str, AdmissibilityBoundary],
    m0_contract: dict[str, Any],
) -> AdmissibilityBoundary:
    """Forward-compose A_i using only the public frozen deterministic G0 terms."""
    if set(provider_boundaries) != set(PROVIDERS):
        raise ValueError("provider_boundaries must contain ProviderA/B/C")
    adapter = dict(m0_contract["phase1_benchmark_adapter"])
    fixed = dict(adapter["fixed_terms_outside_provider_boundaries"])
    boundary = AdmissibilityBoundary(
        l_max=float(fixed["latency"])
        + max(float(provider_boundaries[p].l_max) for p in PROVIDERS),
        c_max=float(fixed["cost"])
        + sum(float(provider_boundaries[p].c_max) for p in PROVIDERS),
        q_min=min(float(provider_boundaries[p].q_min) for p in PROVIDERS),
    )
    formula = dict(adapter["full_boundary_formula"])
    if "max_i" not in str(formula["latency"]):
        raise RuntimeError("public M0 latency formula is not the expected parallel-all rule")
    if "sum_i" not in str(formula["cost"]):
        raise RuntimeError("public M0 cost formula is not the expected additive rule")
    return boundary


def build_empirical_graph_sigma_curve(
    all_ledgers: pd.DataFrame,
    *,
    boundary: AdmissibilityBoundary,
    rho_global: float,
    horizons: list[float],
    stop_time: float,
    accounting_origin: float,
    output_column: str,
) -> pd.DataFrame:
    """Compute graph sigma from extracted top-level traces under one A_G/rho query."""
    definition = SlaComplianceDefinition(
        rho=float(rho_global),
        accounting_origin=float(accounting_origin),
        zero_decision_compliance=1.0,
    )
    sigma, _, _ = calculate_empirical_sla_sigma_from_ledgers(
        all_ledgers,
        latency_threshold=float(boundary.l_max),
        cost_threshold=float(boundary.c_max),
        quality_threshold=float(boundary.q_min),
        horizons=horizons,
        stop_time=float(stop_time),
        sla_definition=definition,
    )
    return sigma[["horizon", "sigma"]].rename(columns={"sigma": output_column})


def _curve_metrics(
    frame: pd.DataFrame,
    prediction_column: str,
    truth_column: str,
) -> dict[str, float]:
    error = (
        frame[prediction_column].astype(float) - frame[truth_column].astype(float)
    ).to_numpy(dtype=float)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def _plot_same_region_three_way(
    curves: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    rho_values = sorted(curves["rho_global"].astype(float).unique())
    figure, axes = plt.subplots(2, 3, figsize=(13.2, 7.5), sharex=True, sharey=True)
    flat_axes = list(axes.flat)
    for axis, rho in zip(flat_axes, rho_values):
        selected = curves[
            np.isclose(
                curves["rho_global"].astype(float),
                float(rho),
                atol=TOLERANCE,
                rtol=0.0,
            )
        ].sort_values("horizon")
        row = summary[
            np.isclose(
                summary["rho_global"].astype(float),
                float(rho),
                atol=TOLERANCE,
                rtol=0.0,
            )
        ].iloc[0]
        axis.plot(
            selected["horizon"],
            selected["sigma_whitebox_same_region"],
            linewidth=2.2,
            label=r"White-box $\sigma_G$",
        )
        axis.plot(
            selected["horizon"],
            selected["sigma_i1_m0"],
            linewidth=1.9,
            linestyle="--",
            label=r"I1-M0 $\hat{\sigma}_G$",
        )
        axis.plot(
            selected["horizon"],
            selected["sigma_i1_m1"],
            linewidth=1.9,
            linestyle=":",
            label=r"I1-M1 $\hat{\sigma}_G$",
        )
        axis.set_title(
            rf"$\rho={rho:g}$  MAE M0={float(row['m0_mae']):.3f}, M1={float(row['m1_mae']):.3f}"
        )
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.22)
    for axis in flat_axes[len(rho_values):]:
        axis.axis("off")
    flat_axes[0].legend(frameon=False, fontsize=9)
    figure.suptitle(
        r"Same-region graph prediction: white-box vs I1-M0 vs I1-M1",
        fontsize=14,
    )
    figure.supxlabel("Horizon H (s)")
    figure.supylabel("Admissibility probability")
    figure.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run_graph_prediction(
    *,
    graph_contract_path: Path,
    m1_contract_path: Path,
    m0_contract_path: Path,
    i1_card_root: Path,
    i1_manifest_path: Path,
    lift_root: Path,
    whitebox_ledger_path: Path,
    output_directory: Path,
    smoke: bool,
    evaluate_whitebox: bool,
) -> dict[str, Any]:
    graph_contract = _read_json(graph_contract_path)
    m1_contract = _read_json(m1_contract_path)
    m0_contract = _read_json(m0_contract_path)
    if graph_contract.get("status") != EXPECTED_GRAPH_CONTRACT_STATUS:
        raise ValueError("unexpected M1-v2 graph prediction contract status")
    if m1_contract.get("status") != EXPECTED_M1_CONTRACT_STATUS:
        raise ValueError("unexpected M1-v2 provider lift contract status")
    if m0_contract.get("status") != EXPECTED_M0_CONTRACT_STATUS:
        raise ValueError("unexpected frozen M0 contract status")

    metadata, provider_surfaces, _ = load_rho_conditioned_i1_cards(
        i1_card_root, i1_manifest_path
    )
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    workload = _common_workload_contract(metadata)
    if abs(float(max(horizons)) - float(workload["horizon_max"])) > TOLERANCE:
        raise RuntimeError("public I1 Hmax and workload horizon_max disagree")

    provider_surrogates, lift_records, lift_hashes = load_selected_provider_surrogates(
        lift_root
    )
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    simulation_cfg = dict(graph_contract["graph_simulation"])
    seed_start = int(simulation_cfg["trajectory_seed_start"])
    seed_end = int(simulation_cfg["trajectory_seed_end_inclusive"])
    seeds = tuple(range(seed_start, seed_end + 1))
    if len(seeds) != int(simulation_cfg["n_trajectories"]):
        raise ValueError("graph simulation seed range does not match n_trajectories")
    if smoke:
        seeds = seeds[: int(simulation_cfg["smoke_n_trajectories"])]

    output_directory.mkdir(parents=True, exist_ok=True)
    trace_directory = output_directory / "traces"
    trace_directory.mkdir(parents=True, exist_ok=True)

    all_ledgers: list[pd.DataFrame] = []
    for trajectory_index, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            ledger = execute_one_m1_graph_trajectory(
                provider_surrogates=provider_surrogates,
                graph_spec=graph_spec,
                workload_period=float(workload["period"]),
                stop_time=float(workload["horizon_max"]),
                trajectory_seed=int(seed),
                canonical_ipt=canonical_ipt,
                execution_fraction=execution_fraction,
            )
        ledger.insert(0, "trajectory", int(trajectory_index))
        ledger.to_csv(
            trace_directory
            / f"trajectory_{trajectory_index:03d}_seed_{int(seed)}.csv",
            index=False,
        )
        all_ledgers.append(ledger)
        if (
            trajectory_index == 0
            or (trajectory_index + 1) % 10 == 0
            or trajectory_index + 1 == len(seeds)
        ):
            print(
                f"M1-v2 graph trajectories {trajectory_index + 1}/{len(seeds)}",
                flush=True,
            )

    combined_ledgers = pd.concat(all_ledgers, ignore_index=True)
    if int(combined_ledgers["trajectory"].nunique()) != len(seeds):
        raise RuntimeError("M1-v2 graph ledger lost trajectories")
    if combined_ledgers[["trajectory", "request_id"]].duplicated().any():
        raise RuntimeError("M1-v2 graph ledger contains duplicate trajectory/request ids")
    ledger_path = output_directory / "m1_graph_top_level_request_ledgers.csv"
    combined_ledgers.to_csv(ledger_path, index=False)

    # Form every M1 prediction before any graph-level white-box ledger is read.
    prediction_rows: list[pd.DataFrame] = []
    boundaries: dict[float, AdmissibilityBoundary] = {}
    for rho in rho_support:
        provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
        induced = build_public_induced_global_boundary(provider_boundaries, m0_contract)
        boundaries[float(rho)] = induced

        m0_curve = build_same_rho_conditioned_m0_curve(
            provider_surfaces,
            rho=float(rho),
            horizons=horizons,
        )
        m1_curve = build_empirical_graph_sigma_curve(
            combined_ledgers,
            boundary=induced,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column="sigma_i1_m1",
        )
        prediction = m0_curve.merge(
            m1_curve, on="horizon", how="inner", validate="one_to_one"
        )
        prediction.insert(1, "A_G_l_max", float(induced.l_max))
        prediction.insert(2, "A_G_c_max", float(induced.c_max))
        prediction.insert(3, "A_G_q_min", float(induced.q_min))
        prediction_rows.append(prediction)

    prediction_curves = pd.concat(prediction_rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)
    prediction_path = output_directory / "m1_graph_prediction_curves.csv"
    prediction_curves.to_csv(prediction_path, index=False)

    prediction_manifest = {
        "status": "PHASE3_M1_V2_GRAPH_PREDICTION_MATERIALIZED_NOT_FROZEN",
        "smoke_mode": bool(smoke),
        "providers": list(PROVIDERS),
        "n_graph_trajectories": len(seeds),
        "trajectory_seed_start": int(seeds[0]),
        "trajectory_seed_end_inclusive": int(seeds[-1]),
        "provider_parameters": {
            provider: {
                "mean_service_time": float(provider_surrogates[provider].mean_service_time),
                "cost_rate": float(provider_surrogates[provider].cost_rate),
                "service_cv": float(provider_surrogates[provider].service_cv),
                "lift_file_sha256": lift_hashes[provider],
                "selected_trial_number": int(lift_records[provider]["selected_trial_number"]),
            }
            for provider in PROVIDERS
        },
        "rho_values": [float(rho) for rho in rho_support],
        "A_G_by_rho": {
            str(float(rho)): {
                "l_max": float(boundaries[float(rho)].l_max),
                "c_max": float(boundaries[float(rho)].c_max),
                "q_min": float(boundaries[float(rho)].q_min),
            }
            for rho in rho_support
        },
        "graph_contract_sha256": _sha256(graph_contract_path),
        "m1_contract_sha256": _sha256(m1_contract_path),
        "m0_contract_sha256": _sha256(m0_contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "top_level_ledger_sha256": _sha256(ledger_path),
        "prediction_curves_sha256": _sha256(prediction_path),
        "graph_level_whitebox_used": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    prediction_manifest_path = output_directory / "m1_graph_prediction_manifest_v2.json"
    _write_json(prediction_manifest_path, prediction_manifest)
    print("M1_V2_GRAPH_PREDICTION_MATERIALIZED_BEFORE_WHITEBOX_PASS", flush=True)

    if not evaluate_whitebox:
        print("PHASE3_M1_V2_GRAPH_PREDICTION_COMPLETE_NOT_FROZEN")
        print(f"output={output_directory.resolve()}")
        return prediction_manifest

    # External evaluation begins only after the prediction and its manifest exist.
    if not whitebox_ledger_path.exists():
        raise FileNotFoundError(f"white-box evaluation ledger not found: {whitebox_ledger_path}")
    whitebox_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(whitebox_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("external WB evaluation expects exactly 100 trajectories")

    comparison_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, float]] = []
    for rho in rho_support:
        induced = boundaries[float(rho)]
        predicted = prediction_curves[
            np.isclose(
                prediction_curves["rho_global"].astype(float),
                float(rho),
                atol=TOLERANCE,
                rtol=0.0,
            )
        ].copy()
        wb_curve = build_empirical_graph_sigma_curve(
            whitebox_ledgers,
            boundary=induced,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column="sigma_whitebox_same_region",
        )
        comparison = predicted.merge(
            wb_curve, on="horizon", how="inner", validate="one_to_one"
        )
        m0_metrics = _curve_metrics(
            comparison, "sigma_i1_m0", "sigma_whitebox_same_region"
        )
        m1_metrics = _curve_metrics(
            comparison, "sigma_i1_m1", "sigma_whitebox_same_region"
        )
        comparison["error_m0_minus_whitebox"] = (
            comparison["sigma_i1_m0"] - comparison["sigma_whitebox_same_region"]
        )
        comparison["error_m1_minus_whitebox"] = (
            comparison["sigma_i1_m1"] - comparison["sigma_whitebox_same_region"]
        )
        comparison_rows.append(comparison)
        summary_rows.append(
            {
                "rho_global": float(rho),
                "A_G_l_max": float(induced.l_max),
                "A_G_c_max": float(induced.c_max),
                "A_G_q_min": float(induced.q_min),
                "m0_mae": float(m0_metrics["mae"]),
                "m0_rmse": float(m0_metrics["rmse"]),
                "m0_bias": float(m0_metrics["bias"]),
                "m0_max_abs_error": float(m0_metrics["max_abs_error"]),
                "m1_mae": float(m1_metrics["mae"]),
                "m1_rmse": float(m1_metrics["rmse"]),
                "m1_bias": float(m1_metrics["bias"]),
                "m1_max_abs_error": float(m1_metrics["max_abs_error"]),
                "mae_improvement_m0_minus_m1": float(
                    m0_metrics["mae"] - m1_metrics["mae"]
                ),
            }
        )

    comparison_curves = pd.concat(comparison_rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)
    summary = pd.DataFrame(summary_rows).sort_values("rho_global").reset_index(drop=True)
    comparison_path = output_directory / "i1_m0_m1_same_region_sigma_curves.csv"
    summary_path = output_directory / "i1_m0_m1_same_region_sigma_summary.csv"
    plot_path = output_directory / "i1_m0_m1_same_region_sigma.png"
    comparison_curves.to_csv(comparison_path, index=False)
    summary.to_csv(summary_path, index=False)
    _plot_same_region_three_way(comparison_curves, summary, plot_path)

    evaluation_manifest = {
        "status": "PHASE3_M1_V2_GRAPH_EXTERNAL_EVALUATION_NOT_FROZEN",
        "prediction_manifest_sha256": _sha256(prediction_manifest_path),
        "whitebox_ledger_sha256": _sha256(whitebox_ledger_path),
        "whitebox_used_only_after_prediction_materialized": True,
        "whitebox_used_for_parameter_selection": False,
        "same_region": True,
        "same_rho_diagonal": "rho_region=rho_query=rho_G",
        "n_whitebox_trajectories": 100,
        "comparison_curves": comparison_path.name,
        "summary": summary_path.name,
        "plot": plot_path.name,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    _write_json(
        output_directory / "m1_graph_external_evaluation_manifest_v2.json",
        evaluation_manifest,
    )

    print("PHASE3_M1_V2_GRAPH_EXTERNAL_EVALUATION_COMPLETE_NOT_FROZEN")
    print("M1_V2_GRAPH_WHITEBOX_FIREWALL_PASS")
    print("\nSAME_REGION_M0_VS_M1_SUMMARY")
    print(summary.to_string(index=False))
    print(f"\nplot={plot_path.resolve()}")
    print(f"output={output_directory.resolve()}")
    return evaluation_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run native M1-v2 G0 prediction, extract traces, and compare sigma curves"
    )
    parser.add_argument(
        "--graph-contract",
        type=Path,
        default=HERE / "config_phase3_m1_graph_prediction_v2.json",
    )
    parser.add_argument(
        "--m1-contract",
        type=Path,
        default=HERE / "config_phase3_m1_contract_v2.json",
    )
    parser.add_argument(
        "--m0-contract",
        type=Path,
        default=HERE / "config_phase3_m0_contract_v1.json",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument(
        "--lift-root",
        type=Path,
        default=HERE / "results" / "m1_provider_lift_v2_full",
    )
    parser.add_argument(
        "--whitebox-ledgers",
        type=Path,
        default=PHASE1
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m1_graph_prediction_v2",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run only the first few graph trajectories; not scientific evidence",
    )
    parser.add_argument(
        "--no-whitebox",
        action="store_true",
        help="materialize M1 graph prediction but skip external WB comparison",
    )
    args = parser.parse_args()

    run_graph_prediction(
        graph_contract_path=args.graph_contract.resolve(),
        m1_contract_path=args.m1_contract.resolve(),
        m0_contract_path=args.m0_contract.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_manifest_path=args.i1_manifest.resolve(),
        lift_root=args.lift_root.resolve(),
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        output_directory=args.output.resolve(),
        smoke=bool(args.smoke),
        evaluate_whitebox=not bool(args.no_whitebox),
    )


if __name__ == "__main__":
    main()
