"""Simulator-independent checks for the direct-trace Phase-2 design harness.

This test is intentionally a scientific-boundary test, not a materialization
test. If the public I1 representation is not explicitly frozen in the design,
Phase 2 must stop rather than infer an A_i envelope from older code.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    contract = _load(HERE / "config_phase2_i1_direct_trace_v2.json")
    evidence = _load(HERE / "phase2_i1_freeze_manifest_v1.json")

    assert contract["status"] == (
        "PHASE2_DIRECT_I1_CONSTRUCTION_V2_REPRESENTATION_RECONCILIATION_OPEN"
    )
    retained = contract["retained_valid_evidence"]
    assert retained["seed_bank"] == "6000..6099"
    assert retained["n_trajectories"] == 100

    reconciliation = contract["representation_reconciliation"]
    assert reconciliation["status"] == "OPEN_HARD_STOP_BEFORE_MORE_I1_MATERIALIZATION_CODE"
    assert reconciliation["public_I1_schema"] == "NOT_YET_FROZEN"
    assert reconciliation["raw_trace_publication_assumed"] is False

    harness = contract["hard_design_harness"]
    assert harness["A_G_to_A_i_forbidden"] is True
    assert harness["global_budget_split_forbidden"] is True
    assert harness["quantile_or_percentile_based_A_i_forbidden"] is True
    assert harness["support_extrema_based_A_i_forbidden_without_explicit_design_change"] is True
    assert harness["local_sigma_shape_tuning_forbidden"] is True
    assert harness["Phase1_global_sigma_used_to_construct_I1"] is False
    assert harness["M0_result_used_to_construct_I1"] is False
    assert harness["M1_result_used_to_construct_I1"] is False
    assert harness["infer_unspecified_scientific_choice_from_old_code"] is False
    assert harness["required_behavior_when_design_is_unspecified"] == (
        "STOP_AND_RECONCILE_THE_DESIGN_DOCUMENT"
    )

    # The p99/quantile branch was a design-harness violation and must not remain
    # as active Phase-2 materialization code.
    forbidden_active_files = [
        "config_phase2_i1_local_region_rule_v1.json",
        "config_phase2_i1_provider_card_v2.json",
        "materialize_direct_i1_cards.py",
        "test_materialize_direct_i1_cards.py",
        "diagnose_direct_i1_local_ar.py",
        "test_diagnose_direct_i1_local_ar.py",
    ]
    for filename in forbidden_active_files:
        assert not (HERE / filename).exists(), filename

    # The already acquired evidence is preserved exactly.
    assert evidence["n_trajectories"] == 100
    assert evidence["provider_rows"] == {
        "ProviderA": 119900,
        "ProviderB": 119900,
        "ProviderC": 119900,
    }
    assert set(evidence["provider_corpus_sha256"]) == {
        "ProviderA",
        "ProviderB",
        "ProviderC",
    }

    m0 = contract["m0_boundary"]
    assert m0["generic_topology_aware_LCQ_algebra_remains_frozen"] is True
    assert m0["numerical_I1_to_M0_adapter_status"] == "BLOCKED_PENDING_FINAL_I1_SCHEMA"
    assert m0["M0_may_not_force_a_particular_I1_representation"] is True

    finalization = contract["finalization"]
    assert finalization["public_I1_schema_frozen"] is False
    assert finalization["final_I1_materialized"] is False
    assert finalization["numerical_phase3_allowed"] is False

    # The active contract itself must not encode the rejected percentile rule.
    active_text = (HERE / "config_phase2_i1_direct_trace_v2.json").read_text(
        encoding="utf-8"
    ).lower()
    assert "p99" not in active_text
    assert '"quantile":' not in active_text
    assert '"percentile":' not in active_text

    print("PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS")
    print("UNSPECIFIED_I1_REPRESENTATION_HARD_STOP_PASS")
    print("PERCENTILE_A_I_BRANCH_REMOVED_PASS")
    print("M0_STRUCTURAL_KERNEL_PRESERVED_NUMERIC_ADAPTER_BLOCKED_PASS")


if __name__ == "__main__":
    run_all_tests()
