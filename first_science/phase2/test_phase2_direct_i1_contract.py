"""Simulator-independent checks for the direct-trace Phase-2 design harness.

The public I1 schema and the recovered provider-local coordinate calibration are
frozen.  The tests prevent regression to the rejected request-level percentile
construction, A_G localization, rho_i-driven A_i construction, or method
feedback.
"""
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
    assert contract["finalization"]["public_I1_schema_frozen"] is True
    assert contract["finalization"]["A_i_construction_rule_frozen"] is True
    assert contract["frozen_I1_schema"]["definition"] == (
        "I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})"
    )
    assert contract["frozen_I1_schema"]["sigma"] == (
        "sigma_i(A_i,H;rho)=P(c_i(A_i,H)>=rho)"
    )
    assert contract["frozen_I1_schema"]["R"] == [
        0.95, 0.975, 0.9833333333333333, 0.99, 1.0
    ]

    assert card["status"] == "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_TRACE"
    assert card["frozen"] is True
    assert card["card_instance"] == (
        "I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})"
    )
    assert card["R"]["phase2_selects_rho_i"] is False
    assert card["A_i"]["status"] == "FROZEN_TRACE_COORDINATE_SIGMA_CALIBRATION_V1"
    assert card["A_i"]["owner"] == "Phase2 information construction"
    assert card["A_i"]["A_G_is_input"] is False
    assert card["A_i"]["rho_i_is_input"] is False
    assert card["A_i"]["M0_or_M1_may_choose_or_alter_A_i"] is False
    assert card["A_i"]["request_level_percentile_target_used"] is False
    assert card["A_i"]["posthoc_method_result_tuning_authorized"] is False

    card_calibration = card["A_i"]["calibration"]
    assert card_calibration["rho_anchor"] == 0.95
    assert card_calibration["H_star"] == 120.0
    assert card_calibration["sigma_target"] == 0.95
    assert "first sigma_i" in card_calibration["coordinate_rule"]
    assert "not forced" in card_calibration["combine_rule"]

    ai = contract["A_i_instantiation"]
    assert ai["status"] == "FROZEN_TRACE_COORDINATE_SIGMA_CALIBRATION_V1"
    assert ai["source"] == "provider_i_local_acquisition_evidence_only"
    assert ai["A_G_is_input"] is False
    assert ai["rho_i_is_input"] is False
    assert ai["global_budget_split_allowed"] is False
    assert ai["M0_or_M1_may_choose_A_i"] is False
    assert ai["rho_anchor"] == 0.95
    assert ai["H_star"] == 120.0
    assert ai["sigma_target"] == 0.95
    assert "first sigma_i" in ai["selection_rule"]
    assert ai["request_level_percentile_target_forbidden"] is True
    assert ai["posthoc_method_result_tuning_forbidden"] is True
    assert ai["implementation_module"] == "i1_local_region.py"

    harness = contract["hard_design_harness"]
    assert harness["I1_schema_may_not_be_reopened_to_solve_A_i_instantiation"] is True
    assert harness["A_G_to_A_i_forbidden"] is True
    assert harness["rho_i_to_A_i_forbidden"] is True
    assert harness["global_budget_split_forbidden"] is True
    assert harness["request_level_percentile_A_i_forbidden"] is True
    assert harness["coordinate_sigma_crossing_H120_rule_required"] is True
    assert harness["posthoc_local_sigma_shape_tuning_forbidden"] is True
    assert harness["Phase1_global_sigma_used_to_construct_A_i"] is False
    assert harness["M0_result_used_to_construct_A_i"] is False
    assert harness["M1_result_used_to_construct_A_i"] is False

    # The rejected fixed-p99 branch must remain absent.
    for filename in [
        "config_phase2_i1_local_region_rule_v1.json",
        "materialize_direct_i1_cards.py",
        "test_materialize_direct_i1_cards.py",
        "diagnose_direct_i1_local_ar.py",
        "test_diagnose_direct_i1_local_ar.py",
    ]:
        assert not (HERE / filename).exists(), filename

    assert (HERE / "i1_local_region.py").exists()

    # The already acquired evidence is preserved exactly.
    assert evidence["n_trajectories"] == 100
    assert evidence["provider_rows"] == {
        "ProviderA": 119900,
        "ProviderB": 119900,
        "ProviderC": 119900,
    }
    assert set(evidence["provider_corpus_sha256"]) == {
        "ProviderA", "ProviderB", "ProviderC"
    }

    m0 = contract["m0_boundary"]
    assert m0["generic_topology_aware_LCQ_algebra_remains_frozen"] is True
    assert m0["rho_slice_policy_status"] == "FROZEN_SAME_AS_GLOBAL"
    assert m0["rho_slice_policy"] == "rho_i=rho_G for every required provider"
    assert m0["violation_budget_redistribution"] is False
    assert m0["M0_interpretation"] == (
        "analytic baseline prediction, not a global-rho certification lower bound"
    )
    assert m0["numerical_I1_to_M0_status"] == "READY_FOR_DIAGNOSTIC_AFTER_TRACE_DERIVED_A_i"
    assert m0["M0_may_not_choose_or_modify_A_i"] is True

    assert contract["finalization"]["concrete_A_i_calibrated_from_anchor_rho_G_0p95"] is True
    assert contract["finalization"]["phase2_rho_i_selected"] is False
    assert contract["finalization"]["final_I1_materialized"] is False
    assert contract["finalization"]["numerical_phase3_diagnostic_allowed"] is True

    print("PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS")
    print("I1_SCHEMA_REMAINS_FROZEN_PASS")
    print("A_I_H120_COORDINATE_CALIBRATION_FROZEN_PASS")
    print("REQUEST_LEVEL_PERCENTILE_A_I_BLOCKED_PASS")
    print("JOINT_SIGMA_NOT_FORCED_TO_CALIBRATION_TARGET_PASS")
    print("M0_SAME_RHO_POLICY_FROZEN_PASS")


if __name__ == "__main__":
    run_all_tests()
