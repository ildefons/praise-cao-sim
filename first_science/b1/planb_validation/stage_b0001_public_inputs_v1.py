#!/usr/bin/env python3
"""B0001 predictor-input firewall: stage only public I1 cards and frozen query definitions.

Requires successful B0001 eligibility freeze. Does not run predictors,
derive provider models, read simulation ledger contents, or touch historical
Phase-5 outputs. Never copies hidden physical parameters or confirmation
outcomes to the prediction workspace.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

ROLES=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
PUBLIC_COLUMNS=("query_id","provider_world_id","graph_id","rho_label","rho",
                "regime","scale","A_G_l_max","A_G_c_max","A_G_q_min",
                "step0_cell_status")
PASS="FROZEN_PHASE5_STEP0_PASS_V2"
SELECTED={"P1":"B0001_P1_A02","P3":"B0001_P3_A01","P4":"B0001_P4_A01"}


def require(ok,message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(content,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def materialize(freeze,out,verify_only=False):
    freeze=freeze.expanduser().resolve()
    out=out.expanduser().resolve()
    doc=read(freeze)
    require(doc["status"]=="B0001_STEP0_ELIGIBILITY_EVIDENCE_FROZEN",
            "Eligibility freeze missing or status unexpected")
    require(doc["selected_by_role"]==SELECTED,"Frozen selected roles changed")
    require(doc["eligible_cells"]==12 and doc["selected_queries_per_cell"]==15,
            "Eligibility freeze incomplete")
    require(doc["method_outcomes_used"] is False,"Method outcomes tainted freeze")
    require(len(doc["attempts"])==4,"Recruitment attempt ledger incomplete")
    require([x["candidate_id"] for x in doc["attempts"]]==
            ["B0001_P1_A01","B0001_P1_A02","B0001_P3_A01","B0001_P4_A01"],
            "Recruitment attempt order changed")
    indexed={a["candidate_id"]:a for a in doc["attempts"]}
    for att in doc["attempts"]:
        root=Path(att["source_workspace"]).resolve()
        require(root.exists(),"Missing original workspace "+str(root))
        for entry in att["files"]:
            p=root/entry["path"]
            require(p.is_file() and sha(p)==entry["sha256"],
                    "Frozen evidence mutated or missing: "+str(p))

    audit_path=freeze.parent/"b0001_prediction_pipeline_audit.json"
    audit=read(audit_path)
    require(audit["status"]=="BLOCKED_HISTORICAL_RUNNERS_NOT_REWIRED_FOR_B0001",
            "Original pipeline audit changed unexpectedly")
    require(audit["safe_to_launch_predictions"] is False,
            "Staging must not inherit launch authorization")

    require(not out.exists(),"Refusing to overwrite predictor-input staging directory")
    require(out != freeze.parent and freeze.parent not in out.parents,
            "Prediction workspace must not be nested in private freeze directory")
    require(all(out!=Path(a["source_workspace"]).resolve()
                and Path(a["source_workspace"]).resolve() not in out.parents
                for a in doc["attempts"]),
            "Prediction output cannot be inside isolated private evidence")

    # Build the copy plan and validate source formats BEFORE writing anything.
    files=[]
    used=set()
    for role in ROLES:
        attempt=indexed[SELECTED[role]]
        require(attempt["eligible"] is True,"Selected world not eligible")
        root=Path(attempt["source_workspace"]).resolve()
        world_i1=root/"isolated_contracts"/"results"/"01_i1"/role/"public"
        require(world_i1.is_dir(),"Public I1 cards missing: "+str(world_i1))
        for provider in PROVIDERS:
            parent=world_i1/provider
            require(parent.is_dir(),"Provider card folder missing: "+str(parent))
            # Public cards only, never sibling private/ or provenance files.
            for filename in ("sigma_surface.csv",):
                p=parent/filename
                require(p.is_file(),"Public sigma surface missing: "+str(p))
            for source in sorted(parent.iterdir()):
                require(source.is_file(),"Unexpected public nested path: "+str(source))
                require(source.suffix.lower() in (".csv",".json"),
                        "Unexpected public file extension: "+str(source))
                target=Path("public_I1")/role/provider/source.name
                require(str(target) not in used,"Duplicate target path")
                used.add(str(target))
                files.append((source,target,sha(source)))
        records=[x for x in attempt["graphs"] if x["eligible"]]
        require(len(records)==4 and {x["graph_id"] for x in records}==set(GRAPHS),
                "Eligible graph set incomplete for "+role)
        for graph in GRAPHS:
            source=root/"step0"/f"{role}__{graph}"/"step0_frozen_queries.csv"
            require(source.is_file(),"Missing frozen query file: "+str(source))
            q=pd.read_csv(source)
            require(len(q)==15 and q.query_id.is_unique,
                    "Frozen query count or identity changed: "+str(source))
            require(set(q.graph_id)=={graph} and set(q.provider_world_id)=={role},
                    "Frozen query role or graph mismatch")
            require(set(q.step0_cell_status)=={PASS},
                    "Nonpassing Step-0 query was selected")
            require(set(PUBLIC_COLUMNS).issubset(q.columns),
                    "Frozen queries lack required prediction definition fields")
            # Strip calibration-fitted means and diagnostic columns; only
            # the original prediction-stage approved definitions survive.
            target=Path("frozen_queries")/f"{role}__{graph}"/"step0_frozen_queries.csv"
            files.append((source,target,sha(source)))

    if verify_only:
        print("B0001_PUBLIC_INPUT_STAGING_VERIFY_PASS",
              "roles=3","cells=12","public_I1=9_provider_directories",
              "no_simulations=YES",flush=True)
        return
    out.mkdir(parents=True)
    staged=[]
    for source,target,digest in files:
        dest=out/target
        dest.parent.mkdir(parents=True,exist_ok=True)
        if target.parts[0]=="frozen_queries":
            q=pd.read_csv(source,usecols=list(PUBLIC_COLUMNS))
            q.to_csv(dest,index=False)
        else:
            shutil.copy2(source,dest)
        staged.append({
            "path":str(target),"source_sha256":digest,
            "staged_sha256":sha(dest),
        })
    result={
        "status":"B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE",
        "eligibility_freeze_sha256":sha(freeze),
        "pipeline_audit_sha256":sha(audit_path),
        "selected_worlds":SELECTED,
        "cells":12,"queries_per_cell":15,
        "staged_files":staged,
        "hidden_world_parameters_copied":False,
        "calibration_or_confirmation_values_copied":False,
        "simulation_trajectories_generated":0,
        "predictions_generated":0,
        "prediction_execution_authorized":False,
        "next_gate":"fresh reconstruction and support adapters with equivalence tests"
    }
    save(out/"b0001_public_inputs_manifest.json",result)
    print("B0001_PUBLIC_PREDICTION_INPUTS_STAGED",len(files),"files",flush=True)
    print("PREDICTION_EXECUTION_BLOCKED pending reconstruction and support adapters",flush=True)
    print("MANIFEST",out/"b0001_public_inputs_manifest.json",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify",action="store_true")
    args=p.parse_args()
    materialize(args.freeze,args.out,args.verify)


if __name__=="__main__":
    main()
