#!/usr/bin/env python3
"""Isolated B0001 final reference N=1000 per cell: ORIGINAL Phase5 simulation.

Uses the frozen P1_A02/P3_A01/P4_A01 physical worlds from B0001 Step-0,
and preauthorized fresh final reference seeds. All blind predictions are
frozen, rehashed before each cell, and NEVER read to generate reference data.
Reference predictions/accuracy are not computed here.

--check: no private-world parameters or WB outcomes read, no writes.
--run: 12 reference cells, sequential and restartable per trajectory.
        This crosses the prospective blind/WB boundary; do not launch until
        the authorization preflight has passed and been independently reviewed.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
import pandas as pd

import preflight_b0001_final_wb_v1 as gate

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parents[1]/"phase5"
ROLES=gate.ROLES
GRAPHS=gate.GRAPHS
CELL_STATUS="B0001_FINAL_WB_N1000_CELL_FROZEN"
GLOBAL_STATUS="B0001_FINAL_WB_N1000_12_CELL_FROZEN_EVALUATION_NOT_YET_AUDITED"


def inputs(a):
    a.auth=a.authorization/"b0001_final_wb_authorization_freeze.json"
    gate.require(a.auth.is_file(),"Final reference preflight authorization absent")
    auth=gate.load(a.auth)
    gate.require(auth["status"]==gate.STATUS
                 and auth["reference_execution_authorized"] is True
                 and auth["analysis_authorized"] is False
                 and auth["final_WB_outcomes_read"] is False,
                 "Final reference authorization altered")
    gate.require(auth["postrun_integrity_audit_sha256"]==
                 gate.sha(a.audit/"b0001_full343_postrun_integrity_audit.json")
                 and auth["blind_global_freeze_sha256"]==
                 gate.sha(a.graph/"scientific"/
                          "b0001_full343_global_prediction_freeze.json"),
                 "Reference authorization no longer matches frozen predictions")
    gate.require(auth["b0001_step0_eligibility_sha256"]==gate.sha(a.eligibility)
                 and auth["public_staging_manifest_sha256"]==
                 gate.sha(a.staging/"b0001_public_inputs_manifest.json"),
                 "Final WB selected worlds or queries changed")
    gate.require(auth["original_reference_runner_sha256"]==
                 gate.sha(PHASE5/"run_phase5_final_wb_v3b_fullsupport.py")
                 and auth["original_reference_contract_sha256"]==
                 gate.sha(PHASE5/"config_phase5_final_wb_v3b_fullsupport.json"),
                 "Final-WB original scientific method changed since authorization")
    frozen=gate.load(a.graph/"scientific"/"b0001_full343_global_prediction_freeze.json")
    for cell,hashed in frozen["prediction_manifest_sha256_by_cell"].items():
        gate.require(gate.sha(a.graph/"scientific"/cell/
                              "prediction_manifest.json")==hashed,
                     "Blind prediction changed after WB gate: "+cell)
    for role in ROLES:
        world=auth["selected_worlds"][role]
        gate.require(world["candidate_id"]==gate.WORLD_IDS[role]
                     and gate.sha(Path(world["source_world_contract"]))==
                     world["world_contract_sha256"],
                     "Selected physical world contract mutated: "+role)
    seed=auth["final_reference_seed_bank"]
    gate.require(seed["start"]==gate.WB_START
                 and seed["end_inclusive"]==gate.WB_START+999
                 and seed["n"]==1000,
                 "Final WB seed bank differs from B0001 freeze")
    gate.require(a.out != a.graph and a.graph not in a.out.parents
                 and a.out!=a.authorization and a.authorization not in a.out.parents,
                 "Reference output cannot overlap frozen input")
    return auth


def historical():
    for folder in (PHASE5.parent/"phase1",PHASE5.parent/"phase2",PHASE5):
        if str(folder) not in sys.path:
            sys.path.insert(0,str(folder))
    import run_phase5_final_wb_v3b_fullsupport as wb
    return wb


def execute(a,auth):
    wb=historical()
    root=a.out
    seed_block=auth["final_reference_seed_bank"]
    seeds=list(range(int(seed_block["start"]),
                     int(seed_block["end_inclusive"])+1))
    gate.require(len(seeds)==1000,"Final WB N=1000 seed coverage")
    global_path=root/"b0001_final_wb_global_freeze.json"
    gate.require(not global_path.exists(),
                 "B0001 final reference already globally frozen")
    for role in ROLES:
        physical_file=Path(auth["selected_worlds"][role]["source_world_contract"])
        physical_root=physical_file.parent
        # Load the isolated physical-world contract, not the old P1/P3/P4.
        contracts=wb.load_phase5_contracts(physical_root)
        identity=wb.provider_world(contracts,role)
        gate.require(identity["id"]==role,
                     "Selected physical contract missing provider role: "+role)
        # The original simulator internally loads from module HERE; patch this
        # only for the duration of the reference cell. All other source
        # scientific functions and simulator code remain unchanged.
        for graph in GRAPHS:
            cell_id=f"{role}__{graph}"
            cell_root=root/cell_id
            manifest=cell_root/"final_wb_manifest.json"
            if manifest.is_file():
                old=gate.load(manifest)
                gate.require(old["status"]==CELL_STATUS
                             and old["authorization_sha256"]==gate.sha(a.auth),
                             "Frozen reference cell identity/authority invalid: "+cell_id)
                for key,filename in (("final_wb_ledger","final_wb_ledger.csv"),
                                     ("final_wb_curves","final_wb_curves.csv")):
                    gate.require(gate.sha(cell_root/filename)==old["output_sha256"][key],
                                 "Previously frozen final WB output mutated: "+cell_id)
                print("B0001_FINAL_WB_CELL_CACHED",cell_id,flush=True)
                continue
            # Re-check source blind predictions before opening each reference.
            inputs(a)
            q_file=a.staging/"frozen_queries"/cell_id/"step0_frozen_queries.csv"
            gate.require(q_file.is_file(),"Missing public frozen queries: "+cell_id)
            started=time.perf_counter()
            old_here,old_root,old_step0,old_wb_seeds=(
                wb.HERE,wb.ROOT,wb.STEP0_ROOT,wb._wb_seeds)
            try:
                wb.HERE=physical_root
                wb.ROOT=root
                wb.STEP0_ROOT=a.staging/"frozen_queries"
                wb._wb_seeds=lambda:seeds
                queries=wb._queries(cell_id)
                ledger,elapsed=wb._simulate_cell_ledger(
                    world_id=role,graph_id=graph,cell_root=cell_root)
                curves=wb._score_queries(ledger,queries)
            finally:
                wb.HERE=old_here
                wb.ROOT=old_root
                wb.STEP0_ROOT=old_step0
                wb._wb_seeds=old_wb_seeds
            gate.require(len(curves)==735
                         and curves.query_id.nunique()==15
                         and set(curves.wb_n.astype(int))=={1000},
                         "Final WB query/trajectory coverage invalid: "+cell_id)
            curves_path=cell_root/"final_wb_curves.csv"
            curves.to_csv(curves_path,index=False)
            ledger_path=cell_root/"final_wb_ledger.csv"
            gate.require(ledger_path.is_file()
                         and set(ledger.trajectory_seed.astype(int))==set(seeds),
                         "Final WB ledger identity mismatch: "+cell_id)
            mf={
                "status":CELL_STATUS,
                "scientific_evidence":True,
                "physical_cell_id":cell_id,
                "provider_world_id":role,
                "graph_id":graph,
                "selected_candidate_id":auth["selected_worlds"][role]["candidate_id"],
                "selected_physical_contract_sha256":
                    auth["selected_worlds"][role]["world_contract_sha256"],
                "authorization_sha256":gate.sha(a.auth),
                "frozen_query_sha256":gate.sha(q_file),
                "prediction_manifest_sha256":
                    gate.sha(a.graph/"scientific"/cell_id/"prediction_manifest.json"),
                "reference_seeds":seed_block,
                "query_count":15,"horizon_count":49,"wb_n":1000,
                "outputs":{"final_wb_ledger":str(ledger_path),
                           "final_wb_curves":str(curves_path)},
                "output_sha256":{"final_wb_ledger":gate.sha(ledger_path),
                                 "final_wb_curves":gate.sha(curves_path)},
                "generation_uses_prediction_values":False,
                "method_selection_changed":False,
                "wall_seconds":time.perf_counter()-started,
            }
            gate.save(manifest,mf)
            print("B0001_FINAL_WB_CELL_PASS",cell_id,"N=1000",
                  f"elapsed={mf['wall_seconds']/60:.1f}min",flush=True)
    # Global status does NOT yet unlock accuracy analysis: the independent
    # final-reference mechanical audit is a separate step.
    hashes={}
    for role in ROLES:
        for graph in GRAPHS:
            name=f"{role}__{graph}"
            manifest=root/name/"final_wb_manifest.json"
            gate.require(manifest.is_file(),"Missing final WB cell: "+name)
            hashes[name]=gate.sha(manifest)
    result={
        "status":GLOBAL_STATUS,
        "cell_manifest_sha256":hashes,
        "n_cells":12,"reference_trajectories":12000,
        "final_reference_authorization_sha256":gate.sha(a.auth),
        "postrun_prediction_audit_sha256":
            auth["postrun_integrity_audit_sha256"],
        "reference_method_source_sha256":
            gate.sha(PHASE5/"run_phase5_final_wb_v3b_fullsupport.py"),
        "prediction_files_modified":False,
        "evaluation_unlocked":False,
        "seven_method_plan_b_complete":False,
    }
    gate.save(global_path,result)
    print("B0001_FINAL_WB_12_CELL_REFERENCE_FREEZE_PASS",flush=True)
    print("EVALUATION_BLOCKED_PENDING_REFERENCE_MECHANICAL_AUDIT",flush=True)
    print("FREEZE",global_path,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mx=p.add_mutually_exclusive_group(required=True)
    mx.add_argument("--check",action="store_true")
    mx.add_argument("--run",action="store_true")
    for name in ("authorization","audit","graph","staging","eligibility","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    for name in ("authorization","audit","graph","staging","eligibility","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    auth=inputs(a)
    if a.check:
        print("B0001_FINAL_WB_ADAPTER_CHECK_PASS 12 selected cells N=1000",
              flush=True)
        print("NO_HIDDEN_PHYSICAL_PARAMETERS_READ / NO_SIMULATIONS",flush=True)
    else:
        execute(a,auth)


if __name__=="__main__":
    main()
