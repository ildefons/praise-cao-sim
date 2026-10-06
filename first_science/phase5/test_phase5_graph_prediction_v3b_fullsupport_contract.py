from __future__ import annotations

import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"


def test_fullsupport_contract_primary_m3_is_343():
    c=json.loads(CFG.read_text())
    assert c["status"]=="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT"
    assert c["methods"]["M3"]["full_joint_support"]==343
    assert c["methods"]["M3"]["primary_support"]=="all ranks 1..343"
    assert c["methods"]["M3"]["primary_method_id"]=="M3_FULL343"
    assert c["methods"]["M3"]["graph_budget_per_physical_cell"]==1400
    assert c["methods"]["M3"]["full_support_truncation_bound"]==0.0
    assert c["methods"]["M3"]["no_extra_simulation_for_nested_diagnostics"] is True


def test_fullsupport_seed_registry_extends_rank_streams():
    s=json.loads(SEEDS.read_text())
    assert s["status"]=="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT"
    m3=s["graph_prediction"]["M3"]
    assert m3["support_ranks"]=="1..343"
    assert m3["support_size"]==343
    assert m3["total_budget_per_physical_cell"]==1400
    assert m3["seed_base"]==7000000
    assert m3["seed_block_stride"]==10000
    assert s["final_whitebox"]["start"]==54000
    assert s["final_whitebox"]["end_inclusive"]==54999


def test_fullsupport_revision_is_pre_graph_wb_and_new_namespace():
    c=json.loads(CFG.read_text())
    p=c["provenance"]
    assert p["graph_prediction_used_before_revision"] is False
    assert p["graph_whitebox_used_before_revision"] is False
    assert p["final_whitebox_used_before_revision"] is False
    assert c["outputs"]["root"]=="results/04_prediction_v3b_fullsupport"
    assert c["seeds"]["final_whitebox"]["may_be_opened_before_global_prediction_freeze"] is False
