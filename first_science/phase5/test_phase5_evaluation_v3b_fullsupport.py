from __future__ import annotations

import numpy as np
import pandas as pd

import run_phase5_evaluation_v3b_fullsupport as ev


def _tiny(method="M1"):
    return pd.DataFrame({
        "physical_cell_id":["P1__G_PAR"]*3,
        "query_id":["Q"]*3,
        "provider_world_id":["P1"]*3,
        "graph_id":["G_PAR"]*3,
        "rho_label":["R"]*3,
        "rho":[0.95]*3,
        "regime":["Mid"]*3,
        "H":[60.0,65.0,70.0],
        "method_id":[method]*3,
        "status":["PREDICTED"]*3,
        "sigma_hat":[0.8,0.9,1.0],
        "sigma_wb":[0.7,0.9,0.9],
        "wb_n":[1000]*3,
        "wb_successes":[700,900,900],
        "wb_ci_lower":[0.67,0.88,0.88],
        "wb_ci_upper":[0.73,0.92,0.92],
    })


def test_error_metric_sign_and_scale():
    m=ev._error_metrics(_tiny())
    assert m["n_points"]==3
    assert np.isclose(m["MAE"],(0.1+0.0+0.1)/3)
    assert np.isclose(m["signed_bias"],(0.1+0.0+0.1)/3)
    assert np.isclose(m["RMSE"],np.sqrt((0.01+0.0+0.01)/3))


def test_m0_not_applicable_is_not_scored():
    t=_tiny("M0")
    t.loc[0,"status"]="NOT_APPLICABLE"
    t.loc[0,"sigma_hat"]=np.nan
    m=ev._error_metrics(t)
    assert m["n_points"]==2


def test_decision_scoring_excludes_wb_crossing_points():
    t=_tiny("M1")
    out=ev._decision_table(t,[0.9])
    allrow=out[(out["scope"]=="ALL")&(out["scope_value"]=="ALL")].iloc[0]
    # At beta=.9: point1 certain reject, points2/3 Wilson interval crosses beta.
    assert int(allrow["wb_certain_point_count"])==1
    assert int(allrow["false_accept_count"])==0
    assert int(allrow["false_reject_count"])==0


def test_reference_noise_adjustment_formula_is_nonnegative():
    t=_tiny()
    m=ev._error_metrics(t)
    assert m["reference_noise_adjusted_RMSE"]>=0.0


def test_primary_method_set_and_fullsupport_role():
    assert ev.PRIMARY_METHODS==("M0","M1","M2","M3_FULL343")
    assert ev.M3_DIAGNOSTICS==("M3_TOP1","M3_TOP3","M3_TOP14")
