from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_graph_prediction_v3b_fullsupport as run

HERE=Path(__file__).resolve().parent


def test_scientific_runner_targets_frozen_fullsupport_contract():
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b_fullsupport.json").read_text())
    assert run.SUPPORT_SIZE==343
    assert run.M2_SIZE==27
    assert cfg["methods"]["M3"]["primary_method_id"]=="M3_FULL343"
    assert run.ROOT==HERE/"results"/"04_prediction_v3b_fullsupport"


def test_m3_weighted_readout_full_support_has_zero_truncation():
    rows=[]
    for rank,(w,p,n) in enumerate(
        [(0.5,0.2,10),(0.3,0.5,6),(0.2,0.9,4)],start=1
    ):
        rows.append({
            "query_id":"Q","provider_world_id":"P1","graph_id":"G_PAR",
            "rho_label":"R","rho":0.95,"regime":"Easy","H":60.0,
            "method_id":"M3_MEMBER","joint_rank":rank,"joint_weight":w,
            "graph_n":n,"sigma_member":p,
        })
    # Pad to the runner's exact support size with zero-weight synthetic members.
    for rank in range(4,344):
        rows.append({
            "query_id":"Q","provider_world_id":"P1","graph_id":"G_PAR",
            "rho_label":"R","rho":0.95,"regime":"Easy","H":60.0,
            "method_id":"M3_MEMBER","joint_rank":rank,"joint_weight":0.0,
            "graph_n":1,"sigma_member":0.0,
        })
    out=run._m3_predictions(pd.DataFrame(rows))
    full=out[out["method_id"]=="M3_FULL343"].iloc[0]
    assert np.isclose(float(full["sigma_hat"]),0.43)
    assert np.isclose(float(full["retained_mass"]),1.0)
    assert np.isclose(float(full["truncation_bound"]),0.0)
    assert int(full["support_size"])==343


def test_runner_source_has_no_final_wb_namespace_dependency():
    source=Path(run.__file__).read_text(encoding="utf-8")
    assert '"05_final_wb"' not in source
    assert "'05_final_wb'" not in source
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b_fullsupport.json").read_text())
    assert cfg["seeds"]["final_whitebox"]["may_be_opened_before_global_prediction_freeze"] is False


def test_expected_per_cell_scientific_trajectory_total():
    assert 100 + 27*100 + 1400 == 4200
