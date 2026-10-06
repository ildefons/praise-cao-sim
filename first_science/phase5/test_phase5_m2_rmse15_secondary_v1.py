from __future__ import annotations

import math

from phase5_runtime_v2 import read_json
import run_phase5_m2_rmse15_secondary_v1 as runner


def test_rmse15_contract_matches_equivalent_mse_ratio():
    cfg=read_json(runner.CONTRACT)
    assert cfg["status"]==runner.EXPECTED_CONTRACT
    rmse=float(cfg["closeness_definition"]["rmse_ratio_max"])
    mse=float(cfg["closeness_definition"]["equivalent_mse_ratio_max"])
    assert math.isclose(rmse,1.15,rel_tol=0.0,abs_tol=1e-12)
    assert math.isclose(mse,rmse*rmse,rel_tol=0.0,abs_tol=1e-12)
    assert math.isclose(runner.RATIO,mse,rel_tol=0.0,abs_tol=1e-12)


def test_secondary_contract_forbids_new_search_and_wb():
    cfg=read_json(runner.CONTRACT)
    gen=cfg["candidate_generation"]
    assert int(gen["new_TPE_trials"])==0
    assert int(gen["new_LHS_points"])==0
    assert int(gen["new_GP_evaluations"])==0
    firewall=cfg["firewall"]
    assert firewall["graph_prediction_used"] is False
    assert firewall["graph_whitebox_used"] is False
    assert firewall["final_whitebox_used"] is False
    assert firewall["step0_whitebox_values_used"] is False


def test_secondary_keeps_primary_5_to_3_structure():
    cfg=read_json(runner.CONTRACT)
    p=cfg["portfolio_construction"]
    assert int(p["provisional_portfolio_size"])==5
    assert int(p["final_portfolio_size_per_provider"])==3
    assert "first three" in p["final_selection"].lower()
