"""Graph propagation of the frozen Phase-6 I2b-v1 M2 support on P4/G_SEQPAR."""
from __future__ import annotations

import argparse
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

CFG=HERE/"config_phase6_i2b_m2_p4_g_seqpar_v1.json"
RECON=HERE/"results"/"24_i2b_energy_reconstruction_p4"
P5_GRAPH_CFG=PHASE5/"config_phase5_graph_prediction_v3b_fullsupport.json"
P5_SEEDS=PHASE5/"config_phase5_seed_registry_v3b_fullsupport.json"
ROOT=HERE/"results"/"25_i2b_m2_p4_g_seqpar"

WORLD="P4"
GRAPH="G_SEQPAR"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED="FROZEN_PHASE6_I2B_M2_P4_G_SEQPAR_V1"


def _surrogate(row)->GraphProviderSurrogate:
    def value(name:str):
        if hasattr(row,name):
            return getattr(row,name)
        return row[name]
    return GraphProviderSurrogate(
        mean_service_time=float(value("mean_service_time")),
        cost_rate=float(value("cost_rate")),
        service_cv=float(value("service_cv")),
    )


def run(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")

    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected I2b-M2 graph contract")

    recon_manifest=RECON/"p4_i2b_energy_reconstruction_manifest.json"
    if not recon_manifest.is_file():
        raise FileNotFoundError("run I2b reconstruction first")
    rm=read_json(recon_manifest)
    if rm.get("status")!="PHASE6_I2B_ENERGY_P4_RECONSTRUCTION_COMPLETE":
        raise RuntimeError("I2b reconstruction not frozen complete")

    ROOT.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/"prediction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_I2B_M2_P4_G_SEQPAR_PREDICTION_COMPLETE":
            print("PHASE6_I2B_M2_P4_G_SEQPAR_CACHED")
            return manifest_path
        raise RuntimeError("unexpected existing I2b prediction manifest")

    contracts=load_phase5_contracts(PHASE5)
    graph=graph_record(contracts,GRAPH)
    cell=physical_cell_id(WORLD,GRAPH)
    queries=_query_definitions(cell)
    horizons=_horizons(read_json(P5_GRAPH_CFG))

    candidates={}
    for provider in PROVIDERS:
        t=pd.read_csv(RECON/provider/"i2b_m2_provider_models.csv")
        if len(t)!=3:
            raise RuntimeError(f"{provider}: I2b M2 provider support !=3")
        candidates[provider]={
            str(r.candidate_id):_surrogate(r)
            for r in t.itertuples(index=False)
        }

    support=pd.read_csv(RECON/"m2_joint_support_27.csv").sort_values("joint_rank")
    if len(support)!=27:
        raise RuntimeError("I2b M2 joint support !=27")

    seed_cfg=read_json(P5_SEEDS)
    bank=seed_cfg["graph_prediction"]["M1_M2_common_bank"]
    seeds=list(range(int(bank["start"]),int(bank["end_inclusive"])+1))
    if len(seeds)!=100:
        raise RuntimeError("M2 graph seed bank !=100")

    ledgers=ROOT/"ledgers"
    ledgers.mkdir(parents=True,exist_ok=True)

    variants=[]
    for rec in support.itertuples(index=False):
        ids={
            p:str(getattr(rec,f"{p}_candidate_id"))
            for p in PROVIDERS
        }
        variants.append({
            "rank":int(rec.joint_rank),
            "candidate_ids":ids,
            "surrogates":{
                p:candidates[p][ids[p]]
                for p in PROVIDERS
            },
            "joint_weight":float(rec.joint_weight),
        })

    started=time.perf_counter()
    payloads=[]
    for v in variants:
        rank=v["rank"]
        payloads.append(_simulation_payload(
            cell_root=ROOT,
            graph_id=GRAPH,
            graph_ast=graph["ast"],
            variant_id=f"I2B_M2_R{rank:02d}",
            surrogates=v["surrogates"],
            seeds=seeds,
            ledger_path=ledgers/f"I2B_M2_R{rank:02d}.csv",
            contracts=contracts,
        ))

    _execute_payloads(
        payloads,
        workers=workers,
        label="PHASE6 I2B_M2 P4__G_SEQPAR",
    )

    frames=[]
    for v in variants:
        rank=v["rank"]
        ledger=_validate_complete_ledger(
            ledgers/f"I2B_M2_R{rank:02d}.csv",
            seeds,
        )
        frames.append(_member_curves(
            ledger=ledger,
            queries=queries,
            horizons=horizons,
            method_id="I2B_M2_MEMBER",
            rank=rank,
            graph_n=100,
            joint_weight=v["joint_weight"],
            candidate_ids=v["candidate_ids"],
        ))

    members=pd.concat(frames,ignore_index=True)
    members_path=ROOT/"i2b_m2_member_curves.csv"
    members.to_csv(members_path,index=False)

    pred=_m2_predictions(members)
    pred["method_id"]="I2B_M2"
    pred_path=ROOT/"i2b_m2_predictions.csv"
    pred.to_csv(pred_path,index=False)

    manifest={
        "status":"PHASE6_I2B_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
        "development_evidence":True,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "reconstruction_manifest_sha256":sha256_file(recon_manifest),
        "provider_world_id":WORLD,
        "graph_id":GRAPH,
        "joint_models":27,
        "trajectory_total":2700,
        "workers":workers,
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

    print("PHASE6_I2B_M2_P4_G_SEQPAR_PREDICTION_PASS")
    print("trajectory_total 2700")
    print(f"wall_minutes {manifest['wall_seconds']/60:.2f}")
    return manifest_path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    run(args.workers)


if __name__=="__main__":
    main()
