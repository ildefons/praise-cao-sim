"""Unit tests for exact-event Phase-1 survival-area candidate metrics."""
from __future__ import annotations

import pandas as pd

from exact_auc_candidate_metrics import (
    build_threshold_event_cache_for_trajectory,
    calculate_exact_normalized_restricted_survival_area,
    combine_cached_event_times,
    deduplicate_exact_admissibility_regions,
)


def test_exact_area_matches_mean_capped_first_violation_time() -> None:
    """Verify the exact restricted-area identity on hand-checkable observations."""
    area_seconds, normalized = calculate_exact_normalized_restricted_survival_area(
        [60.0, 120.0, None, 240.0],
        horizon_min=0.0,
        horizon_max=240.0,
    )
    assert abs(area_seconds - 165.0) < 1e-12
    assert abs(normalized - 0.6875) < 1e-12


def test_cached_events_preserve_latency_and_cost_semantics() -> None:
    """Verify cached threshold events reproduce frozen first-event semantics."""
    ledger = pd.DataFrame(
        [
            {"request_id": 1, "emission": 0.0, "completion": 5.0, "C": 2.0, "Q": 0.5},
            {"request_id": 2, "emission": 10.0, "completion": 20.0, "C": 5.0, "Q": 0.5},
        ]
    )
    cache = build_threshold_event_cache_for_trajectory(
        ledger,
        latency_thresholds=[4.0, 20.0],
        cost_thresholds=[3.0, 10.0],
        quality_thresholds=[0.5],
        stop_time=30.0,
    )
    assert cache["latency"][4.0] == 4.0
    assert cache["latency"][20.0] is None
    assert cache["cost"][3.0] == 20.0
    assert cache["cost"][10.0] is None
    time, cause = combine_cached_event_times(
        cache["latency"][4.0], cache["cost"][3.0], cache["quality"][0.5]
    )
    assert time == 4.0
    assert cause == "latency"


def test_exact_A_deduplication_retains_provenance() -> None:
    """Verify identical thresholds are evaluated once despite multiple region IDs."""
    regions = pd.DataFrame(
        [
            {
                "physical_setting_id": "P",
                "region_id": "A1",
                "center_instruction_mean": 1.0,
                "dispersion": 0.1,
                "l_max": 2.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "ar_augmentation_type": "ORIGINAL",
            },
            {
                "physical_setting_id": "P",
                "region_id": "A2",
                "center_instruction_mean": 1.0,
                "dispersion": 0.1,
                "l_max": 2.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "ar_augmentation_type": "AUGMENTED",
            },
        ]
    )
    deduplicated = deduplicate_exact_admissibility_regions(regions)
    assert len(deduplicated) == 1
    assert deduplicated.iloc[0]["equivalent_region_count"] == 2
    assert deduplicated.iloc[0]["equivalent_region_ids"] == "A1;A2"


def run_all_exact_auc_candidate_metric_tests() -> None:
    """Execute all exact-event AUC metric tests."""
    test_exact_area_matches_mean_capped_first_violation_time()
    test_cached_events_preserve_latency_and_cost_semantics()
    test_exact_A_deduplication_retains_provenance()
    print("PHASE1_EXACT_AUC_CANDIDATE_METRICS_TESTS_PASS")


if __name__ == "__main__":
    run_all_exact_auc_candidate_metric_tests()
