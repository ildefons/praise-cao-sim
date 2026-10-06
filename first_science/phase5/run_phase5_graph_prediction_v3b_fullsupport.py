"""Blind scientific graph prediction for Phase-5 V3b FULL343.

This runner consumes only:
- the frozen public I1 cards;
- the frozen Step-0 eligibility map and query definitions;
- the frozen V3b provider reconstructions/weights;
- the frozen full-support graph contract, seed registry, and pre-execution
  allocations;
- public graph mechanics.

It never reads hidden generating provider parameters, private I1 traces, Step-0
white-box outcome values beyond eligibility/query definitions, or final graph
white-box evidence.

For each eligible physical cell it materializes:
- M0 analytic predictions;
- M1 graph predictions from the single V3b rank-1 reconstruction;
- M2 all 27 equal-weight joint members and their mean/min/max;
- M3 all 343 weighted joint members under the frozen B=1400 full-support
  allocation, plus FULL343 and nested Top1/Top3/Top14 readouts.

Native graph ledgers are resumable through per-trajectory checkpoints.  A cell
is immutable once its prediction_manifest.json is frozen.  When --all-cells is
used, the runner freezes a battery-level 12-predicted + 4-Step0-failed global
prediction manifest after every eligible cell is complete.  Only that global
freeze unlocks the later final-WB stage.
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
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE3=FIRST_SCIENCE/"phase3"
for p in (PHASE3,):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from diagnose_rho_conditioned_i1_m0 import build_same_rho_conditioned_m0_curve  # noqa:E402
from m0_analytic_composition import AdmissibilityBoundary, boundary_is_sufficient_for_query  # noqa:E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa:E402
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve  # noqa:E402

from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory  # noqa:E402
from phase5_runtime_v2 import (  # noqa:E402
    canonical_graph_ids,
    canonical_provider_world_ids,
    git_head,
    graph_record,
    load_phase5_contracts,
    physical_cell_id,
    read_json,
    sha256_file,
    utc_now_iso,
    validate_global_prediction_freeze_inputs,
    write_json,
)
from run_phase5_step0_v2 import _base_boundary, _load_public_i1_world  # noqa:E402

CFG=HERE/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"
STEP0_ROOT=HERE/"results"/"02_step0"
V3B_ROOT=HERE/"results"/"03_reconstruction_v3b"
ROOT=HERE/"results"/"04_prediction_v3b_fullsupport"
PREEXEC=ROOT/"_preexecution"/"phase5_v3b_fullsupport_preexecution_freeze_manifest.json"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT"
EXPECTED_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT"
EXPECTED_PREEXEC="FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_PREEXECUTION"
FROZEN_CELL_STATUS="FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION"
FROZEN_GLOBAL_STATUS="FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"
SUPPORT_SIZE=343
M2_SIZE=27
TOL=1e-12


def _horizons(cfg:dict)->list[float]:
    spec=cfg["horizons"]["prediction_grid_seconds"]
    vals=np.arange(
        float(spec["start"]),
        float(spec["end_inclusive"])+0.5*float(spec["step"]),
        float(spec["step"]),
        dtype=float,
    ).tolist()
    if len(vals)!=49 or vals[0]!=0.0 or vals[-1]!=240.0:
        raise RuntimeError("frozen prediction horizon grid changed")
    return vals


def _query_definitions(cell:str)->pd.DataFrame:
    path=STEP0_ROOT/cell/"step0_frozen_queries.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    # Deliberately load only the frozen query definition.  Step-0 calibration/
    # confirmation sigma outcome columns are not scientific prediction inputs.
    cols=[
        "query_id","provider_world_id","graph_id","rho_label","rho","regime",
        "scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status",
    ]
    q=pd.read_csv(path,usecols=cols)
    if len(q)!=15:
        raise RuntimeError(f"{cell}: expected exactly 15 frozen queries")
    if set(q["step0_cell_status"].astype(str))!={"FROZEN_PHASE5_STEP0_PASS_V2"}:
        raise RuntimeError(f"{cell}: frozen query file is not Step-0 PASS")
    if q["query_id"].astype(str).nunique()!=15:
        raise RuntimeError(f"{cell}: duplicate query_id")
    return q.sort_values(["rho","regime"],kind="mergesort").reset_index(drop=True)


def _public_surfaces(world:str)->dict[str,pd.DataFrame]:
    out={}
    for p in PROVIDERS:
        path=HERE/"results"/"01_i1"/world/"public"/p/"sigma_surface.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        use=["provider_id","region_id","region_rho","rho","horizon","sigma_hat"]
        out[p]=pd.read_csv(path,usecols=use)
    return out


def _surrogate(row:pd.Series)->GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _m1_surrogates(world:str)->dict[str,GraphProviderSurrogate]:
    out={}
    for p in PROVIDERS:
        path=V3B_ROOT/world/p/"m1_provider_model.csv"
        t=pd.read_csv(path)
        if len(t)!=1:
            raise RuntimeError(f"{world}/{p}: M1 provider cardinality !=1")
        out[p]=_surrogate(t.iloc[0])
    return out


def _candidate_lookup(world:str,method:str)->dict[tuple[str,str],GraphProviderSurrogate]:
    filename={"M2":"m2_provider_models.csv","M3":"m3_provider_models.csv"}[method]
    out={}
    expected=3 if method=="M2" else 7
    for p in PROVIDERS:
        path=V3B_ROOT/world/p/filename
        t=pd.read_csv(path)
        if len(t)!=expected:
            raise RuntimeError(f"{world}/{p}: {method} provider cardinality !={expected}")
        for _,row in t.iterrows():
            key=(p,str(row["candidate_id"]))
            if key in out:
                raise RuntimeError(f"{world}: duplicate candidate key {key}")
            out[key]=_surrogate(row)
    return out


def _m2_variants(world:str)->list[dict[str,Any]]:
    path=V3B_ROOT/world/"m2_joint_support_27.csv"
    t=pd.read_csv(path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    if len(t)!=M2_SIZE or t["joint_rank"].astype(int).tolist()!=list(range(1,M2_SIZE+1)):
        raise RuntimeError(f"{world}: frozen M2 joint support changed")
    if not np.allclose(t["joint_weight"].astype(float),1.0/27.0,rtol=0.0,atol=TOL):
        raise RuntimeError(f"{world}: frozen M2 weights changed")
    lookup=_candidate_lookup(world,"M2")
    rows=[]
    for rec in t.itertuples(index=False):
        rows.append({
            "rank":int(rec.joint_rank),
            "joint_weight":float(rec.joint_weight),
            "candidate_ids":{
                p:str(getattr(rec,f"{p}_candidate_id")) for p in PROVIDERS
            },
            "surrogates":{
                p:lookup[(p,str(getattr(rec,f"{p}_candidate_id")))]
                for p in PROVIDERS
            },
        })
    return rows


def _m3_variants(world:str)->tuple[list[dict[str,Any]],pd.DataFrame]:
    support_path=V3B_ROOT/world/"m3_joint_support_343.csv"
    support=pd.read_csv(support_path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    if len(support)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: M3 support !=343")
    if support["joint_rank"].astype(int).tolist()!=list(range(1,SUPPORT_SIZE+1)):
        raise RuntimeError(f"{world}: M3 ranks changed")
    if abs(float(support["joint_weight"].astype(float).sum())-1.0)>1e-10:
        raise RuntimeError(f"{world}: M3 weights do not normalize")

    pre=ROOT/"_preexecution"/f"m3_fullsupport_allocation_{world}.csv"
    allocation=pd.read_csv(pre).sort_values("rank",kind="mergesort").reset_index(drop=True)
    if len(allocation)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: frozen M3 allocation !=343 rows")
    if allocation["rank"].astype(int).tolist()!=list(range(1,SUPPORT_SIZE+1)):
        raise RuntimeError(f"{world}: M3 allocation ranks changed")
    if int(allocation["n_trajectories"].astype(int).sum())!=1400:
        raise RuntimeError(f"{world}: frozen M3 allocation budget !=1400")
    if (allocation["n_trajectories"].astype(int)<1).any():
        raise RuntimeError(f"{world}: M3 allocation has N<1")

    lookup=_candidate_lookup(world,"M3")
    rows=[]
    for rec in support.itertuples(index=False):
        rank=int(rec.joint_rank)
        arow=allocation[allocation["rank"].astype(int)==rank]
        if len(arow)!=1:
            raise RuntimeError(f"{world}: missing allocation rank {rank}")
        ar=arow.iloc[0]
        if abs(float(ar["joint_weight"])-float(rec.joint_weight))>1e-15:
            raise RuntimeError(f"{world}: allocation/support weight mismatch rank {rank}")
        rows.append({
            "rank":rank,
            "joint_weight":float(rec.joint_weight),
            "n_trajectories":int(ar["n_trajectories"]),
            "seed_start":int(ar["seed_start"]),
            "seed_end_inclusive":int(ar["seed_end_inclusive"]),
            "candidate_ids":{
                p:str(getattr(rec,f"{p}_candidate_id")) for p in PROVIDERS
            },
            "surrogates":{
                p:lookup[(p,str(getattr(rec,f"{p}_candidate_id")))]
                for p in PROVIDERS
            },
        })
    return rows,allocation


def _surrogates_plain(s:dict[str,GraphProviderSurrogate])->dict[str,dict[str,float]]:
    return {
        p:{
            "mean_service_time":float(x.mean_service_time),
            "cost_rate":float(x.cost_rate),
            "service_cv":float(x.service_cv),
        }
        for p,x in s.items()
    }


def _variant_checkpoint(cell_root:Path,variant_id:str,seed:int)->Path:
    return cell_root/"checkpoints"/variant_id/f"seed_{int(seed)}.csv"


def _validate_complete_ledger(path:Path,seeds:list[int])->pd.DataFrame:
    ledger=pd.read_csv(path)
    actual=sorted(ledger["trajectory_seed"].astype(int).unique().tolist())
    if actual!=sorted(map(int,seeds)):
        raise RuntimeError(f"{path}: trajectory seed set mismatch")
    if int(ledger["trajectory"].nunique())!=len(seeds):
        raise RuntimeError(f"{path}: trajectory count mismatch")
    return ledger


def _simulate_variant_worker(payload:dict[str,Any])->dict[str,Any]:
    cell_root=Path(payload["cell_root"])
    ledger_path=Path(payload["ledger_path"])
    seeds=[int(x) for x in payload["seeds"]]
    variant_id=str(payload["variant_id"])
    if ledger_path.is_file():
        _validate_complete_ledger(ledger_path,seeds)
        return {
            "variant_id":variant_id,
            "n_trajectories":len(seeds),
            "ledger_path":str(ledger_path),
            "reused":True,
            "wall_seconds":0.0,
        }

    s={
        p:GraphProviderSurrogate(
            mean_service_time=float(v["mean_service_time"]),
            cost_rate=float(v["cost_rate"]),
            service_cv=float(v["service_cv"]),
        )
        for p,v in payload["surrogates"].items()
    }
    started=time.perf_counter()
    graph_id=str(payload["graph_id"])
    graph_ast=payload["graph_ast"]
    graph_invariants=payload["graph_invariants"]
    workload=float(payload["workload_period"])
    stop=float(payload["stop_time"])
    ipt=float(payload["canonical_ipt"])
    x=float(payload["execution_fraction"])

    for ordinal,seed in enumerate(seeds):
        cp=_variant_checkpoint(cell_root,variant_id,seed)
        if cp.is_file():
            continue
        cp.parent.mkdir(parents=True,exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",FutureWarning)
            one,_=execute_one_phase5_graph_trajectory(
                graph_id=graph_id,
                graph_ast=graph_ast,
                provider_surrogates=s,
                graph_invariants=graph_invariants,
                workload_period=workload,
                stop_time=stop,
                trajectory_seed=seed,
                canonical_ipt=ipt,
                execution_fraction=x,
            )
        one.insert(0,"trajectory",int(ordinal))
        one.insert(1,"trajectory_seed",int(seed))
        tmp=cp.with_suffix(".tmp")
        one.to_csv(tmp,index=False)
        tmp.replace(cp)

    pieces=[]
    for ordinal,seed in enumerate(seeds):
        cp=_variant_checkpoint(cell_root,variant_id,seed)
        if not cp.is_file():
            raise RuntimeError(f"{variant_id}: missing checkpoint seed={seed}")
        one=pd.read_csv(cp)
        if set(one["trajectory"].astype(int))!={ordinal}:
            raise RuntimeError(f"{variant_id}: checkpoint ordinal mismatch seed={seed}")
        if set(one["trajectory_seed"].astype(int))!={seed}:
            raise RuntimeError(f"{variant_id}: checkpoint seed mismatch seed={seed}")
        pieces.append(one)
    ledger=pd.concat(pieces,ignore_index=True)
    if ledger[["trajectory","request_id"]].duplicated().any():
        raise RuntimeError(f"{variant_id}: duplicate trajectory/request_id")
    ledger_path.parent.mkdir(parents=True,exist_ok=True)
    tmp=ledger_path.with_suffix(".tmp")
    ledger.to_csv(tmp,index=False)
    tmp.replace(ledger_path)
    ck=cell_root/"checkpoints"/variant_id
    if ck.exists():
        shutil.rmtree(ck)
    return {
        "variant_id":variant_id,
        "n_trajectories":len(seeds),
        "ledger_path":str(ledger_path),
        "reused":False,
        "wall_seconds":float(time.perf_counter()-started),
    }


def _simulation_payload(
    *,
    cell_root:Path,
    graph_id:str,
    graph_ast:dict,
    variant_id:str,
    surrogates:dict[str,GraphProviderSurrogate],
    seeds:list[int],
    ledger_path:Path,
    contracts,
)->dict[str,Any]:
    inv=dict(contracts.battery["graph_invariants"])
    family=contracts.battery["provider_family"]
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    return {
        "cell_root":str(cell_root),
        "ledger_path":str(ledger_path),
        "variant_id":variant_id,
        "graph_id":graph_id,
        "graph_ast":graph_ast,
        "surrogates":_surrogates_plain(surrogates),
        "seeds":list(map(int,seeds)),
        "graph_invariants":inv,
        "workload_period":float(contracts.battery["workload"]["period_seconds"]),
        "stop_time":float(contracts.battery["horizon"]["maximum_seconds"]),
        "canonical_ipt":float(family["effective_IPT"]),
        "execution_fraction":float(family["execution_fraction_x"]),
    }


def _execute_payloads(payloads:list[dict[str,Any]],workers:int,label:str)->list[dict[str,Any]]:
    if workers<1:
        raise ValueError("workers must be >=1")
    total_models=len(payloads)
    total_traj=sum(len(x["seeds"]) for x in payloads)
    if workers==1:
        out=[]
        done_traj=0
        wall=time.perf_counter()
        for i,payload in enumerate(payloads,1):
            rec=_simulate_variant_worker(payload)
            out.append(rec)
            done_traj+=int(rec["n_trajectories"])
            elapsed=time.perf_counter()-wall
            print(
                f"{label}: models {i}/{total_models} | trajectories "
                f"{done_traj}/{total_traj} | elapsed={elapsed/60:.1f} min",
                flush=True,
            )
        return out

    out=[]
    done_models=0
    done_traj=0
    wall=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
        futures=[ex.submit(_simulate_variant_worker,p) for p in payloads]
        for future in concurrent.futures.as_completed(futures):
            rec=future.result()
            out.append(rec)
            done_models+=1
            done_traj+=int(rec["n_trajectories"])
            if done_models==1 or done_models%20==0 or done_models==total_models:
                elapsed=time.perf_counter()-wall
                print(
                    f"{label}: models {done_models}/{total_models} | trajectories "
                    f"{done_traj}/{total_traj} | elapsed={elapsed/60:.1f} min",
                    flush=True,
                )
    return out


def _member_curves(
    *,
    ledger:pd.DataFrame,
    queries:pd.DataFrame,
    horizons:list[float],
    method_id:str,
    rank:int,
    graph_n:int,
    joint_weight:float,
    candidate_ids:dict[str,str],
)->pd.DataFrame:
    rows=[]
    for q in queries.itertuples(index=False):
        boundary=AdmissibilityBoundary(
            l_max=float(q.A_G_l_max),
            c_max=float(q.A_G_c_max),
            q_min=float(q.A_G_q_min),
        )
        curve=build_empirical_graph_sigma_curve(
            ledger,
            boundary=boundary,
            rho_global=float(q.rho),
            horizons=horizons,
            stop_time=240.0,
            accounting_origin=0.0,
            output_column="sigma_member",
        )
        curve.insert(0,"query_id",str(q.query_id))
        curve.insert(1,"provider_world_id",str(q.provider_world_id))
        curve.insert(2,"graph_id",str(q.graph_id))
        curve.insert(3,"rho_label",str(q.rho_label))
        curve.insert(4,"rho",float(q.rho))
        curve.insert(5,"regime",str(q.regime))
        curve=curve.rename(columns={"horizon":"H"})
        curve["method_id"]=method_id
        curve["joint_rank"]=int(rank)
        curve["joint_weight"]=float(joint_weight)
        curve["graph_n"]=int(graph_n)
        for p in PROVIDERS:
            curve[f"{p}_candidate_id"]=str(candidate_ids[p])
        rows.append(curve)
    return pd.concat(rows,ignore_index=True)


def _m0_predictions(
    *,
    contracts,
    world:str,
    graph_id:str,
    queries:pd.DataFrame,
    horizons:list[float],
)->pd.DataFrame:
    cards=_load_public_i1_world(contracts,world)
    surfaces=_public_surfaces(world)
    rows=[]
    for q in queries.itertuples(index=False):
        induced=_base_boundary(
            contracts,graph_id=graph_id,cards=cards,rho=float(q.rho)
        )
        requested=AdmissibilityBoundary(
            l_max=float(q.A_G_l_max),
            c_max=float(q.A_G_c_max),
            q_min=float(q.A_G_q_min),
        )
        applicable=boundary_is_sufficient_for_query(induced,requested)
        curve=build_same_rho_conditioned_m0_curve(
            surfaces,rho=float(q.rho),horizons=horizons
        )
        for rec in curve.itertuples(index=False):
            rows.append({
                "query_id":str(q.query_id),
                "provider_world_id":world,
                "graph_id":graph_id,
                "rho_label":str(q.rho_label),
                "rho":float(q.rho),
                "regime":str(q.regime),
                "H":float(rec.horizon),
                "method_id":"M0",
                "status":"PREDICTED" if applicable else "NOT_APPLICABLE",
                "sigma_hat":float(rec.sigma_i1_m0) if applicable else np.nan,
                "induced_A_G_l_max":float(induced.l_max),
                "induced_A_G_c_max":float(induced.c_max),
                "induced_A_G_q_min":float(induced.q_min),
                "requested_A_G_l_max":float(requested.l_max),
                "requested_A_G_c_max":float(requested.c_max),
                "requested_A_G_q_min":float(requested.q_min),
            })
    return pd.DataFrame(rows).sort_values(
        ["query_id","H"],kind="mergesort"
    ).reset_index(drop=True)


def _m1_predictions(members:pd.DataFrame)->pd.DataFrame:
    out=members.rename(columns={"sigma_member":"sigma_hat"}).copy()
    out["method_id"]="M1"
    out["status"]="PREDICTED"
    keep=[
        "query_id","provider_world_id","graph_id","rho_label","rho","regime",
        "H","method_id","status","sigma_hat","graph_n",
    ]
    return out[keep].sort_values(["query_id","H"],kind="mergesort").reset_index(drop=True)


def _m2_predictions(members:pd.DataFrame)->pd.DataFrame:
    keys=["query_id","provider_world_id","graph_id","rho_label","rho","regime","H"]
    g=(
        members.groupby(keys,as_index=False)
        .agg(
            sigma_hat=("sigma_member","mean"),
            sigma_min=("sigma_member","min"),
            sigma_max=("sigma_member","max"),
            member_count=("joint_rank","nunique"),
        )
    )
    if set(g["member_count"].astype(int))!={27}:
        raise RuntimeError("M2 aggregation does not contain 27 members at every point")
    g["method_id"]="M2"
    g["status"]="PREDICTED"
    g["graph_n_per_member"]=100
    return g.sort_values(["query_id","H"],kind="mergesort").reset_index(drop=True)


def _m3_predictions(members:pd.DataFrame)->pd.DataFrame:
    keys=["query_id","provider_world_id","graph_id","rho_label","rho","regime","H"]
    rows=[]
    for key,g in members.groupby(keys,sort=True):
        g=g.sort_values("joint_rank",kind="mergesort")
        if g["joint_rank"].astype(int).tolist()!=list(range(1,344)):
            raise RuntimeError(f"M3 incomplete member support at {key}")
        full_weights=g["joint_weight"].astype(float).to_numpy()
        p=g["sigma_member"].astype(float).to_numpy()
        n=g["graph_n"].astype(int).to_numpy()
        if abs(float(full_weights.sum())-1.0)>1e-10:
            raise RuntimeError("M3 member weights do not normalize")
        for k,method in (
            (1,"M3_TOP1"),
            (3,"M3_TOP3"),
            (14,"M3_TOP14"),
            (343,"M3_FULL343"),
        ):
            w=full_weights[:k]
            retained=float(w.sum())
            alpha=w/retained
            ph=p[:k]
            nh=n[:k]
            sigma=float(np.sum(alpha*ph))
            plugin=float(np.sum(alpha*alpha*ph*(1.0-ph)/nh))
            worst=float(0.25*np.sum(alpha*alpha/nh))
            rows.append({
                "query_id":str(key[0]),
                "provider_world_id":str(key[1]),
                "graph_id":str(key[2]),
                "rho_label":str(key[3]),
                "rho":float(key[4]),
                "regime":str(key[5]),
                "H":float(key[6]),
                "method_id":method,
                "status":"PREDICTED",
                "sigma_hat":sigma,
                "support_size":k,
                "retained_mass":retained,
                "omitted_mass":1.0-retained,
                "truncation_bound":1.0-retained,
                "graph_budget":int(nh.sum()),
                "mc_var_plugin":plugin,
                "mc_se_plugin":math.sqrt(max(0.0,plugin)),
                "mc_var_worstcase_bound":worst,
                "mc_se_bound":math.sqrt(max(0.0,worst)),
            })
    out=pd.DataFrame(rows)
    full=out[out["method_id"]=="M3_FULL343"]
    if not np.allclose(full["retained_mass"].astype(float),1.0,atol=1e-10,rtol=0.0):
        raise RuntimeError("M3 FULL343 retained mass !=1")
    if not np.allclose(full["truncation_bound"].astype(float),0.0,atol=1e-10,rtol=0.0):
        raise RuntimeError("M3 FULL343 truncation bound !=0")
    return out.sort_values(["query_id","H","support_size"],kind="mergesort").reset_index(drop=True)


def _ledger_hash_table(cell_root:Path)->pd.DataFrame:
    ledgers=sorted((cell_root/"ledgers").glob("*.csv"))
    rows=[]
    for path in ledgers:
        if path.name=="prediction_ledger_hashes.csv":
            continue
        ledger=pd.read_csv(path,usecols=["trajectory","trajectory_seed"])
        rows.append({
            "ledger_file":str(path.relative_to(cell_root)),
            "sha256":sha256_file(path),
            "n_trajectories":int(ledger["trajectory"].nunique()),
            "seed_min":int(ledger["trajectory_seed"].min()),
            "seed_max":int(ledger["trajectory_seed"].max()),
        })
    return pd.DataFrame(rows).sort_values("ledger_file",kind="mergesort").reset_index(drop=True)


def _cell_manifest(
    *,
    cell_root:Path,
    cell:str,
    world:str,
    graph_id:str,
    queries_path:Path,
    outputs:dict[str,Path],
    ledger_hashes:pd.DataFrame,
    started_utc:str,
    wall_seconds:float,
)->dict:
    return {
        "status":FROZEN_CELL_STATUS,
        "stage_id":"BLIND_PREDICTION_V3B_FULLSUPPORT",
        "protocol_version":"PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT_2026-10-06",
        "scientific_evidence":True,
        "provider_world_id":world,
        "graph_id":graph_id,
        "physical_cell_id":cell,
        "code_commit":git_head(),
        "graph_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "preexecution_manifest_sha256":sha256_file(PREEXEC),
        "step0_frozen_queries_sha256":sha256_file(queries_path),
        "v3b_world_selection_manifest_sha256":sha256_file(
            V3B_ROOT/world/"world_selection_freeze_manifest.json"
        ),
        "inputs":{
            "query_count":15,
            "M1_joint_models":1,
            "M2_joint_models":27,
            "M3_joint_models":343,
            "M3_budget":1400,
            "graph_WB_read":False,
            "final_WB_read":False,
            "hidden_provider_parameters_read":False,
            "private_I1_traces_read":False,
        },
        "seed_banks":{
            "M1_M2":"56900..56999",
            "M3":"rank r: 7000000+(r-1)*10000+k, frozen provider-world prefix length",
        },
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "ledger_count":int(len(ledger_hashes)),
        "ledger_trajectory_total":int(ledger_hashes["n_trajectories"].sum()),
        "started_utc":started_utc,
        "completed_utc":utc_now_iso(),
        "python_wall_seconds":float(wall_seconds),
    }


def _run_cell(world:str,graph_id:str,workers:int)->dict[str,Any]:
    cell=physical_cell_id(world,graph_id)
    cell_root=ROOT/cell
    manifest_path=cell_root/"prediction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")==FROZEN_CELL_STATUS:
            return {
                "physical_cell_id":cell,
                "status":"FROZEN_CACHED",
                "wall_seconds":0.0,
            }
        raise RuntimeError(f"{cell}: existing prediction manifest has unexpected status")

    contracts=load_phase5_contracts(HERE)
    graph=graph_record(contracts,graph_id)
    queries_path=STEP0_ROOT/cell/"step0_frozen_queries.csv"
    queries=_query_definitions(cell)
    horizons=_horizons(read_json(CFG))
    started_utc=utc_now_iso()
    wall=time.perf_counter()
    cell_root.mkdir(parents=True,exist_ok=True)
    ledgers=cell_root/"ledgers"
    ledgers.mkdir(parents=True,exist_ok=True)

    # M0 is public-I1 analytic composition only.
    m0=_m0_predictions(
        contracts=contracts,world=world,graph_id=graph_id,
        queries=queries,horizons=horizons,
    )
    m0_path=cell_root/"m0_predictions.csv"
    m0.to_csv(m0_path,index=False)

    common=read_json(SEEDS)["graph_prediction"]["M1_M2_common_bank"]
    common_seeds=list(range(int(common["start"]),int(common["end_inclusive"])+1))
    if len(common_seeds)!=100:
        raise RuntimeError("M1/M2 common seed bank !=100")

    # M1.
    m1_s=_m1_surrogates(world)
    m1_payload=_simulation_payload(
        cell_root=cell_root,graph_id=graph_id,graph_ast=graph["ast"],
        variant_id="M1",surrogates=m1_s,seeds=common_seeds,
        ledger_path=ledgers/"M1.csv",contracts=contracts,
    )
    _execute_payloads([m1_payload],workers=min(workers,1),label=f"{cell} M1")
    m1_ledger=_validate_complete_ledger(ledgers/"M1.csv",common_seeds)
    m1_ids={
        p:str(pd.read_csv(V3B_ROOT/world/p/"m1_provider_model.csv").iloc[0]["candidate_id"])
        for p in PROVIDERS
    }
    m1_members=_member_curves(
        ledger=m1_ledger,queries=queries,horizons=horizons,
        method_id="M1",rank=1,graph_n=100,joint_weight=1.0,
        candidate_ids=m1_ids,
    )
    m1=_m1_predictions(m1_members)
    m1_path=cell_root/"m1_predictions.csv"
    m1.to_csv(m1_path,index=False)

    # M2.
    m2_variants=_m2_variants(world)
    m2_payloads=[]
    for v in m2_variants:
        rank=int(v["rank"])
        m2_payloads.append(_simulation_payload(
            cell_root=cell_root,graph_id=graph_id,graph_ast=graph["ast"],
            variant_id=f"M2_R{rank:02d}",surrogates=v["surrogates"],
            seeds=common_seeds,ledger_path=ledgers/f"M2_R{rank:02d}.csv",
            contracts=contracts,
        ))
    _execute_payloads(m2_payloads,workers=workers,label=f"{cell} M2")
    m2_frames=[]
    for v in m2_variants:
        rank=int(v["rank"])
        ledger=_validate_complete_ledger(ledgers/f"M2_R{rank:02d}.csv",common_seeds)
        m2_frames.append(_member_curves(
            ledger=ledger,queries=queries,horizons=horizons,
            method_id="M2_MEMBER",rank=rank,graph_n=100,
            joint_weight=float(v["joint_weight"]),
            candidate_ids=v["candidate_ids"],
        ))
    m2_members=pd.concat(m2_frames,ignore_index=True)
    m2_members_path=cell_root/"m2_member_curves.csv"
    m2_members.to_csv(m2_members_path,index=False)
    m2=_m2_predictions(m2_members)
    m2_path=cell_root/"m2_predictions.csv"
    m2.to_csv(m2_path,index=False)

    # M3 FULL343.
    m3_variants,allocation=_m3_variants(world)
    m3_payloads=[]
    for v in m3_variants:
        rank=int(v["rank"])
        seeds_rank=list(range(int(v["seed_start"]),int(v["seed_end_inclusive"])+1))
        if len(seeds_rank)!=int(v["n_trajectories"]):
            raise RuntimeError(f"{cell}: M3 rank {rank} seed/allocation mismatch")
        m3_payloads.append(_simulation_payload(
            cell_root=cell_root,graph_id=graph_id,graph_ast=graph["ast"],
            variant_id=f"M3_R{rank:03d}",surrogates=v["surrogates"],
            seeds=seeds_rank,ledger_path=ledgers/f"M3_R{rank:03d}.csv",
            contracts=contracts,
        ))
    _execute_payloads(m3_payloads,workers=workers,label=f"{cell} M3_FULL343")

    alloc_path=cell_root/"m3_fullsupport_allocation.csv"
    allocation.to_csv(alloc_path,index=False)
    m3_frames=[]
    for v in m3_variants:
        rank=int(v["rank"])
        seeds_rank=list(range(int(v["seed_start"]),int(v["seed_end_inclusive"])+1))
        ledger=_validate_complete_ledger(ledgers/f"M3_R{rank:03d}.csv",seeds_rank)
        m3_frames.append(_member_curves(
            ledger=ledger,queries=queries,horizons=horizons,
            method_id="M3_MEMBER",rank=rank,
            graph_n=int(v["n_trajectories"]),
            joint_weight=float(v["joint_weight"]),
            candidate_ids=v["candidate_ids"],
        ))
    m3_members=pd.concat(m3_frames,ignore_index=True)
    m3_members_path=cell_root/"m3_member_curves.csv"
    m3_members.to_csv(m3_members_path,index=False)
    m3=_m3_predictions(m3_members)
    m3_path=cell_root/"m3_predictions_full343_and_nested.csv"
    m3.to_csv(m3_path,index=False)

    ledger_hashes=_ledger_hash_table(cell_root)
    expected_ledger_count=1+27+343
    if len(ledger_hashes)!=expected_ledger_count:
        raise RuntimeError(
            f"{cell}: expected {expected_ledger_count} ledgers, found {len(ledger_hashes)}"
        )
    expected_traj=100+27*100+1400
    if int(ledger_hashes["n_trajectories"].sum())!=expected_traj:
        raise RuntimeError(f"{cell}: scientific graph trajectory total != {expected_traj}")
    ledger_hashes_path=cell_root/"prediction_ledger_hashes.csv"
    ledger_hashes.to_csv(ledger_hashes_path,index=False)

    outputs={
        "m0_predictions":m0_path,
        "m1_predictions":m1_path,
        "m2_member_curves":m2_members_path,
        "m2_predictions":m2_path,
        "m3_fullsupport_allocation":alloc_path,
        "m3_member_curves":m3_members_path,
        "m3_predictions_full343_and_nested":m3_path,
        "prediction_ledger_hashes":ledger_hashes_path,
    }
    manifest=_cell_manifest(
        cell_root=cell_root,cell=cell,world=world,graph_id=graph_id,
        queries_path=queries_path,outputs=outputs,ledger_hashes=ledger_hashes,
        started_utc=started_utc,wall_seconds=time.perf_counter()-wall,
    )
    write_json(manifest_path,manifest)
    if (cell_root/"checkpoints").exists():
        # Only empty/obsolete checkpoint roots should remain after all ledgers freeze.
        shutil.rmtree(cell_root/"checkpoints")

    print(
        f"PHASE5_V3B_FULLSUPPORT_CELL_PREDICTION_PASS {cell} | "
        f"ledgers={len(ledger_hashes)} trajectories={expected_traj} | "
        f"wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {
        "physical_cell_id":cell,
        "status":FROZEN_CELL_STATUS,
        "wall_seconds":float(manifest["python_wall_seconds"]),
    }


def _freeze_global()->Path:
    contracts=load_phase5_contracts(HERE)
    eligibility_path=STEP0_ROOT/"phase5_step0_eligibility.csv"
    eligibility=pd.read_csv(eligibility_path)
    mapping={}
    failed=[]
    status_rows=[]
    for rec in eligibility.sort_values(["provider_world_id","graph_id"],kind="mergesort").itertuples(index=False):
        cell=str(rec.physical_cell_id)
        if str(rec.eligibility)=="GATE_FAILED_STEP0":
            failed.append(cell)
            status_rows.append({
                "physical_cell_id":cell,
                "provider_world_id":str(rec.provider_world_id),
                "graph_id":str(rec.graph_id),
                "prediction_status":"GATE_FAILED_STEP0",
            })
            continue
        path=ROOT/cell/"prediction_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(f"cannot globally freeze; missing {path}")
        m=read_json(path)
        if m.get("status")!=FROZEN_CELL_STATUS:
            raise RuntimeError(f"{cell}: prediction manifest not frozen")
        mapping[cell]=path
        status_rows.append({
            "physical_cell_id":cell,
            "provider_world_id":str(rec.provider_world_id),
            "graph_id":str(rec.graph_id),
            "prediction_status":FROZEN_CELL_STATUS,
        })

    payload=validate_global_prediction_freeze_inputs(
        contracts,prediction_manifests=mapping,gate_failed_cells=failed
    )
    if len(payload["prediction_frozen_cells"])!=12 or len(payload["gate_failed_step0_cells"])!=4:
        raise RuntimeError("global prediction-freeze coverage is not 12+4")

    status=pd.DataFrame(status_rows)
    status_path=ROOT/"phase5_v3b_fullsupport_prediction_status.csv"
    status.to_csv(status_path,index=False)
    manifest={
        "status":FROZEN_GLOBAL_STATUS,
        "stage_id":"GLOBAL_PREDICTION_FREEZE_V3B_FULLSUPPORT",
        "protocol_version":"PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT_2026-10-06",
        "scientific_evidence":True,
        "code_commit":git_head(),
        "graph_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "preexecution_manifest_sha256":sha256_file(PREEXEC),
        "step0_eligibility_sha256":sha256_file(eligibility_path),
        "prediction_frozen_cells":payload["prediction_frozen_cells"],
        "gate_failed_step0_cells":payload["gate_failed_step0_cells"],
        "prediction_manifest_sha256":payload["prediction_manifest_sha256"],
        "complete":True,
        "final_WB_read":False,
        "outputs":{"prediction_status":str(status_path)},
        "output_hashes_sha256":{"prediction_status":sha256_file(status_path)},
        "completed_utc":utc_now_iso(),
    }
    path=ROOT/"phase5_v3b_fullsupport_global_prediction_freeze_manifest.json"
    write_json(path,manifest)
    print("PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE_PASS")
    print("prediction_frozen_cells 12")
    print("gate_failed_step0_cells 4")
    print("final_WB_read False")
    print("manifest",path)
    return path


def _preflight()->tuple[dict,dict,pd.DataFrame]:
    cfg=read_json(CFG)
    seeds=read_json(SEEDS)
    pre=read_json(PREEXEC)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected full-support graph contract")
    if seeds.get("status")!=EXPECTED_SEEDS:
        raise RuntimeError("unexpected full-support seed registry")
    if pre.get("status")!=EXPECTED_PREEXEC:
        raise RuntimeError("full-support pre-execution freeze has not passed")
    if pre.get("graph_contract_sha256")!=sha256_file(CFG):
        raise RuntimeError("pre-execution graph-contract hash mismatch")
    if pre.get("seed_registry_sha256")!=sha256_file(SEEDS):
        raise RuntimeError("pre-execution seed-registry hash mismatch")
    if pre.get("inputs",{}).get("graph_simulation_run") is not False:
        raise RuntimeError("pre-execution provenance says graph simulation already ran")
    if pre.get("inputs",{}).get("final_WB_read") is not False:
        raise RuntimeError("pre-execution final-WB firewall invalid")

    eligibility=pd.read_csv(STEP0_ROOT/"phase5_step0_eligibility.csv")
    if len(eligibility)!=16:
        raise RuntimeError("eligibility map !=16 cells")
    return cfg,seeds,eligibility


def main()->None:
    p=argparse.ArgumentParser(description="Run blind V3b FULL343 graph predictions")
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-cells",action="store_true")
    group.add_argument("--cell",type=str,help="one eligible physical cell, e.g. P1__G_PAR")
    p.add_argument("--workers",type=int,default=1)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")

    _,_,eligibility=_preflight()
    eligible=eligibility[eligibility["eligibility"].astype(str)=="ELIGIBLE"].copy()
    if len(eligible)!=12:
        raise RuntimeError("expected 12 eligible cells")

    if args.cell:
        match=eligible[eligible["physical_cell_id"].astype(str)==str(args.cell)]
        if len(match)!=1:
            raise RuntimeError(f"{args.cell}: not exactly one eligible physical cell")
        rec=match.iloc[0]
        _run_cell(str(rec["provider_world_id"]),str(rec["graph_id"]),args.workers)
        return

    summaries=[]
    started=time.perf_counter()
    for rec in eligible.sort_values(["provider_world_id","graph_id"],kind="mergesort").itertuples(index=False):
        summaries.append(_run_cell(
            str(rec.provider_world_id),str(rec.graph_id),args.workers
        ))
        done=len(summaries)
        elapsed=time.perf_counter()-started
        print(
            f"V3B FULLSUPPORT BATTERY PROGRESS {done}/12 cells | "
            f"elapsed={elapsed/3600:.2f} h",
            flush=True,
        )
    _freeze_global()


if __name__=="__main__":
    main()
