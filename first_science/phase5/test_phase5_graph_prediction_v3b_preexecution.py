from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import freeze_phase5_graph_prediction_v3b_preexecution as prep


HERE=Path(__file__).resolve().parent


def test_preexecution_points_only_to_v3b_prediction_namespace():
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b.json").read_text())
    assert cfg["outputs"]["root"]=="results/04_prediction_v3b"
    assert prep.DEFAULT_ROOT==HERE/"results"/"04_prediction_v3b"
    assert prep.PREP_DIRNAME=="_preexecution"


def test_integer_minimax_allocation_sums_to_frozen_budget():
    from m3_v4_dominant_mass_graph import _integer_minimax_allocations
    alpha=np.array([0.40,0.25,0.15,0.10,0.10],dtype=float)
    out=_integer_minimax_allocations(alpha,[1400])
    assert int(out["n_trajectories"].sum())==1400
    assert out["rank"].astype(int).tolist()==[1,2,3,4,5]
    assert (out["n_trajectories"].astype(int)>=1).all()


def test_final_whitebox_is_not_a_preexecution_input():
    source=Path(prep.__file__).read_text(encoding="utf-8")
    assert '"05_final_wb"' not in source
    assert "'05_final_wb'" not in source
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b.json").read_text())
    assert cfg["seeds"]["final_whitebox"]["may_be_opened_before_global_prediction_freeze"] is False
