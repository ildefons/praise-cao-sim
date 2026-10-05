"""Official Phase-5 V2 M1 provider reconstruction.

This runner adapts the frozen M1-v2 public-I1 inverse lift to the Phase-5 seed
registry.  It consumes only each world's frozen public I1 cards, W0 and the
declared M1 closure conventions.  Step-0 WB values and hidden provider
parameters are never inputs.

Boundary handling follows the prospective Phase-5 rule exactly: start from the
base M1-v2 domain; if the selected candidate is within 2% of a mu or kappa
log-bound, expand only that implicated edge by one decade and rerun once using
the same evidence banks.  CV edges are never expanded.  Any unresolved edge
after the one permitted round yields M1 NOT_INSTANTIABLE for that provider.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE2=FIRST_SCIENCE/"phase2"
PHASE3=FIRST_SCIENCE/"phase3"
for p in (PHASE2,PHASE3):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa:E402
from run_m1_provider_lift_v2 import run_joint_lift_for_provider  # noqa:E402

from phase5_runtime_v2 import (
    base_manifest,
    canonical_provider_world_ids,
    inclusive_seed_range,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

PROVIDERS=("ProviderA","ProviderB","ProviderC")
SOURCE_CONTRACT=PHASE3/"config_phase3_m1_contract_v2.json"
DEFAULT_ROOT=HERE/"results"/"03_reconstruction"
ELIGIBILITY_MANIFEST=HERE/"results"/"02_step0"/"phase5_step0_eligibility_manifest.json"


def _require_step0_frozen()->dict[str,Any]:
    if not ELIGIBILITY_MANIFEST.is_file():
        raise FileNotFoundError(
            f"{ELIGIBILITY_MANIFEST} is missing; freeze Step-0 eligibility first"
        )
    m=read_json(ELIGIBILITY_MANIFEST)
    if m.get("status")!="FROZEN_PHASE5_STEP0_ELIGIBILITY_MAP_V2":
        raise RuntimeError("Step-0 eligibility map is not frozen")
    if int(m.get("n_eligible_cells",-1))+int(m.get("n_gate_failed_cells",-1))!=16:
        raise RuntimeError("Step-0 eligibility map does not cover all 16 cells")
    return m


def _load_public_card(world_id:str,provider:str):
    root=HERE/"results"/"01_i1"/world_id
    freeze=read_json(root/"i1_freeze_manifest.json")
    contracts=load_phase5_contracts(HERE)
    if freeze.get("status")!="FROZEN_PHASE5_I1_COMPLETE_V2":
        raise RuntimeError(f"{world_id}: I1 not frozen")
    if freeze.get("battery_config_sha256")!=contracts.hashes["battery"]:
        raise RuntimeError(f"{world_id}: I1 battery hash mismatch")
    manifest=read_json(root/"public"/"i1_rho_conditioned_manifest_v2.json")
    rec=dict(manifest["cards"][provider])
    card_dir=root/"public"/provider
    if sha256_file(card_dir/"card.json")!=rec["card_json_sha256"]:
        raise RuntimeError(f"{world_id}/{provider}: card hash mismatch")
    if sha256_file(card_dir/"sigma_surface.csv")!=rec["sigma_surface_sha256"]:
        raise RuntimeError(f"{world_id}/{provider}: surface hash mismatch")
    metadata,surface=load_rho_conditioned_i1_provider_card(card_dir)
    return metadata,surface,rec


def _phase5_contract()->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    source=read_json(SOURCE_CONTRACT)
    cfg=copy.deepcopy(source)
    m1=contracts.methods["M1"]
    opt=cfg["joint_full_surface_lift"]["optimization"]
    declared=m1["optimization"]
    if int(opt["n_trials"])!=int(declared["n_trials"]):
        raise RuntimeError("M1 source n_trials differs from Phase-5 freeze")
    if int(opt["n_startup_trials"])!=int(declared["n_startup_trials"]):
        raise RuntimeError("M1 source startup count differs from Phase-5 freeze")
    if int(opt["shortlist_confirmation"]["top_k"])!=int(declared["shortlist_top_k"]):
        raise RuntimeError("M1 source shortlist differs from Phase-5 freeze")
    if int(opt["sampler_seed"])!=int(declared["TPE_sampler_seed"]):
        raise RuntimeError("M1 source sampler seed differs from Phase-5 freeze")

    seeds=contracts.seeds["provider_reconstruction"]
    search=inclusive_seed_range(seeds["M1_M2_local_search_CRN"])
    confirm=inclusive_seed_range(seeds["M1_M2_local_confirmation_CRN"])
    replay=inclusive_seed_range(seeds["M1_M2_local_replay_CRN"])
    opt["calibration_common_random_numbers"]["trajectory_seed_start"]=search[0]
    opt["calibration_common_random_numbers"]["n_trajectories"]=len(search)
    opt["shortlist_confirmation"]["trajectory_seed_start"]=confirm[0]
    opt["shortlist_confirmation"]["n_trajectories"]=len(confirm)
    opt["independent_replay"]["trajectory_seed_start"]=replay[0]
    opt["independent_replay"]["n_trajectories"]=len(replay)
    opt["boundary_fraction"]=float(m1["boundary_gate"]["boundary_fraction"])
    return cfg


def _edge_hits(result:dict[str,Any])->dict[str,str]:
    d=result["boundary_diagnostics"]
    frac=float(d["boundary_fraction"])
    hits={}
    for name,pos in d["normalized_search_positions"].items():
        p=float(pos)
        if p<=frac:
            hits[str(name)]="lower"
        elif p>=1.0-frac:
            hits[str(name)]="upper"
    return hits


def _expanded_contract(base:dict[str,Any],hits:dict[str,str])->dict[str,Any]:
    cfg=copy.deepcopy(base)
    search=cfg["joint_full_surface_lift"]["optimization"]["search_space"]
    if "service_cv" in hits:
        raise RuntimeError("CV edges are not expandable in Phase 5")
    if "mean_service_time" in hits:
        bounds=list(map(float,search["mu_over_workload_period_bounds"]))
        if hits["mean_service_time"]=="lower":
            bounds[0]/=10.0
        else:
            bounds[1]*=10.0
        search["mu_over_workload_period_bounds"]=bounds
    if "cost_rate" in hits:
        bounds=list(map(float,search["cost_rate_reference_multiplier_bounds"]))
        if hits["cost_rate"]=="lower":
            bounds[0]/=10.0
        else:
            bounds[1]*=10.0
        search["cost_rate_reference_multiplier_bounds"]=bounds
    return cfg


def _run_one(world_id:str,provider:str,result_root:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    root=Path(result_root).resolve()/world_id/"m1"/provider
    freeze_path=root/"m1_provider_freeze.json"
    if freeze_path.is_file():
        m=read_json(freeze_path)
        if m.get("status") in (
            "FROZEN_PHASE5_M1_PROVIDER_V2",
            "FROZEN_PHASE5_M1_PROVIDER_NOT_INSTANTIABLE_V2",
        ):
            return {
                "world":world_id,"provider":provider,
                "status":str(m["status"]),"wall_seconds":0.0,
            }
        raise RuntimeError(f"{world_id}/{provider}: unknown existing M1 freeze")

    started_utc=utc_now_iso()
    wall=time.perf_counter()
    metadata,surface,card_rec=_load_public_card(world_id,provider)
    base=_phase5_contract()
    root.mkdir(parents=True,exist_ok=True)

    print(f"M1 START {world_id}/{provider} round0",flush=True)
    r0=run_joint_lift_for_provider(
        provider=provider,
        metadata=metadata,
        public_surface=surface,
        contract=base,
        output_directory=root/"round0",
        smoke=False,
        quiet_simulator=True,
    )
    hits0=_edge_hits(r0)
    final=r0
    final_round=0
    expansion=None
    unresolved=[]

    if "service_cv" in hits0:
        unresolved.append(f"initial CV {hits0['service_cv']} edge")
    elif hits0:
        expansion={k:v for k,v in hits0.items()}
        expanded=_expanded_contract(base,hits0)
        print(
            f"M1 EXPAND {world_id}/{provider} once: {expansion}",
            flush=True,
        )
        r1=run_joint_lift_for_provider(
            provider=provider,
            metadata=metadata,
            public_surface=surface,
            contract=expanded,
            output_directory=root/"round1_expanded",
            smoke=False,
            quiet_simulator=True,
        )
        final=r1
        final_round=1
        hits1=_edge_hits(r1)
        if hits1:
            unresolved.extend(
                f"post-expansion {name} {edge} edge"
                for name,edge in sorted(hits1.items())
            )

    instantiable=not unresolved
    status=(
        "FROZEN_PHASE5_M1_PROVIDER_V2"
        if instantiable
        else "FROZEN_PHASE5_M1_PROVIDER_NOT_INSTANTIABLE_V2"
    )
    summary_path=root/"m1_final_parameters.json"
    payload={
        "status":status,
        "provider_world_id":world_id,
        "provider_id":provider,
        "instantiable":instantiable,
        "final_round":final_round,
        "parameters":dict(final["parameters"]) if instantiable else None,
        "selected_parameters_before_not_instantiable":(
            None if instantiable else dict(final["parameters"])
        ),
        "initial_boundary_hits":hits0,
        "one_round_expansion":expansion,
        "unresolved_boundary_reasons":unresolved,
        "confirmation_metrics":final["shortlist_confirmation"]["metrics"],
        "independent_replay_metrics":final["independent_replay"]["metrics"],
        "graph_whitebox_used":False,
        "step0_whitebox_outcomes_used":False,
    }
    write_json(summary_path,payload)

    search=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_search_CRN"]
    )
    confirm=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_confirmation_CRN"]
    )
    replay=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_replay_CRN"]
    )
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status=status,
        inputs={
            "provider_world_id":world_id,
            "provider_id":provider,
            "public_card_json_sha256":card_rec["card_json_sha256"],
            "public_sigma_surface_sha256":card_rec["sigma_surface_sha256"],
            "source_m1_contract_sha256":sha256_file(SOURCE_CONTRACT),
            "one_round_boundary_expansion_rule":True,
            "hidden_provider_parameters_used":False,
            "step0_WB_values_used":False,
            "graph_WB_used":False,
        },
        seed_banks={
            "local_search":{"start":search[0],"end_inclusive":search[-1],"n":len(search)},
            "local_confirmation":{"start":confirm[0],"end_inclusive":confirm[-1],"n":len(confirm)},
            "local_replay":{"start":replay[0],"end_inclusive":replay[-1],"n":len(replay)},
        },
        outputs={"m1_final_parameters":str(summary_path)},
        started_utc=started_utc,
    )
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall)
    manifest["initial_boundary_hits"]=hits0
    manifest["one_round_expansion"]=expansion
    manifest["unresolved_boundary_reasons"]=unresolved
    write_json(freeze_path,manifest)
    print(
        f"M1 {'PASS' if instantiable else 'NOT_INSTANTIABLE'} "
        f"{world_id}/{provider} | wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {
        "world":world_id,"provider":provider,"status":status,
        "wall_seconds":manifest["python_wall_seconds"],
    }


def _freeze_world_manifests(result_root:Path)->None:
    contracts=load_phase5_contracts(HERE)
    for world in canonical_provider_world_ids(contracts):
        root=result_root/world/"m1"
        rows=[]
        for provider in PROVIDERS:
            path=root/provider/"m1_provider_freeze.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            m=read_json(path)
            rows.append({
                "provider":provider,
                "status":m["status"],
                "manifest_sha256":sha256_file(path),
            })
        table=pd.DataFrame(rows)
        table_path=root/"m1_provider_status.csv"
        table.to_csv(table_path,index=False)
        status=(
            "FROZEN_PHASE5_M1_WORLD_V2"
            if table["status"].eq("FROZEN_PHASE5_M1_PROVIDER_V2").all()
            else "FROZEN_PHASE5_M1_WORLD_WITH_NOT_INSTANTIABLE_PROVIDER_V2"
        )
        manifest=base_manifest(
            contracts,stage_id="RECONSTRUCTION",status=status,
            inputs={
                "provider_world_id":world,
                "provider_level_only":True,
                "graph_cell_step0_eligibility_does_not_gate_reconstruction":True,
            },
            seed_banks={},
            outputs={"m1_provider_status":str(table_path)},
            started_utc=utc_now_iso(),
        )
        manifest["provider_manifest_sha256"]={
            row["provider"]:row["manifest_sha256"] for row in rows
        }
        write_json(root/"m1_world_freeze_manifest.json",manifest)


def main()->None:
    p=argparse.ArgumentParser(description="Official Phase-5 V2 M1 reconstruction")
    t=p.add_mutually_exclusive_group(required=True)
    t.add_argument("--world",choices=("P1","P2","P3","P4"))
    t.add_argument("--all-worlds",action="store_true")
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--result-root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    _require_step0_frozen()
    contracts=load_phase5_contracts(HERE)
    worlds=canonical_provider_world_ids(contracts) if args.all_worlds else (str(args.world),)
    tasks=[(w,p) for w in worlds for p in PROVIDERS]
    started=time.perf_counter()
    rows=[]
    if args.workers==1:
        for w,pid in tasks:
            rows.append(_run_one(w,pid,str(args.result_root)))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={
                pool.submit(_run_one,w,pid,str(args.result_root)):(w,pid)
                for w,pid in tasks
            }
            for f in concurrent.futures.as_completed(futures):
                w,pid=futures[f]
                try:
                    rows.append(f.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"M1 worker failed for {w}/{pid}") from exc
    _freeze_world_manifests(args.result_root.resolve())
    table=pd.DataFrame(rows).sort_values(["world","provider"]).reset_index(drop=True)
    print("\nPHASE5_M1_RECONSTRUCTION_SUMMARY")
    print(table.to_string(index=False))
    print(
        f"stage_wall={(time.perf_counter()-started)/60:.1f} min "
        f"workers={args.workers}"
    )


if __name__=="__main__":
    main()
