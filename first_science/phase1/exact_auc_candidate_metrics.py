"""Compute exact-event survival-area metrics for every distinct Phase-1 N=10 AR.

This is an offline white-box post-process. It consumes the already generated
top-level request ledgers and admissibility-region table, deduplicates numerically
identical A=(l_max,c_max,q_min) regions, and evaluates every distinct A without
rerunning AICon/YAFS. The implementation precomputes latency/cost/quality event
times for each trajectory and threshold so the complete AR table can be reranked
without a lengthy per-region request scan.

The result directory keeps its historical effective configuration untouched.
The revised finalist-selection policy is read separately from the current
versioned Phase-1 configuration, which is important because existing N=10 result
folders predate the survival-area revision.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from selection_policy import load_survival_area_selection_policy

EVENT_TOLERANCE = 1e-12


def deduplicate_exact_admissibility_regions(regions: pd.DataFrame) -> pd.DataFrame:
    """Keep one provenance row for every exact physical-setting/A tuple."""
    required = {
        "physical_setting_id",
        "region_id",
        "center_instruction_mean",
        "dispersion",
        "l_max",
        "c_max",
        "q_min",
    }
    missing = required.difference(regions.columns)
    if missing:
        raise ValueError(f"admissibility_regions missing columns: {sorted(missing)}")

    keys = ["physical_setting_id", "l_max", "c_max", "q_min"]
    rows: list[dict[str, object]] = []
    for _, group in regions.groupby(keys, sort=True, dropna=False):
        row = group.iloc[0].to_dict()
        row["equivalent_region_count"] = int(len(group))
        row["equivalent_region_ids"] = ";".join(sorted(group["region_id"].astype(str)))
        if "ar_augmentation_type" in group.columns:
            row["equivalent_ar_provenance"] = ";".join(
                sorted(set(group["ar_augmentation_type"].astype(str)))
            )
        rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def _earliest_latency_event_time(
    emission: np.ndarray,
    completion: np.ndarray,
    latency_threshold: float,
    stop_time: float,
) -> float | None:
    """Return the earliest frozen-semantics latency violation for one threshold."""
    deadlines = emission + float(latency_threshold)
    completed_by_deadline = np.isfinite(completion) & (
        completion <= deadlines + EVENT_TOLERANCE
    )
    mask = (deadlines <= float(stop_time) + EVENT_TOLERANCE) & (~completed_by_deadline)
    if not np.any(mask):
        return None
    return float(np.min(deadlines[mask]))


def _earliest_completion_attribute_event_time(
    completion: np.ndarray,
    values: np.ndarray,
    threshold: float,
    stop_time: float,
    direction: str,
) -> float | None:
    """Return earliest completion-time cost or quality violation."""
    observable = np.isfinite(completion) & (completion <= float(stop_time) + EVENT_TOLERANCE)
    if direction == "above":
        violates = np.isfinite(values) & (values > float(threshold))
    elif direction == "below":
        violates = np.isfinite(values) & (values < float(threshold))
    else:
        raise ValueError(f"unknown threshold direction: {direction}")
    mask = observable & violates
    if not np.any(mask):
        return None
    return float(np.min(completion[mask]))


def build_threshold_event_cache_for_trajectory(
    trajectory_ledger: pd.DataFrame,
    latency_thresholds: list[float],
    cost_thresholds: list[float],
    quality_thresholds: list[float],
    stop_time: float,
) -> dict[str, dict[float, float | None]]:
    """Precompute earliest event times for every threshold in one trajectory."""
    ordered = trajectory_ledger.sort_values(["emission", "request_id"])
    emission = ordered["emission"].astype(float).to_numpy()
    completion = ordered["completion"].astype(float).to_numpy()
    cost = ordered["C"].astype(float).to_numpy()
    quality = ordered["Q"].astype(float).to_numpy()

    return {
        "latency": {
            float(threshold): _earliest_latency_event_time(
                emission, completion, float(threshold), stop_time
            )
            for threshold in latency_thresholds
        },
        "cost": {
            float(threshold): _earliest_completion_attribute_event_time(
                completion, cost, float(threshold), stop_time, "above"
            )
            for threshold in cost_thresholds
        },
        "quality": {
            float(threshold): _earliest_completion_attribute_event_time(
                completion, quality, float(threshold), stop_time, "below"
            )
            for threshold in quality_thresholds
        },
    }


def combine_cached_event_times(
    latency_time: float | None,
    cost_time: float | None,
    quality_time: float | None,
) -> tuple[float | None, str]:
    """Combine cached per-axis events into the first joint-A violation."""
    named = [("latency", latency_time), ("cost", cost_time), ("quality", quality_time)]
    finite = [(name, float(time)) for name, time in named if time is not None]
    if not finite:
        return None, "censored"
    earliest = min(time for _, time in finite)
    causes = sorted(name for name, time in finite if abs(time - earliest) <= EVENT_TOLERANCE)
    return float(earliest), causes[0] if len(causes) == 1 else "tie"


def calculate_exact_normalized_restricted_survival_area(
    first_violation_times: list[float | None],
    horizon_min: float,
    horizon_max: float,
) -> tuple[float, float]:
    """Return exact empirical restricted survival area and normalized area.

    For each trajectory the contribution to the integral over [Ha,Hb] is
    max(0,min(T,Hb)-Ha); a right-censored trajectory contributes Hb-Ha. This is
    the exact area under the empirical P(T>H) staircase and does not depend on
    the stored reporting grid.
    """
    if not first_violation_times:
        raise ValueError("at least one first-violation observation is required")
    start = float(horizon_min)
    stop = float(horizon_max)
    if start < 0.0 or stop <= start:
        raise ValueError("restricted-survival horizon must satisfy 0 <= min < max")
    width = stop - start
    durations = []
    for time in first_violation_times:
        if time is None:
            durations.append(width)
        else:
            durations.append(max(0.0, min(float(time), stop) - start))
    area_seconds = float(np.mean(durations))
    return area_seconds, float(area_seconds / width)


def _curve_geometry_from_exact_events(
    first_violation_times: list[float | None],
    horizon_min: float,
    horizon_max: float,
) -> dict[str, float | int]:
    """Calculate secondary exact-event temporal-richness diagnostics."""
    n = len(first_violation_times)
    finite = [
        float(time)
        for time in first_violation_times
        if time is not None and float(horizon_min) <= float(time) <= float(horizon_max)
    ]
    counts = Counter(finite)
    maximum_jump = max(counts.values()) / n if counts else 0.0
    boundaries = [float(horizon_min), *sorted(counts), float(horizon_max)]
    plateau_lengths = [
        max(0.0, right - left)
        for left, right in zip(boundaries[:-1], boundaries[1:])
    ]
    longest = max(plateau_lengths) if plateau_lengths else float(horizon_max - horizon_min)
    width = float(horizon_max - horizon_min)
    return {
        "n_failed_by_area_horizon": int(len(finite)),
        "n_unique_first_violation_times": int(len(counts)),
        "maximum_empirical_jump": float(maximum_jump),
        "longest_plateau": float(longest),
        "longest_plateau_fraction_of_domain": float(longest / width),
    }


def compute_metrics_for_one_physical_setting(
    setting_regions: pd.DataFrame,
    setting_ledgers: pd.DataFrame,
    area_horizon_min: float,
    area_horizon_max: float,
    reporting_anchor_horizon: float,
    stop_time: float,
) -> pd.DataFrame:
    """Compute exact metrics for every distinct A in one physical setting."""
    latency_thresholds = sorted(setting_regions["l_max"].astype(float).unique())
    cost_thresholds = sorted(setting_regions["c_max"].astype(float).unique())
    quality_thresholds = sorted(setting_regions["q_min"].astype(float).unique())

    trajectory_caches: list[tuple[object, dict[str, dict[float, float | None]]]] = []
    for trajectory_id, trajectory_ledger in setting_ledgers.groupby("trajectory", sort=True):
        trajectory_caches.append(
            (
                trajectory_id,
                build_threshold_event_cache_for_trajectory(
                    trajectory_ledger,
                    latency_thresholds,
                    cost_thresholds,
                    quality_thresholds,
                    stop_time,
                ),
            )
        )
    if not trajectory_caches:
        raise ValueError("physical setting has no trajectory ledgers")

    rows: list[dict[str, object]] = []
    for _, region in setting_regions.iterrows():
        l_max = float(region["l_max"])
        c_max = float(region["c_max"])
        q_min = float(region["q_min"])
        times: list[float | None] = []
        causes: list[str] = []
        for _, cache in trajectory_caches:
            time, cause = combine_cached_event_times(
                cache["latency"][l_max],
                cache["cost"][c_max],
                cache["quality"][q_min],
            )
            times.append(time)
            causes.append(cause)

        area_seconds, normalized_area = calculate_exact_normalized_restricted_survival_area(
            times,
            area_horizon_min,
            area_horizon_max,
        )
        cause_counts = Counter(causes)
        geometry = _curve_geometry_from_exact_events(
            times,
            area_horizon_min,
            area_horizon_max,
        )
        sigma_anchor = float(
            np.mean(
                [
                    time is None or float(time) > float(reporting_anchor_horizon)
                    for time in times
                ]
            )
        )
        output = region.to_dict()
        output.update(
            {
                "normalized_restricted_survival_area": normalized_area,
                "restricted_survival_area_seconds": area_seconds,
                "survival_area_horizon_min": float(area_horizon_min),
                "survival_area_horizon_max": float(area_horizon_max),
                "sigma_120_reporting": sigma_anchor,
                "latency_first_count_exact": int(cause_counts.get("latency", 0)),
                "cost_first_count_exact": int(cause_counts.get("cost", 0)),
                "quality_first_count_exact": int(cause_counts.get("quality", 0)),
                "tie_first_count_exact": int(cause_counts.get("tie", 0)),
                "censored_count_exact": int(cause_counts.get("censored", 0)),
                **geometry,
            }
        )
        rows.append(output)
    return pd.DataFrame(rows)


def compute_exact_auc_candidate_metrics(
    results_directory: Path,
    policy_configuration_path: Path,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Compute all-distinct exact N=10 AUC metrics from an existing result set."""
    result_configuration = json.loads(
        (results_directory / "effective_config.json").read_text(encoding="utf-8")
    )
    policy_configuration = json.loads(
        policy_configuration_path.read_text(encoding="utf-8")
    )
    policy = load_survival_area_selection_policy(policy_configuration)
    stop_time = float(result_configuration["horizon"]["simulation_stop_time"])
    if policy.horizon_max > stop_time + EVENT_TOLERANCE:
        raise ValueError("survival-area horizon cannot exceed simulator stop time")
    if abs(policy.horizon_min - float(result_configuration["horizon"]["minimum"])) > 1e-12:
        raise ValueError("selection area horizon_min differs from discovery horizon minimum")
    if abs(policy.horizon_max - float(result_configuration["horizon"]["maximum"])) > 1e-12:
        raise ValueError("selection area horizon_max differs from discovery horizon maximum")
    anchor_horizon = float(result_configuration["admissibility_calibration"]["anchor_horizon"])

    regions = deduplicate_exact_admissibility_regions(
        pd.read_csv(results_directory / "admissibility_regions.csv")
    )
    ledgers = pd.read_csv(results_directory / "all_top_level_request_ledgers.csv")

    metrics: list[pd.DataFrame] = []
    for setting_id, setting_regions in regions.groupby("physical_setting_id", sort=True):
        setting_ledgers = ledgers[ledgers["physical_setting_id"].astype(str) == str(setting_id)].copy()
        if setting_ledgers.empty:
            raise ValueError(f"no ledgers found for physical setting {setting_id}")
        metrics.append(
            compute_metrics_for_one_physical_setting(
                setting_regions,
                setting_ledgers,
                area_horizon_min=policy.horizon_min,
                area_horizon_max=policy.horizon_max,
                reporting_anchor_horizon=anchor_horizon,
                stop_time=stop_time,
            )
        )

    table = pd.concat(metrics, ignore_index=True)
    if output_path is None:
        output_path = results_directory / "whitebox_selection" / "auc_candidate_metrics.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_path, index=False)
    print(
        "PHASE1_EXACT_AUC_CANDIDATE_METRICS_PASS",
        f"n_distinct_A={len(table)}",
        f"area_band=[{policy.area_min:.6g},{policy.area_max:.6g}]",
        f"policy_config={policy_configuration_path}",
        f"output={output_path}",
    )
    return table


def main() -> None:
    """Command-line entry point for exact-event AUC metric computation."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    compute_exact_auc_candidate_metrics(
        args.results.resolve(),
        args.policy_config.resolve(),
        None if args.output is None else args.output.resolve(),
    )


if __name__ == "__main__":
    main()
