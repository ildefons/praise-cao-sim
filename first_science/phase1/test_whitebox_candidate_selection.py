"""Simulator-independent tests for revised Phase-1 AUC finalist selection."""
from __future__ import annotations

import pandas as pd

from selection_policy import SurvivalAreaSelectionPolicy
from whitebox_candidate_selection import (
    build_whitebox_candidate_table,
    filter_nondegenerate_n10_candidates,
    rank_candidates_for_role,
    select_complementary_whitebox_proposal,
)


def policy() -> SurvivalAreaSelectionPolicy:
    """Return the current test-only parameterized area policy."""
    return SurvivalAreaSelectionPolicy(
        horizon_min=0.0,
        horizon_max=240.0,
        area_min=0.50,
        area_max=0.75,
        optimize_to_midpoint=False,
        min_dominant_cause_count=3,
        dominance_ratio=2.0,
        min_mixed_cause_count_each=2,
        max_mixed_cause_imbalance=2,
    )


def metrics_fixture() -> pd.DataFrame:
    """Create compact exact-event candidate metrics for deterministic tests."""
    common = {
        "q_min": 0.5,
        "restricted_survival_area_seconds": 144.0,
        "sigma_120_reporting": 0.7,
        "quality_first_count_exact": 0,
        "tie_first_count_exact": 0,
        "censored_count_exact": 2,
        "n_unique_first_violation_times": 8,
        "maximum_empirical_jump": 0.1,
        "longest_plateau_fraction_of_domain": 0.2,
    }
    rows = [
        {
            **common,
            "physical_setting_id": "P_MATCH",
            "region_id": "A_latency",
            "center_instruction_mean": 390.0,
            "dispersion": 0.15,
            "l_max": 10.0,
            "c_max": 4.0,
            "normalized_restricted_survival_area": 0.60,
            "latency_first_count_exact": 8,
            "cost_first_count_exact": 0,
        },
        {
            **common,
            "physical_setting_id": "P_MATCH",
            "region_id": "A_cost",
            "center_instruction_mean": 390.0,
            "dispersion": 0.15,
            "l_max": 30.0,
            "c_max": 3.0,
            "normalized_restricted_survival_area": 0.68,
            "latency_first_count_exact": 0,
            "cost_first_count_exact": 6,
        },
        {
            **common,
            "physical_setting_id": "P_MATCH",
            "region_id": "A_mixed",
            "center_instruction_mean": 390.0,
            "dispersion": 0.15,
            "l_max": 18.0,
            "c_max": 3.0,
            "normalized_restricted_survival_area": 0.55,
            "latency_first_count_exact": 4,
            "cost_first_count_exact": 4,
        },
        {
            **common,
            "physical_setting_id": "P_OUT",
            "region_id": "A_outside",
            "center_instruction_mean": 300.0,
            "dispersion": 0.0,
            "l_max": 1.0,
            "c_max": 1.0,
            "normalized_restricted_survival_area": 0.90,
            "latency_first_count_exact": 9,
            "cost_first_count_exact": 0,
        },
    ]
    return pd.DataFrame(rows)


def test_area_band_is_gate_not_midpoint_optimization() -> None:
    """Verify both 0.55 and 0.68 pass while 0.90 fails the configured gate."""
    candidates = build_whitebox_candidate_table(metrics_fixture(), policy())
    eligible = filter_nondegenerate_n10_candidates(candidates, policy())
    assert set(eligible["region_id"]) == {"A_latency", "A_cost", "A_mixed"}
    assert candidates.loc[candidates["region_id"] == "A_cost", "inside_survival_area_band"].iloc[0]


def test_role_rankings_use_failure_mechanism_after_area_gate() -> None:
    """Verify role assignment happens only after the common AUC gate."""
    candidates = build_whitebox_candidate_table(metrics_fixture(), policy())
    assert rank_candidates_for_role(candidates, "latency", policy()).iloc[0]["region_id"] == "A_latency"
    assert rank_candidates_for_role(candidates, "cost", policy()).iloc[0]["region_id"] == "A_cost"
    assert rank_candidates_for_role(candidates, "mixed", policy()).iloc[0]["region_id"] == "A_mixed"


def test_matched_physical_regime_is_preferred_when_all_roles_exist() -> None:
    """Verify the proposal uses one physical setting when a complete matched battery exists."""
    candidates = build_whitebox_candidate_table(metrics_fixture(), policy())
    selected = select_complementary_whitebox_proposal(
        candidates,
        policy(),
        prefer_matched_physical_regime=True,
    )
    assert list(selected["selection_role"]) == ["latency", "cost", "mixed"]
    assert selected["physical_setting_id"].nunique() == 1
    assert selected["matched_physical_regime"].all()


def run_all_whitebox_selection_tests() -> None:
    """Execute revised simulator-independent white-box selection tests."""
    test_area_band_is_gate_not_midpoint_optimization()
    test_role_rankings_use_failure_mechanism_after_area_gate()
    test_matched_physical_regime_is_preferred_when_all_roles_exist()
    print("PHASE1_WHITEBOX_AUC_SELECTION_TESTS_PASS")


if __name__ == "__main__":
    run_all_whitebox_selection_tests()
