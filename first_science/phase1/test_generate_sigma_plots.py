"""Simulator-independent tests for Phase-1 sigma-plot post-processing."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from generate_sigma_plots import (
    calculate_exact_empirical_sigma_staircase_for_region,
    choose_anchor_sigma_levels_bracketing_target,
    generate_sigma_plots_from_phase1_atlas_results,
    select_best_sigma_representative_regions_for_one_physical_setting,
)


def create_synthetic_plotting_fixture() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Create representative ARs, native ledgers, and configuration for tests.

    Called by:
        - selection and end-to-end tests in this module.
    """
    representatives = pd.DataFrame(
        [
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R090_L",
                "l_max": 1.5,
                "c_max": 10.0,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 1,
                "cost_first_count": 0,
            },
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R090_C",
                "l_max": 10.0,
                "c_max": 2.0,
                "q_min": 0.5,
                "sigma_anchor": 0.9,
                "latency_first_count": 0,
                "cost_first_count": 1,
            },
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R100",
                "l_max": 10.0,
                "c_max": 10.0,
                "q_min": 0.5,
                "sigma_anchor": 1.0,
                "latency_first_count": 0,
                "cost_first_count": 0,
            },
        ]
    )
    ledgers = pd.DataFrame(
        [
            {
                "physical_setting_id": "DTEST_d0.000",
                "trajectory": 0,
                "request_id": 0,
                "emission": 0.0,
                "completion": 1.0,
                "L": 1.0,
                "C": 1.0,
                "Q": 0.5,
            },
            {
                "physical_setting_id": "DTEST_d0.000",
                "trajectory": 1,
                "request_id": 0,
                "emission": 0.0,
                "completion": 2.0,
                "L": 2.0,
                "C": 3.0,
                "Q": 0.5,
            },
        ]
    )
    effective_configuration = {
        "admissibility_scan": {"anchor_horizon": 1.0},
        "horizon": {"simulation_stop_time": 3.0},
    }
    return representatives, ledgers, effective_configuration


def test_choose_anchor_sigma_levels_bracketing_target() -> None:
    """Verify N=10-style 0.9/1.0 values bracket target 0.95.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    selected = choose_anchor_sigma_levels_bracketing_target(
        pd.Series([0.0, 0.8, 0.9, 1.0]), 0.95
    )
    assert selected == [0.9, 1.0]


def test_select_best_sigma_representatives_preserves_same_sigma_regions() -> None:
    """Verify distinct ARs at one selected sigma are all retained.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    representatives, _, _ = create_synthetic_plotting_fixture()
    selected = select_best_sigma_representative_regions_for_one_physical_setting(
        representatives, target_anchor_sigma=0.95
    )
    assert set(selected["region_id"]) == {"R090_L", "R090_C", "R100"}


def test_exact_empirical_staircase_uses_actual_event_times() -> None:
    """Verify the plotted sigma drops at exact first-violation event times.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    representatives, ledgers, _ = create_synthetic_plotting_fixture()
    region = representatives[representatives["region_id"] == "R090_L"].iloc[0]
    curve = calculate_exact_empirical_sigma_staircase_for_region(
        physical_setting_request_ledger=ledgers,
        representative_region=region,
        stop_time=3.0,
    )
    assert curve["horizon"].tolist() == [0.0, 1.5, 3.0]
    assert curve["sigma"].tolist() == [1.0, 0.5, 0.5]


def test_generate_sigma_plots_creates_png_and_selection_table() -> None:
    """Verify end-to-end exact staircase plotting creates PNG and audit CSV.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    representatives, ledgers, effective_configuration = create_synthetic_plotting_fixture()
    with tempfile.TemporaryDirectory() as temporary_directory:
        results_directory = Path(temporary_directory)
        representatives.to_csv(
            results_directory / "representative_regions_by_sigma.csv", index=False
        )
        ledgers.to_csv(
            results_directory / "all_top_level_request_ledgers.csv", index=False
        )
        (results_directory / "effective_config.json").write_text(
            json.dumps(effective_configuration), encoding="utf-8"
        )
        selection = generate_sigma_plots_from_phase1_atlas_results(
            results_directory, target_anchor_sigma=0.95
        )
        output_directory = results_directory / "sigma_plots"
        assert (output_directory / "best_sigma_curves_DTEST_d0.000.png").is_file()
        assert (output_directory / "best_sigma_plot_selection.csv").is_file()
        assert len(selection) == 3


def run_all_sigma_plot_tests() -> None:
    """Execute all simulator-independent sigma-plot tests.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    test_choose_anchor_sigma_levels_bracketing_target()
    test_select_best_sigma_representatives_preserves_same_sigma_regions()
    test_exact_empirical_staircase_uses_actual_event_times()
    test_generate_sigma_plots_creates_png_and_selection_table()
    print("PHASE1_SIGMA_PLOT_TESTS_PASS")


if __name__ == "__main__":
    run_all_sigma_plot_tests()
