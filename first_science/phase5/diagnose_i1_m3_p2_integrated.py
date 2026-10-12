"""Read-only integrated diagnostic of frozen P2 G_PAR I1-M3 and WB evidence.

No simulations, no optimizer, no modifications to method or frozen outputs.
Outputs are exploratory/post-hoc diagnostics, not prospective validation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_graph_prediction_v3b_fullsupport as m3
from phase5_runtime_v2 import sha256_file
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve
from m0_analytic_composition import AdmissibilityBoundary
from evaluate_i1_m3_p2_pilot import ROOT, REF, QUERIES, PRED, MANIFEST, _assert_prediction_frozen

OUTPUT = ROOT / "integrated_diagnostic"
HORIZONS = [float(h) for h in range(0, 241, 5)]
KEYS = ["query_id", "H"]


def compute(queries: pd.DataFrame, wb: pd.DataFrame, members: pd.DataFrame):
    rho_vals = sorted(queries.rho.astype(float).unique().tolist())
    if len(rho_vals) != 5:
        raise RuntimeError("expected five region and compliance rho values")
    if sorted(members.joint_rank.astype(int).unique().tolist()) != list(range(1, 344)):
        raise RuntimeError("incomplete 343-member support")
    rows = []
    member_rows = []
    # Read each expensive native graph ledger exactly once.
    member_ledgers = {}
    for rank in range(1, 344):
        source = ROOT / "ledgers" / f"M3_R{rank:03d}.csv"
        if not source.is_file():
            raise FileNotFoundError(source)
        member_ledgers[rank] = pd.read_csv(source)
    for query in queries.itertuples(index=False):
        region_rho = float(query.rho)
        boundary = AdmissibilityBoundary(
            l_max=float(query.A_G_l_max), c_max=float(query.A_G_c_max),
            q_min=float(query.A_G_q_min),
        )
        for query_rho in rho_vals:
            query_id = f"{query.query_id}__threshold_{query_rho:.9f}"
            wb_curve = build_empirical_graph_sigma_curve(
                wb, boundary=boundary, rho_global=query_rho,
                horizons=HORIZONS, stop_time=240.0, accounting_origin=0.0,
                output_column="sigma_wb",
            )
            wb_curve = wb_curve.rename(columns={"horizon":"H"})
            wb_curve["query_id"] = query_id
            wb_curve["rho_region"] = region_rho
            wb_curve["rho_query"] = query_rho
            rows.append(wb_curve)

            # All member ledgers use their original frozen seed allocations.
            for rank in range(1, 344):
                ledger = member_ledgers[rank]
                curve = build_empirical_graph_sigma_curve(
                    ledger, boundary=boundary, rho_global=query_rho,
                    horizons=HORIZONS, stop_time=240.0, accounting_origin=0.0,
                    output_column="sigma_member",
                )
                curve["query_id"] = query_id
                curve["rho_region"] = region_rho
                curve["rho_query"] = query_rho
                curve["joint_rank"] = rank
                member_rows.append(curve.rename(columns={"horizon":"H"}))
    wbc = pd.concat(rows, ignore_index=True)
    mc = pd.concat(member_rows, ignore_index=True)
    weights = (
        members[["joint_rank","joint_weight","graph_n"]]
        .drop_duplicates("joint_rank").sort_values("joint_rank")
    )
    if len(weights) != 343 or not np.isclose(weights.joint_weight.sum(), 1.0):
        raise RuntimeError("invalid member weights")
    mc = mc.merge(weights, on="joint_rank", validate="many_to_one")
    group = ["query_id","rho_region","rho_query","H"]
    series = []
    for name, top in [("FULL343",343),("TOP1",1),("TOP3",3),("TOP14",14)]:
        t = mc.loc[mc.joint_rank<=top].copy()
        norm = float(weights.loc[weights.joint_rank<=top,"joint_weight"].sum())
        t["weighted"] = t.sigma_member*t.joint_weight/norm
        agg = t.groupby(group, as_index=False)["weighted"].sum()
        agg["method"] = name
        agg = agg.rename(columns={"weighted":"sigma_hat"})
        series.append(agg)
    preds = pd.concat(series, ignore_index=True)
    grid = preds.merge(wbc,on=group,validate="many_to_one")
    grid["error"] = grid.sigma_hat-grid.sigma_wb
    primary = grid.loc[grid.H>=60]
    errors = primary.groupby(["method","rho_region","rho_query"],as_index=False).agg(
        mae=("error",lambda x: float(np.abs(x).mean())),
        rmse=("error",lambda x: float(np.sqrt(np.mean(np.square(x))))),
        bias=("error","mean"), wb_mean=("sigma_wb","mean"),
        prediction_mean=("sigma_hat","mean"),
    )
    overall = primary.groupby("method",as_index=False).agg(
        mae=("error",lambda x:float(np.abs(x).mean())),
        rmse=("error",lambda x:float(np.sqrt(np.mean(np.square(x))))),
        bias=("error","mean"),
    )
    wb_small=wbc[group+["sigma_wb"]]
    member_compare=mc.merge(wb_small,on=group,validate="many_to_one")
    member_compare["squared_error"]=(member_compare.sigma_member-member_compare.sigma_wb)**2
    member_compare["absolute_error"]=(member_compare.sigma_member-member_compare.sigma_wb).abs()
    member_primary=member_compare.loc[member_compare.H>=60]
    member_scores=member_primary.groupby("joint_rank",as_index=False).agg(
        raw_rmse=("squared_error",lambda x:float(np.sqrt(x.mean()))),
        raw_mae=("absolute_error","mean"),
        joint_weight=("joint_weight","first"),
        graph_n=("graph_n","first"),
    ).sort_values("joint_rank")
    member_scores["warning"]="Individual low-N joint-model RMSE is high-noise; best member is posthoc oracle, not validated selection"
    mc_var = mc.copy()
    mc_var["term"] = mc_var.joint_weight**2*mc_var.sigma_member*(1-mc_var.sigma_member)/mc_var.graph_n
    uncertainty=mc_var.groupby(group,as_index=False)["term"].sum().rename(columns={"term":"mc_var_plugin"})
    uncertainty["mc_se_plugin"]=np.sqrt(uncertainty.mc_var_plugin)
    uncertainty["mc_se_conservative"]=np.sqrt(float(np.sum(
        weights.joint_weight.to_numpy()**2 / (4*weights.graph_n.to_numpy())
    )))
    return grid,errors,overall,member_scores,uncertainty


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",action="store_true")
    args=ap.parse_args()
    q,p=_assert_prediction_frozen()
    evaluation_manifest=REF/"evaluation_manifest.json"
    if not evaluation_manifest.is_file():
        raise FileNotFoundError("run independent WB evaluation first")
    wbpath=REF/"wb_request_ledger.csv"
    if sha256_file(wbpath)!=json.loads(evaluation_manifest.read_text())["wb_ledger_sha256"]:
        raise RuntimeError("white-box reference ledger hash changed")
    members_path=ROOT/"m3_member_curves.csv"
    members=pd.read_csv(members_path)
    if not args.run:
        print("P2_M3_INTEGRATED_DIAGNOSTIC_PREFLIGHT_PASS")
        print("25 rho combinations, 343 models; pure ledger rescore")
        return
    wb=pd.read_csv(wbpath)
    grid,errors,overall,member_scores,uncertainty=compute(q,wb,members)
    # Independently recover the prior diagonal result, against frozen predictions.
    diagonal=grid.loc[
        (grid.method=="FULL343") &
        np.isclose(grid.rho_region,grid.rho_query)
    ]
    original=pd.read_csv(PRED)
    original=original.loc[original.method_id=="M3_FULL343",["H","rho","sigma_hat"]]
    merged=diagonal.merge(
        original,left_on=["H","rho_region"],right_on=["H","rho"],
        validate="one_to_one",
    )
    if len(merged)!=245 or not np.allclose(
        merged.sigma_hat_x,merged.sigma_hat_y,atol=1e-12,rtol=0
    ):
        raise RuntimeError("diagnostic does not reproduce frozen diagonal M3 predictions")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    files = {
        "rho_grid_curves.csv":grid,
        "rho_grid_errors.csv":errors,
        "method_overall_errors.csv":overall,
        "joint_member_diagnostic_errors.csv":member_scores,
        "mc_uncertainty.csv":uncertainty,
    }
    for filename,frame in files.items():
        frame.to_csv(OUTPUT/filename,index=False)
    manifest={
        "status":"EXPLORATORY_P2_G_PAR_M3_DIAGNOSTIC_COMPLETE",
        "posthoc_whitebox_used":True,
        "must_not_tune_frozen_M3":True,
        "prediction_manifest_sha256":sha256_file(MANIFEST),
        "evaluation_manifest_sha256":sha256_file(evaluation_manifest),
        "outputs_sha256":{name:sha256_file(OUTPUT/name) for name in files},
        "limitations":[
            "not an independent generalization test",
            "joint-model graph predictions often have N=1 or few trajectories",
            "local I1 fitting error and model misspecification not causally separated",
            "mc plugin SE omits reconstruction and across-query dependencies",
        ],
    }
    (OUTPUT/"diagnostic_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("P2_G_PAR_M3_INTEGRATED_DIAGNOSTIC_COMPLETE")
    print(overall.to_string(index=False))
    print("TOP WEIGHTED JOINT MEMBERS (posthoc RMSE, high MC noise):")
    print(member_scores.head(8).to_string(index=False))
    print("FROZEN DIAGONAL REPRODUCED 245/245")


if __name__=="__main__":
    main()
