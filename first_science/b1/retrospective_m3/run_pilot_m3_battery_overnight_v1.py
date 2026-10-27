#!/usr/bin/env python3
"""Resume frozen ORIGINAL-pilot M3 transfer across the Phase-II eligible battery.

Scheduling wrapper ONLY. It never alters the scientific controller, CV rules,
model selection, support threshold, graph budget, simulator, or frozen results.

P1 has already been prepared, with a recorded original-policy infeasibility:
K=14267 > B=1400. Preserve this outcome. Prepare P3 and P4 independently,
continue past ONLY the precisely documented K>B infeasibility, and run all
four graph cells for each feasible world using the original controller.

Prediction is public-only. No Phase-II white-box read/evaluation occurs here.
The controller's all-12 freeze/evaluate require every cell, so this script
does not call either when any world has an infeasible original-method support.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CTRL = HERE / "run_pilot_m3_policy_transfer_v1.py"
CFG = HERE / "config_pilot_m3_policy_transfer_v1.json"
CORE = HERE / "_pilot_m3_policy_transfer_core_v1.py"
PILOT_GATE = REPO / "first_science/b1/local_audit/pilot_m3_reproduction_gate_v1/gate.json"
OUTPUT = REPO / "first_science/phase5/results/b1_pilot_m3_policy_transfer_v1"
AUDIT = REPO / "first_science/b1/local_audit/pilot_m3_battery_overnight_v1"
STATE = AUDIT / "overnight_status.json"
GRAPHS = ("G_PAR", "G_SEQ", "G_SEQPAR", "G_PARSEQ")
WORLDS = ("P1", "P3", "P4")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_status(state: dict):
    AUDIT.mkdir(parents=True, exist_ok=True)
    state["updated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def call(stage: str, *, world: str | None = None, cell: str | None = None,
         workers: int = 4) -> tuple[int, str]:
    cmd = [sys.executable, str(CTRL), "--stage", stage, "--workers", str(workers)]
    if world:
        cmd += ["--world", world]
    if cell:
        cmd += ["--cell", cell]
    print("\n$ " + " ".join(cmd), flush=True)
    started = time.monotonic()
    tail = collections.deque(maxlen=130)
    with subprocess.Popen(
        cmd, cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            tail.append(line)
        code = proc.wait()
    print(f"STAGE {stage} {world or cell or 'ALL'} EXIT {code} "
          f"wall={((time.monotonic()-started)/60):.2f}min", flush=True)
    return code, "".join(tail)


def feasibility(world: str, budget: int) -> dict:
    path = OUTPUT / "candidate_support" / world / "support_feasibility.json"
    if not path.is_file():
        raise RuntimeError(f"{world}: missing frozen feasibility evidence {path}")
    record = read_json(path)
    if (record.get("world") != world
            or record.get("status") != "B1_PILOT_POLICY_SUPPORT_FEASIBILITY"
            or int(record.get("graph_budget", -1)) != budget
            or float(record.get("target_mass", -1)) != 0.999
            or record.get("no_graph_whitebox_read") is not True):
        raise RuntimeError(f"{world}: unexpected feasibility record; refuse to continue")
    k = int(record["top_k"])
    if bool(record["feasible"]) != (k <= budget):
        raise RuntimeError(f"{world}: feasibility flag inconsistent with frozen B={budget}")
    selection = OUTPUT / "candidate_support" / world / "cv_selection.json"
    if not selection.is_file():
        raise RuntimeError(f"{world}: missing frozen CV-selection record")
    cv = read_json(selection)
    if (cv.get("world") != world
            or cv.get("status") != "B1_PILOT_POLICY_I1_CV_FROZEN"
            or float(cv.get("selected_lambda", float("nan"))) != float(record["selected_lambda"])):
        raise RuntimeError(f"{world}: mismatched CV and support evidence")
    if record["feasible"]:
        manifest = OUTPUT / "candidate_support" / world / "support_manifest.json"
        support = OUTPUT / "candidate_support" / world / "adaptive_support.csv"
        if (not manifest.is_file() or not support.is_file()
                or read_json(manifest).get("status") != "B1_PILOT_POLICY_SUPPORT_FROZEN"
                or read_json(manifest).get("support_sha256") != file_sha(support)):
            raise RuntimeError(f"{world}: feasible but support is not properly frozen")
    else:
        if (OUTPUT / "candidate_support" / world / "support_manifest.json").exists():
            raise RuntimeError(f"{world}: infeasible but support manifest exists")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--prepare-only", action="store_true",
                    help="Prepare P3/P4 only, do not start graph simulations")
    args = ap.parse_args()
    if not 1 <= args.workers <= 16:
        ap.error("--workers must be 1..16")
    cfg = read_json(CFG)
    if (cfg["eligible_worlds"] != list(WORLDS)
            or cfg["graphs"] != list(GRAPHS)
            or cfg["graph_budget"] != 1400
            or cfg["target_mass"] != 0.999):
        raise RuntimeError("Frozen 12-cell transfer contract changed")
    if not PILOT_GATE.is_file():
        raise RuntimeError("Original pilot reproduction gate not sealed")
    gate = read_json(PILOT_GATE)
    if (gate.get("status") != "B1_PILOT_REPRODUCTION_GATE_PASS"
            or gate.get("decision") != "PASS"):
        raise RuntimeError("Original pilot gate not passed")

    hashes = {str(p.relative_to(REPO)): file_sha(p)
              for p in (CFG, CTRL, CORE, PILOT_GATE)}
    if STATE.is_file():
        prior = read_json(STATE)
        if prior.get("source_hashes") != hashes:
            raise RuntimeError(
                "Frozen policy/gate changed since previous overnight run. "
                "Do not continue silently."
            )
        status = prior
    else:
        status = {
            "status": "IN_PROGRESS",
            "description": "Frozen original-pilot policy transfer; scheduling only",
            "source_hashes": hashes,
            "workers": args.workers,
            "worlds": {}, "cells": {},
            "whitebox_read": False,
            "global_12_cell_accuracy_scored": False,
        }
    save_status(status)

    try:
        rc, _ = call("preflight", workers=args.workers)
        if rc:
            raise RuntimeError("Frozen policy preflight failed")
        # The verified P1 result is not recomputed or overridden.
        p1 = feasibility("P1", cfg["graph_budget"])
        status["worlds"]["P1"] = p1
        if p1["feasible"]:
            raise RuntimeError("P1 was previously infeasible; unexpected changed selection")
        for graph in GRAPHS:
            status["cells"][f"P1__{graph}"] = "INFEASIBLE_ORIGINAL_POLICY_K_EXCEEDS_B"
        print(f"\nP1 PRESERVED: lambda={p1['selected_lambda']}, "
              f"K={p1['top_k']} > B={p1['graph_budget']}; "
              "no new selection rule or fallback", flush=True)
        save_status(status)

        for world in ("P3", "P4"):
            print(f"\n========== PREPARE {world} (FROZEN ORIGINAL POLICY) ==========", flush=True)
            rc, tail = call("prepare", world=world, workers=args.workers)
            f = feasibility(world, cfg["graph_budget"])
            if rc:
                expected_stop = (
                    f["feasible"] is False
                    and "original 99.9%-mass selection requires K=" in tail
                    and "Feasibility saved; stop without changing either rule." in tail
                )
                if not expected_stop:
                    raise RuntimeError(
                        f"{world}: unexpected preparation error, halt; "
                        "inspect log before restarting"
                    )
                print(f"EXPECTED ORIGINAL-POLICY INFEASIBILITY {world}: "
                      f"K={f['top_k']} > B={f['graph_budget']}", flush=True)
            elif not f["feasible"]:
                raise RuntimeError(f"{world}: preparation returned success but infeasible")
            else:
                print(f"FROZEN SUPPORT READY {world}: lambda={f['selected_lambda']}, "
                      f"K={f['top_k']}, retained_mass={f['retained_mass']:.8f}", flush=True)
            status["worlds"][world] = f
            if not f["feasible"]:
                for graph in GRAPHS:
                    status["cells"][f"{world}__{graph}"] = \
                        "INFEASIBLE_ORIGINAL_POLICY_K_EXCEEDS_B"
            save_status(status)

        if args.prepare_only:
            status["status"] = "PREPARATION_COMPLETE"
            save_status(status)
            print("\nPREPARATION_COMPLETE: frozen method and feasibility recorded "
                  "for P1/P3/P4; no graph simulations", flush=True)
            return

        # No white-box access. Each feasible cell is handled independently.
        for world in WORLDS:
            if not status["worlds"][world]["feasible"]:
                continue
            for graph in GRAPHS:
                cell = f"{world}__{graph}"
                manifest = OUTPUT / "predictions" / cell / "prediction_manifest.json"
                if not manifest.is_file():
                    rc, _ = call("graph-benchmark", cell=cell, workers=args.workers)
                    if rc:
                        raise RuntimeError(f"{cell}: graph benchmark failed; halt")
                rc, _ = call("predict", cell=cell, workers=args.workers)
                if rc:
                    raise RuntimeError(f"{cell}: frozen policy graph prediction failed")
                if not manifest.is_file():
                    raise RuntimeError(f"{cell}: prediction returned success without freeze")
                marker = read_json(manifest)
                if (marker.get("status") != "B1_PILOT_POLICY_CELL_PREDICTED"
                        or marker.get("reference_whitebox_read") is not False):
                    raise RuntimeError(f"{cell}: invalid frozen prediction manifest")
                status["cells"][cell] = "PREDICTIONS_FROZEN_NO_WB_ACCESS"
                save_status(status)

        status["status"] = "FEASIBLE_CELLS_COMPLETE"
        status["all_12_cells_feasible"] = all(
            status["worlds"][w]["feasible"] for w in WORLDS
        )
        status["predicted_cells"] = sum(
            v == "PREDICTIONS_FROZEN_NO_WB_ACCESS"
            for v in status["cells"].values()
        )
        status["not_predicted_infeasible_cells"] = sum(
            v == "INFEASIBLE_ORIGINAL_POLICY_K_EXCEEDS_B"
            for v in status["cells"].values()
        )
        save_status(status)
        print("\nFROZEN ORIGINAL POLICY BATTERY EXECUTION COMPLETE", flush=True)
        print(f"Frozen prediction cells: {status['predicted_cells']}/12; "
              f"infeasible cells: {status['not_predicted_infeasible_cells']}/12",
              flush=True)
        print("No white-box data opened. No automatic fallback, "
              "no replacement of the original 12-cell accuracy metric.", flush=True)
        print(f"Status evidence: {STATE}", flush=True)
    except BaseException as exc:
        status["status"] = "HALTED_ERROR"
        status["error"] = f"{type(exc).__name__}: {exc}"
        save_status(status)
        print(f"\nHALTED_ERROR: {exc}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
