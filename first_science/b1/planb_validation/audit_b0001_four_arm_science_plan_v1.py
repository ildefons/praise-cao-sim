#!/usr/bin/env python3
"""Independent, blind read-only audit of the frozen B0001 four-arm science plan.

--check reads frozen public-only inputs and code; never imports the simulator.
--freeze writes ONLY an audit attestation into a fresh separate --out directory.
Neither mode launches graph simulations or opens the white-box reference.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FAMILIES = ("original", "fixed_cv")
WORLDS = ("P1", "P3", "P4")
GRAPHS = ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
METHODS = {"original": ("ORIGINAL_TOP14_B1400", "ORIGINAL_TOP1_B1400"),
           "fixed_cv": ("FIXED_CV_TOP14", "FIXED_CV_TOP1")}
PLAN_STATUS = "B0001_FOUR_ARM_48_CELL_SCIENCE_PLAN_FROZEN_EXECUTION_BLOCKED"
GATE_STATUS = "B0001_FOUR_ARM_GRAPH_ISOLATION_PREFLIGHT_FROZEN_EXECUTION_BLOCKED"
AUDIT_STATUS = "B0001_FOUR_ARM_SCIENCE_PLAN_INDEPENDENT_AUDIT_PASS_EXECUTION_BLOCKED"
RUNNER = "first_science/b1/planb_validation/run_b0001_four_arm_graph_science_v1.py"
ENGINE = "first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py"


def require(ok, why):
    if not bool(ok):
        raise RuntimeError("B0001 INDEPENDENT GRAPH PLAN AUDIT: " + why)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def historical_allocation(alpha, budget=1400):
    """Independently implement archived greedy minimax integer allocation."""
    alpha = np.asarray(alpha, dtype=float)
    require(len(alpha) == 14 and np.isclose(alpha.sum(), 1, atol=1e-12),
            "Malformed allocation weights")
    n = np.ones(len(alpha), dtype=int)
    for _ in range(budget - len(n)):
        j = int(np.argmax(alpha ** 2 / (n * (n + 1))))
        n[j] += 1
    return n.tolist()


def audit_code():
    """Static restart/firewall assertions; no execution of scientific code."""
    source = (REPO / RUNNER).read_text(encoding="utf-8")
    engine = (REPO / ENGINE).read_text(encoding="utf-8")
    runner_ast = ast.parse(source)
    engine_ast = ast.parse(engine)
    funcs = {node.name: node for node in runner_ast.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    sim = {node.name: node for node in engine_ast.body
           if isinstance(node, ast.FunctionDef)}
    for name in ("inputs", "specification", "execute_method", "verify_method",
                 "frozen_csv", "freeze", "main"):
        require(name in funcs, "Missing runner safety stage: " + name)
    for name in ("_simulation_payload", "_simulate_variant_worker",
                 "_validate_complete_ledger", "_member_curves", "_execute_payloads"):
        require(name in sim, "Missing frozen graph engine stage: " + name)
    method = ast.get_source_segment(source, funcs["execute_method"]) or ""
    check = ast.get_source_segment(source, funcs["main"]) or ""
    save_csv = ast.get_source_segment(source, funcs["frozen_csv"]) or ""
    verify = ast.get_source_segment(source, funcs["verify_method"]) or ""
    worker = ast.get_source_segment(engine, sim["_simulate_variant_worker"]) or ""
    require("if args.check:" in check and
            check.index("if args.check:") < check.index("engines()") and
            "require(args.authorize_science_run" in check and
            "read(plan_file) == plan" in check,
            "Read-only mode, explicit execution approval or frozen plan guard missing")
    require("if manifest_path.exists():" in method and
            "verify_method(cell, row)" in method and
            "graph._validate_complete_ledger(path, seeds)" in method and
            "graph._execute_payloads(payloads" in method,
            "Runner restart or complete ledger verification path missing")
    require("if path.exists():" in save_csv and
            "path.read_bytes() == expected" in save_csv and
            "temporary.replace(path)" in save_csv,
            "Frozen CSV immutability/restart contract missing")
    require("digest(cell / name) == m[field]" in verify and
            "digest(cell / \"ledgers\" / name) == expected" in verify,
            "Frozen prediction or rank ledger SHA verification missing")
    require("if ledger_path.is_file():" in worker and
            "_validate_complete_ledger(ledger_path,seeds)" in worker and
            "if cp.is_file():" in worker and
            "tmp.replace(cp)" in worker and
            "tmp.replace(ledger_path)" in worker,
            "Historical graph engine checkpoint/restart contract changed")
    forbid = ("final_wb", "whitebox_reference", "reference_audit", "wb_isolated")
    # Files may document the firewall, so check imported module identifiers,
    # not incidental comments or manifest Boolean fields.
    imported = []
    for node in ast.walk(runner_ast):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append((node.module or "").lower())
    require(not any(term in name for name in imported for term in forbid),
            "Scientific runner imports forbidden WB/reference module")
    return {"runner_sha256": digest(REPO / RUNNER),
            "historical_graph_engine_sha256": digest(REPO / ENGINE),
            "restart_safeguards_verified_statically": True,
            "restart_dynamically_tested_by_this_audit": False}


def audit(a):
    for name in ("plan", "gate", "weights", "staging"):
        require(getattr(a, name).is_dir(), "Missing frozen directory: " + name)
        require(a.out != getattr(a, name) and
                getattr(a, name) not in a.out.parents and
                a.out not in getattr(a, name).parents,
                "Audit output overlaps frozen science source")
    require(a.out != REPO and REPO not in a.out.parents,
            "Audit output must be separate from repository")
    plan_path = a.plan / "b0001_four_arm_science_execution_plan.json"
    gate_path = a.gate / "b0001_four_arm_graph_isolation_preflight.json"
    weight_path = a.weights / "b0001_48_lhs_weight_and_support_freeze.json"
    stage_path = a.staging / "b0001_public_inputs_manifest.json"
    plan, gate, weights, stage = map(read, (plan_path, gate_path, weight_path, stage_path))
    require(plan["status"] == PLAN_STATUS and gate["status"] == GATE_STATUS and
            plan["scientific_graph_execution_authorized"] is False and
            plan["graph_simulations_executed"] == 0 and
            plan["whitebox_reference_read"] is False and
            gate["scientific_graph_execution_authorized"] is False,
            "Frozen execution boundary changed")
    require(plan["input_sha256"]["gate"] == digest(gate_path) and
            plan["input_sha256"]["weights"] == digest(weight_path) and
            plan["input_sha256"]["staging"] == digest(stage_path) and
            gate["weight_freeze_sha256"] == digest(weight_path) and
            gate["public_input_freeze_sha256"] == digest(stage_path),
            "Plan/gate public-input fingerprint drift")
    require(weights["status"] == "B0001_48_LHS_TWO_FAMILY_WEIGHTS_AND_TOP14_SUPPORT_FROZEN" and
            weights["whitebox_reference_opened"] is False and
            stage["hidden_world_parameters_copied"] is False and
            stage["calibration_or_confirmation_values_copied"] is False,
            "Public-only provenance invalid")
    query_hashes = {entry["path"]: entry["staged_sha256"]
                    for entry in stage["staged_files"]}
    rows = plan["method_cells"]
    require(plan["method_cell_count"] == len(rows) == 48 and
            plan["nominal_graph_trajectories"] == 67200,
            "Incorrect 48-cell experiment budget")
    expected_keys = {(f, w, g, kind) for f in FAMILIES for w in WORLDS
                     for g in GRAPHS for kind in ("top14", "top1")}
    observed = {(r["family"], r["world"], r["graph"], r["kind"]) for r in rows}
    require(len(observed) == 48 and observed == expected_keys,
            "Duplicate/missing method-condition cell")
    bank_map = {}
    seed_by_method = {}
    total = 0
    allocations = 0
    for row in rows:
        family, world, graph, kind = (row[k] for k in ("family", "world", "graph", "kind"))
        require(row["cell"] == world + "__" + graph and
                row["method"] == METHODS[family][0 if kind == "top14" else 1],
                "Wrong method-condition mapping")
        query_rel = f"frozen_queries/{world}__{graph}/step0_frozen_queries.csv"
        require(row["query_sha256"] == query_hashes[query_rel] ==
                digest(a.staging / query_rel),
                "Query provenance differs from original public freeze")
        worldmeta = gate["world_supports_and_fresh_graph_seeds"][family + "/" + world]
        support_path = a.weights / family / world / "support" / "top14_support.csv"
        support = pd.read_csv(support_path)
        require(row["support_sha256"] == worldmeta["top14_support_sha256"] ==
                digest(support_path), "Top14 support provenance mismatch")
        require(len(support) == 14 and
                support.joint_rank.astype(int).tolist() == list(range(1, 15)),
                "Incorrect frozen support rank ordering")
        expected_n = historical_allocation(support.alpha.astype(float).to_numpy())
        require(expected_n == support.n_trajectories.astype(int).tolist(),
                "Frozen Top14 allocation disagrees with historical minimax rule")
        providers = {}
        manifest_path = a.weights / family / world / "support" / "world_support_manifest.json"
        require(digest(manifest_path) == worldmeta["support_manifest_sha256"] ==
                weights["world_supports"][family + "/" + world]["world_support_manifest_sha256"],
                "Frozen world support manifest hash mismatch")
        manifest = read(manifest_path)
        for p in PROVIDERS:
            ppath = a.weights / family / world / p / "provider_weights.csv"
            require(digest(ppath) == manifest["provider_weight_sha256"][p],
                    "Frozen provider weights changed: " + family + "/" + world + "/" + p)
            table = pd.read_csv(ppath)
            require(len(table) == 48 and table.candidate_id.nunique() == 48,
                    "Provider candidate bank malformed")
            providers[p] = table.set_index("candidate_id")
        variants = row["variants"]
        require(len(variants) == (14 if kind == "top14" else 1),
                "Incorrect Top14/Top1 number of members")
        alpha_sum = 0.0
        for i, variant in enumerate(variants):
            parent = support.iloc[i]
            rank = int(parent.joint_rank)
            n = expected_n[i] if kind == "top14" else 1400
            if kind == "top14":
                block = worldmeta["top14_rank_seed_blocks"][i]
                lo, hi = int(block["seed_start"]), int(block["seed_end_inclusive"])
                require(block["joint_rank"] == rank and block["n_trajectories"] == n,
                        "Seed registry allocation mismatch")
            else:
                lo, hi = (int(worldmeta["top1_seed_start"]),
                          int(worldmeta["top1_seed_end_inclusive"]))
            require(variant["rank"] == rank and variant["n"] == n and
                    variant["seed_start"] == lo and variant["seed_end"] == hi and
                    hi - lo + 1 == n,
                    "Candidate allocation/seed interval mismatch")
            expected_alpha = float(parent.alpha) if kind == "top14" else 1.0
            require(np.isclose(variant["alpha"], expected_alpha, atol=1e-14, rtol=0) and
                    np.isclose(variant["joint_weight"], float(parent.joint_weight),
                               atol=1e-14, rtol=0),
                    "Incorrect Top14 renormalization/Top1 identity")
            alpha_sum += variant["alpha"]
            joint = 1.0
            for p in PROVIDERS:
                candidate = str(parent[p + "_candidate_id"])
                require(variant["candidate_ids"][p] == candidate and
                        candidate in providers[p].index,
                        "Provider candidate identity changed")
                source = providers[p].loc[candidate]
                joint *= float(source["weight"])
                for parameter in ("mean_service_time", "cost_rate", "service_cv"):
                    require(float(variant["surrogates"][p][parameter]) == float(source[parameter]),
                            "Frozen physical surrogate parameter mismatch: " + parameter)
            require(np.isclose(joint, variant["joint_weight"], atol=1e-14, rtol=1e-12),
                    "Joint weight disagrees with product of provider weights")
            interval = (lo, hi)
            tag = (family, kind, rank)
            if tag in bank_map:
                if world in bank_map[tag]:
                    require(bank_map[tag][world] == interval,
                            "Seed interval changed across graphs in same world")
                bank_map[tag][world] = interval
            else:
                bank_map[tag] = {world: interval}
            seed_by_method.setdefault((family, kind), set()).update(range(lo, hi + 1))
            total += n
            allocations += 1
        require(np.isclose(alpha_sum, 1, atol=1e-12) and
                sum(v["n"] for v in variants) == 1400,
                "Aggregation normalization or method budget mismatch")
    require(total == 67200 and allocations == 360,
            "Graph trajectory or rank-allocation count mismatch")
    methods = list(seed_by_method)
    for i, m1 in enumerate(methods):
        for m2 in methods[i + 1:]:
            require(seed_by_method[m1].isdisjoint(seed_by_method[m2]),
                    "Scientific RNG namespace collision between methods")
    for tag, worlds in bank_map.items():
        require(len(worlds) == 3 and
                len({lo for lo, _ in worlds.values()}) == 1,
                "CRN seed block start unexpectedly differs across worlds")
        # Top14 allocations may vary by world: CRN reuse is a shared seed
        # prefix, not an assertion that all worlds use equal trajectory counts.
    require(len(bank_map) == 30, "Unexpected independent seed rank-bank count")
    code_audit = audit_code()
    return {"status": AUDIT_STATUS, "source_plan_sha256": digest(plan_path),
            "source_gate_sha256": digest(gate_path),
            "source_weights_sha256": digest(weight_path),
            "source_staging_sha256": digest(stage_path),
            "method_cells_verified": 48, "rank_allocations_verified": allocations,
            "graph_trajectories_planned": total, "independent_seed_banks": len(bank_map),
            "method_seed_sets_disjoint": True,
            "world_and_graph_CRN_reuse_as_frozen": True,
            "candidate_parameters_match_frozen_provider_weights": True,
            "top14_minimax_allocation_recomputed": True,
            "top1_identity_and_top14_normalization_verified": True,
            "code_safety_audit": code_audit,
            "graph_simulations_executed": 0,
            "whitebox_reference_read": False,
            "scientific_graph_execution_authorized": False,
            "caveat": "Restart behavior checked statically; no interruption/restart simulation was performed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("plan", "gate", "weights", "staging", "out"):
        parser.add_argument("--" + key, required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--freeze", action="store_true")
    a = parser.parse_args()
    for key in ("plan", "gate", "weights", "staging", "out"):
        setattr(a, key, getattr(a, key).expanduser().resolve())
    result = audit(a)
    print("B0001_FOUR_ARM_SCIENCE_INDEPENDENT_AUDIT_CHECK_PASS",
          "48 cells; 360 rank allocations; 67200 trajectories; 30 CRN banks", flush=True)
    print("RESTART_STATIC_CHECK_PASS / NO_GRAPH_SIMULATIONS / NO_WHITEBOX_READ", flush=True)
    if a.check:
        print("NO_WRITES / SCIENCE_EXECUTION_BLOCKED", flush=True)
        return
    require(not a.out.exists(), "Refusing to overwrite independent audit workspace")
    a.out.mkdir(parents=True)
    dest = a.out / "b0001_four_arm_science_plan_independent_audit.json"
    dest.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("B0001_FOUR_ARM_SCIENCE_INDEPENDENT_AUDIT_FROZEN_EXECUTION_BLOCKED", flush=True)
    print("FREEZE", dest, flush=True)


if __name__ == "__main__":
    main()
