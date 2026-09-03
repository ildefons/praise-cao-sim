"""Simulator-independent tests for five-battery N=100 stability calibration."""
from __future__ import annotations

import pandas as pd

from run_n100_shortlist_calibration import (
    select_first_stable_battery,
    summarize_battery_passes,
)


def _summary_row(rank, setting, score, role, passed):
    return {
        "shortlist_rank": rank,
        "physical_setting_id": setting,
        "triplet_score": score,
        "selection_role": role,
        "scientific_confirmation_pass": passed,
    }


def test_first_pre_ranked_passing_battery_is_selected() -> None:
    rows = []
    for role in ("latency", "cost", "mixed"):
        rows.append(_summary_row(1, "P1", 7, role, role != "mixed"))
    for role in ("latency", "cost", "mixed"):
        rows.append(_summary_row(2, "P2", 10, role, True))
    for role in ("latency", "cost", "mixed"):
        rows.append(_summary_row(3, "P3", 18, role, True))
    summary = pd.DataFrame(rows)
    battery_summary = summarize_battery_passes(summary)
    shortlist = {
        "batteries": [
            {"shortlist_rank": 1, "physical_setting_id": "P1"},
            {"shortlist_rank": 2, "physical_setting_id": "P2"},
            {"shortlist_rank": 3, "physical_setting_id": "P3"},
        ]
    }
    winner = select_first_stable_battery(shortlist, battery_summary)
    assert winner is not None
    assert winner["shortlist_rank"] == 2
    assert bool(
        battery_summary.loc[
            battery_summary["shortlist_rank"] == 1, "battery_pass"
        ].iloc[0]
    ) is False


def test_no_passing_battery_returns_none() -> None:
    rows = []
    for rank, setting in ((1, "P1"), (2, "P2")):
        for role in ("latency", "cost", "mixed"):
            rows.append(
                _summary_row(
                    rank,
                    setting,
                    rank,
                    role,
                    role != "mixed",
                )
            )
    summary = pd.DataFrame(rows)
    battery_summary = summarize_battery_passes(summary)
    shortlist = {
        "batteries": [
            {"shortlist_rank": 1, "physical_setting_id": "P1"},
            {"shortlist_rank": 2, "physical_setting_id": "P2"},
        ]
    }
    assert select_first_stable_battery(shortlist, battery_summary) is None


def run_all_tests() -> None:
    test_first_pre_ranked_passing_battery_is_selected()
    test_no_passing_battery_returns_none()
    print("PHASE1_N100_SHORTLIST_CALIBRATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
