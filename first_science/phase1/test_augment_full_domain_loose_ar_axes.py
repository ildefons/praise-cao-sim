"""Simulator-independent tests for full-domain loose-axis AR augmentation."""
from __future__ import annotations

import pandas as pd

from augment_full_domain_loose_ar_axes import (
    build_full_domain_loose_axis_regions_for_one_setting,
    calculate_full_domain_loose_thresholds,
)


def create_late_latency_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create trajectories where latency becomes larger after the anchor.

    Cost values vary across trajectories so a full-domain-loose latency axis can
    isolate cost-first failure structure.

    Called by:
        - all tests in this module.
    """
    rows = []
    for trajectory in range(4):
        rows.extend(
            [
                {
                    "physical_setting_id": "P",
                    "center_instruction_mean": 1.0,
                    "dispersion": 0.0,
                    "trajectory": trajectory,
                    "request_id": trajectory * 2,
                    "emission": 10.0,
                    "completion": 11.0,
                    "L": 1.0,
                    "C": 1.0 + trajectory,
                    "Q": 0.5,
                },
                {
                    "physical_setting_id": "P",
                    "center_instruction_mean": 1.0,
                    "dispersion": 0.0,
                    "trajectory": trajectory,
                    "request_id": trajectory * 2 + 1,
                    "emission": 150.0,
                    "completion": 170.0,
                    "L": 20.0,
                    "C": 2.0 + trajectory,
                    "Q": 0.5,
                },
            ]
        )
    regions = pd.DataFrame(
        [
            {
                "physical_setting_id": "P",
                "region_id": "P_A0",
                "center_instruction_mean": 1.0,
                "dispersion": 0.0,
                "l_max": 2.0,
                "c_max": 2.5,
                "q_min": 0.5,
                "sigma_anchor": 0.5,
                "n_trajectories": 4,
                "latency_first_count": 0,
                "cost_first_count": 2,
                "quality_first_count": 0,
                "tie_first_count": 0,
                "censored_count": 2,
            },
            {
                "physical_setting_id": "P",
                "region_id": "P_A1",
                "center_instruction_mean": 1.0,
                "dispersion": 0.0,
                "l_max": 3.0,
                "c_max": 4.5,
                "q_min": 0.5,
                "sigma_anchor": 1.0,
                "n_trajectories": 4,
                "latency_first_count": 0,
                "cost_first_count": 0,
                "quality_first_count": 0,
                "tie_first_count": 0,
                "censored_count": 4,
            },
        ]
    )
    return pd.DataFrame(rows), regions


def test_full_domain_loose_thresholds_exceed_late_requirements() -> None:
    """Verify loose axes remain nonbinding through the full horizon."""
    ledger, _ = create_late_latency_fixture()
    latency_loose, cost_loose = calculate_full_domain_loose_thresholds(
        ledger,
        stop_time=240.0,
        loose_multiplier=1.05,
        relative_epsilon=1e-9,
    )
    assert latency_loose > 20.0
    assert cost_loose > 5.0


def test_augmented_loose_latency_can_isolate_cost_failures() -> None:
    """Verify a cost-threshold family can remain latency-nonbinding to H=240."""
    ledger, regions = create_late_latency_fixture()
    summary, curves = build_full_domain_loose_axis_regions_for_one_setting(
        ledger,
        regions,
        physical_setting_id="P",
        center_instruction_mean=1.0,
        dispersion=0.0,
        quality_threshold=0.5,
        anchor_horizon=120.0,
        horizons=[0.0, 120.0, 180.0, 240.0],
        stop_time=240.0,
        loose_multiplier=1.05,
        relative_epsilon=1e-9,
    )
    cost_isolating = summary[
        summary["ar_augmentation_type"] == "FULL_DOMAIN_LOOSE_LATENCY"
    ]
    assert not cost_isolating.empty
    assert int(cost_isolating["latency_first_count"].max()) == 0
    assert int(cost_isolating["cost_first_count"].max()) >= 2
    assert not curves.empty


def run_all_full_domain_ar_augmentation_tests() -> None:
    """Execute all simulator-independent augmentation tests."""
    test_full_domain_loose_thresholds_exceed_late_requirements()
    test_augmented_loose_latency_can_isolate_cost_failures()
    print("PHASE1_FULL_DOMAIN_AR_AUGMENTATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_full_domain_ar_augmentation_tests()
