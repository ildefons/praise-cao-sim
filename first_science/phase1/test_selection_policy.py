"""Tests for the parameterized Phase-1 survival-area selection policy."""
from __future__ import annotations

from selection_policy import load_survival_area_selection_policy


def base_configuration() -> dict:
    """Create a minimal test-only area-selection configuration."""
    return {
        "selection_quality_gate": {
            "metric": "normalized_restricted_survival_area",
            "normalized_restricted_survival_area": {
                "horizon_min": 0.0,
                "horizon_max": 240.0,
                "minimum": 0.5,
                "maximum": 0.75,
                "parameterized_band": True,
                "optimize_to_midpoint": False,
            },
            "role_evidence": {
                "min_dominant_cause_count": 3,
                "dominance_ratio": 2.0,
                "min_mixed_cause_count_each": 2,
                "max_mixed_cause_imbalance": 2,
            },
        }
    }


def test_current_default_band_is_half_to_three_quarters() -> None:
    """Verify the current configured default without hard-coding it in the selector."""
    policy = load_survival_area_selection_policy(base_configuration())
    assert policy.area_min == 0.5
    assert policy.area_max == 0.75
    assert policy.optimize_to_midpoint is False


def test_band_can_change_by_configuration_without_code_change() -> None:
    """Verify a justified future band revision is purely a configuration change."""
    configuration = base_configuration()
    area = configuration["selection_quality_gate"]["normalized_restricted_survival_area"]
    area["minimum"] = 1.0 / 3.0
    area["maximum"] = 2.0 / 3.0
    policy = load_survival_area_selection_policy(configuration)
    assert abs(policy.area_min - 1.0 / 3.0) < 1e-12
    assert abs(policy.area_max - 2.0 / 3.0) < 1e-12


def test_midpoint_optimization_is_rejected() -> None:
    """Verify the interval cannot silently become a target-at-the-middle objective."""
    configuration = base_configuration()
    configuration["selection_quality_gate"]["normalized_restricted_survival_area"]["optimize_to_midpoint"] = True
    try:
        load_survival_area_selection_policy(configuration)
    except ValueError as exc:
        assert "midpoint" in str(exc)
    else:
        raise AssertionError("midpoint optimization unexpectedly passed")


def run_all_selection_policy_tests() -> None:
    """Execute all selection-policy tests."""
    test_current_default_band_is_half_to_three_quarters()
    test_band_can_change_by_configuration_without_code_change()
    test_midpoint_optimization_is_rejected()
    print("PHASE1_SELECTION_POLICY_TESTS_PASS")


if __name__ == "__main__":
    run_all_selection_policy_tests()
