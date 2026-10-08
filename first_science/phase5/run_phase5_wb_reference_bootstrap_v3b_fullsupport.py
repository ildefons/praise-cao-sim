"""Registered finite-reference bootstrap for Phase-5 V3b FULL343.

The deterministic evaluation is already frozen. This stage keeps every method
prediction fixed and resamples only the untouched N=1000 final-WB trajectory
index. Because the same WB seed index is reused across eligible physical cells
as CRN, one bootstrap multiplicity vector is applied jointly to all 12 cells in
each replicate.

The implementation first reconstructs the exact trajectory-level binary SLA
outcome matrix for the primary H=60..240 window and verifies that its column
means reproduce the frozen sigma_wb values exactly. It then performs the
registered 10,000-replicate percentile bootstrap.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase5_runtime_v2 import git_head, read_json, sha256_file, utc_now_iso, write_json
from run_phase5_evaluation_v3b_fullsupport import PRIMARY_METHODS, SCOPE_COLUMNS

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_wb_reference_bootstrap_v3b_fullsupport.json"
EVAL_CFG=HERE/"config_phase5_evaluation_v3b_fullsupport.json"
EVAL_ROOT=HERE/"results"/"06_evaluation_v3b_fullsupport"
EVAL_MANIFEST=EVAL_ROOT/"phase5_v3b_fullsupport_deterministic_evaluation_manifest.json"
PRED_ROOT=HERE/"results"/"04_prediction_v3b_fullsupport"
WB_ROOT=HERE/"results"/"05_final_wb_v3b_fullsupport"
WB_FREEZE=WB_ROOT/"phase5_v3b_fullsupport_final_wb_freeze_manifest.json"
WB_AUDIT=WB_ROOT/"phase5_v3b_fullsupport_final_wb_mechanical_audit_manifest.json"
ROOT=EVAL_ROOT/"bootstrap_reference"

EXPECTED_CFG="FROZEN_PHASE5_V3B_FULLSUPPORT_WB_REFERENCE_BOOTSTRAP"
EXPECTED_EVAL="FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION"
EXPECTED_WB="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY"
EXPECTED_AUDIT="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_MECHANICAL_AUDIT_PASS"
FROZEN_STATUS="FROZEN_PHASE5_V3B_FULLSUPPORT_WB_REFERENCE_BOOTSTRAP_COMPLETE"

REPS=10000
BOOT_SEED=2026100201
N=1000
PRIMARY_H=np.arange(60.0,240.0+0.5,5.0,dtype=float)
METRICS=(
    "MAE",
    "RMSE",
    "signed_bias",
    "max_abs_error",
    "reference_noise_adjusted_RMSE",
)
TOL=1e-12


def _preflight()->tuple[dict,dict,list[str]]:
    cfg=read_json(CFG)
    ev=read_json(EVAL_MANIFEST)
    wb=read_json(WB_FREEZE)
    audit=read_json(WB_AUDIT)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("WB-reference bootstrap implementation is not frozen")
    if int(cfg["bootstrap"]["reps"])!=REPS or int(cfg["bootstrap"]["seed"])!=BOOT_SEED:
        raise RuntimeError("registered bootstrap reps/seed changed")
    if ev.get("status")!=EXPECTED_EVAL:
        raise RuntimeError("deterministic evaluation is not frozen")
    if ev.get("bootstrap_reference_uncertainty_status")!="PENDING_SEPARATE_FROZEN_STAGE":
        raise RuntimeError("deterministic evaluation bootstrap status changed")
    if wb.get("status")!=EXPECTED_WB or wb.get("complete") is not True:
        raise RuntimeError("final-WB battery is not frozen")
    if audit.get("status")!=EXPECTED_AUDIT:
        raise RuntimeError("final-WB mechanical audit has not passed")
    cells=sorted(map(str,wb["eligible_final_wb_cells"]))
    if len(cells)!=12:
        raise RuntimeError("bootstrap expects 12 eligible WB cells")
    return cfg,ev,cells


def _pass_vector(
    frame:pd.DataFrame,
    *,
    l_max:float,
    c_max:float,
    q_min:float,
    rho:float,
    horizons:np.ndarray,
)->np.ndarray:
    ordered=frame.sort_values(["emission","request_id"],kind="mergesort")
    emission=ordered["emission"].astype(float).to_numpy()
    completion=pd.to_numeric(ordered["completion"],errors="coerce").to_numpy(dtype=float)
    cost=pd.to_numeric(ordered["C"],errors="coerce").to_numpy(dtype=float)
    quality=pd.to_numeric(ordered["Q"],errors="coerce").to_numpy(dtype=float)

    finite=np.isfinite(completion)
    deadline=emission+float(l_max)
    in_time=finite&(completion<=deadline+TOL)
    decision_time=np.where(in_time,completion,deadline)
    decided=np.searchsorted(
        np.sort(decision_time),
        horizons+TOL,
        side="right",
    ).astype(np.int32)

    eligible=(
        in_time
        & np.isfinite(cost)
        & np.isfinite(quality)
        & (cost<=float(c_max)+TOL)
        & (quality>=float(q_min)-TOL)
    )
    compliant=np.searchsorted(
        np.sort(completion[eligible]),
        horizons+TOL,
        side="right",
    ).astype(np.int32)

    fraction=np.ones(len(horizons),dtype=float)
    nonzero=decided>0
    fraction[nonzero]=(
        compliant[nonzero].astype(float)/decided[nonzero].astype(float)
    )
    return (fraction+TOL>=float(rho)).astype(np.uint8)


def _cell_outcomes(cell:str)->tuple[pd.DataFrame,np.ndarray]:
    ledger_path=WB_ROOT/cell/"final_wb_ledger.csv"
    curves_path=WB_ROOT/cell/"final_wb_curves.csv"
    ledger=pd.read_csv(ledger_path)
    curves=pd.read_csv(curves_path)
    curves=curves[curves["H"].astype(float).isin(PRIMARY_H)].copy()
    curves=curves.sort_values(["query_id","H"],kind="mergesort").reset_index(drop=True)
    if len(curves)!=15*37:
        raise RuntimeError(f"{cell}: primary WB curve rows !=555")

    qcols=[
        "query_id","provider_world_id","graph_id","rho_label","rho","regime",
        "A_G_l_max","A_G_c_max","A_G_q_min",
    ]
    qdefs=(
        curves[qcols].drop_duplicates()
        .sort_values("query_id",kind="mergesort").reset_index(drop=True)
    )
    if len(qdefs)!=15:
        raise RuntimeError(f"{cell}: WB query definitions !=15")

    seeds=sorted(ledger["trajectory_seed"].astype(int).unique().tolist())
    if seeds!=list(range(54000,55000)):
        raise RuntimeError(f"{cell}: WB seed identity changed")
    matrix=np.empty((N,len(curves)),dtype=np.uint8)
    groups={int(seed):g for seed,g in ledger.groupby("trajectory_seed",sort=True)}
    for row,seed in enumerate(range(54000,55000)):
        frame=groups.get(seed)
        if frame is None:
            raise RuntimeError(f"{cell}: missing WB seed {seed}")
        offset=0
        for q in qdefs.itertuples(index=False):
            v=_pass_vector(
                frame,
                l_max=float(q.A_G_l_max),
                c_max=float(q.A_G_c_max),
                q_min=float(q.A_G_q_min),
                rho=float(q.rho),
                horizons=PRIMARY_H,
            )
            matrix[row,offset:offset+len(PRIMARY_H)]=v
            offset+=len(PRIMARY_H)
        if offset!=len(curves):
            raise RuntimeError(f"{cell}: outcome column accounting mismatch")

    empirical=matrix.mean(axis=0)
    frozen=curves["sigma_wb"].astype(float).to_numpy()
    if not np.allclose(empirical,frozen,atol=TOL,rtol=0.0):
        worst=float(np.max(np.abs(empirical-frozen)))
        raise RuntimeError(f"{cell}: reconstructed trajectory outcomes do not reproduce frozen WB sigma; max={worst}")

    meta=curves[
        ["query_id","provider_world_id","graph_id","rho_label","rho","regime","H","sigma_wb"]
    ].copy()
    meta.insert(0,"physical_cell_id",cell)
    return meta,matrix


def _build_or_load_outcomes(
    cells:list[str],
    *,
    rebuild:bool,
)->tuple[pd.DataFrame,np.ndarray]:
    ROOT.mkdir(parents=True,exist_ok=True)
    meta_path=ROOT/"wb_primary_outcome_columns.csv"
    npz_path=ROOT/"wb_primary_trajectory_outcomes.npz"
    if not rebuild and meta_path.is_file() and npz_path.is_file():
        meta=pd.read_csv(meta_path)
        with np.load(npz_path) as z:
            matrix=z["outcomes"]
        if matrix.shape!=(1000,12*15*37):
            raise RuntimeError("cached WB outcome matrix has wrong shape")
        if len(meta)!=matrix.shape[1]:
            raise RuntimeError("cached WB outcome metadata length mismatch")
        if matrix.dtype!=np.uint8:
            matrix=matrix.astype(np.uint8)
        if not set(np.unique(matrix)).issubset({0,1}):
            raise RuntimeError("cached WB outcomes are not binary")
        return meta,matrix

    metas=[]; matrices=[]
    started=time.perf_counter()
    for i,cell in enumerate(cells,1):
        meta,matrix=_cell_outcomes(cell)
        metas.append(meta); matrices.append(matrix)
        print(
            f"WB OUTCOME MATRIX {i}/12 {cell} | "
            f"elapsed={(time.perf_counter()-started)/60:.1f} min",
            flush=True,
        )
    meta=pd.concat(metas,ignore_index=True)
    matrix=np.concatenate(matrices,axis=1)
    meta.insert(0,"point_index",np.arange(len(meta),dtype=int))
    if matrix.shape!=(1000,6660):
        raise RuntimeError(f"combined WB outcome matrix shape {matrix.shape} != (1000,6660)")
    meta.to_csv(meta_path,index=False)
    np.savez_compressed(npz_path,outcomes=matrix)
    return meta,matrix


def _predictions(meta:pd.DataFrame)->dict[str,dict[str,Any]]:
    joined=pd.read_csv(EVAL_ROOT/"pointwise_primary_joined.csv")
    key=["physical_cell_id","query_id","H"]
    if len(meta)!=6660 or meta.duplicated(key).any():
        raise RuntimeError("bootstrap point metadata key invalid")
    out={}
    for method in PRIMARY_METHODS:
        p=joined[joined["method_id"].astype(str)==method].copy()
        cols=key+["sigma_hat","status"]
        if p.duplicated(key).any():
            raise RuntimeError(f"{method}: deterministic pointwise rows duplicate bootstrap key")
        a=meta[key].merge(p[cols],on=key,how="left",validate="one_to_one")
        if len(a)!=len(meta):
            raise RuntimeError(f"{method}: bootstrap prediction alignment changed row count")
        pred=pd.to_numeric(a["sigma_hat"],errors="coerce").to_numpy(dtype=float)
        status=a["status"].astype(str).to_numpy()
        valid=(status=="PREDICTED")&np.isfinite(pred)
        if method!="M0" and not bool(valid.all()):
            raise RuntimeError(f"{method}: non-M0 primary predictions are incomplete")
        out[method]={"pred":pred,"valid":valid}
    return out


def _scope_groups(meta:pd.DataFrame)->list[tuple[str,str,np.ndarray]]:
    rows=[]
    for scope,cols in SCOPE_COLUMNS.items():
        if not cols:
            rows.append((scope,"ALL",np.arange(len(meta),dtype=int)))
            continue
        grouper=cols[0] if len(cols)==1 else list(cols)
        for key,g in meta.groupby(grouper,sort=True,dropna=False):
            if len(cols)==1:
                key=(key,)
            value="|".join(f"{c}={v}" for c,v in zip(cols,key))
            rows.append((scope,value,g.index.to_numpy(dtype=int)))
    return rows


def _definitions(meta:pd.DataFrame,pred:dict[str,dict[str,Any]]):
    groups=_scope_groups(meta)
    defs=[]
    for method in PRIMARY_METHODS:
        valid=pred[method]["valid"]
        for scope,value,base_idx in groups:
            idx=base_idx[valid[base_idx]]
            defs.append({
                "method_id":method,
                "scope":scope,
                "scope_value":value,
                "idx":idx,
                "pred":pred[method]["pred"],
            })
    return defs


def _compute_bootstrap(
    outcomes:np.ndarray,
    defs:list[dict[str,Any]],
    *,
    reps:int,
    seed:int,
    batch_size:int,
)->np.ndarray:
    y=outcomes.astype(np.float32,copy=False)
    rng=np.random.Generator(np.random.PCG64(int(seed)))
    probabilities=np.full(N,1.0/N,dtype=float)
    boot=np.full((reps,len(defs),len(METRICS)),np.nan,dtype=np.float32)
    started=time.perf_counter()

    for start in range(0,reps,batch_size):
        stop=min(reps,start+batch_size)
        b=stop-start
        counts=rng.multinomial(N,probabilities,size=b).astype(np.float32,copy=False)
        sigma=(counts@y)/float(N)
        for di,d in enumerate(defs):
            idx=d["idx"]
            if len(idx)==0:
                continue
            truth=sigma[:,idx]
            fixed=d["pred"][idx].astype(np.float32,copy=False)[None,:]
            err=fixed-truth
            abs_err=np.abs(err)
            mse=np.mean(err*err,axis=1,dtype=np.float64)
            boot[start:stop,di,0]=np.mean(abs_err,axis=1,dtype=np.float64)
            boot[start:stop,di,1]=np.sqrt(mse)
            boot[start:stop,di,2]=np.mean(err,axis=1,dtype=np.float64)
            boot[start:stop,di,3]=np.max(abs_err,axis=1)
            noise=np.mean(
                truth*(1.0-truth)/float(N_WB_MINUS_ONE),
                axis=1,dtype=np.float64,
            )
            boot[start:stop,di,4]=np.sqrt(np.maximum(0.0,mse-noise))
        if stop==reps or stop%500==0:
            elapsed=time.perf_counter()-started
            rate=stop/max(elapsed,1e-9)
            eta=(reps-stop)/max(rate,1e-9)
            print(
                f"WB REFERENCE BOOTSTRAP {stop}/{reps} | "
                f"elapsed={elapsed/60:.1f} min | ETA={eta/60:.1f} min",
                flush=True,
            )
    return boot


N_WB_MINUS_ONE=N-1


def _interval_table(
    defs:list[dict[str,Any]],
    boot:np.ndarray,
)->pd.DataFrame:
    det=pd.read_csv(EVAL_ROOT/"primary_metrics.csv")
    lookup={
        (str(r.method_id),str(r.scope),str(r.scope_value)):r
        for r in det.itertuples(index=False)
    }
    rows=[]
    for di,d in enumerate(defs):
        key=(d["method_id"],d["scope"],d["scope_value"])
        if key not in lookup:
            raise RuntimeError(f"deterministic metric row missing {key}")
        r=lookup[key]
        for mi,metric in enumerate(METRICS):
            values=boot[:,di,mi].astype(float)
            finite=values[np.isfinite(values)]
            estimate=float(getattr(r,metric))
            if len(finite)==0:
                lo=hi=np.nan
            else:
                lo,hi=(float(x) for x in np.percentile(finite,[2.5,97.5]))
            rows.append({
                "method_id":d["method_id"],
                "scope":d["scope"],
                "scope_value":d["scope_value"],
                "metric":metric,
                "deterministic_estimate":estimate,
                "bootstrap_lower_95":lo,
                "bootstrap_upper_95":hi,
                "bootstrap_reps_finite":int(len(finite)),
            })
    return pd.DataFrame(rows).sort_values(
        ["method_id","scope","scope_value","metric"],kind="mergesort"
    ).reset_index(drop=True)


def _all_replicates(defs,boot)->pd.DataFrame:
    cols={"bootstrap_rep":np.arange(1,boot.shape[0]+1,dtype=int)}
    for di,d in enumerate(defs):
        if d["scope"]!="ALL" or d["scope_value"]!="ALL":
            continue
        for mi,metric in enumerate(METRICS):
            cols[f"{d['method_id']}__{metric}"]=boot[:,di,mi]
    return pd.DataFrame(cols)


def _topology_intervals(defs,boot)->pd.DataFrame:
    index={
        (d["method_id"],d["scope"],d["scope_value"]):i
        for i,d in enumerate(defs)
    }
    det=pd.read_csv(EVAL_ROOT/"topology_contrasts.csv")
    rows=[]
    for method in PRIMARY_METHODS:
        for world in ("P1","P3","P4"):
            kp=(method,"provider_world_x_graph",f"provider_world_id={world}|graph_id=G_PAR")
            ks=(method,"provider_world_x_graph",f"provider_world_id={world}|graph_id=G_SEQ")
            ip=index[kp]; iseq=index[ks]
            par=boot[:,ip,0].astype(float)
            seq=boot[:,iseq,0].astype(float)
            delta=seq-par
            finite=delta[np.isfinite(delta)]
            drow=det[
                (det["method_id"].astype(str)==method)
                & (det["contrast"].astype(str)=="Delta_P")
                & (det["provider_world_id"].astype(str)==world)
            ]
            deterministic=(
                float(drow.iloc[0]["Delta_SEQ_minus_PAR"])
                if len(drow)==1 and pd.notna(drow.iloc[0]["Delta_SEQ_minus_PAR"])
                else np.nan
            )
            if len(finite):
                lo,hi=(float(x) for x in np.percentile(finite,[2.5,97.5]))
                prob=float(np.mean(finite>0.0))
                status="ESTIMABLE"
            else:
                lo=hi=prob=np.nan
                status="NOT_ESTIMABLE"
            rows.append({
                "method_id":method,
                "provider_world_id":world,
                "contrast":"Delta_P",
                "status":status,
                "deterministic_estimate":deterministic,
                "bootstrap_lower_95":lo,
                "bootstrap_upper_95":hi,
                "bootstrap_probability_Delta_gt_0":prob,
                "bootstrap_reps_finite":int(len(finite)),
            })
        rows.append({
            "method_id":method,
            "provider_world_id":"P2+P4_vs_P1+P3",
            "contrast":"Delta_het",
            "status":"NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE",
            "deterministic_estimate":np.nan,
            "bootstrap_lower_95":np.nan,
            "bootstrap_upper_95":np.nan,
            "bootstrap_probability_Delta_gt_0":np.nan,
            "bootstrap_reps_finite":0,
        })
    return pd.DataFrame(rows)


def _input_hashes(cells:list[str])->pd.DataFrame:
    rows=[
        {"input_kind":"evaluation_contract","path":str(EVAL_CFG),"sha256":sha256_file(EVAL_CFG)},
        {"input_kind":"bootstrap_contract","path":str(CFG),"sha256":sha256_file(CFG)},
        {"input_kind":"deterministic_evaluation_manifest","path":str(EVAL_MANIFEST),"sha256":sha256_file(EVAL_MANIFEST)},
        {"input_kind":"final_wb_freeze","path":str(WB_FREEZE),"sha256":sha256_file(WB_FREEZE)},
        {"input_kind":"final_wb_audit","path":str(WB_AUDIT),"sha256":sha256_file(WB_AUDIT)},
        {"input_kind":"pointwise_primary","path":str(EVAL_ROOT/"pointwise_primary_joined.csv"),"sha256":sha256_file(EVAL_ROOT/"pointwise_primary_joined.csv")},
        {"input_kind":"primary_metrics","path":str(EVAL_ROOT/"primary_metrics.csv"),"sha256":sha256_file(EVAL_ROOT/"primary_metrics.csv")},
    ]
    for cell in cells:
        for kind,path in (
            ("wb_ledger",WB_ROOT/cell/"final_wb_ledger.csv"),
            ("wb_curves",WB_ROOT/cell/"final_wb_curves.csv"),
        ):
            rows.append({
                "input_kind":kind,
                "physical_cell_id":cell,
                "path":str(path),
                "sha256":sha256_file(path),
            })
    return pd.DataFrame(rows)


def run(*,rebuild_outcomes:bool,batch_size:int)->Path:
    if batch_size<1:
        raise ValueError("batch_size must be >=1")
    cfg,ev,cells=_preflight()
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/"phase5_v3b_fullsupport_wb_reference_bootstrap_manifest.json"
    if manifest_path.is_file():
        old=read_json(manifest_path)
        if old.get("status")==FROZEN_STATUS:
            raise RuntimeError(f"bootstrap already frozen at {manifest_path}")

    meta,outcomes=_build_or_load_outcomes(cells,rebuild=rebuild_outcomes)
    pred=_predictions(meta)
    defs=_definitions(meta,pred)
    boot=_compute_bootstrap(
        outcomes,defs,reps=REPS,seed=BOOT_SEED,batch_size=batch_size
    )

    intervals=_interval_table(defs,boot)
    allrep=_all_replicates(defs,boot)
    topology=_topology_intervals(defs,boot)
    hashes=_input_hashes(cells)

    outputs={
        "outcome_columns":ROOT/"wb_primary_outcome_columns.csv",
        "outcome_matrix":ROOT/"wb_primary_trajectory_outcomes.npz",
        "metric_intervals":ROOT/"bootstrap_metric_intervals.csv",
        "all_metric_replicates":ROOT/"bootstrap_all_metric_replicates.csv",
        "topology_intervals":ROOT/"bootstrap_topology_contrast_intervals.csv",
        "input_hashes":ROOT/"bootstrap_input_hashes.csv",
    }
    intervals.to_csv(outputs["metric_intervals"],index=False)
    allrep.to_csv(outputs["all_metric_replicates"],index=False)
    topology.to_csv(outputs["topology_intervals"],index=False)
    hashes.to_csv(outputs["input_hashes"],index=False)

    manifest={
        "status":FROZEN_STATUS,
        "stage_id":"WB_REFERENCE_BOOTSTRAP_V3B_FULLSUPPORT",
        "scientific_evidence":True,
        "bootstrap_contract_sha256":sha256_file(CFG),
        "deterministic_evaluation_manifest_sha256":sha256_file(EVAL_MANIFEST),
        "final_wb_freeze_sha256":sha256_file(WB_FREEZE),
        "final_wb_audit_sha256":sha256_file(WB_AUDIT),
        "code_commit":git_head(),
        "bootstrap_reps":REPS,
        "bootstrap_seed":BOOT_SEED,
        "rng":"numpy.random.Generator(PCG64)",
        "resampling_unit":"complete final-WB trajectory index",
        "joint_resample_across_physical_cells":True,
        "method_predictions_fixed":True,
        "primary_window":"H60..H240",
        "eligible_cells":12,
        "primary_points_per_complete_method":6660,
        "decision_metrics_bootstrapped":False,
        "registered_Delta_het_status":"NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE",
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    }
    write_json(manifest_path,manifest)

    all_intervals=intervals[
        (intervals["scope"]=="ALL")&(intervals["scope_value"]=="ALL")
    ].copy()
    print("PHASE5_V3B_FULLSUPPORT_WB_REFERENCE_BOOTSTRAP_PASS")
    print("\nPRIMARY ALL 95% REFERENCE-BOOTSTRAP INTERVALS")
    print(all_intervals[[
        "method_id","metric","deterministic_estimate",
        "bootstrap_lower_95","bootstrap_upper_95"
    ]].to_string(index=False))
    print("\nTOPOLOGY DELTA_P 95% REFERENCE-BOOTSTRAP INTERVALS")
    print(topology.to_string(index=False))
    print("\nregistered_Delta_het_status NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE")
    print("method_predictions_fixed True")
    print("manifest",manifest_path)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(description="Run registered N=1000 WB-reference bootstrap")
    p.add_argument("--batch-size",type=int,default=16)
    p.add_argument("--rebuild-outcomes",action="store_true")
    args=p.parse_args()
    run(rebuild_outcomes=bool(args.rebuild_outcomes),batch_size=int(args.batch_size))


if __name__=="__main__":
    main()
