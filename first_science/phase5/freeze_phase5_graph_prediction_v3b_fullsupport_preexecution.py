"""Freeze Phase-5 V3b full-support graph-prediction pre-execution state.

No scientific graph simulation occurs here.  This stage verifies the passed
full-support adapter smoke, the frozen Step-0 eligibility map, and the frozen
V3b provider-selection audit.  It then derives and hash-freezes the exact
provider-world-specific M3 FULL343 B=1400 allocations from the already frozen
343-member joint weights.

The final graph white-box bank remains unread and embargoed.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE4=FIRST_SCIENCE/"phase4"
if str(PHASE4) not in sys.path:
    sys.path.insert(0,str(PHASE4))

from m3_v4_dominant_mass_graph import _integer_minimax_allocations  # noqa:E402
from phase5_runtime_v2 import (  # noqa:E402
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

CFG=HERE/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"
STEP0_ROOT=HERE/"results"/"02_step0"
V3B_ROOT=HERE/"results"/"03_reconstruction_v3b"
SMOKE=HERE/"smoke"/"v3b_fullsupport_graph_adapter"/"phase5_v3b_fullsupport_graph_adapter_smoke_manifest.json"
DEFAULT_ROOT=HERE/"results"/"04_prediction_v3b_fullsupport"
PREP_DIRNAME="_preexecution"

EXPECTED_CFG="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT"
EXPECTED_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT"
EXPECTED_SMOKE="FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_ADAPTER_SMOKE_PASS"
EXPECTED_AUDIT="FROZEN_PHASE5_V3B_SELECTION_MECHANICAL_AUDIT_PASS"
SUPPORT_SIZE=343
BUDGET=1400
TOL=1e-12


def _allocation(world:str,cfg:dict)->tuple[pd.DataFrame,dict]:
    path=V3B_ROOT/world/"m3_joint_support_343.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    support=pd.read_csv(path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    if len(support)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: full M3 support !=343")
    if support["joint_rank"].astype(int).tolist()!=list(range(1,SUPPORT_SIZE+1)):
        raise RuntimeError(f"{world}: M3 joint ranks changed")
    weights=support["joint_weight"].astype(float).to_numpy()
    if abs(float(weights.sum())-1.0)>1e-10:
        raise RuntimeError(f"{world}: M3 weights do not normalize")
    if not np.all(np.diff(weights)<=TOL):
        raise RuntimeError(f"{world}: M3 weights not descending")

    alloc=_integer_minimax_allocations(weights,[BUDGET]).copy()
    if len(alloc)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: allocation rank count !=343")
    if int(alloc["n_trajectories"].astype(int).sum())!=BUDGET:
        raise RuntimeError(f"{world}: allocation does not sum to {BUDGET}")
    if (alloc["n_trajectories"].astype(int)<1).any():
        raise RuntimeError(f"{world}: N<1 in full-support allocation")

    seed_base=int(cfg["seeds"]["M3"]["seed_base"])
    stride=int(cfg["seeds"]["M3"]["seed_block_stride"])
    alloc["joint_weight"]=weights
    alloc["seed_start"]=[
        seed_base+(int(r)-1)*stride for r in alloc["rank"]
    ]
    alloc["seed_end_inclusive"]=[
        int(s)+int(n)-1
        for s,n in zip(alloc["seed_start"],alloc["n_trajectories"])
    ]
    if any(int(n)>=stride for n in alloc["n_trajectories"]):
        raise RuntimeError(f"{world}: allocation reaches seed-block stride")
    starts=alloc["seed_start"].astype(int).to_numpy()
    ends=alloc["seed_end_inclusive"].astype(int).to_numpy()
    if np.any(ends[:-1]>=starts[1:]):
        raise RuntimeError(f"{world}: M3 rank seed prefixes overlap")

    summary={
        "provider_world_id":world,
        "support_size":SUPPORT_SIZE,
        "budget":BUDGET,
        "members_with_one_trajectory":int((alloc["n_trajectories"].astype(int)==1).sum()),
        "rank1_n":int(alloc.loc[alloc["rank"].astype(int)==1,"n_trajectories"].iloc[0]),
        "max_n":int(alloc["n_trajectories"].max()),
        "min_n":int(alloc["n_trajectories"].min()),
        "worst_case_mc_variance_bound":float(alloc["worst_case_mc_variance_bound_budget"].iloc[0]),
        "worst_case_mc_se_bound":float(alloc["worst_case_mc_se_bound_budget"].iloc[0]),
        "full_support_mass":float(weights.sum()),
        "full_support_truncation_bound":0.0,
    }
    return alloc,summary


def run(root:Path,*,reset:bool)->Path:
    cfg=read_json(CFG)
    seeds=read_json(SEEDS)
    smoke=read_json(SMOKE)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected full-support graph contract")
    if seeds.get("status")!=EXPECTED_SEEDS:
        raise RuntimeError("unexpected full-support seed registry")
    if smoke.get("status")!=EXPECTED_SMOKE:
        raise RuntimeError("full-support adapter smoke has not passed")
    if smoke.get("scientific_evidence") is not False:
        raise RuntimeError("full-support smoke incorrectly marked scientific")
    if smoke.get("checks",{}).get("final_WB_read") is not False:
        raise RuntimeError("full-support smoke final-WB firewall invalid")
    if smoke.get("graph_contract_sha256")!=sha256_file(CFG):
        raise RuntimeError("full-support smoke graph-contract hash mismatch")
    if smoke.get("seed_registry_sha256")!=sha256_file(SEEDS):
        raise RuntimeError("full-support smoke seed-registry hash mismatch")

    audit_path=V3B_ROOT/"phase5_v3b_selection_audit_manifest.json"
    audit=read_json(audit_path)
    if audit.get("status")!=EXPECTED_AUDIT:
        raise RuntimeError("V3b reconstruction-selection audit has not passed")

    eligibility_path=STEP0_ROOT/"phase5_step0_eligibility.csv"
    eligibility_manifest_path=STEP0_ROOT/"phase5_step0_eligibility_manifest.json"
    eligibility=pd.read_csv(eligibility_path)
    if len(eligibility)!=16:
        raise RuntimeError("Step-0 eligibility map must contain 16 cells")
    ok=eligibility[eligibility["eligibility"].astype(str)=="ELIGIBLE"]
    failed=eligibility[eligibility["eligibility"].astype(str)=="GATE_FAILED_STEP0"]
    if len(ok)!=12 or len(failed)!=4:
        raise RuntimeError("expected 12 eligible and 4 gate-failed cells")
    if set(failed["provider_world_id"].astype(str))!={"P2"}:
        raise RuntimeError("expected all gate-failed cells to belong to P2")
    worlds=sorted(ok["provider_world_id"].astype(str).unique().tolist())
    if worlds!=["P1","P3","P4"]:
        raise RuntimeError(f"unexpected eligible worlds {worlds}")

    contracts=load_phase5_contracts(HERE)
    expected={
        physical_cell_id(p,g)
        for p in canonical_provider_world_ids(contracts)
        for g in canonical_graph_ids(contracts)
    }
    if set(eligibility["physical_cell_id"].astype(str))!=expected:
        raise RuntimeError("Step-0 eligibility physical-cell set changed")

    root=root.resolve()
    pre=root/PREP_DIRNAME
    if reset and pre.exists():
        shutil.rmtree(pre)
    if pre.exists():
        mf=pre/"phase5_v3b_fullsupport_preexecution_freeze_manifest.json"
        if mf.is_file() and read_json(mf).get("status")=="FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_PREEXECUTION":
            raise RuntimeError(f"full-support pre-execution already frozen at {mf}")
    pre.mkdir(parents=True,exist_ok=True)

    outputs={}
    summaries=[]
    for world in worlds:
        alloc,summary=_allocation(world,cfg)
        path=pre/f"m3_fullsupport_allocation_{world}.csv"
        alloc.to_csv(path,index=False)
        outputs[f"m3_fullsupport_allocation_{world}"]=str(path)
        summaries.append(summary)

    summary=pd.DataFrame(summaries).sort_values("provider_world_id",kind="mergesort").reset_index(drop=True)
    summary_path=pre/"m3_fullsupport_allocation_summary.csv"
    summary.to_csv(summary_path,index=False)
    outputs["m3_fullsupport_allocation_summary"]=str(summary_path)

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
        "status":"FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_PREEXECUTION",
        "stage_id":"BLIND_PREDICTION_PREEXECUTION_V3B_FULLSUPPORT",
        "protocol_version":"PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT_2026-10-06",
        "scientific_evidence":False,
        "code_commit":git_head(),
        "graph_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "fullsupport_smoke_manifest_sha256":sha256_file(SMOKE),
        "v3b_selection_audit_sha256":sha256_file(audit_path),
        "step0_eligibility_table_sha256":sha256_file(eligibility_path),
        "step0_eligibility_manifest_sha256":sha256_file(eligibility_manifest_path),
        "inputs":{
            "eligible_provider_worlds":worlds,
            "eligible_cell_count":12,
            "gate_failed_cell_count":4,
            "M3_support_size":343,
            "M3_budget_per_eligible_cell":1400,
            "allocation_rule":"integer minimax over all frozen full-support joint weights",
            "graph_simulation_run":False,
            "graph_WB_read":False,
            "final_WB_read":False,
        },
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "started_utc":utc_now_iso(),
        "completed_utc":utc_now_iso(),
    }
    manifest_path=pre/"phase5_v3b_fullsupport_preexecution_freeze_manifest.json"
    write_json(manifest_path,manifest)

    print("PHASE5_V3B_FULLSUPPORT_GRAPH_PREEXECUTION_FREEZE_PASS")
    print(summary.to_string(index=False))
    print("eligible_cells 12")
    print("gate_failed_cells 4")
    print("graph_simulation_run False")
    print("final_WB_read False")
    print("manifest",manifest_path)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(description="Freeze V3b full-support graph pre-execution state")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    p.add_argument("--reset",action="store_true")
    args=p.parse_args()
    run(args.root,reset=bool(args.reset))


if __name__=="__main__":
    main()
