"""Final untouched graph white-box execution for Phase-5 V3b FULL343.

This stage is unlocked only by the completed, hash-frozen global blind-
prediction manifest.  It generates the final N=1000 graph-level reference for
the 12 eligible physical cells using seeds 54000..54999.  P2 remains excluded
because all four P2 cells failed the prospective Step-0 confirmation gate.

One native physical ledger per eligible provider-world x graph cell is reused
to score all 15 already-frozen queries over H=0,5,...,240.  Pointwise
uncertainty is a Wilson 95% binomial interval over trajectory-level SLA
pass/fail outcomes.

The runner is resumable at trajectory granularity and refuses to alter a cell
once its final_wb_manifest.json is frozen.
"""
from __future__ import annotations

import argparse
import concurrent.futures
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
PHASE1=FIRST_SCIENCE/"phase1"
PHASE2=FIRST_SCIENCE/"phase2"
for p in (PHASE1,PHASE2):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from sla_compliance_analysis import (  # noqa:E402
    SlaComplianceDefinition,
    calculate_empirical_sla_sigma_from_ledgers,
)
from i1_provider_card import wilson_binomial_interval  # noqa:E402

from phase5_graph_simulator_v2 import (  # noqa:E402
    GraphProviderSurrogate,
    execute_one_phase5_graph_trajectory,
)
from phase5_runtime_v2 import (  # noqa:E402
    canonical_graph_ids,
    canonical_provider_world_ids,
    git_head,
    graph_record,
    load_phase5_contracts,
    physical_cell_id,
    provider_world,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

CFG=HERE/"config_phase5_final_wb_v3b_fullsupport.json"
GRAPH_CFG=HERE/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"
PRED_ROOT=HERE/"results"/"04_prediction_v3b_fullsupport"
GLOBAL_PRED_FREEZE=PRED_ROOT/"phase5_v3b_fullsupport_global_prediction_freeze_manifest.json"
STEP0_ROOT=HERE/"results"/"02_step0"
ROOT=HERE/"results"/"05_final_wb_v3b_fullsupport"

EXPECTED_CFG="FROZEN_PHASE5_FINAL_WB_EXECUTION_V3B_FULLSUPPORT"
EXPECTED_GLOBAL="FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"
FROZEN_CELL="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_CELL"
FROZEN_BATTERY="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
TOL=1e-12


def _wb_seeds()->list[int]:
    cfg=read_json(CFG)
    block=cfg["whitebox_generation"]["seeds"]
    seeds=list(range(int(block["start"]),int(block["end_inclusive"])+1))
    if len(seeds)!=int(block["n"]) or seeds[0]!=54000 or seeds[-1]!=54999:
        raise RuntimeError("final-WB seed bank changed")
    if len(seeds)!=1000:
        raise RuntimeError("final-WB N changed")
    return seeds


def _horizons()->list[float]:
    spec=read_json(CFG)["scope"]["horizons"]
    vals=np.arange(
        float(spec["start_seconds"]),
        float(spec["end_inclusive_seconds"])+0.5*float(spec["step_seconds"]),
        float(spec["step_seconds"]),
        dtype=float,
    ).tolist()
    if len(vals)!=49 or vals[0]!=0.0 or vals[-1]!=240.0:
        raise RuntimeError("final-WB horizon grid changed")
    return vals


def _unlock_and_eligibility()->pd.DataFrame:
    cfg=read_json(CFG)
    seeds=read_json(SEEDS)
    graph_cfg=read_json(GRAPH_CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected final-WB contract status")
    if seeds.get("status")!="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT":
        raise RuntimeError("unexpected full-support seed registry")
    if graph_cfg.get("status")!="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT":
        raise RuntimeError("unexpected full-support graph-prediction contract")

    global_freeze=read_json(GLOBAL_PRED_FREEZE)
    if global_freeze.get("status")!=EXPECTED_GLOBAL:
        raise RuntimeError("final WB is locked: global blind-prediction freeze missing")
    if global_freeze.get("complete") is not True:
        raise RuntimeError("final WB is locked: prediction freeze incomplete")
    if global_freeze.get("final_WB_read") is not False:
        raise RuntimeError("global prediction manifest does not preserve pre-WB firewall")
    predicted=list(global_freeze.get("prediction_frozen_cells",[]))
    failed=list(global_freeze.get("gate_failed_step0_cells",[]))
    if len(predicted)!=12 or len(failed)!=4:
        raise RuntimeError("global prediction freeze is not exact 12+4 coverage")

    # Re-hash every frozen blind-prediction manifest before opening WB.  This
    # makes the irreversible prediction/WB boundary mechanically explicit.
    stored=dict(global_freeze.get("prediction_manifest_sha256",{}))
    if set(stored)!=set(predicted):
        raise RuntimeError("global prediction freeze manifest-hash set mismatch")
    for cell in predicted:
        path=PRED_ROOT/cell/"prediction_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha256_file(path)!=str(stored[cell]):
            raise RuntimeError(f"{cell}: blind prediction manifest changed after global freeze")
        payload=read_json(path)
        if payload.get("status")!="FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION":
            raise RuntimeError(f"{cell}: blind prediction manifest status changed")
        if payload.get("inputs",{}).get("final_WB_read") is not False:
            raise RuntimeError(f"{cell}: prediction manifest WB-firewall flag invalid")

    eligibility=pd.read_csv(STEP0_ROOT/"phase5_step0_eligibility.csv")
    if len(eligibility)!=16:
        raise RuntimeError("Step-0 eligibility map must contain 16 cells")
    expected_pred=set(
        eligibility.loc[
            eligibility["eligibility"].astype(str)=="ELIGIBLE",
            "physical_cell_id"
        ].astype(str)
    )
    expected_fail=set(
        eligibility.loc[
            eligibility["eligibility"].astype(str)=="GATE_FAILED_STEP0",
            "physical_cell_id"
        ].astype(str)
    )
    if expected_pred!=set(predicted) or expected_fail!=set(failed):
        raise RuntimeError("global prediction freeze does not match frozen Step-0 eligibility")
    if len(expected_pred)!=12 or len(expected_fail)!=4:
        raise RuntimeError("expected 12 eligible and 4 gate-failed cells")
    if set(
        eligibility.loc[
            eligibility["eligibility"].astype(str)=="GATE_FAILED_STEP0",
            "provider_world_id"
        ].astype(str)
    )!={"P2"}:
        raise RuntimeError("expected all Step-0 gate failures to be P2")
    return eligibility


def _queries(cell:str)->pd.DataFrame:
    path=STEP0_ROOT/cell/"step0_frozen_queries.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    cols=[
        "query_id","provider_world_id","graph_id","rho_label","rho","regime",
        "scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status",
    ]
    q=pd.read_csv(path,usecols=cols)
    if len(q)!=15 or q["query_id"].astype(str).nunique()!=15:
        raise RuntimeError(f"{cell}: expected 15 unique frozen queries")
    if set(q["step0_cell_status"].astype(str))!={"FROZEN_PHASE5_STEP0_PASS_V2"}:
        raise RuntimeError(f"{cell}: query file is not frozen Step-0 PASS")
    return q.sort_values(["rho","regime"],kind="mergesort").reset_index(drop=True)


def _hidden_surrogates(contracts,world_id:str)->dict[str,GraphProviderSurrogate]:
    """Materialize the frozen hidden generating world, now that WB is unlocked."""
    world=provider_world(contracts,world_id)
    family=contracts.battery["provider_family"]
    ipt=float(family["effective_IPT"])
    x=float(family["execution_fraction_x"])
    cv=float(family["instruction_cv"])
    rate=float(family["cost_rate"])
    out={
        p:GraphProviderSurrogate(
            mean_service_time=float(world["provider_means"][p])*x/ipt,
            cost_rate=rate,
            service_cv=cv,
        )
        for p in PROVIDERS
    }
    if set(out)!=set(PROVIDERS):
        raise RuntimeError(f"{world_id}: hidden WB provider set changed")
    return out


def _checkpoint(cell_root:Path,seed:int)->Path:
    return cell_root/"checkpoints"/f"seed_{int(seed)}.csv"


def _simulate_cell_ledger(
    *,
    world_id:str,
    graph_id:str,
    cell_root:Path,
)->tuple[pd.DataFrame,float]:
    ledger_path=cell_root/"final_wb_ledger.csv"
    seeds=_wb_seeds()
    if ledger_path.is_file():
        ledger=pd.read_csv(ledger_path)
        actual=sorted(ledger["trajectory_seed"].astype(int).unique().tolist())
        if actual!=seeds or int(ledger["trajectory"].nunique())!=1000:
            raise RuntimeError(f"{world_id}/{graph_id}: cached final-WB ledger seed mismatch")
        return ledger,0.0

    contracts=load_phase5_contracts(HERE)
    graph=graph_record(contracts,graph_id)
    family=contracts.battery["provider_family"]
    inv=dict(contracts.battery["graph_invariants"])
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    surrogates=_hidden_surrogates(contracts,world_id)

    started=time.perf_counter()
    completed=sum(1 for seed in seeds if _checkpoint(cell_root,seed).is_file())
    if completed:
        print(
            f"{world_id}__{graph_id} FINAL_WB resume {completed}/1000",
            flush=True,
        )

    newly=0
    for ordinal,seed in enumerate(seeds):
        cp=_checkpoint(cell_root,seed)
        if cp.is_file():
            continue
        cp.parent.mkdir(parents=True,exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",FutureWarning)
            one,_=execute_one_phase5_graph_trajectory(
                graph_id=graph_id,
                graph_ast=graph["ast"],
                provider_surrogates=surrogates,
                graph_invariants=inv,
                workload_period=float(contracts.battery["workload"]["period_seconds"]),
                stop_time=float(contracts.battery["horizon"]["maximum_seconds"]),
                trajectory_seed=int(seed),
                canonical_ipt=float(family["effective_IPT"]),
                execution_fraction=float(family["execution_fraction_x"]),
            )
        one.insert(0,"trajectory",int(ordinal))
        one.insert(1,"trajectory_seed",int(seed))
        tmp=cp.with_suffix(".tmp")
        one.to_csv(tmp,index=False)
        tmp.replace(cp)
        newly+=1
        completed_now=sum(1 for s in seeds if _checkpoint(cell_root,s).is_file())
        if newly==1 or completed_now%50==0 or completed_now==1000:
            elapsed=time.perf_counter()-started
            sec_per=elapsed/max(1,newly)
            eta=sec_per*(1000-completed_now)
            print(
                f"{world_id}__{graph_id} FINAL_WB {completed_now}/1000 | "
                f"elapsed={elapsed/60:.1f} min | avg={sec_per:.2f} s/traj | "
                f"ETA={eta/60:.1f} min",
                flush=True,
            )

    parts=[]
    for ordinal,seed in enumerate(seeds):
        cp=_checkpoint(cell_root,seed)
        if not cp.is_file():
            raise RuntimeError(f"{world_id}/{graph_id}: missing checkpoint seed={seed}")
        one=pd.read_csv(cp)
        if set(one["trajectory"].astype(int))!={ordinal}:
            raise RuntimeError(f"{world_id}/{graph_id}: trajectory ordinal mismatch seed={seed}")
        if set(one["trajectory_seed"].astype(int))!={seed}:
            raise RuntimeError(f"{world_id}/{graph_id}: trajectory seed mismatch seed={seed}")
        parts.append(one)
    ledger=pd.concat(parts,ignore_index=True)
    if int(ledger["trajectory"].nunique())!=1000:
        raise RuntimeError(f"{world_id}/{graph_id}: final-WB ledger trajectory count !=1000")
    if ledger[["trajectory","request_id"]].duplicated().any():
        raise RuntimeError(f"{world_id}/{graph_id}: duplicate trajectory/request_id")
    tmp=ledger_path.with_suffix(".tmp")
    ledger.to_csv(tmp,index=False)
    tmp.replace(ledger_path)
    ck=cell_root/"checkpoints"
    if ck.exists():
        shutil.rmtree(ck)
    return ledger,float(time.perf_counter()-started)


def _score_queries(ledger:pd.DataFrame,queries:pd.DataFrame)->pd.DataFrame:
    horizons=_horizons()
    rows=[]
    for q in queries.itertuples(index=False):
        definition=SlaComplianceDefinition(
            rho=float(q.rho),
            accounting_origin=0.0,
            zero_decision_compliance=1.0,
        )
        sigma,trajectory_curves,_=calculate_empirical_sla_sigma_from_ledgers(
            ledger,
            latency_threshold=float(q.A_G_l_max),
            cost_threshold=float(q.A_G_c_max),
            quality_threshold=float(q.A_G_q_min),
            horizons=horizons,
            stop_time=240.0,
            sla_definition=definition,
        )
        counts=(
            trajectory_curves.groupby("horizon",as_index=False)
            .agg(
                n_success=("sla_compliant","sum"),
                wb_n=("sla_compliant","count"),
            )
            .sort_values("horizon",kind="mergesort")
            .reset_index(drop=True)
        )
        merged=sigma[["horizon","sigma"]].merge(
            counts,on="horizon",how="inner",validate="one_to_one"
        )
        if len(merged)!=49 or set(merged["wb_n"].astype(int))!={1000}:
            raise RuntimeError(f"{q.query_id}: final-WB point count/N mismatch")
        for rec in merged.itertuples(index=False):
            successes=int(rec.n_success)
            n=int(rec.wb_n)
            lo,hi=wilson_binomial_interval(successes,n)
            sigma_wb=float(rec.sigma)
            if abs(sigma_wb-successes/n)>1e-12:
                raise RuntimeError(f"{q.query_id}: sigma/count inconsistency")
            rows.append({
                "query_id":str(q.query_id),
                "provider_world_id":str(q.provider_world_id),
                "graph_id":str(q.graph_id),
                "rho_label":str(q.rho_label),
                "rho":float(q.rho),
                "regime":str(q.regime),
                "H":float(rec.horizon),
                "sigma_wb":sigma_wb,
                "wb_n":n,
                "wb_successes":successes,
                "wb_ci_lower":float(lo),
                "wb_ci_upper":float(hi),
                "A_G_l_max":float(q.A_G_l_max),
                "A_G_c_max":float(q.A_G_c_max),
                "A_G_q_min":float(q.A_G_q_min),
            })
    out=pd.DataFrame(rows).sort_values(
        ["query_id","H"],kind="mergesort"
    ).reset_index(drop=True)
    if len(out)!=15*49:
        raise RuntimeError("final-WB curve table row count !=735")
    return out


def _run_cell(world_id:str,graph_id:str)->dict[str,Any]:
    cell=physical_cell_id(world_id,graph_id)
    root=ROOT/cell
    manifest_path=root/"final_wb_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")==FROZEN_CELL:
            return {
                "physical_cell_id":cell,
                "provider_world_id":world_id,
                "graph_id":graph_id,
                "status":"FROZEN_CACHED",
                "wall_seconds":0.0,
            }
        raise RuntimeError(f"{cell}: existing final-WB manifest has unexpected status")

    started_utc=utc_now_iso()
    wall=time.perf_counter()
    root.mkdir(parents=True,exist_ok=True)
    queries_path=STEP0_ROOT/cell/"step0_frozen_queries.csv"
    queries=_queries(cell)
    ledger,sim_seconds=_simulate_cell_ledger(
        world_id=world_id,graph_id=graph_id,cell_root=root
    )
    curves=_score_queries(ledger,queries)

    ledger_path=root/"final_wb_ledger.csv"
    curves_path=root/"final_wb_curves.csv"
    curves.to_csv(curves_path,index=False)
    pred_manifest=PRED_ROOT/cell/"prediction_manifest.json"
    global_pred=read_json(GLOBAL_PRED_FREEZE)

    manifest={
        "status":FROZEN_CELL,
        "stage_id":"FINAL_WB_V3B_FULLSUPPORT",
        "protocol_version":"PHASE5_FINAL_WB_V3B_FULLSUPPORT_2026-10-07",
        "scientific_evidence":True,
        "provider_world_id":world_id,
        "graph_id":graph_id,
        "physical_cell_id":cell,
        "code_commit":git_head(),
        "final_wb_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "global_prediction_freeze_sha256":sha256_file(GLOBAL_PRED_FREEZE),
        "frozen_prediction_manifest_sha256":sha256_file(pred_manifest),
        "step0_frozen_queries_sha256":sha256_file(queries_path),
        "inputs":{
            "query_count":15,
            "horizon_count":49,
            "whitebox_n":1000,
            "hidden_generating_world_used":True,
            "prediction_used_to_generate_WB":False,
            "method_repair_allowed":False,
            "query_reselection_allowed":False,
            "global_prediction_freeze_complete_before_open":bool(global_pred.get("complete")),
        },
        "seed_banks":{
            "final_whitebox":{"start":54000,"end_inclusive":54999,"n":1000}
        },
        "outputs":{
            "final_wb_ledger":str(ledger_path),
            "final_wb_curves":str(curves_path),
        },
        "output_hashes_sha256":{
            "final_wb_ledger":sha256_file(ledger_path),
            "final_wb_curves":sha256_file(curves_path),
        },
        "simulation_wall_seconds":float(sim_seconds),
        "python_wall_seconds":float(time.perf_counter()-wall),
        "started_utc":started_utc,
        "completed_utc":utc_now_iso(),
    }
    write_json(manifest_path,manifest)
    print(
        f"PHASE5_V3B_FULLSUPPORT_FINAL_WB_CELL_PASS {cell} | "
        f"N=1000 queries=15 points={len(curves)} | "
        f"wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {
        "physical_cell_id":cell,
        "provider_world_id":world_id,
        "graph_id":graph_id,
        "status":FROZEN_CELL,
        "wall_seconds":float(manifest["python_wall_seconds"]),
    }


def _freeze_battery(eligibility:pd.DataFrame)->Path:
    rows=[]
    manifest_hashes={}
    for rec in eligibility.sort_values(
        ["provider_world_id","graph_id"],kind="mergesort"
    ).itertuples(index=False):
        cell=str(rec.physical_cell_id)
        if str(rec.eligibility)=="GATE_FAILED_STEP0":
            rows.append({
                "physical_cell_id":cell,
                "provider_world_id":str(rec.provider_world_id),
                "graph_id":str(rec.graph_id),
                "final_wb_status":"GATE_FAILED_STEP0_NO_FINAL_WB",
            })
            continue
        path=ROOT/cell/"final_wb_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        m=read_json(path)
        if m.get("status")!=FROZEN_CELL:
            raise RuntimeError(f"{cell}: final-WB cell is not frozen")
        manifest_hashes[cell]=sha256_file(path)
        rows.append({
            "physical_cell_id":cell,
            "provider_world_id":str(rec.provider_world_id),
            "graph_id":str(rec.graph_id),
            "final_wb_status":FROZEN_CELL,
        })
    if len(manifest_hashes)!=12:
        raise RuntimeError("final-WB battery freeze expected 12 frozen cell manifests")

    status=pd.DataFrame(rows)
    status_path=ROOT/"phase5_v3b_fullsupport_final_wb_status.csv"
    status.to_csv(status_path,index=False)
    manifest={
        "status":FROZEN_BATTERY,
        "stage_id":"FINAL_WB_BATTERY_FREEZE_V3B_FULLSUPPORT",
        "protocol_version":"PHASE5_FINAL_WB_V3B_FULLSUPPORT_2026-10-07",
        "scientific_evidence":True,
        "code_commit":git_head(),
        "final_wb_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "global_prediction_freeze_sha256":sha256_file(GLOBAL_PRED_FREEZE),
        "eligible_final_wb_cells":sorted(manifest_hashes),
        "gate_failed_step0_cells":sorted(
            status.loc[
                status["final_wb_status"]=="GATE_FAILED_STEP0_NO_FINAL_WB",
                "physical_cell_id"
            ].astype(str).tolist()
        ),
        "final_wb_manifest_sha256":manifest_hashes,
        "complete":True,
        "evaluation_unlocked":True,
        "outputs":{"final_wb_status":str(status_path)},
        "output_hashes_sha256":{"final_wb_status":sha256_file(status_path)},
        "completed_utc":utc_now_iso(),
    }
    path=ROOT/"phase5_v3b_fullsupport_final_wb_freeze_manifest.json"
    write_json(path,manifest)
    print("PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY_FREEZE_PASS")
    print("eligible_final_wb_cells 12")
    print("gate_failed_step0_cells 4")
    print("evaluation_unlocked True")
    print("manifest",path)
    return path


def main()->None:
    p=argparse.ArgumentParser(description="Run final N=1000 V3b FULL343 graph white-box reference")
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-cells",action="store_true")
    group.add_argument("--cell",type=str)
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")

    eligibility=_unlock_and_eligibility()
    eligible=eligibility[
        eligibility["eligibility"].astype(str)=="ELIGIBLE"
    ].sort_values(["provider_world_id","graph_id"],kind="mergesort")
    if len(eligible)!=12:
        raise RuntimeError("expected exactly 12 eligible final-WB cells")

    if args.cell:
        match=eligible[
            eligible["physical_cell_id"].astype(str)==str(args.cell)
        ]
        if len(match)!=1:
            raise RuntimeError(f"{args.cell}: not exactly one eligible final-WB cell")
        rec=match.iloc[0]
        _run_cell(str(rec["provider_world_id"]),str(rec["graph_id"]))
        return

    tasks=[
        (str(r.provider_world_id),str(r.graph_id))
        for r in eligible.itertuples(index=False)
    ]
    wall=time.perf_counter()
    results=[]
    if args.workers==1:
        for world,graph in tasks:
            results.append(_run_cell(world,graph))
            print(
                f"FINAL_WB BATTERY PROGRESS {len(results)}/12 | "
                f"elapsed={(time.perf_counter()-wall)/3600:.2f} h",
                flush=True,
            )
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
            future_map={
                ex.submit(_run_cell,world,graph):(world,graph)
                for world,graph in tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                world,graph=future_map[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    for other in future_map:
                        other.cancel()
                    raise RuntimeError(f"{world}/{graph}: final-WB worker failed") from exc
                print(
                    f"FINAL_WB BATTERY PROGRESS {len(results)}/12 | "
                    f"elapsed={(time.perf_counter()-wall)/3600:.2f} h",
                    flush=True,
                )
    _freeze_battery(eligibility)


if __name__=="__main__":
    main()
