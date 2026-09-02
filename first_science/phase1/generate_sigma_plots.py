"""Generate auditable sigma plots from Phase-1 development-atlas outputs.

This module is post-processing only. It never invokes AICon/YAFS and never
changes the white-box trajectories or admissibility-region calculations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def load_phase1_atlas_tables_for_sigma_plotting(
    results_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load representative ARs, survival curves, and effective configuration.

    Args:
        results_directory: Directory containing Phase-1 atlas outputs.

    Returns:
        Tuple containing representative regions, survival curves, and effective
        configuration.

    Called by:
        - ``generate_sigma_plots_from_phase1_atlas_results`` in this module.
    """
    representative_path = results_directory / "representative_regions_by_sigma.csv"
    survival_path = results_directory / "survival_curves.csv"
    configuration_path = results_directory / "effective_config.json"

    for required_path in (representative_path, survival_path, configuration_path):
        if not required_path.exists():
            raise FileNotFoundError(f"required atlas output not found: {required_path}")

    representatives = pd.read_csv(representative_path)
    survival_curves = pd.read_csv(survival_path)
    effective_configuration = json.loads(
        configuration_path.read_text(encoding="utf-8")
    )
    return representatives, survival_curves, effective_configuration


def choose_anchor_sigma_levels_bracketing_target(
    achievable_anchor_sigmas: pd.Series,
    target_anchor_sigma: float,
) -> list[float]:
    """Choose closest achievable sigma at/below and at/above the target.

    When the target itself is achievable only that level is selected. If all
    available values lie on one side of the target, the closest available value
    is selected.

    Args:
        achievable_anchor_sigmas: Achievable empirical sigma values at H*.
        target_anchor_sigma: Desired anchor survival, normally 0.95.

    Returns:
        Sorted list containing one or two selected sigma levels.

    Called by:
        - ``select_best_sigma_representative_regions_for_one_physical_setting``
          in this module.
        - ``test_choose_anchor_sigma_levels_bracketing_target`` in
          ``test_generate_sigma_plots.py``.
    """
    values = sorted({float(value) for value in achievable_anchor_sigmas})
    if not values:
        raise ValueError("no achievable anchor sigma values were provided")

    target = float(target_anchor_sigma)
    below = [value for value in values if value <= target]
    above = [value for value in values if value >= target]

    selected: list[float] = []
    if below:
        selected.append(max(below))
    if above:
        selected.append(min(above))
    if not selected:
        selected.append(min(values, key=lambda value: abs(value - target)))
    return sorted(set(selected))


def select_best_sigma_representative_regions_for_one_physical_setting(
    representative_regions_for_one_physical_setting: pd.DataFrame,
    target_anchor_sigma: float,
) -> pd.DataFrame:
    """Select representative ARs at sigma levels closest to the target.

    All representative ARs already retained by the atlas for the closest
    achievable sigma level below/at the target and above/at the target are kept.
    This preserves latency-first, cost-first, and mixed representatives rather
    than silently choosing one AR among scientifically different regions.

    Args:
        representative_regions_for_one_physical_setting: Representative-region
            table filtered to one physical setting.
        target_anchor_sigma: Desired anchor survival, normally 0.95.

    Returns:
        Selected representative-region rows.

    Called by:
        - ``write_sigma_plots_for_all_physical_settings`` in this module.
        - ``test_select_best_sigma_representatives_preserves_same_sigma_regions``
          in ``test_generate_sigma_plots.py``.
    """
    if representative_regions_for_one_physical_setting.empty:
        raise ValueError("representative-region table is empty")

    selected_sigma_levels = choose_anchor_sigma_levels_bracketing_target(
        representative_regions_for_one_physical_setting["sigma_anchor"],
        target_anchor_sigma,
    )
    selected = representative_regions_for_one_physical_setting[
        representative_regions_for_one_physical_setting["sigma_anchor"].astype(float).isin(
            selected_sigma_levels
        )
    ].copy()
    return selected.sort_values(
        ["sigma_anchor", "latency_first_count", "cost_first_count", "region_id"]
    ).reset_index(drop=True)


def format_sigma_curve_legend_label(representative_region: pd.Series) -> str:
    """Format one representative AR as a concise plot legend entry.

    Args:
        representative_region: One representative-region row.

    Returns:
        Legend label containing sigma, L/C thresholds, and first-failure counts.

    Called by:
        - ``write_best_sigma_plot_for_one_physical_setting`` in this module.
    """
    return (
        f"sigma@H*={float(representative_region['sigma_anchor']):.2f} | "
        f"l={float(representative_region['l_max']):.4g} | "
        f"c={float(representative_region['c_max']):.4g} | "
        f"Lfirst={int(representative_region['latency_first_count'])} | "
        f"Cfirst={int(representative_region['cost_first_count'])}"
    )


def write_best_sigma_plot_for_one_physical_setting(
    selected_representative_regions: pd.DataFrame,
    survival_curves_for_one_physical_setting: pd.DataFrame,
    physical_setting_id: str,
    anchor_horizon: float,
    target_anchor_sigma: float,
    output_png_path: Path,
) -> None:
    """Write one PNG with the sigma curves closest to the target for one setting.

    Args:
        selected_representative_regions: AR representatives at the closest
            achievable sigma level(s) around the target.
        survival_curves_for_one_physical_setting: Survival curves for the same
            physical setting.
        physical_setting_id: Stable atlas physical-setting identifier.
        anchor_horizon: H* used by the atlas.
        target_anchor_sigma: Desired target survival.
        output_png_path: Destination PNG path.

    Side effects:
        Writes one PNG file.

    Called by:
        - ``write_sigma_plots_for_all_physical_settings`` in this module.
    """
    figure = plt.figure(figsize=(10, 6))
    axis = figure.add_subplot(111)

    for _, representative_region in selected_representative_regions.iterrows():
        region_id = str(representative_region["region_id"])
        curve = survival_curves_for_one_physical_setting[
            survival_curves_for_one_physical_setting["region_id"].astype(str) == region_id
        ].sort_values("horizon")
        if curve.empty:
            raise ValueError(
                f"missing survival curve for region {region_id} "
                f"in physical setting {physical_setting_id}"
            )
        axis.plot(
            curve["horizon"],
            curve["sigma"],
            marker="o",
            markersize=3,
            label=format_sigma_curve_legend_label(representative_region),
        )

    axis.axvline(float(anchor_horizon), linestyle="--", label=f"H*={anchor_horizon:g}")
    axis.axhline(
        float(target_anchor_sigma),
        linestyle=":",
        label=f"target sigma={target_anchor_sigma:.2f}",
    )
    axis.set_xlim(left=0.0)
    axis.set_ylim(-0.02, 1.02)
    axis.set_xlabel("Horizon H")
    axis.set_ylabel("sigma(H) = P(T_violation > H)")
    axis.set_title(f"Best Phase-1 sigma curves near target — {physical_setting_id}")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_png_path, dpi=160)
    plt.close(figure)


def write_sigma_plots_for_all_physical_settings(
    representative_regions_by_sigma: pd.DataFrame,
    survival_curves: pd.DataFrame,
    anchor_horizon: float,
    target_anchor_sigma: float,
    output_directory: Path,
) -> pd.DataFrame:
    """Write one best-sigma PNG per physical setting plus an audit selection CSV.

    Args:
        representative_regions_by_sigma: Atlas representative-region table.
        survival_curves: Atlas full survival-curve table.
        anchor_horizon: H* used by the atlas.
        target_anchor_sigma: Desired target survival.
        output_directory: Directory where PNGs and selection CSV are written.

    Returns:
        DataFrame containing exactly the representative ARs plotted.

    Side effects:
        Writes PNGs and ``best_sigma_plot_selection.csv``.

    Called by:
        - ``generate_sigma_plots_from_phase1_atlas_results`` in this module.
        - ``test_write_sigma_plots_creates_png_and_selection_table`` in
          ``test_generate_sigma_plots.py``.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    selected_groups: list[pd.DataFrame] = []

    for physical_setting_id, representative_group in representative_regions_by_sigma.groupby(
        "physical_setting_id", sort=True
    ):
        selected = select_best_sigma_representative_regions_for_one_physical_setting(
            representative_group,
            target_anchor_sigma,
        )
        selected_groups.append(selected)

        survival_group = survival_curves[
            survival_curves["physical_setting_id"] == physical_setting_id
        ].copy()
        if survival_group.empty:
            raise ValueError(
                f"no survival curves found for physical setting {physical_setting_id}"
            )

        output_png_path = (
            output_directory / f"best_sigma_curves_{physical_setting_id}.png"
        )
        write_best_sigma_plot_for_one_physical_setting(
            selected_representative_regions=selected,
            survival_curves_for_one_physical_setting=survival_group,
            physical_setting_id=str(physical_setting_id),
            anchor_horizon=anchor_horizon,
            target_anchor_sigma=target_anchor_sigma,
            output_png_path=output_png_path,
        )

    selection_table = pd.concat(selected_groups, ignore_index=True)
    selection_table.to_csv(
        output_directory / "best_sigma_plot_selection.csv",
        index=False,
    )
    return selection_table


def generate_sigma_plots_from_phase1_atlas_results(
    results_directory: Path,
    target_anchor_sigma: float,
) -> pd.DataFrame:
    """Generate post-process sigma plots from an existing Phase-1 atlas run.

    Args:
        results_directory: Existing development-atlas results directory.
        target_anchor_sigma: Desired anchor survival, normally 0.95.

    Returns:
        DataFrame listing every representative AR plotted.

    Side effects:
        Creates ``results_directory/sigma_plots`` and writes PNG/CSV outputs.

    Called by:
        - ``main`` in this module.
    """
    representatives, survival_curves, effective_configuration = (
        load_phase1_atlas_tables_for_sigma_plotting(results_directory)
    )
    anchor_horizon = float(
        effective_configuration["admissibility_scan"]["anchor_horizon"]
    )
    return write_sigma_plots_for_all_physical_settings(
        representative_regions_by_sigma=representatives,
        survival_curves=survival_curves,
        anchor_horizon=anchor_horizon,
        target_anchor_sigma=float(target_anchor_sigma),
        output_directory=results_directory / "sigma_plots",
    )


def parse_sigma_plot_command_line_arguments() -> argparse.Namespace:
    """Parse command-line arguments for Phase-1 sigma plotting.

    Returns:
        Parsed command-line namespace.

    Called by:
        - ``main`` in this module.
    """
    parser = argparse.ArgumentParser(
        description="Generate best-sigma PNGs from existing Phase-1 atlas outputs."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/development_atlas"),
        help="Existing Phase-1 development-atlas result directory.",
    )
    parser.add_argument(
        "--target-sigma",
        type=float,
        default=0.95,
        help="Target sigma at H* used to choose the closest achievable curves.",
    )
    return parser.parse_args()


def main() -> None:
    """Generate sigma plots and print an auditable completion marker.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    arguments = parse_sigma_plot_command_line_arguments()
    selection_table = generate_sigma_plots_from_phase1_atlas_results(
        results_directory=arguments.results_dir,
        target_anchor_sigma=arguments.target_sigma,
    )
    number_of_physical_settings = int(selection_table["physical_setting_id"].nunique())
    print(
        "PHASE1_SIGMA_PLOTS_PASS",
        f"n_physical_settings={number_of_physical_settings}",
        f"n_plotted_regions={len(selection_table)}",
        f"output_directory={arguments.results_dir / 'sigma_plots'}",
    )


if __name__ == "__main__":
    main()
