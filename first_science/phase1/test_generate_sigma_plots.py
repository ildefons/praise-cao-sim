"""Simulator-independent tests for Phase-1 sigma-plot post-processing."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from generate_sigma_plots import (
    choose_anchor_sigma_levels_bracketing_target,
    generate_sigma_plots_from_phase1_atlas_results,
    select_best_sigma_representative_regions_for_one_physical_setting,
)


def create_synthetic_plotting_fixture() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Create a minimal synthetic atlas fixture for plotting tests.

    Returns:
        Representative regions, survival curves, and effective configuration.

    Called by:
        - ``test_select_best_sigma_representatives_preserves_same_sigma_regions``
          in this module.
        - ``test_generate_sigma_plots_creates_png_and_selection_table`` in this
          module.
    """
    representatives = pd.DataFrame(
        [
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R090_L",
                "l_max": 1.0,
                "c_max": 2.0,
                "sigma_anchor": 0.9,
                "latency_first_count": 1,
                "cost_first_count": 0,
            },
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R090_C",
                "l_max": 1.1,
                "c_max": 1.9,
                "sigma_anchor": 0.9,
                "latency_first_count": 0,
                "cost_first_count": 1,
            },
            {
                "physical_setting_id": "DTEST_d0.000",
                "region_id": "R100",
                "l_max": 1.2,
                "c_max": 2.1,
                "sigma_anchor": 1.0,
                "latency_first_count": 0,
                "cost_first_count": 0,
            },
        ]
    )
    curve_rows = []
    for region_id, values in {
        "R090_L": [1.0, 0.9, 0.8],
        "R090_C": [1.0, 0.9, 0.7],
        "R100": [1.0, 1.0, 0.9],
    }.items():
        for horizon, sigma in zip([0.0, 120.0, 240.0], values):
            curve_rows.append(
                {
                    "physical_setting_id": "DTEST_d0.000",
                    "region_id": region_id,
                    "horizon": horizon,
                    "sigma": sigma,
                }
            )
    survival_curves = pd.DataFrame(curve_rows)
    effective_configuration = {"admissibility_scan": {"anchor_horizon": 120.0}}
    return representatives, survival_curves, effective_configuration


def test_choose_anchor_sigma_levels_bracketing_target() -> None:
    """Verify that N=10-style 0.9/1.0 values bracket target 0.95.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    selected = choose_anchor_sigma_levels_bracketing_target(
        pd.Series([0.0, 0.8, 0.9, 1.0]),
        0.95,
    )
    assert selected == [0.9, 1.0]


def test_select_best_sigma_representatives_preserves_same_sigma_regions() -> None:
    """Verify that distinct ARs at a selected sigma are all retained.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    representatives, _, _ = create_synthetic_plotting_fixture()
    selected = select_best_sigma_representative_regions_for_one_physical_setting(
        representatives,
        target_anchor_sigma=0.95,
    )
    assert set(selected["region_id"]) == {"R090_L", "R090_C", "R100"}


def test_generate_sigma_plots_creates_png_and_selection_table() -> None:
    """Verify end-to-end post-processing creates a PNG and audit CSV.

    Called by:
        - ``run_all_sigma_plot_tests`` in this module.
    """
    representatives, survival_curves, effective_configuration = (
        create_synthetic_plotting_fixture()
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        results_directory = Path(temporary_directory)
        representatives.to_csv(
            results_directory / "representative_regions_by_sigma.csv", index=False
        )
        survival_curves.to_csv(results_directory / "survival_curves.csv", index=False)
        (results_directory / "effective_config.json").write_text(
            json.dumps(effective_configuration), encoding="utf-8"
        )

        selection = generate_sigma_plots_from_phase1_atlas_results(
            results_directory,
            target_anchor_sigma=0.95,
        )
        output_directory = results_directory / "sigma_plots"
        assert (
            output_directory / "best_sigma_curves_DTEST_d0.000.png"
        ).is_file()
        assert (output_directory / "best_sigma_plot_selection.csv").is_file()
        assert len(selection) == 3


def run_all_sigma_plot_tests() -> None:
    """Execute all simulator-independent sigma-plot tests.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    test_choose_anchor_sigma_levels_bracketing_target()
    test_select_best_sigma_representatives_preserves_same_sigma_regions()
    test_generate_sigma_plots_creates_png_and_selection_table()
    print("PHASE1_SIGMA_PLOT_TESTS_PASS")


if __name__ == "__main__":
    run_all_sigma_plot_tests()
