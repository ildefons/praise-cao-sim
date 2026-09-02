"""Run the frozen Phase-1 N=10 scientific white-box discovery grid.

This driver reuses the validated native AICon/YAFS Phase-1 execution machinery.
The physical discovery grid remains frozen; finalist selection is now governed
by the versioned survival-area policy and is performed offline after discovery.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from presearch_contract import assert_phase1_discovery_configuration_is_frozen
from selection_policy import load_survival_area_selection_policy


def load_and_validate_scientific_discovery_configuration(configuration_path: Path) -> dict:
    """Load and validate the frozen targeted-grid discovery configuration."""
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    if configuration.get("configuration_status") != "SCIENTIFIC_DISCOVERY_V1_FROZEN":
        raise ValueError("scientific discovery runner requires SCIENTIFIC_DISCOVERY_V1_FROZEN")

    assert_phase1_discovery_configuration_is_frozen(configuration)
    policy = load_survival_area_selection_policy(configuration)

    centers = list(map(float, configuration["physical_atlas"]["center_instruction_means"]))
    dispersions = list(map(float, configuration["physical_atlas"]["dispersions"]))
    expected_budget = len(centers) * len(dispersions)
    declared_budget = int(configuration["discovery_search"]["total_candidate_budget"])
    if expected_budget != declared_budget:
        raise ValueError(
            f"targeted grid has {expected_budget} candidates but budget declares {declared_budget}"
        )

    center_bounds = list(map(float, configuration["provider_parameterization"]["center_instruction_mean_bounds"]))
    dispersion_bounds = list(map(float, configuration["provider_parameterization"]["dispersion_bounds"]))
    if min(centers) < center_bounds[0] or max(centers) > center_bounds[1]:
        raise ValueError("candidate centers exceed frozen center_instruction_mean_bounds")
    if min(dispersions) < dispersion_bounds[0] or max(dispersions) > dispersion_bounds[1]:
        raise ValueError("candidate dispersions exceed frozen dispersion_bounds")

    development_seeds = set(map(int, configuration["development_smoke"]["seed_bank"]))
    discovery_seeds = set(map(int, configuration["discovery_search"]["calibration_seed_bank"]))
    if development_seeds.intersection(discovery_seeds):
        raise ValueError("scientific discovery seeds must be fresh from development-atlas seeds")

    horizon = configuration["horizon"]
    if abs(policy.horizon_min - float(horizon["minimum"])) > 1e-12:
        raise ValueError("AUC horizon_min must match frozen Phase-1 horizon minimum")
    if abs(policy.horizon_max - float(horizon["maximum"])) > 1e-12:
        raise ValueError("AUC horizon_max must match frozen Phase-1 horizon maximum")
    return configuration


def build_native_runtime_configuration(scientific_configuration: dict) -> dict:
    """Adapt frozen scientific discovery fields to validated atlas machinery."""
    runtime = deepcopy(scientific_configuration)
    runtime["development_seeds"] = list(
        map(int, scientific_configuration["discovery_search"]["calibration_seed_bank"])
    )
    runtime["development_trajectory_count"] = int(
        scientific_configuration["discovery_search"]["n_trajectories_per_candidate"]
    )
    return runtime


def execute_scientific_discovery(
    configuration_path: Path,
    output_directory: Path,
    clean: bool,
    maximum_physical_settings: int | None,
    maximum_trajectories_per_setting: int | None,
) -> None:
    """Execute the frozen targeted N=10 grid and offline AR scan."""
    from whitebox_atlas import (
        execute_development_whitebox_atlas_simulations,
        scan_all_physical_settings_and_write_atlas_outputs,
    )

    scientific_configuration = load_and_validate_scientific_discovery_configuration(
        configuration_path
    )
    runtime_configuration = build_native_runtime_configuration(scientific_configuration)

    if clean and output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_config.json").write_text(
        json.dumps(scientific_configuration, indent=2), encoding="utf-8"
    )

    ledgers = execute_development_whitebox_atlas_simulations(
        runtime_configuration,
        output_directory,
        maximum_physical_settings=maximum_physical_settings,
        maximum_trajectories_per_setting=maximum_trajectories_per_setting,
    )
    scan_all_physical_settings_and_write_atlas_outputs(
        ledgers,
        runtime_configuration,
        output_directory,
    )

    n_settings = int(ledgers["physical_setting_id"].nunique())
    n_trajectories = int(
        ledgers[["physical_setting_id", "trajectory"]].drop_duplicates().shape[0]
    )
    print(
        "PHASE1_SCIENTIFIC_DISCOVERY_RUN_PASS",
        f"n_physical_settings={n_settings}",
        f"n_setting_trajectories={n_trajectories}",
        f"output_directory={output_directory}",
    )


def main() -> None:
    """Command-line entry point for the frozen Phase-1 scientific discovery grid."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1",
    )
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--max-physical-settings", type=int, default=None)
    parser.add_argument("--max-trajectories-per-setting", type=int, default=None)
    args = parser.parse_args()

    execute_scientific_discovery(
        configuration_path=args.config.resolve(),
        output_directory=args.output.resolve(),
        clean=bool(args.clean),
        maximum_physical_settings=args.max_physical_settings,
        maximum_trajectories_per_setting=args.max_trajectories_per_setting,
    )


if __name__ == "__main__":
    main()
