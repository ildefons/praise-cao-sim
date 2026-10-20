#!/usr/bin/env python3
"""No-simulation pilot M3 estimator parity, Phase4 versus Phase5 helpers.

Recompute original pilot provider Gibbs weights directly from archived
candidate I1 curves, then reconstruct top-14 joint weighted support using
the current Phase5 helper, and audit greedy B1400 allocation against frozen
pilot design. Do not load graph WB, simulator, Step0 results or alter files.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent.parent
P4 = FIRST / "phase4" / "results"
P5 = FIRST / "phase5"
sys.path.insert(0, str(P5))
from phase5_reconstruction_v3_selection import gibbs_weights, joint_product_support  # noqa: E402

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
BASE = P4 / "m3_local_weighting_v1" / "local_surfaces"
WFILE = P4 / "m3_lambda_cv_v3" / "m3_v3_provider_weights.csv"
D = P4 / "m3_v4_dominant_mass_graph_v1" / "m3_v4_dominant_design.csv"


def allocation(weights, budget=1400):
    w = np.asarray(weights, float)
    n = np.ones(len(w), dtype=int)
    for _ in range(budget - len(w)):
        n[int(np.argmax(w*w/(n*(n+1))))] += 1
    return n


def main():
    old = pd.read_csv(WFILE)
    design = pd.read_csv(D).sort_values("rank").reset_index(drop=True)
    if len(design) != 14:
        raise RuntimeError("Frozen pilot dominant support does not have K14")
    new_tables = {}
    for p in PROVIDERS:
        sub = old.loc[old["provider"].astype(str) == p].copy()
        sub = sub.sort_values("candidate_id", kind="mergesort").reset_index(drop=True)
        if len(sub) != 48:
            raise RuntimeError(f"{p}: missing archived pilot candidates")
        surfaces = []
        public = None
        for cid in sub["candidate_id"].astype(str):
            frame = pd.read_csv(BASE / (cid + "_comparison.csv"))
            x = frame["sigma_i1"].to_numpy(float)
            y = frame["sigma_m1_local"].to_numpy(float)
            if public is None:
                public = x
            elif not np.allclose(x, public, atol=1e-12, rtol=0):
                raise RuntimeError(f"{p}: public I1 alignment mismatch")
            surfaces.append(y)
        t = gibbs_weights(
            sub["candidate_id"].astype(str).tolist(),
            np.stack(surfaces), public,
            n_public=100, n_candidate=100, lam=30.,
        )
        merged = t.merge(
            sub[["candidate_id", "weight_v3"]],
            on="candidate_id", validate="one_to_one"
        )
        diff = np.abs(merged["weight"] - merged["weight_v3"])
        maxdiff = float(diff.max())
        if maxdiff > 1e-10:
            raise RuntimeError(f"{p}: Gibbs weight mismatch max={maxdiff}")
        print(f"MATCH pilot weights {p}: maxdiff={maxdiff:.3g}", flush=True)
        new_tables[p] = t[["candidate_id", "weight"]]

    joint = joint_product_support(new_tables)
    top = joint.head(14).copy().reset_index(drop=True)
    joint_weight_diff = []
    for i, rec in enumerate(design.itertuples(index=False)):
        nr = top.iloc[i]
        expected = [str(getattr(rec, p + "_candidate_id")) for p in PROVIDERS]
        actual = [str(nr[p + "_candidate_id"]) for p in PROVIDERS]
        if expected != actual:
            raise RuntimeError(f"Pilot rank {i+1}: selected candidate IDs differ: "
                               f"{expected} != {actual}")
        joint_weight_diff.append(abs(float(rec.joint_weight) - float(nr.joint_weight)))
    mass = float(top["joint_weight"].sum())
    a = top["joint_weight"].to_numpy(float) / mass
    archived_a = design["alpha_renormalized"].to_numpy(float)
    if not np.allclose(a, archived_a, atol=1e-10, rtol=0):
        raise RuntimeError("Archived pilot normalized alpha differs")
    current_alloc = allocation(a, 1400)
    archived_alloc = design["n_B1400"].to_numpy(int)
    if not np.array_equal(current_alloc, archived_alloc):
        raise RuntimeError(f"Pilot allocation differs: {current_alloc} != {archived_alloc}")
    if abs(mass - 0.9991741970173574) > 1e-8:
        raise RuntimeError(f"Pilot retained mass differs: {mass}")
    print(f"MATCH pilot Top14 member identities and order: 14/14")
    print(f"MATCH pilot joint weights, maximum abs difference="
          f"{max(joint_weight_diff):.3g}")
    print(f"MATCH pilot retained mass={mass:.12f}")
    print(f"MATCH pilot renormalized alpha and B1400 allocations "
          f"(total={int(current_alloc.sum())})")
    print("This is mathematical estimator/archived-input parity, not graph-runtime")
    print("or white-box accuracy parity. No files written, no simulations.")
    print("B1_PILOT_M3_ESTIMATOR_PARITY_PASS")


if __name__ == "__main__":
    main()
