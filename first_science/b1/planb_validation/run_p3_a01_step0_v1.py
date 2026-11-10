#!/usr/bin/env python3
"""Prospective P3 attempt A01: isolated I1 and Step-0 for four frozen graphs.

Only candidate B0001_P3_A01; no source contracts or B1 outcomes modified.
Original Phase-5 science functions are reused unmodified. A frozen I1 corpus
is shared by the four graphs. --verify is simulation-free.
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

import isolated_step0_pilot_v1 as base

CANDIDATE_ID="B0001_P3_A01"
ROLE="P3"
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
CALPASS="FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2"
PASS="FROZEN_PHASE5_STEP0_PASS_V2"
CALFAIL="GATE_FAILED_STEP0_CALIBRATION"
FAIL="GATE_FAILED_STEP0"


def candidate_for(preview_path):
    preview=base.read(preview_path)
    if (preview.get("status")!=base.EXPECTED_STATUS or
            preview.get("execution_authorized") is not False or
            preview.get("provider_simulations_generated")!=0):
        raise ValueError("Not the predeclared simulation-free preview")
    if tuple(preview["world_roles"])!=("P1","P3","P4"):
        raise ValueError("World-role order differs from draft")
    if set(preview["graph_ids"])!=set(GRAPHS):
        raise ValueError("Four graph IDs differ from preview")
    rows=[c for c in preview["candidates"] if c["candidate_id"]==CANDIDATE_ID]
    if len(rows)!=1:
        raise ValueError("P3/A01 candidate missing or duplicated")
    c=rows[0]
    if ((c["battery_id"],c["role"],c["attempt"],c["step0_status"])
            !=("B0001",ROLE,1,"NOT_RUN")):
        raise ValueError("Candidate origin/status differs from preview")
    old=base.read(base.PHASE5/base.COPY_NAMES[0])
    draft=base.read(base.DRAFT)
    if draft.get("execution_authorized") is not False:
        raise ValueError("Draft's execution firewall was changed")
    if c["max_approx_utilization"]>float(
            draft["sampling"]["physical_preconditions"]["max_approx_utilization"]):
        raise ValueError("Candidate exceeds physical utilization cap")
    historical={w["id"]:w for w in old["provider_worlds"]}
    if set(historical)!={"P1","P2","P3","P4"}:
        raise ValueError("Unexpected provider-world contract")
    if (c["D_instructions"]==historical[ROLE]["D_instructions"] and
            c["delta"]==historical[ROLE]["delta"]):
        raise ValueError("Candidate matches historical world coordinates")
    for p in ("ProviderA","ProviderB","ProviderC"):
        if c["provider_means"][p]<=0:
            raise ValueError("Nonpositive mean")
    sourcehash=preview["input_sha256"]
    matches=[v for k,v in sourcehash.items() if k.endswith(base.COPY_NAMES[0])]
    if len(matches)!=1 or matches[0]!=base.sha(base.PHASE5/base.COPY_NAMES[0]):
        raise ValueError("Historical physical contract changed from preview")
    return c


def seeds_for(candidate_id):
    blocks=base.seed_blocks(candidate_id)
    own=set(range(blocks["region"]["start"],blocks["confirmation"]["end_inclusive"]+1))
    # Guard against overlap with already executed P1 attempts; do not create
    # accidental cross-world common random numbers.
    for other in ("B0001_P1_A01","B0001_P1_A02"):
        x=base.seed_blocks(other)
        used=set(range(x["region"]["start"],x["confirmation"]["end_inclusive"]+1))
        if own & used:
            raise ValueError("New P3 bank collides with "+other)
    return blocks


def initialize(root,preview,c):
    phase=root/"isolated_contracts"
    phase.mkdir(parents=True,exist_ok=False)
    for name in base.COPY_NAMES:
        shutil.copy2(base.PHASE5/name,phase/name)
    b=base.read(phase/base.COPY_NAMES[0])
    s=base.read(phase/base.COPY_NAMES[1])
    physical=next(w for w in b["provider_worlds"] if w["id"]==ROLE)
    physical.update({
        "D_instructions":c["D_instructions"],
        "delta":c["delta"],
        "provider_means":c["provider_means"],
        "approx_utilization":c["approx_utilization"],
    })
    blocks=seeds_for(CANDIDATE_ID)
    for k in ("region","sigma"):
        s["public_I1"][ROLE][k]=blocks[k]
    s["step0"]["calibration_WB"]=blocks["calibration"]
    s["step0"]["confirmation_WB"]=blocks["confirmation"]
    base.save(phase/base.COPY_NAMES[0],b)
    base.save(phase/base.COPY_NAMES[1],s)
    provenance={
        "status":"ISOLATED_P3_A01_FOUR_GRAPH_ELIGIBILITY",
        "candidate_id":CANDIDATE_ID,
        "provider_role":ROLE,
        "graph_ids":list(GRAPHS),
        "preview_sha256":base.sha(preview),
        "isolated_contract_sha256":{n:base.sha(phase/n) for n in base.COPY_NAMES},
        "original_contract_sha256":{n:base.sha(base.PHASE5/n) for n in base.COPY_NAMES},
        "private_candidate_parameters":"isolated_contracts/"+base.COPY_NAMES[0],
        "seed_blocks":blocks,
        "historical_code_unchanged":True,
        "method_outcomes_used":False,
        "not_for_sequential_policy":True,
        "created_utc":base.utc(),
    }
    base.save(root/"pilot_provenance_PRIVATE.json",provenance)
    return phase


def validate(root,preview,c):
    root=root.expanduser().resolve()
    if root==base.REPO or base.REPO in root.parents:
        raise ValueError("Output directory must be outside source repository")
    if not root.exists():
        raise FileNotFoundError("P3 workspace not found: "+str(root))
    provenance=base.read(root/"pilot_provenance_PRIVATE.json")
    if (provenance.get("candidate_id")!=CANDIDATE_ID or
            provenance.get("preview_sha256")!=base.sha(preview) or
            provenance.get("graph_ids")!=list(GRAPHS)):
        raise ValueError("P3 workspace identity/provenance mismatch")
    phase=root/"isolated_contracts"
    for n in base.COPY_NAMES:
        if (base.sha(phase/n)!=provenance["isolated_contract_sha256"][n] or
                base.sha(base.PHASE5/n)!=provenance["original_contract_sha256"][n]):
            raise ValueError("Historical or isolated contracts changed: "+n)
    sys.path.insert(0,str(base.PHASE5))
    from phase5_runtime_v2 import load_phase5_contracts,provider_world,inclusive_seed_range
    contracts=load_phase5_contracts(phase)
    world=provider_world(contracts,ROLE)
    for key in ("D_instructions","delta","provider_means","approx_utilization"):
        if world[key]!=c[key]:
            raise ValueError("Private P3 parameters mismatch: "+key)
    banks=[inclusive_seed_range(contracts.seeds["public_I1"][ROLE][k])
           for k in ("region","sigma")]
    banks.extend(inclusive_seed_range(contracts.seeds["step0"][k])
                 for k in ("calibration_WB","confirmation_WB"))
    if list(map(len,banks))!=[100,100,200,200]:
        raise ValueError("Unexpected corpus sizes")
    used=set()
    for bank in banks:
        if set(bank)&used or min(bank)<base.SEED_NAMESPACE or max(bank)>base.MAX_TRAJECTORY_SEED:
            raise ValueError("Seed bank overlap, old namespace, or overflow")
        used.update(bank)
    expected=seeds_for(CANDIDATE_ID)
    for bank,kind in zip(banks,("region","sigma","calibration","confirmation")):
        if (bank[0],bank[-1])!=(expected[kind]["start"],expected[kind]["end_inclusive"]):
            raise ValueError("Seed block mismatch: "+kind)
    i1=phase/"results"/"01_i1"/ROLE/"i1_freeze_manifest.json"
    if i1.is_file():
        freeze=base.read(i1)
        if (freeze.get("status")!="FROZEN_PHASE5_I1_COMPLETE_V2" or
                freeze.get("battery_config_sha256")!=base.sha(phase/base.COPY_NAMES[0]) or
                freeze.get("seed_registry_sha256")!=base.sha(phase/base.COPY_NAMES[1])):
            raise ValueError("Existing I1 freeze not from these contracts")
    for graph in GRAPHS:
        cell=root/"step0"/f"{ROLE}__{graph}"
        cm=cell/"step0_calibration_manifest.json"
        fm=cell/"step0_confirmation_manifest.json"
        if cm.is_file() and base.read(cm).get("status") not in (CALPASS,CALFAIL):
            raise ValueError("Unexpected prior calibration status: "+graph)
        if fm.is_file() and base.read(fm).get("status") not in (PASS,FAIL):
            raise ValueError("Unexpected prior confirmation status: "+graph)
    return root,phase


def graph_result(root,graph):
    cell=root/"step0"/f"{ROLE}__{graph}"
    cm=base.read(cell/"step0_calibration_manifest.json")
    fm=base.read(cell/"step0_confirmation_manifest.json")
    return {
        "graph_id":graph,
        "calibration_status":cm["status"],
        "confirmation_status":fm["status"],
        "eligible":fm["status"]==PASS,
        "failures":fm.get("failures",[]),
        "calibration_wall_seconds":cm.get("python_wall_seconds"),
        "confirmation_wall_seconds":fm.get("python_wall_seconds"),
    }


def run(root,phase,preview,c):
    sys.path.insert(0,str(base.PHASE5))
    import run_phase5_i1_v2 as i1
    import run_phase5_step0_v2 as step0
    old_i1=i1.HERE
    old_step0=step0.HERE
    summaries=[]
    try:
        i1.HERE=phase
        step0.HERE=phase
        public=phase/"results"/"01_i1"
        frozen=public/ROLE/"i1_freeze_manifest.json"
        if frozen.is_file():
            print("P3_I1_FROZEN_REUSED",flush=True)
        else:
            base.run_stage(root,"i1",lambda:i1.run_world(ROLE,result_root=public,reset_world=False))
        validate(root,preview,c)
        if not frozen.is_file():
            raise ValueError("I1 acquisition did not freeze")
        for graph in GRAPHS:
            cell=root/"step0"/f"{ROLE}__{graph}"
            cm=cell/"step0_calibration_manifest.json"
            fm=cell/"step0_confirmation_manifest.json"
            print("P3_GRAPH_START",graph,flush=True)
            if cm.is_file():
                print("P3_CALIBRATION_REUSED",graph,flush=True)
            else:
                base.run_stage(root,"step0_calibration_"+graph,
                    lambda graph=graph:step0._run_calibration_cell(
                        ROLE,graph,str(root/"step0")))
            if fm.is_file():
                print("P3_CONFIRMATION_REUSED",graph,flush=True)
            else:
                base.run_stage(root,"step0_confirmation_"+graph,
                    lambda graph=graph:step0._run_confirmation_cell(
                        ROLE,graph,str(root/"step0")))
            summaries.append(graph_result(root,graph))
            print("P3_GRAPH_DONE",graph,"eligible",summaries[-1]["eligible"],flush=True)
            validate(root,preview,c)
            if not summaries[-1]["eligible"]:
                print("P3_CANDIDATE_REJECTED_FIRST_FAILED_GRAPH",graph,flush=True)
                break
        result={
            "status":("P3_A01_ALL_FOUR_STEP0_PASS" if len(summaries)==4 and all(x["eligible"] for x in summaries)
                      else "P3_A01_STEP0_INELIGIBLE"),
            "candidate_id":CANDIDATE_ID,
            "provider_world_role":ROLE,
            "graphs_completed":len(summaries),
            "all_four_graphs_eligible":len(summaries)==4 and all(x["eligible"] for x in summaries),
            "other_graphs":summaries,
            "frozen_I1_reused_across_graphs":True,
            "method_outcomes_used":False,
            "confirmatory_evidence":False,
            "observed_utc":base.utc(),
        }
        base.save(root/"p3_a01_eligibility_summary.json",result)
        print("P3_A01_STEP0_FINAL",result["status"],
              "summary",root/"p3_a01_eligibility_summary.json",flush=True)
    finally:
        i1.HERE=old_i1
        step0.HERE=old_step0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify",action="store_true")
    mode.add_argument("--run",action="store_true")
    mode.add_argument("--resume",action="store_true")
    a=p.parse_args()
    preview=a.preview.expanduser().resolve()
    root=a.out.expanduser().resolve()
    c=candidate_for(preview)
    if a.verify:
        if root.exists():
            validate(root,preview,c)
        else:
            if root==base.REPO or base.REPO in root.parents:
                raise ValueError("Output must be outside source repository")
            with __import__("tempfile").TemporaryDirectory(prefix="praise_p3_verify_") as tmp:
                scratch=Path(tmp)
                initialize(scratch,preview,c)
                validate(scratch,preview,c)
        print("P3_A01_ISOLATION_VERIFY_PASS candidate",CANDIDATE_ID,
              "graphs",",".join(GRAPHS),"NO_SIMULATIONS",flush=True)
        return
    if a.run:
        if root.exists():
            raise FileExistsError("Refusing to overwrite existing P3 workspace: "+str(root))
        if root==base.REPO or base.REPO in root.parents:
            raise ValueError("Output must be outside source repository")
        root.mkdir(parents=True)
        initialize(root,preview,c)
    root,phase=validate(root,preview,c)
    run(root,phase,preview,c)


if __name__=="__main__":
    main()
