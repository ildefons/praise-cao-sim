#!/usr/bin/env python3
"""Disposable B0001 four-method graph adapter engineering smoke.

Calls the historical Phase-5 graph simulator and member-curve construction
for each of four frozen methods on P1/G_PAR, one DISPOSABLE trajectory each.
Also tests historical Top1 aggregation using a one-member/budget-one
engineering synthetic analogue, not a scientific prediction.

--check: only hashes and frozen source/model lookup, no simulations/writes.
--smoke: four engineering trajectories in a NEW isolated directory.
NEVER writes graph-prediction or WB/evaluation results. Scientific run blocked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PHASE5=REPO/"first_science"/"phase5"
WORLD="P1";GRAPH="G_PAR"
FAMILIES=("original","fixed_cv")
VARIANTS=("top14","top1")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
STATUS="B0001_FOUR_ARM_GRAPH_ADAPTER_ENGINEERING_SMOKE_PASS_SCIENCE_BLOCKED"
GATE_STATUS="B0001_FOUR_ARM_GRAPH_ISOLATION_PREFLIGHT_FROZEN_EXECUTION_BLOCKED"
SEEDS={
    "original/top14":39_200_001,
    "original/top1":39_200_002,
    "fixed_cv/top14":39_200_003,
    "fixed_cv/top1":39_200_004,
}


def require(ok,message):
    if not bool(ok):raise RuntimeError("B0001 four-arm graph smoke: "+message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def imports():
    for folder in (REPO/"first_science"/"phase2",
                   REPO/"first_science"/"phase3",
                   REPO/"first_science"/"phase4",
                   PHASE5,REPO/"first_science"/"b1"/"retrospective_m3"):
        if str(folder) not in sys.path:sys.path.insert(0,str(folder))
    import run_phase5_graph_prediction_v3b_fullsupport as graph
    from phase5_runtime_v2 import load_phase5_contracts,graph_record
    return graph,load_phase5_contracts,graph_record


def validate(a):
    for attr in ("gate","weights","staging"):
        source=getattr(a,attr)
        require(source.is_dir(),"Missing scientific source: "+str(source))
        require(source!=a.out and source not in a.out.parents
                and a.out not in source.parents,
                "Smoke output path overlaps scientific source")
    require(a.out!=REPO and REPO not in a.out.parents,
            "No outputs in Git checkout")
    gatefile=a.gate/"b0001_four_arm_graph_isolation_preflight.json"
    gate=read(gatefile)
    require(gate["status"]==GATE_STATUS and
            gate["engineering_graph_smoke_authorized"] is False and
            gate["scientific_graph_execution_authorized"] is False and
            gate["graph_simulations_executed"]==0 and
            gate["whitebox_reference_read"] is False,
            "Frozen graph isolation execution firewall invalid")
    weights=a.weights/"b0001_48_lhs_weight_and_support_freeze.json"
    stage=a.staging/"b0001_public_inputs_manifest.json"
    require(gate["weight_freeze_sha256"]==sha(weights)
            and gate["public_input_freeze_sha256"]==sha(stage),
            "Frozen scientific inputs differ from isolation gate")
    for rel,expected in gate["source_code_sha256"].items():
        require(sha(REPO/rel)==expected,
                "Original source changed after isolation preflight: "+rel)
    for family in FAMILIES:
        frozen=gate["world_supports_and_fresh_graph_seeds"][family+"/"+WORLD]
        support=Path(frozen["top14_support_path"])
        require(support==a.weights/family/WORLD/"support"/"top14_support.csv"
                and sha(support)==frozen["top14_support_sha256"],
                "Frozen Top14 support changed: "+family)
        t=pd.read_csv(support)
        require(len(t)==14 and int(t.n_trajectories.sum())==1400,
                "Invalid Top14 support budget")
        ids={p:str(t.iloc[0][p+"_candidate_id"]) for p in PROVIDERS}
        for p in PROVIDERS:
            weights_path=a.weights/family/WORLD/p/"provider_weights.csv"
            w=pd.read_csv(weights_path)
            require(ids[p] in set(w.candidate_id.astype(str)),
                    "Rank1 provider candidate missing")
    require(len(set(SEEDS.values()))==4
            and max(SEEDS.values())<39_500_000
            and min(SEEDS.values())>39_000_003,
            "Engineering seed stream collides with science")
    q=a.staging/"frozen_queries"/(WORLD+"__"+GRAPH)/"step0_frozen_queries.csv"
    require(q.is_file() and len(pd.read_csv(q))==15,
            "Invalid public query source")
    return gatefile,gate,weights,stage


def smoke(a,gatefile,gate,weightfile,stage):
    require(not a.out.exists(),"Refusing overwrite of graph smoke workspace")
    graph,load_contracts,graph_record=imports()
    contracts=load_contracts(PHASE5)
    gc=graph_record(contracts,GRAPH)
    cfg=read(PHASE5/"config_phase5_graph_prediction_v3b_fullsupport.json")
    horizons=graph._horizons(cfg)
    require(len(horizons)==49,"Historical graph horizon grid changed")
    # Historical predictor assumes old STEP0_ROOT; redirect only inside this
    # process, restoring the binding even on exceptions.
    old_step0=graph.STEP0_ROOT
    graph.STEP0_ROOT=a.staging/"frozen_queries"
    try:
        queries=graph._query_definitions(WORLD+"__"+GRAPH)
    finally:
        graph.STEP0_ROOT=old_step0
    require(len(queries)==15,"Public graph query interface mismatch")
    records={}
    for family in FAMILIES:
        support=pd.read_csv(a.weights/family/WORLD/"support"/"top14_support.csv")
        rank=support.iloc[0]
        ids={p:str(rank[p+"_candidate_id"]) for p in PROVIDERS}
        surrogates={}
        for p in PROVIDERS:
            w=pd.read_csv(a.weights/family/WORLD/p/"provider_weights.csv")
            t=w.loc[w.candidate_id.astype(str)==ids[p]]
            require(len(t)==1,"Missing unique frozen provider surrogate")
            surrogates[p]=graph._surrogate(t.iloc[0])
        for kind in VARIANTS:
            name=family+"/"+kind
            method=gate["world_supports_and_fresh_graph_seeds"][family+"/"+WORLD]["methods"][
                0 if kind=="top14" else 1]
            seed=SEEDS[name]
            cell=a.out/"engineering_only"/family/kind/(WORLD+"__"+GRAPH)
            payload=graph._simulation_payload(
                cell_root=cell,graph_id=GRAPH,graph_ast=gc["ast"],
                variant_id="ENGINEERING_"+family.upper()+"_"+kind.upper(),
                surrogates=surrogates,seeds=[seed],
                ledger_path=cell/"ledgers"/"one_trajectory.csv",
                contracts=contracts)
            require(payload["seeds"]==[seed] and
                    Path(payload["cell_root"])==cell and
                    Path(payload["ledger_path"]).is_relative_to(a.out),
                    "Graph payload not isolated")
            result=graph._simulate_variant_worker(payload)
            ledger=graph._validate_complete_ledger(
                Path(result["ledger_path"]),[seed])
            curves=graph._member_curves(
                ledger=ledger,queries=queries,horizons=horizons,
                method_id="ENGINEERING_ONLY",rank=1,graph_n=1,
                joint_weight=1.0,candidate_ids=ids)
            require(len(curves)==735
                    and curves["sigma_member"].between(0,1).all()
                    and set(curves["graph_n"])=={1},
                    "Original graph ledger/curves failed smoke")
            # Apply the original mathematical Top1 aggregation identity
            # to engineering-only data; no 1400-budget claim is made.
            members=curves.copy()
            members["alpha"]=1.0
            from run_pilot_m3_generalization_v1 import predictions
            aggregated=predictions(members,"ENGINEERING_ONLY_TOP1",1,1.0,1)
            require(len(aggregated)==735 and
                    aggregated["sigma_hat"].between(0,1).all()
                    and np.allclose(
                        members.sort_values(["query_id","H"])["sigma_member"].to_numpy(float),
                        aggregated.sort_values(["query_id","H"])["sigma_hat"].to_numpy(float),
                        atol=1e-12,rtol=0),
                    "Historical Top1 aggregation incompatible")
            records[method]={
                "family":family,"variant":kind,"seed":seed,
                "provider_candidate_ids":ids,
                "graph_ledger_sha256":sha(Path(result["ledger_path"])),
                "trajectory_count":1,"point_count":735,
                "original_graph_simulator_used":True,
                "original_aggregation_used":True,
                "scientific_prediction":False,
            }
            print("B0001_FOUR_ARM_ENGINEERING_CELL_PASS",method,
                  "one trajectory; 735 member/aggregate points",flush=True)
    manifest={
        "status":STATUS,"world":WORLD,"graph":GRAPH,
        "engineering_trajectories":4,
        "scientific_graph_simulations":0,
        "reference_whitebox_read":False,
        "old_graph_results_read":False,
        "historical_source_hashes":gate["source_code_sha256"],
        "graph_isolation_gate_sha256":sha(gatefile),
        "weight_freeze_sha256":sha(weightfile),
        "public_staging_manifest_sha256":sha(stage),
        "four_methods":records,
        "scientific_execution_authorized":False,
        "next_gate":"Independent execution audit, then graph runner full 48-method-cell implementation",
    }
    target=a.out/"engineering_only"/"b0001_four_arm_graph_smoke_manifest.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    require(not target.exists(),"Smoke manifest exists")
    target.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",
                      encoding="utf-8")
    print("B0001_FOUR_ARM_GRAPH_ADAPTER_ENGINEERING_SMOKE_PASS",flush=True)
    print("SCIENCE_GRAPH_EXECUTION_REMAINS_BLOCKED",flush=True)
    print("SMOKE",target,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("gate","weights","staging","out"):
        p.add_argument("--"+key,required=True,type=Path)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check",action="store_true")
    modes.add_argument("--smoke",action="store_true")
    a=p.parse_args()
    for key in ("gate","weights","staging","out"):
        setattr(a,key,getattr(a,key).expanduser().resolve())
    gatefile,gate,weightfile,stage=validate(a)
    print("B0001_FOUR_ARM_GRAPH_SMOKE_PREFLIGHT_PASS",
          "four frozen methods; engine hashes match",flush=True)
    if a.check:
        print("NO_SIMULATIONS / NO_WRITES / NO_WHITEBOX_READ",flush=True)
        return
    smoke(a,gatefile,gate,weightfile,stage)


if __name__=="__main__":
    main()
