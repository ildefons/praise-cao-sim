from __future__ import annotations

import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_final_wb_v3b_fullsupport.json"


def test_final_wb_contract_is_locked_to_1000_unseen_trajectories():
    c=json.loads(CFG.read_text())
    assert c["status"]=="FROZEN_PHASE5_FINAL_WB_EXECUTION_V3B_FULLSUPPORT"
    wb=c["whitebox_generation"]
    assert wb["n_trajectories_per_eligible_physical_cell"]==1000
    assert wb["seeds"]["start"]==54000
    assert wb["seeds"]["end_inclusive"]==54999
    assert wb["seeds"]["n"]==1000
    assert wb["simulation_stop_seconds"]==240


def test_final_wb_unlock_requires_full_global_prediction_freeze():
    c=json.loads(CFG.read_text())
    u=c["unlock_condition"]
    assert u["required_global_prediction_status"]=="FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"
    assert u["required_prediction_frozen_cells"]==12
    assert u["required_gate_failed_step0_cells"]==4
    assert u["final_WB_read_before_unlock"] is False


def test_final_wb_does_not_reopen_methods_or_step0():
    c=json.loads(CFG.read_text())
    f=c["firewall_after_opening"]
    assert all(v is False for v in f.values())
    assert c["scope"]["queries_per_eligible_cell"]==15
    assert c["outputs"]["root"]=="results/05_final_wb_v3b_fullsupport"
