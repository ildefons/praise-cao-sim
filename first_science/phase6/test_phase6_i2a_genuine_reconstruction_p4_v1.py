from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import run_phase6_i2a_genuine_reconstruction_p4_v1 as p6

HERE=Path(__file__).resolve().parent


def test_contract_requires_genuine_i2a_search():
    c=json.loads((HERE/"config_phase6_i2a_genuine_reconstruction_p4_v1.json").read_text())
    assert c["status"]=="FROZEN_PHASE6_GENUINE_I2A_RECONSTRUCTION_P4_V1"
    assert c["candidate_generation"]["objective"].startswith("mean empirical 1D Wasserstein")
    assert c["candidate_generation"]["search_n_per_trial"]==15
    assert c["common_rescore"]["n"]==100
    assert c["firewall"]["private_i1_ledger_used"] is False
    assert c["firewall"]["graph_wb_used_for_reconstruction"] is False


def test_empirical_w1_equal_n_matches_sorted_formula():
    a=np.asarray([0.0,0.2,0.9,1.0])
    b=np.asarray([0.1,0.1,0.8,1.0])
    expected=float(np.mean(np.abs(np.sort(a)-np.sort(b))))
    assert abs(p6.empirical_w1(a,b)-expected)<1e-12


def test_empirical_w1_unequal_n_simple_case():
    # delta at 0 versus half mass at 0 and half at 1 => W1=0.5
    assert abs(p6.empirical_w1([0.0],[0.0,1.0])-0.5)<1e-12


def test_empirical_w1_symmetric_and_zero_identity():
    a=[0.0,0.25,0.5,1.0]
    b=[0.1,0.4,0.8]
    assert abs(p6.empirical_w1(a,b)-p6.empirical_w1(b,a))<1e-12
    assert p6.empirical_w1(a,a)<1e-15
