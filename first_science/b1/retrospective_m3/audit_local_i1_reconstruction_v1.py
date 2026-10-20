#!/usr/bin/env python3
"""Read-only local public-I1 reconstruction audit: Phase-4 pilot vs P1/P3/P4.

This checks whether the weighted candidate mixtures still fit their own public
I1 surfaces. It runs NO simulator and does NOT read Step-0 or graph WB evidence.
It does not change any original prediction, candidate or result file.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent.parent
P4 = FIRST / "phase4" / "results"
RETRO = FIRST / "phase5" / "results" / "b1_pilot_m3_retrospective_v1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
WORLDS = ("P_DEV", "P1", "P3", "P4")


def weight_and_surface_paths(world: str, provider: str):
    if world == "P_DEV":
        weights_file = P4 / "m3_lambda_cv_v3" / "m3_v3_provider_weights.csv"
        surface_root = P4 / "m3_local_weighting_v1" / "local_surfaces"
    else:
        parent = RETRO / "candidates" / world / provider
        weights_file = parent / "provider_weights.csv"
        surface_root = parent / "surfaces"
    return weights_file, surface_root


def evaluate(world: str, provider: str) -> dict:
    weights_file, surface_root = weight_and_surface_paths(world, provider)
    if not weights_file.is_file():
        raise FileNotFoundError(f"Required frozen weights not found: {weights_file}")
    frame = pd.read_csv(weights_file)
    if world == "P_DEV":
        frame = frame[frame["provider"].astype(str) == provider].copy()
        weight_col = "weight_v3"
        energy_col = "mean_bernoulli_kl"
        mse_col = "mse"
    else:
        weight_col = "weight"
        energy_col = "kl_energy"
        mse_col = "local_mse"
    if len(frame) != 48 or frame["candidate_id"].nunique() != 48:
        raise RuntimeError(f"{world}/{provider}: expected 48 distinct candidates")
    frame = frame.sort_values(["candidate_id"], kind="mergesort").reset_index(drop=True)
    w = frame[weight_col].to_numpy(float)
    energies = frame[energy_col].to_numpy(float)
    mse_local = frame[mse_col].to_numpy(float)
    if not (np.isfinite(w).all() and (w >= 0).all() and np.isclose(w.sum(), 1, atol=1e-8)):
        raise RuntimeError(f"{world}/{provider}: provider Gibbs weights invalid")
    if not (np.isfinite(energies).all() and np.isfinite(mse_local).all()):
        raise RuntimeError(f"{world}/{provider}: local candidate objectives invalid")

    surface_matrix = []
    public = None
    for cid in frame["candidate_id"].astype(str):
        file = surface_root / (cid + ("_comparison.csv" if world == "P_DEV" else ".csv"))
        if not file.is_file():
            raise FileNotFoundError(f"Missing archived local candidate curve: {file}")
        dat = pd.read_csv(file, usecols=["sigma_i1", "sigma_m1_local"])
        p = dat["sigma_i1"].to_numpy(float)
        q = dat["sigma_m1_local"].to_numpy(float)
        if public is None:
            public = p
        elif len(p) != len(public) or not np.allclose(
            public, p, rtol=0, atol=1e-12
        ):
            raise RuntimeError(f"{world}/{provider}: candidate surfaces are misaligned")
        surface_matrix.append(q)
    assert public is not None
    matrix = np.stack(surface_matrix, axis=0)
    if not (np.isfinite(matrix).all() and
            ((matrix >= 0) & (matrix <= 1)).all() and
            ((public >= 0) & (public <= 1)).all()):
        raise RuntimeError(f"{world}/{provider}: probability range invalid")

    full_mix = w @ matrix
    order = np.argsort(-w, kind="stable")
    top1 = matrix[order[0]]
    k = 14
    top14_weight = w[order[:k]]
    top14_local_mix = np.sum(
        matrix[order[:k]] * (top14_weight / top14_weight.sum())[:, None],
        axis=0,
    )

    def mae(q):
        return float(np.mean(np.abs(q - public)))

    return {
        "world": world, "provider": provider,
        "local_points": len(public), "best_kl": float(energies.min()),
        "best_candidate_local_mse": float(mse_local.min()),
        "top1_local_mse": float(mse_local[order[0]]),
        "top1_local_mae": mae(top1),
        "top14_local_mae": mae(top14_local_mix),
        "full48_local_mae": mae(full_mix),
        "full48_local_bias": float(np.mean(full_mix - public)),
        "full48_local_rmse": float(np.sqrt(np.mean((full_mix - public)**2))),
        "provider_ess": float(1.0 / np.sum(w*w)),
        "top1_weight": float(w[order[0]]),
        "top14_weight_mass": float(top14_weight.sum()),
        "top1_mu": float(frame.iloc[order[0]]["mean_service_time"]),
        "top1_kappa": float(frame.iloc[order[0]]["cost_rate"]),
        "top1_cv": float(frame.iloc[order[0]]["service_cv"]),
    }


def main(worlds: list[str]):
    rows = []
    for world in worlds:
        for provider in PROVIDERS:
            print(f"Reading {world}/{provider} frozen public-I1 evidence...", flush=True)
            rows.append(evaluate(world, provider))
    t = pd.DataFrame(rows)
    cols = [
        "world", "provider", "local_points", "best_kl",
        "top1_local_mae", "top14_local_mae", "full48_local_mae",
        "full48_local_bias", "full48_local_rmse",
        "provider_ess", "top1_weight", "top14_weight_mass"
    ]
    with pd.option_context("display.width", 170, "display.max_columns", 20):
        print("\nLOCAL I1 RECONSTRUCTION: pilot versus new worlds")
        print(t[cols].round(6).to_string(index=False))
        print("\nTOP1 SURROGATE PARAMETERS")
        print(t[["world", "provider", "top1_mu", "top1_kappa", "top1_cv",
                 "top1_local_mse", "best_candidate_local_mse"]]
              .round(6).to_string(index=False))
    print("\nInterpretation: all errors are against each world's PUBLIC local I1 curve.")
    print("Do not compare them to graph white-box error or interpret Top14 local")
    print("provider mixtures as the same object as the 14-member joint graph mixture.")
    print("No simulator or white-box evidence accessed. No files changed.")
    print("B1_LOCAL_I1_RECONSTRUCTION_AUDIT_COMPLETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worlds", nargs="+", choices=WORLDS, default=WORLDS)
    args = parser.parse_args()
    main(args.worlds)
