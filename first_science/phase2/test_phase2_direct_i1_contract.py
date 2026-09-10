"""Simulator-independent checks for the frozen direct-trace Phase-2 design."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    contract = _load(HERE / "config_phase2_i1_direct_trace_v2.json")
    card = _load(HERE / "config_phase2_i1_provider_card_v2.json")
    evidence = _load(HERE / "phase2_i1_freeze_manifest_v1.json")

    assert contract["status"] == "PHASE2_DIRECT_I1_CONSTRUCTION_V2_A_I_RULE_FROZEN"
    assert contract["frozen_I1_schema"]["definition"] == (
        "I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})"
    )
    assert contract["frozen_I1_schema"]["R"] == [
        0.95, 0.975, 0.9833333333333333, 0.99, 1.0
    ]

    assert card["status"] == "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_TRACE"
    assert card["R"]["phase2_selects_rho_i"] is False
    assert card["A_i"]["status"] == "FROZEN_TRACE_COORDINATE_SIGMA_CALIBRATION_V1"
    assert card["A_i"]["A_G_is_input"] is False
    assert card["A_i"]["rho_i_is_input"] is False
    calibration = card["A_i"]["calibration"]
    assert calibration["rho_anchor"] == 0.95
    assert calibration["H_star"] == 120.0
    assert calibration["sigma_target"] == 0.95
    assert "first sigma_i" in calibration["coordinate_rule"]
    assert "not forced" in calibration["combine_rule"]

    ai = contract["A_i_instantiation"]
    assert ai["status"] == "FROZEN_TRACE_COORDINATE_SIGMA_CALIBRATION_V1"
    assert ai["A_G_is_input"] is False
    assert ai["rho_i_is_input"] is False
    assert ai["M0_or_M1_may_choose_A_i"] is False
    assert ai["request_level_percentile_target_forbidden"] is True
    assert ai["implementation_module"] == "i1_local_region.py"

    materialization = contract["materialization"]
    assert materialization["status"] == "FROZEN_PIPELINE_READY"
    assert materialization["implementation_module"] == "materialize_frozen_i1_cards.py"
    assert materialization["private_evidence_hash_check_required"] is True
    assert materialization["card_hash_freeze_required"] is True
    assert materialization["same_materialized_cards_for_M0_and_M1"] is True
    assert (HERE / "materialize_frozen_i1_cards.py").exists()
    assert (HERE / "test_materialize_frozen_i1_cards.py").exists()

    harness = contract["hard_design_harness"]
    assert harness["A_G_to_A_i_forbidden"] is True
    assert harness["rho_i_to_A_i_forbidden"] is True
    assert harness["request_level_percentile_A_i_forbidden"] is True
    assert harness["coordinate_sigma_crossing_H120_rule_required"] is True
    assert harness["M0_result_used_to_construct_A_i"] is False
    assert harness["M1_result_used_to_construct_A_i"] is False

    firewall = contract["information_firewall"]
    assert firewall["phase3_may_read_private_provider_ledgers"] is False
    assert firewall["phase3_must_consume_hash_frozen_public_I1_cards"] is True

    assert evidence["n_trajectories"] == 100
    assert evidence["provider_rows"] == {
        "ProviderA": 119900,
        "ProviderB": 119900,
        "ProviderC": 119900,
    }
    assert "Phase 2 derives one fixed provider-local A_i" in evidence["A_i_policy"]
    assert evidence["phase2_selects_provider_specific_rho_i"] is False
    assert evidence["same_materialized_I1_for_M0_and_M1"] is True

    m0 = contract["m0_boundary"]
    assert m0["rho_slice_policy"] == "rho_i=rho_G for every required provider"
    assert m0["violation_budget_redistribution"] is False
    assert m0["numerical_I1_to_M0_status"] == (
        "REQUIRES_HASH_FROZEN_PUBLIC_I1_INSTANCE_MANIFEST"
    )

    finalization = contract["finalization"]
    assert finalization["public_I1_schema_frozen"] is True
    assert finalization["A_i_construction_rule_frozen"] is True
    assert finalization["materialization_pipeline_frozen"] is True
    assert finalization["materialized_instance_state_is_recorded_only_by_instance_manifest"] is True
    assert finalization["numerical_phase3_requires_materialized_instance_manifest"] is True

    # Rejected fixed-percentile branch remains absent.
    for filename in [
        "config_phase2_i1_local_region_rule_v1.json",
        "materialize_direct_i1_cards.py",
        "test_materialize_direct_i1_cards.py",
        "diagnose_direct_i1_local_ar.py",
        "test_diagnose_direct_i1_local_ar.py",
    ]:
        assert not (HERE / filename).exists(), filename

    print("PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS")
    print("I1_SCHEMA_REMAINS_FROZEN_PASS")
    print("A_I_H120_COORDINATE_CALIBRATION_FROZEN_PASS")
    print("I1_MATERIALIZATION_PIPELINE_FROZEN_PASS")
    print("PHASE3_PUBLIC_I1_ONLY_FIREWALL_FROZEN_PASS")
    print("REQUEST_LEVEL_PERCENTILE_A_I_BLOCKED_PASS")
    print("M0_SAME_RHO_POLICY_FROZEN_PASS")


if __name__ == "__main__":
    run_all_tests()
