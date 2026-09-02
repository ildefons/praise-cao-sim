"""Simulator-independent tests for Phase-1 admissibility-atlas analysis."""
from __future__ import annotations

import pandas as pd

from atlas_analysis import (
    FirstViolationObservation,
    build_anchor_informed_admissibility_threshold_candidates,
    calculate_anchor_critical_cost_for_trajectory,
    calculate_anchor_critical_latency_for_trajectory,
    calculate_empirical_survival_curve_from_first_violation_observations,
    calculate_first_violation_observation_for_trajectory,
    scan_admissibility_regions_for_one_physical_setting,
    select_representative_regions_for_each_achievable_anchor_survival,
)


def create_hand_checkable_top_level_request_ledger() -> pd.DataFrame:
    """Create two root requests with known L/C violation timing.

    Called by:
        - ``test_first_violation_cause_semantics`` in this module.
        - ``test_anchor_critical_thresholds`` in this module.
    """
    return pd.DataFrame(
        [
            {"trajectory": 0, "request_id": 1, "emission": 1.0, "completion": 4.0, "L": 3.0, "C": 2.0, "Q": 0.5},
            {"trajectory": 0, "request_id": 2, "emission": 8.0, "completion": 13.0, "L": 5.0, "C": 7.0, "Q": 0.5},
        ]
    )


def create_ten_trajectory_atlas_fixture() -> pd.DataFrame:
    """Create ten trajectories with monotonically increasing latency and cost.

    Called by:
        - ``test_threshold_candidate_generation_brackets_transitions`` in this module.
        - ``test_scan_recovers_multiple_anchor_survival_levels`` in this module.
    """
    rows = []
    for trajectory in range(10):
        latency = 1.0 + trajectory
        cost = 10.0 + trajectory
        rows.append(
            {
                "trajectory": trajectory,
                "request_id": trajectory,
                "emission": 1.0,
                "completion": 1.0 + latency,
                "L": latency,
                "C": cost,
                "Q": 0.5,
            }
        )
    return pd.DataFrame(rows)


def test_first_violation_cause_semantics() -> None:
    """Verify latency deadlines and completion-time cost violations.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    ledger = create_hand_checkable_top_level_request_ledger()
    latency_first = calculate_first_violation_observation_for_trajectory(
        ledger, latency_threshold=2.0, cost_threshold=100.0, quality_threshold=0.5, stop_time=20.0
    )
    assert latency_first == FirstViolationObservation(time=3.0, cause="latency")

    cost_first = calculate_first_violation_observation_for_trajectory(
        ledger, latency_threshold=100.0, cost_threshold=5.0, quality_threshold=0.5, stop_time=20.0
    )
    assert cost_first == FirstViolationObservation(time=13.0, cause="cost")


def test_survival_curve_uses_strict_greater_than_convention() -> None:
    """Verify a violation exactly at H is not counted as survival.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    observations = [
        FirstViolationObservation(time=5.0, cause="latency"),
        FirstViolationObservation(time=None, cause="censored"),
    ]
    curve = calculate_empirical_survival_curve_from_first_violation_observations(
        observations, horizons=[0.0, 5.0, 10.0], stop_time=10.0
    )
    assert curve["sigma"].tolist() == [1.0, 0.5, 0.5]


def test_anchor_critical_thresholds() -> None:
    """Verify trajectory-level H* critical latency and cost values.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    ledger = create_hand_checkable_top_level_request_ledger()
    assert calculate_anchor_critical_latency_for_trajectory(ledger, anchor_horizon=10.0) == 3.0
    assert calculate_anchor_critical_cost_for_trajectory(ledger, anchor_horizon=10.0) == 2.0


def test_threshold_candidate_generation_brackets_transitions() -> None:
    """Verify generated L/C candidates surround every N=10 critical value.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    fixture = create_ten_trajectory_atlas_fixture()
    latency_candidates, cost_candidates = build_anchor_informed_admissibility_threshold_candidates(
        fixture,
        anchor_horizon=20.0,
        threshold_relative_epsilon=1e-9,
        unconstrained_threshold_multiplier=1.05,
    )
    assert len(latency_candidates) >= 21
    assert len(cost_candidates) >= 21
    assert max(latency_candidates) > 10.0
    assert max(cost_candidates) > 19.0


def test_scan_recovers_multiple_anchor_survival_levels() -> None:
    """Verify the N=10 atlas exposes multiple 0.1-resolution sigma levels.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    fixture = create_ten_trajectory_atlas_fixture()
    summary, curves = scan_admissibility_regions_for_one_physical_setting(
        fixture,
        physical_setting_id="fixture",
        center_instruction_mean=1.0,
        dispersion=0.0,
        quality_threshold=0.5,
        anchor_horizon=20.0,
        horizons=[0.0, 10.0, 20.0],
        stop_time=20.0,
        threshold_relative_epsilon=1e-9,
        unconstrained_threshold_multiplier=1.05,
    )
    achievable = set(summary["sigma_anchor"].round(10).tolist())
    assert 0.0 in achievable
    assert 0.5 in achievable
    assert 1.0 in achievable
    assert not curves.empty


def test_representative_selection_covers_achievable_sigma() -> None:
    """Verify compact representatives retain every achievable sigma group.

    Called by:
        - ``execute_all_phase1_atlas_analysis_tests`` in this module.
    """
    fixture = create_ten_trajectory_atlas_fixture()
    summary, _ = scan_admissibility_regions_for_one_physical_setting(
        fixture,
        physical_setting_id="fixture",
        center_instruction_mean=1.0,
        dispersion=0.0,
        quality_threshold=0.5,
        anchor_horizon=20.0,
        horizons=[0.0, 10.0, 20.0],
        stop_time=20.0,
        threshold_relative_epsilon=1e-9,
        unconstrained_threshold_multiplier=1.05,
    )
    representatives = select_representative_regions_for_each_achievable_anchor_survival(summary, 3)
    assert set(representatives["sigma_anchor"].round(10)) == set(summary["sigma_anchor"].round(10))


def execute_all_phase1_atlas_analysis_tests() -> None:
    """Execute all simulator-independent Phase-1 atlas tests.

    Called by:
        - Python ``__main__`` entry point of ``test_atlas_analysis.py``.
    """
    test_first_violation_cause_semantics()
    test_survival_curve_uses_strict_greater_than_convention()
    test_anchor_critical_thresholds()
    test_threshold_candidate_generation_brackets_transitions()
    test_scan_recovers_multiple_anchor_survival_levels()
    test_representative_selection_covers_achievable_sigma()
    print("PHASE1_ATLAS_ANALYSIS_TESTS_PASS")


if __name__ == "__main__":
    execute_all_phase1_atlas_analysis_tests()
