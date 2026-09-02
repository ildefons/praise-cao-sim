"""Simulator-independent tests for all-distinct-AR N=10 to existing-N=100 exploration."""
from __future__ import annotations

import pandas as pd

from explore_all_distinct_ar_to_existing_n100 import deduplicate_exact_admissibility_regions


def test_exact_A_deduplication_ignores_region_id_provenance() -> None:
    """Verify duplicate region IDs with identical A collapse to one exact AR."""
    table = pd.DataFrame(
        [
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "A",
                "l_max": 10.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 2,
                "cost_first_count": 1,
                "ar_augmentation_type": "ORIGINAL",
            },
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "B",
                "l_max": 10.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 2,
                "cost_first_count": 1,
                "ar_augmentation_type": "AUGMENTED",
            },
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "C",
                "l_max": 11.0,
                "c_max": 3.0,
                "q_min": 0.5,
                "sigma_anchor": 1.0,
                "latency_first_count": 0,
                "cost_first_count": 0,
                "ar_augmentation_type": "ORIGINAL",
            },
        ]
    )
    deduped = deduplicate_exact_admissibility_regions(table, "D390000000_d0.150")
    assert len(deduped) == 2
    first = deduped[(deduped["l_max"] == 10.0) & (deduped["c_max"] == 3.0)].iloc[0]
    assert int(first["equivalent_region_count"]) == 2
    assert set(str(first["equivalent_region_ids"]).split(";")) == {"A", "B"}


def run_all_tests() -> None:
    """Run all simulator-independent tests in this module."""
    test_exact_A_deduplication_ignores_region_id_provenance()
    print("PHASE1_ALL_DISTINCT_AR_TRANSFER_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
