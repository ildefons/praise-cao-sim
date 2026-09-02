"""Offline admissibility-region atlas for PRAISE Phase-1 white-box traces.

This module contains no AICon/YAFS imports. It consumes top-level request
ledgers produced by the native simulator and scans admissibility regions
A={L<=l, C<=c, Q>=q} without rerunning the physical simulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FirstViolationObservation:
    """Represent one trajectory's first known top-level admissibility violation.

    Args:
        time: First violation time, or ``None`` when no violation is known by stop.
        cause: ``latency``, ``cost``, ``quality``, ``tie``, or ``censored``.

    Called by:
        - ``calculate_first_violation_observation_for_trajectory`` in this module.
        - ``scan_admissibility_regions_for_one_physical_setting`` in this module.
    """

    time: float | None
    cause: str


def calculate_first_violation_observation_for_trajectory(
    trajectory_request_ledger: pd.DataFrame,
    latency_threshold: float,
    cost_threshold: float,
    quality_threshold: float,
    stop_time: float,
) -> FirstViolationObservation:
    """Calculate the first known violation time and cause for one trajectory.

    Latency can fail at ``emission + latency_threshold`` when the request has
    not completed by that deadline. Cost and quality become observable only at
    top-level completion. Requests with no known violation by ``stop_time`` are
    right-censored rather than counted as failures.

    Args:
        trajectory_request_ledger: One row per root request for one trajectory.
        latency_threshold: Inclusive top-level latency limit ``l``.
        cost_threshold: Inclusive top-level cost limit ``c``.
        quality_threshold: Inclusive minimum top-level quality ``q``.
        stop_time: Common simulator stopping time.

    Returns:
        FirstViolationObservation for the trajectory.

    Called by:
        - ``scan_admissibility_regions_for_one_physical_setting`` in this module.
        - ``test_first_violation_cause_semantics`` in ``test_atlas_analysis.py``.
    """
    candidate_events: list[tuple[float, str]] = []
    latency_limit = float(latency_threshold)
    cost_limit = float(cost_threshold)
    quality_limit = float(quality_threshold)
    stop = float(stop_time)

    for request in trajectory_request_ledger.itertuples(index=False):
        emission = float(request.emission)
        completion = None if pd.isna(request.completion) else float(request.completion)

        latency_deadline = emission + latency_limit
        request_completed_by_deadline = completion is not None and completion <= latency_deadline + 1e-12
        if latency_deadline <= stop + 1e-12 and not request_completed_by_deadline:
            candidate_events.append((latency_deadline, "latency"))

        if completion is not None and completion <= stop + 1e-12:
            if not pd.isna(request.C) and float(request.C) > cost_limit:
                candidate_events.append((completion, "cost"))
            if not pd.isna(request.Q) and float(request.Q) < quality_limit:
                candidate_events.append((completion, "quality"))

    if not candidate_events:
        return FirstViolationObservation(time=None, cause="censored")

    earliest_time = min(event_time for event_time, _ in candidate_events)
    earliest_causes = sorted(
        {
            cause
            for event_time, cause in candidate_events
            if abs(event_time - earliest_time) <= 1e-12
        }
    )
    cause = earliest_causes[0] if len(earliest_causes) == 1 else "tie"
    return FirstViolationObservation(time=float(earliest_time), cause=cause)


def calculate_empirical_survival_curve_from_first_violation_observations(
    first_violation_observations: Iterable[FirstViolationObservation],
    horizons: Iterable[float],
    stop_time: float,
) -> pd.DataFrame:
    """Calculate empirical ``P(T_violation > H)`` on a common censoring horizon.

    Args:
        first_violation_observations: One first-violation observation per trajectory.
        horizons: Horizons at which survival is required.
        stop_time: Common simulator stopping time; horizons may not exceed it.

    Returns:
        DataFrame with columns ``horizon`` and ``sigma``.

    Called by:
        - ``scan_admissibility_regions_for_one_physical_setting`` in this module.
        - ``test_survival_curve_uses_strict_greater_than_convention`` in
          ``test_atlas_analysis.py``.
    """
    observations = list(first_violation_observations)
    if not observations:
        raise ValueError("at least one trajectory observation is required")

    rows: list[dict[str, float]] = []
    stop = float(stop_time)
    for horizon in map(float, horizons):
        if horizon > stop + 1e-12:
            raise ValueError("survival horizon cannot exceed stop_time")
        survivors = 0
        for observation in observations:
            if observation.time is None or float(observation.time) > horizon:
                survivors += 1
        rows.append({"horizon": horizon, "sigma": survivors / len(observations)})
    return pd.DataFrame(rows)


def calculate_anchor_critical_latency_for_trajectory(
    trajectory_request_ledger: pd.DataFrame,
    anchor_horizon: float,
) -> float:
    """Calculate the minimum latency threshold needed to survive through H*.

    Completed requests contribute their realized top-level latency. Requests
    emitted by H* but incomplete at H* contribute their age ``H*-emission``;
    the scanner later evaluates thresholds immediately above and below these
    critical values to handle the strict ``T_violation > H`` convention.

    Called by:
        - ``build_anchor_informed_admissibility_threshold_candidates`` in this module.
        - ``test_anchor_critical_thresholds`` in ``test_atlas_analysis.py``.
    """
    anchor = float(anchor_horizon)
    critical_values: list[float] = [0.0]
    for request in trajectory_request_ledger.itertuples(index=False):
        emission = float(request.emission)
        if emission > anchor + 1e-12:
            continue
        completion = None if pd.isna(request.completion) else float(request.completion)
        if completion is not None and completion <= anchor + 1e-12:
            critical_values.append(float(request.L))
        else:
            critical_values.append(max(0.0, anchor - emission))
    return float(max(critical_values))


def calculate_anchor_critical_cost_for_trajectory(
    trajectory_request_ledger: pd.DataFrame,
    anchor_horizon: float,
) -> float:
    """Calculate the largest cost observable by H* in one trajectory.

    Only top-level requests completed by the anchor horizon contribute because
    cost violation becomes observable at completion under the frozen semantics.

    Called by:
        - ``build_anchor_informed_admissibility_threshold_candidates`` in this module.
        - ``test_anchor_critical_thresholds`` in ``test_atlas_analysis.py``.
    """
    anchor = float(anchor_horizon)
    completed = trajectory_request_ledger[
        trajectory_request_ledger["completion"].notna()
        & (trajectory_request_ledger["completion"].astype(float) <= anchor + 1e-12)
    ]
    if completed.empty:
        return 0.0
    return float(completed["C"].max())


def build_anchor_informed_admissibility_threshold_candidates(
    physical_setting_request_ledger: pd.DataFrame,
    anchor_horizon: float,
    threshold_relative_epsilon: float,
    unconstrained_threshold_multiplier: float,
) -> tuple[list[float], list[float]]:
    """Build compact L/C threshold grids from trajectory-level H* critical values.

    For each trajectory, thresholds immediately below and above its critical L
    and C values are included. This makes the N=10 development atlas enumerate
    the survival transitions actually achievable at H* without an arbitrary
    dense numerical grid. A loose upper threshold is also included for each axis.

    Called by:
        - ``scan_admissibility_regions_for_one_physical_setting`` in this module.
        - ``test_threshold_candidate_generation_brackets_transitions`` in
          ``test_atlas_analysis.py``.
    """
    required_columns = {"trajectory", "emission", "completion", "L", "C", "Q"}
    missing = required_columns.difference(physical_setting_request_ledger.columns)
    if missing:
        raise ValueError(f"request ledger missing required columns: {sorted(missing)}")

    relative_epsilon = float(threshold_relative_epsilon)
    if not 0.0 < relative_epsilon < 1e-3:
        raise ValueError("threshold_relative_epsilon must be small and positive")

    latency_critical_values: list[float] = []
    cost_critical_values: list[float] = []
    for _, trajectory_ledger in physical_setting_request_ledger.groupby("trajectory", sort=True):
        latency_critical_values.append(
            calculate_anchor_critical_latency_for_trajectory(trajectory_ledger, anchor_horizon)
        )
        cost_critical_values.append(
            calculate_anchor_critical_cost_for_trajectory(trajectory_ledger, anchor_horizon)
        )

    def build_thresholds_immediately_below_and_above_critical_values(values: list[float]) -> list[float]:
        """Bracket critical values with tiny below/above threshold candidates.

        Called by:
            - ``build_anchor_informed_admissibility_threshold_candidates`` in this module.
        """
        candidates = {0.0}
        for value in values:
            value = max(0.0, float(value))
            scale = max(1.0, abs(value))
            candidates.add(max(0.0, value - relative_epsilon * scale))
            candidates.add(value)
            candidates.add(value + relative_epsilon * scale)
        maximum = max(values) if values else 0.0
        candidates.add(maximum * float(unconstrained_threshold_multiplier) + relative_epsilon)
        return sorted(candidates)

    return (
        build_thresholds_immediately_below_and_above_critical_values(latency_critical_values),
        build_thresholds_immediately_below_and_above_critical_values(cost_critical_values),
    )


def scan_admissibility_regions_for_one_physical_setting(
    physical_setting_request_ledger: pd.DataFrame,
    physical_setting_id: str,
    center_instruction_mean: float,
    dispersion: float,
    quality_threshold: float,
    anchor_horizon: float,
    horizons: Iterable[float],
    stop_time: float,
    threshold_relative_epsilon: float,
    unconstrained_threshold_multiplier: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Enumerate anchor-informed ARs and their complete empirical survival curves.

    Args:
        physical_setting_request_ledger: All N trajectory request rows for one
            physical ``(center, dispersion)`` setting.
        physical_setting_id: Stable identifier written to outputs.
        center_instruction_mean: Physical central gamma instruction mean.
        dispersion: Symmetric provider dispersion.
        quality_threshold: Frozen ``q*=x`` for this development atlas.
        anchor_horizon: H* used to enumerate achievable anchor survival levels.
        horizons: Full horizon grid for survival-curve output.
        stop_time: Common simulator stop time.
        threshold_relative_epsilon: Small relative bracket around critical values.
        unconstrained_threshold_multiplier: Loose-threshold multiplier.

    Returns:
        ``(region_summary, survival_curves)`` data frames.

    Called by:
        - ``scan_all_physical_settings_and_write_atlas_outputs`` in
          ``whitebox_atlas.py``.
        - ``test_scan_recovers_multiple_anchor_survival_levels`` in
          ``test_atlas_analysis.py``.
    """
    latency_candidates, cost_candidates = build_anchor_informed_admissibility_threshold_candidates(
        physical_setting_request_ledger,
        anchor_horizon=anchor_horizon,
        threshold_relative_epsilon=threshold_relative_epsilon,
        unconstrained_threshold_multiplier=unconstrained_threshold_multiplier,
    )

    summary_rows: list[dict[str, float | int | str]] = []
    survival_rows: list[pd.DataFrame] = []
    grouped_trajectories = list(physical_setting_request_ledger.groupby("trajectory", sort=True))

    region_index = 0
    for latency_threshold in latency_candidates:
        for cost_threshold in cost_candidates:
            observations = [
                calculate_first_violation_observation_for_trajectory(
                    trajectory_ledger,
                    latency_threshold=latency_threshold,
                    cost_threshold=cost_threshold,
                    quality_threshold=quality_threshold,
                    stop_time=stop_time,
                )
                for _, trajectory_ledger in grouped_trajectories
            ]
            survival_curve = calculate_empirical_survival_curve_from_first_violation_observations(
                observations,
                horizons=horizons,
                stop_time=stop_time,
            )
            anchor_row = survival_curve.iloc[
                int(np.argmin(np.abs(survival_curve["horizon"].to_numpy() - float(anchor_horizon))))
            ]
            if abs(float(anchor_row["horizon"]) - float(anchor_horizon)) > 1e-12:
                raise ValueError("anchor_horizon must be present in the horizon grid")

            region_id = f"{physical_setting_id}_A{region_index:05d}"
            cause_counts = pd.Series([observation.cause for observation in observations]).value_counts()
            summary_rows.append(
                {
                    "physical_setting_id": physical_setting_id,
                    "region_id": region_id,
                    "center_instruction_mean": float(center_instruction_mean),
                    "dispersion": float(dispersion),
                    "l_max": float(latency_threshold),
                    "c_max": float(cost_threshold),
                    "q_min": float(quality_threshold),
                    "sigma_anchor": float(anchor_row["sigma"]),
                    "n_trajectories": len(observations),
                    "latency_first_count": int(cause_counts.get("latency", 0)),
                    "cost_first_count": int(cause_counts.get("cost", 0)),
                    "quality_first_count": int(cause_counts.get("quality", 0)),
                    "tie_first_count": int(cause_counts.get("tie", 0)),
                    "censored_count": int(cause_counts.get("censored", 0)),
                }
            )
            tagged_curve = survival_curve.copy()
            tagged_curve.insert(0, "region_id", region_id)
            tagged_curve.insert(0, "physical_setting_id", physical_setting_id)
            survival_rows.append(tagged_curve)
            region_index += 1

    return pd.DataFrame(summary_rows), pd.concat(survival_rows, ignore_index=True)


def select_representative_regions_for_each_achievable_anchor_survival(
    region_summary: pd.DataFrame,
    representatives_per_anchor_survival: int,
) -> pd.DataFrame:
    """Select compact L-dominant, balanced, and C-dominant AR examples per sigma.

    The selection is descriptive only. It minimizes the absolute difference
    between latency-first and cost-first counts for a balanced representative,
    and separately prefers large positive/negative cause-count differences for
    latency- and cost-dominant representatives.

    Called by:
        - ``scan_all_physical_settings_and_write_atlas_outputs`` in
          ``whitebox_atlas.py``.
        - ``test_representative_selection_covers_achievable_sigma`` in
          ``test_atlas_analysis.py``.
    """
    if region_summary.empty:
        return region_summary.copy()

    maximum_representatives = max(1, int(representatives_per_anchor_survival))
    selected_rows: list[pd.Series] = []
    grouping_columns = ["physical_setting_id", "sigma_anchor"]
    for _, group in region_summary.groupby(grouping_columns, sort=True):
        ranked = group.copy()
        ranked["cause_difference"] = ranked["latency_first_count"] - ranked["cost_first_count"]
        candidate_indices: list[int] = []
        candidate_indices.append(int(ranked["cause_difference"].idxmax()))
        candidate_indices.append(int(ranked["cause_difference"].abs().idxmin()))
        candidate_indices.append(int(ranked["cause_difference"].idxmin()))
        for index in candidate_indices[:maximum_representatives]:
            if index not in [row.name for row in selected_rows]:
                selected_rows.append(ranked.loc[index])

    output = pd.DataFrame(selected_rows).drop(columns=["cause_difference"], errors="ignore")
    return output.sort_values(["physical_setting_id", "sigma_anchor", "region_id"]).reset_index(drop=True)
