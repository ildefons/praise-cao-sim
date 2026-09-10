"""Simulator-independent tests for corrected Phase-2 I1 query instantiation."""
from __future__ import annotations

import json
from pathlib import Path

from i1_query_instantiation import (
    PROVIDERS,
    QUERY_DECLARATION_STATUS,
    build_exact_i1_query_declaration,
    derive_public_localization_context,
    validate_exact_i1_query_declaration,
)

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    phase1_manifest = _load(PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json")
    phase1_config = _load(PHASE1 / "config_phase1_discovery_v1.json")
    contract = _load(HERE / "config_phase2_i1_query_instantiation_v1.json")
    card_contract = _load(HERE / "config_phase2_i1_provider_card_v1.json")

    context = derive_public_localization_context(phase1_config)
    assert abs(context.latency_common - 0.012002) < 1e-15
    assert len(context.branch_network_latency) == 3
    assert all(abs(x - 0.001001) < 1e-15 for x in context.branch_network_latency)
    assert abs(context.fixed_execution_cost - 0.03) < 1e-15
    assert abs(context.fixed_quality_floor - 1.0) < 1e-15

    declaration = build_exact_i1_query_declaration(
        phase1_manifest,
        phase1_config,
        contract,
    )
    validate_exact_i1_query_declaration(declaration)

    assert declaration["status"] == QUERY_DECLARATION_STATUS
    assert declaration["rho_localization_performed"] is False
    assert declaration["same_materialized_cards_for_M0_and_M1"] is True
    assert set(declaration["regions_by_provider"]) == set(PROVIDERS)

    expected = {
        "V2_LATENCY_LOCAL": (0.6755498419999432, 0.8579676517266361, 0.5),
        "V2_COST_LOCAL": (0.7343911390000150, 0.7032642270000000, 0.5),
        "V2_MIXED_LOCAL": (0.7343911390000150, 0.7146997750000000, 0.5),
    }

    reference = declaration["regions_by_provider"]["ProviderA"]
    assert {r["region_id"] for r in reference} == set(expected)
    for region in reference:
        exp_l, exp_c, exp_q = expected[region["region_id"]]
        assert abs(float(region["l_max"]) - exp_l) < 1e-15
        assert abs(float(region["c_max"]) - exp_c) < 1e-15
        assert abs(float(region["q_min"]) - exp_q) < 1e-15
        assert "rho" not in region and "rho_local" not in region

    # The first benchmark I1 instantiation is deliberately symmetric across
    # providers. The exact same three A_i regions must therefore be declared for
    # ProviderA/B/C before any method reads card values.
    for provider in PROVIDERS[1:]:
        assert declaration["regions_by_provider"][provider] == reference

    # The card exposes rho as a complete frozen support, so Phase 2 must not
    # choose the M0 equal-budget slice. It must merely ensure the support exists.
    rho_support = [float(x) for x in card_contract["R"]["values"]]
    assert rho_support == [0.95, 0.975, 0.9833333333333333, 0.99, 1.0]
    assert 0.9833333333333333 in rho_support

    print("PHASE2_I1_QUERY_INSTANTIATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
