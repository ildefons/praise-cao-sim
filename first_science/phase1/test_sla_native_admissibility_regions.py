"""Simulator-independent tests for SLA-native Phase-1 AR generation."""
from __future__ import annotations

import pandas as pd

from generate_sla_native_admissibility_regions import (
    build_sla_native_regions_for_one_physical_setting,
    empirical_higher_quantiles,
    load_sla_native_ar_generator_policy,
)


def test_configuration() -> dict:
    """Return compact frozen SLA-native AR policy fixture."""
    return {
        "provider_family": {"x": 0.5},
        "horizon": {"simulation_stop_time": 240.0},
        "sla_compliance": {"search_rho": 0.95},
        "sla_admissibility_region_generator": {
            "status": "FROZEN_SLA_NATIVE_AR_GENERATOR_V1",
            "quantile_levels": [0.90, 0.925, 0.95, 0.975, 0.99],
            "quantile_interpolation": "higher",
            "pooling": "pooled_requests_within_physical_setting_across_N10",
            "quality_threshold_rule": "q_star=x",
            "loose_latency_rule": "simulation_stop_time_plus_epsilon",
            "loose_cost_rule": "max_finite_cost_times_multiplier_plus_epsilon",
            "loose_cost_multiplier": 1.05,
            "epsilon": 1e-9,
            "candidate_families": [
                "latency_quantile_x_cost_loose",
                "latency_loose_x_cost_quantile",
                "latency_quantile_x_cost_quantile",
            ],
            "m0_m1_allowed_in_generator": False,
            "midpoint_or_area_target_used_in_generator": False,
        },
    }


def synthetic_ledgers() -> pd.DataFrame:
    """Create deterministic pooled request outcomes with distinct quantiles."""
    rows = []
    request_id = 0
    for trajectory in range(10):
        for local_index in range(100):
            value = trajectory * 100 + local_index + 1
            rows.append(
                {
                    "physical_setting_id": "P",
                    "center_instruction_mean": 390.0,
                    "dispersion": 0.1,
                    "trajectory": trajectory,
                    "request_id": request_id,
                    "L": float(value) / 1000.0,
                    "C": float(value) / 100.0,
                    "Q": 0.5,
                }
            )
            request_id += 1
    return pd.DataFrame(rows)


def test_higher_quantiles_return_observed_thresholds() -> None:
    """Verify empirical quantiles use observed upper order statistics."""
    values = pd.Series([1.0, 2.0, 3.0, 4.0])
    thresholds = empirical_higher_quantiles(values, [0.5, 0.75])
    assert thresholds == [3.0, 4.0]


def test_generator_builds_axis_isolated_and_crossed_candidates() -> None:
    """Verify the frozen 5x5 SLA-native battery and loose-axis semantics."""
    configuration = test_configuration()
    load_sla_native_ar_generator_policy(configuration)
    regions = build_sla_native_regions_for_one_physical_setting(
        synthetic_ledgers(), "P", configuration
    )
    assert len(regions) == 35
    counts = regions["generator_family"].value_counts().to_dict()
    assert counts["latency_quantile_x_cost_loose"] == 5
    assert counts["latency_loose_x_cost_quantile"] == 5
    assert counts["latency_quantile_x_cost_quantile"] == 25
    assert set(regions["q_min"]) == {0.5}
    assert set(regions["search_rho"]) == {0.95}

    cost_only = regions[
        regions["generator_family"] == "latency_loose_x_cost_quantile"
    ]
    assert (cost_only["l_max"] > 240.0).all()

    latency_only = regions[
        regions["generator_family"] == "latency_quantile_x_cost_loose"
    ]
    assert (latency_only["c_max"] > synthetic_ledgers()["C"].max()).all()


def test_generator_does_not_reference_composition_methods() -> None:
    """Verify the AR generator remains technology-neutral."""
    policy = load_sla_native_ar_generator_policy(test_configuration())
    assert policy["m0_m1_allowed_in_generator"] is False


def run_all_sla_native_ar_tests() -> None:
    """Execute SLA-native AR generator unit tests."""
    test_higher_quantiles_return_observed_thresholds()
    test_generator_builds_axis_isolated_and_crossed_candidates()
    test_generator_does_not_reference_composition_methods()
    print("PHASE1_SLA_NATIVE_AR_GENERATOR_TESTS_PASS")


if __name__ == "__main__":
    run_all_sla_native_ar_tests()
