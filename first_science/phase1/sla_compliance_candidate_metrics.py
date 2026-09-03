"""Compute SLA-compliance metrics for every distinct Phase-1 N=10 candidate A.

This offline reranker reuses the sealed N=10 physical request ledgers. It does
not rerun AICon/YAFS and does not use M0/M1. For each distinct admissibility
region A=(l_max,c_max,q_min), it reconstructs request-level SLA decisions under
rho*=0.95 and cumulative [0,H]-from-t=0 accounting, then computes exact
normalized SLA-compliance area plus all-request L/C failure diagnostics.

The implementation caches latency-threshold-dependent decision times per
trajectory so the full AR table can be reranked without repeatedly rescanning
raw request rows in Python.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from selection_policy import (
    SlaComplianceAreaSelectionPolicy,
    load_sla_compliance_area_selection_policy,
)
from sla_compliance_analysis import EVENT_TOLERANCE


@dataclass(frozen=True)
class TrajectoryRequestArrays:
    """Store numeric request arrays for one stochastic trajectory.

    Called by:
        - ``build_physical_setting_trajectory_arrays`` in this module.
        - ``calculate_candidate_metrics_for_one_trajectory`` in this module.
    """

    trajectory: object
    seed: int | None
    emission: np.ndarray
    completion: np.ndarray
    cost: np.ndarray
    quality: np.ndarray


@dataclass(frozen=True)
class LatencyDecisionCache:
    """Cache request decision geometry that depends only on l_max.

    Called by:
        - ``build_latency_decision_cache`` in this module.
        - ``calculate_candidate_metrics_for_one_trajectory`` in this module.
    """

    decision_time: np.ndarray
    decided_by_stop: np.ndarray
    completed_in_time: np.ndarray
    sorted_decided_indices: np.ndarray
    sorted_decision_times: np.ndarray


def deduplicate_exact_admissibility_regions(regions: pd.DataFrame) -> pd.DataFrame:
    """Retain one provenance row for each physical-setting/A tuple.

    Args:
        regions: Existing ``admissibility_regions.csv`` including original and
            full-domain augmented ARs.

    Returns:
        Deduplicated A table with equivalent-region provenance.

    Side effects:
        None.

    Called by:
        - ``compute_sla_candidate_metrics`` in this module.
        - unit tests in ``test_sla_compliance_candidate_metrics.py``.
    """
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
        row["equivalent_region_ids"] = ";".join(
            sorted(group["region_id"].astype(str).tolist())
        )
        if "ar_augmentation_type" in group.columns:
            row["equivalent_ar_provenance"] = ";".join(
                sorted(set(group["ar_augmentation_type"].astype(str)))
            )
        rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def build_physical_setting_trajectory_arrays(
    physical_setting_ledgers: pd.DataFrame,
) -> list[TrajectoryRequestArrays]:
    """Convert one physical setting's request ledgers to compact numeric arrays.

    Called by:
        - ``compute_metrics_for_one_physical_setting`` in this module.
    """
    required = {"trajectory", "emission", "completion", "C", "Q"}
    missing = required.difference(physical_setting_ledgers.columns)
    if missing:
        raise ValueError(f"request ledgers missing columns: {sorted(missing)}")

    trajectories: list[TrajectoryRequestArrays] = []
    for trajectory, ledger in physical_setting_ledgers.groupby("trajectory", sort=True):
        ordered = ledger.sort_values(["emission", "request_id"])
        seed = int(ordered["seed"].iloc[0]) if "seed" in ordered.columns else None
        trajectories.append(
            TrajectoryRequestArrays(
                trajectory=trajectory,
                seed=seed,
                emission=ordered["emission"].astype(float).to_numpy(),
                completion=pd.to_numeric(
                    ordered["completion"], errors="coerce"
                ).to_numpy(dtype=float),
                cost=pd.to_numeric(ordered["C"], errors="coerce").to_numpy(dtype=float),
                quality=pd.to_numeric(
                    ordered["Q"], errors="coerce"
                ).to_numpy(dtype=float),
            )
        )
    if not trajectories:
        raise ValueError("at least one trajectory is required")
    return trajectories


def build_latency_decision_cache(
    trajectory: TrajectoryRequestArrays,
    latency_threshold: float,
    stop_time: float,
) -> LatencyDecisionCache:
    """Precompute SLA decision times for one trajectory and latency threshold.

    Args:
        trajectory: Numeric request arrays.
        latency_threshold: Candidate l_max.
        stop_time: Simulator stop time.

    Returns:
        Decision-time and in-time-completion masks independent of c_max/q_min.

    Side effects:
        None.

    Called by:
        - ``compute_metrics_for_one_physical_setting`` in this module.
        - unit tests in ``test_sla_compliance_candidate_metrics.py``.
    """
    deadline = trajectory.emission + float(latency_threshold)
    finite_completion = np.isfinite(trajectory.completion)
    completed_in_time = finite_completion & (
        trajectory.completion <= deadline + EVENT_TOLERANCE
    )
    decision_time = np.where(completed_in_time, trajectory.completion, deadline)
    decided_by_stop = decision_time <= float(stop_time) + EVENT_TOLERANCE
    decided_indices = np.flatnonzero(decided_by_stop)
    if len(decided_indices):
        order = decided_indices[
            np.argsort(decision_time[decided_indices], kind="stable")
        ]
        sorted_times = decision_time[order]
    else:
        order = np.array([], dtype=int)
        sorted_times = np.array([], dtype=float)
    return LatencyDecisionCache(
        decision_time=decision_time,
        decided_by_stop=decided_by_stop,
        completed_in_time=completed_in_time,
        sorted_decided_indices=order,
        sorted_decision_times=sorted_times,
    )


def _calculate_exact_area_and_state_transitions(
    sorted_decision_times: np.ndarray,
    sorted_compliant: np.ndarray,
    policy: SlaComplianceAreaSelectionPolicy,
) -> tuple[float, list[tuple[float, int]]]:
    """Integrate one trajectory SLA state and retain pass/fail transitions.

    Called by:
        - ``calculate_candidate_metrics_for_one_trajectory`` in this module.
    """
    start = float(policy.horizon_min)
    stop = float(policy.horizon_max)
    rho = float(policy.sla_definition.rho)
    zero = float(policy.sla_definition.zero_decision_compliance)

    if len(sorted_decision_times) == 0:
        initial = bool(zero + EVENT_TOLERANCE >= rho)
        return (stop - start) * float(initial), []

    unique_times, first_indices, counts = np.unique(
        sorted_decision_times, return_index=True, return_counts=True
    )
    compliant_counts = np.add.reduceat(
        sorted_compliant.astype(int), first_indices
    )

    before_or_at_start = unique_times <= start + EVENT_TOLERANCE
    n_decided = int(counts[before_or_at_start].sum())
    n_compliant = int(compliant_counts[before_or_at_start].sum())
    fraction = zero if n_decided == 0 else n_compliant / n_decided
    current_state = bool(fraction + EVENT_TOLERANCE >= rho)
    current_time = start
    area = 0.0
    transitions: list[tuple[float, int]] = []

    future_indices = np.flatnonzero(
        (unique_times > start + EVENT_TOLERANCE)
        & (unique_times <= stop + EVENT_TOLERANCE)
    )
    for group_index in future_indices:
        event_time = min(float(unique_times[group_index]), stop)
        if event_time > current_time:
            area += (event_time - current_time) * float(current_state)
        previous = current_state
        n_decided += int(counts[group_index])
        n_compliant += int(compliant_counts[group_index])
        current_state = bool(
            (n_compliant / n_decided) + EVENT_TOLERANCE >= rho
        )
        if current_state != previous:
            transitions.append((event_time, 1 if current_state else -1))
        current_time = event_time

    if current_time < stop:
        area += (stop - current_time) * float(current_state)
    return float(area), transitions


def _calculate_cumulative_sla_at_horizon(
    decision_time: np.ndarray,
    decided_by_stop: np.ndarray,
    compliant: np.ndarray,
    horizon: float,
    policy: SlaComplianceAreaSelectionPolicy,
) -> tuple[float, float, int]:
    """Return trajectory SLA indicator, compliance fraction and decided count.

    Called by:
        - ``calculate_candidate_metrics_for_one_trajectory`` in this module.
    """
    mask = decided_by_stop & (
        decision_time <= float(horizon) + EVENT_TOLERANCE
    )
    n_decided = int(mask.sum())
    if n_decided == 0:
        fraction = float(policy.sla_definition.zero_decision_compliance)
    else:
        fraction = float(compliant[mask].sum() / n_decided)
    state = float(
        fraction + EVENT_TOLERANCE >= float(policy.sla_definition.rho)
    )
    return state, fraction, n_decided


def calculate_candidate_metrics_for_one_trajectory(
    trajectory: TrajectoryRequestArrays,
    latency_cache: LatencyDecisionCache,
    cost_threshold: float,
    quality_threshold: float,
    reporting_anchor_horizon: float,
    policy: SlaComplianceAreaSelectionPolicy,
) -> dict[str, object]:
    """Calculate exact SLA metrics for one trajectory/A without DataFrame rebuilds.

    Called by:
        - ``compute_metrics_for_one_physical_setting`` in this module.
        - unit tests in ``test_sla_compliance_candidate_metrics.py``.
    """
    in_time = latency_cache.completed_in_time
    decided = latency_cache.decided_by_stop
    cost_failed = decided & in_time & (trajectory.cost > float(cost_threshold))
    quality_failed = decided & in_time & (
        trajectory.quality < float(quality_threshold)
    )
    compliant = decided & in_time & (~cost_failed) & (~quality_failed)
    latency_failed = decided & (~in_time)

    sorted_indices = latency_cache.sorted_decided_indices
    sorted_compliant = compliant[sorted_indices] if len(sorted_indices) else np.array([], dtype=bool)
    area_seconds, transitions = _calculate_exact_area_and_state_transitions(
        latency_cache.sorted_decision_times,
        sorted_compliant,
        policy,
    )
    sigma_anchor, anchor_fraction, anchor_decided = _calculate_cumulative_sla_at_horizon(
        latency_cache.decision_time,
        decided,
        compliant,
        reporting_anchor_horizon,
        policy,
    )
    sigma_stop, final_fraction, final_decided = _calculate_cumulative_sla_at_horizon(
        latency_cache.decision_time,
        decided,
        compliant,
        policy.horizon_max,
        policy,
    )

    return {
        "area_seconds": area_seconds,
        "sigma_anchor_indicator": sigma_anchor,
        "sigma_stop_indicator": sigma_stop,
        "anchor_compliance_fraction": anchor_fraction,
        "anchor_decided_requests": anchor_decided,
        "final_compliance_fraction": final_fraction,
        "final_decided_requests": final_decided,
        "decided_request_count": int(decided.sum()),
        "unresolved_request_count": int((~decided).sum()),
        "compliant_request_count": int(compliant.sum()),
        "failed_request_count": int(decided.sum() - compliant.sum()),
        "latency_failure_count": int(latency_failed.sum()),
        "cost_failure_count": int(cost_failed.sum()),
        "quality_failure_count": int(quality_failed.sum()),
        "state_transitions": transitions,
    }


def compute_metrics_for_one_physical_setting(
    setting_regions: pd.DataFrame,
    setting_ledgers: pd.DataFrame,
    reporting_anchor_horizon: float,
    stop_time: float,
    policy: SlaComplianceAreaSelectionPolicy,
) -> pd.DataFrame:
    """Compute SLA-compliance metrics for every distinct A in one physical setting.

    Called by:
        - ``compute_sla_candidate_metrics`` in this module.
        - unit tests in ``test_sla_compliance_candidate_metrics.py``.
    """
    trajectories = build_physical_setting_trajectory_arrays(setting_ledgers)
    latency_thresholds = sorted(setting_regions["l_max"].astype(float).unique())
    latency_caches: dict[tuple[int, float], LatencyDecisionCache] = {}
    for trajectory_index, trajectory in enumerate(trajectories):
        for threshold in latency_thresholds:
            latency_caches[(trajectory_index, float(threshold))] = (
                build_latency_decision_cache(
                    trajectory, float(threshold), stop_time
                )
            )

    n_trajectories = len(trajectories)
    width = float(policy.horizon_max - policy.horizon_min)
    rows: list[dict[str, object]] = []
    for _, region in setting_regions.iterrows():
        l_max = float(region["l_max"])
        c_max = float(region["c_max"])
        q_min = float(region["q_min"])
        trajectory_metrics: list[dict[str, object]] = []
        transition_deltas: Counter[float] = Counter()
        for trajectory_index, trajectory in enumerate(trajectories):
            metrics = calculate_candidate_metrics_for_one_trajectory(
                trajectory,
                latency_caches[(trajectory_index, l_max)],
                cost_threshold=c_max,
                quality_threshold=q_min,
                reporting_anchor_horizon=reporting_anchor_horizon,
                policy=policy,
            )
            trajectory_metrics.append(metrics)
            for event_time, delta in metrics["state_transitions"]:
                transition_deltas[float(event_time)] += int(delta)

        mean_area_seconds = float(
            np.mean([float(m["area_seconds"]) for m in trajectory_metrics])
        )
        sigma_anchor = float(
            np.mean([float(m["sigma_anchor_indicator"]) for m in trajectory_metrics])
        )
        sigma_stop = float(
            np.mean([float(m["sigma_stop_indicator"]) for m in trajectory_metrics])
        )
        total_decided = int(
            sum(int(m["decided_request_count"]) for m in trajectory_metrics)
        )
        total_unresolved = int(
            sum(int(m["unresolved_request_count"]) for m in trajectory_metrics)
        )
        total_compliant = int(
            sum(int(m["compliant_request_count"]) for m in trajectory_metrics)
        )
        total_failed = int(
            sum(int(m["failed_request_count"]) for m in trajectory_metrics)
        )
        latency_failures = int(
            sum(int(m["latency_failure_count"]) for m in trajectory_metrics)
        )
        cost_failures = int(
            sum(int(m["cost_failure_count"]) for m in trajectory_metrics)
        )
        quality_failures = int(
            sum(int(m["quality_failure_count"]) for m in trajectory_metrics)
        )
        lc_total = latency_failures + cost_failures

        transition_times = sorted(
            time
            for time, delta in transition_deltas.items()
            if delta != 0
            and policy.horizon_min - EVENT_TOLERANCE
            <= time
            <= policy.horizon_max + EVENT_TOLERANCE
        )
        boundaries = [
            float(policy.horizon_min),
            *transition_times,
            float(policy.horizon_max),
        ]
        plateau_lengths = [
            max(0.0, right - left)
            for left, right in zip(boundaries[:-1], boundaries[1:])
        ]
        longest_plateau = max(plateau_lengths) if plateau_lengths else width
        maximum_jump = (
            max(abs(int(transition_deltas[time])) for time in transition_times)
            / n_trajectories
            if transition_times
            else 0.0
        )

        output = region.to_dict()
        output.update(
            {
                "rho": float(policy.sla_definition.rho),
                "accounting_origin": float(
                    policy.sla_definition.accounting_origin
                ),
                "accounting_window": "cumulative_[0,H]_from_t0",
                "normalized_sla_compliance_area": float(
                    mean_area_seconds / width
                ),
                "sla_compliance_area_seconds": mean_area_seconds,
                "sigma_120_reporting": sigma_anchor,
                "sigma_240_reporting": sigma_stop,
                "decided_request_count": total_decided,
                "unresolved_request_count": total_unresolved,
                "compliant_request_count": total_compliant,
                "failed_request_count": total_failed,
                "request_compliance_fraction": (
                    float(total_compliant / total_decided)
                    if total_decided
                    else 1.0
                ),
                "latency_failure_count": latency_failures,
                "cost_failure_count": cost_failures,
                "quality_failure_count": quality_failures,
                "latency_failure_fraction_of_lc": (
                    float(latency_failures / lc_total)
                    if lc_total
                    else float("nan")
                ),
                "cost_failure_fraction_of_lc": (
                    float(cost_failures / lc_total)
                    if lc_total
                    else float("nan")
                ),
                "mean_final_trajectory_compliance_fraction": float(
                    np.mean(
                        [
                            float(m["final_compliance_fraction"])
                            for m in trajectory_metrics
                        ]
                    )
                ),
                "minimum_final_trajectory_compliance_fraction": float(
                    np.min(
                        [
                            float(m["final_compliance_fraction"])
                            for m in trajectory_metrics
                        ]
                    )
                ),
                "maximum_final_trajectory_compliance_fraction": float(
                    np.max(
                        [
                            float(m["final_compliance_fraction"])
                            for m in trajectory_metrics
                        ]
                    )
                ),
                "n_sigma_transition_times": int(len(transition_times)),
                "maximum_empirical_sigma_jump": float(maximum_jump),
                "longest_sigma_plateau": float(longest_plateau),
                "longest_sigma_plateau_fraction_of_domain": float(
                    longest_plateau / width
                ),
            }
        )
        rows.append(output)
    return pd.DataFrame(rows)


def compute_sla_candidate_metrics(
    results_directory: Path,
    policy_configuration_path: Path,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Rerank the complete sealed N=10 AR substrate under SLA sigma semantics.

    Args:
        results_directory: Existing N=10 full-domain AR result directory.
        policy_configuration_path: Current versioned Phase-1 configuration.
        output_path: Optional output CSV override.

    Returns:
        One metrics row per distinct physical-setting/A tuple.

    Side effects:
        Writes ``whitebox_selection/sla_candidate_metrics.csv``.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(
        policy_configuration_path.read_text(encoding="utf-8")
    )
    policy = load_sla_compliance_area_selection_policy(configuration)
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    if abs(stop_time - policy.horizon_max) > 1e-12:
        raise ValueError(
            "current Phase-1 SLA area upper horizon must equal simulator stop"
        )
    reporting_anchor = float(
        configuration["admissibility_calibration"]["anchor_horizon"]
    )

    regions = deduplicate_exact_admissibility_regions(
        pd.read_csv(results_directory / "admissibility_regions.csv")
    )
    ledgers = pd.read_csv(
        results_directory / "all_top_level_request_ledgers.csv"
    )

    frames: list[pd.DataFrame] = []
    for setting_id, setting_regions in regions.groupby(
        "physical_setting_id", sort=True
    ):
        setting_ledgers = ledgers[
            ledgers["physical_setting_id"].astype(str) == str(setting_id)
        ].copy()
        if setting_ledgers.empty:
            raise ValueError(f"no request ledgers for {setting_id}")
        frames.append(
            compute_metrics_for_one_physical_setting(
                setting_regions,
                setting_ledgers,
                reporting_anchor_horizon=reporting_anchor,
                stop_time=stop_time,
                policy=policy,
            )
        )

    metrics = pd.concat(frames, ignore_index=True)
    if output_path is None:
        output_path = (
            results_directory
            / "whitebox_selection"
            / "sla_candidate_metrics.csv"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_path, index=False)
    print(
        "PHASE1_SLA_CANDIDATE_METRICS_PASS",
        f"n_distinct_A={len(metrics)}",
        f"rho={policy.sla_definition.rho:.6g}",
        f"area_band=[{policy.area_min:.6g},{policy.area_max:.6g}]",
        "accounting=cumulative_[0,H]_from_t0",
        f"output={output_path}",
    )
    return metrics


def main() -> None:
    """Command-line entry point for N=10 SLA-compliance offline reranking.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory
        / "results"
        / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    compute_sla_candidate_metrics(
        args.results.resolve(),
        args.policy_config.resolve(),
        None if args.output is None else args.output.resolve(),
    )


if __name__ == "__main__":
    main()
