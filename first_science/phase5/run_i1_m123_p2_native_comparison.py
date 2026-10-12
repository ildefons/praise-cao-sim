"""Matched native-budget M1/M2 predictions for frozen P2 G_PAR I1-M3 pilot.

M1 = V3b best N100-I1-RMSE candidate/provider (100 graph trajectories).
M2 = V3b top3/provider, 27 equal-weight joint models (100 each).
M3 was already frozen separately, B=1400. Same query geometry/horizons.
This file never reads any white-box evidence. Resumable native ledgers.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import run_phase5_graph_prediction_v3b_fullsupport as engine
from phase5_runtime_v2 import load_phase5_contracts, graph_record, sha256_file

HERE=Path(__file__).resolve().parent
ROOT=HERE/"results"/"i1_m3_p2_induced_pilot"/"P2__G_PAR"
OUT=ROOT/"m1_m2_native_comparison"
QUERIES=ROOT/"public_induced_queries.csv"
M3FREEZE=ROOT/"prediction_manifest.json"
WORLD="P2"
GRAPH="G_PAR"
SEED_START=11_000_000
N=100
H=[float(h) for h in range(0,241,5)]


def prerequisite():
    if not M3FREEZE.is_file():
        raise FileNotFoundError("M3 prediction freeze missing")
    manifest=json.loads(M3FREEZE.read_text())
    if manifest.get("status")!="FROZEN_P2_I1_M3_INDUCED_GRAPH_PREDICTION":
        raise RuntimeError("unexpected M3 prediction status")
    if sha256_file(QUERIES)!=manifest["files"]["queries"]:
        raise RuntimeError("public query file changed after M3 prediction freeze")
    q=pd.read_csv(QUERIES)
    if len(q)!=5 or q.query_id.nunique()!=5:
        raise RuntimeError("expected five public induced queries")
    return q


def run(workers:int,dry_run:bool):
    q=prerequisite()
    contracts=load_phase5_contracts(HERE)
    graph=graph_record(contracts,GRAPH)
    variants=engine._m2_variants(WORLD)
    m1=engine._m1_surrogates(WORLD)
    seeds=list(range(SEED_START,SEED_START+N))
    if len(variants)!=27:
        raise RuntimeError("expected 27 M2 variants")
    if dry_run:
        print("P2_G_PAR_M1_M2_PREFLIGHT_PASS")
        print("queries=5 horizons=49 M1=100 M2=27x100 trajectories")
        print("seed bank=11000000..11000099 (reused for M1/M2 as CRN)")
        return
    OUT.mkdir(parents=True,exist_ok=True)
    freeze=OUT/"prediction_manifest.json"
    if freeze.exists():
        raise FileExistsError(f"already frozen: {freeze}")
    payloads=[engine._simulation_payload(
        cell_root=OUT,graph_id=GRAPH,graph_ast=graph["ast"],
        variant_id="M1",surrogates=m1,seeds=seeds,
        ledger_path=OUT/"ledgers"/"M1.csv",contracts=contracts,
    )]
    for variant in variants:
        rank=int(variant["rank"])
        payloads.append(engine._simulation_payload(
            cell_root=OUT,graph_id=GRAPH,graph_ast=graph["ast"],
            variant_id=f"M2_R{rank:02d}",surrogates=variant["surrogates"],
            seeds=seeds,ledger_path=OUT/"ledgers"/f"M2_R{rank:02d}.csv",
            contracts=contracts,
        ))
    engine._execute_payloads(payloads,workers=workers,label="P2 G_PAR M1/M2 native")
    m1ledger=engine._validate_complete_ledger(OUT/"ledgers"/"M1.csv",seeds)
    m1ids={
        p:str(pd.read_csv(engine.V3B_ROOT/WORLD/p/"m1_provider_model.csv").iloc[0].candidate_id)
        for p in engine.PROVIDERS
    }
    m1members=engine._member_curves(
        ledger=m1ledger,queries=q,horizons=H,method_id="M1",
        rank=1,graph_n=N,joint_weight=1.0,candidate_ids=m1ids,
    )
    m1out=engine._m1_predictions(m1members)
    m2rows=[]
    for v in variants:
        rank=int(v["rank"])
        ledger=engine._validate_complete_ledger(
            OUT/"ledgers"/f"M2_R{rank:02d}.csv",seeds,
        )
        m2rows.append(engine._member_curves(
            ledger=ledger,queries=q,horizons=H,method_id="M2_MEMBER",
            rank=rank,graph_n=N,joint_weight=1.0/27.0,
            candidate_ids=v["candidate_ids"],
        ))
    m2members=pd.concat(m2rows,ignore_index=True)
    m2out=engine._m2_predictions(m2members)
    frames={
        "m1_predictions.csv":m1out,
        "m2_member_curves.csv":m2members,
        "m2_predictions.csv":m2out,
    }
    for name,df in frames.items():
        df.to_csv(OUT/name,index=False)
    record={
        "status":"FROZEN_P2_G_PAR_MATCHED_QUERY_M1_M2_NATIVE_PREDICTIONS",
        "whitebox_read":False,
        "provider_world_id":WORLD,"graph_id":GRAPH,
        "selection":"V3b common-N100 RMSE-ranked provider reconstructions",
        "native_graph_budgets":{"M1":100,"M2":2700,"M3_existing":1400},
        "common_query_sha256":sha256_file(QUERIES),
        "m3_prediction_manifest_sha256":sha256_file(M3FREEZE),
        "seed_start":SEED_START,"seed_end":SEED_START+N-1,
        "output_sha256":{name:sha256_file(OUT/name) for name in frames},
        "ledger_sha256":{
            p.name:sha256_file(p) for p in sorted((OUT/"ledgers").glob("*.csv"))
        },
    }
    freeze.write_text(json.dumps(record,indent=2)+"\n")
    print("P2_G_PAR_M1_M2_NATIVE_PREDICTIONS_FROZEN")
    print("M1=100 M2=2700; M3 existing=1400")


def main():
    ap=argparse.ArgumentParser()
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run",action="store_true")
    g.add_argument("--run",action="store_true")
    ap.add_argument("--workers",type=int,default=3)
    args=ap.parse_args()
    if args.workers<1:raise ValueError("workers must be >=1")
    run(args.workers,args.dry_run)

if __name__=="__main__":
    main()
