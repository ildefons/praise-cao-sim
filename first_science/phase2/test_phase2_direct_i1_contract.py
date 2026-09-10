"""Simulator-independent contract checks for the corrected direct Phase-2 I1 path."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    contract = _load(HERE / "config_phase2_i1_direct_trace_v2.json")
    evidence = _load(HERE / "phase2_i1_freeze_manifest_v1.json")

    assert contract["status"] == "PHASE2_DIRECT_I1_CONSTRUCTION_V2_AI_SELECTION_OPEN"
    assert contract["provider_acquisition"]["seed_bank"] == "6000..6099"
    assert contract["provider_acquisition"]["n_trajectories"] == 100

    ownership = contract["A_i_ownership"]
    assert ownership["owner"] == "Phase2 information construction"
    assert ownership["source"] == "provider_i_local_acquisition_evidence_only"
    assert ownership["A_G_is_input"] is False
    assert ownership["global_budget_split_allowed"] is False
    assert ownership["M0_or_M1_may_choose_A_i"] is False
    assert ownership["same_rule_form_for_all_providers"] is True
    assert ownership["selection_rule_status"] == "OPEN_BEFORE_FINAL_CARD_FREEZE"

    firewall = contract["information_firewall"]
    assert all(value is False for value in firewall.values())

    assert contract["surface_support"]["H"] == {
        "minimum": 0.0,
        "maximum": 240.0,
        "step": 5.0,
    }
    assert contract["surface_support"]["R"] == [
        0.95,
        0.975,
        0.9833333333333333,
        0.99,
        1.0,
    ]

    # The corrected architecture reuses the already frozen provider evidence;
    # it does not replace or reinterpret the actual acquisition corpus.
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

    assert contract["finalization"]["A_i_rule_frozen"] is False
    assert contract["finalization"]["final_cards_materialized"] is False
    assert contract["finalization"]["phase3_allowed"] is False

    print("PHASE2_DIRECT_I1_CONTRACT_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
