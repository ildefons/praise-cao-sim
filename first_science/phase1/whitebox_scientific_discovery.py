"""Run the frozen Phase-1 N=10 scientific white-box discovery grid.

This driver reuses the already validated native AICon/YAFS Phase-1 execution
machinery. It differs from the development atlas in governance: the configuration
is frozen and versioned, the N=10 discovery seeds are fresh from development,
and outputs are eligible only for white-box candidate/AR discovery. They are not
precision estimates and M0/M1 never enter the loop.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from presearch_contract import assert_phase1_discovery_configuration_is_frozen
from whitebox_candidate_selection import (
    MAX_MIXED_CAUSE_IMBALANCE,
    MIN_DOMINANT_CAUSE_COUNT,
    MIN_FAILED_BY_STOP,
    MIN_MIXED_CAUSE_COUNT,
    MIN_UNIQUE_FIRST_VIOLATION_TIMES,
)


def load_and_validate_scientific_discovery_configuration(configuration_path: Path) -> dict:
    """Load and validate the frozen targeted-grid discovery configuration.

    Args:
        configuration_path: Versioned scientific discovery JSON.

    Returns:
        Parsed configuration after contract and grid consistency checks.

    Called by:
        - ``execute_scientific_discovery`` in this module.
        - ``test_scientific_discovery_configuration.py``.
    """
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    if configuration.get("configuration_status") != "SCIENTIFIC_DISCOVERY_V1_FROZEN":
        raise ValueError("scientific discovery runner requires SCIENTIFIC_DISCOVERY_V1_FROZEN")

    assert_phase1_discovery_configuration_is_frozen(configuration)

    centers = list(map(float, configuration["physical_atlas"]["center_instruction_means"]))
    dispersions = list(map(float, configuration["physical_atlas"]["dispersions"]))
    expected_budget = len(centers) * len(dispersions)
    declared_budget = int(configuration["discovery_search"]["total_candidate_budget"])
    if expected_budget != declared_budget:
        raise ValueError(
            f"targeted grid has {expected_budget} candidates but budget declares {declared_budget}"
        )

    center_bounds = list(
        map(
            float,
            configuration["provider_parameterization"]["center_instruction_mean_bounds"],
        )
    )
    dispersion_bounds = list(
        map(float, configuration["provider_parameterization"]["dispersion_bounds"])
    )
    if min(centers) < center_bounds[0] or max(centers) > center_bounds[1]:
        raise ValueError("candidate centers exceed frozen center_instruction_mean_bounds")
    if min(dispersions) < dispersion_bounds[0] or max(dispersions) > dispersion_bounds[1]:
        raise ValueError("candidate dispersions exceed frozen dispersion_bounds")

    development_seeds = set(map(int, configuration["development_smoke"]["seed_bank"]))
    discovery_seeds = set(map(int, configuration["discovery_search"]["calibration_seed_bank"]))
    if development_seeds.intersection(discovery_seeds):
        raise ValueError("scientific discovery seeds must be fresh from development-atlas seeds")

    gate = configuration["selection_quality_gate"]
    expected_gate = {
        "min_failed_by_stop": MIN_FAILED_BY_STOP,
        "min_unique_first_violation_times": MIN_UNIQUE_FIRST_VIOLATION_TIMES,
        "min_dominant_cause_count": MIN_DOMINANT_CAUSE_COUNT,
        "min_mixed_cause_count_each": MIN_MIXED_CAUSE_COUNT,
        "max_mixed_cause_imbalance": MAX_MIXED_CAUSE_IMBALANCE,
    }
    if gate != expected_gate:
        raise ValueError(
            "selection_quality_gate in config does not match whitebox selector constants"
        )
    return configuration


def build_native_runtime_configuration(scientific_configuration: dict) -> dict:
    """Adapt frozen scientific discovery fields to validated atlas machinery.

    The native simulator functions predate the discovery/confirmation split and
    read their common seed bank from ``development_seeds``. This adapter supplies
    the scientific discovery seed bank under that internal compatibility key; it
    does not alter the scientific meaning or provenance of the run.

    Args:
        scientific_configuration: Validated discovery configuration.

    Returns:
        Deep-copied runtime configuration accepted by ``whitebox_atlas.py``.

    Called by:
        - ``execute_scientific_discovery`` in this module.
        - ``test_scientific_discovery_configuration.py``.
    """
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
    """Execute the frozen targeted N=10 grid and offline AR scan.

    Args:
        configuration_path: Frozen discovery-v1 JSON path.
        output_directory: Directory for native ledgers and AR outputs.
        clean: Remove an existing output directory before a full rerun.
        maximum_physical_settings: Optional engineering-only truncation.
        maximum_trajectories_per_setting: Optional engineering-only truncation.

    Side effects:
        Imports native AICon/YAFS execution machinery, runs simulations and
        writes Phase-1 discovery outputs.

    Called by:
        - ``main`` in this module.
    """
    # Defer native simulator imports so configuration tests remain genuinely
    # simulator-independent and can run without importing YAFS.
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
