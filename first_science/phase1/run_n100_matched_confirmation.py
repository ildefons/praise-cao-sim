"""Run fresh paired N=100 confirmation for frozen SLA-based Phase-1 whiteboxes.

All selected white boxes must share one physical regime. One common bank of 100
fresh AICon/YAFS trajectories is therefore generated and evaluated against all
three frozen admissibility regions. A and rho are never recalibrated on N=100.

The scientific sigma is sigma_G(A,H,rho*=0.95)=P(c_G(A,H)>=0.95), where every H
uses cumulative request accounting over [0,H] from the prescribed t=0 origin.
The output includes request decisions, trajectory compliance curves, empirical
sigma curves, exact transition-time steps, confirmation summaries and plots.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from presearch_contract import assert_phase1_confirmation_configuration_is_ready
from selection_policy import (
    classify_lc_failure_role,
    load_sla_compliance_area_selection_policy,
)
from sla_compliance_analysis import (
    calculate_empirical_sla_sigma_from_ledgers,
    calculate_exact_empirical_sla_compliance_area,
    calculate_exact_sla_sigma_step_curve,
    calculate_pointwise_sigma_standard_error,
    summarize_request_level_sla_outcomes,
)


def load_and_validate_confirmation_inputs(
    configuration_path: Path,
    selected_whiteboxes_path: Path,
) -> tuple[dict, dict]:
    """Load and validate frozen paired N=100 SLA confirmation inputs.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
        - simulator-independent tests of confirmation input validation.
    """
    configuration = json.loads(
        configuration_path.read_text(encoding="utf-8")
    )
    manifest = json.loads(
        selected_whiteboxes_path.read_text(encoding="utf-8")
    )
    assert_phase1_confirmation_configuration_is_ready(
        configuration, manifest
    )
    if manifest.get("paired_matched_physical_regime") is not True:
        raise ValueError(
            "N=100 matched runner requires paired_matched_physical_regime=true"
        )
    whiteboxes = manifest["whiteboxes"]
    if {
        str(item["selection_role"]) for item in whiteboxes
    } != {"latency", "mixed", "cost"}:
        raise ValueError(
            "matched confirmation requires latency, mixed and cost cases"
        )
    physical_keys = {
        (
            str(item["physical_setting_id"]),
            float(item["center_instruction_mean"]),
            float(item["dispersion"]),
        )
        for item in whiteboxes
    }
    if len(physical_keys) != 1:
        raise ValueError(
            "all matched N=100 cases must share one physical regime"
        )
    return configuration, manifest


def execute_shared_physical_n100_trajectories(
    configuration: dict,
    manifest: dict,
    output_directory: Path,
) -> pd.DataFrame:
    """Execute exactly 100 fresh trajectories for the common physical regime.

    Native AICon/YAFS is imported lazily so all SLA analysis/tests remain
    simulator-independent.

    Side effects:
        Runs AICon/YAFS and writes raw trajectory directories plus the combined
        top-level request ledger.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
    """
    from whitebox_atlas import execute_one_whitebox_trajectory

    reference_case = manifest["whiteboxes"][0]
    center = float(reference_case["center_instruction_mean"])
    dispersion = float(reference_case["dispersion"])
    setting_id = str(reference_case["physical_setting_id"])
    seeds = list(
        map(int, configuration["confirmation"]["confirmation_seed_bank"])
    )
    if len(seeds) != 100 or len(set(seeds)) != 100:
        raise ValueError(
            "paired N=100 confirmation requires 100 unique seeds"
        )

    all_ledgers: list[pd.DataFrame] = []
    for trajectory_index, seed in enumerate(seeds):
        trajectory_directory = (
            output_directory
            / "trajectories"
            / setting_id
            / f"trajectory_{trajectory_index:03d}_seed_{seed}"
        )
        ledger = execute_one_whitebox_trajectory(
            configuration,
            center_instruction_mean=center,
            dispersion=dispersion,
            trajectory_seed=seed,
            trajectory_output_directory=trajectory_directory,
        )
        ledger.insert(0, "trajectory", trajectory_index)
        ledger.insert(0, "dispersion", dispersion)
        ledger.insert(0, "center_instruction_mean", center)
        ledger.insert(0, "physical_setting_id", setting_id)
        all_ledgers.append(ledger)

    combined = pd.concat(all_ledgers, ignore_index=True)
    combined.to_csv(
        output_directory / "all_top_level_request_ledgers.csv",
        index=False,
    )
    return combined


def _extract_decision_tables_by_trajectory(
    all_request_decisions: pd.DataFrame,
) -> list[pd.DataFrame]:
    """Split one case's detailed decisions into trajectory-local tables.

    Called by:
        - ``analyze_and_plot_n100_confirmation`` in this module.
    """
    return [
        group.drop(
            columns=[
                "case_id",
                "selection_role",
                "trajectory",
                "seed",
            ],
            errors="ignore",
        )
        for _, group in all_request_decisions.groupby(
            "trajectory", sort=True
        )
    ]


def _calculate_final_trajectory_compliance_fractions(
    trajectory_curves: pd.DataFrame,
    stop_time: float,
) -> pd.DataFrame:
    """Extract c_j(A,Hmax) for every trajectory.

    Called by:
        - ``analyze_and_plot_n100_confirmation`` in this module.
    """
    final = trajectory_curves[
        np.isclose(
            trajectory_curves["horizon"].astype(float),
            float(stop_time),
            atol=1e-12,
        )
    ].copy()
    if final.empty:
        raise ValueError(
            "trajectory compliance curves do not contain stop horizon"
        )
    return final[
        [
            "trajectory",
            "compliance_fraction",
            "sla_compliant",
            "decided_requests",
            "compliant_requests",
        ]
    ].copy()


def analyze_and_plot_n100_confirmation(
    configuration: dict,
    manifest: dict,
    all_ledgers: pd.DataFrame,
    output_directory: Path,
) -> pd.DataFrame:
    """Compute and visualize fresh N=100 SLA confirmation results.

    Side effects:
        Writes ``sla_request_decisions.csv``,
        ``trajectory_compliance_curves.csv``, ``sigma_curves.csv``,
        ``exact_sigma_steps.csv``, ``confirmation_summary.csv``,
        ``n100_matched_sla_sigma_curves.png`` and
        ``n100_final_trajectory_compliance_ecdf.png``.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
        - simulator-independent analysis tests.
    """
    policy = load_sla_compliance_area_selection_policy(configuration)
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    anchor_horizon = float(
        configuration["admissibility_calibration"]["anchor_horizon"]
    )
    horizons = list(map(float, configuration["horizon"]["grid"]))
    n_trajectories = int(
        all_ledgers["trajectory"].nunique()
    )
    if n_trajectories != 100:
        raise ValueError(
            f"expected 100 confirmation trajectories, found {n_trajectories}"
        )

    decision_frames: list[pd.DataFrame] = []
    trajectory_frames: list[pd.DataFrame] = []
    sigma_frames: list[pd.DataFrame] = []
    exact_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    final_fraction_frames: list[pd.DataFrame] = []

    sigma_figure, sigma_axis = plt.subplots(figsize=(8.0, 5.2))
    ecdf_figure, ecdf_axis = plt.subplots(figsize=(7.0, 5.2))
    labels = {
        "latency": "L-dominant",
        "mixed": "Mixed L/C",
        "cost": "C-dominant",
    }

    for whitebox in manifest["whiteboxes"]:
        sigma, trajectory_curves, decisions = (
            calculate_empirical_sla_sigma_from_ledgers(
                all_ledgers,
                latency_threshold=float(whitebox["l_max"]),
                cost_threshold=float(whitebox["c_max"]),
                quality_threshold=float(whitebox["q_min"]),
                horizons=horizons,
                stop_time=stop_time,
                sla_definition=policy.sla_definition,
            )
        )
        case_id = str(whitebox["case_id"])
        role = str(whitebox["selection_role"])
        for frame in (sigma, trajectory_curves, decisions):
            frame.insert(0, "selection_role", role)
            frame.insert(0, "case_id", case_id)
        decision_frames.append(decisions)
        trajectory_frames.append(trajectory_curves)
        sigma_frames.append(sigma)

        decision_tables = _extract_decision_tables_by_trajectory(decisions)
        exact = calculate_exact_sla_sigma_step_curve(
            decision_tables,
            policy.sla_definition,
            policy.horizon_min,
            policy.horizon_max,
        )
        exact.insert(0, "selection_role", role)
        exact.insert(0, "case_id", case_id)
        exact_frames.append(exact)

        area_seconds, normalized_area = (
            calculate_exact_empirical_sla_compliance_area(
                decision_tables,
                policy.sla_definition,
                policy.horizon_min,
                policy.horizon_max,
            )
        )
        request_summary = summarize_request_level_sla_outcomes(decisions)

        anchor_row = sigma.iloc[
            int(
                np.argmin(
                    np.abs(
                        sigma["horizon"].astype(float).to_numpy()
                        - anchor_horizon
                    )
                )
            )
        ]
        stop_row = sigma.iloc[
            int(
                np.argmin(
                    np.abs(
                        sigma["horizon"].astype(float).to_numpy()
                        - stop_time
                    )
                )
            )
        ]
        sigma_anchor = float(anchor_row["sigma"])
        sigma_stop = float(stop_row["sigma"])

        observed_role = classify_lc_failure_role(
            int(request_summary["latency_failure_count"]),
            int(request_summary["cost_failure_count"]),
            policy.dominance_ratio,
        )
        role_replication_pass = observed_role == role
        area_gate_pass = (
            normalized_area >= policy.area_min - 1e-12
            and normalized_area <= policy.area_max + 1e-12
        )

        final_fractions = (
            _calculate_final_trajectory_compliance_fractions(
                trajectory_curves, stop_time
            )
        )
        final_fractions.insert(0, "selection_role", role)
        final_fractions.insert(0, "case_id", case_id)
        final_fraction_frames.append(final_fractions)

        summary_rows.append(
            {
                "case_id": case_id,
                "selection_role": role,
                "observed_request_failure_role": observed_role,
                "physical_setting_id": str(
                    whitebox["physical_setting_id"]
                ),
                "center_instruction_mean": float(
                    whitebox["center_instruction_mean"]
                ),
                "dispersion": float(whitebox["dispersion"]),
                "l_max": float(whitebox["l_max"]),
                "c_max": float(whitebox["c_max"]),
                "q_min": float(whitebox["q_min"]),
                "rho": float(policy.sla_definition.rho),
                "accounting_window": "cumulative_[0,H]_from_t0",
                "n_trajectories": n_trajectories,
                "normalized_sla_compliance_area": float(
                    normalized_area
                ),
                "sla_compliance_area_seconds": float(area_seconds),
                "area_gate_pass": bool(area_gate_pass),
                "sigma_120": sigma_anchor,
                "sigma_120_binomial_se": (
                    calculate_pointwise_sigma_standard_error(
                        sigma_anchor, n_trajectories
                    )
                ),
                "sigma_240": sigma_stop,
                "sigma_240_binomial_se": (
                    calculate_pointwise_sigma_standard_error(
                        sigma_stop, n_trajectories
                    )
                ),
                "mean_final_trajectory_compliance_fraction": float(
                    final_fractions["compliance_fraction"].mean()
                ),
                "median_final_trajectory_compliance_fraction": float(
                    final_fractions["compliance_fraction"].median()
                ),
                **request_summary,
                "role_replication_pass": bool(role_replication_pass),
                "scientific_confirmation_pass": bool(
                    area_gate_pass and role_replication_pass
                ),
            }
        )

        sigma_axis.step(
            exact["horizon"],
            exact["sigma"],
            where="post",
            linewidth=1.8,
            label=labels.get(role, role),
        )
        sigma_axis.plot(
            sigma["horizon"],
            sigma["sigma"],
            marker="o",
            linestyle="None",
            markersize=2.2,
            alpha=0.45,
        )

        sorted_fraction = np.sort(
            final_fractions["compliance_fraction"].astype(float).to_numpy()
        )
        ecdf_y = np.arange(1, len(sorted_fraction) + 1) / len(
            sorted_fraction
        )
        ecdf_axis.step(
            sorted_fraction,
            ecdf_y,
            where="post",
            linewidth=1.6,
            label=labels.get(role, role),
        )

    decisions_table = pd.concat(decision_frames, ignore_index=True)
    trajectories_table = pd.concat(
        trajectory_frames, ignore_index=True
    )
    sigma_table = pd.concat(sigma_frames, ignore_index=True)
    exact_table = pd.concat(exact_frames, ignore_index=True)
    final_fraction_table = pd.concat(
        final_fraction_frames, ignore_index=True
    )
    summary_table = pd.DataFrame(summary_rows)

    decisions_table.to_csv(
        output_directory / "sla_request_decisions.csv", index=False
    )
    trajectories_table.to_csv(
        output_directory / "trajectory_compliance_curves.csv",
        index=False,
    )
    sigma_table.to_csv(
        output_directory / "sigma_curves.csv", index=False
    )
    exact_table.to_csv(
        output_directory / "exact_sigma_steps.csv", index=False
    )
    final_fraction_table.to_csv(
        output_directory / "final_trajectory_compliance.csv",
        index=False,
    )
    summary_table.to_csv(
        output_directory / "confirmation_summary.csv", index=False
    )

    sigma_axis.set_xlim(policy.horizon_min, policy.horizon_max)
    sigma_axis.set_ylim(0.0, 1.02)
    sigma_axis.set_xlabel("Horizon H since t=0")
    sigma_axis.set_ylabel(
        f"Empirical SLA compliance probability σ(H; ρ={policy.sla_definition.rho:.2f})"
    )
    sigma_axis.set_title(
        "Fresh N=100 matched white-box SLA-compliance curves"
    )
    sigma_axis.grid(True, alpha=0.25)
    sigma_axis.legend()
    sigma_figure.tight_layout()
    sigma_plot_path = (
        output_directory / "n100_matched_sla_sigma_curves.png"
    )
    sigma_figure.savefig(sigma_plot_path, dpi=180)
    plt.close(sigma_figure)

    ecdf_axis.axvline(
        float(policy.sla_definition.rho),
        linestyle=":",
        linewidth=1.2,
        label=f"ρ={policy.sla_definition.rho:.2f}",
    )
    ecdf_axis.set_xlim(0.0, 1.01)
    ecdf_axis.set_ylim(0.0, 1.02)
    ecdf_axis.set_xlabel(
        f"Final trajectory request compliance c_j(A,{stop_time:g})"
    )
    ecdf_axis.set_ylabel("Empirical cumulative fraction of trajectories")
    ecdf_axis.set_title(
        "N=100 final trajectory compliance distribution"
    )
    ecdf_axis.grid(True, alpha=0.25)
    ecdf_axis.legend()
    ecdf_figure.tight_layout()
    ecdf_plot_path = (
        output_directory
        / "n100_final_trajectory_compliance_ecdf.png"
    )
    ecdf_figure.savefig(ecdf_plot_path, dpi=180)
    plt.close(ecdf_figure)

    overall = bool(
        summary_table["scientific_confirmation_pass"].all()
    )
    print("PHASE1_N100_SLA_CONFIRMATION_ANALYSIS_PASS")
    print(summary_table.to_string(index=False))
    print(f"scientific_confirmation_pass={str(overall).lower()}")
    print(f"sigma_plot={sigma_plot_path}")
    print(f"compliance_ecdf={ecdf_plot_path}")
    return summary_table


def execute_n100_matched_confirmation(
    configuration_path: Path,
    selected_whiteboxes_path: Path,
    output_directory: Path,
    clean: bool,
) -> pd.DataFrame:
    """Execute and analyze frozen fresh N=100 SLA confirmation.

    Side effects:
        Runs native simulation, saves frozen inputs, writes all SLA confirmation
        diagnostics and plots.

    Called by:
        - ``main`` in this module.
    """
    configuration, manifest = load_and_validate_confirmation_inputs(
        configuration_path, selected_whiteboxes_path
    )
    if clean and output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_config.json").write_text(
        json.dumps(configuration, indent=2), encoding="utf-8"
    )
    (
        output_directory / "selected_whiteboxes_frozen.json"
    ).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ledgers = execute_shared_physical_n100_trajectories(
        configuration, manifest, output_directory
    )
    summary = analyze_and_plot_n100_confirmation(
        configuration, manifest, ledgers, output_directory
    )
    print(
        "PHASE1_N100_SLA_CONFIRMATION_RUN_PASS",
        "n_physical_trajectories=100",
        "n_frozen_A=3",
        f"rho={configuration['sla_compliance']['search_rho']}",
        "accounting=cumulative_[0,H]_from_t0",
        f"output_directory={output_directory}",
    )
    return summary


def main() -> None:
    """Command-line entry point for paired fresh N=100 SLA confirmation.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--selected",
        type=Path,
        default=module_directory / "selected_whiteboxes.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory
        / "results"
        / "n100_sla_confirmation",
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    execute_n100_matched_confirmation(
        args.config.resolve(),
        args.selected.resolve(),
        args.output.resolve(),
        clean=bool(args.clean),
    )


if __name__ == "__main__":
    main()
