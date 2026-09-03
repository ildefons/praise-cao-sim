"""Run or validate the frozen Phase-1 N=10 physical discovery substrate.

The 25-point physical discovery grid remains valid after the sigma semantic
revision. Native AICon/YAFS trajectories do not need to be rerun solely because
finalist selection now uses SLA-compliance sigma. If this runner is invoked, it
reproduces the same physical ledgers and historical candidate-A atlas; current
finalist selection is performed later by ``sla_compliance_candidate_metrics.py``
and ``whitebox_candidate_selection.py``.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from presearch_contract import assert_phase1_discovery_configuration_is_frozen
from selection_policy import load_sla_compliance_area_selection_policy


def load_and_validate_scientific_discovery_configuration(
    configuration_path: Path,
) -> dict:
    """Load and validate the frozen physical grid plus SLA reranking policy.

    Args:
        configuration_path: Versioned Phase-1 scientific configuration.

    Returns:
        Parsed configuration after contract and grid checks.

    Side effects:
        None.

    Called by:
        - ``execute_scientific_discovery`` in this module.
        - ``test_scientific_discovery_configuration.py``.
    """
    configuration = json.loads(
        configuration_path.read_text(encoding="utf-8")
    )
    if (
        configuration.get("configuration_status")
        != "SCIENTIFIC_DISCOVERY_V1_FROZEN"
    ):
        raise ValueError(
            "scientific discovery runner requires SCIENTIFIC_DISCOVERY_V1_FROZEN"
        )
    assert_phase1_discovery_configuration_is_frozen(configuration)
    policy = load_sla_compliance_area_selection_policy(configuration)

    centers = list(
        map(
            float,
            configuration["physical_atlas"][
                "center_instruction_means"
            ],
        )
    )
    dispersions = list(
        map(float, configuration["physical_atlas"]["dispersions"])
    )
    expected_budget = len(centers) * len(dispersions)
    declared_budget = int(
        configuration["discovery_search"]["total_candidate_budget"]
    )
    if expected_budget != declared_budget:
        raise ValueError(
            f"targeted grid has {expected_budget} candidates but budget "
            f"declares {declared_budget}"
        )

    center_bounds = list(
        map(
            float,
            configuration["provider_parameterization"][
                "center_instruction_mean_bounds"
            ],
        )
    )
    dispersion_bounds = list(
        map(
            float,
            configuration["provider_parameterization"][
                "dispersion_bounds"
            ],
        )
    )
    if min(centers) < center_bounds[0] or max(centers) > center_bounds[1]:
        raise ValueError("candidate centers exceed frozen bounds")
    if (
        min(dispersions) < dispersion_bounds[0]
        or max(dispersions) > dispersion_bounds[1]
    ):
        raise ValueError("candidate dispersions exceed frozen bounds")

    development_seeds = set(
        map(int, configuration["development_smoke"]["seed_bank"])
    )
    discovery_seeds = set(
        map(
            int,
            configuration["discovery_search"][
                "calibration_seed_bank"
            ],
        )
    )
    if development_seeds.intersection(discovery_seeds):
        raise ValueError(
            "scientific discovery seeds must be fresh from development seeds"
        )
    if abs(policy.sla_definition.rho - 0.95) > 1e-12:
        raise ValueError("SLA reranking search rho must be 0.95")
    return configuration


def build_native_runtime_configuration(
    scientific_configuration: dict,
) -> dict:
    """Adapt scientific seed/budget fields to validated atlas machinery.

    The atlas runner predates the discovery/confirmation split and reads its
    trajectory bank from compatibility keys. This adapter changes only those
    internal keys; it does not change physical or SLA semantics.

    Called by:
        - ``execute_scientific_discovery`` in this module.
        - ``test_scientific_discovery_configuration.py``.
    """
    runtime = deepcopy(scientific_configuration)
    runtime["development_seeds"] = list(
        map(
            int,
            scientific_configuration["discovery_search"][
                "calibration_seed_bank"
            ],
        )
    )
    runtime["development_trajectory_count"] = int(
        scientific_configuration["discovery_search"][
            "n_trajectories_per_candidate"
        ]
    )
    return runtime


def execute_scientific_discovery(
    configuration_path: Path,
    output_directory: Path,
    clean: bool,
    maximum_physical_settings: int | None,
    maximum_trajectories_per_setting: int | None,
) -> None:
    """Reproduce the frozen N=10 physical substrate when explicitly requested.

    Current workflows should normally reuse the existing
    ``scientific_discovery_v1_full_domain_ar`` result directory and rerank it
    offline under SLA semantics instead of rerunning native simulation.

    Side effects:
        May run AICon/YAFS and write native physical ledgers plus historical
        candidate-A atlas outputs.

    Called by:
        - ``main`` in this module.
    """
    from whitebox_atlas import (
        execute_development_whitebox_atlas_simulations,
        scan_all_physical_settings_and_write_atlas_outputs,
    )

    scientific_configuration = (
        load_and_validate_scientific_discovery_configuration(
            configuration_path
        )
    )
    runtime_configuration = build_native_runtime_configuration(
        scientific_configuration
    )

    if clean and output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_config.json").write_text(
        json.dumps(scientific_configuration, indent=2),
        encoding="utf-8",
    )

    ledgers = execute_development_whitebox_atlas_simulations(
        runtime_configuration,
        output_directory,
        maximum_physical_settings=maximum_physical_settings,
        maximum_trajectories_per_setting=maximum_trajectories_per_setting,
    )
    scan_all_physical_settings_and_write_atlas_outputs(
        ledgers, runtime_configuration, output_directory
    )

    n_settings = int(ledgers["physical_setting_id"].nunique())
    n_trajectories = int(
        ledgers[
            ["physical_setting_id", "trajectory"]
        ].drop_duplicates().shape[0]
    )
    print(
        "PHASE1_SCIENTIFIC_DISCOVERY_RUN_PASS",
        f"n_physical_settings={n_settings}",
        f"n_setting_trajectories={n_trajectories}",
        "finalist_sigma_semantics=SLA_COMPLIANCE_RHO_0.95",
        "next=python sla_native_candidate_metrics.py",
        f"output_directory={output_directory}",
    )


def main() -> None:
    """Command-line entry point for optional physical-substrate reproduction."""
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
        default=module_directory
        / "results"
        / "scientific_discovery_v1",
    )
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--max-physical-settings", type=int, default=None
    )
    parser.add_argument(
        "--max-trajectories-per-setting", type=int, default=None
    )
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
