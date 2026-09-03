"""Simulator-independent tests for SLA-based Phase-1 white-box selection."""
from __future__ import annotations

import pandas as pd

from selection_policy import load_sla_compliance_area_selection_policy
from whitebox_candidate_selection import (
    build_whitebox_candidate_table,
    rank_candidates_for_role,
    select_complementary_whitebox_proposal,
)


def build_policy():
    return load_sla_compliance_area_selection_policy(
        {
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
    )


def row(region, latency, cost, area=0.6, setting="P"):
    lc = latency + cost
    return {
        "physical_setting_id": setting,
        "region_id": region,
        "center_instruction_mean": 390e6,
        "dispersion": 0.1,
        "l_max": 10.0,
        "c_max": 3.0,
        "q_min": 0.5,
        "rho": 0.95,
        "normalized_sla_compliance_area": area,
        "sla_compliance_area_seconds": area * 240.0,
        "sigma_120_reporting": 0.6,
        "sigma_240_reporting": 0.7,
        "decided_request_count": 1000,
        "unresolved_request_count": 5,
        "compliant_request_count": 930,
        "failed_request_count": 70,
        "latency_failure_count": latency,
        "cost_failure_count": cost,
        "quality_failure_count": 0,
        "latency_failure_fraction_of_lc": latency / lc if lc else float("nan"),
        "cost_failure_fraction_of_lc": cost / lc if lc else float("nan"),
        "n_sigma_transition_times": 12,
        "maximum_empirical_sigma_jump": 0.1,
        "longest_sigma_plateau_fraction_of_domain": 0.2,
    }


def build_candidates():
    return pd.DataFrame(
        [
            row("L", 90, 10),
            row("C", 10, 90),
            row("M", 45, 55),
            row("OUT", 90, 10, area=0.9),
        ]
    )


def test_role_classification_uses_all_request_failures() -> None:
    policy = build_policy()
    candidates = build_whitebox_candidate_table(build_candidates(), policy)
    assert rank_candidates_for_role(candidates, "latency", policy).iloc[0]["region_id"] == "L"
    assert rank_candidates_for_role(candidates, "cost", policy).iloc[0]["region_id"] == "C"
    assert rank_candidates_for_role(candidates, "mixed", policy).iloc[0]["region_id"] == "M"


def test_area_gate_excludes_ceiling_candidate() -> None:
    policy = build_policy()
    candidates = build_whitebox_candidate_table(build_candidates(), policy)
    latency = rank_candidates_for_role(candidates, "latency", policy)
    assert "OUT" not in set(latency["region_id"])


def test_selection_prefers_matched_physical_regime() -> None:
    policy = build_policy()
    candidates = build_whitebox_candidate_table(build_candidates(), policy)
    selected = select_complementary_whitebox_proposal(
        candidates, policy, prefer_matched_physical_regime=True
    )
    assert list(selected["selection_role"]) == ["latency", "cost", "mixed"]
    assert selected["region_id"].nunique() == 3
    assert selected["physical_setting_id"].nunique() == 1
    assert bool(selected["matched_physical_regime"].all())


def run_all_tests() -> None:
    test_role_classification_uses_all_request_failures()
    test_area_gate_excludes_ceiling_candidate()
    test_selection_prefers_matched_physical_regime()
    print("PHASE1_WHITEBOX_SLA_SELECTION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
