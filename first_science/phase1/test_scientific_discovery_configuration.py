"""Simulator-independent tests for frozen Phase-1 physical discovery + SLA policy."""
from __future__ import annotations

from pathlib import Path

from whitebox_scientific_discovery import (
    build_native_runtime_configuration,
    load_and_validate_scientific_discovery_configuration,
)


def load_discovery_configuration() -> dict:
    """Load and validate versioned scientific discovery configuration."""
    return load_and_validate_scientific_discovery_configuration(
        Path(__file__).with_name("config_phase1_discovery_v1.json")
    )


def test_targeted_grid_has_frozen_25_candidates() -> None:
    cfg = load_discovery_configuration()
    centers = cfg["physical_atlas"]["center_instruction_means"]
    dispersions = cfg["physical_atlas"]["dispersions"]
    assert centers == [
        300000000.0,
        330000000.0,
        360000000.0,
        390000000.0,
        420000000.0,
    ]
    assert dispersions == [0.0, 0.05, 0.1, 0.15, 0.2]
    assert len(centers) * len(dispersions) == 25


def test_sla_search_semantics_are_rho095_cumulative_from_t0() -> None:
    cfg = load_discovery_configuration()
    sla = cfg["sla_compliance"]
    assert sla["search_rho"] == 0.95
    assert sla["accounting_origin"] == 0.0
    assert sla["accounting_window"] == "cumulative_[0,H]_from_t0"
    assert sla["rolling_windows_allowed"] is False


def test_runtime_adapter_preserves_discovery_seed_bank() -> None:
    cfg = load_discovery_configuration()
    runtime = build_native_runtime_configuration(cfg)
    assert runtime["development_seeds"] == cfg["discovery_search"]["calibration_seed_bank"]
    assert runtime["development_trajectory_count"] == 10
    assert runtime["physical_atlas"] == cfg["physical_atlas"]


def test_confirmation_seed_bank_is_fresh_and_frozen_after_selection() -> None:
    cfg = load_discovery_configuration()
    confirmation = set(cfg["confirmation"]["confirmation_seed_bank"])
    prior = (
        set(cfg["development_smoke"]["seed_bank"])
        | set(cfg["discovery_search"]["calibration_seed_bank"])
        | set(cfg["confirmation_round_1_exploratory"]["seed_bank"])
    )
    assert len(confirmation) == 100
    assert confirmation == set(range(4000, 4100))
    assert confirmation.isdisjoint(prior)
    assert cfg["confirmation"]["seed_bank_status"] == "FROZEN_AFTER_N10_SLA_FINALIST_SELECTION"


def run_all_tests() -> None:
    test_targeted_grid_has_frozen_25_candidates()
    test_sla_search_semantics_are_rho095_cumulative_from_t0()
    test_runtime_adapter_preserves_discovery_seed_bank()
    test_confirmation_seed_bank_is_fresh_and_frozen_after_selection()
    print("PHASE1_SCIENTIFIC_DISCOVERY_SLA_CONFIGURATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
