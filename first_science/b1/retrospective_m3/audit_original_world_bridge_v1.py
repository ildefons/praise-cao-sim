#!/usr/bin/env python3
"""Matched original-world native G0 -> G_PAR replay using archived pilot M3 models.

No new provider reconstruction and no white-box access. Select first N frozen
graph seeds for each of the first K frozen pilot M3 joint members, compare their
archived native G0 request records with fresh Phase5 G_PAR native records under
(1) exactly matched IPT=1e6, and (2) Phase5 IPT=1e9. Evaluate on precisely
the 15 ORIGINAL pilot Step-0 query boundaries.

The subset's SLA summaries do not replace the official B1400 M3 estimates.
No frozen files are written or modified.
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
P4 = FIRST / "phase4"
P5 = FIRST / "phase5"
PILOT = P4 / "results" / "m3_v4_dominant_mass_graph_v1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")

options = ([Path(os.environ["PRAISE_YAFS_SRC"]).expanduser()]
           if os.environ.get("PRAISE_YAFS_SRC") else []) + [
    FIRST.parent.parent / "aicon" / "src" / "yafs" / "src"
]
for src in options:
    if (src / "yafs" / "application.py").is_file():
        sys.path.insert(0, str(src.resolve()))
        break
for src in (P3, P4, P5):
    sys.path.insert(0, str(src))
from yafs.application import Application  # noqa: E402
if not callable(getattr(Application, "add_service_module_praise", None)):
    raise SystemExit("PRAISE-modified YAFS is required.")
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory  # noqa: E402
from run_m1_graph_prediction_v2 import build_empirical_graph_sigma_curve  # noqa: E402
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402

NUM = ("emission", "completion", "L", "C", "Q")
CAT = ("status", "completed_by_stop")
HORIZONS = [float(x) for x in range(60, 241, 5)]


def aligned_native(old, new, rank, mode):
    keys = ["trajectory", "request_id"]
    o = old.sort_values(keys).reset_index(drop=True)
    n = new.sort_values(keys).reset_index(drop=True)
    if not o[keys].equals(n[keys]):
        print(f"DIFFERENT rank={rank} mode={mode}: native request identities", flush=True)
        return False, float("inf")
    mismatched = {}
    max_abs = 0.
    for name in NUM:
        x, y = o[name].to_numpy(float), n[name].to_numpy(float)
        finite = np.isfinite(x) & np.isfinite(y)
        delta = np.abs(x[finite] - y[finite])
        mx = float(np.max(delta)) if delta.size else 0.
        max_abs = max(max_abs, mx)
        close = np.isclose(x, y, atol=1e-8, rtol=1e-8, equal_nan=True)
        mismatched[name] = int((~close).sum())
    for name in CAT:
        mismatched[name] = int((o[name].astype(str) != n[name].astype(str)).sum())
    passed = all(v == 0 for v in mismatched.values())
    print(f"{'MATCH' if passed else 'DIFFERENT'} rank={rank} mode={mode} "
          f"requests={len(o)} max_abs={max_abs:.9g} "
          f"mismatched={mismatched}", flush=True)
    return passed, max_abs


def sigma_curve(frame, q):
    b = AdmissibilityBoundary(
        l_max=float(q.A_G_l_max), c_max=float(q.A_G_c_max),
        q_min=float(q.A_G_q_min)
    )
    return build_empirical_graph_sigma_curve(
        frame, boundary=b, rho_global=float(q.rho_global),
        horizons=HORIZONS, stop_time=240., accounting_origin=0.,
        output_column="sigma_member"
    )


def weighted_query_predictions(members, queries, rank_weights):
    rows = []
    total = sum(rank_weights.values())
    for q in queries.itertuples(index=False):
        estimates = {}
        for mode, by_rank in members.items():
            total_sigma = None
            for rank, frame in by_rank.items():
                x = sigma_curve(frame, q)["sigma_member"].to_numpy(float)
                total_sigma = (x * rank_weights[rank] if total_sigma is None else
                               total_sigma + x * rank_weights[rank])
            estimates[mode] = total_sigma / total
        for idx, h in enumerate(HORIZONS):
            rows.append((str(q.regime), float(q.rho_global), h,
                         *(estimates[mode][idx] for mode in ("OLD_G0", "NEW_GPAR_1E6", "NEW_GPAR_1E9"))))
    t = pd.DataFrame(rows, columns=[
        "regime", "rho", "H", "old", "new_1e6", "new_1e9"
    ])
    a = abs(t["old"] - t["new_1e6"])
    b = abs(t["old"] - t["new_1e9"])
    print(f"\nOriginal-pilot query readout, same small trajectory subset: "
          f"{len(t)} query-horizon points")
    print(f"OLD_G0 versus G_PAR(1e6): changed={(a>1e-12).sum()} "
          f"mean_abs={a.mean():.9g} max_abs={a.max():.9g}")
    print(f"OLD_G0 versus G_PAR(1e9): changed={(b>1e-12).sum()} "
          f"mean_abs={b.mean():.9g} max_abs={b.max():.9g}")
    print("These are within-subset engine/gauge differences, not WB errors.")
    return a, b


def main(ranks, n_per_rank):
    begin = time.monotonic()
    design = pd.read_csv(PILOT / "m3_v4_dominant_design.csv")
    design = design.sort_values("rank").reset_index(drop=True)
    weights = pd.read_csv(P4 / "results" / "m3_lambda_cv_v3" / "m3_v3_provider_weights.csv")
    queries = pd.read_csv(P4 / "results" / "sigma_regime_step0_calibration_v2" /
                          "sigma_regime_v2_selected_regions_frozen.csv")
    if len(design) != 14 or len(queries) != 15 or len(weights) != 144:
        raise RuntimeError("Unexpected frozen Phase4 pilot artifacts")
    if ranks > len(design):
        raise RuntimeError("Requested more than 14 frozen ranks")
    phase5 = json.loads((P5 / "config_phase5_recoverability_battery_v2.json").read_text())
    graph = next(g for g in phase5["graphs"] if g["id"] == "G_PAR")
    family = phase5["provider_family"]
    inv = dict(phase5["graph_invariants"])
    inv["effective_IPT"] = float(family["effective_IPT"])
    inv["cost_rate"] = float(family["cost_rate"])
    if float(family["effective_IPT"]) != 1e9:
        raise RuntimeError("Phase5 gauge unexpectedly changed")
    data = {"OLD_G0": {}, "NEW_GPAR_1E6": {}, "NEW_GPAR_1E9": {}}
    rank_weights = {}
    print(f"B1 original-world bridge: K={ranks}, N={n_per_rank} per rank, "
          f"{2*ranks*n_per_rank} new graph trajectories. No WB access.", flush=True)
    native_ok = True

    for row in design.head(ranks).itertuples(index=False):
        rank = int(row.rank)
        rank_weights[rank] = float(row.alpha_renormalized)
        local_models = {}
        for provider in PROVIDERS:
            cid = str(getattr(row, provider + "_candidate_id"))
            g = weights.loc[(weights["provider"].astype(str) == provider)
                            & (weights["candidate_id"].astype(str) == cid)]
            if len(g) != 1:
                raise RuntimeError(f"Missing historical pilot candidate: {provider}/{cid}")
            v = g.iloc[0]
            local_models[provider] = GraphProviderSurrogate(
                mean_service_time=float(v.mean_service_time),
                cost_rate=float(v.cost_rate),
                service_cv=float(v.service_cv)
            )
        original_file = PILOT / "ledgers" / f"M3Q_R{rank:02d}.csv"
        legacy = pd.read_csv(original_file)
        # The original graph contract uses the first N of the rank seed stream.
        requested = [int(row.seed_start) + j for j in range(n_per_rank)]
        old = legacy.loc[legacy["trajectory_seed"].astype(int).isin(requested)].copy()
        if sorted(old["trajectory_seed"].astype(int).unique().tolist()) != requested:
            raise RuntimeError(f"Missing historical pilot graph ledger seeds for rank {rank}")
        if sorted(old["trajectory"].astype(int).unique().tolist()) != list(range(n_per_rank)):
            raise RuntimeError("Archived rank trajectory ordinals do not match seed prefix")
        data["OLD_G0"][rank] = old
        produced = {}
        for label, ipt in (("NEW_GPAR_1E6", 1e6), ("NEW_GPAR_1E9", 1e9)):
            pieces = []
            for ordinal, seed in enumerate(requested):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    ledger, _ = execute_one_phase5_graph_trajectory(
                        graph_id="G_PAR", graph_ast=graph["ast"],
                        provider_surrogates=local_models, graph_invariants=inv,
                        workload_period=.2, stop_time=240.,
                        trajectory_seed=seed, canonical_ipt=ipt,
                        execution_fraction=.5
                    )
                ledger.insert(0, "trajectory", ordinal)
                ledger.insert(1, "trajectory_seed", seed)
                pieces.append(ledger)
            produced[label] = pd.concat(pieces, ignore_index=True)
            data[label][rank] = produced[label]
            ok, _ = aligned_native(old, produced[label], rank, label)
            if label == "NEW_GPAR_1E6":
                native_ok = native_ok and ok
    d1, d2 = weighted_query_predictions(data, queries, rank_weights)
    print(f"Elapsed {time.monotonic()-begin:.1f} seconds")
    print("B1_BRIDGE_NATIVE_PARITY_PASS" if native_ok and d1.max()<1e-12
          else "B1_BRIDGE_NATIVE_PARITY_DIFFERENCE")
    print("B1_BRIDGE_DIAGNOSTIC_COMPLETE")
    # A matched-gauge discrepancy is an actual parity failure.
    return 0 if native_ok and d1.max()<1e-12 else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranks", type=int, default=3)
    parser.add_argument("--seeds-per-rank", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.ranks <= 14 or not 1 <= args.seeds_per_rank <= 10:
        parser.error("ranks in 1..14 and seeds-per-rank in 1..10 required")
    raise SystemExit(main(args.ranks, args.seeds_per_rank))
