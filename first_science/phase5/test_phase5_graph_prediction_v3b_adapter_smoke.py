from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import run_phase5_graph_prediction_v3b_adapter_smoke as smoke
from m3_v4_dominant_mass_graph import _integer_minimax_allocations


HERE=Path(__file__).resolve().parent


def test_v3b_graph_adapter_smoke_is_engineering_only():
    cfg=json.loads((HERE/"config_phase5_seed_registry_v3.json").read_text())
    assert cfg["engineering_smoke"]["scientific_evidence"] is False
    assert "smoke" in smoke.DEFAULT_OUTPUT.parts
    assert "results" not in smoke.DEFAULT_OUTPUT.parts
    assert smoke.SMOKE_M3_BUDGET==28


def test_minimax_smoke_allocation_is_deterministic_and_complete():
    alpha=np.array([0.50,0.25,0.15,0.10],dtype=float)
    a=_integer_minimax_allocations(alpha,[8])
    b=_integer_minimax_allocations(alpha,[8])
    assert a.equals(b)
    assert int(a["n_trajectories"].sum())==8
    assert (a["n_trajectories"].astype(int)>=1).all()


def test_smoke_targets_real_v3b_cardinalities():
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b.json").read_text())
    assert cfg["methods"]["M2"]["joint_models"]==27
    assert cfg["methods"]["M3"]["retained_support_size"]==14
    assert cfg["methods"]["M3"]["graph_budget_per_physical_cell"]==1400
    assert cfg["global_prediction_freeze"]["must_enumerate_all_16_physical_cells"] is True
