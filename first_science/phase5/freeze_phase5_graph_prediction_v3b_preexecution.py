"""Freeze the Phase-5 V3b graph-prediction pre-execution state.

This stage performs no graph simulation.  It verifies that the real engineering
adapter smoke passed, rechecks the frozen Step-0 eligibility map and V3b
selection audit, derives the provider-world-specific M3 B=1400 integer minimax
allocations from the already frozen Top14 weights, and hash-freezes those
allocations before any scientific V3b graph trajectory is executed.

It never reads final graph white-box evidence.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from phase5_runtime_v2 import (
    canonical_graph_ids,
    canonical_provider_world_ids,
    git_head,
    load_phase5_contracts,
    physical_cell_id,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE4=FIRST_SCIENCE/"phase4"
import sys
if str(PHASE4) not in sys.path:
    sys.path.insert(0,str(PHASE4))
from m3_v4_dominant_mass_graph import _integer_minimax_allocations  # noqa:E402

GRAPH_CFG=HERE/"config_phase5_graph_prediction_v3b.json"
SEEDS_V3=HERE/"config_phase5_seed_registry_v3.json"
STEP0_ROOT=HERE/"results"/"02_step0"
V3B_ROOT=HERE/"results"/"03_reconstruction_v3b"
SMOKE_MANIFEST=HERE/"smoke"/"v3b_graph_adapter"/"phase5_v3b_graph_adapter_smoke_manifest.json"
DEFAULT_ROOT=HERE/"results"/"04_prediction_v3b"
PREP_DIRNAME="_preexecution"
EXPECTED_SMOKE="FROZEN_PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS"
EXPECTED_AUDIT="FROZEN_PHASE5_V3B_SELECTION_MECHANICAL_AUDIT_PASS"
EXPECTED_CFG="FROZEN_PHASE5_GRAPH_PREDICTION_EXECUTION_V3B"
EXPECTED_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3"
TOL=1e-12


def _eligible_worlds(eligibility:pd.DataFrame)->list[str]:
    ok=eligibility[eligibility["eligibility"].astype(str)=="ELIGIBLE"].copy()
    worlds=sorted(ok["provider_world_id"].astype(str).unique().tolist())
    return worlds


def _allocation_for_world(world:str,cfg:dict)->tuple[pd.DataFrame,dict]:
    full_path=V3B_ROOT/world/"m3_joint_support_343.csv"
    top_path=V3B_ROOT/world/"m3_joint_support_top14.csv"
    if not full_path.is_file() or not top_path.is_file():
        raise FileNotFoundError(f"{world}: missing frozen V3b M3 support")

    full=pd.read_csv(full_path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    top=pd.read_csv(top_path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    if len(full)!=343 or len(top)!=14:
        raise RuntimeError(f"{world}: M3 support cardinality mismatch")
    if full["joint_rank"].astype(int).tolist()!=list(range(1,344)):
        raise RuntimeError(f"{world}: full M3 joint ranks changed")
    if top["joint_rank"].astype(int).tolist()!=list(range(1,15)):
        raise RuntimeError(f"{world}: Top14 ranks changed")

    prefix=full.head(14)
    for col in full.columns:
        a=prefix[col].reset_index(drop=True)
        b=top[col].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            if not np.allclose(a.to_numpy(float),b.to_numpy(float),rtol=0.0,atol=1e-15,equal_nan=True):
                raise RuntimeError(f"{world}: Top14 numeric prefix mismatch in {col}")
        else:
            if a.fillna("<NA>").astype(str).tolist()!=b.fillna("<NA>").astype(str).tolist():
                raise RuntimeError(f"{world}: Top14 prefix mismatch in {col}")

    full_sum=float(full["joint_weight"].astype(float).sum())
    if abs(full_sum-1.0)>1e-10:
        raise RuntimeError(f"{world}: full M3 weights do not normalize")
    retained=float(top["joint_weight"].astype(float).sum())
    alpha=top["joint_weight"].astype(float).to_numpy()/retained
    if abs(float(alpha.sum())-1.0)>TOL:
        raise RuntimeError(f"{world}: Top14 normalized weights do not sum to one")

    budget=int(cfg["methods"]["M3"]["graph_budget_per_physical_cell"])
    alloc=_integer_minimax_allocations(alpha,[budget]).copy()
    if int(alloc["n_trajectories"].sum())!=budget:
        raise RuntimeError(f"{world}: M3 allocation does not sum to {budget}")
    if (alloc["n_trajectories"].astype(int)<1).any():
        raise RuntimeError(f"{world}: M3 allocation contains N<1")
    if alloc["rank"].astype(int).tolist()!=list(range(1,15)):
        raise RuntimeError(f"{world}: M3 allocation rank order changed")

    top_by_rank=top.set_index("joint_rank")
    alloc["joint_weight_full_support"]=[
        float(top_by_rank.loc[int(r),"joint_weight"]) for r in alloc["rank"]
    ]
    alloc["retained_mass_top14"]=retained
    alloc["omitted_mass_top14"]=1.0-retained

    seed_base=int(cfg["seeds"]["M3"]["seed_base"])
    stride=int(cfg["seeds"]["M3"]["seed_block_stride"])
    alloc["seed_start"]=[
        seed_base+(int(r)-1)*stride for r in alloc["rank"]
    ]
    alloc["seed_end_inclusive"]=[
        int(s)+int(n)-1
        for s,n in zip(alloc["seed_start"],alloc["n_trajectories"])
    ]
    if any(int(n)>=stride for n in alloc["n_trajectories"]):
        raise RuntimeError(f"{world}: M3 allocation exceeds seed-block stride")

    summary={
        "provider_world_id":world,
        "full_support_size":343,
        "retained_support_size":14,
        "retained_mass_top14":retained,
        "omitted_mass_top14":1.0-retained,
        "budget":budget,
        "rank1_n":int(alloc.loc[alloc["rank"].astype(int)==1,"n_trajectories"].iloc[0]),
        "max_rank_n":int(alloc["n_trajectories"].max()),
        "min_rank_n":int(alloc["n_trajectories"].min()),
        "worst_case_mc_variance_bound":float(alloc["worst_case_mc_variance_bound_budget"].iloc[0]),
        "worst_case_mc_se_bound":float(alloc["worst_case_mc_se_bound_budget"].iloc[0]),
    }
    return alloc,summary


def run(root:Path,*,reset:bool)->Path:
    cfg=read_json(GRAPH_CFG)
    seeds=read_json(SEEDS_V3)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected V3b graph-prediction contract")
    if seeds.get("status")!=EXPECTED_SEEDS:
        raise RuntimeError("unexpected V3 seed registry")

    smoke=read_json(SMOKE_MANIFEST)
    if smoke.get("status")!=EXPECTED_SMOKE:
        raise RuntimeError("real V3b graph-adapter smoke has not passed")
    if smoke.get("scientific_evidence") is not False or smoke.get("inputs",{}).get("final_WB_read") is not False:
        raise RuntimeError("smoke provenance/firewall flags invalid")
    if smoke.get("graph_prediction_contract_sha256")!=sha256_file(GRAPH_CFG):
        raise RuntimeError("smoke was not run against the current graph-prediction contract")
    if smoke.get("v3_seed_registry_sha256")!=sha256_file(SEEDS_V3):
        raise RuntimeError("smoke V3 seed-registry hash mismatch")

    audit_path=V3B_ROOT/"phase5_v3b_selection_audit_manifest.json"
    audit=read_json(audit_path)
    if audit.get("status")!=EXPECTED_AUDIT:
        raise RuntimeError("V3b reconstruction-selection mechanical audit has not passed")

    eligibility_path=STEP0_ROOT/"phase5_step0_eligibility.csv"
    eligibility_manifest=STEP0_ROOT/"phase5_step0_eligibility_manifest.json"
    eligibility=pd.read_csv(eligibility_path)
    if len(eligibility)!=16:
        raise RuntimeError("Step-0 eligibility map must contain 16 cells")
    ok=eligibility[eligibility["eligibility"].astype(str)=="ELIGIBLE"]
    failed=eligibility[eligibility["eligibility"].astype(str)=="GATE_FAILED_STEP0"]
    if len(ok)!=12 or len(failed)!=4:
        raise RuntimeError("expected 12 eligible + 4 Step-0-failed cells")
    if set(failed["provider_world_id"].astype(str))!={"P2"}:
        raise RuntimeError("expected all four Step-0 failures to be P2")
    eligible_worlds=_eligible_worlds(eligibility)
    if eligible_worlds!=["P1","P3","P4"]:
        raise RuntimeError(f"unexpected eligible provider worlds {eligible_worlds}")

    contracts=load_phase5_contracts(HERE)
    expected_cells={
        physical_cell_id(p,g)
        for p in canonical_provider_world_ids(contracts)
        for g in canonical_graph_ids(contracts)
    }
    if set(eligibility["physical_cell_id"].astype(str))!=expected_cells:
        raise RuntimeError("Step-0 eligibility cell set changed")

    root=root.resolve()
    pre=root/PREP_DIRNAME
    if reset and pre.exists():
        shutil.rmtree(pre)
    if pre.exists():
        manifest_path=pre/"phase5_v3b_preexecution_freeze_manifest.json"
        if manifest_path.is_file():
            old=read_json(manifest_path)
            if old.get("status")=="FROZEN_PHASE5_V3B_GRAPH_PREEXECUTION":
                raise RuntimeError(
                    f"pre-execution state already frozen at {manifest_path}; "
                    "do not overwrite without --reset"
                )
    pre.mkdir(parents=True,exist_ok=True)

    rows=[]
    outputs={}
    for world in eligible_worlds:
        alloc,summary=_allocation_for_world(world,cfg)
        path=pre/f"m3_allocation_{world}.csv"
        alloc.to_csv(path,index=False)
        outputs[f"m3_allocation_{world}"]=str(path)
        rows.append(summary)

    summary=pd.DataFrame(rows).sort_values("provider_world_id",kind="mergesort").reset_index(drop=True)
    summary_path=pre/"m3_allocation_summary.csv"
    summary.to_csv(summary_path,index=False)
    outputs["m3_allocation_summary"]=str(summary_path)

    status_rows=[]
    for rec in eligibility.sort_values(["provider_world_id","graph_id"],kind="mergesort").itertuples(index=False):
        status_rows.append({
            "physical_cell_id":str(rec.physical_cell_id),
            "provider_world_id":str(rec.provider_world_id),
            "graph_id":str(rec.graph_id),
            "preexecution_status":(
                "READY_FOR_BLIND_PREDICTION"
                if str(rec.eligibility)=="ELIGIBLE"
                else "GATE_FAILED_STEP0_NO_PREDICTION"
            ),
        })
    status=pd.DataFrame(status_rows)
    status_path=pre/"preexecution_cell_status.csv"
    status.to_csv(status_path,index=False)
    outputs["preexecution_cell_status"]=str(status_path)

    manifest={
        "status":"FROZEN_PHASE5_V3B_GRAPH_PREEXECUTION",
        "stage_id":"BLIND_PREDICTION_PREEXECUTION_V3B",
        "protocol_version":"PHASE5_GRAPH_PREDICTION_V3B_2026-10-06",
        "scientific_evidence":False,
        "code_commit":git_head(),
        "graph_prediction_contract_sha256":sha256_file(GRAPH_CFG),
        "v3_seed_registry_sha256":sha256_file(SEEDS_V3),
        "v3b_selection_audit_sha256":sha256_file(audit_path),
        "step0_eligibility_table_sha256":sha256_file(eligibility_path),
        "step0_eligibility_manifest_sha256":sha256_file(eligibility_manifest),
        "graph_adapter_smoke_manifest_sha256":sha256_file(SMOKE_MANIFEST),
        "inputs":{
            "eligible_provider_worlds":eligible_worlds,
            "eligible_cell_count":12,
            "gate_failed_cell_count":4,
            "M3_budget_per_eligible_cell":1400,
            "allocation_rule":"integer minimax over provider-world-specific frozen Top14 weights",
            "graph_simulation_run":False,
            "graph_WB_read":False,
            "final_WB_read":False,
        },
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "started_utc":utc_now_iso(),
        "completed_utc":utc_now_iso(),
    }
    manifest_path=pre/"phase5_v3b_preexecution_freeze_manifest.json"
    write_json(manifest_path,manifest)

    print("PHASE5_V3B_GRAPH_PREEXECUTION_FREEZE_PASS")
    print(summary.to_string(index=False))
    print("eligible_cells 12")
    print("gate_failed_cells 4")
    print("graph_simulation_run False")
    print("final_WB_read False")
    print("manifest",manifest_path)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(description="Freeze V3b graph-prediction pre-execution state")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    p.add_argument("--reset",action="store_true")
    args=p.parse_args()
    run(args.root,reset=bool(args.reset))


if __name__=="__main__":
    main()
