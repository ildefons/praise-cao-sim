"""Materialize M3-v2 tempered Gibbs weights from frozen M3-v1 local scores.

No simulation is run. This script reads only the already-frozen M3-v1 local
candidate scores and local comparison surfaces, applies the frozen beta=5 rule,
and generates one new ordered 200-draw joint latent bank for later graph use.
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
EXPECTED_STATUS = "FROZEN_PHASE4_M3_WEIGHTING_V2_TEMPERED"
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


def _ess(w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    return float(1.0 / np.sum(np.square(w)))


def _entropy(w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    nz = w > 0
    return float(-np.sum(w[nz] * np.log(w[nz])))


def _n_for_mass(w: np.ndarray, target: float) -> int:
    s = np.sort(np.asarray(w, dtype=float))[::-1]
    return int(np.searchsorted(np.cumsum(s), float(target), side="left") + 1)


def _normalize_weights(results: pd.DataFrame, beta: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    diagnostics = []

    for provider in PROVIDERS:
        g = results[results["provider"].astype(str) == provider].copy()
        if len(g) != 48:
            raise RuntimeError(f"{provider}: expected 48 frozen LHS candidates, found {len(g)}")
        e = g["mean_bernoulli_kl"].to_numpy(float)
        logu = -float(beta) * e
        logu -= np.max(logu)
        u = np.exp(logu)
        w = u / np.sum(u)
        g["beta"] = float(beta)
        g["log_unnormalized_weight_v2"] = -float(beta) * e
        g["weight_v2"] = w
        g["log_weight_v2"] = np.log(w)
        frames.append(g)

        entropy = _entropy(w)
        diagnostics.append(
            {
                "provider": provider,
                "beta": float(beta),
                "effective_sample_size": _ess(w),
                "entropy_nats": entropy,
                "perplexity": float(math.exp(entropy)),
                "max_weight": float(np.max(w)),
                "min_weight": float(np.min(w)),
                "n50": _n_for_mass(w, 0.50),
                "n90": _n_for_mass(w, 0.90),
                "n95": _n_for_mass(w, 0.95),
                "n99": _n_for_mass(w, 0.99),
                "weighted_mean_log_mu": float(
                    np.sum(w * np.log(g["mean_service_time"].to_numpy(float)))
                ),
                "weighted_mean_log_kappa": float(
                    np.sum(w * np.log(g["cost_rate"].to_numpy(float)))
                ),
                "weighted_mean_cv": float(
                    np.sum(w * g["service_cv"].to_numpy(float))
                ),
            }
        )

    weights = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["provider", "lhs_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    diag = pd.DataFrame(diagnostics)
    joint_row = {
        "provider": "JOINT_PRODUCT",
        "beta": float(beta),
        "effective_sample_size": float(np.prod(diag["effective_sample_size"].to_numpy(float))),
        "entropy_nats": float(diag["entropy_nats"].sum()),
        "perplexity": float(np.prod(diag["perplexity"].to_numpy(float))),
        "max_weight": float(np.prod(diag["max_weight"].to_numpy(float))),
        "min_weight": float(np.prod(diag["min_weight"].to_numpy(float))),
        "n50": np.nan,
        "n90": np.nan,
        "n95": np.nan,
        "n99": np.nan,
        "weighted_mean_log_mu": np.nan,
        "weighted_mean_log_kappa": np.nan,
        "weighted_mean_cv": np.nan,
    }
    diag = pd.concat([diag, pd.DataFrame([joint_row])], ignore_index=True)
    return weights, diag


def _weighted_reconstruction(
    *,
    weights: pd.DataFrame,
    local_surface_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for provider in PROVIDERS:
        wp = weights[weights["provider"].astype(str) == provider].copy()
        for rec in wp.itertuples(index=False):
            path = local_surface_root / f"{rec.candidate_id}_comparison.csv"
            if not path.exists():
                raise FileNotFoundError(path)
            pointwise = pd.read_csv(path)
            pointwise["component_weight"] = float(rec.weight_v2)
            pointwise["weighted_sigma_component"] = (
                pointwise["sigma_m1_local"].astype(float) * float(rec.weight_v2)
            )
            rows.append(pointwise)

    all_points = pd.concat(rows, ignore_index=True)
    keys = ["provider", "provider_id", "region_id", "horizon", "region_rho", "rho"]
    reconstruction = (
        all_points.groupby(keys, as_index=False)
        .agg(
            sigma_i1=("sigma_i1", "first"),
            sigma_m3_v2_local_weighted=("weighted_sigma_component", "sum"),
            component_weight_sum=("component_weight", "sum"),
        )
        .sort_values(["provider", "region_rho", "rho", "horizon"])
        .reset_index(drop=True)
    )
    if not np.allclose(
        reconstruction["component_weight_sum"].to_numpy(float),
        1.0,
        atol=1e-10,
        rtol=0.0,
    ):
        raise RuntimeError("M3-v2 weights do not sum to one at each I1 point")

    reconstruction["error"] = (
        reconstruction["sigma_m3_v2_local_weighted"].astype(float)
        - reconstruction["sigma_i1"].astype(float)
    )
    reconstruction["abs_error"] = reconstruction["error"].abs()
    reconstruction["squared_error"] = reconstruction["error"] ** 2

    summaries = []
    for provider in PROVIDERS:
        g = reconstruction[reconstruction["provider"].astype(str) == provider]
        e = g["error"].to_numpy(float)
        summaries.append(
            {
                "provider": provider,
                "n_points": int(len(g)),
                "mse": float(np.mean(np.square(e))),
                "rmse": float(np.sqrt(np.mean(np.square(e)))),
                "mae": float(np.mean(np.abs(e))),
                "bias": float(np.mean(e)),
                "max_abs_error": float(np.max(np.abs(e))),
            }
        )
    return reconstruction, pd.DataFrame(summaries)


def _sample_joint_bank(weights: pd.DataFrame, k: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(int(seed))
    by_provider = {}
    chosen = {}
    for provider in PROVIDERS:
        g = (
            weights[weights["provider"].astype(str) == provider]
            .sort_values("lhs_index")
            .reset_index(drop=True)
        )
        p = g["weight_v2"].to_numpy(float)
        by_provider[provider] = g
        chosen[provider] = rng.choice(len(g), size=int(k), replace=True, p=p)

    rows = []
    for draw_id in range(int(k)):
        row = {
            "joint_draw_id": int(draw_id),
            "m3_100x20_member": bool(draw_id < 100),
            "m3_200x10_member": True,
            "monte_carlo_draw_weight_K100": 0.01 if draw_id < 100 else np.nan,
            "monte_carlo_draw_weight_K200": 0.005,
        }
        mass = 1.0
        ids = []
        for provider in PROVIDERS:
            rec = by_provider[provider].iloc[int(chosen[provider][draw_id])]
            prefix = provider.replace("Provider", "").lower()
            row[f"{prefix}_candidate_id"] = str(rec["candidate_id"])
            row[f"{prefix}_lhs_index"] = int(rec["lhs_index"])
            row[f"{prefix}_mean_service_time"] = float(rec["mean_service_time"])
            row[f"{prefix}_cost_rate"] = float(rec["cost_rate"])
            row[f"{prefix}_service_cv"] = float(rec["service_cv"])
            row[f"{prefix}_provider_weight"] = float(rec["weight_v2"])
            mass *= float(rec["weight_v2"])
            ids.append(str(rec["candidate_id"]))
        row["joint_target_mass"] = float(mass)
        row["joint_latent_id"] = "|".join(ids)
        rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize frozen M3-v2 beta=5 weights")
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_weighting_v2_tempered.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_weighting_v2_tempered",
    )
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M3-v2 weighting contract status")

    inputs = dict(contract["inputs"])
    v1_manifest_path = (HERE / str(inputs["v1_manifest"])).resolve()
    v1_results_path = (HERE / str(inputs["v1_local_results"])).resolve()
    v1_bank_path = (HERE / str(inputs["v1_provider_candidate_bank"])).resolve()
    local_surface_root = (HERE / str(inputs["v1_local_surfaces"])).resolve()

    v1_manifest = _read_json(v1_manifest_path)
    if v1_manifest.get("status") != EXPECTED_V1_STATUS:
        raise RuntimeError("unexpected M3-v1 manifest status")
    if bool(v1_manifest.get("graph_simulation")) or bool(v1_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M3-v1 provenance violates local-only assumption")

    local = pd.read_csv(v1_results_path)
    bank = pd.read_csv(v1_bank_path)
    if set(local["candidate_id"].astype(str)) != set(bank["candidate_id"].astype(str)):
        raise RuntimeError("M3-v1 local results and candidate bank IDs differ")

    beta = float(contract["temperature_selection"]["selected_beta"])
    weights, diagnostics = _normalize_weights(local, beta=beta)

    min_provider_ess = float(
        diagnostics[diagnostics["provider"].isin(PROVIDERS)]["effective_sample_size"].min()
    )
    if min_provider_ess < 3.0 - 1e-9:
        raise RuntimeError(
            f"frozen beta={beta:g} violates ESS>=3 criterion: min ESS={min_provider_ess}"
        )

    weights_path = output_root / "m3_v2_provider_weights_beta5.csv"
    diagnostics_path = output_root / "m3_v2_weight_diagnostics_beta5.csv"
    weights.to_csv(weights_path, index=False)
    diagnostics.to_csv(diagnostics_path, index=False)

    reconstruction, reconstruction_summary = _weighted_reconstruction(
        weights=weights,
        local_surface_root=local_surface_root,
    )
    reconstruction_path = output_root / "m3_v2_weighted_i1_reconstruction.csv"
    reconstruction_summary_path = (
        output_root / "m3_v2_weighted_i1_reconstruction_summary.csv"
    )
    reconstruction.to_csv(reconstruction_path, index=False)
    reconstruction_summary.to_csv(reconstruction_summary_path, index=False)

    joint_cfg = dict(contract["joint_sampling"])
    joint = _sample_joint_bank(
        weights,
        k=int(joint_cfg["ordered_bank_size"]),
        seed=int(joint_cfg["rng_seed"]),
    )
    joint_path = output_root / "m3_v2_joint_latent_draws_200.csv"
    joint.to_csv(joint_path, index=False)

    counts = joint["joint_latent_id"].value_counts()
    manifest = {
        "status": "FROZEN_PHASE4_M3_V2_TEMPERED_PROVIDER_DISTRIBUTION_AND_JOINT_BANK",
        "contract_sha256": _sha256(contract_path),
        "v1_manifest_sha256": _sha256(v1_manifest_path),
        "v1_local_results_sha256": _sha256(v1_results_path),
        "v1_candidate_bank_sha256": _sha256(v1_bank_path),
        "beta": beta,
        "temperature_selection_criterion": contract["temperature_selection"]["criterion"],
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
        "duplicate_joint_draws_retained": int(len(joint) - joint["joint_latent_id"].nunique()),
        "largest_observed_duplicate_count": int(counts.max()),
        "weights_sha256": _sha256(weights_path),
        "weight_diagnostics_sha256": _sha256(diagnostics_path),
        "weighted_i1_reconstruction_sha256": _sha256(reconstruction_path),
        "weighted_i1_reconstruction_summary_sha256": _sha256(reconstruction_summary_path),
        "joint_draws_sha256": _sha256(joint_path),
        "provider_resimulation": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": contract["next_gate"],
    }
    _write_json(output_root / "m3_v2_tempered_weighting_manifest.json", manifest)

    print("M3_V2_WEIGHT_DIAGNOSTICS")
    print(diagnostics.to_string(index=False))
    print("\nM3_V2_WEIGHTED_I1_RECONSTRUCTION")
    print(reconstruction_summary.to_string(index=False))
    print(
        f"\nM3-v2 joint draws: total={len(joint)} "
        f"unique={joint['joint_latent_id'].nunique()} "
        f"duplicates_retained={len(joint)-joint['joint_latent_id'].nunique()}"
    )
    print("M3_V2_TEMPERED_WEIGHTING_FROZEN_PASS")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
