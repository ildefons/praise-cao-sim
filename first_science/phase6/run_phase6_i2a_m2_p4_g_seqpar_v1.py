"""Phase-6 single-cell I2a-M2 graph prediction for P4 / G_SEQPAR.

This is development evidence, not a new prospective battery. Provider selection
is frozen by the completed Phase-6 I2a provider-only audit. The graph run uses
exactly the Phase-5 M2 graph simulator semantics and common N=100 seed bank.
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
PHASE3=HERE.parent/"phase3"
for p in (PHASE5,PHASE3):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa:E402
from phase5_runtime_v2 import (  # noqa:E402
    graph_record, load_phase5_contracts, physical_cell_id,
    read_json, sha256_file, utc_now_iso, write_json, git_head,
)
from run_phase5_graph_prediction_v3b_fullsupport import (  # noqa:E402
    _execute_payloads, _horizons, _member_curves, _m2_predictions,
    _query_definitions, _simulation_payload, _validate_complete_ledger,
)

CFG=HERE/"config_phase6_i2a_m2_p4_g_seqpar_v1.json"
P5_GRAPH_CFG=PHASE5/"config_phase5_graph_prediction_v3b_fullsupport.json"
P5_SEEDS=PHASE5/"config_phase5_seed_registry_v3b_fullsupport.json"
I2A_ROOT=HERE/"results"/"01_i2a_marginal_audit"
ROOT=HERE/"results"/"02_i2a_m2_p4_g_seqpar"
WORLD="P4"
GRAPH="G_SEQPAR"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED="FROZEN_PHASE6_I2A_M2_P4_G_SEQPAR_DEVELOPMENT_V1"


def _surrogate(row)->GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _provider_top3():
    out={}
    for provider in PROVIDERS:
        path=I2A_ROOT/WORLD/provider/"i2a_top3_preview.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        t=pd.read_csv(path)
        if len(t)!=3 or t["candidate_id"].astype(str).nunique()!=3:
            raise RuntimeError(f"{provider}: expected exactly three I2a candidates")
        if "i2a_rank" in t.columns and t["i2a_rank"].astype(int).tolist()!=[1,2,3]:
            raise RuntimeError(f"{provider}: I2a Top3 ranks changed")
        out[provider]=t.reset_index(drop=True)
    return out


def run(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected Phase-6 I2a-M2 contract")

    ROOT.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/"i2a_m2_prediction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_I2A_M2_P4_G_SEQPAR_PREDICTION_COMPLETE":
            print("PHASE6_I2A_M2_P4_G_SEQPAR_CACHED")
            return manifest_path
        raise RuntimeError("unexpected existing Phase-6 prediction manifest")

    contracts=load_phase5_contracts(PHASE5)
    graph=graph_record(contracts,GRAPH)
    cell=physical_cell_id(WORLD,GRAPH)
    if cell!="P4__G_SEQPAR":
        raise RuntimeError(f"unexpected physical cell id {cell}")
    queries=_query_definitions(cell)
    horizons=_horizons(read_json(P5_GRAPH_CFG))

    seed_cfg=read_json(P5_SEEDS)
    bank=seed_cfg["graph_prediction"]["M1_M2_common_bank"]
    seeds=list(range(int(bank["start"]),int(bank["end_inclusive"])+1))
    if len(seeds)!=100:
        raise RuntimeError("frozen M1/M2 graph bank is not N=100")

    top3=_provider_top3()
    ledgers=ROOT/"ledgers"
    ledgers.mkdir(parents=True,exist_ok=True)
    variants=[]
    rank=0
    for ia,ib,ic in itertools.product(range(3),repeat=3):
        rank+=1
        rows={
            "ProviderA":top3["ProviderA"].iloc[ia],
            "ProviderB":top3["ProviderB"].iloc[ib],
            "ProviderC":top3["ProviderC"].iloc[ic],
        }
        variants.append({
            "rank":rank,
            "candidate_ids":{p:str(rows[p]["candidate_id"]) for p in PROVIDERS},
            "surrogates":{p:_surrogate(rows[p]) for p in PROVIDERS},
            "joint_weight":1.0/27.0,
        })
    if len(variants)!=27:
        raise RuntimeError("I2a-M2 joint support is not 27")

    started=time.perf_counter()
    payloads=[]
    for v in variants:
        rank=int(v["rank"])
        payloads.append(_simulation_payload(
            cell_root=ROOT,
            graph_id=GRAPH,
            graph_ast=graph["ast"],
            variant_id=f"I2A_M2_R{rank:02d}",
            surrogates=v["surrogates"],
            seeds=seeds,
            ledger_path=ledgers/f"I2A_M2_R{rank:02d}.csv",
            contracts=contracts,
        ))
    _execute_payloads(payloads,workers=workers,label="PHASE6 P4__G_SEQPAR I2A_M2")

    frames=[]
    for v in variants:
        rank=int(v["rank"])
        ledger=_validate_complete_ledger(ledgers/f"I2A_M2_R{rank:02d}.csv",seeds)
        frames.append(_member_curves(
            ledger=ledger,
            queries=queries,
            horizons=horizons,
            method_id="I2A_M2_MEMBER",
            rank=rank,
            graph_n=100,
            joint_weight=1.0/27.0,
            candidate_ids=v["candidate_ids"],
        ))
    members=pd.concat(frames,ignore_index=True)
    members_path=ROOT/"i2a_m2_member_curves.csv"
    members.to_csv(members_path,index=False)

    pred=_m2_predictions(members)
    pred["method_id"]="I2A_M2"
    pred_path=ROOT/"i2a_m2_predictions.csv"
    pred.to_csv(pred_path,index=False)

    manifest={
        "status":"PHASE6_I2A_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
        "development_evidence":True,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "provider_world_id":WORLD,
        "graph_id":GRAPH,
        "physical_cell_id":cell,
        "joint_models":27,
        "n_trajectories_per_joint_model":100,
        "trajectory_total":2700,
        "workers":int(workers),
        "graph_wb_read":False,
        "hidden_provider_parameters_read":False,
        "outputs":{
            "member_curves":str(members_path),
            "predictions":str(pred_path),
        },
        "output_hashes_sha256":{
            "member_curves":sha256_file(members_path),
            "predictions":sha256_file(pred_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    }
    write_json(manifest_path,manifest)
    print("PHASE6_I2A_M2_P4_G_SEQPAR_PREDICTION_PASS")
    print("trajectory_total 2700")
    print(f"wall_minutes {manifest['wall_seconds']/60:.2f}")
    print("output",ROOT)
    return manifest_path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    run(args.workers)


if __name__=="__main__":
    main()
