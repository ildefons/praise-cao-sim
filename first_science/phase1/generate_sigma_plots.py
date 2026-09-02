"""Generate exact empirical sigma staircases from Phase-1 atlas outputs.

This module is post-processing only. It reconstructs each plotted admissibility
region's trajectory-level first-violation times from the native top-level ledger
and draws the exact finite-sample empirical survival function over the full
configured horizon. It never invokes AICon/YAFS and never smooths sigma.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from atlas_analysis import calculate_first_violation_observation_for_trajectory


def load_phase1_atlas_tables_for_sigma_plotting(
    results_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load representative ARs, native top-level ledgers, and configuration.

    Called by:
        - ``generate_sigma_plots_from_phase1_atlas_results`` in this module.
    """
    representative_path = results_directory / "representative_regions_by_sigma.csv"
    ledger_path = results_directory / "all_top_level_request_ledgers.csv"
    configuration_path = results_directory / "effective_config.json"
    for required_path in (representative_path, ledger_path, configuration_path):
        if not required_path.exists():
            raise FileNotFoundError(f"required atlas output not found: {required_path}")
    representatives = pd.read_csv(representative_path)
    ledgers = pd.read_csv(ledger_path)
    effective_configuration = json.loads(
        configuration_path.read_text(encoding="utf-8")
    )
    return representatives, ledgers, effective_configuration


def choose_anchor_sigma_levels_bracketing_target(
    achievable_anchor_sigmas: pd.Series,
    target_anchor_sigma: float,
) -> list[float]:
    """Choose closest achievable anchor sigma at/below and at/above target.

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
    return sorted(set(selected or [min(values, key=lambda value: abs(value - target))]))


def select_best_sigma_representative_regions_for_one_physical_setting(
    representative_regions_for_one_physical_setting: pd.DataFrame,
    target_anchor_sigma: float,
) -> pd.DataFrame:
    """Retain all representative ARs at sigma levels closest to the target.

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


def calculate_exact_empirical_sigma_staircase_for_region(
    physical_setting_request_ledger: pd.DataFrame,
    representative_region: pd.Series,
    stop_time: float,
) -> pd.DataFrame:
    """Reconstruct exact finite-sample sigma(H) from first-violation times.

    Sigma is evaluated at every distinct first-violation event time plus the two
    domain endpoints. With the frozen strict convention ``P(T_violation > H)``,
    the empirical curve drops vertically at each observed event time and is
    constant between events.

    Called by:
        - ``write_best_sigma_plot_for_one_physical_setting`` in this module.
        - ``test_exact_empirical_staircase_uses_actual_event_times`` in
          ``test_generate_sigma_plots.py``.
    """
    observations = []
    for _, trajectory_ledger in physical_setting_request_ledger.groupby(
        "trajectory", sort=True
    ):
        observations.append(
            calculate_first_violation_observation_for_trajectory(
                trajectory_request_ledger=trajectory_ledger,
                latency_threshold=float(representative_region["l_max"]),
                cost_threshold=float(representative_region["c_max"]),
                quality_threshold=float(representative_region["q_min"]),
                stop_time=float(stop_time),
            )
        )
    if not observations:
        raise ValueError("no trajectories available for exact sigma reconstruction")

    event_times = sorted(
        {
            float(observation.time)
            for observation in observations
            if observation.time is not None
            and 0.0 <= float(observation.time) <= float(stop_time)
        }
    )
    horizons = sorted({0.0, float(stop_time), *event_times})
    rows = []
    for horizon in horizons:
        survivors = sum(
            observation.time is None or float(observation.time) > horizon
            for observation in observations
        )
        rows.append(
            {
                "horizon": float(horizon),
                "sigma": survivors / len(observations),
            }
        )
    return pd.DataFrame(rows)


def format_sigma_curve_legend_label(representative_region: pd.Series) -> str:
    """Format one representative AR as a concise legend entry.

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
    physical_setting_request_ledger: pd.DataFrame,
    physical_setting_id: str,
    anchor_horizon: float,
    target_anchor_sigma: float,
    stop_time: float,
    output_png_path: Path,
) -> None:
    """Write exact empirical survival staircases for one physical setting.

    Side effects:
        Writes one PNG file.

    Called by:
        - ``write_sigma_plots_for_all_physical_settings`` in this module.
    """
    figure = plt.figure(figsize=(10, 6))
    axis = figure.add_subplot(111)
    for _, representative_region in selected_representative_regions.iterrows():
        exact_curve = calculate_exact_empirical_sigma_staircase_for_region(
            physical_setting_request_ledger=physical_setting_request_ledger,
            representative_region=representative_region,
            stop_time=stop_time,
        )
        axis.step(
            exact_curve["horizon"],
            exact_curve["sigma"],
            where="post",
            label=format_sigma_curve_legend_label(representative_region),
        )

    axis.axvline(float(anchor_horizon), linestyle="--", label=f"H*={anchor_horizon:g}")
    axis.axhline(
        float(target_anchor_sigma),
        linestyle=":",
        label=f"target sigma={target_anchor_sigma:.2f}",
    )
    axis.set_xlim(0.0, float(stop_time))
    axis.set_ylim(-0.02, 1.02)
    axis.set_xlabel("Horizon H")
    axis.set_ylabel("sigma(H) = P(T_violation > H)")
    axis.set_title(f"Exact empirical Phase-1 sigma staircases — {physical_setting_id}")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_png_path, dpi=160)
    plt.close(figure)


def write_sigma_plots_for_all_physical_settings(
    representative_regions_by_sigma: pd.DataFrame,
    all_top_level_request_ledgers: pd.DataFrame,
    anchor_horizon: float,
    target_anchor_sigma: float,
    stop_time: float,
    output_directory: Path,
) -> pd.DataFrame:
    """Write one exact best-sigma staircase PNG per physical setting.

    Side effects:
        Writes PNGs and ``best_sigma_plot_selection.csv``.

    Called by:
        - ``generate_sigma_plots_from_phase1_atlas_results`` in this module.
        - ``test_generate_sigma_plots_creates_png_and_selection_table`` in
          ``test_generate_sigma_plots.py``.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    selected_groups: list[pd.DataFrame] = []
    for physical_setting_id, representative_group in representative_regions_by_sigma.groupby(
        "physical_setting_id", sort=True
    ):
        selected = select_best_sigma_representative_regions_for_one_physical_setting(
            representative_group, target_anchor_sigma
        )
        selected_groups.append(selected)
        physical_ledger = all_top_level_request_ledgers[
            all_top_level_request_ledgers["physical_setting_id"] == physical_setting_id
        ].copy()
        if physical_ledger.empty:
            raise ValueError(f"no top-level ledger rows for {physical_setting_id}")
        write_best_sigma_plot_for_one_physical_setting(
            selected_representative_regions=selected,
            physical_setting_request_ledger=physical_ledger,
            physical_setting_id=str(physical_setting_id),
            anchor_horizon=anchor_horizon,
            target_anchor_sigma=target_anchor_sigma,
            stop_time=stop_time,
            output_png_path=output_directory / f"best_sigma_curves_{physical_setting_id}.png",
        )

    selection_table = pd.concat(selected_groups, ignore_index=True)
    selection_table.to_csv(output_directory / "best_sigma_plot_selection.csv", index=False)
    return selection_table


def generate_sigma_plots_from_phase1_atlas_results(
    results_directory: Path,
    target_anchor_sigma: float,
) -> pd.DataFrame:
    """Generate exact empirical sigma plots from an existing Phase-1 atlas run.

    Called by:
        - ``main`` in this module.
    """
    representatives, ledgers, effective_configuration = (
        load_phase1_atlas_tables_for_sigma_plotting(results_directory)
    )
    anchor_horizon = float(
        effective_configuration["admissibility_scan"]["anchor_horizon"]
    )
    stop_time = float(effective_configuration["horizon"]["simulation_stop_time"])
    return write_sigma_plots_for_all_physical_settings(
        representative_regions_by_sigma=representatives,
        all_top_level_request_ledgers=ledgers,
        anchor_horizon=anchor_horizon,
        target_anchor_sigma=float(target_anchor_sigma),
        stop_time=stop_time,
        output_directory=results_directory / "sigma_plots",
    )


def parse_sigma_plot_command_line_arguments() -> argparse.Namespace:
    """Parse command-line arguments for Phase-1 sigma plotting.

    Called by:
        - ``main`` in this module.
    """
    parser = argparse.ArgumentParser(
        description="Generate exact empirical sigma staircases from Phase-1 atlas outputs."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/development_atlas"),
    )
    parser.add_argument("--target-sigma", type=float, default=0.95)
    return parser.parse_args()


def main() -> None:
    """Generate exact sigma plots and print an auditable completion marker.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    arguments = parse_sigma_plot_command_line_arguments()
    selection_table = generate_sigma_plots_from_phase1_atlas_results(
        results_directory=arguments.results_dir,
        target_anchor_sigma=arguments.target_sigma,
    )
    print(
        "PHASE1_SIGMA_PLOTS_PASS",
        f"n_physical_settings={selection_table['physical_setting_id'].nunique()}",
        f"n_plotted_regions={len(selection_table)}",
        f"output_directory={arguments.results_dir / 'sigma_plots'}",
    )


if __name__ == "__main__":
    main()
