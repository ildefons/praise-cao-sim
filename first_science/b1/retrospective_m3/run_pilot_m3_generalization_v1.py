#!/usr/bin/env python3
"""Retrospective, isolated Phase-5 transfer test for the original-style I1/M3 method.

This is a NEW method instantiation and an exploratory, not confirmatory, comparison.
The original Phase-4 pilot records and Phase-5 V3b/FULL343 records are immutable.

Stages are deliberately separated. prepare/predict do not load graph white-box
outcomes. evaluate is disabled until the complete 12-cell prediction freeze exists.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent.parent
P5 = FIRST / "phase5"
P4 = FIRST / "phase4"
for directory in (P5, P4):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from m2_a2_nonadaptive_coverage import _latin_hypercube, _map_unit_to_parameters
from phase5_runtime_v2 import (
    graph_record, load_phase5_contracts, physical_cell_id,
    read_json, sha256_file, utc_now_iso, write_json,
)
from phase5_reconstruction_v3_selection import gibbs_weights, joint_product_support
from run_phase5_m2_reconstruction_v2 import _load_public_card, _domain_row, _bounds
from run_phase5_graph_prediction_v3b_fullsupport import (
    _execute_payloads, _horizons, _member_curves, _query_definitions,
    _simulation_payload, _surrogate, _validate_complete_ledger,
)
from run_m1_provider_lift_v2 import _simulate_and_score

CONFIG = HERE / "config_pilot_m3_generalization_v1.json"
OUT = P5 / "results" / "b1_pilot_m3_retrospective_v1"
STEP0 = P5 / "results" / "02_step0"
WB_ROOT = P5 / "results" / "05_final_wb_v3b_fullsupport"
BASELINE_ROOT = P5 / "results" / "04_prediction_v3b_fullsupport"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
KEYS = ["query_id", "provider_world_id", "graph_id", "rho_label", "rho", "regime", "H"]


def configuration():
    cfg = read_json(CONFIG)
    if cfg.get("status") != "B1_RETROSPECTIVE_M3_V1_DESIGN_FROZEN":
        raise RuntimeError("Unexpected retrospective design status")
    contracts = load_phase5_contracts(P5)
    m2 = contracts.methods["M2"]["nonadaptive_LHS"]
    m3 = contracts.methods["M3"]
    s = contracts.seeds["provider_reconstruction"]["M3_fresh_local_rescore_CRN"]
    assert int(m2["n_points_per_provider"]) == 48
    assert int(cfg["n_candidates_per_provider"]) == 48
    assert int(cfg["top_k"]) == int(m3["graph_support"]["rank_count"]) == 14
    assert int(cfg["graph_budget"]) == int(m3["graph_support"]["production_budget"]) == 1400
    assert float(cfg["lambda"]) == float(m3["gibbs_lambda"]) == 30.0
    assert int(cfg["lhs_seed"]) == int(m2["seed"])
    assert int(cfg["local_rescore_start"]) == int(s["start"])
    assert int(cfg["local_rescore_n"]) == int(s["n"]) == 100
    assert cfg["eligible_worlds"] == ["P1", "P3", "P4"]
    assert cfg["graphs"] == ["G_PAR", "G_SEQ", "G_SEQPAR", "G_PARSEQ"]
    if cfg["top14_seed_base"] < 8000000 or cfg["top1_seed_base"] < 8000000:
        raise RuntimeError("Retrospective seeds must not overlap historical science banks")
    if abs(int(cfg["top14_seed_base"]) - int(cfg["top1_seed_base"])) < 140000:
        raise RuntimeError("Top1 and Top14 seed namespaces must be disjoint")
    if int(cfg["seed_stride"]) < int(cfg["graph_budget"]):
        raise RuntimeError("Insufficient rank-specific seed stride")
    return cfg, contracts


def eligible_cells(cfg):
    path = STEP0 / "phase5_step0_eligibility.csv"
    t = pd.read_csv(path)
    t = t[t["eligibility"].astype(str) == "ELIGIBLE"].copy()
    t = t.sort_values(["provider_world_id", "graph_id"], kind="mergesort")
    actual = set(t["physical_cell_id"].astype(str))
    expected = {
        physical_cell_id(w, g) for w in cfg["eligible_worlds"] for g in cfg["graphs"]
    }
    if len(t) != 12 or actual != expected:
        raise RuntimeError("The historical 12-cell eligibility set has changed")
    return t


def preflight(cfg):
    eligible_cells(cfg)
    for w in cfg["eligible_worlds"]:
        for provider in PROVIDERS:
            _domain_row(w, provider)
            _load_public_card(w, provider)
    for w in cfg["eligible_worlds"]:
        for g in cfg["graphs"]:
            _query_definitions(physical_cell_id(w, g))
    print("B1_PILOT_M3_RETROSPECTIVE_PREFLIGHT_PASS")
    print("12 historical eligible cells; frozen I1, Step-0 queries and reconstruction domains accessible")
    print("No white-box reference was opened")


def allocation(weights, budget):
    """Original greedy minimax bound allocation, deterministic lower-rank tie break."""
    a = np.asarray(weights, dtype=float)
    if a.ndim != 1 or len(a) == 0 or budget < len(a):
        raise ValueError("Invalid support size or graph budget")
    if np.any(a < 0) or not np.isfinite(a).all() or not np.isclose(a.sum(), 1):
        raise ValueError("Invalid normalized weights")
    n = np.ones(len(a), dtype=int)
    for _ in range(budget - len(a)):
        n[int(np.argmax(a * a / (n * (n + 1))))] += 1
    assert int(n.sum()) == budget
    return n


def candidate_design(cfg, world, provider):
    b = _bounds(_domain_row(world, provider))
    unit = _latin_hypercube(
        48, 3, cfg["lhs_seed"] + PROVIDERS.index(provider) * 100003
    )
    t = _map_unit_to_parameters(unit, b)
    t.insert(0, "candidate_id", [
        f"{world}_{provider}_LHS_{i:03d}" for i in range(48)
    ])
    return t


def prepare_provider(cfg, world, provider):
    """The same frozen Phase-5 48-point LHS design, freshly scored on public I1."""
    base = OUT / "candidates" / world / provider
    base.mkdir(parents=True, exist_ok=True)
    design = candidate_design(cfg, world, provider)
    design_file = base / "lhs_design.csv"
    if design_file.exists():
        old = pd.read_csv(design_file)
        if not old["candidate_id"].astype(str).equals(design["candidate_id"].astype(str)):
            raise RuntimeError("Frozen LHS candidate IDs differ")
        if not np.allclose(old[["mean_service_time", "cost_rate", "service_cv"]],
                           design[["mean_service_time", "cost_rate", "service_cv"]],
                           rtol=1e-12, atol=1e-12):
            raise RuntimeError("Frozen LHS candidate parameters differ")
    else:
        design.to_csv(design_file, index=False)

    metadata, public, record = _load_public_card(world, provider)
    seeds = list(range(cfg["local_rescore_start"],
                       cfg["local_rescore_start"] + cfg["local_rescore_n"]))
    scores = []
    surfaces = []
    public_vector = None
    for i, row in enumerate(design.itertuples(index=False), start=1):
        cid = str(row.candidate_id)
        curve_file = base / "surfaces" / (cid + ".csv")
        if curve_file.is_file():
            curve = pd.read_csv(curve_file)
            if not np.isfinite(curve["sigma_m1_local"].to_numpy(dtype=float)).all():
                raise RuntimeError(f"Corrupt cached candidate surface {cid}")
        else:
            metrics, _simulated, comparison = _simulate_and_score(
                metadata=metadata, public_surface=public,
                mean_service_time=float(row.mean_service_time),
                cost_rate=float(row.cost_rate),
                service_cv=float(row.service_cv),
                trajectory_seeds=seeds, canonical_ipt=1000000.0,
                execution_fraction=0.5, quiet=True,
            )
            curve = comparison[["sigma_i1", "sigma_m1_local"]].copy()
            curve.insert(0, "point_index", range(len(curve)))
            curve_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = curve_file.with_suffix(".tmp")
            curve.to_csv(tmp, index=False)
            tmp.replace(curve_file)
        if not {"point_index", "sigma_i1", "sigma_m1_local"}.issubset(curve.columns):
            raise RuntimeError(f"Incomplete candidate curve {cid}")
        if curve["point_index"].astype(int).tolist() != list(range(len(curve))):
            raise RuntimeError(f"Invalid point indexing {cid}")
        p = curve["sigma_i1"].to_numpy(dtype=float)
        s = curve["sigma_m1_local"].to_numpy(dtype=float)
        if public_vector is None:
            public_vector = p
        elif len(p) != len(public_vector) or not np.allclose(p, public_vector):
            raise RuntimeError(f"Public I1 surface does not match at {cid}")
        surfaces.append(s)
        scores.append({"candidate_id": cid, "local_mse": float(np.mean((p-s)**2)),
                       "curve_sha256": sha256_file(curve_file)})
        if i == 1 or i % 8 == 0 or i == 48:
            print(f"PUBLIC-I1 LHS {world}/{provider}: {i}/48", flush=True)

    weights = gibbs_weights(
        design["candidate_id"].astype(str), np.stack(surfaces),
        public_vector, n_public=100, n_candidate=100, lam=cfg["lambda"]
    )
    weights = design.merge(weights, on="candidate_id", validate="one_to_one")
    weights = weights.merge(pd.DataFrame(scores), on="candidate_id", validate="one_to_one")
    weights = weights.sort_values("weight_rank", kind="mergesort")
    if len(weights) != 48 or not np.isclose(weights["weight"].sum(), 1):
        raise RuntimeError("Incorrect provider weights")
    file = base / "provider_weights.csv"
    if file.exists():
        saved = pd.read_csv(file)
        if saved["candidate_id"].tolist() != weights["candidate_id"].tolist() or not np.allclose(
            saved["weight"].astype(float), weights["weight"].astype(float), atol=1e-12
        ):
            raise RuntimeError("Previously frozen provider weights differ")
    else:
        weights.to_csv(file, index=False)
    manifest = base / "provider_manifest.json"
    payload = {
        "status": "B1_RETROSPECTIVE_PROVIDER_FROZEN",
        "world": world, "provider": provider, "candidates": 48,
        "design_sha256": sha256_file(design_file),
        "weights_sha256": sha256_file(file),
        "public_card_json_sha256": record["card_json_sha256"],
        "public_sigma_surface_sha256": record["sigma_surface_sha256"],
        "domain_registry_sha256": sha256_file(
            P5/"results"/"03_reconstruction"/"phase5_m1_domain_registry.csv"),
        "config_sha256": sha256_file(CONFIG),
        "local_rescore_n": 100,
        "no_graph_whitebox_read": True,
    }
    if manifest.exists():
        if read_json(manifest) != payload:
            raise RuntimeError("Frozen provider manifest changed")
    else:
        write_json(manifest, payload)


def prepare_world(cfg, world):
    for provider in PROVIDERS:
        prepare_provider(cfg, world, provider)
    base = OUT / "candidate_support" / world
    base.mkdir(parents=True, exist_ok=True)
    p = {}
    for provider in PROVIDERS:
        root = OUT / "candidates" / world / provider
        manifest = read_json(root / "provider_manifest.json")
        weights_file = root / "provider_weights.csv"
        if sha256_file(weights_file) != manifest["weights_sha256"]:
            raise RuntimeError("Provider weight hash mismatch")
        p[provider] = pd.read_csv(weights_file)
    support = joint_product_support(p)
    assert len(support) == 48**3
    top = support.iloc[:cfg["top_k"]].copy()
    retained = float(top["joint_weight"].sum())
    top["alpha"] = top["joint_weight"] / retained
    n = allocation(top["alpha"].to_numpy(), cfg["graph_budget"])
    top["n_trajectories"] = n
    top["seed_start"] = [
        cfg["top14_seed_base"] + i * cfg["seed_stride"]
        for i in range(cfg["top_k"])
    ]
    top["seed_end_inclusive"] = top["seed_start"] + top["n_trajectories"] - 1
    top["retained_mass"] = retained
    top["omitted_mass"] = 1.0 - retained
    top_path = base / "top14_support.csv"
    if top_path.exists():
        old = pd.read_csv(top_path)
        if old["joint_rank"].astype(int).tolist() != top["joint_rank"].tolist() or (
            not np.allclose(old["alpha"], top["alpha"], atol=1e-12)
        ):
            raise RuntimeError("Frozen Top14 support differs")
    else:
        top.to_csv(top_path, index=False)
    manifest = base / "support_manifest.json"
    data = {
        "status": "B1_RETROSPECTIVE_SUPPORT_FROZEN",
        "world": world, "top_k": 14, "full_support_size": 48**3,
        "retained_mass": retained, "omitted_mass": 1.0-retained,
        "graph_budget": 1400, "top14_support_sha256": sha256_file(top_path),
        "provider_weights_sha256": {
            prov: sha256_file(OUT/"candidates"/world/prov/"provider_weights.csv")
            for prov in PROVIDERS
        }, "config_sha256": sha256_file(CONFIG),
        "no_graph_whitebox_read": True,
    }
    if manifest.exists():
        if read_json(manifest) != data:
            raise RuntimeError("Frozen support manifest differs")
    else:
        write_json(manifest, data)
    print(f"PREPARED {world}: Top14 mass={retained:.6f}, omitted={1.0-retained:.6f}")


def predictions(members, method, support_size, retained_mass, budget):
    rows = []
    for key, g in members.groupby(KEYS, sort=True):
        g = g.sort_values("joint_rank", kind="mergesort")
        if len(g) != support_size:
            raise RuntimeError(f"{method} missing member prediction")
        a = g["alpha"].to_numpy(dtype=float)
        p = g["sigma_member"].to_numpy(dtype=float)
        n = g["graph_n"].to_numpy(dtype=int)
        if not np.isclose(a.sum(), 1) or int(n.sum()) != budget:
            raise RuntimeError("Unexpected aggregation weights/budget")
        point = dict(zip(KEYS, key))
        point.update({
            "method_id": method, "status": "PREDICTED",
            "sigma_hat": float(np.dot(a, p)),
            "support_size": support_size, "retained_mass": retained_mass,
            "omitted_mass": 1.0 - retained_mass, "graph_budget": budget,
            "mc_var_worstcase_bound": float(0.25 * np.sum(a*a/n))
        })
        rows.append(point)
    out = pd.DataFrame(rows).sort_values(["query_id", "H"], kind="mergesort")
    if len(out) != 15*49:
        raise RuntimeError(f"Expected 735 predictions per cell, found {len(out)}")
    return out


def predict_cell(cfg, contracts, cell, workers):
    world, graph_id = cell.split("__", 1)
    root = OUT / "predictions" / cell
    marker = root / "prediction_manifest.json"
    support_file = OUT / "candidate_support" / world / "top14_support.csv"
    support_manifest = OUT / "candidate_support" / world / "support_manifest.json"
    if not support_file.exists() or not support_manifest.exists():
        raise RuntimeError(f"Prepare provider candidates for {world} first")
    if sha256_file(support_file) != read_json(support_manifest)["top14_support_sha256"]:
        raise RuntimeError("Frozen support hash mismatch")
    if marker.exists():
        previous = read_json(marker)
        if previous["status"] != "B1_RETROSPECTIVE_CELL_PREDICTED":
            raise RuntimeError("Unknown existing prediction status")
        if previous["config_sha256"] != sha256_file(CONFIG):
            raise RuntimeError("Retrospective config changed after prediction")
        if previous["support_sha256"] != sha256_file(support_file):
            raise RuntimeError("Candidate support changed after prediction")
        for filename, digest in previous["outputs_sha256"].items():
            if sha256_file(root / filename) != digest:
                raise RuntimeError(f"Prediction output changed: {cell}/{filename}")
        print(f"REUSED FROZEN CELL {cell}")
        return
    root.mkdir(parents=True, exist_ok=True)
    top = pd.read_csv(support_file)
    lookups = {}
    support_details = read_json(support_manifest)
    if support_details["config_sha256"] != sha256_file(CONFIG):
        raise RuntimeError("Candidate support was frozen under a different config")
    for provider in PROVIDERS:
        weights_file = OUT/"candidates"/world/provider/"provider_weights.csv"
        if sha256_file(weights_file) != support_details["provider_weights_sha256"][provider]:
            raise RuntimeError(f"{world}/{provider}: frozen provider weights changed")
        t = pd.read_csv(weights_file)
        lookups[provider] = {
            str(r.candidate_id): _surrogate(pd.Series({
                "mean_service_time": r.mean_service_time,
                "cost_rate": r.cost_rate,
                "service_cv": r.service_cv
            })) for r in t.itertuples(index=False)
        }
    queries = _query_definitions(cell)
    horizons = _horizons(read_json(P5/"config_phase5_graph_prediction_v3b_fullsupport.json"))
    graph = graph_record(contracts, graph_id)
    payloads = []
    specs = []
    for r in top.itertuples(index=False):
        rank = int(r.joint_rank)
        ids = {p: str(getattr(r, f"{p}_candidate_id")) for p in PROVIDERS}
        s = {p: lookups[p][ids[p]] for p in PROVIDERS}
        variant = f"ORIGINAL_TOP14_R{rank:02d}"
        ledger = root/"ledgers"/(variant+".csv")
        seeds = list(range(int(r.seed_start), int(r.seed_end_inclusive)+1))
        payloads.append(_simulation_payload(
            cell_root=root, graph_id=graph_id, graph_ast=graph["ast"],
            variant_id=variant, surrogates=s, seeds=seeds,
            ledger_path=ledger, contracts=contracts
        ))
        specs.append((rank, ids, seeds, ledger, float(r.alpha), float(r.joint_weight)))
    _execute_payloads(payloads, workers=workers, label=f"{cell} ORIGINAL_TOP14")
    curves = []
    for rank, ids, seeds, ledger, alpha, weight in specs:
        piece = _member_curves(
            ledger=_validate_complete_ledger(ledger, seeds),
            queries=queries, horizons=horizons, method_id="ORIGINAL_TOP14",
            rank=rank, graph_n=len(seeds), joint_weight=weight,
            candidate_ids=ids,
        )
        piece["alpha"] = alpha
        curves.append(piece)
    members = pd.concat(curves, ignore_index=True)
    member_path = root/"top14_member_curves.csv"
    members.to_csv(member_path, index=False)
    top14 = predictions(members, "ORIGINAL_TOP14_B1400", 14,
                        float(top["retained_mass"].iloc[0]), 1400)
    top14_path = root/"top14_predictions.csv"
    top14.to_csv(top14_path, index=False)

    if cfg["include_matched_top1"]:
        r = top.iloc[0]
        ids = {p: str(r[f"{p}_candidate_id"]) for p in PROVIDERS}
        variant = "ORIGINAL_TOP1_B1400"
        ledger = root/"ledgers"/(variant+".csv")
        seeds = list(range(cfg["top1_seed_base"],
                           cfg["top1_seed_base"] + cfg["graph_budget"]))
        payload = _simulation_payload(
            cell_root=root, graph_id=graph_id, graph_ast=graph["ast"],
            variant_id=variant,
            surrogates={p: lookups[p][ids[p]] for p in PROVIDERS},
            seeds=seeds, ledger_path=ledger, contracts=contracts
        )
        _execute_payloads([payload], workers=workers, label=f"{cell} ORIGINAL_TOP1")
        t1 = _member_curves(
            ledger=_validate_complete_ledger(ledger, seeds),
            queries=queries, horizons=horizons, method_id="ORIGINAL_TOP1",
            rank=1, graph_n=len(seeds), joint_weight=1.0,
            candidate_ids=ids,
        )
        t1["alpha"] = 1.0
        p1 = predictions(t1, "ORIGINAL_TOP1_B1400", 1, 1.0, 1400)
        p1.to_csv(root/"top1_predictions.csv", index=False)
    names = ["top14_member_curves.csv", "top14_predictions.csv"]
    if cfg["include_matched_top1"]:
        names.append("top1_predictions.csv")
    write_json(marker, {
        "status": "B1_RETROSPECTIVE_CELL_PREDICTED",
        "cell": cell, "config_sha256": sha256_file(CONFIG),
        "support_sha256": sha256_file(support_file),
        "outputs_sha256": {name: sha256_file(root/name) for name in names},
        "reference_whitebox_read": False, "completed_utc": utc_now_iso(),
    })
    print(f"PREDICTED {cell}: 735 points per method; no white-box reference read")


def freeze_all(cfg):
    cells = sorted(
        physical_cell_id(w, g) for w in cfg["eligible_worlds"] for g in cfg["graphs"]
    )
    records = []
    for cell in cells:
        root = OUT/"predictions"/cell
        marker = root/"prediction_manifest.json"
        if not marker.exists():
            raise RuntimeError(f"Incomplete predictions: {cell}")
        m = read_json(marker)
        if m.get("status") != "B1_RETROSPECTIVE_CELL_PREDICTED":
            raise RuntimeError(f"Unfrozen prediction: {cell}")
        if m.get("config_sha256") != sha256_file(CONFIG):
            raise RuntimeError(f"Config changed since prediction: {cell}")
        for filename, digest in m["outputs_sha256"].items():
            if sha256_file(root/filename) != digest:
                raise RuntimeError(f"Edited prediction: {cell}/{filename}")
        records.append({"cell": cell, "manifest_sha256": sha256_file(marker)})
    filename = OUT/"global_prediction_freeze.json"
    payload = {
        "status": "B1_RETROSPECTIVE_ALL_12_PREDICTIONS_FROZEN",
        "config_sha256": sha256_file(CONFIG), "cells": records,
        "reference_whitebox_read": False,
    }
    if filename.exists():
        if read_json(filename) != payload:
            raise RuntimeError("Global prediction freeze differs")
    else:
        write_json(filename, payload)
    print("B1_RETROSPECTIVE_GLOBAL_PREDICTION_FREEZE_PASS")


def evaluate(cfg):
    freeze_all(cfg)
    # The only stage that may open the existing final white-box reference.
    frames = []
    method_files = ["top14_predictions.csv"]
    if cfg["include_matched_top1"]:
        method_files.append("top1_predictions.csv")
    for w in cfg["eligible_worlds"]:
        for g in cfg["graphs"]:
            cell = physical_cell_id(w, g)
            root = OUT/"predictions"/cell
            wbfile = WB_ROOT/cell/"final_wb_curves.csv"
            baselinefile = BASELINE_ROOT/cell/"m3_predictions_full343_and_nested.csv"
            if not wbfile.is_file() or not baselinefile.is_file():
                raise FileNotFoundError(f"Missing existing Phase-5 evidence {cell}")
            wb = pd.read_csv(wbfile)
            baseline = pd.read_csv(baselinefile)
            baseline = baseline[baseline["method_id"] == "M3_FULL343"]
            for methodfile in method_files+[None]:
                p = (baseline if methodfile is None
                     else pd.read_csv(root/methodfile))
                name = ("M3_FULL343_V3B" if methodfile is None
                        else str(p["method_id"].iloc[0]))
                if p.duplicated(KEYS).any() or wb.duplicated(KEYS).any():
                    raise RuntimeError(f"Duplicate evaluation keys in {cell}")
                m = p[KEYS+["sigma_hat"]].merge(
                    wb[KEYS+["sigma_wb"]], on=KEYS, validate="one_to_one"
                )
                m = m[m["H"].between(60, 240)]
                if len(m) != 555:
                    raise RuntimeError(f"{cell}/{name}: expected 555 evaluations, got {len(m)}")
                m["cell"] = cell
                m["method"] = name
                m["error"] = m["sigma_hat"] - m["sigma_wb"]
                frames.append(m)
    result = pd.concat(frames, ignore_index=True)
    stats = []
    for (method, cell), group in result.groupby(["method", "cell"]):
        e = group["error"].to_numpy()
        stats.append({"scope": "cell", "method": method, "cell": cell,
                      "n_points": len(e), "mae": np.mean(np.abs(e)),
                      "rmse": np.sqrt(np.mean(e*e)), "bias": np.mean(e)})
    for method, group in result.groupby("method"):
        e = group["error"].to_numpy()
        stats.append({"scope": "all_12_cells", "method": method, "cell": "ALL",
                      "n_points": len(e), "mae": np.mean(np.abs(e)),
                      "rmse": np.sqrt(np.mean(e*e)), "bias": np.mean(e)})
    for scope, column in (("provider_configuration", "provider_world_id"),
                          ("composition_graph", "graph_id")):
        for (method, value), group in result.groupby(["method", column]):
            e = group["error"].to_numpy()
            stats.append({"scope": scope, "method": method, "cell": str(value),
                          "n_points": len(e), "mae": np.mean(np.abs(e)),
                          "rmse": np.sqrt(np.mean(e*e)), "bias": np.mean(e)})
    dest = OUT/"evaluation"
    dest.mkdir(parents=True, exist_ok=True)
    result.to_csv(dest/"pointwise_retrospective.csv", index=False)
    tab = pd.DataFrame(stats)
    tab.to_csv(dest/"metrics_retrospective.csv", index=False)
    print(tab[tab["scope"] == "all_12_cells"].to_string(index=False))
    write_json(dest/"evaluation_manifest.json", {
        "status": "B1_RETROSPECTIVE_EVALUATION_COMPLETE",
        "prediction_freeze_sha256": sha256_file(OUT/"global_prediction_freeze.json"),
        "pointwise_sha256": sha256_file(dest/"pointwise_retrospective.csv"),
        "metrics_sha256": sha256_file(dest/"metrics_retrospective.csv"),
        "interpretation": "Retrospective after existing Phase-5 WB was already inspected; not independent confirmation",
        "completed_utc": utc_now_iso(),
    })


def main():
    a = argparse.ArgumentParser(description="Original-style M3 retrospective generalization battery")
    a.add_argument("--stage", required=True, choices=["preflight", "prepare", "predict", "freeze", "evaluate"])
    a.add_argument("--world", choices=["P1", "P3", "P4"])
    a.add_argument("--cell", help="e.g. P1__G_PAR")
    a.add_argument("--workers", type=int, default=1)
    args = a.parse_args()
    cfg, contracts = configuration()
    if args.workers < 1:
        raise ValueError("workers must be >=1")
    if args.stage == "preflight":
        preflight(cfg)
    elif args.stage == "prepare":
        for w in ([args.world] if args.world else cfg["eligible_worlds"]):
            prepare_world(cfg, w)
    elif args.stage == "predict":
        allowed = {physical_cell_id(w, g) for w in cfg["eligible_worlds"] for g in cfg["graphs"]}
        if args.cell and args.cell not in allowed:
            raise RuntimeError(f"Cell not eligible: {args.cell}")
        cells = [args.cell] if args.cell else sorted(allowed)
        for i, cell in enumerate(cells, 1):
            predict_cell(cfg, contracts, cell, args.workers)
            print(f"PROGRESS {i}/{len(cells)}", flush=True)
        if not args.cell:
            freeze_all(cfg)
    elif args.stage == "freeze":
        freeze_all(cfg)
    elif args.stage == "evaluate":
        evaluate(cfg)


if __name__ == "__main__":
    main()
