from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import run_phase5_graph_prediction_v3b_fullsupport_adapter_smoke as smoke
from m3_v4_dominant_mass_graph import _integer_minimax_allocations

HERE=Path(__file__).resolve().parent


def test_fullsupport_smoke_is_non_scientific_and_new_namespace():
    s=json.loads((HERE/"config_phase5_seed_registry_v3b_fullsupport.json").read_text())
    assert s["engineering_smoke"]["scientific_evidence"] is False
    assert "smoke" in smoke.DEFAULT_OUTPUT.parts
    assert "results" not in smoke.DEFAULT_OUTPUT.parts
    assert smoke.SUPPORT_SIZE==343
    assert smoke.PRODUCTION_BUDGET==1400


def test_fullsupport_integer_allocation_requires_at_least_one_each():
    w=np.ones(343,dtype=float)/343.0
    out=_integer_minimax_allocations(w,[1400])
    assert len(out)==343
    assert int(out["n_trajectories"].sum())==1400
    assert (out["n_trajectories"].astype(int)>=1).all()


def test_fullsupport_smoke_includes_tail_sentinel():
    assert smoke.SENTINEL_RANKS==(1,2,3,14,343)
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b_fullsupport.json").read_text())
    assert cfg["methods"]["M3"]["primary_method_id"]=="M3_FULL343"
    assert cfg["methods"]["M3"]["full_support_truncation_bound"]==0.0
