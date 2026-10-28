#!/usr/bin/env python3
"""Post-result FIXED-SUPPORT Top1/Top14 battery, with frozen world-specific CV.

This is NOT a successful execution of the 99.9%-mass adaptive policy.
It reuses frozen P1/P3/P4 provider banks and selected lambda (3/5/5)
from run_pilot_m3_policy_transfer_v1.py. Top14 is fixed to 14 highest
joint-weight models; weights are normalized within Top14, and B=1400
trajectories are allocated by the pilot's original integer minimax
variance-bound rule. Top1 is independently propagated with B=1400.

No provider-local reconstruction, lambda fitting or new search is done here.
No Phase-II white-box references are read until all 12 prediction cells
have immutable manifests and the global prediction freeze has passed.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import math
from pathlib import Path

import numpy as np
import pandas as pd

import _pilot_m3_policy_transfer_core_v1 as core
import run_pilot_m3_policy_transfer_v1 as policy

HERE = Path(__file__).resolve().parent
SOURCE = core.OUT
OUT = core.P5 / "results" / "b1_fixed_cv_top1_top14_b1400_v1"
WORLDS = ("P1", "P3", "P4")
GRAPHS = ("G_PAR", "G_SEQ", "G_SEQPAR", "G_PARSEQ")
PROVIDERS = core.PROVIDERS
KEYS = core.KEYS
BUDGET = 1400
K_FIXED = 14
TOP14 = "B1_FIXED_CV_TOP14_B1400"
TOP1 = "B1_FIXED_CV_TOP1_B1400"
BASELINE = "M3_FULL343_V3B"
METHODS = ((TOP14, "top14_predictions.csv"),
           (TOP1, "top1_predictions.csv"))
CFG_PATH = core.CONFIG
CODE_PATH = Path(__file__).resolve()


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def expected_cells():
    return [core.physical_cell_id(w, g) for w in WORLDS for g in GRAPHS]


def read_frozen_inputs(cfg, world):
    """Fail closed on changed original CV, provider weights or feasibility."""
    support = SOURCE / "candidate_support" / world
    cvfile = support / "cv_selection.json"
    ffile = support / "support_feasibility.json"
    require(cvfile.is_file() and ffile.is_file(),
            f"{world}: overnight CV and feasibility checkpoints missing")
    cv = core.read_json(cvfile)
    feasibility = core.read_json(ffile)
    require(cv.get("status") == "B1_PILOT_POLICY_I1_CV_FROZEN"
            and cv.get("world") == world
            and cv.get("no_graph_whitebox_read") is True,
            f"{world}: invalid frozen CV checkpoint")
    require(feasibility.get("status") == "B1_PILOT_POLICY_SUPPORT_FEASIBILITY"
            and feasibility.get("world") == world
            and feasibility.get("no_graph_whitebox_read") is True
            and float(feasibility["target_mass"]) == 0.999
            and int(feasibility["graph_budget"]) == BUDGET
            and float(cv["selected_lambda"]) == float(feasibility["selected_lambda"]),
            f"{world}: invalid or mismatched adaptive feasibility checkpoint")
    require(not bool(feasibility["feasible"])
            and int(feasibility["top_k"]) > BUDGET,
            f"{world}: expected documented adaptive-support infeasibility")
    providers = {}
    digests = {}
    for p in PROVIDERS:
        path = SOURCE / "candidates" / world / p / "provider_weights.csv"
        manifest_path = path.parent / "provider_manifest.json"
        require(path.is_file() and manifest_path.is_file(),
                f"{world}/{p}: missing frozen provider weights")
        pm = core.read_json(manifest_path)
        digest = core.sha256_file(path)
        require(pm.get("status") == "B1_PILOT_POLICY_CV_PROVIDER_FROZEN"
                and pm.get("world") == world
                and pm.get("provider") == p
                and float(pm["selected_lambda"]) == float(cv["selected_lambda"])
                and pm["cv_selection_sha256"] == core.sha256_file(cvfile)
                and pm["weights_sha256"] == digest
                and pm["config_sha256"] == core.sha256_file(CFG_PATH)
                and pm.get("no_graph_whitebox_read") is True,
                f"{world}/{p}: provider CV weights changed")
        frame = pd.read_csv(path)
        require(len(frame) == 48
                and frame["candidate_id"].is_unique
                and np.isclose(frame["weight"].sum(), 1.0, atol=1e-10),
                f"{world}/{p}: invalid provider weight table")
        providers[p] = frame
        digests[p] = digest
    return providers, {
        "cv_selection_sha256": core.sha256_file(cvfile),
        "adaptive_feasibility_sha256": core.sha256_file(ffile),
        "provider_weights_sha256": digests,
        "selected_lambda": float(cv["selected_lambda"]),
        "adaptive_k": int(feasibility["top_k"]),
    }


def preflight(cfg):
    policy.require_reproduced_pilot_gate()
    policy.preflight(cfg)
    require(cfg["eligible_worlds"] == list(WORLDS)
            and set(cfg["graphs"]) == set(GRAPHS)
            and int(cfg["graph_budget"]) == BUDGET
            and int(cfg["top_k"]) == K_FIXED
            and float(cfg["target_mass"]) == 0.999,
            "Original pilot-policy config changed")
    require(cfg["include_matched_top1"] is True, "Top1 not enabled in pilot config")
    require(int(cfg["seed_stride"]) >= BUDGET, "Insufficient seed stride")
    require(abs(int(cfg["top1_seed_base"]) - int(cfg["top14_seed_base"])) > 14*int(cfg["seed_stride"]),
            "Top1 and Top14 seed namespaces overlap")
    for world in WORLDS:
        _, audit = read_frozen_inputs(cfg, world)
        print(f"FROZEN INPUT {world}: lambda={audit['selected_lambda']:g}, "
              f"adaptive K={audit['adaptive_k']} > B={BUDGET}; "
              "new fixed-support evaluation only", flush=True)
    print("B1_FIXED_CV_TOP1_TOP14_PREFLIGHT_PASS; no graph white-box read", flush=True)


def prepare_one(cfg, world):
    providers, audit = read_frozen_inputs(cfg, world)
    joint = core.joint_product_support(providers)
    require(len(joint) == 48 ** 3, f"{world}: incomplete joint model bank")
    require(np.isclose(joint["joint_weight"].sum(), 1.0, atol=1e-10),
            f"{world}: joint weights do not sum to one")
    top = joint.iloc[:K_FIXED].copy()
    retained = float(top["joint_weight"].sum())
    require(0 < retained <= 1, f"{world}: invalid retained mass")
    top["alpha"] = top["joint_weight"] / retained
    top["n_trajectories"] = core.allocation(top["alpha"].to_numpy(float), BUDGET)
    top["seed_start"] = [int(cfg["top14_seed_base"]) + i * int(cfg["seed_stride"])
                         for i in range(K_FIXED)]
    top["seed_end_inclusive"] = top["seed_start"] + top["n_trajectories"] - 1
    top["retained_mass"] = retained
    top["omitted_mass"] = 1.0-retained
    require(int(top["n_trajectories"].sum()) == BUDGET
            and (top["n_trajectories"] >= 1).all(),
            f"{world}: fixed Top14 allocation failed")
    root = OUT / "support" / world
    root.mkdir(parents=True, exist_ok=True)
    path = root / "top14_support.csv"
    policy.freeze_csv(path, top)
    manifest = {
        "status": "B1_FIXED_CV_TOP14_SUPPORT_FROZEN",
        "world": world, "top_k": K_FIXED, "graph_budget": BUDGET,
        "retained_mass": retained, "omitted_mass": 1-retained,
        "selected_lambda": audit["selected_lambda"],
        "adaptive_k_infeasible": audit["adaptive_k"],
        "support_sha256": core.sha256_file(path),
        "pilot_config_sha256": core.sha256_file(CFG_PATH),
        "source_code_sha256": core.sha256_file(CODE_PATH),
        "core_code_sha256": core.sha256_file(Path(core.__file__)),
        **{k: v for k, v in audit.items() if k.endswith("_sha256")},
        "reference_whitebox_read": False,
        "not_adaptive_99_9_percent_support": True,
    }
    policy.freeze_json(root/"support_manifest.json", manifest)
    print(f"FROZEN FIXED {world}: lambda={audit['selected_lambda']:g}, "
          f"Top14 mass={retained:.9f}, omitted={1-retained:.9f}, "
          f"B={BUDGET}, original adaptive K={audit['adaptive_k']}", flush=True)


def load_support(cfg, world):
    providers, audit = read_frozen_inputs(cfg, world)
    root = OUT / "support" / world
    path, mp = root/"top14_support.csv", root/"support_manifest.json"
    require(path.is_file() and mp.is_file(), f"{world}: run prepare first")
    m = core.read_json(mp)
    require(m.get("status") == "B1_FIXED_CV_TOP14_SUPPORT_FROZEN"
            and m.get("world") == world and m["top_k"] == K_FIXED
            and m["graph_budget"] == BUDGET
            and m["support_sha256"] == core.sha256_file(path)
            and m["pilot_config_sha256"] == core.sha256_file(CFG_PATH)
            and m["source_code_sha256"] == core.sha256_file(CODE_PATH)
            and m["core_code_sha256"] == core.sha256_file(Path(core.__file__))
            and m["cv_selection_sha256"] == audit["cv_selection_sha256"]
            and m["adaptive_feasibility_sha256"] == audit["adaptive_feasibility_sha256"]
            and m["provider_weights_sha256"] == audit["provider_weights_sha256"]
            and m.get("reference_whitebox_read") is False,
            f"{world}: fixed-support manifest mismatch")
    top = pd.read_csv(path)
    require(len(top) == K_FIXED
            and top["joint_rank"].astype(int).tolist() == list(range(1, K_FIXED+1))
            and int(top["n_trajectories"].sum()) == BUDGET
            and np.isclose(top["alpha"].sum(), 1.0, atol=1e-12)
            and float(top["retained_mass"].iloc[0]) < 0.999,
            f"{world}: unexpected fixed Top14 support")
    return providers, top, m


def verify_cell(cfg, cell):
    world, _ = cell.split("__", 1)
    _, _, support = load_support(cfg, world)
    root = OUT / "predictions" / cell
    mp = root / "prediction_manifest.json"
    require(mp.is_file(), f"Missing predicted cell {cell}")
    m = core.read_json(mp)
    require(m.get("status") == "B1_FIXED_CV_CELL_PREDICTED"
            and m["cell"] == cell
            and m["support_manifest_sha256"] == core.sha256_file(
                OUT/"support"/world/"support_manifest.json")
            and m["config_sha256"] == core.sha256_file(CFG_PATH)
            and m["code_sha256"] == core.sha256_file(CODE_PATH)
            and m.get("reference_whitebox_read") is False,
            f"{cell}: invalid predicted-cell manifest")
    for name, digest in m["outputs_sha256"].items():
        require(core.sha256_file(root/name) == digest, f"{cell}: edited output {name}")
    for method, name in METHODS:
        df = pd.read_csv(root/name)
        require(len(df) == 15*49 and df["method_id"].nunique() == 1
                and str(df["method_id"].iloc[0]) == method
                and not df.duplicated(KEYS).any()
                and int(df["graph_budget"].iloc[0]) == BUDGET,
                f"{cell}/{method}: invalid frozen prediction grid")
    return m


def run_cell(cfg, contracts, cell, workers):
    world, graph_id = cell.split("__", 1)
    providers, top, support = load_support(cfg, world)
    root = OUT/"predictions"/cell
    marker = root/"prediction_manifest.json"
    if marker.is_file():
        verify_cell(cfg, cell)
        print(f"REUSED FROZEN {cell}", flush=True)
        return
    root.mkdir(parents=True, exist_ok=True)
    graph = core.graph_record(contracts, graph_id)
    q = core._query_definitions(cell)
    horizons = core._horizons(core.read_json(
        core.P5/"config_phase5_graph_prediction_v3b_fullsupport.json"))
    lookups = {
        p: {str(r.candidate_id): core._surrogate(pd.Series({
            "mean_service_time": r.mean_service_time,
            "cost_rate": r.cost_rate, "service_cv": r.service_cv,
        })) for r in providers[p].itertuples(index=False)}
        for p in PROVIDERS
    }
    payloads = []
    specs = []
    for r in top.itertuples(index=False):
        rank = int(r.joint_rank)
        ids = {p: str(getattr(r, f"{p}_candidate_id")) for p in PROVIDERS}
        variant = f"FIXED_CV_TOP14_R{rank:02d}"
        ledger = root/"ledgers"/(variant+".csv")
        seeds = list(range(int(r.seed_start), int(r.seed_end_inclusive)+1))
        payloads.append(core._simulation_payload(
            cell_root=root, graph_id=graph_id, graph_ast=graph["ast"],
            variant_id=variant,
            surrogates={p: lookups[p][ids[p]] for p in PROVIDERS},
            seeds=seeds, ledger_path=ledger, contracts=contracts))
        specs.append((rank, ids, ledger, seeds, float(r.alpha), float(r.joint_weight)))
    core._execute_balanced_graph_jobs(payloads, workers, f"{cell} FIXED_CV_TOP14")
    pieces = []
    for rank, ids, ledger, seeds, alpha, weight in specs:
        part = core._member_curves(
            ledger=core._validate_complete_ledger(ledger, seeds),
            queries=q, horizons=horizons, method_id=TOP14,
            rank=rank, graph_n=len(seeds), joint_weight=weight, candidate_ids=ids)
        part["alpha"] = alpha
        pieces.append(part)
    members = pd.concat(pieces, ignore_index=True)
    policy.freeze_csv(root/"top14_member_curves.csv", members)
    p14 = core.predictions(members, TOP14, K_FIXED,
                           float(top["retained_mass"].iloc[0]), BUDGET)
    policy.freeze_csv(root/"top14_predictions.csv", p14)
    print(f"{cell}: frozen Top14 graph predictions; starting separate Top1", flush=True)

    first = top.iloc[0]
    ids = {p: str(first[f"{p}_candidate_id"]) for p in PROVIDERS}
    variant = "FIXED_CV_TOP1_B1400"
    ledger = root/"ledgers"/(variant+".csv")
    seeds = list(range(int(cfg["top1_seed_base"]),
                       int(cfg["top1_seed_base"])+BUDGET))
    payload = core._simulation_payload(
        cell_root=root, graph_id=graph_id, graph_ast=graph["ast"],
        variant_id=variant,
        surrogates={p: lookups[p][ids[p]] for p in PROVIDERS},
        seeds=seeds, ledger_path=ledger, contracts=contracts)
    core._execute_balanced_graph_jobs([payload], workers, f"{cell} FIXED_CV_TOP1")
    t1 = core._member_curves(
        ledger=core._validate_complete_ledger(ledger, seeds),
        queries=q, horizons=horizons, method_id=TOP1,
        rank=1, graph_n=BUDGET, joint_weight=1.0, candidate_ids=ids)
    t1["alpha"] = 1.0
    p1 = core.predictions(t1, TOP1, 1, 1.0, BUDGET)
    policy.freeze_csv(root/"top1_predictions.csv", p1)

    names = ("top14_member_curves.csv", "top14_predictions.csv", "top1_predictions.csv")
    policy.freeze_json(marker, {
        "status": "B1_FIXED_CV_CELL_PREDICTED",
        "cell": cell, "graph_budget_per_method": BUDGET,
        "methods": [TOP14, TOP1],
        "support_manifest_sha256": core.sha256_file(
            OUT/"support"/world/"support_manifest.json"),
        "config_sha256": core.sha256_file(CFG_PATH),
        "code_sha256": core.sha256_file(CODE_PATH),
        "outputs_sha256": {name: core.sha256_file(root/name) for name in names},
        "reference_whitebox_read": False,
    })
    verify_cell(cfg, cell)
    print(f"PREDICTED AND FROZEN {cell}: 735 grid points per method, "
          "no white-box reference read", flush=True)


def freeze_all(cfg):
    records = []
    for cell in expected_cells():
        verify_cell(cfg, cell)
        p = OUT/"predictions"/cell/"prediction_manifest.json"
        records.append({"cell": cell, "manifest_sha256": core.sha256_file(p)})
    policy.freeze_json(OUT/"global_prediction_freeze.json", {
        "status": "B1_FIXED_CV_ALL_12_PREDICTIONS_FROZEN",
        "scope": "12 eligible Phase-II cells; Top1 and Top14 each B1400",
        "cells": records, "methods": [TOP14, TOP1],
        "config_sha256": core.sha256_file(CFG_PATH),
        "code_sha256": core.sha256_file(CODE_PATH),
        "reference_whitebox_read": False,
    })
    print("B1_FIXED_CV_ALL_12_PREDICTIONS_FROZEN; no white-box reference read", flush=True)


def evaluate(cfg):
    # Nothing below this line opens white-box data unless every frozen
    # prediction file, source hash and global manifest has been verified.
    freeze_all(cfg)
    frames = []
    for cell in expected_cells():
        root = OUT/"predictions"/cell
        wbpath = core.WB_ROOT/cell/"final_wb_curves.csv"
        basepath = core.BASELINE_ROOT/cell/"m3_predictions_full343_and_nested.csv"
        require(wbpath.is_file() and basepath.is_file(),
                f"{cell}: missing Phase-II reference/comparator")
        wb = pd.read_csv(wbpath)
        full = pd.read_csv(basepath)
        full = full.loc[full["method_id"].eq("M3_FULL343")].copy()
        for method, filename in list(METHODS)+[(BASELINE, None)]:
            p = full if filename is None else pd.read_csv(root/filename)
            pe = p.loc[p["H"].between(60, 240), KEYS+["sigma_hat"]]
            we = wb.loc[wb["H"].between(60, 240), KEYS+["sigma_wb"]]
            require(len(pe) == len(we) == 555 and not pe.duplicated(KEYS).any()
                    and not we.duplicated(KEYS).any(),
                    f"{cell}/{method}: duplicate or incomplete scoring keys")
            joined = pe.merge(we, on=KEYS, validate="one_to_one")
            require(len(joined) == 555, f"{cell}/{method}: scoring key mismatch")
            joined["cell"] = cell
            joined["method"] = method
            joined["error"] = joined["sigma_hat"]-joined["sigma_wb"]
            frames.append(joined)
    results = pd.concat(frames, ignore_index=True)
    require(len(results) == 12*555*3, "Expected 19,980 scored prediction queries")
    metrics = []
    for method, group in results.groupby("method"):
        groups = [("all_12_cells", "ALL", group)]
        groups += [("cell", key, g) for key, g in group.groupby("cell")]
        groups += [("provider_world", key, g)
                   for key, g in group.groupby("provider_world_id")]
        groups += [("composition_graph", key, g)
                   for key, g in group.groupby("graph_id")]
        for scope, cell, g in groups:
            e = g["error"].to_numpy(dtype=float)
            metrics.append({
                "scope": scope, "method": method, "cell": cell,
                "n_points": len(e), "mae": float(np.mean(np.abs(e))),
                "rmse": float(np.sqrt(np.mean(e*e))),
                "bias": float(np.mean(e)),
            })
    metrics = pd.DataFrame(metrics)
    require(metrics.query("scope == 'all_12_cells'")["n_points"].eq(6660).all(),
            "Unexpected aggregate query count")
    folder = OUT/"evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    policy.freeze_csv(folder/"pointwise_errors.csv", results)
    policy.freeze_csv(folder/"metrics.csv", metrics)
    policy.freeze_json(folder/"evaluation_manifest.json", {
        "status": "B1_FIXED_CV_12_CELL_EVALUATION_COMPLETE",
        "global_freeze_sha256": core.sha256_file(
            OUT/"global_prediction_freeze.json"),
        "n_cells": 12, "n_points_per_method": 6660,
        "note": "Retrospective same-reference evaluation, not new holdout; "
                "Top14 fixed support does not meet adaptive 99.9% criterion.",
        "metrics_sha256": core.sha256_file(folder/"metrics.csv"),
        "pointwise_sha256": core.sha256_file(folder/"pointwise_errors.csv"),
    })
    print("\n12-CELL FIXED-SUPPORT RESULTS (same Phase-II WB reference)", flush=True)
    print(metrics.loc[metrics["scope"] == "all_12_cells"].to_string(index=False), flush=True)
    print(f"Evaluation files: {folder}", flush=True)


@contextlib.contextmanager
def execution_lock():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/".runner.lock").open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another fixed-support runner is active") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True,
                    choices=["preflight", "prepare", "predict", "freeze", "evaluate", "all"])
    ap.add_argument("--cell", choices=expected_cells(),
                    help="With --stage predict, one eligible world/graph cell")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    require(1 <= args.workers <= 16, "--workers must be between 1 and 16")
    require(args.cell is None or args.stage == "predict",
            "--cell applies only to --stage predict")
    cfg, contracts = policy.configuration()
    with execution_lock():
        preflight(cfg)
        if args.stage in ("prepare", "all"):
            for w in WORLDS:
                prepare_one(cfg, w)
        if args.stage in ("predict", "all"):
            cells = [args.cell] if args.cell else expected_cells()
            for idx, cell in enumerate(cells, 1):
                print(f"\n=== FIXED CV {idx}/{len(cells)}: {cell} ===", flush=True)
                run_cell(cfg, contracts, cell, args.workers)
        if args.stage in ("freeze", "all"):
            freeze_all(cfg)
        if args.stage in ("evaluate", "all"):
            evaluate(cfg)
    print(f"\nB1_FIXED_CV_TOP1_TOP14_STAGE_{args.stage.upper()}_PASS", flush=True)


if __name__ == "__main__":
    main()
