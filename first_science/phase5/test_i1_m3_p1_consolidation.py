"""Pure, no-simulation P1 I1-M3 consolidation checks.

This is an engineering contract smoke, NOT a scientific prediction or a
reconstruction result. It does not load hidden provider models or WB outcomes.
Run from first_science/phase5: pytest -q test_i1_m3_p1_consolidation.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase5_reconstruction_v3_selection import gibbs_weights, joint_product_support

HERE = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _json(filename: str) -> dict:
    return json.loads((HERE / filename).read_text(encoding="utf-8"))


def test_p1_is_frozen_symmetric_development_world():
    battery = _json("config_phase5_recoverability_battery_v2.json")
    p1 = next(w for w in battery["provider_worlds"] if w["id"] == "P1")
    assert p1["D_instructions"] == 330_000_000
    assert p1["delta"] == 0
    assert set(p1["provider_means"]) == set(PROVIDERS)
    assert len(set(p1["provider_means"].values())) == 1
    assert battery["public_I1"]["same_cards_reused_across_graphs_within_provider_world"]
    assert battery["public_I1"]["region_sigma_evidence_disjoint"]
    assert battery["scientific_target"]["performance_pass_fail_threshold"] is None


def test_p1_method_contracts_agree_on_seven_candidate_m3():
    v3 = _json("config_phase5_provider_reconstruction_v3.json")
    v3b = _json("config_phase5_provider_reconstruction_v3b.json")
    graph = _json("config_phase5_graph_prediction_v3b_fullsupport.json")
    assert v3["candidate_reconstruction"]["candidate_count_per_provider"] == 7
    assert v3["candidate_reconstruction"]["common_rescore"].startswith("All seven")
    assert v3b["methods"]["M3"]["provider_models"].startswith("all seven")
    assert v3b["selection_basis"]["hard_rmse_compatibility_gate"] is False
    assert graph["methods"]["M3"]["full_joint_support"] == 343
    assert graph["methods"]["M3"]["graph_budget_per_physical_cell"] == 1400
    assert graph["methods"]["M3"]["primary_support"] == "all ranks 1..343"
    assert graph["eligibility"]["eligible_provider_worlds"].count("P1") == 1


def test_provider_weighting_and_joint_factorization():
    # Synthetic public I1 points, not real P1 evidence.
    target = np.array([0.15, 0.35, 0.65, 0.85], dtype=float)
    tables = {}
    for provider in PROVIDERS:
        predictions = np.array([
            np.clip(target + (i - 3) * 0.012, 0.0, 1.0)
            for i in range(7)
        ])
        t = gibbs_weights(
            [f"{provider}_candidate_{i}" for i in range(7)],
            predictions,
            target,
            n_public=100,
            n_candidate=100,
            lam=30.0,
        )
        assert len(t) == 7
        assert np.isclose(t["weight"].sum(), 1.0)
        assert (t["weight"] > 0).all()
        tables[provider] = t

    joint = joint_product_support(tables)
    assert len(joint) == 343
    assert joint["joint_rank"].tolist() == list(range(1, 344))
    assert np.isclose(joint["joint_weight"].sum(), 1.0)
    assert joint["joint_weight"].is_monotonic_decreasing
    for provider in PROVIDERS:
        assert joint[f"{provider}_candidate_id"].nunique() == 7


def test_p1_graph_query_and_whitebox_are_distinct_from_provider_i1():
    battery = _json("config_phase5_recoverability_battery_v2.json")
    graph = _json("config_phase5_graph_prediction_v3b_fullsupport.json")
    assert len(battery["public_I1"]["rho_region_values"]) == 5
    assert len(battery["public_I1"]["rho_query_values"]) == 5
    assert graph["queries"]["queries_per_eligible_cell"] == 15
    assert graph["horizons"]["prediction_grid_seconds"]["end_inclusive"] == 240
    assert graph["firewall"]["graph_prediction_must_not_read"]
    assert graph["seeds"]["final_whitebox"]["may_be_opened_before_global_prediction_freeze"] is False
