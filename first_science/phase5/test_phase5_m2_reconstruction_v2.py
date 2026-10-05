import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from m1_joint_lift_v2 import M1V2SearchBounds
from phase5_runtime_v2 import inclusive_seed_range, load_phase5_contracts
from run_phase5_m2_reconstruction_v2 import (
    A4_SOURCE,
    CLARIFICATION,
    _normalize,
    _provisional,
)


HERE=Path(__file__).resolve().parent


@pytest.fixture
def contracts():
    return load_phase5_contracts(HERE)


def test_phase5_m2_frozen_method_constants(contracts):
    m2=contracts.methods["M2"]
    assert m2["nonadaptive_LHS"]["n_points_per_provider"]==48
    assert m2["nonadaptive_LHS"]["seed"]==20260917
    assert m2["nonadaptive_LHS"]["compatibility_ratio"]==pytest.approx(1.25)
    assert m2["GP_levelset"]["new_evaluations_per_provider"]==48
    assert m2["GP_levelset"]["provisional_portfolio_size"]==5
    assert m2["GP_levelset"]["final_portfolio_size_per_provider"]==3
    assert m2["GP_levelset"]["compatibility_ratio"]==pytest.approx(1.25)


def test_phase5_m2_seed_banks_exact(contracts):
    r=contracts.seeds["provider_reconstruction"]
    search=inclusive_seed_range(r["M1_M2_local_search_CRN"])
    confirm=inclusive_seed_range(r["M1_M2_local_confirmation_CRN"])
    replay=inclusive_seed_range(r["M1_M2_local_replay_CRN"])
    assert (search[0],search[-1],len(search))==(52000,52024,25)
    assert (confirm[0],confirm[-1],len(confirm))==(52100,52199,100)
    assert (replay[0],replay[-1],len(replay))==(52200,52299,100)
    assert not set(search)&set(confirm)
    assert not set(search)&set(replay)
    assert not set(confirm)&set(replay)


def test_phase5_m2_a4_source_algorithm_is_frozen():
    cfg=json.loads(A4_SOURCE.read_text(encoding="utf-8"))
    assert cfg["warm_start"]["use_all_existing_tpe_points"] is True
    assert cfg["warm_start"]["use_all_m2_a2_lhs_points"] is True
    assert cfg["acquisition"]["name"]=="straddle_level_set"
    assert cfg["acquisition"]["beta_sigma"]==pytest.approx(1.96)
    pool=cfg["acquisition"]["candidate_pool"]
    assert pool["sampler"]=="scrambled_sobol"
    assert pool["sobol_power"]==14
    assert pool["points_per_provider"]==16384
    assert pool["seed"]==424242
    assert cfg["gp_model"]["random_seed"]==20260917
    assert cfg["provisional_portfolio"]["k_per_provider"]==5


def test_phase5_m2_confirmation_reference_clarification_is_frozen_text():
    text=CLARIFICATION.read_text(encoding="utf-8")
    assert "1.25 * frozen_M1_selected_confirmation_MSE" in text
    assert "does not inspect Step-0 WB values" in text


def test_normalization_uses_final_domain_coordinates():
    b=M1V2SearchBounds(
        mean_service_time_lower=0.01,
        mean_service_time_upper=1.0,
        cost_rate_lower=0.1,
        cost_rate_upper=10.0,
        service_cv_lower=0.0,
        service_cv_upper=2.0,
        cost_rate_public_reference=1.0,
    )
    z=_normalize(0.1,1.0,1.0,b)
    assert z==(pytest.approx(0.5),pytest.approx(0.5),pytest.approx(0.5))


def test_provisional_portfolio_is_best_then_maximin():
    rows=[]
    coords=[
        ("a",0.10,(0.0,0.0,0.0)),
        ("b",0.11,(1.0,0.0,0.0)),
        ("c",0.12,(0.0,1.0,0.0)),
        ("d",0.13,(0.0,0.0,1.0)),
        ("e",0.14,(1.0,1.0,1.0)),
        ("f",2.00,(0.5,0.5,0.5)),
    ]
    for cid,mse,z in coords:
        rows.append({
            "provider":"ProviderA","candidate_id":cid,"source_stage":"TPE",
            "z_log_mu":z[0],"z_log_kappa":z[1],"z_cv":z[2],
            "mean_service_time":1.0,"cost_rate":1.0,"service_cv":1.0,
            "local_mse":mse,
        })
    warm=pd.DataFrame(rows)
    gp=pd.DataFrame(columns=warm.columns)
    p=_provisional(warm,gp,ceiling=0.2,k=5)
    assert len(p)==5
    assert p.iloc[0]["candidate_id"]=="a"
    assert set(p["candidate_id"])=={"a","b","c","d","e"}
    assert list(p["selection_order"].astype(int))==[1,2,3,4,5]
