#!/usr/bin/env python3
"""Read-only mini-audit of IPT gauge effects on frozen original-style M3 G_PAR.

Compare a small number of native Phase-5 G_PAR simulations at surrogate IPT=1e6
with the *same seeds and surrogate parameters* in the archived IPT=1e9 Top14
rank-1 ledger. Evaluate the same 15 frozen SLA query boundaries and 37 primary
horizons. Do not read final-WB results or mutate any frozen scientific artifact.

This is a diagnostic on a small seed subset, not a statistical generalization
or full B1400 re-evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent.parent
P3 = FIRST / "phase3"
P5 = FIRST / "phase5"
OUT = P5 / "results" / "b1_pilot_m3_retrospective_v1"
options = ([Path(os.environ["PRAISE_YAFS_SRC"]).expanduser()]
           if os.environ.get("PRAISE_YAFS_SRC") else []) + [
    FIRST.parent.parent / "aicon" / "src" / "yafs" / "src"
]
for candidate in options:
    if (candidate / "yafs" / "application.py").is_file():
        sys.path.insert(0, str(candidate.resolve()))
        break
for path in (P3, P5):
    sys.path.insert(0, str(path))
from yafs.application import Application  # noqa: E402
if not callable(getattr(Application, "add_service_module_praise", None)):
    raise SystemExit("PRAISE-modified YAFS runtime required")
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve  # noqa: E402
from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory  # noqa: E402

P = ("ProviderA", "ProviderB", "ProviderC")
FIELDS = ("request_id", "emission", "completion", "L", "C",
          "Q", "completed_by_stop", "status")
CONTINUOUS = ("emission", "completion", "L", "C", "Q")
HORIZONS = [float(x) for x in range(60, 241, 5)]


def graph_curves(ledger, queries):
    rows = []
    for q in queries.itertuples(index=False):
        b = AdmissibilityBoundary(
            l_max=float(q.A_G_l_max), c_max=float(q.A_G_c_max),
            q_min=float(q.A_G_q_min)
        )
        t = build_empirical_graph_sigma_curve(
            ledger, boundary=b, rho_global=float(q.rho),
            horizons=HORIZONS, stop_time=240.,
            accounting_origin=0., output_column="sigma"
        )
        t["query_id"] = str(q.query_id)
        rows.append(t)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["query_id", "horizon"]
    ).reset_index(drop=True)


def main(cell, n_seeds):
    if not cell.endswith("__G_PAR"):
        raise ValueError("This diagnostic is restricted to the parallel G_PAR graph")
    world = cell.split("__", 1)[0]
    if world not in ("P1", "P3", "P4"):
        raise ValueError("World must be P1/P3/P4")
    support = pd.read_csv(OUT / "candidate_support" / world / "top14_support.csv")
    if not (len(support) == 14 and int(support["joint_rank"].iloc[0]) == 1):
        raise RuntimeError("Expected frozen 14-member support, with rank 1 first")
    rank1 = support.iloc[0]
    seeds = list(range(int(rank1.seed_start), int(rank1.seed_start) + n_seeds))
    if seeds[-1] > int(rank1.seed_end_inclusive):
        raise RuntimeError("Requested seeds exceed frozen rank-1 trajectory bank")
    params = {}
    for provider in P:
        weights = pd.read_csv(OUT / "candidates" / world / provider / "provider_weights.csv")
        cid = str(rank1[f"{provider}_candidate_id"])
        subset = weights[weights["candidate_id"].astype(str) == cid]
        if len(subset) != 1:
            raise RuntimeError(f"Missing frozen {provider} candidate {cid}")
        row = subset.iloc[0]
        params[provider] = GraphProviderSurrogate(
            mean_service_time=float(row.mean_service_time),
            cost_rate=float(row.cost_rate),
            service_cv=float(row.service_cv)
        )
    frozen_path = OUT / "predictions" / cell / "ledgers" / "ORIGINAL_TOP14_R01.csv"
    if not frozen_path.is_file():
        raise FileNotFoundError(frozen_path)
    original = pd.read_csv(frozen_path)
    original = original.loc[original["trajectory_seed"].isin(seeds)].copy()
    if sorted(original["trajectory_seed"].unique().tolist()) != seeds:
        raise RuntimeError("Frozen ledger missing some requested seeds")

    queries = pd.read_csv(
        P5 / "results" / "02_step0" / cell / "step0_frozen_queries.csv",
        usecols=["query_id", "rho", "regime",
                 "A_G_l_max", "A_G_c_max", "A_G_q_min"]
    )
    if len(queries) != 15:
        raise RuntimeError("Expected 15 frozen SLA query definitions")

    battery = json.loads((P5 / "config_phase5_recoverability_battery_v2.json").read_text())
    graph = next(row for row in battery["graphs"] if row["id"] == "G_PAR")
    family = battery["provider_family"]
    if float(family["effective_IPT"]) != 1e9:
        raise RuntimeError("Phase-5 frozen canonical IPT was changed")
    inv = dict(battery["graph_invariants"])
    inv["effective_IPT"] = float(family["effective_IPT"])
    inv["cost_rate"] = float(family["cost_rate"])
    period = float(battery["workload"]["period_seconds"])
    frac = float(family["execution_fraction_x"])
    print(f"GAUGE_CHECK {cell}, original Top14 rank 1, "
          f"{n_seeds} frozen seed(s). No WB read and no archives altered.",
          flush=True)
    parts = []
    started = time.perf_counter()
    for ordinal, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            changed, _ = execute_one_phase5_graph_trajectory(
                graph_id="G_PAR", graph_ast=graph["ast"],
                provider_surrogates=params, graph_invariants=inv,
                workload_period=period, stop_time=240., trajectory_seed=seed,
                canonical_ipt=1e6, execution_fraction=frac
            )
        changed.insert(0, "trajectory", int(ordinal))
        changed.insert(1, "trajectory_seed", int(seed))
        parts.append(changed)
    alt = pd.concat(parts, ignore_index=True)

    a = original.sort_values(["trajectory_seed", "request_id"]).reset_index(drop=True)
    b = alt.sort_values(["trajectory_seed", "request_id"]).reset_index(drop=True)
    if not a[["trajectory_seed", "request_id"]].equals(
            b[["trajectory_seed", "request_id"]]):
        raise RuntimeError("Request identity mismatch. Inspect native ledger differences.")
    max_abs = {}
    for col in CONTINUOUS:
        u, v = a[col].to_numpy(float), b[col].to_numpy(float)
        mask = np.isfinite(u) & np.isfinite(v)
        max_abs[col] = float(np.abs(u[mask]-v[mask]).max()) if mask.any() else 0.
    status_different = {
        col:int((a[col].astype(str)!=b[col].astype(str)).sum())
        for col in ("completed_by_stop", "status")
    }
    print(f"Same request identities: {len(a)} rows. "
          f"Maximum absolute numeric differences: {max_abs}", flush=True)
    print(f"Completion/status differences: {status_different}", flush=True)

    old = graph_curves(original, queries)
    new = graph_curves(alt, queries)
    if not old[["query_id", "horizon"]].equals(new[["query_id", "horizon"]]):
        raise RuntimeError("SLA curve keys differ")
    diff = (old["sigma"].astype(float)-new["sigma"].astype(float)).abs()
    print(f"SCORING {len(diff)} matched query-horizon points. "
          f"Changed sigma values: {(diff > 1e-12).sum()}; "
          f"mean |delta sigma|: {diff.mean():.9f}; "
          f"maximum |delta sigma|: {diff.max():.9f}",
          flush=True)
    print(f"Elapsed {time.perf_counter()-started:.2f} seconds.", flush=True)
    print("B1_GAUGE_SUBSET_CHECK_COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", default="P3__G_PAR")
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 20:
        parser.error("--seeds must be between 1 and 20")
    main(args.cell, args.seeds)
