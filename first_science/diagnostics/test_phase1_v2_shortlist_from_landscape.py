"""Tests for the proposed Phase-1 v2 shortlist gate diagnostic."""
from __future__ import annotations

import pandas as pd

from phase1_v2_shortlist_from_landscape import (
    build_role_summary,
    extract_v2_shortlist,
    top_candidates,
)


def run_all_tests() -> None:
    landscape = pd.DataFrame(
        [
            {
                "region_id": "lat_a",
                "descriptive_role": "latency",
                "l_max": 0.5,
                "c_max": 2.0,
                "q_min": 0.5,
                "area_rho_0p95": 0.99,
                "area_rho_0p975": 0.90,
                "area_rho_0p99": 0.80,
            },
            {
                "region_id": "lat_b",
                "descriptive_role": "latency",
                "l_max": 0.6,
                "c_max": 2.0,
                "q_min": 0.5,
                "area_rho_0p95": 0.97,
                "area_rho_0p975": 0.92,
                "area_rho_0p99": 0.90,
            },
            {
                "region_id": "cost_a",
                "descriptive_role": "cost",
                "l_max": 0.8,
                "c_max": 2.1,
                "q_min": 0.5,
                "area_rho_0p95": 0.998,
                "area_rho_0p975": 0.986,
                "area_rho_0p99": 0.94,
            },
            {
                "region_id": "mixed_a",
                "descriptive_role": "mixed",
                "l_max": 0.7,
                "c_max": 2.0,
                "q_min": 0.5,
                "area_rho_0p95": 0.995,
                "area_rho_0p975": 0.97,
                "area_rho_0p99": 0.91,
            },
            {
                "region_id": "too_low_nominal",
                "descriptive_role": "latency",
                "l_max": 0.4,
                "c_max": 2.0,
                "q_min": 0.5,
                "area_rho_0p95": 0.94,
                "area_rho_0p975": 0.80,
                "area_rho_0p99": 0.70,
            },
            {
                "region_id": "too_easy_stress",
                "descriptive_role": "mixed",
                "l_max": 0.9,
                "c_max": 2.2,
                "q_min": 0.5,
                "area_rho_0p95": 0.999,
                "area_rho_0p975": 0.995,
                "area_rho_0p99": 0.97,
            },
            {
                "region_id": "too_hard_stress",
                "descriptive_role": "cost",
                "l_max": 0.7,
                "c_max": 1.8,
                "q_min": 0.5,
                "area_rho_0p95": 0.96,
                "area_rho_0p975": 0.60,
                "area_rho_0p99": 0.49,
            },
        ]
    )

    shortlist = extract_v2_shortlist(landscape)
    assert set(shortlist["region_id"]) == {"lat_a", "lat_b", "cost_a", "mixed_a"}

    latency = shortlist[shortlist["descriptive_role"] == "latency"]
    assert latency.iloc[0]["region_id"] == "lat_a"
    assert int(latency.iloc[0]["role_rank"]) == 1
    assert latency.iloc[1]["region_id"] == "lat_b"
    assert int(latency.iloc[1]["role_rank"]) == 2

    summary = build_role_summary(shortlist)
    assert set(summary["descriptive_role"]) == {"latency", "cost", "mixed"}
    assert int(summary.loc[summary["descriptive_role"] == "latency", "n_passing"].iloc[0]) == 2

    top = top_candidates(shortlist, 1)
    assert len(top) == 3
    assert set(top["role_rank"].astype(int)) == {1}

    try:
        extract_v2_shortlist(landscape, stress_min=0.96, stress_max=0.95)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid stress interval must fail")

    print("PHASE1_V2_SHORTLIST_PROPOSED_GATE_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
