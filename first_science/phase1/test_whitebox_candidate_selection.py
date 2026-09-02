"""Simulator-independent tests for Phase-1 white-box finalist selection."""
from __future__ import annotations

import pandas as pd

from whitebox_candidate_selection import (
    build_whitebox_candidate_table,
    filter_informative_n10_candidates,
    rank_candidates_for_role,
    select_complementary_whitebox_proposal,
    summarize_reported_curve_shape,
)


def build_synthetic_selection_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create compact latency/cost/mixed candidate tables for deterministic tests.

    Called by:
        - all tests in this module.
    """
    representatives = pd.DataFrame(
        [
            {
                "physical_setting_id": "P1",
                "region_id": "A_latency",
                "center_instruction_mean": 400.0,
                "dispersion": 0.0,
                "l_max": 8.0,
                "c_max": 4.0,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 6,
                "cost_first_count": 1,
                "quality_first_count": 0,
                "tie_first_count": 0,
                "censored_count": 3,
            },
            {
                "physical_setting_id": "P2",
                "region_id": "A_cost",
                "center_instruction_mean": 300.0,
                "dispersion": 0.15,
                "l_max": 1.0,
                "c_max": 2.5,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 1,
                "cost_first_count": 5,
                "quality_first_count": 0,
                "tie_first_count": 0,
                "censored_count": 4,
            },
            {
                "physical_setting_id": "P3",
                "region_id": "A_mixed",
                "center_instruction_mean": 350.0,
                "dispersion": 0.1,
                "l_max": 2.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "sigma_anchor": 1.0,
                "latency_first_count": 3,
                "cost_first_count": 3,
                "quality_first_count": 0,
                "tie_first_count": 0,
                "censored_count": 4,
            },
        ]
    )
    diagnostics = pd.DataFrame(
        [
            {
                "physical_setting_id": "P1",
                "region_id": "A_latency",
                "l_max": 8.0,
                "c_max": 4.0,
                "q_min": 0.5,
                "n_unique_first_violation_times": 7,
                "n_failed_by_stop": 7,
                "longest_plateau_fraction_of_domain": 0.20,
                "split_half_curve_supremum_difference": 0.20,
            },
            {
                "physical_setting_id": "P2",
                "region_id": "A_cost",
                "l_max": 1.0,
                "c_max": 2.5,
                "q_min": 0.5,
                "n_unique_first_violation_times": 6,
                "n_failed_by_stop": 6,
                "longest_plateau_fraction_of_domain": 0.25,
                "split_half_curve_supremum_difference": 0.20,
            },
            {
                "physical_setting_id": "P3",
                "region_id": "A_mixed",
                "l_max": 2.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "n_unique_first_violation_times": 6,
                "n_failed_by_stop": 6,
                "longest_plateau_fraction_of_domain": 0.22,
                "split_half_curve_supremum_difference": 0.20,
            },
        ]
    )
    curves = []
    for physical_setting_id, region_id, values in [
        ("P1", "A_latency", [1.0, 0.9, 0.6, 0.3]),
        ("P2", "A_cost", [1.0, 0.9, 0.7, 0.4]),
        ("P3", "A_mixed", [1.0, 1.0, 0.7, 0.4]),
    ]:
        for horizon, sigma in zip([0.0, 120.0, 180.0, 240.0], values):
            curves.append(
                {
                    "physical_setting_id": physical_setting_id,
                    "region_id": region_id,
                    "horizon": horizon,
                    "sigma": sigma,
                }
            )
    return representatives, diagnostics, pd.DataFrame(curves)


def test_curve_shape_summary() -> None:
    """Verify reported-grid shape summaries retain anchor/stop information."""
    _, _, curves = build_synthetic_selection_fixture()
    summary = summarize_reported_curve_shape(curves, anchor_horizon=120.0)
    latency = summary[summary["region_id"] == "A_latency"].iloc[0]
    assert latency["sigma_anchor_from_curve"] == 0.9
    assert latency["sigma_stop"] == 0.3
    assert abs(latency["post_anchor_drop"] - 0.6) < 1e-12
    assert latency["n_distinct_sigma_levels"] == 4


def test_role_rankings_require_expected_first_violation_structure() -> None:
    """Verify latency/cost/mixed role filters use only white-box cause counts."""
    reps, diagnostics, curves = build_synthetic_selection_fixture()
    candidates = build_whitebox_candidate_table(
        reps, diagnostics, curves, anchor_horizon=120.0, target_survival=0.95
    )
    assert rank_candidates_for_role(candidates, "latency").iloc[0]["region_id"] == "A_latency"
    assert rank_candidates_for_role(candidates, "cost").iloc[0]["region_id"] == "A_cost"
    assert rank_candidates_for_role(candidates, "mixed").iloc[0]["region_id"] == "A_mixed"


def test_sparse_candidates_fail_information_gate() -> None:
    """Verify two-event N=10 curves cannot be frozen as next-phase whiteboxes."""
    reps, diagnostics, curves = build_synthetic_selection_fixture()
    candidates = build_whitebox_candidate_table(
        reps, diagnostics, curves, anchor_horizon=120.0, target_survival=0.95
    )
    sparse = candidates[candidates["region_id"] == "A_cost"].copy()
    sparse.loc[:, "n_failed_by_stop"] = 2
    sparse.loc[:, "n_unique_first_violation_times"] = 2
    sparse.loc[:, "n_distinct_sigma_levels"] = 3
    assert filter_informative_n10_candidates(sparse).empty
    assert rank_candidates_for_role(sparse, "cost").empty


def test_complementary_selection_uses_distinct_regions() -> None:
    """Verify the proposal contains one distinct region for each diagnostic role."""
    reps, diagnostics, curves = build_synthetic_selection_fixture()
    candidates = build_whitebox_candidate_table(
        reps, diagnostics, curves, anchor_horizon=120.0, target_survival=0.95
    )
    selected = select_complementary_whitebox_proposal(candidates)
    assert list(selected["selection_role"]) == ["latency", "cost", "mixed"]
    assert selected["region_id"].nunique() == 3


def run_all_whitebox_selection_tests() -> None:
    """Execute all simulator-independent white-box selection tests."""
    test_curve_shape_summary()
    test_role_rankings_require_expected_first_violation_structure()
    test_sparse_candidates_fail_information_gate()
    test_complementary_selection_uses_distinct_regions()
    print("PHASE1_WHITEBOX_SELECTION_TESTS_PASS")


if __name__ == "__main__":
    run_all_whitebox_selection_tests()
