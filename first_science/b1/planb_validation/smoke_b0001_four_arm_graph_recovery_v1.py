#!/usr/bin/env python3
"""Disposable deterministic interruption/restart proof for B0001 graph engine.

--check: read-only provenance validation, no graph simulations or writes.
--smoke: on P1/G_PAR, each of four frozen method definitions performs a
deliberately interrupted three-seed run (after one completed checkpoint),
resumes, and compares the ledger byte-for-byte with a fresh uninterrupted run.
Only a fresh engineering --out directory is written; science remains blocked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
P5 = REPO / "first_science" / "phase5"
WORLD, GRAPH = "P1", "G_PAR"
METHODS = ("ORIGINAL_TOP14_B1400", "ORIGINAL_TOP1_B1400",
           "FIXED_CV_TOP14", "FIXED_CV_TOP1")
ENGINEERING_SEEDS = {name: list(range(39_300_001 + 10 * i,
                                      39_300_004 + 10 * i))
                     for i, name in enumerate(METHODS)}
AUDIT_STATUS = "B0001_FOUR_ARM_SCIENCE_PLAN_INDEPENDENT_AUDIT_PASS_EXECUTION_BLOCKED"
STATUS = "B0001_FOUR_ARM_DISPOSABLE_GRAPH_RECOVERY_SMOKE_PASS_EXECUTION_BLOCKED"


def require(ok, why):
    if not bool(ok):
        raise RuntimeError("B0001 GRAPH RECOVERY: " + why)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def engines():
    for folder in (REPO / "first_science" / "phase2",
                   REPO / "first_science" / "phase3",
                   REPO / "first_science" / "phase4", P5,
                   REPO / "first_science" / "b1" / "retrospective_m3"):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    import run_phase5_graph_prediction_v3b_fullsupport as graph
    from phase5_runtime_v2 import load_phase5_contracts, graph_record
    return graph, load_phase5_contracts, graph_record


def preflight(a):
    for key in ("science", "audit", "gate", "weights", "staging"):
        path = getattr(a, key)
        require(path.is_dir(), "Frozen input directory missing: " + str(path))
        require(a.out != path and a.out not in path.parents and
                path not in a.out.parents, "Disposable output overlaps frozen input")
    require(a.out != REPO and REPO not in a.out.parents,
            "Disposable output must not be in Git source repository")
    files = {
        "plan": a.science / "b0001_four_arm_science_execution_plan.json",
        "audit": a.audit / "b0001_four_arm_science_plan_independent_audit.json",
        "gate": a.gate / "b0001_four_arm_graph_isolation_preflight.json",
        "weights": a.weights / "b0001_48_lhs_weight_and_support_freeze.json",
        "staging": a.staging / "b0001_public_inputs_manifest.json",
    }
    for name, file in files.items():
        require(file.is_file(), "Missing frozen contract: " + name)
    plan, audit, gate = (read(files[name]) for name in ("plan", "audit", "gate"))
    require(audit["status"] == AUDIT_STATUS and
            audit["source_plan_sha256"] == digest(files["plan"]) and
            audit["source_gate_sha256"] == digest(files["gate"]) and
            audit["source_weights_sha256"] == digest(files["weights"]) and
            audit["source_staging_sha256"] == digest(files["staging"]) and
            audit["method_cells_verified"] == 48 and
            audit["graph_trajectories_planned"] == 67200 and
            audit["scientific_graph_execution_authorized"] is False and
            audit["whitebox_reference_read"] is False,
            "Independent frozen read-only audit is not valid")
    require(plan["scientific_graph_execution_authorized"] is False and
            plan["graph_simulations_executed"] == 0 and
            gate["scientific_graph_execution_authorized"] is False and
            gate["whitebox_reference_read"] is False,
            "Scientific execution firewall not intact")
    engine_path = REPO / "first_science" / "phase5" / "run_phase5_graph_prediction_v3b_fullsupport.py"
    require(digest(engine_path) == gate["source_code_sha256"][
                "first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py"],
            "Graph engine hash changed since isolation gate")
    query = a.staging / "frozen_queries" / (WORLD + "__" + GRAPH) / "step0_frozen_queries.csv"
    require(query.is_file() and len(pd.read_csv(query)) == 15,
            "Staged public queries missing")
    representatives = {}
    for method in METHODS:
        matches = [row for row in plan["method_cells"]
                   if row["method"] == method and row["cell"] == WORLD + "__" + GRAPH]
        require(len(matches) == 1, "Missing representative frozen method: " + method)
        row = matches[0]
        require(digest(query) == row["query_sha256"] and
                len(row["variants"]) in (1, 14),
                "Frozen method query or support mismatch")
        representatives[method] = row["variants"][0]
    require(len({seed for seeds in ENGINEERING_SEEDS.values() for seed in seeds}) == 12 and
            min(seed for seeds in ENGINEERING_SEEDS.values() for seed in seeds) > 39_200_004 and
            max(seed for seeds in ENGINEERING_SEEDS.values() for seed in seeds) < 39_500_000,
            "Engineering seed namespace conflict")
    # Snapshots taken before and after test; no traversal of privileged reference.
    watch = dict(files)
    watch["query"] = query
    for method, variant in representatives.items():
        family = "original" if method.startswith("ORIGINAL") else "fixed_cv"
        root = a.weights / family / WORLD
        watch[method + "_support"] = root / "support" / "top14_support.csv"
        for provider in ("ProviderA", "ProviderB", "ProviderC"):
            watch[method + "_" + provider] = root / provider / "provider_weights.csv"
    before = {key: digest(path) for key, path in watch.items()}
    return files, before, watch, representatives


def recovery(a, files, before, watch, representatives):
    require(not a.out.exists(), "Refusing reuse/overwrite of engineering recovery directory")
    graph, load_contracts, graph_record = engines()
    contracts = load_contracts(P5)
    record = graph_record(contracts, GRAPH)
    a.out.mkdir(parents=True)
    results = {}
    for method, variant in representatives.items():
        name = "ENGINEERING_RECOVERY_" + method
        seeds = ENGINEERING_SEEDS[method]
        surrogates = {p: graph._surrogate(pd.Series(q))
                      for p, q in variant["surrogates"].items()}

        def payload(root):
            return graph._simulation_payload(
                cell_root=root, graph_id=GRAPH, graph_ast=record["ast"],
                variant_id=name, surrogates=surrogates, seeds=seeds,
                ledger_path=root / "ledgers" / "three_trajectories.csv",
                contracts=contracts)

        resumed_root = a.out / "engineering_only" / method / "interrupted_resumed"
        uninterrupted_root = a.out / "engineering_only" / method / "uninterrupted"
        interrupted = payload(resumed_root)
        baseline = payload(uninterrupted_root)
        # Deliberately abort on the SECOND simulation call: the first seed's
        # atomic checkpoint has already been committed by the real engine.
        original = graph.execute_one_phase5_graph_trajectory
        calls = [0]
        class IntentionalInterruption(Exception):
            pass

        def interrupt_after_checkpoint(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise IntentionalInterruption("test-only interruption after first seed")
            return original(*args, **kwargs)

        graph.execute_one_phase5_graph_trajectory = interrupt_after_checkpoint
        interrupted_as_planned = False
        try:
            try:
                graph._simulate_variant_worker(interrupted)
            except IntentionalInterruption:
                interrupted_as_planned = True
        finally:
            graph.execute_one_phase5_graph_trajectory = original
        require(interrupted_as_planned and calls[0] == 2,
                "Simulation did not interrupt at intended checkpoint boundary")
        cp = graph._variant_checkpoint(resumed_root, name, seeds[0])
        absent = graph._variant_checkpoint(resumed_root, name, seeds[1])
        require(cp.is_file() and not absent.exists() and
                not Path(interrupted["ledger_path"]).exists(),
                "Interrupted run did not leave precisely one usable checkpoint")
        checkpoint_sha = digest(cp)
        checkpoint_mtime = cp.stat().st_mtime_ns
        # Count only fresh simulation calls: the resumed worker MUST skip seed0.
        resumed_calls = [0]
        def counting(*args, **kwargs):
            resumed_calls[0] += 1
            return original(*args, **kwargs)

        graph.execute_one_phase5_graph_trajectory = counting
        try:
            resumed_result = graph._simulate_variant_worker(interrupted)
        finally:
            graph.execute_one_phase5_graph_trajectory = original
        require(resumed_calls[0] == 2 and
                resumed_result["reused"] is False,
                "Restart did not reuse completed checkpoint")
        resumed_path = Path(resumed_result["ledger_path"])
        require(len(graph._validate_complete_ledger(resumed_path, seeds).trajectory.unique()) == 3,
                "Resumed three-trajectory ledger incomplete")
        # Once ledger is complete, historical worker removes checkpoints;
        # the resumption proof is a reduced call count plus unchanged seed0
        # data in the materialized ledger.
        require(not cp.exists() and
                not (resumed_root / "checkpoints" / name).exists(),
                "Historical completed ledger did not retire checkpoints")
        baseline_result = graph._simulate_variant_worker(baseline)
        baseline_path = Path(baseline_result["ledger_path"])
        graph._validate_complete_ledger(baseline_path, seeds)
        require(resumed_path.read_bytes() == baseline_path.read_bytes(),
                "Resumed ledger differs byte-for-byte from uninterrupted baseline")
        frozen_sha = digest(resumed_path)
        prior_stat = resumed_path.stat().st_mtime_ns
        reused = graph._simulate_variant_worker(interrupted)
        require(reused["reused"] is True and
                digest(resumed_path) == frozen_sha and
                resumed_path.stat().st_mtime_ns == prior_stat,
                "Complete ledger was overwritten instead of reused")
        results[method] = {
            "engineering_seeds": seeds,
            "first_checkpoint_sha256_before_resume": checkpoint_sha,
            "first_checkpoint_mtime_ns_before_resume": checkpoint_mtime,
            "interrupted_after_simulation_calls": calls[0],
            "fresh_simulation_calls_on_resume": resumed_calls[0],
            "expected_fresh_calls_on_resume": 2,
            "resumed_ledger_sha256": frozen_sha,
            "uninterrupted_ledger_sha256": digest(baseline_path),
            "identical_ledgers": True,
            "completed_ledger_reused_without_overwrite": True,
        }
        print("B0001_GRAPH_RECOVERY_METHOD_PASS", method,
              "1 checkpoint + 2 resumed = 3; byte-identical baseline", flush=True)
    after = {key: digest(path) for key, path in watch.items()}
    require(after == before, "Frozen science source modified by engineering smoke")
    require(not (a.science / "scientific").exists(),
            "Science output appeared during disposable recovery test")
    manifest = {"status": STATUS, "method_tests": results,
                "method_count": 4, "interrupted_trajectories_completed": 12,
                "uninterrupted_baseline_trajectories": 12,
                "frozen_source_sha256_before": before,
                "frozen_source_sha256_after": after,
                "source_science_plan_sha256": digest(files["plan"]),
                "source_audit_sha256": digest(files["audit"]),
                "scientific_graph_simulations": 0,
                "whitebox_reference_read": False,
                "scientific_execution_authorized": False}
    target = a.out / "engineering_only" / "b0001_four_arm_recovery_smoke_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), "Recovery manifest already exists")
    target.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("B0001_FOUR_ARM_DISPOSABLE_GRAPH_RECOVERY_SMOKE_PASS", flush=True)
    print("SCIENCE_EXECUTION_BLOCKED / NO_WHITEBOX_READ", flush=True)
    print("SMOKE", target, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("science", "audit", "gate", "weights", "staging", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    for key in ("science", "audit", "gate", "weights", "staging", "out"):
        setattr(a, key, getattr(a, key).expanduser().resolve())
    files, before, watch, reps = preflight(a)
    print("B0001_GRAPH_RECOVERY_PREFLIGHT_PASS", len(reps),
          "methods; three engineering seeds per method", flush=True)
    if a.check:
        print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ", flush=True)
        return
    recovery(a, files, before, watch, reps)


if __name__ == "__main__":
    main()
