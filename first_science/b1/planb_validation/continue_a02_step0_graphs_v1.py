#!/usr/bin/env python3
"""Continue A02 Step-0 graph eligibility without changing the frozen G_PAR cell.

Runs G_SEQ, G_SEQPAR, G_PARSEQ in order, reusing the A02 isolated
contracts and frozen I1 cards. Original Phase-5 scientific functions are
called directly. Read-only --verify is the default and does not simulate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import isolated_step0_pilot_v1 as pilot

CANDIDATE = "B0001_P1_A02"
COMPLETED_GRAPH = "G_PAR"
REMAINING_GRAPHS = ("G_SEQ", "G_SEQPAR", "G_PARSEQ")
PASS = "FROZEN_PHASE5_STEP0_PASS_V2"
CALIBRATION_PASS = "FROZEN_PHASE5_STEP0_CALIBRATION_PASS_V2"


def require_workspace(root: Path, preview: Path):
    root = root.expanduser().resolve()
    preview = preview.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError("A02 workspace is missing: " + str(root))
    if root == pilot.REPO or pilot.REPO in root.parents:
        raise ValueError("Workspace must be outside source repository")
    candidate = pilot.validated_candidate(preview, CANDIDATE, COMPLETED_GRAPH)
    provenance_path = root / "pilot_provenance_PRIVATE.json"
    provenance = pilot.read(provenance_path)
    if (provenance.get("candidate_id") != CANDIDATE or
            provenance.get("graph_id") != COMPLETED_GRAPH or
            provenance.get("preview_sha256") != pilot.sha(preview)):
        raise ValueError("A02/G_PAR pilot provenance mismatch")
    phase = root / "isolated_contracts"
    for name in pilot.COPY_NAMES:
        p = phase / name
        if not p.is_file() or pilot.sha(p) != provenance["isolated_contract_sha256"][name]:
            raise ValueError("Private frozen contract mismatch: " + name)
    pilot.verify_patched_contracts(phase, candidate)
    frozen_i1 = phase / "results" / "01_i1" / "P1" / "i1_freeze_manifest.json"
    fm = pilot.read(frozen_i1)
    if (fm.get("status") != "FROZEN_PHASE5_I1_COMPLETE_V2" or
            fm.get("battery_config_sha256") != pilot.sha(phase / pilot.COPY_NAMES[0]) or
            fm.get("seed_registry_sha256") != pilot.sha(phase / pilot.COPY_NAMES[1])):
        raise ValueError("Frozen I1 acquisition cannot be safely reused")
    par_root = root / "step0" / "P1__G_PAR"
    par_calibration = par_root / "step0_calibration_manifest.json"
    par_confirmation = par_root / "step0_confirmation_manifest.json"
    if (pilot.read(par_calibration).get("status") != CALIBRATION_PASS or
            pilot.read(par_confirmation).get("status") != PASS):
        raise ValueError("Original A02/G_PAR pass is missing or altered")
    selected = par_root / "step0_selected_queries.csv"
    frozen = par_root / "step0_frozen_queries.csv"
    if not selected.is_file() or not frozen.is_file():
        raise ValueError("Existing G_PAR frozen query files missing")
    original = {
        str(p.relative_to(root)): pilot.sha(p)
        for p in (provenance_path, frozen_i1, par_calibration,
                  par_confirmation, selected, frozen)
    }
    return root, phase, original


def check_preservation(root: Path, hashes: dict):
    for rel, expected in hashes.items():
        if pilot.sha(root / rel) != expected:
            raise AssertionError("Original A02 evidence changed: " + rel)


def run_graph(step0, root: Path, graph: str):
    cell = root / "step0" / ("P1__" + graph)
    cm_path = cell / "step0_calibration_manifest.json"
    fm_path = cell / "step0_confirmation_manifest.json"
    if cm_path.is_file():
        cm = pilot.read(cm_path)
        if cm["status"] not in (CALIBRATION_PASS, "GATE_FAILED_STEP0_CALIBRATION"):
            raise ValueError("Unexpected existing calibration status for " + graph)
        print("REUSE_FROZEN_CALIBRATION", graph, cm["status"], flush=True)
    else:
        pilot.run_stage(root, "step0_calibration_" + graph,
            lambda: step0._run_calibration_cell("P1", graph, str(root / "step0")))
    if fm_path.is_file():
        fm = pilot.read(fm_path)
        if fm["status"] not in (PASS, "GATE_FAILED_STEP0"):
            raise ValueError("Unexpected existing confirmation status for " + graph)
        print("REUSE_FROZEN_CONFIRMATION", graph, fm["status"], flush=True)
    else:
        pilot.run_stage(root, "step0_confirmation_" + graph,
            lambda: step0._run_confirmation_cell("P1", graph, str(root / "step0")))
    cm = pilot.read(cm_path)
    fm = pilot.read(fm_path)
    return {
        "graph_id": graph,
        "calibration_status": cm["status"],
        "confirmation_status": fm["status"],
        "eligible": fm["status"] == PASS,
        "failures": fm.get("failures", []),
        "calibration_wall_seconds": cm.get("python_wall_seconds"),
        "confirmation_wall_seconds": fm.get("python_wall_seconds"),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", required=True, type=Path)
    p.add_argument("--workspace", required=True, type=Path)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true",
                      help="Read-only validation without any simulations")
    mode.add_argument("--run", action="store_true",
                      help="Continue remaining graphs in original order")
    args = p.parse_args()
    root, phase, original_hashes = require_workspace(args.workspace, args.preview)
    graphs = pilot.read(phase / pilot.COPY_NAMES[0])["graphs"]
    known = {g["id"] for g in graphs}
    if not set(REMAINING_GRAPHS).issubset(known):
        raise ValueError("Some requested graph IDs do not exist in frozen contract")
    if args.verify:
        check_preservation(root, original_hashes)
        print("A02_GRAPH_CONTINUATION_VERIFY_PASS",
              "frozen_I1=YES", "G_PAR_PASS_PRESERVED=YES",
              "remaining=" + ",".join(REMAINING_GRAPHS), flush=True)
        print("NO_SIMULATIONS_NO_OUTPUTS", flush=True)
        return

    # Only the original scientific module's contract lookup is redirected;
    # no candidate selection, query rules, or simulation code changes.
    sys.path.insert(0, str(pilot.PHASE5))
    import run_phase5_step0_v2 as step0
    old_here = step0.HERE
    summaries = []
    try:
        step0.HERE = phase
        for graph in REMAINING_GRAPHS:
            check_preservation(root, original_hashes)
            print("A02_GRAPH_START", graph, flush=True)
            summaries.append(run_graph(step0, root, graph))
            check_preservation(root, original_hashes)
            print("A02_GRAPH_DONE", graph,
                  "eligible", summaries[-1]["eligible"], flush=True)
        existing = pilot.read(root / "pilot_summary.json")
        if (existing.get("candidate_id") != CANDIDATE or
                existing.get("graph_id") != COMPLETED_GRAPH or
                existing.get("eligibility") is not True):
            raise ValueError("G_PAR pilot summary unexpected; refusing rollup")
        output = {
            "status": "A02_FOUR_GRAPH_STEP0_ELIGIBILITY_COMPLETE",
            "candidate_id": CANDIDATE,
            "provider_world_role": "P1",
            "original_G_PAR_eligible": True,
            "other_graphs": summaries,
            "all_four_graphs_eligible": all(x["eligible"] for x in summaries),
            "frozen_I1_reused": True,
            "original_G_PAR_file_sha256": original_hashes,
            "method_outcomes_used": False,
            "confirmatory_evidence": False,
        }
        outfile = root / "a02_four_graph_eligibility_summary.json"
        if outfile.is_file():
            old = pilot.read(outfile)
            if (old.get("candidate_id") != CANDIDATE or
                    old.get("status") != output["status"]):
                raise ValueError("Unexpected existing four-graph summary")
        pilot.save(outfile, output)
        print("A02_FOUR_GRAPH_ELIGIBILITY",
              "PASS" if output["all_four_graphs_eligible"] else "FAILED",
              "summary", outfile, flush=True)
    finally:
        step0.HERE = old_here


if __name__ == "__main__":
    main()
