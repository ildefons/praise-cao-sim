#!/usr/bin/env python3
"""B0001 four-arm graph ISOLATION preflight: NO simulations.

Audits the six previously frozen public-I1 48-LHS supports, B0001 frozen
graph queries, and original scientific graph engine code. Freezes a
source-hash-bound Top14/Top1 B=1400 allocation and a disjoint fresh graph
seed namespace per family (CRN across the four graphs / three worlds).
The runner is NOT authorized by this preflight; next gate is an isolated
one-trajectory engineering smoke and actual simulator equivalence checks.

Does not import a provider simulator or open any final white-box reference.
--check writes nothing; --freeze writes ONLY to fresh isolated output dir.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

REPO=Path(__file__).resolve().parents[3]
FAMILIES=("original","fixed_cv")
ROLES=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
ARM_IDS={
    "original":("ORIGINAL_TOP14_B1400","ORIGINAL_TOP1_B1400"),
    "fixed_cv":("FIXED_CV_TOP14","FIXED_CV_TOP1"),
}
BUDGET=1400
SUPPORT_STATUS="B0001_48_LHS_TWO_FAMILY_WEIGHTS_AND_TOP14_SUPPORT_FROZEN"
WORLD_STATUS="B0001_48_LHS_WORLD_PUBLIC_WEIGHT_AND_TOP14_FROZEN"
STAGING_STATUS="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE"
STATUS="B0001_FOUR_ARM_GRAPH_ISOLATION_PREFLIGHT_FROZEN_EXECUTION_BLOCKED"
MAX_NATIVE=(2**32-1-3)//100
# Each rank stream uses the same fixed seed window for all world/graph cases,
# as the historical graph pipeline does (paired CRN). Method families and
# Top1/Top14 are disjoint from each other and earlier B0001 graph/local banks.
BASE={
    "original":{"top14":39_500_000,"top1":39_600_000},
    "fixed_cv":{"top14":40_000_000,"top1":40_100_000},
}
RANK_STRIDE=2000
SCIENTIFIC_SOURCES=(
    "first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py",
    "first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py",
    "first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py",
    "first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py",
    "first_science/phase5/phase5_graph_simulator_v2.py",
    "first_science/phase5/phase5_runtime_v2.py",
    "first_science/phase5/config_phase5_graph_prediction_v3b_fullsupport.json",
    "first_science/b1/planb_validation/freeze_b0001_48_lhs_weights_v1.py",
    "first_science/b1/planb_validation/preflight_b0001_graph_prediction_v1.py",
)


def require(ok,why):
    if not bool(ok):raise RuntimeError("B0001 FOUR-ARM GRAPH GATE: "+why)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),"Refusing to overwrite freeze: "+str(path))
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",encoding="utf-8")


def input_gate(a):
    for key in ("weights","staging","graph_preflight"):
        source=getattr(a,key)
        require(source.is_dir(),"Missing B0001 frozen input: "+str(source))
        require(a.out!=source and source not in a.out.parents
                and a.out not in source.parents,
                "Output overlaps a frozen input: "+str(source))
    require(REPO!=a.out and REPO not in a.out.parents,
            "Output must be outside Git checkout")
    wfile=a.weights/"b0001_48_lhs_weight_and_support_freeze.json"
    w=read(wfile)
    require(w["status"]==SUPPORT_STATUS and
            w["world_families"]==6 and
            w["graph_simulations"]==0 and
            w["whitebox_reference_opened"] is False,
            "Wrong weighting/source freeze")
    require(set(w["world_supports"])==
            {f"{family}/{world}" for family in FAMILIES for world in ROLES},
            "Missing world-family public supports")
    sfile=a.staging/"b0001_public_inputs_manifest.json"
    s=read(sfile)
    require(s["status"]==STAGING_STATUS and s["cells"]==12 and
            s["hidden_world_parameters_copied"] is False and
            s["calibration_or_confirmation_values_copied"] is False,
            "B0001 public-input firewall changed")
    gfile=a.graph_preflight/"b0001_graph_prediction_preflight.json"
    g=read(gfile)
    require(g["status"]=="B0001_GRAPH_PREDICTION_PREFLIGHT_PASS_EXECUTION_BLOCKED"
            and g["n_graph_cells"]==12 and
            g["graph_whitebox_read"] is False
            and g["final_whitebox_read"] is False
            and g["graph_prediction_execution_authorized"] is False
            and g["public_staging_manifest_sha256"]==digest(sfile),
            "Original B0001 graph preflight failed")
    sources={}
    for name in SCIENTIFIC_SOURCES:
        source=REPO/name
        require(source.is_file(),"Historical scientific source missing: "+name)
        sources[name]=digest(source)
    require(w["historical_sources_sha256"][
            "first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py"]==
            sources["first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py"],
            "Historical allocation engine changed since support freeze")
    require(g["original_graph_source_sha256"][
            "run_phase5_graph_prediction_v3b_fullsupport.py"]==
            sources["first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py"],
            "Graph engine changed since previously frozen B0001 graph preflight")
    stage_hashes={entry["path"]:entry["staged_sha256"]
                  for entry in s["staged_files"]}
    for world in ROLES:
        for graph in GRAPHS:
            key=f"{world}__{graph}"
            rel=f"frozen_queries/{key}/step0_frozen_queries.csv"
            require(rel in stage_hashes and
                    digest(a.staging/rel)==stage_hashes[rel] and
                    digest(a.staging/rel)==g["query_sha256_by_cell"][f"{world}/{graph}"],
                    "Original graph query fingerprint mismatch: "+key)
            q=pd.read_csv(a.staging/rel)
            require(len(q)==15 and q.query_id.nunique()==15
                    and set(q.step0_cell_status)=={"FROZEN_PHASE5_STEP0_PASS_V2"},
                    "Incompatible B0001 query design: "+key)
    return wfile,w,sfile,gfile,g,sources


def allocations(a,w):
    results={}
    reserved=[]
    for family in FAMILIES:
        for world in ROLES:
            key=f"{family}/{world}"
            root=a.weights/family/world
            mpath=root/"support"/"world_support_manifest.json"
            meta=read(mpath)
            require(meta["status"]==WORLD_STATUS and
                    meta["family"]==family and meta["world"]==world
                    and meta["top14_support_size"]==14
                    and meta["graph_budget_per_method"]==1400
                    and meta["graph_simulations"]==0
                    and meta["whitebox_reference_opened"] is False
                    and digest(mpath)==w["world_supports"][key]["world_support_manifest_sha256"],
                    "Frozen world support provenance mismatch: "+key)
            table_path=root/"support"/"top14_support.csv"
            require(digest(table_path)==meta["top14_support_sha256"],
                    "Top14 support edited: "+key)
            t=pd.read_csv(table_path)
            require(len(t)==14 and
                    t.joint_rank.astype(int).tolist()==list(range(1,15))
                    and t.n_trajectories.astype(int).sum()==BUDGET
                    and (t.n_trajectories>=1).all()
                    and np.isclose(t.alpha.astype(float).sum(),1,atol=1e-12)
                    and (t.n_trajectories<=BUDGET).all(),
                    "Invalid original Top14 allocation: "+key)
            for provider in PROVIDERS:
                wpath=root/provider/"provider_weights.csv"
                require(digest(wpath)==meta["provider_weight_sha256"][provider],
                        "Provider candidate weights drift: "+key+"/"+provider)
                weights=pd.read_csv(wpath)
                require(len(weights)==48 and
                        np.isclose(weights.weight.astype(float).sum(),1,atol=1e-12),
                        "Invalid provider model weights: "+key+"/"+provider)
                require(set(t[f"{provider}_candidate_id"]).issubset(
                        set(weights.candidate_id)),
                        "Top14 model identity outside frozen provider weights")
            seeds=[]
            for rank,row in enumerate(t.itertuples(index=False),1):
                start=BASE[family]["top14"]+(rank-1)*RANK_STRIDE
                stop=start+int(row.n_trajectories)-1
                require(stop<start+RANK_STRIDE and stop<=MAX_NATIVE,
                        "Native rank graph seed bound/stride invalid")
                seeds.append({"joint_rank":rank,"seed_start":start,
                              "seed_end_inclusive":stop,
                              "n_trajectories":int(row.n_trajectories)})
            t1=BASE[family]["top1"]
            require(t1+BUDGET-1<=MAX_NATIVE,
                    "Native Top1 seed bound invalid")
            # Seed ranges are intentionally shared by the P1/P3/P4 worlds
            # (and their four graphs) for matched common-random-number
            # comparisons. Reserve each method/family namespace only ONCE.
            # Repeated world reservations are not scientific collisions.
            results[key]={"top14_support_path":str(table_path),
                         "top14_support_sha256":digest(table_path),
                         "support_manifest_sha256":digest(mpath),
                         "top14_rank_seed_blocks":seeds,
                         "top1_seed_start":t1,
                         "top1_seed_end_inclusive":t1+BUDGET-1,
                         "methods":list(ARM_IDS[family]),
                         "allocation_per_method":BUDGET,
                         "same_world_graphs_share_CRN":True}
    for family in FAMILIES:
        reserved.extend([
            (family+" Top14 ranks",BASE[family]["top14"],
             BASE[family]["top14"]+13*RANK_STRIDE+BUDGET-1),
            (family+" Top1",BASE[family]["top1"],
             BASE[family]["top1"]+BUDGET-1),
        ])
    # Only compare independent method/family namespaces. The same bank is
    # deliberately reused across worlds and graphs, never double-counted.
    for i,(name,lo,hi) in enumerate(reserved):
        for other,lo2,hi2 in reserved[i+1:]:
            require(hi<lo2 or hi2<lo,
                    "New four-method graph bank overlap: "+name+"/"+other)
    # Earlier B0001 M3 stream occupies 36M..36.343M and our previously
    # frozen local candidate scoring 38.0M..38.12M (both no overlap).
    require(all(lo>39_000_010 and hi<=MAX_NATIVE for _,lo,hi in reserved),
            "Graph stream may overlap prior science / native overflow")
    require(len(results)==6 and len(reserved)==4,
            "Unexpected four-arm seed group count")
    return results,reserved


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("weights","staging","graph_preflight","out"):
        p.add_argument("--"+name,type=Path,required=True)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check",action="store_true")
    modes.add_argument("--freeze",action="store_true")
    a=p.parse_args()
    for name in ("weights","staging","graph_preflight","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    wf,w,sf,gf,g,sources=input_gate(a)
    supports,reserved=allocations(a,w)
    print("B0001_FOUR_ARM_GRAPH_ISOLATION_CHECK_PASS",
          "six frozen world supports; twelve graph cells; four method definitions",
          flush=True)
    print("B0001_GRAPH_SEED_SEPARATION_PASS",
          len(reserved),"nonoverlapping reserved streams; native uint32 compatible",
          flush=True)
    print("ORIGINAL_TOP14_AND_FIXED_CV_TOP14_NOT_ADAPTIVE_99_9_PERCENT_SUPPORT",
          flush=True)
    if a.check:
        print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ",flush=True)
        return
    require(not a.out.exists(),"Refusing overwrite of graph gate workspace")
    a.out.mkdir(parents=True)
    result={
        "status":STATUS,
        "scientific_graph_execution_authorized":False,
        "engineering_graph_smoke_authorized":False,
        "next_gate":"Build isolated read-only graph engine adapter and verify a one-trajectory disposable smoke test",
        "methods":[m for family in FAMILIES for m in ARM_IDS[family]],
        "worlds":list(ROLES),"graphs":list(GRAPHS),
        "n_method_cell_observations_missing":48,
        "graph_budget_per_method_cell":BUDGET,
        "nominal_trajectories_remaining":4*12*BUDGET,
        "weight_freeze_sha256":digest(wf),
        "public_input_freeze_sha256":digest(sf),
        "B0001_prior_graph_preflight_sha256":digest(gf),
        "source_code_sha256":sources,
        "world_supports_and_fresh_graph_seeds":supports,
        "graph_seed_namespace_reservations":reserved,
        "graph_seed_shared_across_worlds_and_graphs_by_design":True,
        "new_seeds_disjoint_from_prior_B0001_science":True,
        "whitebox_reference_read":False,
        "graph_simulations_executed":0,
        "output_evaluation_or_policy_selection_authorized":False,
    }
    target=a.out/"b0001_four_arm_graph_isolation_preflight.json"
    write_json(target,result)
    print("B0001_FOUR_ARM_GRAPH_ISOLATION_PREFLIGHT_FROZEN_EXECUTION_BLOCKED")
    print("NO_SIMULATIONS / GRAPH_EXECUTION_BLOCKED")
    print("FREEZE",target)


if __name__=="__main__":
    main()
