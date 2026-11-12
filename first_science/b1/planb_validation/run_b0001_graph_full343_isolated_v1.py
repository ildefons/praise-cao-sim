#!/usr/bin/env python3
"""Isolated B0001 full343 graph adapter, engineering smoke, and gated execution.

--check: read-only validation of the B0001 graph preflight and scientific
         source bindings; does not write or simulate.
--smoke: disposable ONE-trajectory M1/M2/M3 graph simulation on P1/G_PAR,
         plus original M0 curve and 343-support construction checks. This is
         engineering-only evidence, NEVER used as scientific prediction.
--run: scientific 12-cell original full343 M0/M1/M2/M3 prediction, ONLY if
       a fresh, hash-bound smoke manifest passes. No final WB opened.
       Uses original _run_cell / graph simulator and NEW B0001 global freeze.
       M3 Top1/Top3/Top14 are nested readouts, not extra simulations.

Historical Phase-5 outputs and private candidate-world workspaces are never
mounted. Provider reconstruction and B0001 selection remain immutable.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

import preflight_b0001_graph_prediction_v1 as pre
from preflight_b0001_graph_prediction_v1 import ROLES,GRAPHS,PROVIDERS,REPO,PHASE5
from preflight_b0001_graph_prediction_v1 import require,load,sha,save

SMOKE_STATUS="B0001_GRAPH_ADAPTER_ENGINEERING_SMOKE_PASS"
STAGE_STATUS="B0001_GRAPH_PREDICTION_PREFLIGHT_PASS_EXECUTION_BLOCKED"
SOURCE=("run_phase5_graph_prediction_v3b_fullsupport.py",
        "run_phase5_step0_v2.py","phase5_graph_simulator_v2.py",
        "phase5_runtime_v2.py")
ENGINEERING_SEEDS=(39_000_001,39_000_002,39_000_003)
COLUMNS=("query_id","provider_world_id","graph_id","rho_label","rho","regime",
         "scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status")


def validate_paths(a):
    for v in (a.staging,a.v3b,a.preflight):
        require(v.is_dir(),"Missing B0001 source directory: "+str(v))
    require(a.out!=REPO and REPO not in a.out.parents,
            "B0001 graph output must not be in repository")
    for v in (a.staging,a.v3b,a.preflight):
        require(a.out!=v and v not in a.out.parents and a.out not in v.parents,
                "B0001 graph output must be isolated from scientific input")
    require(a.out!=PHASE5 and PHASE5 not in a.out.parents,
            "Cannot write historical Phase-5 outputs")


def prerequisites(a):
    freeze_file=a.preflight/"b0001_graph_prediction_preflight.json"
    require(freeze_file.is_file(),"Run B0001 graph preflight before adapter")
    f=load(freeze_file)
    require(f["status"]==STAGE_STATUS and
            f["n_graph_cells"]==12 and f["n_provider_models_sets"]==9 and
            f["n_worlds"]==3 and
            f["scientific_simulations_executed"]==0 and
            f["graph_prediction_execution_authorized"] is False,
            "B0001 graph preflight status invalid")
    require(f["public_staging_manifest_sha256"]==
            sha(a.staging/"b0001_public_inputs_manifest.json") and
            f["v3b_selection_freeze_sha256"]==
            sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
            "Public input or V3b model freeze changed")
    current={name:sha(PHASE5/name) for name in SOURCE}
    require(all(f["original_graph_source_sha256"].get(name)==sha(PHASE5/name)
                for name in ("run_phase5_graph_prediction_v3b_fullsupport.py",
                             "config_phase5_graph_prediction_v3b_fullsupport.json",
                             "config_phase5_seed_registry_v3b_fullsupport.json",
                             "freeze_phase5_graph_prediction_v3b_fullsupport_preexecution.py")),
            "Original fullsupport source/config changed since B0001 preflight")
    for role in ROLES:
        source=a.preflight/f"m3_fullsupport_allocation_{role}.csv"
        require(source.is_file() and
                f["allocation_sha256"][role]==sha(source),
                "Fullsupport preflight allocation changed: "+role)
        t=pd.read_csv(source)
        require(len(t)==343 and
                int(t["n_trajectories"].sum())==1400 and
                t["rank"].astype(int).tolist()==list(range(1,344)),
                "Invalid frozen M3 allocation: "+role)
    for role in ROLES:
        for graph in GRAPHS:
            key=role+"/"+graph
            q=a.staging/"frozen_queries"/f"{role}__{graph}"/"step0_frozen_queries.csv"
            require(q.is_file() and sha(q)==f["query_sha256_by_cell"][key],
                    "B0001 frozen graph queries changed: "+key)
    for role in ROLES:
        for provider in PROVIDERS:
            root=a.v3b/role/provider
            entry=f["provider_selection_sha256_and_ids"][f"{role}/{provider}"]
            for key,name in (("m1_model_sha256","m1_provider_model.csv"),
                             ("m2_model_sha256","m2_provider_models.csv"),
                             ("m3_model_sha256","m3_provider_models.csv")):
                require(sha(root/name)==entry[key],
                        "Provider model changed: "+role+"/"+provider+"/"+name)
        world=f["world_support_sha256_and_allocation"][role]
        for key,name in (("m2_support_sha256","m2_joint_support_27.csv"),
                         ("m3_support_sha256","m3_joint_support_343.csv"),
                         ("m3_top14_sha256","m3_joint_support_top14.csv")):
            require(sha(a.v3b/role/name)==world[key],
                    "World support changed: "+role+"/"+name)
    return f,current


def original_module():
    phase3=PHASE5.parent/"phase3"
    phase2=PHASE5.parent/"phase2"
    phase4=PHASE5.parent/"phase4"
    for path in (phase2,phase3,phase4,PHASE5):
        if str(path) not in sys.path:
            sys.path.insert(0,str(path))
    import run_phase5_graph_prediction_v3b_fullsupport as predictor
    return predictor


def public_cards(a,world):
    require(world in ROLES,"Request for non-B0001 public world")
    return {
        provider:load(a.staging/"public_I1"/world/provider/"card.json")
        for provider in PROVIDERS
    }


def public_surfaces(a,world):
    require(world in ROLES,"Request for non-B0001 I1 surface")
    return {
        provider:pd.read_csv(a.staging/"public_I1"/world/provider/"sigma_surface.csv",
                             usecols=["provider_id","region_id","region_rho",
                                      "rho","horizon","sigma_hat"])
        for provider in PROVIDERS
    }


def scientific_seeds(pre):
    result=copy.deepcopy(load(PHASE5/"config_phase5_seed_registry_v3b_fullsupport.json"))
    spec=pre["graph_seed_plan"]
    common=spec["m1_m2_common_100"]
    m3=spec["m3"]
    result["graph_prediction"]["M1_M2_common_bank"]=dict(common)
    result["graph_prediction"]["M3"]["seed_base"]=m3["seed_base"]
    result["graph_prediction"]["M3"]["seed_block_stride"]=m3["seed_block_stride"]
    result["b0001_seed_provenance"]="b0001_graph_prediction_preflight.json"
    return result


def prepare_workspace(a,pre):
    require(not a.out.exists(),"Refusing to overwrite graph output workspace")
    (a.out/"_preexecution").mkdir(parents=True)
    seed=scientific_seeds(pre)
    save(a.out/"_preexecution"/"b0001_full343_graph_seeds.json",seed)
    alloc={}
    for role in ROLES:
        source=a.preflight/f"m3_fullsupport_allocation_{role}.csv"
        dest=a.out/"_preexecution"/source.name
        dest.write_bytes(source.read_bytes())
        alloc[role]=sha(dest)
        require(alloc[role]==pre["allocation_sha256"][role],
                "Allocation copied incorrectly")
    manifest={
        "status":"B0001_GRAPH_ADAPTER_PREEXECUTION_SMOKE_PENDING",
        "preflight_sha256":sha(a.preflight/"b0001_graph_prediction_preflight.json"),
        "stage_public_sha256":sha(a.staging/"b0001_public_inputs_manifest.json"),
        "v3b_selection_sha256":sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
        "scientific_seed_sha256":sha(a.out/"_preexecution"/"b0001_full343_graph_seeds.json"),
        "allocation_sha256":alloc,
        "simulations_run":0,
        "graph_prediction_authorized":False,
        "final_whitebox_read":False,
    }
    save(a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json",manifest)


def validate_workspace(a,pre):
    root=a.out/"_preexecution"
    mf=root/"b0001_graph_adapter_preexecution.json"
    require(mf.is_file(),"Missing B0001 graph adapter setup. Run --smoke first")
    data=load(mf)
    require(data["status"]=="B0001_GRAPH_ADAPTER_PREEXECUTION_SMOKE_PENDING",
            "B0001 graph adapter preexecution modified")
    require(data["preflight_sha256"]==sha(a.preflight/"b0001_graph_prediction_preflight.json")
            and data["stage_public_sha256"]==sha(a.staging/"b0001_public_inputs_manifest.json")
            and data["v3b_selection_sha256"]==sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
            "B0001 graph preexecution provenance changed")
    seed_file=root/"b0001_full343_graph_seeds.json"
    require(sha(seed_file)==data["scientific_seed_sha256"]
            and load(seed_file)==scientific_seeds(pre),
            "B0001 graph prediction seed registry changed")
    for role in ROLES:
        require(sha(root/f"m3_fullsupport_allocation_{role}.csv")==
                data["allocation_sha256"][role]==pre["allocation_sha256"][role],
                "B0001 frozen fullsupport allocation changed: "+role)
    return seed_file


def patched(predictor,a,pre):
    """Redirect original graph predictor module bindings, process-local only."""
    class Redirect:
        def __enter__(self):
            self.original={
                name:getattr(predictor,name) for name in
                ("ROOT","STEP0_ROOT","V3B_ROOT","SEEDS","CFG","PREEXEC",
                 "_load_public_i1_world","_public_surfaces","_cell_manifest")
            }
            predictor.ROOT=a.out/"scientific"
            predictor.STEP0_ROOT=a.staging/"frozen_queries"
            predictor.V3B_ROOT=a.v3b
            predictor.SEEDS=a.out/"_preexecution"/"b0001_full343_graph_seeds.json"
            predictor.CFG=PHASE5/"config_phase5_graph_prediction_v3b_fullsupport.json"
            predictor.PREEXEC=a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json"
            predictor._load_public_i1_world=lambda contracts,world:public_cards(a,world)
            predictor._public_surfaces=lambda world:public_surfaces(a,world)
            source_cell_manifest=self.original["_cell_manifest"]
            def cell_manifest(**kwargs):
                mf=source_cell_manifest(**kwargs)
                seed=pre["graph_seed_plan"]
                common=seed["m1_m2_common_100"]
                m3=seed["m3"]
                mf["seed_banks"]={
                    "M1_M2":f"{common['start']}..{common['end_inclusive']}",
                    "M3":f"rank r: {m3['seed_base']}+(r-1)*{m3['seed_block_stride']}+k, frozen world-specific N_r"
                }
                mf["b0001_preflight_sha256"]=
                    sha(a.preflight/"b0001_graph_prediction_preflight.json")
                mf["b0001_v3b_selection_sha256"]=
                    sha(a.v3b/"b0001_v3b_selection_audit_freeze.json")
                mf["final_WB_read"]=False
                return mf
            predictor._cell_manifest=cell_manifest
            return predictor
        def __exit__(self,exc_type,exc,tb):
            for name,value in self.original.items():
                setattr(predictor,name,value)
    return Redirect()


def smoke(a,pre):
    if not a.out.exists():
        prepare_workspace(a,pre)
    validate_workspace(a,pre)
    require(not (a.out/"engineering_smoke"/"b0001_graph_smoke.json").exists(),
            "Engineering smoke already frozen; do not overwrite")
    predictor=original_module()
    from phase5_runtime_v2 import load_phase5_contracts,graph_record
    with patched(predictor,a,pre):
        contracts=load_phase5_contracts(PHASE5)
        graph_id="G_PAR"
        world="P1"
        graph=graph_record(contracts,graph_id)
        queries=predictor._query_definitions(world+"__"+graph_id)
        horizons=predictor._horizons(load(predictor.CFG))
        require(len(queries)==15 and len(horizons)==49,
                "Engineering smoke query/horizon compatibility failed")
        m0=predictor._m0_predictions(contracts=contracts,world=world,
                                    graph_id=graph_id,queries=queries,horizons=horizons)
        require(len(m0)==15*49,"Original M0 graph prediction returned wrong grid")
        m1=predictor._m1_surrogates(world)
        m2=predictor._m2_variants(world)
        m3,allocation=predictor._m3_variants(world)
        require(len(m1)==3 and len(m2)==27 and len(m3)==343
                and int(allocation["n_trajectories"].sum())==1400,
                "Original full343 provider-support adapter failed")
        # Three throwaway isolated graph trajectories; no selected scientific
        # prediction bank or ledger is touched.
        base=a.out/"engineering_smoke"/"P1__G_PAR"
        cases=(("M1",m1,ENGINEERING_SEEDS[0]),
               ("M2_R01",m2[0]["surrogates"],ENGINEERING_SEEDS[1]),
               ("M3_R001",m3[0]["surrogates"],ENGINEERING_SEEDS[2]))
        checks={}
        for name,surrogates,seed in cases:
            payload=predictor._simulation_payload(
                cell_root=base,graph_id=graph_id,graph_ast=graph["ast"],
                variant_id=name,surrogates=surrogates,seeds=[seed],
                ledger_path=base/"ledgers"/f"{name}.csv",
                contracts=contracts,
            )
            assert payload["seeds"]==[seed]
            rec=predictor._simulate_variant_worker(payload)
            ledger=predictor._validate_complete_ledger(
                Path(rec["ledger_path"]),[seed])
            curves=predictor._member_curves(
                ledger=ledger,queries=queries,horizons=horizons,
                method_id="ENGINEERING_SMOKE",rank=1,graph_n=1,
                joint_weight=1.0,candidate_ids={
                    p:(pd.read_csv(a.v3b/world/p/"m1_provider_model.csv")
                       .iloc[0]["candidate_id"]) for p in PROVIDERS
                },
            )
            require(len(curves)==15*49
                    and curves["sigma_member"].between(0,1).all(),
                    "Engineering graph curve invalid: "+name)
            checks[name]={"ledger_sha256":sha(Path(rec["ledger_path"])),
                          "n_trajectories":1,"n_prediction_points":len(curves)}
        smoke_manifest={
            "status":SMOKE_STATUS,
            "engineering_only":True,
            "scientific_evidence":False,
            "source_graph_preflight_sha256":
                sha(a.preflight/"b0001_graph_prediction_preflight.json"),
            "b0001_adapter_preexecution_sha256":
                sha(a.out/"_preexecution"/"b0001_graph_adapter_preexecution.json"),
            "original_graph_sources_sha256":{name:sha(PHASE5/name) for name in SOURCE},
            "world":"P1","graph":"G_PAR",
            "m0_grid_points":len(m0),
            "m2_joint_support":len(m2),"m3_full_support":len(m3),
            "m3_total_budget":int(allocation["n_trajectories"].sum()),
            "smoke_trajectories_executed":3,
            "science_graph_trajectories_executed":0,
            "checks":checks,
            "historical_world_artifacts_read":False,
            "hidden_generating_provider_parameters_read":False,
            "step0_WB_outcomes_read":False,
            "final_whitebox_read":False,
            "graph_predictions_authorized":False,
        }
        path=a.out/"engineering_smoke"/"b0001_graph_smoke.json"
        save(path,smoke_manifest)
    print("B0001_GRAPH_ADAPTER_ENGINEERING_SMOKE_PASS",flush=True)
    print("M0 735 points; M1/M2/M3 one trajectory each",flush=True)
    print("SCIENTIFIC_PREDICTIONS_NOT_STARTED",flush=True)
    print("MANIFEST",path,flush=True)


def scientific(a,pre,workers):
    require(a.out.exists(),"Run engineering --smoke before scientific --run")
    validate_workspace(a,pre)
    smoke_path=a.out/"engineering_smoke"/"b0001_graph_smoke.json"
    require(smoke_path.is_file(),"Engineering smoke not complete")
    sm=load(smoke_path)
    require(sm["status"]==SMOKE_STATUS and
            sm["scientific_evidence"] is False and
            sm["source_graph_preflight_sha256"]==
            sha(a.preflight/"b0001_graph_prediction_preflight.json") and
            sm["smoke_trajectories_executed"]==3 and
            sm["science_graph_trajectories_executed"]==0 and
            sm["final_whitebox_read"] is False,
            "Graph engineering smoke provenance invalid")
    require(sm["original_graph_sources_sha256"]==
            {name:sha(PHASE5/name) for name in SOURCE},
            "Graph scientific code differs from smoke-tested version")
    predictor=original_module()
    with patched(predictor,a,pre):
        for role in ROLES:
            for graph in GRAPHS:
                print("B0001_BLIND_GRAPH_PREDICTION_START",role,graph,flush=True)
                predictor._run_cell(role,graph,workers)
                cell=a.out/"scientific"/f"{role}__{graph}"/"prediction_manifest.json"
                require(cell.is_file(),"Missing frozen graph prediction manifest")
                mf=load(cell)
                require(mf["status"]==predictor.FROZEN_CELL_STATUS
                        and mf["b0001_preflight_sha256"]==
                        sha(a.preflight/"b0001_graph_prediction_preflight.json")
                        and mf["ledger_count"]==371
                        and mf["ledger_trajectory_total"]==4200,
                        "Cell prediction ledger/cardinality/freeze invalid")
        # A B0001-specific GLOBAL freeze, not the historical 16-cell Phase-5
        # freeze that encodes P2 as failed. All 12 new-world cells must exist.
        glob={}
        for role in ROLES:
            for graph in GRAPHS:
                cell=f"{role}__{graph}"
                file=a.out/"scientific"/cell/"prediction_manifest.json"
                glob[cell]=sha(file)
        freeze={
            "status":"B0001_FULL343_12_CELL_GRAPH_PREDICTIONS_FROZEN",
            "prediction_manifest_sha256_by_cell":glob,
            "n_frozen_cells":12,
            "n_trajectories_per_cell":4200,
            "source_graph_preflight_sha256":
                sha(a.preflight/"b0001_graph_prediction_preflight.json"),
            "v3b_selection_freeze_sha256":
                sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
            "science_graph_trajectories":12*4200,
            "final_WB_read":False,
            "graph_whitebox_read":False,
            "seven_method_plan_b_complete":False,
            "final_whitebox_authorized":False,
        }
        path=a.out/"scientific"/"b0001_full343_global_prediction_freeze.json"
        require(not path.exists(),"B0001 global freeze already exists")
        save(path,freeze)
        print("B0001_FULL343_12_CELL_GRAPH_PREDICTIONS_FROZEN",flush=True)
        print("SEVEN_METHOD_PLAN_B_REMAINS_INCOMPLETE",flush=True)
        print("FREEZE",path,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--smoke",action="store_true")
    mode.add_argument("--run",action="store_true")
    parser.add_argument("--staging",type=Path,required=True)
    parser.add_argument("--v3b",type=Path,required=True)
    parser.add_argument("--preflight",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--workers",type=int,default=1)
    a=parser.parse_args()
    for name in ("staging","v3b","preflight","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    validate_paths(a)
    pre,source=prerequisites(a)
    if a.check:
        original_module()
        if a.out.exists():
            validate_workspace(a,pre)
        print("B0001_GRAPH_ADAPTER_READ_ONLY_CHECK_PASS 12 cells 3 full343 allocations",
              flush=True)
        print("SCIENTIFIC_PREDICTIONS_BLOCKED until engineering smoke",flush=True)
    elif a.smoke:
        smoke(a,pre)
    else:
        require(a.workers>=1,"workers must be positive")
        scientific(a,pre,a.workers)


if __name__=="__main__":
    main()
