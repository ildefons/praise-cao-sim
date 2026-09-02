"""Run paired N=100 confirmation for the frozen matched Phase-1 whiteboxes.

All selected admissibility regions share one physical regime. Therefore one set
of 100 fresh native AICon/YAFS trajectories is generated and evaluated against
all three frozen A regions. The A thresholds are never recalibrated on N=100.
The module writes exact first-violation observations, reporting-grid sigma CSVs,
a compact confirmation summary, and one exact-event staircase plot.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from atlas_analysis import (
    FirstViolationObservation,
    calculate_empirical_survival_curve_from_first_violation_observations,
    calculate_first_violation_observation_for_trajectory,
)
from presearch_contract import assert_phase1_confirmation_configuration_is_ready
from whitebox_atlas import execute_one_whitebox_trajectory


def load_and_validate_confirmation_inputs(
    configuration_path: Path,
    selected_whiteboxes_path: Path,
) -> tuple[dict, dict]:
    """Load and validate the frozen paired N=100 confirmation specification.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
    """
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    manifest = json.loads(selected_whiteboxes_path.read_text(encoding="utf-8"))
    assert_phase1_confirmation_configuration_is_ready(configuration, manifest)
    if manifest.get("paired_matched_physical_regime") is not True:
        raise ValueError("N=100 matched runner requires paired_matched_physical_regime=true")
    whiteboxes = manifest["whiteboxes"]
    if {str(item["selection_role"]) for item in whiteboxes} != {"latency", "mixed", "cost"}:
        raise ValueError("matched confirmation requires latency, mixed, and cost cases")
    physical_keys = {
        (
            str(item["physical_setting_id"]),
            float(item["center_instruction_mean"]),
            float(item["dispersion"]),
        )
        for item in whiteboxes
    }
    if len(physical_keys) != 1:
        raise ValueError("all matched N=100 cases must share one physical regime")
    return configuration, manifest


def execute_shared_physical_n100_trajectories(
    configuration: dict,
    manifest: dict,
    output_directory: Path,
) -> pd.DataFrame:
    """Execute exactly 100 fresh trajectories for the common physical regime.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
    """
    reference_case = manifest["whiteboxes"][0]
    center = float(reference_case["center_instruction_mean"])
    dispersion = float(reference_case["dispersion"])
    setting_id = str(reference_case["physical_setting_id"])
    seeds = list(map(int, configuration["confirmation"]["confirmation_seed_bank"]))
    if len(seeds) != 100:
        raise ValueError("paired N=100 confirmation requires exactly 100 seeds")

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
    combined.to_csv(output_directory / "all_top_level_request_ledgers.csv", index=False)
    return combined


def calculate_case_observations(
    all_ledgers: pd.DataFrame,
    whitebox: dict,
    stop_time: float,
) -> list[tuple[int, int, FirstViolationObservation]]:
    """Evaluate one frozen A against every shared N=100 physical trajectory.

    Called by:
        - ``analyze_and_plot_n100_confirmation`` in this module.
    """
    labeled: list[tuple[int, int, FirstViolationObservation]] = []
    for trajectory, trajectory_ledger in all_ledgers.groupby("trajectory", sort=True):
        seed = int(trajectory_ledger["seed"].iloc[0])
        observation = calculate_first_violation_observation_for_trajectory(
            trajectory_ledger,
            latency_threshold=float(whitebox["l_max"]),
            cost_threshold=float(whitebox["c_max"]),
            quality_threshold=float(whitebox["q_min"]),
            stop_time=stop_time,
        )
        labeled.append((int(trajectory), seed, observation))
    if len(labeled) != 100:
        raise ValueError(f"expected 100 trajectory observations, got {len(labeled)}")
    return labeled


def build_exact_empirical_staircase(
    observations: list[FirstViolationObservation],
    stop_time: float,
) -> tuple[list[float], list[float]]:
    """Build exact-event coordinates for empirical P(T_violation > H).

    Called by:
        - ``analyze_and_plot_n100_confirmation`` in this module.
    """
    event_times = sorted(
        {
            float(observation.time)
            for observation in observations
            if observation.time is not None and 0.0 <= float(observation.time) <= stop_time
        }
    )
    horizons = [0.0] + [time for time in event_times if time > 0.0]
    if not horizons or horizons[-1] < stop_time:
        horizons.append(float(stop_time))
    sigma = [
        sum(observation.time is None or float(observation.time) > horizon for observation in observations)
        / len(observations)
        for horizon in horizons
    ]
    return horizons, sigma


def analyze_and_plot_n100_confirmation(
    configuration: dict,
    manifest: dict,
    all_ledgers: pd.DataFrame,
    output_directory: Path,
) -> pd.DataFrame:
    """Write N=100 sigma data, summaries, and the three-curve exact-event plot.

    Side effects:
        Writes ``first_violation_observations.csv``, ``sigma_curves.csv``,
        ``confirmation_summary.csv``, and ``n100_matched_sigma_curves.png``.

    Called by:
        - ``execute_n100_matched_confirmation`` in this module.
    """
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    anchor_horizon = float(configuration["admissibility_calibration"]["anchor_horizon"])
    reporting_horizons = list(map(float, configuration["horizon"]["grid"]))

    observation_rows: list[dict[str, object]] = []
    curve_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []

    figure, axis = plt.subplots(figsize=(8.0, 5.2))
    role_labels = {
        "latency": "L-dominant",
        "mixed": "Mixed L/C",
        "cost": "C-dominant",
    }

    for whitebox in manifest["whiteboxes"]:
        labeled = calculate_case_observations(all_ledgers, whitebox, stop_time)
        observations = [entry[2] for entry in labeled]
        for trajectory, seed, observation in labeled:
            observation_rows.append(
                {
                    "case_id": str(whitebox["case_id"]),
                    "selection_role": str(whitebox["selection_role"]),
                    "trajectory": trajectory,
                    "seed": seed,
                    "first_violation_time": (
                        float(observation.time) if observation.time is not None else float("nan")
                    ),
                    "first_violation_cause": observation.cause,
                }
            )

        curve = calculate_empirical_survival_curve_from_first_violation_observations(
            observations,
            horizons=reporting_horizons,
            stop_time=stop_time,
        )
        curve.insert(0, "selection_role", str(whitebox["selection_role"]))
        curve.insert(0, "case_id", str(whitebox["case_id"]))
        curve_rows.append(curve)

        sigma_anchor = float(
            curve.loc[(curve["horizon"] - anchor_horizon).abs().idxmin(), "sigma"]
        )
        sigma_stop = float(curve.loc[(curve["horizon"] - stop_time).abs().idxmin(), "sigma"])
        cause_counts = pd.Series([observation.cause for observation in observations]).value_counts()
        summary_rows.append(
            {
                "case_id": str(whitebox["case_id"]),
                "selection_role": str(whitebox["selection_role"]),
                "physical_setting_id": str(whitebox["physical_setting_id"]),
                "center_instruction_mean": float(whitebox["center_instruction_mean"]),
                "dispersion": float(whitebox["dispersion"]),
                "l_max": float(whitebox["l_max"]),
                "c_max": float(whitebox["c_max"]),
                "q_min": float(whitebox["q_min"]),
                "n_trajectories": 100,
                "sigma_120": sigma_anchor,
                "sigma_120_binomial_se": math.sqrt(sigma_anchor * (1.0 - sigma_anchor) / 100.0),
                "sigma_240": sigma_stop,
                "latency_first_count": int(cause_counts.get("latency", 0)),
                "cost_first_count": int(cause_counts.get("cost", 0)),
                "quality_first_count": int(cause_counts.get("quality", 0)),
                "tie_first_count": int(cause_counts.get("tie", 0)),
                "censored_count": int(cause_counts.get("censored", 0)),
                "n_unique_first_violation_times": int(
                    len({float(o.time) for o in observations if o.time is not None})
                ),
            }
        )

        exact_horizons, exact_sigma = build_exact_empirical_staircase(observations, stop_time)
        role = str(whitebox["selection_role"])
        axis.step(
            exact_horizons,
            exact_sigma,
            where="post",
            linewidth=1.8,
            label=role_labels.get(role, role),
        )

    observations_table = pd.DataFrame(observation_rows)
    curves_table = pd.concat(curve_rows, ignore_index=True)
    summary_table = pd.DataFrame(summary_rows)
    observations_table.to_csv(output_directory / "first_violation_observations.csv", index=False)
    curves_table.to_csv(output_directory / "sigma_curves.csv", index=False)
    summary_table.to_csv(output_directory / "confirmation_summary.csv", index=False)

    axis.set_xlim(0.0, stop_time)
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel("Horizon H")
    axis.set_ylabel("Empirical survival σ(H)")
    axis.set_title("N=100 matched white-box survival curves")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_directory / "n100_matched_sigma_curves.png", dpi=180)
    plt.close(figure)

    print("PHASE1_N100_MATCHED_CONFIRMATION_ANALYSIS_PASS")
    print(summary_table.to_string(index=False))
    print(f"plot={output_directory / 'n100_matched_sigma_curves.png'}")
    return summary_table


def execute_n100_matched_confirmation(
    configuration_path: Path,
    selected_whiteboxes_path: Path,
    output_directory: Path,
    clean: bool,
) -> pd.DataFrame:
    """Execute and analyze the frozen paired N=100 confirmation.

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
    (output_directory / "selected_whiteboxes_frozen.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ledgers = execute_shared_physical_n100_trajectories(
        configuration, manifest, output_directory
    )
    summary = analyze_and_plot_n100_confirmation(
        configuration, manifest, ledgers, output_directory
    )
    print(
        "PHASE1_N100_MATCHED_CONFIRMATION_RUN_PASS",
        "n_physical_trajectories=100",
        "n_frozen_A=3",
        f"output_directory={output_directory}",
    )
    return summary


def main() -> None:
    """Command-line entry point for paired N=100 confirmation and plotting."""
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
        default=module_directory / "results" / "n100_matched_confirmation",
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
