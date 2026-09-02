"""Simulator-independent unit tests for the Phase-1 pre-search contract."""
from __future__ import annotations

import json
from pathlib import Path

from presearch_contract import (
    assert_phase1_development_smoke_budget_is_separate_from_scientific_coarse_search,
    assert_phase1_presearch_configuration_is_frozen,
    calculate_symmetric_provider_instruction_means,
    create_contract_complete_test_configuration,
    list_unfrozen_phase1_presearch_configuration_fields,
)


def load_phase1_configuration_for_contract_tests() -> dict:
    """Load the Phase-1 configuration stored beside this test module.

    Called by:
        - All test functions in ``test_presearch_contract.py``.
    """
    path = Path(__file__).with_name("config_phase1.json")
    return json.loads(path.read_text())


def test_symmetric_provider_instruction_parameterization() -> None:
    """Verify the agreed center/dispersion parameterization of native demand.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    means = calculate_symmetric_provider_instruction_means(100.0, 0.1)
    assert means.provider_a == 90.0
    assert means.provider_b == 100.0
    assert means.provider_c == 110.00000000000001


def test_development_smoke_budget_is_n10_and_separate() -> None:
    """Verify N=10 is development-only while scientific coarse search stays N=100.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = load_phase1_configuration_for_contract_tests()
    assert cfg["development_smoke"]["n_trajectories"] == 10
    assert len(cfg["development_smoke"]["seed_bank"]) == 10
    assert cfg["development_smoke"]["scientific_evidence"] is False
    assert cfg["coarse_search"]["n_trajectories_per_candidate"] == 100
    assert_phase1_development_smoke_budget_is_separate_from_scientific_coarse_search(cfg)


def test_incomplete_configuration_fails_closed() -> None:
    """Verify that the scientific config cannot start a search while OPEN values remain.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = load_phase1_configuration_for_contract_tests()
    missing = list_unfrozen_phase1_presearch_configuration_fields(cfg)
    assert "workload.period" in missing
    assert "provider_family.instruction_cv" in missing
    try:
        assert_phase1_presearch_configuration_is_frozen(cfg)
    except ValueError as exc:
        assert "not frozen" in str(exc)
    else:
        raise AssertionError("incomplete Phase-1 config unexpectedly passed")


def test_complete_configuration_passes_contract() -> None:
    """Verify the gate accepts a synthetically completed test-only fixture.

    Called by:
        - ``run_all_phase1_presearch_contract_tests`` in this module.
    """
    cfg = create_contract_complete_test_configuration(load_phase1_configuration_for_contract_tests())
    assert_phase1_presearch_configuration_is_frozen(cfg)


def run_all_phase1_presearch_contract_tests() -> None:
    """Execute all simulator-independent Phase-1 contract tests.

    Called by:
        - Python ``__main__`` entry point of ``test_presearch_contract.py``.
    """
    test_symmetric_provider_instruction_parameterization()
    test_development_smoke_budget_is_n10_and_separate()
    test_incomplete_configuration_fails_closed()
    test_complete_configuration_passes_contract()
    print("PHASE1_PRESEARCH_CONTRACT_TESTS_PASS")


if __name__ == "__main__":
    run_all_phase1_presearch_contract_tests()
