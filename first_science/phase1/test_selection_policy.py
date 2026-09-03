"""Tests for the Phase-1 SLA-compliance selection policy."""
from __future__ import annotations

from selection_policy import (
    classify_lc_failure_role,
    load_sla_compliance_area_selection_policy,
)


def build_config():
    return {
        "sla_compliance": {
            "search_rho": 0.95,
            "accounting_origin": 0.0,
            "zero_decided_requests_compliance": 1.0,
            "accounting_window": "cumulative_[0,H]_from_t0",
            "rolling_windows_allowed": False,
        },
        "selection_quality_gate": {
            "metric": "normalized_sla_compliance_area",
            "normalized_sla_compliance_area": {
                "horizon_min": 0.0,
                "horizon_max": 240.0,
                "minimum": 0.5,
                "maximum": 0.75,
                "optimize_to_midpoint": False,
            },
            "role_evidence": {"dominance_ratio": 2.0},
        },
    }


def test_policy_loads_rho_and_parameterized_area_band() -> None:
    policy = load_sla_compliance_area_selection_policy(build_config())
    assert policy.sla_definition.rho == 0.95
    assert policy.horizon_min == 0.0
    assert policy.horizon_max == 240.0
    assert policy.area_min == 0.5
    assert policy.area_max == 0.75


def test_role_classifier_uses_all_request_failure_composition() -> None:
    assert classify_lc_failure_role(20, 2, 2.0) == "latency"
    assert classify_lc_failure_role(2, 20, 2.0) == "cost"
    assert classify_lc_failure_role(10, 12, 2.0) == "mixed"
    assert classify_lc_failure_role(0, 0, 2.0) == "no_lc_failure"


def test_midpoint_optimization_is_rejected() -> None:
    cfg = build_config()
    cfg["selection_quality_gate"]["normalized_sla_compliance_area"]["optimize_to_midpoint"] = True
    try:
        load_sla_compliance_area_selection_policy(cfg)
    except ValueError as exc:
        assert "midpoint" in str(exc)
    else:
        raise AssertionError("midpoint optimization unexpectedly accepted")


def run_all_tests() -> None:
    test_policy_loads_rho_and_parameterized_area_band()
    test_role_classifier_uses_all_request_failure_composition()
    test_midpoint_optimization_is_rejected()
    print("PHASE1_SLA_SELECTION_POLICY_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
