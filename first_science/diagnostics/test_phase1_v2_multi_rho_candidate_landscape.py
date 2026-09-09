"""Simulator-independent tests for the Phase-1 v2 candidate landscape."""
from __future__ import annotations

import pandas as pd

from phase1_v2_multi_rho_candidate_landscape import (
    deduplicate_exact_admissibility_regions,
    evaluate_candidate_landscape,
)


def _synthetic_ledgers() -> pd.DataFrame:
    """Two trajectories; trajectory 1 contains one latency failure."""
    rows: list[dict[str, object]] = []
    for trajectory in (0, 1):
        for request_id in range(25):
            emission = float(request_id)
            latency = 0.4
            if trajectory == 1 and request_id == 10:
                latency = 0.6
            rows.append(
                {
                    "trajectory": trajectory,
                    "physical_setting_id": "SYNTHETIC",
                    "request_id": request_id,
                    "emission": emission,
                    "completion": emission + latency,
                    "L": latency,
                    "C": 0.4,
                    "Q": 0.5,
                }
            )
    return pd.DataFrame(rows)


def run_all_tests() -> None:
    duplicated_regions = pd.DataFrame(
        [
            {
                "physical_setting_id": "SYNTHETIC",
                "region_id": "r0",
                "l_max": 0.5,
                "c_max": 1.0,
                "q_min": 0.5,
            },
            {
                "physical_setting_id": "SYNTHETIC",
                "region_id": "r0_duplicate",
                "l_max": 0.5,
                "c_max": 1.0,
                "q_min": 0.5,
            },
        ]
    )
    distinct = deduplicate_exact_admissibility_regions(
        duplicated_regions,
        "SYNTHETIC",
    )
    assert len(distinct) == 1
    assert int(distinct.iloc[0]["equivalent_region_count"]) == 2

    long_metrics, wide_summary = evaluate_candidate_landscape(
        distinct,
        _synthetic_ledgers(),
        rho_values=[0.95, 0.975, 0.99],
        report_horizons=[30.0],
        stop_time=30.0,
        dominance_ratio=2.0,
        expected_trajectories=2,
    )

    assert len(long_metrics) == 3
    assert len(wide_summary) == 1
    assert set(long_metrics["n_trajectories"].astype(int)) == {2}
    assert set(long_metrics["descriptive_role"].astype(str)) == {"latency"}

    ordered = long_metrics.sort_values("rho")
    areas = ordered["normalized_area"].astype(float).tolist()
    sigma_30 = ordered["sigma_30"].astype(float).tolist()
    assert all(
        areas[index] + 1e-12 >= areas[index + 1]
        for index in range(len(areas) - 1)
    )
    assert all(
        sigma_30[index] + 1e-12 >= sigma_30[index + 1]
        for index in range(len(sigma_30) - 1)
    )

    rho095 = ordered[ordered["rho"] == 0.95].iloc[0]
    rho0975 = ordered[ordered["rho"] == 0.975].iloc[0]
    assert abs(float(rho095["sigma_30"]) - 1.0) < 1e-12
    assert abs(float(rho0975["sigma_30"]) - 0.5) < 1e-12

    wide = wide_summary.iloc[0]
    assert "area_rho_0p95" in wide_summary.columns
    assert "area_rho_0p975" in wide_summary.columns
    assert "area_rho_0p99" in wide_summary.columns
    assert abs(float(wide["sigma_30_rho_0p95"]) - 1.0) < 1e-12
    assert abs(float(wide["sigma_30_rho_0p975"]) - 0.5) < 1e-12

    print("PHASE1_V2_MULTI_RHO_CANDIDATE_LANDSCAPE_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
