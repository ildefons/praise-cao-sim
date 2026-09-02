"""Augment Phase-1 discovery ARs with axes nonbinding through the full horizon.

The original Phase-1 scan is deliberately anchor-informed: its threshold grid is
constructed from H*=120 critical values. That is appropriate for anchor
calibration but the resulting finite "loose" threshold need not remain loose out
to H=240. This offline augmentation preserves every original AR and adds two
families useful for diagnostic white-box selection:

- full-domain-loose latency crossed with every original cost threshold;
- full-domain-loose cost crossed with every original latency threshold.

No AICon/YAFS simulation is rerun. The augmentation consumes the already frozen
N=10 discovery ledgers and uses the same first-violation and sigma semantics as
``atlas_analysis.py``. M0/M1 never enter the procedure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd

from atlas_analysis import (
    calculate_empirical_survival_curve_from_first_violation_observations,
    calculate_first_violation_observation_for_trajectory,
    select_representative_regions_for_each_achievable_anchor_survival,
)


def calculate_full_domain_critical_latency_for_trajectory(
    trajectory_request_ledger: pd.DataFrame,
    stop_time: float,
) -> float:
    """Return the minimum latency threshold with no known violation by stop.

    Completed requests contribute realized top-level latency. Requests emitted by
    stop but incomplete at stop contribute their age ``stop-emission``. A loose
    threshold is constructed above the maximum of these trajectory-level values.

    Called by:
        - ``calculate_full_domain_loose_thresholds`` in this module.
        - ``test_full_domain_loose_thresholds_exceed_late_requirements`` in
          ``test_augment_full_domain_loose_ar_axes.py``.
    """
    stop = float(stop_time)
    critical_values: list[float] = [0.0]
    for request in trajectory_request_ledger.itertuples(index=False):
        emission = float(request.emission)
        if emission > stop + 1e-12:
            continue
        completion = None if pd.isna(request.completion) else float(request.completion)
        if completion is not None and completion <= stop + 1e-12:
            critical_values.append(float(request.L))
        else:
            critical_values.append(max(0.0, stop - emission))
    return float(max(critical_values))


def calculate_full_domain_critical_cost_for_trajectory(
    trajectory_request_ledger: pd.DataFrame,
    stop_time: float,
) -> float:
    """Return the maximum cost observable by the simulator stop time.

    Cost is observable only at completion under the frozen event semantics.

    Called by:
        - ``calculate_full_domain_loose_thresholds`` in this module.
        - ``test_full_domain_loose_thresholds_exceed_late_requirements`` in
          ``test_augment_full_domain_loose_ar_axes.py``.
    """
    stop = float(stop_time)
    completed = trajectory_request_ledger[
        trajectory_request_ledger["completion"].notna()
        & (trajectory_request_ledger["completion"].astype(float) <= stop + 1e-12)
    ]
    if completed.empty:
        return 0.0
    return float(completed["C"].max())


def calculate_full_domain_loose_thresholds(
    physical_setting_request_ledger: pd.DataFrame,
    stop_time: float,
    loose_multiplier: float,
    relative_epsilon: float,
) -> tuple[float, float]:
    """Construct finite L/C thresholds nonbinding on all discovery trajectories.

    Args:
        physical_setting_request_ledger: All discovery trajectories for one
            physical setting.
        stop_time: Full declared sigma horizon endpoint.
        loose_multiplier: Frozen finite margin multiplier, currently 1.05.
        relative_epsilon: Frozen small threshold epsilon.

    Returns:
        ``(latency_loose, cost_loose)`` strictly above the largest observed
        full-domain critical values.

    Called by:
        - ``build_full_domain_loose_axis_regions_for_one_setting`` in this module.
        - unit tests in ``test_augment_full_domain_loose_ar_axes.py``.
    """
    grouped = list(physical_setting_request_ledger.groupby("trajectory", sort=True))
    if not grouped:
        raise ValueError("at least one trajectory is required")
    latency_critical = [
        calculate_full_domain_critical_latency_for_trajectory(ledger, stop_time)
        for _, ledger in grouped
    ]
    cost_critical = [
        calculate_full_domain_critical_cost_for_trajectory(ledger, stop_time)
        for _, ledger in grouped
    ]
    multiplier = float(loose_multiplier)
    epsilon = float(relative_epsilon)
    if multiplier <= 1.0:
        raise ValueError("loose_multiplier must be greater than one")
    latency_max = max(latency_critical)
    cost_max = max(cost_critical)
    latency_loose = latency_max * multiplier + epsilon * max(1.0, abs(latency_max))
    cost_loose = cost_max * multiplier + epsilon * max(1.0, abs(cost_max))
    return float(latency_loose), float(cost_loose)


def evaluate_one_augmented_region(
    physical_setting_request_ledger: pd.DataFrame,
    physical_setting_id: str,
    region_id: str,
    center_instruction_mean: float,
    dispersion: float,
    latency_threshold: float,
    cost_threshold: float,
    quality_threshold: float,
    anchor_horizon: float,
    horizons: list[float],
    stop_time: float,
    augmentation_type: str,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Evaluate one augmented AR using the frozen first-violation semantics.

    Called by:
        - ``build_full_domain_loose_axis_regions_for_one_setting`` in this module.
    """
    observations = [
        calculate_first_violation_observation_for_trajectory(
            trajectory_ledger,
            latency_threshold=latency_threshold,
            cost_threshold=cost_threshold,
            quality_threshold=quality_threshold,
            stop_time=stop_time,
        )
        for _, trajectory_ledger in physical_setting_request_ledger.groupby(
            "trajectory", sort=True
        )
    ]
    curve = calculate_empirical_survival_curve_from_first_violation_observations(
        observations,
        horizons=horizons,
        stop_time=stop_time,
    )
    anchor_rows = curve[(curve["horizon"].astype(float) - float(anchor_horizon)).abs() <= 1e-12]
    if len(anchor_rows) != 1:
        raise ValueError("anchor_horizon must occur exactly once in horizon grid")
    cause_counts = pd.Series([observation.cause for observation in observations]).value_counts()
    summary = {
        "physical_setting_id": str(physical_setting_id),
        "region_id": str(region_id),
        "center_instruction_mean": float(center_instruction_mean),
        "dispersion": float(dispersion),
        "l_max": float(latency_threshold),
        "c_max": float(cost_threshold),
        "q_min": float(quality_threshold),
        "sigma_anchor": float(anchor_rows.iloc[0]["sigma"]),
        "n_trajectories": int(len(observations)),
        "latency_first_count": int(cause_counts.get("latency", 0)),
        "cost_first_count": int(cause_counts.get("cost", 0)),
        "quality_first_count": int(cause_counts.get("quality", 0)),
        "tie_first_count": int(cause_counts.get("tie", 0)),
        "censored_count": int(cause_counts.get("censored", 0)),
        "ar_augmentation_type": str(augmentation_type),
    }
    tagged_curve = curve.copy()
    tagged_curve.insert(0, "region_id", str(region_id))
    tagged_curve.insert(0, "physical_setting_id", str(physical_setting_id))
    return summary, tagged_curve


def build_full_domain_loose_axis_regions_for_one_setting(
    physical_setting_request_ledger: pd.DataFrame,
    original_region_summary: pd.DataFrame,
    physical_setting_id: str,
    center_instruction_mean: float,
    dispersion: float,
    quality_threshold: float,
    anchor_horizon: float,
    horizons: list[float],
    stop_time: float,
    loose_multiplier: float,
    relative_epsilon: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build cost-isolating and latency-isolating full-domain AR families.

    Called by:
        - ``augment_existing_discovery_results`` in this module.
        - unit tests in ``test_augment_full_domain_loose_ar_axes.py``.
    """
    latency_loose, cost_loose = calculate_full_domain_loose_thresholds(
        physical_setting_request_ledger,
        stop_time=stop_time,
        loose_multiplier=loose_multiplier,
        relative_epsilon=relative_epsilon,
    )
    original_cost_thresholds = sorted(original_region_summary["c_max"].astype(float).unique())
    original_latency_thresholds = sorted(original_region_summary["l_max"].astype(float).unique())

    summaries: list[dict[str, object]] = []
    curves: list[pd.DataFrame] = []
    for index, cost_threshold in enumerate(original_cost_thresholds):
        summary, curve = evaluate_one_augmented_region(
            physical_setting_request_ledger,
            physical_setting_id=physical_setting_id,
            region_id=f"{physical_setting_id}_FDL_{index:05d}",
            center_instruction_mean=center_instruction_mean,
            dispersion=dispersion,
            latency_threshold=latency_loose,
            cost_threshold=float(cost_threshold),
            quality_threshold=quality_threshold,
            anchor_horizon=anchor_horizon,
            horizons=horizons,
            stop_time=stop_time,
            augmentation_type="FULL_DOMAIN_LOOSE_LATENCY",
        )
        summaries.append(summary)
        curves.append(curve)

    for index, latency_threshold in enumerate(original_latency_thresholds):
        summary, curve = evaluate_one_augmented_region(
            physical_setting_request_ledger,
            physical_setting_id=physical_setting_id,
            region_id=f"{physical_setting_id}_FDC_{index:05d}",
            center_instruction_mean=center_instruction_mean,
            dispersion=dispersion,
            latency_threshold=float(latency_threshold),
            cost_threshold=cost_loose,
            quality_threshold=quality_threshold,
            anchor_horizon=anchor_horizon,
            horizons=horizons,
            stop_time=stop_time,
            augmentation_type="FULL_DOMAIN_LOOSE_COST",
        )
        summaries.append(summary)
        curves.append(curve)

    return pd.DataFrame(summaries), pd.concat(curves, ignore_index=True)


def augment_existing_discovery_results(
    input_directory: Path,
    output_directory: Path,
) -> None:
    """Augment an existing N=10 discovery result set without simulation reruns.

    Side effects:
        Writes a sibling result set containing all original ARs plus the new
        full-domain loose-axis families. Raw ledgers are copied unchanged.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(
        (input_directory / "effective_config.json").read_text(encoding="utf-8")
    )
    ledgers = pd.read_csv(input_directory / "all_top_level_request_ledgers.csv")
    original_summary = pd.read_csv(input_directory / "admissibility_regions.csv")
    original_curves = pd.read_csv(input_directory / "survival_curves.csv")
    physical_settings = pd.read_csv(input_directory / "physical_settings.csv")

    anchor_horizon = float(configuration["admissibility_scan"]["anchor_horizon"])
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    if "grid" in configuration["horizon"] and configuration["horizon"]["grid"] is not None:
        horizons = list(map(float, configuration["horizon"]["grid"]))
    else:
        step = float(configuration["horizon"]["grid_step"])
        minimum = float(configuration["horizon"]["minimum"])
        maximum = float(configuration["horizon"]["maximum"])
        count = int(round((maximum - minimum) / step))
        horizons = [minimum + index * step for index in range(count + 1)]
    quality_threshold = float(configuration["provider_family"]["x"])
    loose_multiplier = float(
        configuration["admissibility_scan"]["include_unconstrained_threshold_multiplier"]
    )
    relative_epsilon = float(configuration["admissibility_scan"]["threshold_relative_epsilon"])

    augmented_summaries: list[pd.DataFrame] = []
    augmented_curves: list[pd.DataFrame] = []
    for setting_id, setting_ledger in ledgers.groupby("physical_setting_id", sort=True):
        setting_regions = original_summary[
            original_summary["physical_setting_id"] == setting_id
        ].copy()
        summary, curves = build_full_domain_loose_axis_regions_for_one_setting(
            setting_ledger,
            setting_regions,
            physical_setting_id=str(setting_id),
            center_instruction_mean=float(setting_ledger["center_instruction_mean"].iloc[0]),
            dispersion=float(setting_ledger["dispersion"].iloc[0]),
            quality_threshold=quality_threshold,
            anchor_horizon=anchor_horizon,
            horizons=horizons,
            stop_time=stop_time,
            loose_multiplier=loose_multiplier,
            relative_epsilon=relative_epsilon,
        )
        augmented_summaries.append(summary)
        augmented_curves.append(curves)

    original_summary = original_summary.copy()
    original_summary["ar_augmentation_type"] = "ORIGINAL_ANCHOR_INFORMED"
    combined_summary = pd.concat(
        [original_summary, *augmented_summaries], ignore_index=True
    )
    combined_curves = pd.concat(
        [original_curves, *augmented_curves], ignore_index=True
    )
    representatives = select_representative_regions_for_each_achievable_anchor_survival(
        combined_summary,
        int(configuration["admissibility_scan"]["representatives_per_anchor_survival"]),
    )
    achievable_sigmas = (
        combined_summary.groupby(["physical_setting_id", "sigma_anchor"], as_index=False)
        .agg(
            number_of_regions=("region_id", "count"),
            minimum_l_max=("l_max", "min"),
            maximum_l_max=("l_max", "max"),
            minimum_c_max=("c_max", "min"),
            maximum_c_max=("c_max", "max"),
        )
        .sort_values(["physical_setting_id", "sigma_anchor"])
    )

    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    augmented_configuration = dict(configuration)
    augmented_configuration["offline_ar_augmentation"] = {
        "status": "FULL_DOMAIN_LOOSE_AXES_V1",
        "source_results_directory": str(input_directory),
        "simulator_rerun": False,
        "latency_loose_semantics": "finite threshold nonbinding on all N=10 discovery trajectories through H=240",
        "cost_loose_semantics": "finite threshold nonbinding on all N=10 discovery trajectories through H=240",
    }
    (output_directory / "effective_config.json").write_text(
        json.dumps(augmented_configuration, indent=2), encoding="utf-8"
    )
    ledgers.to_csv(output_directory / "all_top_level_request_ledgers.csv", index=False)
    physical_settings.to_csv(output_directory / "physical_settings.csv", index=False)
    combined_summary.to_csv(output_directory / "admissibility_regions.csv", index=False)
    combined_curves.to_csv(output_directory / "survival_curves.csv", index=False)
    representatives.to_csv(
        output_directory / "representative_regions_by_sigma.csv", index=False
    )
    achievable_sigmas.to_csv(output_directory / "achievable_sigmas.csv", index=False)
    print(
        "PHASE1_FULL_DOMAIN_LOOSE_AR_AUGMENTATION_PASS",
        f"n_original_regions={len(original_summary)}",
        f"n_augmented_regions={sum(len(frame) for frame in augmented_summaries)}",
        f"n_total_regions={len(combined_summary)}",
        f"output_directory={output_directory}",
    )


def main() -> None:
    """Command-line entry point for offline full-domain loose-axis augmentation."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory
        / "results"
        / "scientific_discovery_v1_full_domain_ar",
    )
    args = parser.parse_args()
    augment_existing_discovery_results(args.input.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
