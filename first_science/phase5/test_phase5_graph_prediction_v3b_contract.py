from __future__ import annotations

from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_graph_prediction_v3b.json"


def _load():
    return json.loads(CFG.read_text(encoding="utf-8"))


def test_v3b_graph_contract_status_and_eligibility():
    c=_load()
    assert c["status"]=="FROZEN_PHASE5_GRAPH_PREDICTION_EXECUTION_V3B"
    e=c["eligibility"]
    assert e["expected_total_physical_cells"]==16
    assert e["expected_eligible_cells"]==12
    assert e["expected_gate_failed_step0_cells"]==4
    assert e["expected_gate_failed_provider_world"]=="P2"


def test_v3b_graph_contract_methods():
    c=_load()
    assert c["methods"]["method_ids"]==[
        "M0","M1","M2","M3_TOP1","M3_TOP3","M3_TOP14"
    ]
    assert c["methods"]["removed_v2_diagnostic"]["included"] is False
    assert c["methods"]["M1"]["joint_models"]==1
    assert c["methods"]["M2"]["joint_models"]==27
    assert c["methods"]["M2"]["joint_weight"]==1.0/27.0
    assert c["methods"]["M3"]["full_joint_support"]==343
    assert c["methods"]["M3"]["retained_support_size"]==14
    assert c["methods"]["M3"]["graph_budget_per_physical_cell"]==1400
    assert c["methods"]["M3"]["no_extra_simulation_for_top1_or_top3"] is True


def test_v3b_graph_contract_seeds_queries_and_firewall():
    c=_load()
    assert c["seeds"]["M1_M2"]["start"]==56900
    assert c["seeds"]["M1_M2"]["end_inclusive"]==56999
    assert c["seeds"]["M1_M2"]["n"]==100
    assert c["seeds"]["M3"]["seed_base"]==7000000
    assert c["seeds"]["M3"]["seed_block_stride"]==10000
    assert c["seeds"]["final_whitebox"]["may_be_opened_before_global_prediction_freeze"] is False
    assert c["queries"]["queries_per_eligible_cell"]==15
    assert c["horizons"]["prediction_grid_seconds"]=={
        "start":0,"end_inclusive":240,"step":5
    }
    assert c["horizons"]["primary_evaluation_grid_seconds"]=={
        "start":60,"end_inclusive":240,"step":5
    }
    assert c["outputs"]["root"]=="results/04_prediction_v3b"
    assert c["global_prediction_freeze"]["required_before_final_whitebox"] is True
