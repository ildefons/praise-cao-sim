from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase6_i2a_marginal_audit_v1 as p6

HERE=Path(__file__).resolve().parent


def test_contract_is_provider_only_and_reuses_same_i1_evidence():
    c=json.loads((HERE/"config_phase6_i2a_marginal_audit_v1.json").read_text())
    assert c["status"]=="FROZEN_PHASE6_I2A_MARGINAL_AUDIT_V1"
    assert c["target_evidence"]["reuse_same_phase5_i1_sigma_corpus"] is True
    assert c["target_evidence"]["new_provider_world_simulation"] is False
    assert c["candidate_family"]["reuse_parameters_without_refit"] is True
    assert c["firewall"]["graph_prediction_read"] is False
    assert c["firewall"]["graph_wb_read"] is False
    assert c["firewall"]["final_wb_read"] is False
    assert c["firewall"]["hidden_provider_parameters_read"] is False


def test_equal_n_wasserstein_matches_sorted_absolute_difference():
    a=[0.0,0.2,1.0,0.9]
    b=[0.1,0.1,0.8,1.0]
    expected=np.mean(np.abs(np.sort(a)-np.sort(b)))
    assert abs(p6.empirical_w1_equal_n(a,b)-expected)<1e-15


def test_wasserstein_is_permutation_invariant():
    a=[0.0,0.3,0.7,1.0]
    b=[0.2,0.4,0.8,0.9]
    x=p6.empirical_w1_equal_n(a,b)
    y=p6.empirical_w1_equal_n(list(reversed(a)),[b[2],b[0],b[3],b[1]])
    assert abs(x-y)<1e-15


def test_public_i2a_removes_trajectory_identity_and_sorts_independently():
    rows=[]
    for H,vals in [(5.0,[0.9,0.1,0.5]),(10.0,[0.2,1.0,0.4])]:
        for tid,value in enumerate(vals):
            rows.append({
                "region_id":"R1",
                "region_rho":0.95,
                "H":H,
                "trajectory_private":tid,
                "compliance_fraction":value,
            })
    # publicizer normally sees N=100; patch up to N=100 per group.
    expanded=[]
    for H in (5.0,10.0):
        base=[r for r in rows if r["H"]==H]
        for k in range(100):
            rec=dict(base[k%3])
            rec["trajectory_private"]=k
            expanded.append(rec)
    pub=p6._publicize_i2a(pd.DataFrame(expanded),"ProviderA")
    assert "trajectory_private" not in pub.columns
    for _,g in pub.groupby(["region_id","H"]):
        vals=g["compliance_fraction"].to_numpy()
        assert np.all(vals[:-1]<=vals[1:])


def test_phase6_runner_has_no_graph_simulator_or_wb_dependency():
    source=Path(p6.__file__).read_text(encoding="utf-8")
    forbidden=(
        "execute_one_phase5_graph_trajectory",
        "phase5_graph_simulator",
        "final_wb",
        "pointwise_primary_joined",
        "step0_frozen_queries",
    )
    lower=source.lower()
    for token in forbidden:
        assert token.lower() not in lower
