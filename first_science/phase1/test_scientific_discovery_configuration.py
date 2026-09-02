"""Simulator-independent tests for the frozen Phase-1 scientific discovery grid."""
from __future__ import annotations

from pathlib import Path

from whitebox_scientific_discovery import (
    build_native_runtime_configuration,
    load_and_validate_scientific_discovery_configuration,
)


def load_discovery_configuration() -> dict:
    """Load and validate the versioned scientific discovery configuration.

    Called by:
        - all tests in this module.
    """
    path = Path(__file__).with_name("config_phase1_discovery_v1.json")
    return load_and_validate_scientific_discovery_configuration(path)


def test_targeted_grid_has_frozen_25_candidates() -> None:
    """Verify the predeclared 5x5 provider grid and bounds."""
    configuration = load_discovery_configuration()
    centers = configuration["physical_atlas"]["center_instruction_means"]
    dispersions = configuration["physical_atlas"]["dispersions"]
    assert centers == [300000000.0, 330000000.0, 360000000.0, 390000000.0, 420000000.0]
    assert dispersions == [0.0, 0.05, 0.1, 0.15, 0.2]
    assert len(centers) * len(dispersions) == 25
    assert configuration["discovery_search"]["total_candidate_budget"] == 25


def test_discovery_uses_fresh_common_n10_seed_bank() -> None:
    """Verify scientific discovery seeds are common and fresh from development."""
    configuration = load_discovery_configuration()
    development = set(configuration["development_smoke"]["seed_bank"])
    discovery = set(configuration["discovery_search"]["calibration_seed_bank"])
    assert len(discovery) == 10
    assert development.isdisjoint(discovery)
    assert configuration["discovery_search"]["common_seed_bank_across_candidates"] is True


def test_runtime_adapter_preserves_scientific_seed_bank() -> None:
    """Verify the native compatibility adapter does not substitute other seeds."""
    configuration = load_discovery_configuration()
    runtime = build_native_runtime_configuration(configuration)
    assert runtime["development_seeds"] == configuration["discovery_search"]["calibration_seed_bank"]
    assert runtime["development_trajectory_count"] == 10
    assert runtime["physical_atlas"] == configuration["physical_atlas"]


def run_all_scientific_discovery_configuration_tests() -> None:
    """Execute all simulator-independent scientific-discovery config tests."""
    test_targeted_grid_has_frozen_25_candidates()
    test_discovery_uses_fresh_common_n10_seed_bank()
    test_runtime_adapter_preserves_scientific_seed_bank()
    print("PHASE1_SCIENTIFIC_DISCOVERY_CONFIGURATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_scientific_discovery_configuration_tests()
