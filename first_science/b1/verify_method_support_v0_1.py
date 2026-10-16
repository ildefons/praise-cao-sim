#!/usr/bin/env python3
"""B1 method-definition archive verifier: no simulation, no scientific modifications.

Verify that persisted V3b provider selections, 27/343 Cartesian products,
Gibbs weights, and pre-graph-WB B=1400 allocations implement the declared
method definitions. Outputs exclusively under B1/local_audit.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent
P5 = FIRST / "phase5" / "results"
ROOT = P5 / "03_reconstruction_v3b"
V3 = P5 / "03_reconstruction_v3"
PRED = P5 / "04_prediction_v3b_fullsupport"
OUT = FIRST / "b1" / "local_audit" / "method_support_v0_1"
WORLDS = ("P1", "P2", "P3", "P4")
ELIGIBLE = ("P1", "P3", "P4")
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EPS = 1e-10


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="Return exit code 1 when checks fail (default prints failures and exits 0)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(world, scope, name, passed, details=""):
        row = {
            "world": world,
            "scope": scope,
            "check": name,
            "result": "PASS" if bool(passed) else "FAIL",
            "details": str(details)
        }
        checks.append(row)
        if not passed:
            print(f"FAIL [{world}/{scope}] {name}: {details}", flush=True)

    def load(path):
        if not path.is_file():
            raise FileNotFoundError(path)
        return pd.read_csv(path)

    for world in WORLDS:
        try:
            choices = {}
            weights = {}
            for provider in PROVIDERS:
                loc = ROOT / world / provider
                quality = load(loc / "v3b_candidate_quality_ranking.csv")
                m1 = load(loc / "m1_provider_model.csv")
                m2 = load(loc / "m2_provider_models.csv")
                m3 = load(loc / "m3_provider_models.csv")
                v3 = load(V3 / world / provider / "m3_provider_models.csv")
                q = quality.sort_values(["rescore_rmse", "candidate_id"], kind="mergesort")
                qids = q["candidate_id"].astype(str).tolist()
                ids1 = m1["candidate_id"].astype(str).tolist()
                ids2 = m2["candidate_id"].astype(str).tolist()
                ids3 = m3["candidate_id"].astype(str).tolist()
                check(world, provider, "bank_7_unique",
                      len(qids) == len(set(qids)) == 7)
                check(world, provider, "m1_best_rescore_rmse",
                      ids1 == qids[:1], ids1)
                check(world, provider, "m2_best3_and_contains_m1",
                      ids2 == qids[:3] and ids1[0] in ids2, ids2)
                check(world, provider, "m2_equal_provider_weights",
                      "provider_weight" in m2 and np.allclose(
                          m2["provider_weight"].astype(float), 1/3, atol=EPS, rtol=0))
                check(world, provider, "m3_same_seven_as_v3",
                      sorted(ids3) == sorted(v3["candidate_id"].astype(str).tolist()) == sorted(qids))
                wm = m3.set_index("candidate_id")["weight"].astype(float)
                wv = v3.set_index("candidate_id")["weight"].astype(float)
                check(world, provider, "m3_weights_unchanged_from_v3",
                      sorted(wm.index.tolist()) == sorted(wv.index.tolist()) and
                      np.allclose(wm.sort_index(), wv.sort_index(), atol=EPS, rtol=0))
                check(world, provider, "m3_provider_weights_sum_one",
                      np.isfinite(wm).all() and (wm > 0).all() and
                      abs(float(wm.sum()) - 1) <= EPS)
                choices[provider] = {"m2": ids2, "m3": ids3}
                weights[provider] = wm

            m2_joint = load(ROOT / world / "m2_joint_support_27.csv")
            m3_joint = load(ROOT / world / "m3_joint_support_343.csv")
            ids = [f"{p}_candidate_id" for p in PROVIDERS]
            check(world, "M2", "joint_count_and_ranks",
                  len(m2_joint) == 27 and m2_joint["joint_rank"].astype(int).tolist() == list(range(1,28)))
            actual2 = set(map(tuple, m2_joint[ids].astype(str).itertuples(index=False, name=None)))
            expected2 = {(a,b,c) for a in choices["ProviderA"]["m2"]
                          for b in choices["ProviderB"]["m2"]
                          for c in choices["ProviderC"]["m2"]}
            check(world, "M2", "cartesian_membership", actual2 == expected2)
            check(world, "M2", "equal_joint_weights",
                  np.allclose(m2_joint["joint_weight"].to_numpy(float), 1/27, atol=EPS, rtol=0))
            check(world, "M3", "joint_count_and_ranks",
                  len(m3_joint) == 343 and m3_joint["joint_rank"].astype(int).tolist() == list(range(1,344)))
            actual3 = set(map(tuple, m3_joint[ids].astype(str).itertuples(index=False, name=None)))
            expected3 = {(a,b,c) for a in choices["ProviderA"]["m3"]
                          for b in choices["ProviderB"]["m3"]
                          for c in choices["ProviderC"]["m3"]}
            check(world, "M3", "cartesian_membership", actual3 == expected3)
            recomputed = np.array([
                float(weights["ProviderA"][str(a)]) *
                float(weights["ProviderB"][str(b)]) *
                float(weights["ProviderC"][str(c)])
                for a,b,c in m3_joint[ids].astype(str).itertuples(index=False, name=None)
            ], dtype=float)
            observed = m3_joint["joint_weight"].to_numpy(float)
            check(world, "M3", "product_weights",
                  np.allclose(observed, recomputed, atol=EPS, rtol=0))
            check(world, "M3", "weights_sum_one", abs(float(observed.sum())-1) <= EPS)
            check(world, "M3", "descending_joint_rank",
                  np.all(np.diff(observed) <= EPS))
            top14 = load(ROOT / world / "m3_joint_support_top14.csv")
            check(world, "M3", "top14_equals_rank_prefix",
                  top14[ids].astype(str).reset_index(drop=True).equals(
                      m3_joint.head(14)[ids].astype(str).reset_index(drop=True)))

            if world in ELIGIBLE:
                alloc_path = PRED / "_preexecution" / f"m3_fullsupport_allocation_{world}.csv"
                alloc = load(alloc_path)
                alloc = alloc.sort_values("rank").reset_index(drop=True)
                check(world, "M3", "allocation_343_ranks",
                      len(alloc) == 343 and alloc["rank"].astype(int).tolist() == list(range(1,344)))
                counts = alloc["n_trajectories"].astype(int).to_numpy()
                check(world, "M3", "allocation_budget1400_min1",
                      len(counts) == 343 and counts.min() >= 1 and int(counts.sum()) == 1400)
                expected_count = np.ones(343, dtype=int)
                for _ in range(1400-343):
                    delta = observed**2 / (expected_count*(expected_count+1))
                    expected_count[int(np.argmax(delta))] += 1
                check(world, "M3", "allocation_greedy_minimax_reproduced",
                      np.array_equal(counts, expected_count),
                      f"archive_sum={counts.sum()}, expected_sum={expected_count.sum()}")
                check(world, "M3", "rank1_graph_N_ge100",
                      int(counts[0]) >= 100, f"N={counts[0]}")
        except Exception as exc:
            check(world, "EXECUTION", "review_incomplete", False, repr(exc))

    pd.DataFrame(checks).to_csv(OUT / "method_checks.csv", index=False)
    summary = {
        "status": "B1_V3B_MODEL_SUPPORT_AUDIT_FINISHED",
        "no_simulations": True,
        "original_scientific_data_untouched": True,
        "pass": sum(c["result"]=="PASS" for c in checks),
        "fail": sum(c["result"]=="FAIL" for c in checks),
        "scope": "P1–P4 provider candidates, V3b M1/M2/M3 selections and P1/P3/P4 M3 B1400 allocation",
        "limit": "Does not independently rerun candidate optimization or graph simulations; checks saved selection and finite-support algebra only."
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("B1_METHOD_SUPPORT_AUDIT_COMPLETE", summary)
    if args.strict and summary["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
