"""Audit concentration of the frozen M3-v1 local Gibbs distribution.

Reads only already-materialized M3 local outputs. No provider or graph simulation,
no graph prediction read, and no white-box read.
"""
from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _ess(w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    w = w / w.sum()
    return float(1.0 / np.sum(w * w))


def _entropy(w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    w = w / w.sum()
    nz = w > 0
    return float(-np.sum(w[nz] * np.log(w[nz])))


def _n_for_mass(w: np.ndarray, target: float) -> int:
    s = np.sort(np.asarray(w, dtype=float))[::-1]
    return int(np.searchsorted(np.cumsum(s), float(target), side="left") + 1)


def _softmax_energy(energy: np.ndarray, beta: float) -> np.ndarray:
    logu = -float(beta) * np.asarray(energy, dtype=float)
    logu -= np.max(logu)
    u = np.exp(logu)
    return u / u.sum()


def _expected_unique(prob: np.ndarray, k: int) -> float:
    p = np.asarray(prob, dtype=float)
    return float(np.sum(1.0 - np.power(1.0 - p, int(k))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=HERE / "results" / "m3_local_weighting_v1",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    weights = pd.read_csv(root / "m3_provider_weights.csv")
    local = pd.read_csv(root / "m3_local_rescore_results.csv")
    recon = pd.read_csv(root / "m3_weighted_i1_reconstruction_summary.csv")
    draws = pd.read_csv(root / "m3_joint_latent_draws_200.csv")

    beta_grid = [0, 1, 2, 5, 10, 20, 50, 100]

    print("M3_V1_PROVIDER_CONCENTRATION_AUDIT")
    provider_tables: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        g = weights[weights["provider"].astype(str) == provider].copy()
        g = g.sort_values("weight", ascending=False).reset_index(drop=True)
        provider_tables[provider] = g
        w = g["weight"].to_numpy(float)
        e = g["mean_bernoulli_kl"].to_numpy(float)

        print(f"\n{provider}")
        print(
            f"ESS={_ess(w):.6f} entropy={_entropy(w):.6f} "
            f"n50={_n_for_mass(w,0.50)} n90={_n_for_mass(w,0.90)} "
            f"n95={_n_for_mass(w,0.95)} n99={_n_for_mass(w,0.99)}"
        )
        cols = [
            "candidate_id",
            "weight",
            "mean_bernoulli_kl",
            "mse",
            "mae",
            "bias",
            "mean_service_time",
            "cost_rate",
            "service_cv",
        ]
        print("Top weights:")
        print(g[cols].head(8).to_string(index=False))

        print("ESS versus Gibbs beta:")
        rows = []
        # use candidate energies sorted independently of frozen weight
        base = local[local["provider"].astype(str) == provider].copy()
        energy = base["mean_bernoulli_kl"].to_numpy(float)
        for beta in beta_grid:
            wb = _softmax_energy(energy, beta)
            rows.append(
                {
                    "beta": beta,
                    "ESS": _ess(wb),
                    "max_weight": float(np.max(wb)),
                    "n95": _n_for_mass(wb, 0.95),
                }
            )
        print(pd.DataFrame(rows).to_string(index=False))

    # Exact finite joint distribution over 48^3 combinations.
    a = provider_tables["ProviderA"]
    b = provider_tables["ProviderB"]
    c = provider_tables["ProviderC"]
    joint_rows = []
    for ia, ib, ic in product(range(len(a)), range(len(b)), range(len(c))):
        pa = float(a.iloc[ia]["weight"])
        pb = float(b.iloc[ib]["weight"])
        pc = float(c.iloc[ic]["weight"])
        p = pa * pb * pc
        joint_rows.append(
            (
                p,
                str(a.iloc[ia]["candidate_id"]),
                str(b.iloc[ib]["candidate_id"]),
                str(c.iloc[ic]["candidate_id"]),
            )
        )
    joint = pd.DataFrame(
        joint_rows, columns=["probability", "A", "B", "C"]
    ).sort_values("probability", ascending=False, ignore_index=True)
    jp = joint["probability"].to_numpy(float)

    print("\nJOINT_DISTRIBUTION")
    print(
        f"support={len(joint)} ESS={_ess(jp):.6f} "
        f"n50={_n_for_mass(jp,0.50)} n90={_n_for_mass(jp,0.90)} "
        f"n95={_n_for_mass(jp,0.95)} n99={_n_for_mass(jp,0.99)}"
    )
    print(
        f"expected_unique_K100={_expected_unique(jp,100):.4f} "
        f"expected_unique_K200={_expected_unique(jp,200):.4f}"
    )
    print("Top joint masses:")
    print(joint.head(10).to_string(index=False))

    print("\nACTUAL_FROZEN_200_DRAW_BANK")
    counts = (
        draws.groupby("joint_latent_id")
        .size()
        .rename("count")
        .sort_values(ascending=False)
        .reset_index()
    )
    counts["fraction"] = counts["count"] / float(len(draws))
    print(counts.head(15).to_string(index=False))

    print("\nWEIGHTED_I1_RECONSTRUCTION")
    print(recon.to_string(index=False))
    print("\nM3_V1_CONCENTRATION_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
