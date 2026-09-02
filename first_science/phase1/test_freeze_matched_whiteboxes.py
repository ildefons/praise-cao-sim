"""Simulator-independent regression test for exact matched-whitebox freezing."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from freeze_matched_whiteboxes import freeze_exact_matched_whiteboxes


def test_freeze_uses_full_ar_table_not_compact_representatives() -> None:
    """Freeze a valid source AR even when it is absent from representatives.

    Called by:
        - ``run_all_freeze_matched_whitebox_tests`` in this module.
    """
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        results = root / "results"
        results.mkdir()

        rows = [
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "A_LATENCY",
                "center_instruction_mean": 390000000.0,
                "dispersion": 0.15,
                "l_max": 15.0,
                "c_max": 3.2,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 10,
                "cost_first_count": 0,
            },
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "A_MIXED_NONREPRESENTATIVE",
                "center_instruction_mean": 390000000.0,
                "dispersion": 0.15,
                "l_max": 18.0,
                "c_max": 2.9,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 6,
                "cost_first_count": 4,
            },
            {
                "physical_setting_id": "D390000000_d0.150",
                "region_id": "A_COST",
                "center_instruction_mean": 390000000.0,
                "dispersion": 0.15,
                "l_max": 33.0,
                "c_max": 2.9,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 0,
                "cost_first_count": 6,
            },
        ]
        pd.DataFrame(rows).to_csv(results / "admissibility_regions.csv", index=False)
        # Deliberately omit the mixed row from the compact representative subset.
        pd.DataFrame([rows[0], rows[2]]).to_csv(
            results / "representative_regions_by_sigma.csv", index=False
        )

        source_specification = {
            "physical_regime": {
                "physical_setting_id": "D390000000_d0.150",
                "center_instruction_mean": 390000000.0,
                "dispersion": 0.15,
            },
            "cases": [
                {
                    "case_id": "WB_L",
                    "selection_role": "latency",
                    "source_region_id": "A_LATENCY",
                },
                {
                    "case_id": "WB_LC",
                    "selection_role": "mixed",
                    "source_region_id": "A_MIXED_NONREPRESENTATIVE",
                },
                {
                    "case_id": "WB_C",
                    "selection_role": "cost",
                    "source_region_id": "A_COST",
                },
            ],
        }
        source_path = root / "matched_whitebox_sources.json"
        source_path.write_text(json.dumps(source_specification), encoding="utf-8")
        output_path = root / "selected_whiteboxes.json"

        manifest = freeze_exact_matched_whiteboxes(results, source_path, output_path)
        frozen = {case["case_id"]: case for case in manifest["whiteboxes"]}
        assert manifest["status"] == "FROZEN_FOR_CONFIRMATION"
        assert frozen["WB_LC"]["source_region_id"] == "A_MIXED_NONREPRESENTATIVE"
        assert frozen["WB_LC"]["l_max"] == 18.0
        assert frozen["WB_LC"]["c_max"] == 2.9
        assert frozen["WB_LC"]["source_table"] == "admissibility_regions.csv"


def run_all_freeze_matched_whitebox_tests() -> None:
    """Execute exact-freeze regression tests."""
    test_freeze_uses_full_ar_table_not_compact_representatives()
    print("PHASE1_MATCHED_WHITEBOX_FREEZE_TESTS_PASS")


if __name__ == "__main__":
    run_all_freeze_matched_whitebox_tests()
