"""Official Phase-5 V2 Step-0 calibration and confirmation.

Step 0 is method-free.  For each of the 16 physical P x G cells, one hidden
white-box ledger is generated on the frozen calibration seed bank and reused to
score the complete scalar query family for all five rho values.  Exactly one
Easy/Mid/Stress query per rho is selected by the frozen mean-survival rule.

A second disjoint N=200 ledger evaluates only those already-frozen 15 queries.
A failed confirmation freezes that physical cell as GATE_FAILED_STEP0; it never
triggers reselection or repair and does not stop other cells.

The runner is resumable at trajectory granularity and supports cell-level
parallelism.  It records elapsed time, average seconds/trajectory and ETA.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import shutil
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE1=FIRST_SCIENCE/"phase1"
PHASE3=FIRST_SCIENCE/"phase3"
for path in (PHASE1,PHASE3):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

from sla_compliance_analysis import EVENT_TOLERANCE  # noqa:E402
from m0_analytic_composition import AdmissibilityBoundary  # noqa:E402
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve  # noqa:E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa:E402

from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory  # noqa:E402
from phase5_runtime_v2 import (  # noqa:E402
    base_manifest,
    canonical_graph_ids,
    canonical_provider_world_ids,
    graph_record,
    inclusive_seed_range,
    load_phase5_contracts,
    physical_cell_id,
    provider_world,
    query_id,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

DEFAULT_ROOT=HERE/"results"/"02_step0"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
TOL=1e-12


def _scale_grid(spec:Mapping[str,Any])->np.ndarray:
    low=float(spec["minimum"]); high=float(spec["maximum"]); step=float(spec["step"])
    if low<=0 or high<low or step<=0:
        raise RuntimeError("invalid frozen Step-0 scale grid")
    n=int(round((high-low)/step))
    grid=low+step*np.arange(n+1,dtype=float)
    if abs(float(grid[-1])-high)>1e-10:
        raise RuntimeError("Step-0 scale-grid endpoint mismatch")
    return np.round(grid,12)


def _horizons(contracts)->list[float]:
    h=contracts.battery["horizon"]
    low=float(h["minimum_seconds"]); high=float(h["maximum_seconds"])
    step=float(h["grid_step_seconds"])
    values=np.arange(low,high+0.5*step,step,dtype=float).tolist()
    if len(values)!=49 or values[0]!=0.0 or values[-1]!=240.0:
        raise RuntimeError("Phase-5 horizon support changed")
    return values


def _diagnostic_horizons(contracts)->list[float]:
    h=contracts.battery["horizon"]
    low=float(h["primary_evaluation_min_seconds"])
    high=float(h["primary_evaluation_max_seconds"])
    vals=[x for x in _horizons(contracts) if low-TOL<=x<=high+TOL]
    if len(vals)!=37 or vals[0]!=60.0 or vals[-1]!=240.0:
        raise RuntimeError("Step-0 diagnostic horizon window changed")
    return vals


def _regimes(contracts)->dict[str,tuple[float,float,float]]:
    rows=contracts.battery["step0"]["regimes"]
    out={
        str(x["id"]):(
            float(x["mean_sigma_lower"]),
            float(x["mean_sigma_upper"]),
            float(x["target_center"]),
        )
        for x in rows
    }
    expected={
        "Easy":(0.95,1.0,0.975),
        "Mid":(0.75,0.90,0.825),
        "Stress":(0.40,0.75,0.575),
    }
    if out!=expected:
        raise RuntimeError(f"Step-0 regimes changed: {out}")
    return out


def _rho_values(contracts)->list[tuple[str,float]]:
    return [
        (str(x["label"]),float(x["value"]))
        for x in contracts.execution["identifiers"]["rho"]
    ]


def _load_public_i1_world(contracts,world_id:str)->dict[str,dict[str,Any]]:
    root=HERE/"results"/"01_i1"/world_id
    freeze_path=root/"i1_freeze_manifest.json"
    if not freeze_path.is_file():
        raise FileNotFoundError(freeze_path)
    freeze=read_json(freeze_path)
    if freeze.get("status")!="FROZEN_PHASE5_I1_COMPLETE_V2":
        raise RuntimeError(f"{world_id}: I1 not frozen")
    if freeze.get("battery_config_sha256")!=contracts.hashes["battery"]:
        raise RuntimeError(f"{world_id}: I1 battery hash mismatch")
    if freeze.get("seed_registry_sha256")!=contracts.hashes["seeds"]:
        raise RuntimeError(f"{world_id}: I1 seed-registry hash mismatch")

    cards={}
    for provider in PROVIDERS:
        path=root/"public"/provider/"card.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        metadata=read_json(path)
        regions=list(metadata.get("rho_conditioned_regions",[]))
        if len(regions)!=5:
            raise RuntimeError(f"{world_id}/{provider}: expected five rho regions")
        cards[provider]=metadata
    return cards


def _local_boundary_at_rho(metadata:Mapping[str,Any],rho:float)->AdmissibilityBoundary:
    matches=[
        r for r in metadata["rho_conditioned_regions"]
        if abs(float(r["region_rho"])-float(rho))<=1e-12
    ]
    if len(matches)!=1:
        raise RuntimeError(f"public I1 has {len(matches)} regions at rho={rho}")
    r=matches[0]
    return AdmissibilityBoundary(
        l_max=float(r["l_max"]),
        c_max=float(r["c_max"]),
        q_min=float(r["q_min"]),
    )


def _network_delay(message_bytes:float,bw_mbps:float,pr:float)->float:
    return float(message_bytes)/(float(bw_mbps)*1_000_000.0)+float(pr)


def _compose_ast_boundary(
    ast:Any,
    local:Mapping[str,AdmissibilityBoundary],
    *,
    branch_data_delay:float,
    completion_control_delay:float,
)->AdmissibilityBoundary:
    if isinstance(ast,str):
        b=local[ast]
        return AdmissibilityBoundary(
            l_max=float(b.l_max)+branch_data_delay+completion_control_delay,
            c_max=float(b.c_max),
            q_min=float(b.q_min),
        )
    if not isinstance(ast,Mapping):
        raise TypeError("invalid graph AST node")
    op=str(ast["op"])
    children=[
        _compose_ast_boundary(
            child,local,
            branch_data_delay=branch_data_delay,
            completion_control_delay=completion_control_delay,
        )
        for child in ast["children"]
    ]
    if op=="sequence":
        latency=sum(float(x.l_max) for x in children)
    elif op=="parallel_all":
        latency=max(float(x.l_max) for x in children)
    else:
        raise ValueError(f"unsupported graph operator {op}")
    return AdmissibilityBoundary(
        l_max=float(latency),
        c_max=float(sum(float(x.c_max) for x in children)),
        q_min=float(min(float(x.q_min) for x in children)),
    )


def _base_boundary(
    contracts,
    *,
    graph_id:str,
    cards:Mapping[str,Mapping[str,Any]],
    rho:float,
)->AdmissibilityBoundary:
    inv=contracts.battery["graph_invariants"]
    family=contracts.battery["provider_family"]
    bw=float(inv["network_bw_mbps"])
    pr=float(inv["network_pr_seconds"])
    ipt=float(family["effective_IPT"])
    cost_rate=float(family["cost_rate"])

    root_delay=_network_delay(inv["request_bytes"],bw,pr)
    branch_delay=_network_delay(inv["branch_bytes"],bw,pr)
    join_delay=_network_delay(inv["join_bytes"],bw,pr)
    completion_delay=pr  # zero-byte native completion-control hop
    pre_service=float(inv["Fpre_instructions"])/ipt
    post_service=float(inv["Fpost_instructions"])/ipt
    outer_latency=root_delay+pre_service+join_delay+post_service
    outer_cost=cost_rate*(pre_service+post_service)

    local={p:_local_boundary_at_rho(cards[p],rho) for p in PROVIDERS}
    graph=graph_record(contracts,graph_id)
    composed=_compose_ast_boundary(
        graph["ast"],local,
        branch_data_delay=branch_delay,
        completion_control_delay=completion_delay,
    )
    result=AdmissibilityBoundary(
        l_max=float(outer_latency+composed.l_max),
        c_max=float(outer_cost+composed.c_max),
        q_min=float(composed.q_min),
    )

    # Exact regression sentinel against the already-audited pilot G_PAR adapter.
    if graph_id=="G_PAR":
        expected=(
            root_delay+pre_service+branch_delay+completion_delay+
            join_delay+post_service+
            max(float(local[p].l_max) for p in PROVIDERS)
        )
        if abs(float(result.l_max)-float(expected))>1e-12:
            raise RuntimeError("G_PAR forward-composition latency sentinel failed")
    return result


def _hidden_surrogates(contracts,world_id:str)->dict[str,GraphProviderSurrogate]:
    world=provider_world(contracts,world_id)
    family=contracts.battery["provider_family"]
    ipt=float(family["effective_IPT"])
    x=float(family["execution_fraction_x"])
    cv=float(family["instruction_cv"])
    rate=float(family["cost_rate"])
    return {
        p:GraphProviderSurrogate(
            mean_service_time=float(world["provider_means"][p])*x/ipt,
            cost_rate=rate,
            service_cv=cv,
        )
        for p in PROVIDERS
    }


def _trajectory_checkpoint(cell_root:Path,stage:str,seed:int)->Path:
    return cell_root/"checkpoints"/stage/f"seed_{int(seed)}.csv"


def _generate_or_load_ledger(
    *,
    contracts,
    world_id:str,
    graph_id:str,
    stage:str,
    cell_root:Path,
    seeds:tuple[int,...],
)->tuple[pd.DataFrame,float]:
    ledger_path=cell_root/f"step0_{stage}_whitebox_ledger.csv"
    if ledger_path.is_file():
        ledger=pd.read_csv(ledger_path)
        actual=tuple(sorted(ledger["trajectory_seed"].astype(int).unique()))
        if actual!=seeds or int(ledger["trajectory"].nunique())!=len(seeds):
            raise RuntimeError(f"{world_id}/{graph_id} {stage}: ledger seed mismatch")
        return ledger,0.0

    graph=graph_record(contracts,graph_id)
    inv=dict(contracts.battery["graph_invariants"])
    family=contracts.battery["provider_family"]
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    surrogates=_hidden_surrogates(contracts,world_id)
    workload=float(contracts.battery["workload"]["period_seconds"])
    stop=float(contracts.battery["horizon"]["maximum_seconds"])
    ipt=float(family["effective_IPT"])
    x=float(family["execution_fraction_x"])

    started=time.perf_counter()
    already=sum(1 for s in seeds if _trajectory_checkpoint(cell_root,stage,s).is_file())
    newly=0
    if already:
        print(f"{world_id} {graph_id} {stage}: resume {already}/{len(seeds)}",flush=True)

    for ordinal,seed in enumerate(seeds):
        path=_trajectory_checkpoint(cell_root,stage,seed)
        if path.is_file():
            continue
        path.parent.mkdir(parents=True,exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",FutureWarning)
            one,_=execute_one_phase5_graph_trajectory(
                graph_id=graph_id,
                graph_ast=graph["ast"],
                provider_surrogates=surrogates,
                graph_invariants=inv,
                workload_period=workload,
                stop_time=stop,
                trajectory_seed=int(seed),
                canonical_ipt=ipt,
                execution_fraction=x,
            )
        one.insert(0,"trajectory",int(ordinal))
        one.insert(1,"trajectory_seed",int(seed))
        tmp=path.with_suffix(".tmp")
        one.to_csv(tmp,index=False)
        tmp.replace(path)
        newly+=1
        completed=sum(1 for s in seeds if _trajectory_checkpoint(cell_root,stage,s).is_file())
        if newly==1 or completed%25==0 or completed==len(seeds):
            elapsed=time.perf_counter()-started
            sec_per=elapsed/max(1,newly)
            eta=sec_per*(len(seeds)-completed)
            print(
                f"{world_id} {graph_id} {stage}: {completed}/{len(seeds)} | "
                f"elapsed={elapsed/60:.1f} min | avg={sec_per:.2f} s/traj | "
                f"ETA={eta/60:.1f} min",
                flush=True,
            )

    parts=[]
    for ordinal,seed in enumerate(seeds):
        path=_trajectory_checkpoint(cell_root,stage,seed)
        frame=pd.read_csv(path)
        if set(frame["trajectory"].astype(int))!={ordinal}:
            raise RuntimeError(f"{world_id}/{graph_id} {stage}: ordinal mismatch seed={seed}")
        parts.append(frame)
    ledger=pd.concat(parts,ignore_index=True)
    if ledger[["trajectory","request_id"]].duplicated().any():
        raise RuntimeError(f"{world_id}/{graph_id} {stage}: duplicate ledger requests")
    ledger_path.parent.mkdir(parents=True,exist_ok=True)
    ledger.to_csv(ledger_path,index=False)
    ck=cell_root/"checkpoints"/stage
    if ck.exists():
        shutil.rmtree(ck)
    return ledger,float(time.perf_counter()-started)


def _candidate_sigma_matrix(
    ledger:pd.DataFrame,
    *,
    base:AdmissibilityBoundary,
    rho:float,
    scales:np.ndarray,
    horizons:list[float],
)->np.ndarray:
    hs=np.asarray(horizons,dtype=float)
    counts=np.zeros((len(scales),len(hs)),dtype=np.int32)
    trajectories=list(ledger.groupby("trajectory",sort=True))
    if not trajectories:
        raise RuntimeError("Step-0 candidate evaluator received no trajectories")
    for _,frame in trajectories:
        ordered=frame.sort_values(["emission","request_id"])
        emission=ordered["emission"].astype(float).to_numpy()
        completion=pd.to_numeric(ordered["completion"],errors="coerce").to_numpy(dtype=float)
        cost=pd.to_numeric(ordered["C"],errors="coerce").to_numpy(dtype=float)
        quality=pd.to_numeric(ordered["Q"],errors="coerce").to_numpy(dtype=float)
        finite=np.isfinite(completion)
        for si,scale in enumerate(scales):
            l=float(base.l_max)*float(scale)
            c=float(base.c_max)*float(scale)
            deadline=emission+l
            in_time=finite&(completion<=deadline+EVENT_TOLERANCE)
            decision_time=np.where(in_time,completion,deadline)
            decided=np.searchsorted(
                np.sort(decision_time),hs+EVENT_TOLERANCE,side="right"
            ).astype(np.int32)
            eligible=(
                in_time & np.isfinite(cost) & np.isfinite(quality)
                & (quality>=float(base.q_min))
                & (cost<=c+EVENT_TOLERANCE)
            )
            compliant_times=np.sort(completion[eligible])
            compliant=np.searchsorted(
                compliant_times,hs+EVENT_TOLERANCE,side="right"
            ).astype(np.int32)
            passing=np.zeros(len(hs),dtype=bool)
            zero=decided==0
            passing[zero]=bool(1.0+EVENT_TOLERANCE>=float(rho))
            nonzero=~zero
            if np.any(nonzero):
                fraction=compliant[nonzero].astype(float)/decided[nonzero].astype(float)
                passing[nonzero]=fraction+EVENT_TOLERANCE>=float(rho)
            counts[si,:]+=passing.astype(np.int32)
    return counts.astype(float)/float(len(trajectories))


def _candidate_table(
    *,
    rho_label:str,
    rho:float,
    regime:str,
    base:AdmissibilityBoundary,
    scales:np.ndarray,
    matrix:np.ndarray,
    band:tuple[float,float,float],
)->pd.DataFrame:
    low,high,target=band
    rows=[]
    for i,scale in enumerate(scales):
        sigma=matrix[i,:].astype(float)
        mean=float(np.mean(sigma))
        margin=float(min(mean-low,high-mean))
        rows.append({
            "rho_label":rho_label,
            "rho":float(rho),
            "regime":regime,
            "scale":float(scale),
            "A_G_l_max":float(base.l_max)*float(scale),
            "A_G_c_max":float(base.c_max)*float(scale),
            "A_G_q_min":float(base.q_min),
            "sigma_mean_H60_H240":mean,
            "sigma_min_H60_H240":float(np.min(sigma)),
            "sigma_max_H60_H240":float(np.max(sigma)),
            "distance_mean_to_target":abs(mean-target),
            "mean_margin_to_nearest_band_edge":margin,
            "distance_log_scale_to_base":abs(math.log(float(scale))),
            "feasible":bool(low-TOL<=mean<=high+TOL),
        })
    return pd.DataFrame(rows)


def _pick(table:pd.DataFrame)->pd.Series:
    feasible=table[table["feasible"].astype(bool)].copy()
    if feasible.empty:
        raise RuntimeError(
            f"rho={table.iloc[0]['rho']} regime={table.iloc[0]['regime']}: "
            "no feasible Step-0 candidate"
        )
    feasible["neg_margin"]=-feasible["mean_margin_to_nearest_band_edge"].astype(float)
    return feasible.sort_values(
        ["distance_mean_to_target","neg_margin","distance_log_scale_to_base","scale"],
        kind="mergesort",
    ).reset_index(drop=True).iloc[0]


def _joint_selection_failures(selected:pd.DataFrame,minimum_gap:float)->list[str]:
    failures=[]
    for rho,group in selected.groupby("rho",sort=True):
        rec={str(r["regime"]):r for _,r in group.iterrows()}
        if set(rec)!={"Easy","Mid","Stress"}:
            failures.append(f"rho={rho:g}: missing regime")
            continue
        sE=float(rec["Easy"]["scale"]); sM=float(rec["Mid"]["scale"]); sS=float(rec["Stress"]["scale"])
        if not (sS+TOL<sM and sM+TOL<sE):
            failures.append(
                f"rho={rho:g}: scale order failed Stress={sS}, Mid={sM}, Easy={sE}"
            )
        mE=float(rec["Easy"]["sigma_mean_H60_H240"])
        mM=float(rec["Mid"]["sigma_mean_H60_H240"])
        mS=float(rec["Stress"]["sigma_mean_H60_H240"])
        if mE-mM<minimum_gap-TOL:
            failures.append(f"rho={rho:g}: Easy-Mid mean gap {mE-mM:.6f} < {minimum_gap}")
        if mM-mS<minimum_gap-TOL:
            failures.append(f"rho={rho:g}: Mid-Stress mean gap {mM-mS:.6f} < {minimum_gap}")
    return failures


def _run_calibration_cell(world_id:str,graph_id:str,result_root:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    cell=physical_cell_id(world_id,graph_id)
    root=Path(result_root).resolve()/cell
    manifest_path=root/"step0_calibration_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2":
            return {"cell":cell,"status":"PASS_CACHED","wall_seconds":0.0}
        raise RuntimeError(f"{cell}: existing non-pass calibration manifest requires manual audit")

    started_utc=utc_now_iso()
    wall_started=time.perf_counter()
    cards=_load_public_i1_world(contracts,world_id)
    seeds=inclusive_seed_range(contracts.seeds["step0"]["calibration_WB"])
    ledger,sim_seconds=_generate_or_load_ledger(
        contracts=contracts,world_id=world_id,graph_id=graph_id,
        stage="calibration",cell_root=root,seeds=seeds,
    )
    scales=_scale_grid(contracts.battery["step0"]["scale_grid"])
    diagnostic=_diagnostic_horizons(contracts)
    regimes=_regimes(contracts)
    minimum_gap=float(contracts.battery["step0"]["minimum_adjacent_mean_sigma_gap"])

    candidate_frames=[]; selected_rows=[]; failures=[]
    for rho_label,rho in _rho_values(contracts):
        base=_base_boundary(
            contracts,graph_id=graph_id,cards=cards,rho=rho
        )
        matrix=_candidate_sigma_matrix(
            ledger,base=base,rho=rho,scales=scales,horizons=diagnostic
        )
        for regime,band in regimes.items():
            table=_candidate_table(
                rho_label=rho_label,rho=rho,regime=regime,base=base,
                scales=scales,matrix=matrix,band=band,
            )
            candidate_frames.append(table)
            try:
                row=_pick(table)
                selected_rows.append({
                    k:row[k] for k in row.index if k!="neg_margin"
                })
            except RuntimeError as exc:
                failures.append(str(exc))

    candidates=pd.concat(candidate_frames,ignore_index=True)
    selected=pd.DataFrame(selected_rows)
    if not selected.empty:
        selected.insert(0,"provider_world_id",world_id)
        selected.insert(1,"graph_id",graph_id)
        selected["query_id"]=[
            query_id(world_id,graph_id,str(r.rho_label),str(r.regime))
            for r in selected.itertuples(index=False)
        ]
        selected=selected.sort_values(["rho","regime"]).reset_index(drop=True)
    if len(selected)!=15:
        failures.append(f"selected query count {len(selected)} != 15")
    if len(selected)==15:
        failures.extend(_joint_selection_failures(selected,minimum_gap))

    root.mkdir(parents=True,exist_ok=True)
    candidates_path=root/"step0_calibration_candidates.csv"
    selected_path=root/"step0_selected_queries.csv"
    candidates.to_csv(candidates_path,index=False)
    selected.to_csv(selected_path,index=False)
    ledger_path=root/"step0_calibration_whitebox_ledger.csv"

    status=(
        "FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2"
        if not failures
        else "GATE_FAILED_STEP0_CALIBRATION"
    )
    manifest=base_manifest(
        contracts,stage_id="STEP0_CALIBRATION",status=status,
        inputs={
            "provider_world_id":world_id,
            "graph_id":graph_id,
            "i1_freeze_manifest_sha256":sha256_file(
                HERE/"results"/"01_i1"/world_id/"i1_freeze_manifest.json"
            ),
            "method_outcomes_used":False,
            "query_reselection_allowed":False,
        },
        seed_banks={
            "calibration_WB":{
                "start":seeds[0],"end_inclusive":seeds[-1],"n":len(seeds)
            }
        },
        outputs={
            "calibration_ledger":str(ledger_path),
            "step0_calibration_candidates":str(candidates_path),
            "step0_selected_queries":str(selected_path),
        },
        started_utc=started_utc,
    )
    manifest["failures"]=failures
    manifest["simulation_wall_seconds"]=sim_seconds
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall_started)
    write_json(manifest_path,manifest)
    print(
        f"STEP0_CALIBRATION_{'PASS' if not failures else 'FAIL'} "
        f"{cell} | wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {
        "cell":cell,
        "status":"PASS" if not failures else "GATE_FAILED",
        "wall_seconds":manifest["python_wall_seconds"],
        "failures":" | ".join(failures),
    }


def _query_curve(
    ledger:pd.DataFrame,
    *,
    boundary:AdmissibilityBoundary,
    rho:float,
    horizons:list[float],
    column:str,
)->pd.DataFrame:
    return build_empirical_graph_sigma_curve(
        ledger,boundary=boundary,rho_global=float(rho),horizons=horizons,
        stop_time=240.0,accounting_origin=0.0,output_column=column,
    )


def _run_confirmation_cell(world_id:str,graph_id:str,result_root:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    cell=physical_cell_id(world_id,graph_id)
    root=Path(result_root).resolve()/cell
    calibration_manifest_path=root/"step0_calibration_manifest.json"
    if not calibration_manifest_path.is_file():
        raise FileNotFoundError(calibration_manifest_path)
    calibration_manifest=read_json(calibration_manifest_path)
    if calibration_manifest.get("status")!="FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2":
        # Calibration failure is already a Step-0 exclusion. Freeze confirmation
        # status without running another WB bank.
        manifest_path=root/"step0_confirmation_manifest.json"
        payload=base_manifest(
            contracts,stage_id="STEP0_CONFIRMATION",status="GATE_FAILED_STEP0",
            inputs={"provider_world_id":world_id,"graph_id":graph_id,
                    "calibration_manifest_sha256":sha256_file(calibration_manifest_path)},
            seed_banks={},outputs={},started_utc=utc_now_iso(),
        )
        payload["failures"]=["calibration did not freeze exactly 15 valid queries"]
        write_json(manifest_path,payload)
        return {"cell":cell,"status":"GATE_FAILED","wall_seconds":0.0}

    selected_path=root/"step0_selected_queries.csv"
    selected=pd.read_csv(selected_path)
    if len(selected)!=15:
        raise RuntimeError(f"{cell}: frozen calibration has {len(selected)} queries")
    if calibration_manifest["output_hashes_sha256"]["step0_selected_queries"]!=sha256_file(selected_path):
        raise RuntimeError(f"{cell}: selected query hash changed after calibration freeze")

    manifest_path=root/"step0_confirmation_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status") in ("FROZEN_PHASE5_STEP0_PASS_V2","GATE_FAILED_STEP0"):
            return {"cell":cell,"status":m["status"],"wall_seconds":0.0}
        raise RuntimeError(f"{cell}: existing confirmation manifest has unknown status")

    started_utc=utc_now_iso()
    wall_started=time.perf_counter()
    seeds=inclusive_seed_range(contracts.seeds["step0"]["confirmation_WB"])
    ledger,sim_seconds=_generate_or_load_ledger(
        contracts=contracts,world_id=world_id,graph_id=graph_id,
        stage="confirmation",cell_root=root,seeds=seeds,
    )
    horizons=_horizons(contracts)
    diagnostic=set(_diagnostic_horizons(contracts))
    regimes=_regimes(contracts)
    minimum_gap=float(contracts.battery["step0"]["minimum_adjacent_mean_sigma_gap"])

    summaries=[]; curves=[]; failures=[]
    for rec in selected.itertuples(index=False):
        boundary=AdmissibilityBoundary(
            l_max=float(rec.A_G_l_max),
            c_max=float(rec.A_G_c_max),
            q_min=float(rec.A_G_q_min),
        )
        curve=_query_curve(
            ledger,boundary=boundary,rho=float(rec.rho),horizons=horizons,
            column="sigma_confirmation",
        )
        curve.insert(0,"query_id",str(rec.query_id))
        curve.insert(1,"rho_label",str(rec.rho_label))
        curve.insert(2,"rho",float(rec.rho))
        curve.insert(3,"regime",str(rec.regime))
        curves.append(curve)
        diag=curve[curve["horizon"].astype(float).isin(diagnostic)].copy()
        sigma=diag["sigma_confirmation"].astype(float).to_numpy()
        mean=float(np.mean(sigma))
        low,high,target=regimes[str(rec.regime)]
        passed=bool(low-TOL<=mean<=high+TOL)
        if not passed:
            failures.append(
                f"{rec.query_id}: confirmation mean {mean:.6f} outside [{low},{high}]"
            )
        summaries.append({
            "query_id":str(rec.query_id),
            "provider_world_id":world_id,
            "graph_id":graph_id,
            "rho_label":str(rec.rho_label),
            "rho":float(rec.rho),
            "regime":str(rec.regime),
            "scale":float(rec.scale),
            "A_G_l_max":float(rec.A_G_l_max),
            "A_G_c_max":float(rec.A_G_c_max),
            "A_G_q_min":float(rec.A_G_q_min),
            "sigma_mean_H60_H240":mean,
            "sigma_min_H60_H240":float(np.min(sigma)),
            "sigma_max_H60_H240":float(np.max(sigma)),
            "band_lower":low,"band_upper":high,"target_center":target,
            "per_query_pass":passed,
        })
    summary=pd.DataFrame(summaries).sort_values(["rho","regime"]).reset_index(drop=True)
    for rho,group in summary.groupby("rho",sort=True):
        means={str(r["regime"]):float(r["sigma_mean_H60_H240"]) for _,r in group.iterrows()}
        if means["Easy"]-means["Mid"]<minimum_gap-TOL:
            failures.append(
                f"rho={rho:g}: confirmation Easy-Mid gap "
                f"{means['Easy']-means['Mid']:.6f} < {minimum_gap}"
            )
        if means["Mid"]-means["Stress"]<minimum_gap-TOL:
            failures.append(
                f"rho={rho:g}: confirmation Mid-Stress gap "
                f"{means['Mid']-means['Stress']:.6f} < {minimum_gap}"
            )

    curves_df=pd.concat(curves,ignore_index=True)
    confirmation_path=root/"step0_confirmation.csv"
    curves_path=root/"step0_confirmation_curves.csv"
    frozen_path=root/"step0_frozen_queries.csv"
    summary.to_csv(confirmation_path,index=False)
    curves_df.to_csv(curves_path,index=False)
    frozen=selected.copy()
    cell_status="FROZEN_PHASE5_STEP0_PASS_V2" if not failures else "GATE_FAILED_STEP0"
    frozen["step0_cell_status"]=cell_status
    frozen.to_csv(frozen_path,index=False)

    ledger_path=root/"step0_confirmation_whitebox_ledger.csv"
    manifest=base_manifest(
        contracts,stage_id="STEP0_CONFIRMATION",status=cell_status,
        inputs={
            "provider_world_id":world_id,"graph_id":graph_id,
            "calibration_manifest_sha256":sha256_file(calibration_manifest_path),
            "selected_queries_sha256":sha256_file(selected_path),
            "no_reselection_after_confirmation":True,
            "method_outcomes_used":False,
        },
        seed_banks={
            "confirmation_WB":{
                "start":seeds[0],"end_inclusive":seeds[-1],"n":len(seeds)
            }
        },
        outputs={
            "confirmation_ledger":str(ledger_path),
            "step0_confirmation":str(confirmation_path),
            "step0_confirmation_curves":str(curves_path),
            "step0_frozen_queries":str(frozen_path),
        },
        started_utc=started_utc,
    )
    manifest["failures"]=failures
    manifest["simulation_wall_seconds"]=sim_seconds
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall_started)
    write_json(manifest_path,manifest)
    print(
        f"STEP0_CONFIRMATION_{'PASS' if not failures else 'GATE_FAILED'} "
        f"{cell} | wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {
        "cell":cell,"status":"PASS" if not failures else "GATE_FAILED",
        "wall_seconds":manifest["python_wall_seconds"],
        "failures":" | ".join(failures),
    }


def _run_stage(stage:str,result_root:Path,workers:int)->None:
    contracts=load_phase5_contracts(HERE)
    cells=[
        (p,g)
        for p in canonical_provider_world_ids(contracts)
        for g in canonical_graph_ids(contracts)
    ]
    fn=_run_calibration_cell if stage=="calibration" else _run_confirmation_cell
    wall=time.perf_counter()
    results=[]
    if workers<=1:
        for p,g in cells:
            results.append(fn(p,g,str(result_root)))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={
                pool.submit(fn,p,g,str(result_root)):(p,g)
                for p,g in cells
            }
            for future in concurrent.futures.as_completed(futures):
                p,g=futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"{p}/{g} {stage} worker failed") from exc
    table=pd.DataFrame(results).sort_values("cell").reset_index(drop=True)
    print(f"\nPHASE5_STEP0_{stage.upper()}_SUMMARY")
    print(table.to_string(index=False))
    elapsed=time.perf_counter()-wall
    print(f"stage_wall={elapsed/60:.1f} min workers={workers}")
    if stage=="calibration" and any(table["status"].astype(str).str.contains("GATE_FAILED")):
        print("Calibration failures are frozen; no repair/reselection is permitted.")
    if stage=="confirmation":
        n_pass=int((table["status"].astype(str)=="PASS").sum())
        n_fail=int((table["status"].astype(str)=="GATE_FAILED").sum())
        print(f"eligible_cells={n_pass} gate_failed_cells={n_fail}")


def main()->None:
    p=argparse.ArgumentParser(description="Official Phase-5 V2 Step-0")
    stage=p.add_mutually_exclusive_group(required=True)
    stage.add_argument("--calibration",action="store_true")
    stage.add_argument("--confirmation",action="store_true")
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--result-root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    _run_stage(
        "calibration" if args.calibration else "confirmation",
        args.result_root.resolve(),
        int(args.workers),
    )


if __name__=="__main__":
    main()
