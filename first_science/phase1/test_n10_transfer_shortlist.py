"""Simulator-independent tests for N=10 to N=100 shortlist construction."""
from __future__ import annotations

import pandas as pd

from explore_n10_to_n100_transfer import build_n10_shortlist, rank_n10_candidates_for_role


def build_fixture() -> tuple[pd.DataFrame, dict]:
    """Create exact-AR rows spanning latency, mixed and cost roles."""
    rows = [
        {"physical_setting_id": "P", "region_id": "L0", "l_max": 1.0, "c_max": 9.0, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 8, "cost_first_count": 1},
        {"physical_setting_id": "P", "region_id": "L1", "l_max": 1.1, "c_max": 9.0, "q_min": 0.5, "sigma_anchor": 1.0, "latency_first_count": 7, "cost_first_count": 1},
        {"physical_setting_id": "P", "region_id": "L2", "l_max": 1.2, "c_max": 9.0, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 6, "cost_first_count": 1},
        {"physical_setting_id": "P", "region_id": "M0", "l_max": 2.0, "c_max": 3.0, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 4, "cost_first_count": 4},
        {"physical_setting_id": "P", "region_id": "M1", "l_max": 2.1, "c_max": 3.1, "q_min": 0.5, "sigma_anchor": 1.0, "latency_first_count": 3, "cost_first_count": 3},
        {"physical_setting_id": "P", "region_id": "M2", "l_max": 2.2, "c_max": 3.2, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 4, "cost_first_count": 3},
        {"physical_setting_id": "P", "region_id": "C0", "l_max": 9.0, "c_max": 2.0, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 0, "cost_first_count": 7},
        {"physical_setting_id": "P", "region_id": "C1", "l_max": 9.0, "c_max": 2.1, "q_min": 0.5, "sigma_anchor": 1.0, "latency_first_count": 0, "cost_first_count": 6},
        {"physical_setting_id": "P", "region_id": "C2", "l_max": 9.0, "c_max": 2.2, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 1, "cost_first_count": 5},
        {"physical_setting_id": "OTHER", "region_id": "OTHER", "l_max": 1.0, "c_max": 1.0, "q_min": 0.5, "sigma_anchor": 0.9, "latency_first_count": 9, "cost_first_count": 0},
    ]
    manifest = {
        "status": "FROZEN_FOR_CONFIRMATION",
        "whiteboxes": [
            {"case_id": "WB_L", "selection_role": "latency", "physical_setting_id": "P", "source_region_id": "L0"},
            {"case_id": "WB_M", "selection_role": "mixed", "physical_setting_id": "P", "source_region_id": "M0"},
            {"case_id": "WB_C", "selection_role": "cost", "physical_setting_id": "P", "source_region_id": "C0"},
        ],
    }
    return pd.DataFrame(rows), manifest


def test_role_ranking_uses_expected_n10_cause_structure() -> None:
    """Verify role ranking uses only N=10 cause counts and thresholds."""
    rows, _ = build_fixture()
    physical = rows[rows["physical_setting_id"] == "P"].copy()
    assert rank_n10_candidates_for_role(physical, "latency").iloc[0]["region_id"] == "L0"
    assert rank_n10_candidates_for_role(physical, "mixed").iloc[0]["region_id"] == "M0"
    assert rank_n10_candidates_for_role(physical, "cost").iloc[0]["region_id"] == "C0"


def test_shortlist_retains_frozen_and_adds_bracket_alternatives() -> None:
    """Verify frozen rows survive and exact alternatives come only from P."""
    rows, manifest = build_fixture()
    shortlist = build_n10_shortlist(rows, manifest, per_role_per_sigma=1)
    region_ids = set(shortlist["region_id"].astype(str))
    assert {"L0", "M0", "C0"}.issubset(region_ids)
    assert "OTHER" not in region_ids
    assert set(shortlist["physical_setting_id"].astype(str)) == {"P"}
    assert set(shortlist["exploration_role"].astype(str)) == {"latency", "mixed", "cost"}
    assert set(shortlist["sigma_anchor"].astype(float)).issubset({0.9, 1.0})


def run_all_tests() -> None:
    """Execute all simulator-independent shortlist tests."""
    test_role_ranking_uses_expected_n10_cause_structure()
    test_shortlist_retains_frozen_and_adds_bracket_alternatives()
    print("PHASE1_N10_N100_TRANSFER_SHORTLIST_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
