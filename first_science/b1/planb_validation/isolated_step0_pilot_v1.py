#!/usr/bin/env python3
"""Isolated Phase-5 I1 + Step-0 feasibility pilot on ONE new world/graph.

Never modifies source contracts, Phase-5 historical outputs, or B1 selector.
Uses the original Phase-5 I1 and Step-0 scientific functions with an isolated
copy of the frozen contracts and new, disjoint trajectory seed namespaces.

Default --verify is simulation-free. --run explicitly starts the pilot.
The new world parameters are PRIVATE; do not pass them to the selector.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PHASE5 = REPO / "first_science" / "phase5"
DRAFT = HERE / "B1_WORLD_GENERATOR_DRAFT_V0_1.json"
SOURCE_PREVIEW = "PRIVATE_world_candidates.json"
COPY_NAMES = (
    "config_phase5_recoverability_battery_v2.json",
    "config_phase5_seed_registry_v2.json",
    "config_phase5_method_instantiation_v2.json",
    "config_phase5_execution_contract_v2.json",
    "config_phase5_analysis_addendum_v2.json",
)
EXPECTED_STATUS = "B1_NEW_WORLD_DRY_RUN_ONLY_NOT_STEP0_ELIGIBILITY"
DEFAULT_CANDIDATE = "B0001_P1_A01"
DEFAULT_GRAPH = "G_PAR"
# Phase-1 / Phase-5 providers derive native seeds as trajectory_seed * 100 + ordinal.
# Keep all derived seeds inside legacy NumPy RandomState's unsigned 32-bit range.
SEED_NAMESPACE = 20_000_000
MAX_NATIVE_SEED = 2**32 - 1
MAX_TRAJECTORY_SEED = (MAX_NATIVE_SEED - 3) // 100


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024*1024), b""):
            h.update(part)
    return h.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def validated_candidate(preview_file, candidate_id, graph_id):
    preview = read(preview_file)
    if (preview.get("status") != EXPECTED_STATUS or
            preview.get("execution_authorized") is not False or
            preview.get("provider_simulations_generated") != 0):
        raise ValueError("Input must be the unassessed V0.1 dry-run preview")
    if candidate_id != DEFAULT_CANDIDATE or graph_id != DEFAULT_GRAPH:
        raise ValueError("V1 pilot is restricted to B0001_P1_A01 / G_PAR")
    rows = [r for r in preview["candidates"] if r["candidate_id"] == candidate_id]
    if len(rows) != 1:
        raise ValueError("Candidate not found or duplicated")
    candidate = rows[0]
    if (candidate["battery_id"], candidate["role"], candidate["attempt"]) != ("B0001", "P1", 1):
        raise ValueError("Unexpected candidate origin")
    if candidate["step0_status"] != "NOT_RUN":
        raise ValueError("Pilot candidate is not unassessed")
    world = read(PHASE5/COPY_NAMES[0])
    draft = read(DRAFT)
    if draft.get("execution_authorized") is not False:
        raise ValueError("Unexpected draft change")
    if candidate["max_approx_utilization"] > float(draft["sampling"]["physical_preconditions"]["max_approx_utilization"]):
        raise ValueError("Physical utilization precondition failed")
    expected = {str(x["id"]): x for x in world["provider_worlds"]}
    if sorted(expected) != ["P1", "P2", "P3", "P4"]:
        raise ValueError("Original world contract changed")
    if graph_id not in {g["id"] for g in world["graphs"]}:
        raise ValueError("Graph absent from original contract")
    if all(candidate["provider_means"][p] == expected["P1"]["provider_means"][p]
           for p in ("ProviderA", "ProviderB", "ProviderC")):
        raise ValueError("Candidate equal to historical P1")
    if sha(PHASE5/COPY_NAMES[0]) != preview["input_sha256"][next(
            k for k in preview["input_sha256"] if k.endswith(COPY_NAMES[0]))]:
        raise ValueError("Original battery contract does not match preview provenance")
    return candidate


def seed_blocks(candidate_id):
    # Assign stage-disjoint and old-bank-disjoint consecutive 100/200 seed ranges.
    # Deterministic unique namespace for this single proof-of-concept candidate.
    h = int(hashlib.sha256(candidate_id.encode()).hexdigest()[:8], 16)
    offset = SEED_NAMESPACE + (h % 10_000) * 1_000
    if offset + 599 > MAX_TRAJECTORY_SEED:
        raise AssertionError("Derived native provider seeds would exceed uint32")
    def block(start, count):
        return dict(start=offset+start, end_inclusive=offset+start+count-1, n=count)
    return dict(region=block(0,100), sigma=block(100,100),
                calibration=block(200,200), confirmation=block(400,200))


def contract_workspace(root, candidate, preview_file, graph_id):
    phase = root/"isolated_contracts"
    phase.mkdir(parents=True,exist_ok=False)
    for name in COPY_NAMES:
        shutil.copy2(PHASE5/name, phase/name)
    battery = read(phase/COPY_NAMES[0])
    seeds = read(phase/COPY_NAMES[1])
    world = next(x for x in battery["provider_worlds"] if x["id"]=="P1")
    world.update({
        "D_instructions": candidate["D_instructions"],
        "delta": candidate["delta"],
        "provider_means": candidate["provider_means"],
        "approx_utilization": candidate["approx_utilization"],
    })
    blocks = seed_blocks(candidate["candidate_id"])
    seeds["public_I1"]["P1"]["region"] = blocks["region"]
    seeds["public_I1"]["P1"]["sigma"] = blocks["sigma"]
    seeds["step0"]["calibration_WB"] = blocks["calibration"]
    seeds["step0"]["confirmation_WB"] = blocks["confirmation"]
    save(phase/COPY_NAMES[0],battery)
    save(phase/COPY_NAMES[1],seeds)
    provenance = {
        "status":"ISOLATED_ONE_WORLD_ONE_GRAPH_ENGINEERING_PILOT",
        "candidate_id":candidate["candidate_id"],
        "graph_id":graph_id,
        "private_candidate_parameters": "isolated_contracts/"+COPY_NAMES[0],
        "preview_sha256":sha(preview_file),
        "source_contract_sha256": {name:sha(PHASE5/name) for name in COPY_NAMES},
        "isolated_contract_sha256": {name:sha(phase/name) for name in COPY_NAMES},
        "seed_blocks":blocks,
        "historical_code_unchanged":True,
        "not_for_sequential_policy":True,
        "pilot_started_utc":utc(),
    }
    save(root/"pilot_provenance_PRIVATE.json",provenance)


def verify_patched_contracts(phase, candidate):
    sys.path.insert(0, str(PHASE5))
    from phase5_runtime_v2 import load_phase5_contracts, provider_world, inclusive_seed_range
    contracts = load_phase5_contracts(phase)
    chosen = provider_world(contracts,"P1")
    if chosen["provider_means"] != candidate["provider_means"]:
        raise AssertionError("Isolated world not wired into contracts")
    ss = contracts.seeds
    banks = [inclusive_seed_range(ss["public_I1"]["P1"][r])
             for r in ("region","sigma")]
    banks += [inclusive_seed_range(ss["step0"][r])
              for r in ("calibration_WB","confirmation_WB")]
    if [len(x) for x in banks] != [100,100,200,200]:
        raise AssertionError("Wrong evidence sizes")
    union=set()
    for bank in banks:
        if union.intersection(bank) or min(bank)<SEED_NAMESPACE:
            raise AssertionError("Overlapping or old seed range")
        if max(bank)>MAX_TRAJECTORY_SEED or max(bank)*100+3>MAX_NATIVE_SEED:
            raise AssertionError("Derived native gamma seed outside uint32")
        union.update(bank)
    return contracts


def run_stage(root,stage,func):
    started=time.perf_counter()
    started_utc=utc()
    try:
        result=func()
        record=dict(stage=stage,status="COMPLETED",started_utc=started_utc,
                    wall_seconds=time.perf_counter()-started,
                    completed_utc=utc(),result=result)
        save(root/f"stage_{stage}.json",record)
        print("PILOT_STAGE_DONE",stage,"wall_seconds",round(record["wall_seconds"],3),flush=True)
        return record
    except BaseException as e:
        record=dict(stage=stage,status="ERROR",started_utc=started_utc,
                    wall_seconds=time.perf_counter()-started,
                    completed_utc=utc(),error_type=type(e).__name__,
                    error=str(e),traceback=traceback.format_exc())
        save(root/f"stage_{stage}.json",record)
        print("PILOT_STAGE_FAILED",stage,type(e).__name__,str(e),flush=True)
        raise


def do_run(root,preview_file,candidate_id,graph_id,resume=False):
    candidate=validated_candidate(preview_file,candidate_id,graph_id)
    resolved = root.resolve()
    if REPO==resolved or REPO in resolved.parents or PHASE5 in resolved.parents:
        raise ValueError("Pilot output must be outside source repository")
    if resume:
        if not resolved.is_dir():
            raise FileNotFoundError("Resume output not found: "+str(resolved))
        provenance_path=resolved/"pilot_provenance_PRIVATE.json"
        provenance=read(provenance_path)
        if (provenance.get("candidate_id") != candidate_id or
                provenance.get("graph_id") != graph_id or
                provenance.get("preview_sha256") != sha(preview_file)):
            raise ValueError("Resume origin mismatch")
        phase=resolved/"isolated_contracts"
        for name in COPY_NAMES:
            if sha(phase/name) != provenance["isolated_contract_sha256"][name]:
                raise ValueError("Isolated contract changed during pilot: "+name)
    else:
        if resolved.exists():
            raise FileExistsError("Refusing existing output: "+str(resolved))
        resolved.mkdir(parents=True)
        contract_workspace(resolved,candidate,preview_file,graph_id)
        phase=resolved/"isolated_contracts"
    verify_patched_contracts(phase,candidate)
    # All scientific execution uses original modules, with ONLY the contract
    # lookup directory and the I1-card lookup directory redirected.
    import run_phase5_i1_v2 as i1
    import run_phase5_step0_v2 as step0
    original_i1_here=i1.HERE
    original_step0_here=step0.HERE
    try:
        i1.HERE = phase
        step0.HERE = phase
        public_root = phase/"results"/"01_i1"
        step0_root = resolved/"step0"
        # The public cards are created from fresh local provider trajectories,
        # and Step0's original _load_public_i1_world reads them in this workspace.
        def stage_i1():
            i1.run_world("P1",result_root=public_root,reset_world=False)
            return {"status":"FROZEN_PHASE5_I1_COMPLETE_V2",
                    "freeze_manifest_sha256":sha(public_root/"P1"/"i1_freeze_manifest.json")}
        frozen_i1=public_root/"P1"/"i1_freeze_manifest.json"
        if frozen_i1.is_file():
            frozen=read(frozen_i1)
            contracts=verify_patched_contracts(phase,candidate)
            if (frozen.get("status")!="FROZEN_PHASE5_I1_COMPLETE_V2"
                    or frozen.get("battery_config_sha256")!=sha(phase/COPY_NAMES[0])
                    or frozen.get("seed_registry_sha256")!=sha(phase/COPY_NAMES[1])):
                raise ValueError("Existing I1 freeze is not this isolated contract")
            print("PILOT_STAGE_REUSED i1 freeze verified",flush=True)
        else:
            run_stage(resolved,"i1",stage_i1)

        calib_manifest=step0_root/f"P1__{graph_id}"/"step0_calibration_manifest.json"
        if calib_manifest.is_file() and read(calib_manifest).get("status")=="GATE_FAILED_STEP0_CALIBRATION":
            print("PILOT_STAGE_REUSED calibration already rejected",flush=True)
        else:
            run_stage(resolved,"step0_calibration",
                lambda:step0._run_calibration_cell("P1",graph_id,str(step0_root)))
        # Even a calibration rejection is a measured/valid pilot result;
        # original confirmation freezes the rejection without simulation.
        confirmation_path=step0_root/f"P1__{graph_id}"/"step0_confirmation_manifest.json"
        if confirmation_path.is_file() and read(confirmation_path).get("status") in (
                "FROZEN_PHASE5_STEP0_PASS_V2","GATE_FAILED_STEP0"):
            print("PILOT_STAGE_REUSED confirmation freeze verified",flush=True)
        else:
            run_stage(resolved,"step0_confirmation",
                lambda:step0._run_confirmation_cell("P1",graph_id,str(step0_root)))
        calibration_manifest=read(step0_root/f"P1__{graph_id}"/"step0_calibration_manifest.json")
        confirmation_manifest=read(step0_root/f"P1__{graph_id}"/"step0_confirmation_manifest.json")
        summary={
            "status":"ISOLATED_STEP0_FEASIBILITY_PILOT_COMPLETE",
            "candidate_id":candidate_id, "graph_id":graph_id,
            "calibration_status":calibration_manifest["status"],
            "confirmation_status":confirmation_manifest["status"],
            "eligibility":confirmation_manifest["status"]=="FROZEN_PHASE5_STEP0_PASS_V2",
            "stage_wall_seconds":{
                s:(read(resolved/f"stage_{s}.json")["wall_seconds"]
                   if (resolved/f"stage_{s}.json").is_file() else None)
                for s in ("i1","step0_calibration","step0_confirmation")},
            "native_i1_wall_seconds":read(frozen_i1).get("python_wall_seconds"),
            "native_calibration_wall_seconds":calibration_manifest.get("python_wall_seconds"),
            "native_confirmation_wall_seconds":confirmation_manifest.get("python_wall_seconds"),
            "new_world_and_graph_simulation":True,
            "confirmatory_evidence":False,
            "private_world_parameters_in_isolated_contract_only":True,
            "observed_utc":utc(),
        }
        save(resolved/"pilot_summary.json",summary)
        print("ISOLATED_STEP0_PILOT_PASS",summary["confirmation_status"],
              "ELIGIBLE",summary["eligibility"],flush=True)
        print("PUBLIC_SUMMARY",resolved/"pilot_summary.json",flush=True)
    finally:
        i1.HERE = original_i1_here
        step0.HERE = original_step0_here


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify",action="store_true",
                      help="No simulator imports, no new outputs")
    mode.add_argument("--run",action="store_true",
                      help="Explicitly launch fresh I1 + Step0 simulation")
    mode.add_argument("--resume",action="store_true",
                      help="Resume exact isolated pilot after verifying previous workspace")
    p.add_argument("--preview",type=Path,required=True)
    p.add_argument("--out",type=Path,help="New scratch output directory, required with --run")
    p.add_argument("--candidate",default=DEFAULT_CANDIDATE)
    p.add_argument("--graph",default=DEFAULT_GRAPH)
    args=p.parse_args()
    preview=args.preview.expanduser().resolve()
    candidate=validated_candidate(preview,args.candidate,args.graph)
    if args.verify:
        original_hashes = {name: sha(PHASE5/name) for name in COPY_NAMES}
        with tempfile.TemporaryDirectory(prefix="praise_step0_isolation_verify_") as temp:
            testroot=Path(temp)
            contract_workspace(testroot,candidate,preview,args.graph)
            phase=testroot/"isolated_contracts"
            contracts=verify_patched_contracts(phase,candidate)
            if read(PHASE5/COPY_NAMES[0])["provider_worlds"][0]["D_instructions"] == candidate["D_instructions"]:
                raise AssertionError("Historical P1 was unexpectedly modified")
            for name in COPY_NAMES:
                if sha(PHASE5/name)!=original_hashes[name]:
                    raise AssertionError("Historical contract changed: "+name)
            if not (testroot/"pilot_provenance_PRIVATE.json").exists():
                raise AssertionError("Isolated provenance absent")
            if (testroot/"step0").exists():
                raise AssertionError("Verification launched unexpected simulation")
            print("ISOLATION_CHECK original_contracts_unchanged=YES isolated_world_present=YES")
            print("ISOLATION_CHECK new_seed_blocks_disjoint=YES native_gamma_uint32_safe=YES simulation_outputs=NONE")
        print("ISOLATED_STEP0_ADAPTER_VERIFY_PASS",
              "candidate",candidate["candidate_id"],"graph",args.graph)
        print("NO_SIMULATIONS_NO_PERSISTENT_OUTPUTS")
        return
    if args.out is None:
        p.error("--out is required with --run or --resume")
    do_run(args.out.expanduser(),preview,args.candidate,args.graph,resume=bool(args.resume))


if __name__=="__main__":
    main()
