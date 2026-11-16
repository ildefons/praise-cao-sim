#!/usr/bin/env python3
"""Blind, checkpointable B0001 four-method graph predictions.

--check performs no writes or graph simulations.
--freeze-plan freezes the 48-cell execution specification, without simulation.
--run requires an explicit --authorize-science-run flag AND the matching plan.
Neither mode reads the final white-box reference or previous graph outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
P5 = REPO / "first_science" / "phase5"
FAMILIES = ("original", "fixed_cv")
WORLDS = ("P1", "P3", "P4")
GRAPHS = ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
METHODS = {"original": ("ORIGINAL_TOP14_B1400", "ORIGINAL_TOP1_B1400"),
           "fixed_cv": ("FIXED_CV_TOP14", "FIXED_CV_TOP1")}
GATE_STATUS = "B0001_FOUR_ARM_GRAPH_ISOLATION_PREFLIGHT_FROZEN_EXECUTION_BLOCKED"
SMOKE_STATUS = "B0001_FOUR_ARM_GRAPH_ADAPTER_ENGINEERING_SMOKE_PASS_SCIENCE_BLOCKED"
PLAN_STATUS = "B0001_FOUR_ARM_48_CELL_SCIENCE_PLAN_FROZEN_EXECUTION_BLOCKED"
METHOD_STATUS = "B0001_FOUR_ARM_METHOD_GRAPH_CELL_FROZEN"
GLOBAL_STATUS = "B0001_FOUR_ARM_48_METHOD_CELLS_GRAPH_PREDICTIONS_FROZEN"
BUDGET = 1400
POINTS = 735


def require(ok, message):
    if not bool(ok):
        raise RuntimeError("B0001 FOUR-ARM SCIENCE: " + message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for part in iter(lambda: handle.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(read(path) == value, "Existing freeze differs: " + str(path))
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    require(not temporary.exists(), "Unresolved temporary freeze: " + str(temporary))
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def frozen_csv(path, frame):
    expected = frame.to_csv(index=False).encode("utf-8")
    if path.exists():
        require(path.read_bytes() == expected,
                "Existing scientific CSV differs on checkpoint resume: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    require(not temporary.exists(), "Unresolved temporary CSV: " + str(temporary))
    temporary.write_bytes(expected)
    temporary.replace(path)


def engines():
    for folder in (REPO / "first_science" / "phase2",
                   REPO / "first_science" / "phase3",
                   REPO / "first_science" / "phase4", P5,
                   REPO / "first_science" / "b1" / "retrospective_m3"):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    import run_phase5_graph_prediction_v3b_fullsupport as graph
    from phase5_runtime_v2 import load_phase5_contracts, graph_record
    from run_pilot_m3_generalization_v1 import predictions
    return graph, load_phase5_contracts, graph_record, predictions


def inputs(a):
    for name in ("gate", "weights", "staging", "smoke"):
        source = getattr(a, name)
        require(source.is_dir(), "Missing frozen input: " + str(source))
        require(source != a.out and source not in a.out.parents and a.out not in source.parents,
                "Input/output directory overlap: " + name)
    require(a.out != REPO and REPO not in a.out.parents,
            "Science output must not be inside the repository")
    gate_file = a.gate / "b0001_four_arm_graph_isolation_preflight.json"
    weight_file = a.weights / "b0001_48_lhs_weight_and_support_freeze.json"
    stage_file = a.staging / "b0001_public_inputs_manifest.json"
    smoke_file = a.smoke / "engineering_only" / "b0001_four_arm_graph_smoke_manifest.json"
    gate = read(gate_file)
    smoke = read(smoke_file)
    require(gate["status"] == GATE_STATUS and
            gate["scientific_graph_execution_authorized"] is False and
            gate["graph_simulations_executed"] == 0 and
            gate["whitebox_reference_read"] is False,
            "Frozen isolation gate is invalid")
    require(smoke["status"] == SMOKE_STATUS and
            smoke["engineering_trajectories"] == 4 and
            smoke["scientific_graph_simulations"] == 0 and
            smoke["reference_whitebox_read"] is False and
            smoke["graph_isolation_gate_sha256"] == digest(gate_file) and
            smoke["weight_freeze_sha256"] == digest(weight_file) and
            smoke["public_staging_manifest_sha256"] == digest(stage_file),
            "Engineering smoke provenance invalid")
    require(gate["weight_freeze_sha256"] == digest(weight_file) and
            gate["public_input_freeze_sha256"] == digest(stage_file),
            "Changed frozen public inputs")
    for rel, expected in gate["source_code_sha256"].items():
        require(digest(REPO / rel) == expected, "Scientific engine drift: " + rel)
    require(gate["nominal_trajectories_remaining"] == 67200 and
            gate["n_method_cell_observations_missing"] == 48 and
            gate["worlds"] == list(WORLDS) and gate["graphs"] == list(GRAPHS),
            "Unexpected scientific experiment cardinality")
    return {"gate": digest(gate_file), "weights": digest(weight_file),
            "staging": digest(stage_file), "smoke": digest(smoke_file)}, gate


def specification(a, gate, fingerprints):
    rows = []
    for family in FAMILIES:
        for world in WORLDS:
            support_meta = gate["world_supports_and_fresh_graph_seeds"][family + "/" + world]
            path = a.weights / family / world / "support" / "top14_support.csv"
            require(path == Path(support_meta["top14_support_path"]) and
                    digest(path) == support_meta["top14_support_sha256"],
                    "Frozen Top14 support fingerprint mismatch")
            support = pd.read_csv(path)
            require(len(support) == 14 and
                    support.joint_rank.astype(int).tolist() == list(range(1, 15)) and
                    int(support.n_trajectories.sum()) == BUDGET and
                    np.isclose(support.alpha.sum(), 1, atol=1e-12),
                    "Invalid frozen Top14 allocation")
            provider_tables = {}
            for provider in PROVIDERS:
                p = a.weights / family / world / provider / "provider_weights.csv"
                provider_tables[provider] = pd.read_csv(p).set_index("candidate_id", verify_integrity=True)
                require(len(provider_tables[provider]) == 48,
                        "Invalid provider candidate bank: " + str(p))
            ranks = support_meta["top14_rank_seed_blocks"]
            require(len(ranks) == 14, "Missing Top14 reserved seed blocks")
            for graph in GRAPHS:
                query = a.staging / "frozen_queries" / f"{world}__{graph}" / "step0_frozen_queries.csv"
                require(query.is_file() and len(pd.read_csv(query)) == 15,
                        "Missing public graph query: " + str(query))
                for kind, method in (("top14", METHODS[family][0]),
                                     ("top1", METHODS[family][1])):
                    configs = []
                    for index, row in support.iterrows():
                        if kind == "top1" and index > 0:
                            break
                        rank = int(row.joint_rank)
                        n = int(row.n_trajectories) if kind == "top14" else BUDGET
                        if kind == "top14":
                            block = ranks[index]
                            require(int(block["joint_rank"]) == rank and
                                    int(block["n_trajectories"]) == n,
                                    "Top14 allocation disagrees with reserved seed block")
                            start, end = int(block["seed_start"]), int(block["seed_end_inclusive"])
                        else:
                            start = int(support_meta["top1_seed_start"])
                            end = int(support_meta["top1_seed_end_inclusive"])
                        require(end - start + 1 == n and 0 < start <= end < 2**32,
                                "Scientific seed allocation mismatch")
                        ids = {p: str(row[p + "_candidate_id"]) for p in PROVIDERS}
                        surrogates = {}
                        for provider in PROVIDERS:
                            table = provider_tables[provider]
                            require(ids[provider] in table.index, "Missing surrogate: " + ids[provider])
                            entry = table.loc[ids[provider]]
                            surrogates[provider] = {key: float(entry[key]) for key in
                                                    ("mean_service_time", "cost_rate", "service_cv")}
                        configs.append({"rank": rank, "n": n, "seed_start": start,
                                        "seed_end": end, "candidate_ids": ids,
                                        "surrogates": surrogates,
                                        "alpha": float(row.alpha) if kind == "top14" else 1.0,
                                        "joint_weight": float(row.joint_weight)})
                    require(sum(c["n"] for c in configs) == BUDGET and
                            np.isclose(sum(c["alpha"] for c in configs), 1, atol=1e-12),
                            "Method allocation invalid")
                    rows.append({"cell": f"{world}__{graph}", "world": world,
                                 "graph": graph, "family": family,
                                 "kind": kind, "method": method,
                                 "query_sha256": digest(query),
                                 "support_sha256": digest(path),
                                 "variants": configs})
    require(len(rows) == 48 and
            sum(sum(c["n"] for c in row["variants"]) for row in rows) == 67200,
            "Total experiment cardinality mismatch")
    return {"status": PLAN_STATUS, "input_sha256": fingerprints,
            "method_cells": rows, "method_cell_count": 48,
            "nominal_graph_trajectories": 67200,
            "whitebox_reference_read": False, "graph_simulations_executed": 0,
            "scientific_graph_execution_authorized": False}


def execute_method(a, row, graph, contracts, graph_record, predictions):
    cell = a.out / "scientific" / row["method"] / row["cell"]
    manifest_path = cell / "prediction_manifest.json"
    if manifest_path.exists():
        require(read(manifest_path)["status"] == METHOD_STATUS,
                "Existing method manifest is not frozen")
        verify_method(cell, row)
        print("B0001_SCIENCE_METHOD_CELL_CACHED", row["method"], row["cell"], flush=True)
        return
    query_path = a.staging / "frozen_queries" / row["cell"] / "step0_frozen_queries.csv"
    require(digest(query_path) == row["query_sha256"], "Graph query changed")
    old_step0 = graph.STEP0_ROOT
    graph.STEP0_ROOT = a.staging / "frozen_queries"
    try:
        queries = graph._query_definitions(row["cell"])
    finally:
        graph.STEP0_ROOT = old_step0
    horizons = graph._horizons(read(P5 / "config_phase5_graph_prediction_v3b_fullsupport.json"))
    require(len(horizons) == 49, "Historical horizon contract changed")
    record = graph_record(contracts, row["graph"])
    payloads = []
    for v in row["variants"]:
        seedset = list(range(v["seed_start"], v["seed_end"] + 1))
        provider_surrogates = {p: graph._surrogate(pd.Series(q))
                               for p, q in v["surrogates"].items()}
        variant_id = "R%02d" % v["rank"]
        payloads.append(graph._simulation_payload(
            cell_root=cell, graph_id=row["graph"], graph_ast=record["ast"],
            variant_id=variant_id, surrogates=provider_surrogates,
            seeds=seedset, ledger_path=cell / "ledgers" / (variant_id + ".csv"),
            contracts=contracts))
    graph._execute_payloads(payloads, workers=a.workers,
                            label="B0001 " + row["method"] + " " + row["cell"])
    members = []
    ledger_sha = {}
    for v, payload in zip(row["variants"], payloads):
        path = Path(payload["ledger_path"])
        seeds = list(range(v["seed_start"], v["seed_end"] + 1))
        ledger = graph._validate_complete_ledger(path, seeds)
        require(not ledger[["trajectory", "request_id"]].duplicated().any(),
                "Duplicate trajectory/request in ledger")
        ledger_sha[path.name] = digest(path)
        member = graph._member_curves(
            ledger=ledger, queries=queries, horizons=horizons,
            method_id=row["method"], rank=v["rank"], graph_n=v["n"],
            joint_weight=v["joint_weight"], candidate_ids=v["candidate_ids"])
        require(len(member) == POINTS and
                member.sigma_member.between(0, 1).all(),
                "Incomplete or invalid member prediction")
        member["alpha"] = v["alpha"]
        members.append(member)
    all_members = pd.concat(members, ignore_index=True)
    pred = predictions(all_members, row["method"], len(row["variants"]),
                       float(sum(v["joint_weight"] for v in row["variants"])), BUDGET)
    require(len(pred) == POINTS and pred.sigma_hat.between(0, 1).all(),
            "Invalid historical aggregation")
    member_path = cell / "member_curves.csv"
    prediction_path = cell / "predictions.csv"
    frozen_csv(member_path, all_members)
    frozen_csv(prediction_path, pred)
    manifest = {"status": METHOD_STATUS, "method": row["method"],
                "cell": row["cell"], "graph_trajectories": BUDGET,
                "member_count": len(row["variants"]), "prediction_points": POINTS,
                "query_sha256": row["query_sha256"],
                "support_sha256": row["support_sha256"],
                "ledger_sha256": ledger_sha,
                "member_curves_sha256": digest(member_path),
                "predictions_sha256": digest(prediction_path),
                "whitebox_reference_read": False}
    freeze(manifest_path, manifest)
    print("B0001_SCIENCE_METHOD_CELL_FROZEN", row["method"], row["cell"], flush=True)


def verify_method(cell, row):
    m = read(cell / "prediction_manifest.json")
    require(m["status"] == METHOD_STATUS and m["method"] == row["method"] and
            m["cell"] == row["cell"] and m["graph_trajectories"] == BUDGET and
            m["member_count"] == len(row["variants"]) and
            m["prediction_points"] == POINTS and
            m["query_sha256"] == row["query_sha256"] and
            m["support_sha256"] == row["support_sha256"] and
            m["whitebox_reference_read"] is False,
            "Frozen method manifest mismatch")
    require(len(m["ledger_sha256"]) == len(row["variants"]),
            "Missing rank ledger hashes")
    for name, expected in m["ledger_sha256"].items():
        require(digest(cell / "ledgers" / name) == expected,
                "Frozen rank ledger SHA mismatch")
    for field, name in (("member_curves_sha256", "member_curves.csv"),
                        ("predictions_sha256", "predictions.csv")):
        require(digest(cell / name) == m[field], "Frozen output SHA mismatch")
    require(len(pd.read_csv(cell / "predictions.csv")) == POINTS,
            "Frozen prediction rows mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--freeze-plan", action="store_true")
    mode.add_argument("--run", action="store_true")
    for name in ("gate", "weights", "staging", "smoke", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--authorize-science-run", action="store_true")
    args = parser.parse_args()
    for name in ("gate", "weights", "staging", "smoke", "out"):
        setattr(args, name, getattr(args, name).expanduser().resolve())
    fingerprints, gate = inputs(args)
    plan = specification(args, gate, fingerprints)
    plan_file = args.out / "b0001_four_arm_science_execution_plan.json"
    print("B0001_FOUR_ARM_SCIENCE_PREFLIGHT_PASS 48 method cells; 67200 trajectories planned",
          flush=True)
    if args.check:
        if plan_file.exists():
            require(read(plan_file) == plan, "Previously frozen execution plan differs")
        print("NO_WRITES / NO_GRAPH_SIMULATIONS / NO_WHITEBOX_READ", flush=True)
        return
    if args.freeze_plan:
        require(not args.out.exists(), "Refusing to overwrite science execution workspace")
        freeze(plan_file, plan)
        print("B0001_FOUR_ARM_SCIENCE_PLAN_FROZEN_EXECUTION_BLOCKED", flush=True)
        print("FREEZE", plan_file, flush=True)
        return
    require(args.authorize_science_run,
            "Scientific execution requires explicit --authorize-science-run")
    require(args.workers >= 1, "workers must be positive")
    require(plan_file.exists() and read(plan_file) == plan,
            "A matching frozen execution plan is required")
    graph, load_contracts, graph_record, predictions = engines()
    contracts = load_contracts(P5)
    for row in plan["method_cells"]:
        execute_method(args, row, graph, contracts, graph_record, predictions)
    manifests = {}
    for row in plan["method_cells"]:
        cell = args.out / "scientific" / row["method"] / row["cell"]
        verify_method(cell, row)
        manifests[row["method"] + "/" + row["cell"]] = digest(cell / "prediction_manifest.json")
    freeze(args.out / "scientific" / "b0001_four_arm_global_prediction_freeze.json",
           {"status": GLOBAL_STATUS, "execution_plan_sha256": digest(plan_file),
            "method_cell_manifest_sha256": manifests,
            "n_method_cells": 48, "graph_trajectories": 67200,
            "whitebox_reference_read": False,
            "seven_arm_independent_confirmation_complete": False})
    print("B0001_FOUR_ARM_48_METHOD_CELLS_GRAPH_PREDICTIONS_FROZEN", flush=True)
    print("WHITEBOX_REFERENCE_UNOPENED / SEVEN_ARM_CONFIRMATION_BLOCKED", flush=True)


if __name__ == "__main__":
    main()
