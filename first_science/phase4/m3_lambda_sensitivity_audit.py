#!/usr/bin/env python3
"""Post-hoc public-I1-only sensitivity audit for the frozen M3 Gibbs lambda.

No graph prediction, graph white box, provider resimulation, candidate
generation, or method re-selection is performed.

The audit reuses:
  * frozen public-I1 local candidate energies,
  * frozen blocked-CV summary over the predeclared lambda grid.

For each lambda it reports predictive CV score and the induced finite-weight
concentration: provider ESS, joint ESS, maximum joint weight, and the number
of joint hypotheses required to retain 99.9% mass.

Because one positive global lambda multiplies the same full-surface candidate
energies, the ranking of joint hypotheses is invariant for lambda > 0. Lambda
changes concentration and therefore K_99.9, not the energy ordering.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from m2_b2_remote_graph import _sha256, _write_json

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TARGET_MASS = 0.999
TOL = 1e-12


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _weights(energy: np.ndarray, lam: float) -> np.ndarray:
    z = -float(lam) * np.asarray(energy, dtype=float)
    z = z - np.max(z)
    w = np.exp(z)
    return w / np.sum(w)


def _ess(w: np.ndarray) -> float:
    return float(1.0 / np.sum(np.square(w)))


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()

    contract_path = args.contract.resolve()
    local_path = args.local_results.resolve()
    cv_path = args.cv_summary.resolve()

    contract = _read_json(contract_path)
    lambda_grid = [float(x) for x in contract["lambda_grid"]]
    selected_lambda = float(args.selected_lambda)

    local = pd.read_csv(local_path)
    cv = pd.read_csv(cv_path)
    required_local = {"provider", "candidate_id", "mean_bernoulli_kl"}
    missing = sorted(required_local.difference(local.columns))
    if missing:
        raise RuntimeError("local M3 results missing: " + ", ".join(missing))

    cv_lambdas = sorted(cv["lambda"].astype(float).tolist())
    if not np.allclose(cv_lambdas, sorted(lambda_grid), atol=TOL, rtol=0.0):
        raise RuntimeError("CV summary lambda grid differs from frozen contract")
    if not any(np.isclose(selected_lambda, x, atol=TOL, rtol=0.0) for x in lambda_grid):
        raise RuntimeError("selected lambda is not on frozen grid")

    energies: dict[str, np.ndarray] = {}
    candidate_ids: dict[str, list[str]] = {}
    for provider in PROVIDERS:
        g = (
            local[local["provider"].astype(str) == provider]
            .sort_values("candidate_id")
            .reset_index(drop=True)
        )
        if len(g) != 48:
            raise RuntimeError(f"{provider}: expected 48 candidates, found {len(g)}")
        energies[provider] = g["mean_bernoulli_kl"].astype(float).to_numpy()
        candidate_ids[provider] = g["candidate_id"].astype(str).tolist()

    # Full joint energy determines the rank for every lambda > 0.
    eA, eB, eC = (energies[p] for p in PROVIDERS)
    joint_energy = (
        eA[:, None, None] + eB[None, :, None] + eC[None, None, :]
    ).reshape(-1)
    order = np.argsort(joint_energy, kind="mergesort")

    selected_rank_prefix14 = order[:14].copy()
    rows: list[dict[str, Any]] = []

    cv_by_lambda = cv.set_index("lambda")
    for lam in lambda_grid:
        provider_weights = {p: _weights(energies[p], lam) for p in PROVIDERS}
        provider_ess = {p: _ess(provider_weights[p]) for p in PROVIDERS}
        provider_max = {p: float(np.max(provider_weights[p])) for p in PROVIDERS}

        joint = (
            provider_weights["ProviderA"][:, None, None]
            * provider_weights["ProviderB"][None, :, None]
            * provider_weights["ProviderC"][None, None, :]
        ).reshape(-1)

        if lam > 0:
            ranked = joint[order]
            top14_identity_stable = True
        else:
            # Uniform lambda=0 has no unique energy-induced mass ranking.
            ranked = np.sort(joint)[::-1]
            top14_identity_stable = False

        cumulative = np.cumsum(ranked)
        k999 = int(np.searchsorted(cumulative, TARGET_MASS, side="left") + 1)
        retained_mass = float(cumulative[k999 - 1])

        cvrow = cv_by_lambda.loc[lam]
        rows.append({
            "lambda": float(lam),
            "selected_lambda": bool(np.isclose(lam, selected_lambda)),
            "mean_validation_bernoulli_kl": float(
                cvrow["mean_validation_bernoulli_kl"]
            ),
            "median_validation_bernoulli_kl": float(
                cvrow["median_validation_bernoulli_kl"]
            ),
            "mean_validation_mse": float(cvrow["mean_validation_mse"]),
            "ProviderA_ESS": provider_ess["ProviderA"],
            "ProviderB_ESS": provider_ess["ProviderB"],
            "ProviderC_ESS": provider_ess["ProviderC"],
            "joint_ESS": float(np.prod(list(provider_ess.values()))),
            "ProviderA_max_weight": provider_max["ProviderA"],
            "ProviderB_max_weight": provider_max["ProviderB"],
            "ProviderC_max_weight": provider_max["ProviderC"],
            "max_joint_weight": float(np.max(joint)),
            "top3_joint_mass": float(np.sum(ranked[:3])),
            "top14_joint_mass": float(np.sum(ranked[:14])),
            "K_99_9pct": int(k999),
            "retained_mass_at_K": retained_mass,
            "omitted_mass_at_K": float(1.0 - retained_mass),
            "top14_identity_stable_vs_lambda30": top14_identity_stable,
        })

    out = pd.DataFrame(rows).sort_values("lambda").reset_index(drop=True)
    best_kl = float(out["mean_validation_bernoulli_kl"].min())
    out["cv_KL_excess_over_best"] = out["mean_validation_bernoulli_kl"] - best_kl
    out["cv_KL_ratio_to_best"] = out["mean_validation_bernoulli_kl"] / best_kl

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    table_path = output / "m3_lambda_public_i1_sensitivity.csv"
    out.to_csv(table_path, index=False)

    # Plot 1: public-I1 CV score only.
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(
        out["lambda"].astype(float),
        out["mean_validation_bernoulli_kl"].astype(float),
        marker="o",
    )
    ax.axvline(selected_lambda, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Gibbs concentration lambda")
    ax.set_ylabel("Mean held-out Bernoulli KL")
    ax.set_title("Public-I1 blocked-CV sensitivity")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    cv_fig = output / "m3_lambda_cv_sensitivity.png"
    fig.savefig(cv_fig, dpi=220)
    plt.close(fig)

    # Plot 2: concentration / retained support.
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    positive = out["lambda"].astype(float) > 0
    ax.plot(
        out.loc[positive, "lambda"].astype(float),
        out.loc[positive, "K_99_9pct"].astype(float),
        marker="o",
    )
    ax.axvline(selected_lambda, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Gibbs concentration lambda")
    ax.set_ylabel("Joint hypotheses needed for 99.9% mass")
    ax.set_title("M3 dominant-mass support sensitivity")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    mass_fig = output / "m3_lambda_K999_sensitivity.png"
    fig.savefig(mass_fig, dpi=220)
    plt.close(fig)

    selected = out[np.isclose(out["lambda"].astype(float), selected_lambda)]
    if len(selected) != 1:
        raise RuntimeError("selected lambda row is not unique")

    manifest = {
        "status": "POSTHOC_M3_PUBLIC_I1_LAMBDA_SENSITIVITY_COMPLETE_V1",
        "scientific_role": (
            "Public-I1-only robustness characterization of frozen lambda; "
            "not model re-selection and not graph-WB tuning."
        ),
        "contract_sha256": _sha256(contract_path),
        "local_results_sha256": _sha256(local_path),
        "cv_summary_sha256": _sha256(cv_path),
        "selected_lambda": selected_lambda,
        "lambda_grid": lambda_grid,
        "target_retained_mass": TARGET_MASS,
        "joint_hypotheses": 48 ** 3,
        "positive_lambda_joint_rank_invariance": True,
        "provider_resimulation": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "lambda_changed": False,
        "M3_changed": False,
        "output_table_sha256": _sha256(table_path),
        "python_wall_seconds": float(time.perf_counter() - started),
    }
    manifest_path = output / "m3_lambda_public_i1_sensitivity_manifest.json"
    _write_json(manifest_path, manifest)

    show_cols = [
        "lambda", "mean_validation_bernoulli_kl", "joint_ESS",
        "max_joint_weight", "top3_joint_mass", "top14_joint_mass",
        "K_99_9pct", "selected_lambda",
    ]
    print("\nM3_PUBLIC_I1_LAMBDA_SENSITIVITY")
    print(out[show_cols].to_string(index=False))
    print("\nPOSTHOC_M3_PUBLIC_I1_LAMBDA_SENSITIVITY_COMPLETE")
    print(f"table={table_path}")
    print(f"cv_figure={cv_fig}")
    print(f"mass_figure={mass_fig}")
    print(f"manifest={manifest_path}")
    print(
        "NOTE: no graph prediction or white-box result is used in this audit; "
        "the frozen lambda remains 30."
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Public-I1-only sensitivity audit of the frozen M3 lambda"
    )
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_lambda_cv_v3.json",
    )
    p.add_argument(
        "--local-results",
        type=Path,
        default=HERE / "results" / "m3_local_weighting_v1"
        / "m3_local_rescore_results.csv",
    )
    p.add_argument(
        "--cv-summary",
        type=Path,
        default=HERE / "results" / "m3_lambda_cv_v3"
        / "m3_lambda_cv_summary.csv",
    )
    p.add_argument("--selected-lambda", type=float, default=30.0)
    p.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "m3_lambda_sensitivity_audit_v1",
    )
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
