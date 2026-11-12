#!/usr/bin/env python3
"""Final B0001 graph execution audit. NO physical simulations or WB access.

Verifies smoke ledgers, all frozen inputs, exact per-cell M1/M2/M3 seed
assignment, original V3b graph bindings, and actual checkpoint/restart worker
semantics using ONLY synthetic in-memory ledger records in a TemporaryDirectory.
Writes an immutable audit gate used by --run. Never touches scientific output.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

import run_b0001_graph_full343_isolated_v1 as adapter
from preflight_b0001_graph_prediction_v1 import ROLES,GRAPHS,PROVIDERS,require,load,sha,save

STATUS="B0001_FINAL_GRAPH_EXECUTION_AUDIT_PASS"
ENGINEERING_IDS=("M1","M2_R01","M3_R001")


def checkpoint_test(predictor):
    """Original _simulate_variant_worker: real checkpoint IO, fake simulator.

    Test both a partial interruption and a completed ledger replay. All
    generated records are synthetic, not model outputs.
    """
    previous=predictor.execute_one_phase5_graph_trajectory
    calls=[]
    try:
        def synthetic(**kwargs):
            calls.append(int(kwargs["trajectory_seed"]))
            return pd.DataFrame({"request_id":[100],
                                 "test_synthetic_record":[1]}),None
        predictor.execute_one_phase5_graph_trajectory=synthetic
        with tempfile.TemporaryDirectory(prefix="b0001_resume_audit_") as root:
            root=Path(root)
            cell=root/"cell"
            variant="AUDIT_FAKE"
            s1,s2=40_500_011,40_500_012
            cp=predictor._variant_checkpoint(cell,variant,s1)
            cp.parent.mkdir(parents=True)
            # An interrupted run already completed first trajectory.
            pd.DataFrame({"trajectory":[0],"trajectory_seed":[s1],
                          "request_id":[100],
                          "test_synthetic_record":[1]}).to_csv(cp,index=False)
            payload={"cell_root":str(cell),
                     "ledger_path":str(cell/"ledgers"/"synthetic.csv"),
                     "variant_id":variant,
                     "seeds":[s1,s2],
                     "surrogates":{p:{"mean_service_time":1.0,
                                      "cost_rate":1.0,"service_cv":0.0}
                                   for p in PROVIDERS},
                     "graph_id":"G_PAR","graph_ast":{},
                     "graph_invariants":{},"workload_period":1.0,
                     "stop_time":1.0,"canonical_ipt":1.0,
                     "execution_fraction":1.0}
            result=predictor._simulate_variant_worker(payload)
            require(calls==[s2] and result["reused"] is False,
                    "Original checkpoint worker re-executed completed seed")
            ledger_path=Path(result["ledger_path"])
            require(ledger_path.is_file() and
                    not predictor._variant_checkpoint(cell,variant,s1).exists() and
                    not predictor._variant_checkpoint(cell,variant,s2).exists(),
                    "Checkpoint-to-ledger finalization failed")
            actual=predictor._validate_complete_ledger(ledger_path,[s1,s2])
            require(actual["trajectory_seed"].astype(int).tolist()==[s1,s2],
                    "Synthetic resumed ledger seed/ordinal mismatch")
            cached=predictor._simulate_variant_worker(payload)
            require(cached["reused"] is True and calls==[s2],
                    "Original worker failed to reuse completed ledger")
            try:
                predictor._validate_complete_ledger(ledger_path,[s1,s2+1])
            except RuntimeError:
                pass
            else:
                raise RuntimeError("Original ledger validator accepted mismatched seeds")
            # This should reject an existing completed ledger even without
            # reading any simulation or checkpoint values beyond seed labels.
        return {"partial_checkpoint_reused":True,
                "only_missing_seed_executed_by_mock":True,
                "completed_ledger_reused_without_execution":True,
                "wrong_seed_ledger_rejected":True,
                "physical_simulations_executed":0}
    finally:
        predictor.execute_one_phase5_graph_trajectory=previous


def verify_smoke(a,pre):
    path=a.out/"engineering_smoke"/"b0001_graph_smoke.json"
    require(path.is_file(),"Engineering smoke manifest missing")
    mf=load(path)
    require(mf["status"]==adapter.SMOKE_STATUS
            and mf["scientific_evidence"] is False
            and mf["engineering_only"] is True
            and mf["world"]=="P1" and mf["graph"]=="G_PAR"
            and mf["m0_grid_points"]==735
            and mf["m2_joint_support"]==27
            and mf["m3_full_support"]==343
            and mf["m3_total_budget"]==1400
            and mf["smoke_trajectories_executed"]==3
            and mf["science_graph_trajectories_executed"]==0
            and mf["graph_predictions_authorized"] is False
            and mf["final_whitebox_read"] is False
            and mf["historical_world_artifacts_read"] is False
            and mf["hidden_generating_provider_parameters_read"] is False
            and mf["step0_WB_outcomes_read"] is False,
            "Graph smoke evidence inconsistent")
    require(mf["source_graph_preflight_sha256"]==
            sha(a.preflight/"b0001_graph_prediction_preflight.json")
            and mf["b0001_adapter_preexecution_sha256"]==
            sha(a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json")
            and mf["original_graph_sources_sha256"]==
            {name:sha(adapter.PHASE5/name) for name in adapter.SOURCE},
            "Graph smoke provenance hash mismatch")
    require(set(mf["checks"])==set(ENGINEERING_IDS),
            "Engineering smoke did not exercise M1, M2 and M3")
    for method,seed in zip(ENGINEERING_IDS,adapter.ENGINEERING_SEEDS):
        record=mf["checks"][method]
        ledger=a.out/"engineering_smoke"/"P1__G_PAR"/"ledgers"/(method+".csv")
        require(ledger.is_file() and
                record["ledger_sha256"]==sha(ledger) and
                record["n_trajectories"]==1 and
                record["n_prediction_points"]==735,
                "Engineering smoke ledger checksum/cardinality mismatch: "+method)
        t=pd.read_csv(ledger,usecols=["trajectory","trajectory_seed","request_id"])
        require(set(t["trajectory_seed"].astype(int))=={seed}
                and set(t["trajectory"].astype(int))=={0}
                and len(t)>=1 and not t[["trajectory","request_id"]].duplicated().any(),
                "Engineering smoke ledger malformed or unexpected seed: "+method)
    return sha(path)


def audit(a):
    adapter.validate_paths(a)
    pre,_=adapter.prerequisites(a)
    adapter.validate_workspace(a,pre)
    smoke_sha=verify_smoke(a,pre)
    predictor=adapter.original_module()
    allocation_checks={}
    # Read all 12 query sets and each of the 371 variant seed blocks as
    # enumerated by the unchanged original M2/M3 methods.
    with adapter.patched(predictor,a,pre):
        for role in ROLES:
            m1=predictor._m1_surrogates(role)
            m2=predictor._m2_variants(role)
            m3,allocation=predictor._m3_variants(role)
            require(set(m1)==set(PROVIDERS) and len(m2)==27 and len(m3)==343,
                    "Original graph adapter model support failed for "+role)
            require(m2[0]["rank"]==1 and m2[-1]["rank"]==27
                    and [v["rank"] for v in m3]==list(range(1,344)),
                    "Original graph variant ranks changed for "+role)
            common=load(predictor.SEEDS)["graph_prediction"]["M1_M2_common_bank"]
            cseeds=set(range(int(common["start"]),int(common["end_inclusive"])+1))
            require(len(cseeds)==100
                    and cseeds==set(range(35_000_000,35_000_100)),
                    "M1/M2 graph CRN bank not as frozen")
            rank_seeds=set()
            n3=0
            for v in m3:
                seeds=set(range(int(v["seed_start"]),
                                int(v["seed_end_inclusive"])+1))
                require(len(seeds)==int(v["n_trajectories"])
                        and len(rank_seeds.intersection(seeds))==0
                        and cseeds.isdisjoint(seeds),
                        "Overlapping/incorrect M3 variant seed range: "+role)
                rank_seeds.update(seeds)
                n3+=len(seeds)
            require(n3==1400 and len(rank_seeds)==1400,
                    "M3 full343 total allocation not 1400 for "+role)
            require(int(allocation["n_trajectories"].sum())==1400
                    and np.isclose(m3[0]["joint_weight"],
                                   float(allocation.iloc[0]["joint_weight"]),
                                   atol=1e-15,rtol=0),
                    "Original M3 support vs frozen allocation mismatch: "+role)
            allocation_checks[role]={
                "variant_count":len(m3),
                "unique_m3_seeds":len(rank_seeds),
                "common_m1m2_seeds":len(cseeds),
                "m3_seed_min":min(rank_seeds),"m3_seed_max":max(rank_seeds),
                "per_cell_expected_trajectory_count":100+27*100+n3,
            }
            for graph in GRAPHS:
                q=predictor._query_definitions(f"{role}__{graph}")
                require(len(q)==15 and q["query_id"].nunique()==15
                        and set(q["provider_world_id"])=={role}
                        and set(q["graph_id"])=={graph},
                        "Wrong frozen graph-query selection: "+role+"/"+graph)
                require(len(predictor._horizons(load(predictor.CFG)))==49,
                        "Graph horizon grid incompatible")
    # Re-open actual original worker in-memory only to test real resume logic,
    # without invoking the native graph simulator.
    resume=checkpoint_test(predictor)
    # We have not started scientific cells.  Do not permit a surprise
    # pre-existing scientific freeze or unknown scientific output here.
    root=a.out/"scientific"
    for role in ROLES:
        for graph in GRAPHS:
            cell=root/f"{role}__{graph}"
            require(not cell.exists(),
                    "Scientific cell already exists; initial gate audit refuses overwriting: "+str(cell))
    require(not (root/"b0001_full343_global_prediction_freeze.json").exists(),
            "B0001 scientific global freeze already exists")
    return {
        "status":STATUS,
        "graph_preflight_sha256":
            sha(a.preflight/"b0001_graph_prediction_preflight.json"),
        "engineering_smoke_sha256":smoke_sha,
        "adapter_preexecution_sha256":
            sha(a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json"),
        "graph_runner_source_sha256":sha(Path(adapter.__file__)),
        "audit_source_sha256":sha(Path(__file__)),
        "v3b_selection_freeze_sha256":
            sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
        "scientific_seed_registry_sha256":
            sha(a.out/"_preexecution"/"b0001_full343_graph_seeds.json"),
        "allocations_sha256":{
            role:sha(root/"_preexecution"/f"m3_fullsupport_allocation_{role}.csv")
            for role in ROLES},
        "all_12_frozen_graph_queries_verified":True,
        "all_nine_provider_model_sets_verified":True,
        "expected_graph_cells":12,
        "expected_graph_variants_per_cell":371,
        "expected_trajectories_per_cell":4200,
        "expected_total_graph_trajectories":50400,
        "world_allocation_checks":allocation_checks,
        "resume_tests":resume,
        "native_graph_simulations_during_audit":0,
        "graph_whitebox_read":False,
        "final_whitebox_read":False,
        "seven_method_plan_b_complete":False,
        "authorization_scope":"B0001 full343 12-cell blind predictions only",
    }


def verify_execution_gate(a):
    """Read-only fast fail-closed gate. May be called repeatedly on resume."""
    target=a.out/"_execution_audit"/"b0001_final_execution_audit.json"
    require(target.is_file(),"Missing final execution audit; run audit script first")
    g=load(target)
    require(g["status"]==STATUS and
            g["native_graph_simulations_during_audit"]==0 and
            g["expected_graph_cells"]==12 and
            g["expected_total_graph_trajectories"]==50400 and
            g["authorization_scope"]=="B0001 full343 12-cell blind predictions only"
            and g["final_whitebox_read"] is False,
            "Final execution audit status/scope invalid")
    sources={
        "graph_preflight_sha256":
            a.preflight/"b0001_graph_prediction_preflight.json",
        "engineering_smoke_sha256":
            a.out/"engineering_smoke"/"b0001_graph_smoke.json",
        "adapter_preexecution_sha256":
            a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json",
        "graph_runner_source_sha256":Path(adapter.__file__),
        "audit_source_sha256":Path(__file__),
        "v3b_selection_freeze_sha256":
            a.v3b/"b0001_v3b_selection_audit_freeze.json",
        "scientific_seed_registry_sha256":
            a.out/"_preexecution"/"b0001_full343_graph_seeds.json",
    }
    for key,p in sources.items():
        require(sha(p)==g[key],"Final execution gate provenance changed: "+key)
    for role in ROLES:
        require(sha(a.out/"scientific"/"_preexecution"/
                    f"m3_fullsupport_allocation_{role}.csv")==
                g["allocations_sha256"][role],
                "Final gate M3 allocation changed: "+role)
    # Verify the originally frozen input hashes again; never rely only on
    # smoke status or an old audit manifest.
    adapter.prerequisites(a)
    adapter.validate_workspace(a,load(a.preflight/"b0001_graph_prediction_preflight.json"))
    verify_smoke(a,load(a.preflight/"b0001_graph_prediction_preflight.json"))
    print("B0001_FINAL_GRAPH_EXECUTION_GATE_PASS frozen sources and smoke",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging",type=Path,required=True)
    p.add_argument("--v3b",type=Path,required=True)
    p.add_argument("--preflight",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    for name in ("staging","v3b","preflight","out"):
        setattr(args,name,getattr(args,name).expanduser().resolve())
    require(args.out.is_dir(),"Graph smoke workspace missing")
    target=args.out/"_execution_audit"/"b0001_final_execution_audit.json"
    require(not target.exists(),"Final graph execution audit already exists; cannot overwrite")
    result=audit(args)
    save(target,result)
    verify_execution_gate(args)
    print("B0001_FINAL_GRAPH_EXECUTION_AUDIT_PASS",flush=True)
    print("SMOKE_MANIFEST_SHA256_VERIFIED, ALL_12_CELLS_SEEDS_PASS",flush=True)
    print("SYNTHETIC_CHECKPOINT_RESUME_PASS, ZERO_SCIENTIFIC_SIMULATIONS",flush=True)
    print("MANIFEST",target,flush=True)


if __name__=="__main__":
    main()
