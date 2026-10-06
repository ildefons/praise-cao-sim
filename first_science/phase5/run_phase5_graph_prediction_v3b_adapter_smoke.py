"""Real non-scientific adapter smoke for Phase-5 V3b graph prediction.

This runner consumes the *frozen real V3b reconstruction artifacts* and the
frozen Step-0 query definitions, but it uses only engineering smoke seeds and
tiny graph budgets.  It never reads or generates final graph white-box data.

Coverage:
- real M0 path and real M1 selected surrogates on all four graph ASTs;
- all 27 real M2 joint combinations on G_PAR, with equal-weight aggregation;
- all 14 real M3 retained combinations on G_PAR, with the frozen minimax
  allocation rule exercised at a tiny smoke budget and Top1/Top3/Top14 nested
  readouts;
- the real B=1400 M3 allocation is derived and checked, but not simulated;
- manifest/hash production and the 12-predicted + 4-Step0-failed global-freeze
  bookkeeping path are exercised with fake smoke prediction manifests.

Smoke output is written only under phase5/smoke/ and is never scientific input.
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE3=FIRST_SCIENCE/"phase3"
PHASE4=FIRST_SCIENCE/"phase4"
for p in (PHASE3,PHASE4):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from m0_analytic_composition import AdmissibilityBoundary, boundary_is_sufficient_for_query
from diagnose_rho_conditioned_i1_m0 import build_same_rho_conditioned_m0_curve
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve
from m3_v4_dominant_mass_graph import _integer_minimax_allocations

from phase5_graph_simulator_v2 import GraphProviderSurrogate, execute_one_phase5_graph_trajectory
from phase5_runtime_v2 import (
    canonical_graph_ids,
    canonical_provider_world_ids,
    graph_record,
    load_phase5_contracts,
    physical_cell_id,
    read_json,
    sha256_file,
    utc_now_iso,
    validate_global_prediction_freeze_inputs,
    write_json,
)
from run_phase5_step0_v2 import _base_boundary, _load_public_i1_world

CFG=HERE/"config_phase5_graph_prediction_v3b.json"
SEEDS_V3=HERE/"config_phase5_seed_registry_v3.json"
V3B_ROOT=HERE/"results"/"03_reconstruction_v3b"
STEP0_ROOT=HERE/"results"/"02_step0"
DEFAULT_OUTPUT=HERE/"smoke"/"v3b_graph_adapter"
WORLD="P1"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SMOKE_STOP_TIME=5.0
SMOKE_HORIZONS=[0.0,5.0]
SMOKE_M2_N_PER_MEMBER=1
SMOKE_M3_BUDGET=28
TOL=1e-12


def _surrogate(row:pd.Series)->GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _provider_tables(world:str,method:str)->dict[str,pd.DataFrame]:
    filename={
        "M1":"m1_provider_model.csv",
        "M2":"m2_provider_models.csv",
        "M3":"m3_provider_models.csv",
    }[method]
    out={}
    for provider in PROVIDERS:
        path=V3B_ROOT/world/provider/filename
        if not path.is_file():
            raise FileNotFoundError(path)
        out[provider]=pd.read_csv(path)
    return out


def _candidate_lookup(tables:dict[str,pd.DataFrame])->dict[tuple[str,str],pd.Series]:
    out={}
    for provider,table in tables.items():
        for _,row in table.iterrows():
            key=(provider,str(row["candidate_id"]))
            if key in out:
                raise RuntimeError(f"duplicate candidate key {key}")
            out[key]=row
    return out


def _one_graph_ledger(
    *,
    contracts,
    graph_id:str,
    surrogates:dict[str,GraphProviderSurrogate],
    seeds:list[int],
)->pd.DataFrame:
    rec=graph_record(contracts,graph_id)
    inv=dict(contracts.battery["graph_invariants"])
    family=contracts.battery["provider_family"]
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    parts=[]
    for ordinal,seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",FutureWarning)
            one,_=execute_one_phase5_graph_trajectory(
                graph_id=graph_id,
                graph_ast=rec["ast"],
                provider_surrogates=surrogates,
                graph_invariants=inv,
                workload_period=float(contracts.battery["workload"]["period_seconds"]),
                stop_time=SMOKE_STOP_TIME,
                trajectory_seed=int(seed),
                canonical_ipt=float(family["effective_IPT"]),
                execution_fraction=float(family["execution_fraction_x"]),
            )
        one.insert(0,"trajectory",int(ordinal))
        one.insert(1,"trajectory_seed",int(seed))
        parts.append(one)
    ledger=pd.concat(parts,ignore_index=True)
    if ledger.empty:
        raise RuntimeError(f"{graph_id}: empty smoke ledger")
    if int(ledger["completed_by_stop"].astype(bool).sum())==0:
        raise RuntimeError(f"{graph_id}: no completed smoke requests")
    return ledger


def _selected_smoke_query(graph_id:str)->pd.Series:
    path=STEP0_ROOT/physical_cell_id(WORLD,graph_id)/"step0_frozen_queries.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    q=pd.read_csv(path)
    if len(q)!=15:
        raise RuntimeError(f"{graph_id}: expected 15 frozen Step-0 queries")
    # Mechanical smoke choice only: use the largest already-frozen region.  This
    # does not alter or select any scientific query; all 15 remain frozen.
    return q.sort_values(["scale_s","rho","regime"],ascending=[False,True,True],kind="mergesort").iloc[0]


def _curve(ledger:pd.DataFrame,query:pd.Series,column:str)->pd.DataFrame:
    b=AdmissibilityBoundary(
        l_max=float(query["l_max"]),
        c_max=float(query["c_max"]),
        q_min=float(query["q_min"]),
    )
    return build_empirical_graph_sigma_curve(
        ledger,
        boundary=b,
        rho_global=float(query["rho"]),
        horizons=SMOKE_HORIZONS,
        stop_time=SMOKE_STOP_TIME,
        accounting_origin=0.0,
        output_column=column,
    )


def _real_m1_surrogates()->dict[str,GraphProviderSurrogate]:
    tables=_provider_tables(WORLD,"M1")
    if any(len(t)!=1 for t in tables.values()):
        raise RuntimeError("P1 V3b M1 provider cardinality mismatch")
    return {p:_surrogate(t.iloc[0]) for p,t in tables.items()}


def _m2_variants()->list[tuple[int,dict[str,GraphProviderSurrogate]]]:
    tables=_provider_tables(WORLD,"M2")
    lookup=_candidate_lookup(tables)
    support_path=V3B_ROOT/WORLD/"m2_joint_support_27.csv"
    support=pd.read_csv(support_path)
    if len(support)!=27:
        raise RuntimeError("P1 V3b M2 support is not 27")
    variants=[]
    for rec in support.sort_values("joint_rank").itertuples(index=False):
        variants.append((
            int(rec.joint_rank),
            {
                p:_surrogate(lookup[(p,str(getattr(rec,f"{p}_candidate_id")))])
                for p in PROVIDERS
            },
        ))
    return variants


def _m3_design()->tuple[pd.DataFrame,dict[int,dict[str,GraphProviderSurrogate]],pd.DataFrame,pd.DataFrame]:
    tables=_provider_tables(WORLD,"M3")
    lookup=_candidate_lookup(tables)
    full_path=V3B_ROOT/WORLD/"m3_joint_support_343.csv"
    top_path=V3B_ROOT/WORLD/"m3_joint_support_top14.csv"
    full=pd.read_csv(full_path).sort_values("joint_rank").reset_index(drop=True)
    top=pd.read_csv(top_path).sort_values("joint_rank").reset_index(drop=True)
    if len(full)!=343 or len(top)!=14:
        raise RuntimeError("P1 V3b M3 support cardinality mismatch")
    if top["joint_rank"].astype(int).tolist()!=list(range(1,15)):
        raise RuntimeError("P1 V3b M3 Top14 ranks changed")
    retained=float(top["joint_weight"].astype(float).sum())
    alpha=top["joint_weight"].astype(float).to_numpy()/retained
    production=_integer_minimax_allocations(alpha,[1400])
    smoke=_integer_minimax_allocations(alpha,[SMOKE_M3_BUDGET])
    if int(production["n_trajectories"].sum())!=1400:
        raise RuntimeError("production M3 allocation does not sum to 1400")
    if int(smoke["n_trajectories"].sum())!=SMOKE_M3_BUDGET:
        raise RuntimeError("smoke M3 allocation sum mismatch")
    variants={}
    for rec in top.itertuples(index=False):
        rank=int(rec.joint_rank)
        variants[rank]={
            p:_surrogate(lookup[(p,str(getattr(rec,f"{p}_candidate_id")))])
            for p in PROVIDERS
        }
    return top,variants,production,smoke


def _m0_probe(contracts,graph_id:str,query:pd.Series,cards,surfaces)->pd.DataFrame:
    rho=float(query["rho"])
    induced=_base_boundary(contracts,graph_id=graph_id,cards=cards,rho=rho)
    requested=AdmissibilityBoundary(
        l_max=float(query["l_max"]),
        c_max=float(query["c_max"]),
        q_min=float(query["q_min"]),
    )
    applicable=boundary_is_sufficient_for_query(induced,requested)
    product=build_same_rho_conditioned_m0_curve(
        surfaces,rho=rho,horizons=SMOKE_HORIZONS
    )
    product["m0_status"]="PREDICTED" if applicable else "NOT_APPLICABLE"
    if not applicable:
        product["sigma_i1_m0"]=np.nan
    return product


def _fake_global_freeze_probe(output:Path,contracts,eligibility:pd.DataFrame)->Path:
    root=output/"global_freeze_probe"
    root.mkdir(parents=True,exist_ok=True)
    mapping={}
    failed=[]
    for rec in eligibility.itertuples(index=False):
        cell=str(rec.physical_cell_id)
        if str(rec.eligibility)=="GATE_FAILED_STEP0":
            failed.append(cell)
            continue
        path=root/f"{cell}.json"
        write_json(path,{
            "status":"FROZEN_PHASE5_V3B_SMOKE_PREDICTION",
            "stage_id":"BLIND_PREDICTION_V3B_SMOKE",
            "physical_cell_id":cell,
            "scientific_evidence":False,
        })
        mapping[cell]=path
    payload=validate_global_prediction_freeze_inputs(
        contracts,prediction_manifests=mapping,gate_failed_cells=failed
    )
    if not payload["complete"]:
        raise RuntimeError("V3b smoke global-freeze probe incomplete")
    if len(payload["prediction_frozen_cells"])!=12 or len(payload["gate_failed_step0_cells"])!=4:
        raise RuntimeError("V3b smoke global-freeze counts changed")
    path=root/"global_freeze_probe.json"
    write_json(path,payload)
    return path


def run(output:Path,*,reset:bool)->None:
    started=utc_now_iso()
    cfg=read_json(CFG)
    seeds=read_json(SEEDS_V3)
    if cfg.get("status")!="FROZEN_PHASE5_GRAPH_PREDICTION_EXECUTION_V3B":
        raise RuntimeError("unexpected V3b graph contract")
    if seeds.get("status")!="FROZEN_PHASE5_SEED_REGISTRY_V3":
        raise RuntimeError("unexpected V3 seed registry")
    if seeds["engineering_smoke"]["scientific_evidence"] is not False:
        raise RuntimeError("engineering smoke flag changed")

    contracts=load_phase5_contracts(HERE)
    eligibility_path=STEP0_ROOT/"phase5_step0_eligibility.csv"
    eligibility=pd.read_csv(eligibility_path)
    if len(eligibility)!=16:
        raise RuntimeError("Step-0 eligibility must contain 16 cells")
    if int((eligibility["eligibility"]=="ELIGIBLE").sum())!=12:
        raise RuntimeError("expected 12 eligible cells")
    failed=eligibility[eligibility["eligibility"]=="GATE_FAILED_STEP0"]
    if len(failed)!=4 or set(failed["provider_world_id"].astype(str))!={"P2"}:
        raise RuntimeError("expected exactly four P2 Step-0 failures")

    audit_path=V3B_ROOT/"phase5_v3b_selection_audit_manifest.json"
    audit=read_json(audit_path)
    if audit.get("status")!="FROZEN_PHASE5_V3B_SELECTION_MECHANICAL_AUDIT_PASS":
        raise RuntimeError("V3b selection audit has not passed")

    output=output.resolve()
    try:
        output.relative_to(HERE.resolve())
    except ValueError as exc:
        raise RuntimeError("smoke output must remain inside phase5/") from exc
    if "results" in output.parts:
        raise RuntimeError("engineering smoke must not write under scientific results/")
    if reset and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True,exist_ok=True)

    smoke_base=int(seeds["engineering_smoke"]["seed_base"])
    cards=_load_public_i1_world(contracts,WORLD)
    surfaces={
        p:pd.read_csv(HERE/"results"/"01_i1"/WORLD/"public"/p/"sigma_surface.csv")
        for p in PROVIDERS
    }

    # 1) M0 + real selected M1 on all four graph ASTs.
    m1_surrogates=_real_m1_surrogates()
    graph_rows=[]
    m1_curve_rows=[]
    for gi,graph_id in enumerate(canonical_graph_ids(contracts)):
        query=_selected_smoke_query(graph_id)
        m0=_m0_probe(contracts,graph_id,query,cards,surfaces)
        seed=smoke_base+1000+gi
        ledger=_one_graph_ledger(
            contracts=contracts,graph_id=graph_id,
            surrogates=m1_surrogates,seeds=[seed],
        )
        curve=_curve(ledger,query,"sigma_m1_smoke")
        curve.insert(0,"graph_id",graph_id)
        curve.insert(1,"query_id",str(query["query_id"]))
        curve["rho"]=float(query["rho"])
        curve["regime"]=str(query["regime"])
        m1_curve_rows.append(curve)
        graph_rows.append({
            "graph_id":graph_id,
            "query_id":str(query["query_id"]),
            "rho":float(query["rho"]),
            "regime":str(query["regime"]),
            "m0_status":str(m0["m0_status"].iloc[0]),
            "m1_seed":seed,
            "m1_requests":int(len(ledger)),
            "m1_completed":int(ledger["completed_by_stop"].astype(bool).sum()),
        })
        print(f"V3B GRAPH SMOKE M1 {graph_id} PASS",flush=True)

    graph_summary=pd.DataFrame(graph_rows)
    m1_curves=pd.concat(m1_curve_rows,ignore_index=True)
    graph_summary_path=output/"graph_ast_m1_summary.csv"
    m1_curve_path=output/"m1_smoke_curves.csv"
    graph_summary.to_csv(graph_summary_path,index=False)
    m1_curves.to_csv(m1_curve_path,index=False)

    # 2) Full real M2 27-member plumbing on one representative graph.
    graph_id="G_PAR"
    query=_selected_smoke_query(graph_id)
    m2_member_rows=[]
    m2_seed=smoke_base+2000
    for rank,surrogates in _m2_variants():
        ledger=_one_graph_ledger(
            contracts=contracts,graph_id=graph_id,
            surrogates=surrogates,seeds=[m2_seed],
        )
        curve=_curve(ledger,query,"sigma_member")
        curve.insert(0,"joint_rank",rank)
        m2_member_rows.append(curve)
    m2_members=pd.concat(m2_member_rows,ignore_index=True)
    if m2_members["joint_rank"].nunique()!=27:
        raise RuntimeError("M2 smoke did not execute 27 unique members")
    m2_pred=(
        m2_members.groupby("horizon",as_index=False)["sigma_member"]
        .agg(["mean","min","max"]).reset_index()
        .rename(columns={"mean":"sigma_m2_mean","min":"sigma_m2_min","max":"sigma_m2_max"})
    )
    if len(m2_pred)!=len(SMOKE_HORIZONS):
        raise RuntimeError("M2 smoke aggregation horizon mismatch")
    m2_members_path=output/"m2_smoke_member_curves.csv"
    m2_pred_path=output/"m2_smoke_predictions.csv"
    m2_members.to_csv(m2_members_path,index=False)
    m2_pred.to_csv(m2_pred_path,index=False)
    print("V3B GRAPH SMOKE M2 27-MEMBER AGGREGATION PASS",flush=True)

    # 3) Real M3 Top14 identities/weights.  Derive and check the production
    # B=1400 allocation, then execute a tiny B=28 smoke allocation.
    top14,m3_variants,production_alloc,smoke_alloc=_m3_design()
    production_alloc_path=output/"m3_production_B1400_allocation_probe.csv"
    smoke_alloc_path=output/"m3_smoke_B28_allocation.csv"
    production_alloc.to_csv(production_alloc_path,index=False)
    smoke_alloc.to_csv(smoke_alloc_path,index=False)
    smoke_counts=smoke_alloc.set_index("rank")["n_trajectories"].astype(int).to_dict()

    m3_rows=[]
    for rec in top14.itertuples(index=False):
        rank=int(rec.joint_rank)
        n=int(smoke_counts[rank])
        rank_seed0=smoke_base+3000+(rank-1)*100
        seeds_rank=[rank_seed0+k for k in range(n)]
        ledger=_one_graph_ledger(
            contracts=contracts,graph_id=graph_id,
            surrogates=m3_variants[rank],seeds=seeds_rank,
        )
        curve=_curve(ledger,query,"sigma_member")
        curve.insert(0,"joint_rank",rank)
        curve["joint_weight"]=float(rec.joint_weight)
        curve["n_trajectories"]=n
        m3_rows.append(curve)
    m3_members=pd.concat(m3_rows,ignore_index=True)

    readout_rows=[]
    for k,label in ((1,"M3_TOP1"),(3,"M3_TOP3"),(14,"M3_TOP14")):
        sub=m3_members[m3_members["joint_rank"].astype(int)<=k].copy()
        weights=(
            top14[top14["joint_rank"].astype(int)<=k]
            .set_index("joint_rank")["joint_weight"].astype(float)
        )
        retained_full_mass=float(weights.sum())
        alpha=weights/retained_full_mass
        for horizon,g in sub.groupby("horizon",sort=True):
            by_rank=g.set_index("joint_rank")["sigma_member"].astype(float)
            sigma=float(sum(float(alpha.loc[r])*float(by_rank.loc[r]) for r in alpha.index))
            readout_rows.append({
                "method_id":label,
                "support_size":k,
                "horizon":float(horizon),
                "sigma_hat":sigma,
                "retained_full_mass":retained_full_mass,
                "omitted_full_mass":1.0-retained_full_mass,
            })
    m3_pred=pd.DataFrame(readout_rows)
    if set(m3_pred["method_id"])!={"M3_TOP1","M3_TOP3","M3_TOP14"}:
        raise RuntimeError("M3 nested smoke readouts incomplete")
    if len(m3_pred)!=3*len(SMOKE_HORIZONS):
        raise RuntimeError("M3 nested smoke readout row count mismatch")
    m3_members_path=output/"m3_smoke_member_curves.csv"
    m3_pred_path=output/"m3_smoke_predictions_top1_top3_top14.csv"
    m3_members.to_csv(m3_members_path,index=False)
    m3_pred.to_csv(m3_pred_path,index=False)
    print("V3B GRAPH SMOKE M3 ALLOCATION + NESTED READOUTS PASS",flush=True)

    global_probe=_fake_global_freeze_probe(output,contracts,eligibility)
    print("V3B GRAPH SMOKE GLOBAL FREEZE 12+4 LOGIC PASS",flush=True)

    outputs={
        "graph_ast_m1_summary":graph_summary_path,
        "m1_smoke_curves":m1_curve_path,
        "m2_smoke_member_curves":m2_members_path,
        "m2_smoke_predictions":m2_pred_path,
        "m3_production_B1400_allocation_probe":production_alloc_path,
        "m3_smoke_B28_allocation":smoke_alloc_path,
        "m3_smoke_member_curves":m3_members_path,
        "m3_smoke_predictions":m3_pred_path,
        "global_freeze_probe":global_probe,
    }
    manifest={
        "status":"FROZEN_PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS",
        "stage_id":"ENGINEERING_SMOKE_V3B_GRAPH_ADAPTER",
        "protocol_version":"PHASE5_GRAPH_PREDICTION_V3B_2026-10-06",
        "scientific_evidence":False,
        "graph_prediction_contract_sha256":sha256_file(CFG),
        "v3_seed_registry_sha256":sha256_file(SEEDS_V3),
        "v3b_selection_audit_sha256":sha256_file(audit_path),
        "inputs":{
            "real_frozen_v3b_provider_models_used":True,
            "real_frozen_step0_queries_used":True,
            "world_exercised":WORLD,
            "all_four_graph_asts_exercised_with_M1":True,
            "M2_joint_members_exercised":27,
            "M3_retained_members_exercised":14,
            "M3_production_allocation_derived_not_simulated":True,
            "M3_smoke_budget":SMOKE_M3_BUDGET,
            "final_WB_read":False,
            "hidden_provider_parameters_read":False,
            "scientific_graph_seeds_used":False,
        },
        "seed_banks":{
            "engineering_smoke_seed_base":smoke_base,
            "scientific_M1_M2_bank_not_used":"56900..56999",
            "scientific_M3_rank_streams_not_used":"7000000 + rank blocks",
        },
        "checks":{
            "m0_path_exercised":True,
            "m1_real_selection_all_four_graphs":True,
            "m2_27_member_equal_weight_aggregation":True,
            "m3_real_top14_support":True,
            "m3_production_B1400_allocation_sums_to_1400":True,
            "m3_smoke_allocation_sums_to_28":True,
            "m3_nested_top1_top3_top14_readouts":True,
            "global_freeze_12_predicted_plus_4_gate_failed_logic":True,
            "manifest_hash_production":True,
            "final_WB_firewall_preserved":True,
        },
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "started_utc":started,
        "completed_utc":utc_now_iso(),
    }
    manifest_path=output/"phase5_v3b_graph_adapter_smoke_manifest.json"
    write_json(manifest_path,manifest)
    reloaded=read_json(manifest_path)
    if reloaded.get("status")!="FROZEN_PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS":
        raise RuntimeError("smoke manifest round-trip failed")
    for key,path in outputs.items():
        if sha256_file(path)!=manifest["output_hashes_sha256"][key]:
            raise RuntimeError(f"smoke output hash changed: {key}")

    print("PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS")
    for key,val in manifest["checks"].items():
        print(key,val)
    print("scientific_evidence False")
    print("final_WB_read False")
    print("manifest",manifest_path)


def main()->None:
    p=argparse.ArgumentParser(description="Run the real non-scientific V3b graph-adapter smoke")
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--reset",action="store_true")
    args=p.parse_args()
    run(args.output,reset=bool(args.reset))


if __name__=="__main__":
    main()
