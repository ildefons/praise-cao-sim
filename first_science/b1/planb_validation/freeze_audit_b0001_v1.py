#!/usr/bin/env python3
"""Freeze/audit prospective B0001 Step-0 eligibility without simulation.

Read-only inputs: four isolated attempt workspaces and the exact dry-run
candidate preview. Output: a new, immutable-by-convention audit directory
outside the source repository, containing SHA-256 evidence hashes, the
recruitment record, and a fail-closed prediction compatibility report.

This does NOT launch predictions and does NOT certify the historical seven
method runners for independent-world reuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
ROLE_ATTEMPTS=(
    ("P1","B0001_P1_A01",False),
    ("P1","B0001_P1_A02",True),
    ("P3","B0001_P3_A01",True),
    ("P4","B0001_P4_A01",True),
)
CALPASS="FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2"
PASS="FROZEN_PHASE5_STEP0_PASS_V2"
CALFAIL="GATE_FAILED_STEP0_CALIBRATION"
FAIL="GATE_FAILED_STEP0"
METHODS=(
    "M1","M2","M3_FULL343","ORIGINAL_TOP14_B1400",
    "ORIGINAL_TOP1_B1400","FIXED_CV_TOP14","FIXED_CV_TOP1",
)
SOURCE_RUNNERS=(
    "first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py",
    "first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py",
    "first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py",
    "first_science/phase5/run_phase5_final_wb_v3b_fullsupport.py",
    "first_science/b1/planb_validation/b1_budget_comparison_v1.py",
)
TRAJECTORIES_PER_CELL={
    "M1":100,"M2":2700,"M3_FULL343":1400,
    "ORIGINAL_TOP14_B1400":1400,"ORIGINAL_TOP1_B1400":1400,
    "FIXED_CV_TOP14":1400,"FIXED_CV_TOP1":1400,
}
# Counts above are verified against historical cost inventory below rather
# than represented as a new-world execution specification.


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()


def require(flag,message):
    if not flag:
        raise ValueError(message)


def hashed(path,root):
    require(path.is_file(),"Missing freeze evidence "+str(path))
    return {"path":str(path.relative_to(root)),"sha256":sha(path)}


def audit_attempt(root,role,candidate,eligible,preview_hash,preview_row):
    root=root.expanduser().resolve()
    provenance=root/"pilot_provenance_PRIVATE.json"
    prov=load(provenance)
    require(prov["candidate_id"]==candidate,"Candidate provenance differs: "+candidate)
    require(prov["preview_sha256"]==preview_hash,"Preview hash differs: "+candidate)
    require(preview_row["battery_id"]=="B0001" and preview_row["role"]==role,
            "Invalid candidate recruitment origin")
    phase=root/"isolated_contracts"
    evidence=[hashed(provenance,root)]
    for name,digest in prov["isolated_contract_sha256"].items():
        p=phase/name
        require(sha(p)==digest,"Isolated contract changed: "+str(p))
        evidence.append(hashed(p,root))
    for name,digest in prov.get("source_contract_sha256",prov.get("original_contract_sha256",{})).items():
        require(sha(REPO/"first_science"/"phase5"/name)==digest,
                "Historical source contract changed: "+name)

    i1=phase/"results"/"01_i1"/role/"i1_freeze_manifest.json"
    frozen=load(i1)
    require(frozen["status"]=="FROZEN_PHASE5_I1_COMPLETE_V2",
            "I1 freeze incomplete: "+candidate)
    require(frozen["battery_config_sha256"]==sha(
        phase/"config_phase5_recoverability_battery_v2.json"),"I1 battery hash drift")
    require(frozen["seed_registry_sha256"]==sha(
        phase/"config_phase5_seed_registry_v2.json"),"I1 seed hash drift")
    evidence.append(hashed(i1,root))

    available=[]
    complete=True
    for graph in GRAPHS:
        cell=root/"step0"/f"{role}__{graph}"
        cp=cell/"step0_calibration_manifest.json"
        fp=cell/"step0_confirmation_manifest.json"
        if not cp.exists() or not fp.exists():
            complete=False
            if eligible:
                raise ValueError("Missing required eligible cell: "+str(cell))
            continue
        cal=load(cp)
        conf=load(fp)
        require(cal["status"] in (CALPASS,CALFAIL),"Bad calibration status")
        require(conf["status"] in (PASS,FAIL),"Bad confirmation status")
        require(conf["inputs"]["calibration_manifest_sha256"]==sha(cp),
                "Confirmation/calibration provenance mismatch: "+str(cell))
        evidence.extend([hashed(cp,root),hashed(fp,root)])
        record={"role":role,"candidate_id":candidate,"graph_id":graph,
                "calibration_status":cal["status"],"confirmation_status":conf["status"],
                "eligible":conf["status"]==PASS,
                "failure_reasons":conf.get("failures",[])}
        if cal["status"]==CALPASS:
            sp=cell/"step0_selected_queries.csv"
            selected=pd.read_csv(sp)
            require(len(selected)==15 and selected.query_id.is_unique,
                    "Selected query count/identity mismatch: "+str(cell))
            require(cal["output_hashes_sha256"]["step0_selected_queries"]==sha(sp),
                    "Calibration-selected query hash mismatch: "+str(cell))
            require(set(selected.graph_id)=={graph} and set(selected.provider_world_id)=={role},
                    "Frozen selected query cell identity mismatch: "+str(cell))
            evidence.append(hashed(sp,root))
            if conf["status"]==PASS:
                require(conf["inputs"]["selected_queries_sha256"]==sha(sp),
                        "Confirmation selected-query hash mismatch: "+str(cell))
                frozen_file=cell/"step0_frozen_queries.csv"
                confirmation=cell/"step0_confirmation.csv"
                confirmed=pd.read_csv(confirmation)
                require(len(confirmed)==15 and confirmed.query_id.is_unique,
                        "Confirmation query count mismatch: "+str(cell))
                require(set(confirmed.query_id)==set(selected.query_id),
                        "Confirmation reselected queries: "+str(cell))
                require(confirmed.per_query_pass.astype(str).str.lower().eq("true").all(),
                        "Unexpected failed query in passed cell: "+str(cell))
                for p in (frozen_file,confirmation):
                    evidence.append(hashed(p,root))
        available.append(record)
    if eligible:
        require(complete and len(available)==4 and all(x["eligible"] for x in available),
                "Selected candidate lacks four eligible graphs: "+candidate)
    else:
        require(any(not x["eligible"] for x in available),
                "Rejected A01 has no recorded failed graph")
        require(not all(x["eligible"] for x in available),"A01 incorrectly accepted")
    return {"candidate_id":candidate,"role":role,"eligible":eligible,
            "graphs":available,"files":evidence,
            "seed_blocks":prov["seed_blocks"],
            "source_workspace":str(root)}


def check_banks(attempts):
    # Shared seeds across graphs within a given world are intentionally CRN.
    # Across different attempts, provider and Step-0 trajectory banks are disjoint.
    used=set()
    for att in attempts:
        blocks=att["seed_blocks"]
        this=set()
        for name in ("region","sigma","calibration","confirmation"):
            b=blocks[name]
            values=set(range(int(b["start"]),int(b["end_inclusive"])+1))
            require(len(values)==int(b["n"]),"Invalid seed bank size")
            require(not (this&values),"Within-attempt seed overlap")
            require(max(values)*100+3 <= 2**32-1,"Native seed overflows uint32")
            this |= values
        require(not (used&this),"Across-attempt seed overlap")
        used |= this


def prediction_audit():
    files={}
    for rel in SOURCE_RUNNERS:
        p=REPO/rel
        require(p.is_file(),"Historical prediction runner missing: "+str(p))
        files[rel]=sha(p)
    # The existing historical runners are explicitly tied to frozen Phase-5
    # paths/results. They cannot be run against the isolated new-world
    # contracts without scientific adapter work and validation.
    phase=(REPO/SOURCE_RUNNERS[0]).read_text(encoding="utf-8")
    fixed=(REPO/SOURCE_RUNNERS[2]).read_text(encoding="utf-8")
    wb=(REPO/SOURCE_RUNNERS[3]).read_text(encoding="utf-8")
    require("load_phase5_contracts" in phase and "_preflight()" in phase,
            "Phase-II prediction runner changed; re-audit required")
    require("SOURCE = core.OUT" in fixed and "cv_selection.json" in fixed,
            "Fixed-CV source assumptions changed; re-audit required")
    require("GLOBAL_PRED_FREEZE" in wb and "PRED_ROOT" in wb,
            "Final WB unlock assumptions changed; re-audit required")
    return {
        "status":"BLOCKED_HISTORICAL_RUNNERS_NOT_REWIRED_FOR_B0001",
        "method_ids":METHODS,
        "historical_runner_hashes":files,
        "blockers":[
            "Phase-II graph predictor uses historical Phase-5 paths and original world-specific reconstructions; isolated public I1 and Step-0 are not sufficient to run it unchanged.",
            "Original-style Top1/Top14 requires fresh provider candidate preparation and frozen new-world supports; historical retrospective checkpoints must not be substituted.",
            "Fixed-CV Top1/Top14 explicitly consumes historical core.OUT and frozen historical CV/weights; fresh-world CV/support must be derived and frozen without confirmation leakage.",
            "Final white-box reference requires a new battery-specific global prediction freeze and independent WB seeds. Original Phase-5 final-WB unlock cannot be reused.",
            "Seven-method outcome matrix and sequential selector must be assessed only after all new-world predictions are frozen and compared with independent WB evidence.",
        ],
        "per_cell_prediction_graph_trajectories":9800,
        "twelve_cell_prediction_graph_trajectories":117600,
        "separate_final_wb_trajectories":12000,
        "reconstruction_and_provider_local_cost":"additional; not included in 117600",
        "safe_to_launch_predictions":False,
        "safe_to_launch_final_wb":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview",required=True,type=Path)
    p.add_argument("--p1-rejected",required=True,type=Path)
    p.add_argument("--p1-selected",required=True,type=Path)
    p.add_argument("--p3-selected",required=True,type=Path)
    p.add_argument("--p4-selected",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    out=a.out.expanduser().resolve()
    require(out!=REPO and REPO not in out.parents,
            "B0001 freeze must be outside source repository")
    require(not out.exists(),"Refusing to overwrite a freeze or audit directory")
    preview=a.preview.expanduser().resolve()
    pv=load(preview)
    require(pv["status"]=="B1_NEW_WORLD_DRY_RUN_ONLY_NOT_STEP0_ELIGIBILITY",
            "Candidate preview status drift")
    require(not pv["execution_authorized"],"Candidate preview must not authorize simulation")
    lookup={c["candidate_id"]:c for c in pv["candidates"]}
    roots={
        "B0001_P1_A01":a.p1_rejected,
        "B0001_P1_A02":a.p1_selected,
        "B0001_P3_A01":a.p3_selected,
        "B0001_P4_A01":a.p4_selected,
    }
    attempts=[]
    for role,cid,eligible in ROLE_ATTEMPTS:
        require(cid in lookup,"Candidate missing from original preview: "+cid)
        attempts.append(audit_attempt(
            roots[cid],role,cid,eligible,sha(preview),lookup[cid]))
    check_banks(attempts)
    for role in ("P1","P3","P4"):
        selected=[x for x in attempts if x["role"]==role and x["eligible"]]
        require(len(selected)==1,"Missing unique eligible world: "+role)
    result={
        "status":"B0001_STEP0_ELIGIBILITY_EVIDENCE_FROZEN",
        "candidate_preview_sha256":sha(preview),
        "attempt_order":[x["candidate_id"] for x in attempts],
        "selected_by_role":{x["role"]:x["candidate_id"] for x in attempts if x["eligible"]},
        "attempts":attempts,
        "eligible_cells":12,
        "selected_queries_per_cell":15,
        "method_outcomes_used":False,
        "confirmatory_method_evidence":False,
        "no_new_simulations":True,
    }
    audit=prediction_audit()
    out.mkdir(parents=True)
    (out/"b0001_step0_evidence_freeze.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"b0001_prediction_pipeline_audit.json").write_text(
        json.dumps(audit,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("B0001_STEP0_EVIDENCE_FREEZE_PASS 12 eligible cells 4 recorded attempts")
    print("B0001_PREDICTION_AUDIT_BLOCKED original runners need isolated adapters")
    print("B0001_NO_PREDICTIONS_LAUNCHED")
    print("FREEZE",out/"b0001_step0_evidence_freeze.json")
    print("AUDIT",out/"b0001_prediction_pipeline_audit.json")


if __name__=="__main__":
    main()
