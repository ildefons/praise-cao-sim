#!/usr/bin/env python3
"""B0001 final-WB authorization and preflight (NO WHITE-BOX OUTCOMES READ).

This gate binds independently audited blind predictions to the 12 selected
B0001 physical graph cells; validates the original reference contract, immutable
source-world provenance, public query hashes, and fresh stage-disjoint N=1000
reference seeds. It reads ONLY frozen eligibility metadata and SHA-256 hashes
of private-world contract files; not generating parameters or any WB curves.

The resulting authorization is irrevocably bound to the supplied audit digest.
It permits ONLY the independent reference execution, not accuracy analysis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

ROLES=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
WORLD_IDS={"P1":"B0001_P1_A02","P3":"B0001_P3_A01",
           "P4":"B0001_P4_A01"}
WB_START=42_000_000
WB_N=1000
STATUS="B0001_FINAL_WB_PREFLIGHT_PASS_REFERENCE_EXECUTION_ONLY"


def require(flag,msg):
    if not flag:
        raise RuntimeError("B0001 WB GATE: "+msg)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for b in iter(lambda:stream.read(1<<20),b""):
            h.update(b)
    return h.hexdigest()


def save(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),"Refusing to overwrite preflight freeze")
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def verify(a):
    audit_path=a.audit/"b0001_full343_postrun_integrity_audit.json"
    audit=load(audit_path)
    require(audit["status"]==
            "B0001_FULL343_POSTRUN_INTEGRITY_AUDIT_PASS_FINAL_WB_EMBARGOED"
            and audit["audited_cell_count"]==12
            and audit["ledger_files_verified"]==4452
            and audit["trajectories_verified"]==50400
            and audit["final_whitebox_read"] is False
            and audit["final_whitebox_authorized"] is False,
            "Post-run audit not complete or WB firewall changed")
    global_path=a.graph/"scientific"/"b0001_full343_global_prediction_freeze.json"
    global_doc=load(global_path)
    require(audit["global_prediction_freeze_sha256"]==sha(global_path)
            and global_doc["status"]==
            "B0001_FULL343_12_CELL_GRAPH_PREDICTIONS_FROZEN"
            and global_doc["n_frozen_cells"]==12
            and global_doc["final_WB_read"] is False,
            "Blind global freeze does not match independently audited freeze")
    cells={f"{role}__{graph}" for role in ROLES for graph in GRAPHS}
    require(set(global_doc["prediction_manifest_sha256_by_cell"])==cells,
            "Predicted cell coverage changed")
    for cell,digest in global_doc["prediction_manifest_sha256_by_cell"].items():
        manifest=a.graph/"scientific"/cell/"prediction_manifest.json"
        require(sha(manifest)==digest,
                "Blind prediction manifest changed since audit: "+cell)
    staged=load(a.staging/"b0001_public_inputs_manifest.json")
    require(staged["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE"
            and staged["selected_worlds"]==WORLD_IDS
            and staged["cells"]==12,
            "Staging selected-world identities changed")
    for role in ROLES:
        for graph in GRAPHS:
            cell=f"{role}__{graph}"
            p=a.staging/"frozen_queries"/cell/"step0_frozen_queries.csv"
            q=pd.read_csv(p)
            require(len(q)==15 and q.query_id.nunique()==15
                    and set(q.provider_world_id)=={role}
                    and set(q.graph_id)=={graph},
                    "Frozen query definition differs: "+cell)
    root=Path(__file__).resolve().parents[2]/"phase5"
    original=root/"config_phase5_final_wb_v3b_fullsupport.json"
    contract=load(original)
    require(contract["status"]==
            "FROZEN_PHASE5_FINAL_WB_EXECUTION_V3B_FULLSUPPORT"
            and contract["scope"]["eligible_physical_cells"]==12
            and contract["whitebox_generation"][
                "n_trajectories_per_eligible_physical_cell"]==1000
            and contract["scope"]["horizons"]==
                {"start_seconds":0,"end_inclusive_seconds":240,
                 "step_seconds":5},
            "Historical reference methodology differs")
    evidence=load(a.eligibility)
    require(evidence["status"]=="B0001_STEP0_ELIGIBILITY_EVIDENCE_FROZEN"
            and evidence["selected_by_role"]==WORLD_IDS
            and evidence["eligible_cells"]==12,
            "Selected physical world evidence authority changed")
    attempts={x["candidate_id"]:x for x in evidence["attempts"]}
    occupied=[]
    for x in evidence["attempts"]:
        for name,bank in x["seed_blocks"].items():
            occupied.append((x["candidate_id"]+"/"+name,
                             int(bank["start"]),int(bank["end_inclusive"])))
    selected={}
    for role,candidate in WORLD_IDS.items():
        att=attempts[candidate]
        require(att["eligible"] is True,
                "Selected physical world is not eligible: "+candidate)
        source=Path(att["source_workspace"]).resolve()
        require(source.is_dir(),"Missing selected physical-world directory: "+candidate)
        file=source/"isolated_contracts"/"config_phase5_recoverability_battery_v2.json"
        records={x["path"]:x["sha256"] for x in att["files"]}
        rel=str(file.relative_to(source))
        require(rel in records and sha(file)==records[rel],
                "Private physical-world contract hash changed: "+candidate)
        selected[role]={"candidate_id":candidate,
                         "source_world_contract":str(file),
                         "world_contract_sha256":sha(file)}
    seeds=load(a.graph/"_preexecution"/"b0001_full343_graph_seeds.json")
    common=seeds["graph_prediction"]["M1_M2_common_bank"]
    m3=seeds["graph_prediction"]["M3"]
    occupied.extend([
        ("B0001_M1M2",int(common["start"]),int(common["end_inclusive"])),
        ("B0001_M3",int(m3["seed_base"]),
         int(m3["seed_base"])+342*int(m3["seed_block_stride"])+1400),
        ("engineering_smoke",39_000_001,39_000_003),
        ("historical_final_WB",54000,54999),
    ])
    # B0001 V3 reconstruction seeds were separately frozen and audited
    # in selection preflight; 42m is outside their reserved namespace.
    lo,hi=WB_START,WB_START+WB_N-1
    require(0<lo<hi<42_949_000,
            "Reference seed range exceeds conservative native safe region")
    for name,start,end in occupied:
        require(hi<start or lo>end,
                "Final-WB seeds overlap "+name)
    # The selection preflight and source manifests are immutable.
    pre=load(a.preflight/"b0001_graph_prediction_preflight.json")
    require(pre["status"]==
            "B0001_GRAPH_PREDICTION_PREFLIGHT_PASS_EXECUTION_BLOCKED"
            and pre["v3b_selection_freeze_sha256"]==
            audit["v3b_selection_sha256"],
            "Source V3b provider selection provenance mismatch")
    return {
        "status":STATUS,
        "reference_execution_authorized":True,
        "analysis_authorized":False,
        "postrun_integrity_audit_sha256":sha(audit_path),
        "blind_global_freeze_sha256":sha(global_path),
        "public_staging_manifest_sha256":
            sha(a.staging/"b0001_public_inputs_manifest.json"),
        "b0001_step0_eligibility_sha256":sha(a.eligibility),
        "original_reference_contract_sha256":sha(original),
        "original_reference_runner_sha256":
            sha(root/"run_phase5_final_wb_v3b_fullsupport.py"),
        "original_reference_audit_sha256":
            sha(root/"audit_phase5_final_wb_v3b_fullsupport.py"),
        "evaluation_contract_sha256":
            sha(root/"config_phase5_evaluation_v3b_fullsupport.json"),
        "evaluation_runner_sha256":
            sha(root/"run_phase5_evaluation_v3b_fullsupport.py"),
        "selected_worlds":selected,
        "cells":12,
        "queries_per_cell":15,
        "horizons_per_query":49,
        "reference_n_per_cell":1000,
        "reference_trajectories_total":12000,
        "final_reference_seed_bank":{
            "start":lo,"end_inclusive":hi,"n":WB_N,
            "reused_across_cells_as_common_random_numbers":True},
        "stage_seed_overlaps":0,
        "private_physical_world_contracts_hashed_only":True,
        "hidden_physical_parameters_parsed_or_used":False,
        "final_WB_outcomes_read":False,
        "new_simulations_run":0,
        "prediction_files_mutable":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("audit","graph","staging","preflight","eligibility","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    for name in ("audit","graph","staging","preflight","eligibility","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    require(a.out not in a.graph.parents and
            a.out!=a.graph and a.graph not in a.out.parents,
            "Reference preflight output must not overlap prediction workspace")
    result=verify(a)
    path=a.out/"b0001_final_wb_authorization_freeze.json"
    save(path,result)
    print("B0001_FINAL_WB_PREFLIGHT_PASS 12 cells N=1000 each",flush=True)
    print("B0001_FINAL_WB_SEEDS_FRESH",WB_START,WB_START+WB_N-1,flush=True)
    print("BLIND_PREDICTIONS_IMMUTABLE / REFERENCE_ONLY",flush=True)
    print("FREEZE",path,flush=True)


if __name__=="__main__":
    main()
