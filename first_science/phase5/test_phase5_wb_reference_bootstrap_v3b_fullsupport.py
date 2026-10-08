from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_wb_reference_bootstrap_v3b_fullsupport as bs

HERE=Path(__file__).resolve().parent


def test_registered_bootstrap_constants():
    c=json.loads((HERE/"config_phase5_wb_reference_bootstrap_v3b_fullsupport.json").read_text())
    assert bs.REPS==10000
    assert bs.BOOT_SEED==2026100201
    assert bs.N==1000
    assert c["bootstrap"]["joint_resample_across_physical_cells"] is True
    assert c["bootstrap"]["method_predictions_fixed"] is True


def test_pass_vector_zero_decisions_uses_frozen_compliance_one():
    frame=pd.DataFrame({
        "request_id":[0],
        "emission":[100.0],
        "completion":[np.nan],
        "C":[np.nan],
        "Q":[np.nan],
    })
    got=bs._pass_vector(
        frame,l_max=10.0,c_max=1.0,q_min=0.5,rho=0.99,
        horizons=np.array([0.0,50.0]),
    )
    assert got.tolist()==[1,1]


def test_pass_vector_detects_decided_failure():
    frame=pd.DataFrame({
        "request_id":[0],
        "emission":[0.0],
        "completion":[20.0],
        "C":[1.0],
        "Q":[1.0],
    })
    got=bs._pass_vector(
        frame,l_max=5.0,c_max=2.0,q_min=0.5,rho=0.95,
        horizons=np.array([0.0,10.0]),
    )
    assert got.tolist()==[1,0]


def test_bootstrap_joint_count_representation_is_reproducible():
    rng1=np.random.Generator(np.random.PCG64(bs.BOOT_SEED))
    rng2=np.random.Generator(np.random.PCG64(bs.BOOT_SEED))
    p=np.full(1000,0.001)
    a=rng1.multinomial(1000,p,size=3)
    b=rng2.multinomial(1000,p,size=3)
    assert np.array_equal(a,b)
    assert np.all(a.sum(axis=1)==1000)


def test_primary_method_set_unchanged():
    assert tuple(bs.PRIMARY_METHODS)==("M0","M1","M2","M3_FULL343")
