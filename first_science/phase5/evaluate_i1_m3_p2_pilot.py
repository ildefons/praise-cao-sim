"""Independent P2 G_PAR white-box evaluation of the frozen I1-M3 pilot.

The primary sigma comparison uses the SAME public-I1-induced region on both
sides. Secondary region discrepancy uses an independently fitted WB graph
rho-region with the already-existing Phase-2 extractor. This latter is a
diagnostic comparison of different region constructions, NOT an M3 fitted
graph region and NOT a claim that M0 public algebra should equal WB quantiles.

Run:
  python evaluate_i1_m3_p2_pilot.py --dry-run
  python evaluate_i1_m3_p2_pilot.py --run --workers 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

import run_phase5_graph_prediction_v3b_fullsupport as m3
from phase5_runtime_v2 import load_phase5_contracts, graph_record, sha256_file
from run_phase5_step0_v2 import _hidden_surrogates
from i1_m3_graph_region_pilot import graph_rho_regions
from m0_analytic_composition import AdmissibilityBoundary
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve

HERE = Path(__file__).resolve().parent
ROOT = HERE/"results"/"i1_m3_p2_induced_pilot"/"P2__G_PAR"
REF = ROOT/"whitebox_evaluation"
PRED = ROOT/"m3_predictions_full343_and_nested.csv"
QUERIES = ROOT/"public_induced_queries.csv"
MANIFEST = ROOT/"prediction_manifest.json"
SEED_BASE = 10_000_000
N_WB = 1000
HORIZONS = [float(h) for h in range(0,241,5)]


def _wb_one(seed: int) -> pd.DataFrame:
    from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory
    contracts=load_phase5_contracts(HERE)
    family=contracts.battery["provider_family"]
    inv=dict(contracts.battery["graph_invariants"])
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    graph=graph_record(contracts,"G_PAR")
    one,_=execute_one_phase5_graph_trajectory(
        graph_id="G_PAR",graph_ast=graph["ast"],
        provider_surrogates=_hidden_surrogates(contracts,"P2"),
        graph_invariants=inv,
        workload_period=float(contracts.battery["workload"]["period_seconds"]),
        stop_time=float(contracts.battery["horizon"]["maximum_seconds"]),
        trajectory_seed=int(seed),
        canonical_ipt=float(family["effective_IPT"]),
        execution_fraction=float(family["execution_fraction_x"]),
    )
    one.insert(0,"trajectory",seed-SEED_BASE)
    one.insert(1,"trajectory_seed",seed)
    return one


def _assert_prediction_frozen():
    if not MANIFEST.is_file():
        raise FileNotFoundError("M3 prediction must be frozen before WB execution")
    m=json.loads(MANIFEST.read_text())
    if m.get("status")!="FROZEN_P2_I1_M3_INDUCED_GRAPH_PREDICTION" or m.get("whitebox_read") is not False:
        raise RuntimeError("invalid prediction freeze")
    for label,filename in (
        ("queries",QUERIES),("predictions",PRED),
    ):
        if m["files"][label]!=sha256_file(filename):
            raise RuntimeError(f"{label} changed after prediction freeze")
    q=pd.read_csv(QUERIES)
    p=pd.read_csv(PRED)
    z=p[p["method_id"]=="M3_FULL343"]
    if len(q)!=5 or len(z)!=5*49:
        raise RuntimeError("expected 5 query regions x 49 horizons")
    return q,z


def _ledger(workers:int)->pd.DataFrame:
    REF.mkdir(parents=True,exist_ok=True)
    path=REF/"wb_request_ledger.csv"
    seeds=list(range(SEED_BASE,SEED_BASE+N_WB))
    if path.is_file():
        frame=pd.read_csv(path)
        if sorted(frame.trajectory_seed.astype(int).unique())!=seeds:
            raise RuntimeError("WB ledger seed provenance mismatch")
        return frame
    cp=REF/"checkpoints"
    cp.mkdir(exist_ok=True)
    missing=[seed for seed in seeds if not (cp/f"{seed}.csv").exists()]
    if workers==1:
        for i,seed in enumerate(missing,1):
            _wb_one(seed).to_csv(cp/f"{seed}.csv",index=False)
            if i%100==0:print(f"WB trajectories {i}/{len(missing)}",flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            future_map={pool.submit(_wb_one,seed):seed for seed in missing}
            for i,future in enumerate(as_completed(future_map),1):
                seed=future_map[future]
                future.result().to_csv(cp/f"{seed}.csv",index=False)
                if i%100==0:print(f"WB trajectories {i}/{len(missing)}",flush=True)
    pieces=[pd.read_csv(cp/f"{seed}.csv") for seed in seeds]
    frame=pd.concat(pieces,ignore_index=True)
    if frame[["trajectory","request_id"]].duplicated().any():
        raise RuntimeError("duplicate WB requests")
    frame.to_csv(path,index=False)
    return frame


def evaluate(q:pd.DataFrame,p:pd.DataFrame,wb:pd.DataFrame):
    rows=[]
    for query in q.itertuples(index=False):
        b=AdmissibilityBoundary(
            l_max=float(query.A_G_l_max),
            c_max=float(query.A_G_c_max),
            q_min=float(query.A_G_q_min),
        )
        curve=build_empirical_graph_sigma_curve(
            wb,boundary=b,rho_global=float(query.rho),
            horizons=HORIZONS,stop_time=240.0,accounting_origin=0.0,
            output_column="sigma_wb",
        )
        curve["query_id"]=query.query_id
        rows.append(curve.rename(columns={"horizon":"H"}))
    wbcurves=pd.concat(rows,ignore_index=True)
    pred=p[["query_id","H","sigma_hat"]]
    joined=pred.merge(wbcurves,on=["query_id","H"],how="inner",validate="one_to_one")
    if len(joined)!=5*49:
        raise RuntimeError("WB/prediction point mismatch")
    joined["error"]=joined.sigma_hat-joined.sigma_wb
    primary=joined[joined.H>=60]
    scores=primary.groupby("query_id").agg(
        mae=("error",lambda x:float(np.mean(np.abs(x)))),
        rmse=("error",lambda x:float(np.sqrt(np.mean(np.square(x))))),
        bias=("error","mean"),
        sigma_wb_mean=("sigma_wb","mean"),
        sigma_hat_mean=("sigma_hat","mean"),
    ).reset_index()
    overall=pd.DataFrame([{
        "mae":float(np.abs(primary.error).mean()),
        "rmse":float(np.sqrt(np.square(primary.error).mean())),
        "bias":float(primary.error.mean()),
        "n_points":len(primary),
    }])
    return joined,scores,overall


def main():
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run",action="store_true")
    group.add_argument("--run",action="store_true")
    ap.add_argument("--workers",type=int,default=1)
    args=ap.parse_args()
    if args.workers<1:raise ValueError("workers must be positive")
    q,p=_assert_prediction_frozen()
    if args.dry_run:
        print("P2_G_PAR_WB_PREFLIGHT_PASS")
        print("queries=5 horizons=49 prediction_points=245 wb_trajectories=1000")
        print("independent WB seeds 10000000..10000999")
        return
    wb=_ledger(args.workers)
    joined,scores,overall=evaluate(q,p,wb)
    # Distinct exploratory graph-region diagnostic, using the Phase-2 rule
    # and white-box top-level completed requests (no leakage into M3).
    rho=q.rho.astype(float).tolist()
    regions,audit=graph_rho_regions(
        wb,rho,model_samples=100_000,random_state=271828,
    )
    geom=q.merge(regions,left_on="rho",right_on="region_rho",validate="one_to_one")
    for dimension,pred,truth in (
        ("latency","A_G_l_max","l_max"),("cost","A_G_c_max","c_max")
    ):
        geom[f"{dimension}_relative_error"]=(geom[pred]-geom[truth])/geom[truth]
        geom[f"{dimension}_absolute_error"]=(geom[pred]-geom[truth]).abs()
    # Origin-anchored boxes: intersection/union area is geometric, not a
    # measure of probability mass or a joint SLA accuracy metric.
    geom["region_iou_lc"]=(
        np.minimum(geom.A_G_l_max,geom.l_max)
        *np.minimum(geom.A_G_c_max,geom.c_max)
        /(
            geom.A_G_l_max*geom.A_G_c_max+
            geom.l_max*geom.c_max-
            np.minimum(geom.A_G_l_max,geom.l_max)
            *np.minimum(geom.A_G_c_max,geom.c_max)
        )
    )
    # Quality is constant for this benchmark.
    for name,frame in [
        ("wb_survival_on_public_region.csv",joined),
        ("sigma_error_by_rho.csv",scores),
        ("sigma_error_overall.csv",overall),
        ("graph_region_comparison.csv",geom),
        ("graph_region_wb_extraction_audit.csv",audit),
    ]:
        frame.to_csv(REF/name,index=False)
    manifest={
        "status":"P2_G_PAR_I1_M3_WB_EVALUATION_COMPLETE",
        "prediction_manifest_sha256":sha256_file(MANIFEST),
        "wb_seeds":[SEED_BASE,SEED_BASE+N_WB-1],
        "wb_ledger_sha256":sha256_file(REF/"wb_request_ledger.csv"),
        "interpretation":"Primary sigma error on identical public-I1-induced A_G. Secondary comparison of public induced A_G versus independent WB graph rho-quantile region; these are different constructions.",
        "output_sha256":{f:sha256_file(REF/f) for f in [
            "wb_survival_on_public_region.csv","sigma_error_by_rho.csv",
            "sigma_error_overall.csv","graph_region_comparison.csv",
            "graph_region_wb_extraction_audit.csv",
        ]},
    }
    (REF/"evaluation_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("P2_G_PAR_I1_M3_WB_EVALUATION_COMPLETE")
    print("SURVIVAL ERROR (H>=60):")
    print(overall.to_string(index=False))
    print("BY RHO:")
    print(scores.to_string(index=False))
    print("REGION COMPARISON:")
    print(geom[["rho","latency_relative_error","cost_relative_error","region_iou_lc"]].to_string(index=False))


if __name__=="__main__":
    main()
