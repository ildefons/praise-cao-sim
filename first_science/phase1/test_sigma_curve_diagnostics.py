"""Simulator-independent tests for Phase-1 sigma resolution diagnostics."""
from __future__ import annotations

import pandas as pd

from atlas_analysis import FirstViolationObservation
from sigma_curve_diagnostics import (
    calculate_exact_first_crossing_below_target,
    calculate_no_violation_probability_through_horizon,
    calculate_sigma_resolution_diagnostics_for_region,
)


def create_three_trajectory_resolution_fixture() -> tuple[pd.DataFrame, pd.Series]:
    """Create three trajectories with exact violation events at known times.

    Returns:
        Top-level request ledger and one representative-region row.

    Called by:
        - ``test_resolution_diagnostics_report_expected_jump_size`` in this module.
    """
    ledger = pd.DataFrame(
        [
            {
                "physical_setting_id": "fixture",
                "trajectory": 0,
                "request_id": 0,
                "emission": 0.0,
                "completion": 2.0,
                "L": 2.0,
                "C": 1.0,
                "Q": 0.5,
            },
            {
                "physical_setting_id": "fixture",
                "trajectory": 1,
                "request_id": 1,
                "emission": 0.0,
                "completion": 4.0,
                "L": 4.0,
                "C": 1.0,
                "Q": 0.5,
            },
            {
                "physical_setting_id": "fixture",
                "trajectory": 2,
                "request_id": 2,
                "emission": 0.0,
                "completion": 1.0,
                "L": 1.0,
                "C": 1.0,
                "Q": 0.5,
            },
        ]
    )
    region = pd.Series(
        {
            "physical_setting_id": "fixture",
            "region_id": "fixture_A",
            "l_max": 3.0,
            "c_max": 10.0,
            "q_min": 0.5,
        }
    )
    return ledger, region


def test_primary_no_violation_semantics_matches_first_event_form() -> None:
    """Verify cumulative no-violation semantics equal T_first > H.

    Called by:
        - ``run_all_sigma_curve_diagnostic_tests`` in this module.
    """
    observations = [
        FirstViolationObservation(time=2.5, cause="latency"),
        FirstViolationObservation(time=7.0, cause="cost"),
        FirstViolationObservation(time=None, cause="censored"),
    ]
    assert calculate_no_violation_probability_through_horizon(observations, 0.0) == 1.0
    assert calculate_no_violation_probability_through_horizon(observations, 2.5) == 2.0 / 3.0
    assert calculate_no_violation_probability_through_horizon(observations, 6.0) == 2.0 / 3.0
    assert calculate_no_violation_probability_through_horizon(observations, 7.0) == 1.0 / 3.0


def test_exact_crossing_uses_event_time_not_reporting_grid() -> None:
    """Verify target crossing is located at an exact event time.

    Called by:
        - ``run_all_sigma_curve_diagnostic_tests`` in this module.
    """
    observations = [
        FirstViolationObservation(time=12.37, cause="latency"),
        FirstViolationObservation(time=90.11, cause="cost"),
        FirstViolationObservation(time=None, cause="censored"),
        FirstViolationObservation(time=None, cause="censored"),
    ]
    crossing = calculate_exact_first_crossing_below_target(
        observations,
        target_survival=0.80,
        stop_time=120.0,
    )
    assert abs(float(crossing) - 12.37) < 1e-12


def test_resolution_diagnostics_report_expected_jump_size() -> None:
    """Verify finite-N diagnostics report exact empirical staircase resolution.

    Called by:
        - ``run_all_sigma_curve_diagnostic_tests`` in this module.
    """
    ledger, region = create_three_trajectory_resolution_fixture()
    diagnostics = calculate_sigma_resolution_diagnostics_for_region(
        physical_setting_request_ledger=ledger,
        representative_region=region,
        anchor_horizon=3.0,
        target_survival=0.8,
        stop_time=6.0,
    )
    assert diagnostics["n_trajectories"] == 3
    assert abs(diagnostics["vertical_probability_resolution"] - 1.0 / 3.0) < 1e-12
    assert diagnostics["n_failed_by_anchor"] == 1
    assert abs(diagnostics["sigma_anchor_exact"] - 2.0 / 3.0) < 1e-12
    assert diagnostics["n_unique_first_violation_times"] == 1
    assert abs(diagnostics["maximum_empirical_jump"] - 1.0 / 3.0) < 1e-12
    assert abs(float(diagnostics["exact_first_crossing_below_target"]) - 3.0) < 1e-12


def run_all_sigma_curve_diagnostic_tests() -> None:
    """Execute all simulator-independent sigma diagnostic tests.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    test_primary_no_violation_semantics_matches_first_event_form()
    test_exact_crossing_uses_event_time_not_reporting_grid()
    test_resolution_diagnostics_report_expected_jump_size()
    print("PHASE1_SIGMA_CURVE_DIAGNOSTIC_TESTS_PASS")


if __name__ == "__main__":
    run_all_sigma_curve_diagnostic_tests()
