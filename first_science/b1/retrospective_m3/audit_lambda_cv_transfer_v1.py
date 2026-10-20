#!/usr/bin/env python3
"""No-simulation public-I1 cross-validation audit of pilot lambda=30 transfer.

Reuses the EXACT Phase-4 five-fold blocked-CV implementation on archived candidate
surfaces. It reads public cards but never reads graph, Step-0 or WB outcomes.
The resulting world-specific lambda selections are POST-HOC DIAGNOSTICS, not
new production hyperparameter choices and must not update frozen predictions.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent.parent
P4 = FIRST / "phase4"
P5 = FIRST / "phase5"
RETRO = P5 / "results" / "b1_pilot_m3_retrospective_v1"
P = ("ProviderA", "ProviderB", "ProviderC")
sys.path.insert(0, str(P4))
from m3_lambda_cv_v3 import (  # noqa: E402
    _fold_assignments, _cv_scores, _summarize_cv,
    _select_lambda, _load_candidate_surfaces,
)

LAMBDAS = [0, .25, .5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 75, 100, 150, 200]


def new_world_surfaces(world):
    by_provider = {}
    for provider in P:
        root = RETRO / "candidates" / world / provider
        weights = pd.read_csv(root / "provider_weights.csv")
        assert len(weights) == 48 and weights["candidate_id"].nunique() == 48
        public_path = P5 / "results" / "01_i1" / world / "public" / provider / "sigma_surface.csv"
        reference = pd.read_csv(public_path)
        reference = reference.loc[reference["horizon"].astype(float) > 0].copy()
        reference = reference.sort_values(
            ["region_rho", "rho", "horizon"], kind="mergesort"
        ).reset_index(drop=True)
        if len(reference) != 1200:
            raise RuntimeError(f"{world}/{provider}: expected exactly 1200 I1 points")
        public = reference["sigma_hat"].to_numpy(float)
        if not np.isfinite(public).all():
            raise RuntimeError("Nonfinite public I1")

        by_provider[provider] = {}
        for candidate_id in weights["candidate_id"].astype(str):
            curve = pd.read_csv(root / "surfaces" / (candidate_id + ".csv"))
            if len(curve) != len(public):
                raise RuntimeError(f"{world}/{candidate_id}: curve length mismatch")
            if curve["point_index"].astype(int).tolist() != list(range(len(public))):
                raise RuntimeError("Candidate point-index mismatch")
            cp = curve["sigma_i1"].to_numpy(float)
            cq = curve["sigma_m1_local"].to_numpy(float)
            if not np.allclose(public, cp, rtol=0, atol=1e-12):
                raise RuntimeError(
                    f"{world}/{candidate_id}: public I1 does not align to CV keys"
                )
            pp = (100 * cp + .5) / 101.
            qq = (100 * cq + .5) / 101.
            kl = pp * np.log(pp / qq) + (1 - pp) * np.log((1 - pp) / (1 - qq))
            t = reference[["region_rho", "rho", "horizon"]].copy()
            t["p_i1_jeffreys"] = pp
            t["p_candidate_jeffreys"] = qq
            t["bernoulli_kl_i1_to_candidate"] = kl
            by_provider[provider][candidate_id] = t
    return by_provider


def pilot_surfaces():
    base = P4 / "results" / "m3_local_weighting_v1"
    local = pd.read_csv(base / "m3_local_rescore_results.csv")
    return _load_candidate_surfaces(
        local_results=local, local_surface_root=base / "local_surfaces"
    )


def main(worlds):
    results = []
    t0 = time.monotonic()
    for world in worlds:
        print(f"Checking {world}: public-I1-only five-fold blocked CV...", flush=True)
        surfaces = pilot_surfaces() if world == "P_DEV" else new_world_surfaces(world)
        assignments = _fold_assignments(next(iter(surfaces["ProviderA"].values())))
        table = _cv_scores(
            surfaces=surfaces, assignments=assignments,
            lambda_grid=[float(x) for x in LAMBDAS]
        )
        summary = _summarize_cv(table)
        selected = _select_lambda(summary)
        chosen = summary.loc[np.isclose(summary["lambda"].astype(float), 30.)]
        if len(chosen) != 1:
            raise RuntimeError("Lambda30 missing from fixed CV grid")
        best = float(selected["mean_validation_bernoulli_kl"])
        fixed = float(chosen.iloc[0]["mean_validation_bernoulli_kl"])
        results.append({
            "world": world, "cv_optimal_lambda": float(selected["lambda"]),
            "cv_optimal_kl": best, "lambda30_kl": fixed,
            "excess_lambda30_kl": fixed - best,
            "relative_excess_percent": 100 * (fixed - best) / max(best, 1e-12),
            "lambda30_rank": int(
                summary["mean_validation_bernoulli_kl"].rank(method="min").loc[
                    summary["lambda"].astype(float).eq(30.)
                ].iloc[0]
            )
        })
        print(
            f"  CV lambda={float(selected['lambda']):g}; "
            f"fixed lambda30 CV-KL={fixed:.6f}; "
            f"best CV-KL={best:.6f}; "
            f"excess={fixed-best:.6f}", flush=True
        )

    print("\nPOST-HOC LAMBDA TRANSFER DIAGNOSTIC")
    print(pd.DataFrame(results).round(6).to_string(index=False))
    print(f"\nElapsed {time.monotonic()-t0:.1f}s")
    print("These are public-local holdout scores, not graph-WB performance.")
    print("No simulation, WB access, new method selection, or output files.")
    print("B1_LAMBDA_CV_TRANSFER_AUDIT_COMPLETE")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--worlds", nargs="+",
                   choices=("P_DEV", "P1", "P3", "P4"),
                   default=["P_DEV", "P1", "P3", "P4"])
    a = p.parse_args()
    main(a.worlds)
