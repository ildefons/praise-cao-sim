"""Simulator-independent unit tests for the Phase-1 discovery/confirmation contract."""
from __future__ import annotations

import json
from pathlib import Path

from presearch_contract import (
    assert_phase1_confirmation_configuration_is_ready,
    assert_phase1_discovery_configuration_is_frozen,
    assert_phase1_sampling_policy_is_consistent,
    calculate_symmetric_provider_instruction_means,
    create_confirmation_ready_test_configuration,
    create_contract_complete_test_configuration,
    create_frozen_selected_whitebox_test_manifest,
    list_unfrozen_phase1_discovery_configuration_fields,
)


def load_phase1_configuration_for_contract_tests() -> dict:
    """Load the Phase-1 configuration stored beside this test module.

    Called by:
        - All test functions in ``test_presearch_contract.py``.
    """
    path = Path(__file__).with_name("config_phase1.json")
    return json.loads(path.read_text())


def test_symmetric_provider_instruction_parameterization() -> None:
    """Verify the agreed center/dispersion provider parameterization.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    means = calculate_symmetric_provider_instruction_means(100.0, 0.1)
    assert means.provider_a == 90.0
    assert means.provider_b == 100.0
    assert means.provider_c == 110.00000000000001


def test_discovery_is_n10_and_confirmation_is_n100() -> None:
    """Verify discovery uses N=10 and finalist confirmation uses fresh N=100.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = load_phase1_configuration_for_contract_tests()
    assert cfg["development_smoke"]["n_trajectories"] == 10
    assert cfg["development_smoke"]["scientific_evidence"] is False
    assert cfg["discovery_search"]["n_trajectories_per_candidate"] == 10
    assert cfg["confirmation"]["n_trajectories_per_selected_whitebox"] == 100
    assert cfg["confirmation"]["fresh_seeds_required"] is True
    assert cfg["confirmation"]["recalibrate_A_on_confirmation"] is False
    assert_phase1_sampling_policy_is_consistent(cfg)


def test_incomplete_discovery_configuration_fails_closed() -> None:
    """Verify scientific N=10 discovery cannot start while OPEN values remain.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = load_phase1_configuration_for_contract_tests()
    missing = list_unfrozen_phase1_discovery_configuration_fields(cfg)
    assert "workload.period" in missing
    assert "provider_family.instruction_cv" in missing
    assert "discovery_search.calibration_seed_bank" in missing
    try:
        assert_phase1_discovery_configuration_is_frozen(cfg)
    except ValueError as exc:
        assert "not frozen" in str(exc)
    else:
        raise AssertionError("incomplete Phase-1 discovery config unexpectedly passed")


def test_complete_discovery_configuration_passes_contract() -> None:
    """Verify the N=10 discovery gate accepts a complete test-only fixture.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = create_contract_complete_test_configuration(
        load_phase1_configuration_for_contract_tests()
    )
    assert_phase1_discovery_configuration_is_frozen(cfg)


def test_confirmation_requires_frozen_whiteboxes_and_fresh_n100_seeds() -> None:
    """Verify confirmation rejects unfrozen finalists and accepts valid fresh seeds.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    base = load_phase1_configuration_for_contract_tests()
    cfg = create_confirmation_ready_test_configuration(base)

    empty_manifest = {
        "status": "EMPTY_UNTIL_DISCOVERY_SELECTION",
        "whiteboxes": [],
    }
    try:
        assert_phase1_confirmation_configuration_is_ready(cfg, empty_manifest)
    except ValueError as exc:
        assert "FROZEN_FOR_CONFIRMATION" in str(exc)
    else:
        raise AssertionError("confirmation unexpectedly accepted an unfrozen empty manifest")

    frozen_manifest = create_frozen_selected_whitebox_test_manifest()
    assert_phase1_confirmation_configuration_is_ready(cfg, frozen_manifest)

    cfg_with_seed_overlap = create_confirmation_ready_test_configuration(base)
    cfg_with_seed_overlap["confirmation"]["confirmation_seed_bank"][0] = cfg_with_seed_overlap[
        "discovery_search"
    ]["calibration_seed_bank"][0]
    try:
        assert_phase1_confirmation_configuration_is_ready(
            cfg_with_seed_overlap,
            frozen_manifest,
        )
    except ValueError as exc:
        assert "disjoint" in str(exc)
    else:
        raise AssertionError("confirmation unexpectedly accepted a discovery-seed overlap")


def run_all_phase1_presearch_contract_tests() -> None:
    """Execute all simulator-independent Phase-1 contract tests.

    Called by:
        - Python ``__main__`` entry point of ``test_presearch_contract.py``.
    """
    test_symmetric_provider_instruction_parameterization()
    test_discovery_is_n10_and_confirmation_is_n100()
    test_incomplete_discovery_configuration_fails_closed()
    test_complete_discovery_configuration_passes_contract()
    test_confirmation_requires_frozen_whiteboxes_and_fresh_n100_seeds()
    print("PHASE1_PRESEARCH_CONTRACT_TESTS_PASS")


if __name__ == "__main__":
    run_all_phase1_presearch_contract_tests()
