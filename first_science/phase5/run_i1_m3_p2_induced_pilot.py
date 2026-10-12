"""Separate P2 I1-M3 induced-region pilot (prediction-only).

No Step-0 selection or graph white-box access. Region construction is exactly
Phase-5's public-I1 forward graph boundary composition, not graph GMM fitting.
Run --dry-run before --run. --max-members <343 is engineering smoke ONLY.
Canonical M3_FULL343 uses all 343 models and B=1400 trajectories per graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_graph_prediction_v3b_fullsupport as m3
from phase5_runtime_v2 import graph_record, load_phase5_contracts, sha256_file
from run_phase5_step0_v2 import _base_boundary, _load_public_i1_world

HERE = Path(__file__).resolve().parent
ROOT = HERE / "results" / "i1_m3_p2_induced_pilot"
WORLD = "P2"
BUDGET = 1400
SEED_BASE = 9_000_000
SEED_STRIDE = 10_000


def allocation(support: pd.DataFrame) -> pd.DataFrame:
    table = support.sort_values("joint_rank").reset_index(drop=True)
    ranks = table["joint_rank"].astype(int).to_numpy()
    weights = table["joint_weight"].astype(float).to_numpy()
    if ranks.tolist() != list(range(1, 344)):
        raise ValueError("M3 support must contain ranks 1..343")
    if not np.isclose(weights.sum(), 1.0, atol=1e-10, rtol=0):
        raise ValueError("M3 weights must sum to one")
    if (weights < 0).any() or not np.isfinite(weights).all():
        raise ValueError("invalid M3 weights")
    n = np.ones(343, dtype=int)
    for _ in range(BUDGET - 343):
        improvements = weights**2 / (n * (n+1))
        n[int(np.argmax(improvements))] += 1
    return pd.DataFrame({
        "rank": ranks, "joint_weight": weights,
        "n_trajectories": n,
        "seed_start": SEED_BASE + (ranks-1)*SEED_STRIDE,
        "seed_end_inclusive": SEED_BASE + (ranks-1)*SEED_STRIDE+n-1,
    })


def build_queries(contracts, graph_id: str) -> pd.DataFrame:
    cards = _load_public_i1_world(contracts, WORLD)
    rho_values = tuple(float(x) for x in contracts.battery["public_I1"]["rho_region_values"])
    queries = []
    for rho in rho_values:
        b = _base_boundary(contracts, graph_id=graph_id, cards=cards, rho=rho)
        queries.append({
            "query_id": f"{WORLD}__{graph_id}__rho_{rho:.9f}",
            "provider_world_id": WORLD, "graph_id": graph_id,
            "rho_label": f"rho_{rho:.9f}", "rho": rho,
            "regime": "INDUCED_I1",
            "A_G_l_max": b.l_max, "A_G_c_max": b.c_max,
            "A_G_q_min": b.q_min,
        })
    return pd.DataFrame(queries)


def run(graph_id: str, workers: int, *, dry_run: bool, max_members: int) -> Path:
    contracts = load_phase5_contracts(HERE)
    graph = graph_record(contracts, graph_id)
    queries = build_queries(contracts, graph_id)
    support_path = m3.V3B_ROOT / WORLD / "m3_joint_support_343.csv"
    support = pd.read_csv(support_path)
    alloc = allocation(support)
    lookup = m3._candidate_lookup(WORLD, "M3")
    output = ROOT / f"{WORLD}__{graph_id}"
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
    if max_members != 343 and not dry_run:
        raise ValueError("Partial supports are excluded from the prediction runner; use --dry-run for inspection")
    if dry_run:
        print("P2_I1_M3_PILOT_PREFLIGHT_PASS")
        print(queries.to_string(index=False))
        print(f"joint_models=343 graph_budget={int(alloc.n_trajectories.sum())} graph={graph_id}")
        return output

    freeze = output / "prediction_manifest.json"
    if freeze.exists():
        raise FileExistsError(f"Pilot already frozen; refusing overwrite: {freeze}")
    queries_path = output / "public_induced_queries.csv"
    queries.to_csv(queries_path, index=False)
    alloc_path = output / "m3_allocation.csv"
    alloc.to_csv(alloc_path, index=False)

    payloads = []
    variants = []
    for row in support.sort_values("joint_rank").itertuples(index=False):
        rank = int(row.joint_rank)
        a = alloc.iloc[rank-1]
        ids = {p: str(getattr(row, f"{p}_candidate_id")) for p in m3.PROVIDERS}
        surrogates = {p: lookup[(p, ids[p])] for p in m3.PROVIDERS}
        seeds = list(range(int(a.seed_start), int(a.seed_end_inclusive)+1))
        payloads.append(m3._simulation_payload(
            cell_root=output, graph_id=graph_id, graph_ast=graph["ast"],
            variant_id=f"M3_R{rank:03d}", surrogates=surrogates, seeds=seeds,
            ledger_path=output/"ledgers"/f"M3_R{rank:03d}.csv",
            contracts=contracts,
        ))
        variants.append((rank, ids, float(row.joint_weight), seeds))
    m3._execute_payloads(payloads, workers=workers, label=f"P2 {graph_id} induced M3")

    frames = []
    horizons = [float(x) for x in np.arange(0, 241, 5)]
    for rank, ids, weight, seeds in variants:
        ledger = m3._validate_complete_ledger(
            output/"ledgers"/f"M3_R{rank:03d}.csv", seeds
        )
        frames.append(m3._member_curves(
            ledger=ledger, queries=queries, horizons=horizons,
            method_id="M3_MEMBER", rank=rank, graph_n=len(seeds),
            joint_weight=weight, candidate_ids=ids,
        ))
    members = pd.concat(frames, ignore_index=True)
    member_path = output/"m3_member_curves.csv"
    members.to_csv(member_path, index=False)
    prediction = m3._m3_predictions(members)
    pred_path = output/"m3_predictions_full343_and_nested.csv"
    prediction.to_csv(pred_path, index=False)
    manifest = {
        "status":"FROZEN_P2_I1_M3_INDUCED_GRAPH_PREDICTION",
        "world":WORLD, "graph_id":graph_id,
        "primary_method":"M3_FULL343", "graph_budget":BUDGET,
        "joint_support":343, "whitebox_read":False,
        "query_semantics":"public I1 induced A_G(rho_region), same rho_query",
        "source_support_sha256":sha256_file(support_path),
        "source_provider_config_sha256":sha256_file(m3.V3B_ROOT/WORLD/"m3_joint_support_343.csv"),
        "files":{
            "queries":sha256_file(queries_path),
            "allocation":sha256_file(alloc_path),
            "members":sha256_file(member_path),
            "predictions":sha256_file(pred_path),
        },
        "ledger_hashes":{
            f"M3_R{rank:03d}":sha256_file(output/"ledgers"/f"M3_R{rank:03d}.csv")
            for rank, *_ in variants
        },
    }
    freeze.write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"P2_I1_M3_INDUCED_PREDICTION_FROZEN {freeze}")
    return output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="G_PAR",
                    choices=["G_PAR","G_SEQ","G_SEQPAR","G_PARSEQ"])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-members", type=int, default=343)
    args = ap.parse_args()
    if args.workers < 1 or args.max_members < 1 or args.max_members > 343:
        raise ValueError("workers and max-members out of range")
    run(args.graph, args.workers, dry_run=args.dry_run,
        max_members=args.max_members)


if __name__ == "__main__":
    main()
