"""Simulator-independent tests for the Phase-3A structural M0 contract."""
from __future__ import annotations

import json
from pathlib import Path

from m0_structural_contract import (
    PROVIDERS,
    aligned_counting_certificate,
    decompose_global_query_equal_m0,
    derive_public_boundary_context,
    equal_violation_budget,
    load_frozen_global_queries,
    request_level_implication_holds,
    validate_phase3a_contract_sources,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    here = Path(__file__).resolve().parent
    phase3a = _load(here / "config_phase3a_m0_structural_contract_v1.json")
    phase1_manifest = _load(here.parent / "phase1" / "phase1_v2_ar_freeze_manifest_v1.json")
    phase1_config = _load(here.parent / "phase1" / "config_phase1_discovery_v1.json")
    phase2_freeze = _load(here.parent / "phase2" / "phase2_i1_freeze_manifest_v1.json")
    phase2_card = _load(here.parent / "phase2" / "config_phase2_i1_provider_card_v1.json")

    validate_phase3a_contract_sources(phase3a, phase1_manifest, phase2_freeze, phase2_card)
    context = derive_public_boundary_context(phase1_config)
    assert abs(context.root_network_latency - 0.001001) < 1e-15
    assert abs(context.join_network_latency - 0.001001) < 1e-15
    assert abs(context.pre_service_time - 0.005) < 1e-15
    assert abs(context.post_service_time - 0.005) < 1e-15
    assert abs(context.latency_common - 0.012002) < 1e-15
    assert all(abs(value - 0.001001) < 1e-15 for value in context.branch_network_latency)
    assert abs(context.fixed_execution_cost - 0.03) < 1e-15

    epsilon_local, rho_local = equal_violation_budget(0.95, 3)
    assert abs(epsilon_local - 0.05 / 3.0) < 1e-15
    assert abs(rho_local - 0.9833333333333333) < 1e-15
    assert any(abs(float(v) - rho_local) < 1e-15 for v in phase2_card["R"]["values"])

    global_queries = load_frozen_global_queries(phase1_manifest)
    assert {q.selection_role for q in global_queries} == {"latency", "cost", "mixed"}

    expected = {
        "latency": {
            "l_max": 0.6755498419999432,
            "c_max": 0.8579676517266361,
        },
        "cost": {
            "l_max": 0.734391139000015,
            "c_max": 0.703264227,
        },
        "mixed": {
            "l_max": 0.734391139000015,
            "c_max": 0.714699775,
        },
    }

    for global_query in global_queries:
        local_queries = decompose_global_query_equal_m0(global_query, context)
        assert [q.provider_id for q in local_queries] == list(PROVIDERS)
        for local in local_queries:
            assert abs(local.l_max - expected[global_query.selection_role]["l_max"]) < 1e-15
            assert abs(local.c_max - expected[global_query.selection_role]["c_max"]) < 1e-15
            assert abs(local.q_min - 0.5) < 1e-15
            assert abs(local.rho_local - rho_local) < 1e-15
        assert request_level_implication_holds(global_query, local_queries, context)

    # Hand-checkable aligned counting theorem: 60 common root IDs and one
    # distinct local failure at each provider. Every local fraction is 59/60;
    # conjunction is 57/60 = 0.95.
    roots = [f"r{i:02d}" for i in range(60)]
    local = {
        provider: {root: True for root in roots}
        for provider in PROVIDERS
    }
    local["ProviderA"]["r03"] = False
    local["ProviderB"]["r17"] = False
    local["ProviderC"]["r42"] = False
    certificate = aligned_counting_certificate(
        local,
        rho_global=0.95,
        rho_local={provider: rho_local for provider in PROVIDERS},
    )
    assert certificate["n_aligned_roots"] == 60
    assert certificate["local_targets_hold"] is True
    assert certificate["budget_valid"] is True
    assert certificate["certified"] is True
    assert abs(certificate["global_sufficient_conjunction_fraction"] - 0.95) < 1e-15

    # Equal cardinality is not enough. Distinct logical root-id sets must be
    # rejected so decision-time subset misalignment cannot silently satisfy the
    # structural counting helper.
    misaligned = {
        "ProviderA": {"r1": True, "r2": True},
        "ProviderB": {"r1": True, "r3": True},
        "ProviderC": {"r1": True, "r2": True},
    }
    try:
        aligned_counting_certificate(
            misaligned,
            rho_global=0.95,
            rho_local={provider: rho_local for provider in PROVIDERS},
        )
    except ValueError as exc:
        assert "not exactly aligned" in str(exc)
    else:
        raise AssertionError("misaligned root-id sets must be rejected")

    proof = phase3a["proof_status"]
    assert proof["real_decision_time_horizon_alignment"] == "UNRESOLVED_REQUIRES_SEPARATE_AUDIT"
    assert proof["independent_probability_product"] == "NOT_YET_FROZEN_PHASE3B"

    print("PHASE3A_M0_STRUCTURAL_CONTRACT_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
