"""Select M3 Gibbs concentration lambda using public-I1-only blocked CV.

This script runs NO simulation. It reuses the already-generated M3-v1 local
candidate comparison surfaces and performs structural holdout cross-validation
over complete (region_rho, query_rho) horizon curves.

After selecting one global lambda, it materializes full-surface provider weights
and one ordered bank of 200 joint latent draws for the later graph experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_STATUS = "FROZEN_PHASE4_M3_LAMBDA_CV_V3"
EXPECTED_V1_STATUS = "FROZEN_PHASE4_M3_WEIGHTED_PROVIDER_DISTRIBUTION_AND_JOINT_BANK_V1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        return None


def _bernoulli_kl(p: np.ndarray, r: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    r = np.asarray(r, dtype=float)
    eps = 1e-15
    p = np.clip(p, eps, 1.0 - eps)
    r = np.clip(r, eps, 1.0 - eps)
    return p * np.log(p / r) + (1.0 - p) * np.log((1.0 - p) / (1.0 - r))


def _normalize_logweights(logu: np.ndarray) -> np.ndarray:
    z = np.asarray(logu, dtype=float)
    z = z - np.max(z)
    u = np.exp(z)
    return u / np.sum(u)


def _ess(w: np.ndarray) -> float:
    return float(1.0 / np.sum(np.square(np.asarray(w, dtype=float))))


def _entropy(w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    nz = w > 0
    return float(-np.sum(w[nz] * np.log(w[nz])))


def _n_for_mass(w: np.ndarray, target: float) -> int:
    s = np.sort(np.asarray(w, dtype=float))[::-1]
    return int(np.searchsorted(np.cumsum(s), float(target), side="left") + 1)


def _load_candidate_surfaces(
    *,
    local_results: pd.DataFrame,
    local_surface_root: Path,
) -> dict[str, dict[str, pd.DataFrame]]:
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for provider in PROVIDERS:
        provider_results = local_results[
            local_results["provider"].astype(str) == provider
        ].copy()
        if len(provider_results) != 48:
            raise RuntimeError(
                f"{provider}: expected 48 candidate results, found {len(provider_results)}"
            )
        out[provider] = {}
        for rec in provider_results.itertuples(index=False):
            candidate_id = str(rec.candidate_id)
            path = local_surface_root / f"{candidate_id}_comparison.csv"
            if not path.exists():
                raise FileNotFoundError(path)
            frame = pd.read_csv(path)
            required = {
                "region_rho",
                "rho",
                "horizon",
                "p_i1_jeffreys",
                "p_candidate_jeffreys",
                "bernoulli_kl_i1_to_candidate",
            }
            missing = sorted(required.difference(frame.columns))
            if missing:
                raise RuntimeError(
                    f"{candidate_id}: missing comparison fields {missing}"
                )
            out[provider][candidate_id] = frame.copy()
    return out


def _fold_assignments(reference: pd.DataFrame) -> pd.DataFrame:
    region_values = sorted(reference["region_rho"].astype(float).unique())
    query_values = sorted(reference["rho"].astype(float).unique())
    if len(region_values) != 5 or len(query_values) != 5:
        raise RuntimeError(
            f"expected 5x5 rho support, found {len(region_values)}x{len(query_values)}"
        )

    region_map = {float(v): i for i, v in enumerate(region_values)}
    query_map = {float(v): i for i, v in enumerate(query_values)}

    cells = (
        reference[["region_rho", "rho"]]
        .drop_duplicates()
        .sort_values(["region_rho", "rho"])
        .reset_index(drop=True)
    )
    cells["region_rho_ordinal"] = cells["region_rho"].astype(float).map(region_map)
    cells["query_rho_ordinal"] = cells["rho"].astype(float).map(query_map)
    cells["fold"] = (
        cells["region_rho_ordinal"].astype(int)
        + cells["query_rho_ordinal"].astype(int)
    ) % 5

    counts = cells.groupby("fold").size()
    if not (counts == 5).all():
        raise RuntimeError("each CV fold must contain exactly 5 curve cells")
    for fold in range(5):
        g = cells[cells["fold"] == fold]
        if g["region_rho_ordinal"].nunique() != 5:
            raise RuntimeError(f"fold {fold}: region_rho coverage is not Latin-balanced")
        if g["query_rho_ordinal"].nunique() != 5:
            raise RuntimeError(f"fold {fold}: query_rho coverage is not Latin-balanced")
    return cells


def _attach_fold(frame: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    out = frame.merge(
        assignments[["region_rho", "rho", "fold"]],
        on=["region_rho", "rho"],
        how="left",
        validate="many_to_one",
    )
    if out["fold"].isna().any():
        raise RuntimeError("failed to assign CV fold to some surface points")
    out["fold"] = out["fold"].astype(int)
    return out


def _cv_scores(
    *,
    surfaces: dict[str, dict[str, pd.DataFrame]],
    assignments: pd.DataFrame,
    lambda_grid: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        candidate_ids = sorted(surfaces[provider])
        attached = {
            cid: _attach_fold(surfaces[provider][cid], assignments)
            for cid in candidate_ids
        }

        # Verify pointwise public target is identical across candidate files.
        base = attached[candidate_ids[0]].sort_values(
            ["region_rho", "rho", "horizon"]
        ).reset_index(drop=True)
        for cid in candidate_ids[1:]:
            g = attached[cid].sort_values(
                ["region_rho", "rho", "horizon"]
            ).reset_index(drop=True)
            if not np.allclose(
                base["p_i1_jeffreys"].to_numpy(float),
                g["p_i1_jeffreys"].to_numpy(float),
                atol=1e-14,
                rtol=0.0,
            ):
                raise RuntimeError(f"{provider}: public I1 target differs across {cid}")

        for fold in range(5):
            train_energy = []
            valid_predictions = []
            valid_target = None

            for cid in candidate_ids:
                g = attached[cid]
                train = g[g["fold"] != fold]
                valid = g[g["fold"] == fold].sort_values(
                    ["region_rho", "rho", "horizon"]
                )
                train_energy.append(
                    float(train["bernoulli_kl_i1_to_candidate"].mean())
                )
                pred = valid["p_candidate_jeffreys"].to_numpy(float)
                valid_predictions.append(pred)
                target = valid["p_i1_jeffreys"].to_numpy(float)
                if valid_target is None:
                    valid_target = target
                elif not np.allclose(valid_target, target, atol=1e-14, rtol=0.0):
                    raise RuntimeError(
                        f"{provider} fold {fold}: validation target mismatch"
                    )

            energy = np.asarray(train_energy, dtype=float)
            pred_matrix = np.vstack(valid_predictions)
            assert valid_target is not None

            for lam in lambda_grid:
                w = _normalize_logweights(-float(lam) * energy)
                mix = np.sum(w[:, None] * pred_matrix, axis=0)
                kl = _bernoulli_kl(valid_target, mix)
                mse = np.square(valid_target - mix)
                rows.append(
                    {
                        "provider": provider,
                        "fold": int(fold),
                        "lambda": float(lam),
                        "validation_mean_bernoulli_kl": float(np.mean(kl)),
                        "validation_mse": float(np.mean(mse)),
                        "train_weight_ess": _ess(w),
                        "train_weight_entropy": _entropy(w),
                        "train_weight_max": float(np.max(w)),
                        "n_validation_points": int(len(valid_target)),
                    }
                )

    return pd.DataFrame(rows)


def _summarize_cv(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lam, g in scores.groupby("lambda", sort=True):
        # Equal provider-fold weighting because each cell contains the same number of points.
        vals = g["validation_mean_bernoulli_kl"].to_numpy(float)
        mse_vals = g["validation_mse"].to_numpy(float)
        rows.append(
            {
                "lambda": float(lam),
                "mean_validation_bernoulli_kl": float(np.mean(vals)),
                "median_validation_bernoulli_kl": float(np.median(vals)),
                "mean_validation_mse": float(np.mean(mse_vals)),
                "mean_train_weight_ess": float(g["train_weight_ess"].mean()),
                "min_train_weight_ess": float(g["train_weight_ess"].min()),
                "max_train_weight": float(g["train_weight_max"].max()),
                "n_provider_fold_cells": int(len(g)),
            }
        )
    return pd.DataFrame(rows).sort_values("lambda").reset_index(drop=True)


def _select_lambda(summary: pd.DataFrame) -> pd.Series:
    best_score = float(summary["mean_validation_bernoulli_kl"].min())
    tied = summary[
        np.abs(summary["mean_validation_bernoulli_kl"] - best_score) <= 1e-12
    ].sort_values("lambda")
    if tied.empty:
        raise RuntimeError("lambda selection produced no candidate")
    return tied.iloc[0]


def _full_weights(
    *,
    local_results: pd.DataFrame,
    selected_lambda: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    diagnostics = []

    for provider in PROVIDERS:
        g = local_results[local_results["provider"].astype(str) == provider].copy()
        e = g["mean_bernoulli_kl"].to_numpy(float)
        w = _normalize_logweights(-float(selected_lambda) * e)
        g["lambda"] = float(selected_lambda)
        g["weight_v3"] = w
        g["log_weight_v3"] = np.log(w)
        frames.append(g)

        ent = _entropy(w)
        diagnostics.append(
            {
                "provider": provider,
                "lambda": float(selected_lambda),
                "effective_sample_size": _ess(w),
                "entropy_nats": ent,
                "perplexity": float(math.exp(ent)),
                "max_weight": float(np.max(w)),
                "min_weight": float(np.min(w)),
                "n50": _n_for_mass(w, 0.50),
                "n90": _n_for_mass(w, 0.90),
                "n95": _n_for_mass(w, 0.95),
                "n99": _n_for_mass(w, 0.99),
            }
        )

    weights = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["provider", "lhs_index"])
        .reset_index(drop=True)
    )
    diag = pd.DataFrame(diagnostics)
    diag = pd.concat(
        [
            diag,
            pd.DataFrame(
                [
                    {
                        "provider": "JOINT_PRODUCT",
                        "lambda": float(selected_lambda),
                        "effective_sample_size": float(
                            np.prod(diag["effective_sample_size"].to_numpy(float))
                        ),
                        "entropy_nats": float(diag["entropy_nats"].sum()),
                        "perplexity": float(
                            np.prod(diag["perplexity"].to_numpy(float))
                        ),
                        "max_weight": float(
                            np.prod(diag["max_weight"].to_numpy(float))
                        ),
                        "min_weight": float(
                            np.prod(diag["min_weight"].to_numpy(float))
                        ),
                        "n50": np.nan,
                        "n90": np.nan,
                        "n95": np.nan,
                        "n99": np.nan,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return weights, diag


def _weighted_reconstruction(
    *,
    weights: pd.DataFrame,
    surfaces: dict[str, dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = []
    for provider in PROVIDERS:
        wp = weights[weights["provider"].astype(str) == provider]
        for rec in wp.itertuples(index=False):
            g = surfaces[provider][str(rec.candidate_id)].copy()
            g["provider"] = provider
            g["candidate_id"] = str(rec.candidate_id)
            g["component_weight"] = float(rec.weight_v3)
            g["weighted_probability"] = (
                g["p_candidate_jeffreys"].astype(float) * float(rec.weight_v3)
            )
            all_rows.append(g)

    all_points = pd.concat(all_rows, ignore_index=True)
    keys = ["provider", "region_rho", "rho", "horizon"]
    recon = (
        all_points.groupby(keys, as_index=False)
        .agg(
            p_i1_jeffreys=("p_i1_jeffreys", "first"),
            p_m3_v3_weighted=("weighted_probability", "sum"),
            weight_sum=("component_weight", "sum"),
        )
        .sort_values(keys)
        .reset_index(drop=True)
    )
    if not np.allclose(recon["weight_sum"], 1.0, atol=1e-10, rtol=0.0):
        raise RuntimeError("full M3-v3 provider weights do not sum to one")

    recon["bernoulli_kl"] = _bernoulli_kl(
        recon["p_i1_jeffreys"].to_numpy(float),
        recon["p_m3_v3_weighted"].to_numpy(float),
    )
    recon["error"] = (
        recon["p_m3_v3_weighted"].astype(float)
        - recon["p_i1_jeffreys"].astype(float)
    )
    recon["squared_error"] = np.square(recon["error"].to_numpy(float))

    summaries = []
    for provider in PROVIDERS:
        g = recon[recon["provider"].astype(str) == provider]
        e = g["error"].to_numpy(float)
        summaries.append(
            {
                "provider": provider,
                "n_points": int(len(g)),
                "mean_bernoulli_kl": float(g["bernoulli_kl"].mean()),
                "mse": float(np.mean(np.square(e))),
                "rmse": float(np.sqrt(np.mean(np.square(e)))),
                "mae": float(np.mean(np.abs(e))),
                "bias": float(np.mean(e)),
                "max_abs_error": float(np.max(np.abs(e))),
            }
        )
    return recon, pd.DataFrame(summaries)


def _sample_joint_bank(
    *,
    weights: pd.DataFrame,
    k: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(seed))
    by_provider = {}
    chosen = {}

    for provider in PROVIDERS:
        g = (
            weights[weights["provider"].astype(str) == provider]
            .sort_values("lhs_index")
            .reset_index(drop=True)
        )
        p = g["weight_v3"].to_numpy(float)
        by_provider[provider] = g
        chosen[provider] = rng.choice(len(g), size=int(k), replace=True, p=p)

    rows = []
    for draw_id in range(int(k)):
        row: dict[str, Any] = {
            "joint_draw_id": int(draw_id),
            "m3_100x20_member": bool(draw_id < 100),
            "m3_200x10_member": True,
            "monte_carlo_draw_weight_K100": 0.01 if draw_id < 100 else np.nan,
            "monte_carlo_draw_weight_K200": 0.005,
        }
        ids = []
        target_mass = 1.0
        for provider in PROVIDERS:
            rec = by_provider[provider].iloc[int(chosen[provider][draw_id])]
            prefix = provider.replace("Provider", "").lower()
            row[f"{prefix}_candidate_id"] = str(rec["candidate_id"])
            row[f"{prefix}_lhs_index"] = int(rec["lhs_index"])
            row[f"{prefix}_mean_service_time"] = float(rec["mean_service_time"])
            row[f"{prefix}_cost_rate"] = float(rec["cost_rate"])
            row[f"{prefix}_service_cv"] = float(rec["service_cv"])
            row[f"{prefix}_provider_weight"] = float(rec["weight_v3"])
            target_mass *= float(rec["weight_v3"])
            ids.append(str(rec["candidate_id"]))
        row["joint_target_mass"] = float(target_mass)
        row["joint_latent_id"] = "|".join(ids)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="M3 public-I1-only lambda CV")
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_lambda_cv_v3.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_lambda_cv_v3",
    )
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M3 lambda-CV contract status")

    inputs = dict(contract["inputs"])
    v1_manifest_path = (HERE / str(inputs["v1_manifest"])).resolve()
    local_results_path = (HERE / str(inputs["v1_local_results"])).resolve()
    local_surface_root = (HERE / str(inputs["v1_local_surfaces"])).resolve()

    v1_manifest = _read_json(v1_manifest_path)
    if v1_manifest.get("status") != EXPECTED_V1_STATUS:
        raise RuntimeError("unexpected M3-v1 manifest status")
    if bool(v1_manifest.get("graph_simulation")) or bool(v1_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M3-v1 local evidence is not graph-clean")

    local_results = pd.read_csv(local_results_path)
    surfaces = _load_candidate_surfaces(
        local_results=local_results,
        local_surface_root=local_surface_root,
    )

    reference = next(iter(surfaces["ProviderA"].values()))
    assignments = _fold_assignments(reference)
    assignments_path = output_root / "m3_lambda_cv_fold_assignments.csv"
    assignments.to_csv(assignments_path, index=False)

    lambda_grid = [float(x) for x in contract["lambda_grid"]]
    scores = _cv_scores(
        surfaces=surfaces,
        assignments=assignments,
        lambda_grid=lambda_grid,
    )
    scores_path = output_root / "m3_lambda_cv_scores.csv"
    scores.to_csv(scores_path, index=False)

    summary = _summarize_cv(scores)
    summary_path = output_root / "m3_lambda_cv_summary.csv"
    summary.to_csv(summary_path, index=False)

    selected = _select_lambda(summary)
    selected_lambda = float(selected["lambda"])
    selected_payload = {
        "status": "FROZEN_PHASE4_M3_LAMBDA_SELECTED_BY_PUBLIC_I1_CV_V3",
        "selected_lambda": selected_lambda,
        "mean_validation_bernoulli_kl": float(
            selected["mean_validation_bernoulli_kl"]
        ),
        "mean_validation_mse": float(selected["mean_validation_mse"]),
        "selection_rule": contract["selection_rule"],
        "selected_at_grid_maximum": bool(
            np.isclose(selected_lambda, max(lambda_grid))
        ),
        "selected_at_grid_minimum": bool(
            np.isclose(selected_lambda, min(lambda_grid))
        ),
    }
    selected_path = output_root / "m3_lambda_cv_selected.json"
    _write_json(selected_path, selected_payload)

    weights, diagnostics = _full_weights(
        local_results=local_results,
        selected_lambda=selected_lambda,
    )
    weights_path = output_root / "m3_v3_provider_weights.csv"
    diag_path = output_root / "m3_v3_weight_diagnostics.csv"
    weights.to_csv(weights_path, index=False)
    diagnostics.to_csv(diag_path, index=False)

    recon, recon_summary = _weighted_reconstruction(
        weights=weights,
        surfaces=surfaces,
    )
    recon_path = output_root / "m3_v3_weighted_i1_reconstruction.csv"
    recon_summary_path = output_root / "m3_v3_weighted_i1_reconstruction_summary.csv"
    recon.to_csv(recon_path, index=False)
    recon_summary.to_csv(recon_summary_path, index=False)

    post = dict(contract["post_selection"])
    joint = _sample_joint_bank(
        weights=weights,
        k=int(post["joint_bank_size"]),
        seed=int(post["joint_sampling_seed"]),
    )
    joint_path = output_root / "m3_v3_joint_latent_draws_200.csv"
    joint.to_csv(joint_path, index=False)

    manifest = {
        "status": "FROZEN_PHASE4_M3_V3_PUBLIC_I1_CV_WEIGHTING_COMPLETE",
        "contract_sha256": _sha256(contract_path),
        "v1_manifest_sha256": _sha256(v1_manifest_path),
        "v1_local_results_sha256": _sha256(local_results_path),
        "fold_assignments_sha256": _sha256(assignments_path),
        "cv_scores_sha256": _sha256(scores_path),
        "cv_summary_sha256": _sha256(summary_path),
        "selected_lambda_sha256": _sha256(selected_path),
        "selected_lambda": selected_lambda,
        "selected_at_grid_maximum": selected_payload["selected_at_grid_maximum"],
        "provider_effective_sample_sizes": {
            str(row.provider): float(row.effective_sample_size)
            for row in diagnostics.itertuples(index=False)
            if str(row.provider) in PROVIDERS
        },
        "joint_effective_sample_size": float(
            diagnostics[
                diagnostics["provider"].astype(str) == "JOINT_PRODUCT"
            ]["effective_sample_size"].iloc[0]
        ),
        "ordered_joint_draws": int(len(joint)),
        "unique_joint_latent_ids": int(joint["joint_latent_id"].nunique()),
        "duplicates_retained": int(
            len(joint) - joint["joint_latent_id"].nunique()
        ),
        "weights_sha256": _sha256(weights_path),
        "weight_diagnostics_sha256": _sha256(diag_path),
        "weighted_reconstruction_sha256": _sha256(recon_path),
        "weighted_reconstruction_summary_sha256": _sha256(recon_summary_path),
        "joint_draws_sha256": _sha256(joint_path),
        "provider_resimulation": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": contract["next_gate"],
    }
    _write_json(output_root / "m3_v3_lambda_cv_manifest.json", manifest)

    print("M3_LAMBDA_CV_SUMMARY")
    print(summary.to_string(index=False))
    print("\nM3_LAMBDA_SELECTED")
    print(json.dumps(selected_payload, indent=2))
    print("\nM3_V3_WEIGHT_DIAGNOSTICS")
    print(diagnostics.to_string(index=False))
    print("\nM3_V3_WEIGHTED_I1_RECONSTRUCTION")
    print(recon_summary.to_string(index=False))
    print(
        f"\nM3-v3 joint draws: total={len(joint)} "
        f"unique={joint['joint_latent_id'].nunique()} "
        f"duplicates_retained={len(joint)-joint['joint_latent_id'].nunique()}"
    )
    print("M3_V3_PUBLIC_I1_LAMBDA_CV_FROZEN_PASS")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
