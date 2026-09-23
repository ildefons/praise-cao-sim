"""M3-0/M3-1: freeze provider support, rescore it on public I1, and weight it.

This stage is local only. It does not simulate the graph and does not read graph
predictions or graph white-box results.

Usage
-----
Prepare/audit the existing 48-point-per-provider non-adaptive LHS support:

    python m3_local_weighting.py --prepare-only

Run the fresh N=100 local rescoring, compute frozen Gibbs weights, and materialize
one ordered bank of 200 joint latent draws:

    python m3_local_weighting.py

The full run is resumable at the candidate level.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE3 = FIRST_SCIENCE / "phase3"

if str(PHASE3) not in sys.path:
    sys.path.insert(0, str(PHASE3))

from run_m1_provider_lift_v2 import (  # noqa: E402
    _simulate_and_score,
    load_verified_public_i1_cards,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_STATUS = "FROZEN_PHASE4_M3_LOCAL_WEIGHTING_V1"
EXPECTED_A2_STATUS = "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_AUDIT_COMPLETE_V1"
TOL = 1e-12


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


def _seed_bank(start: int, count: int) -> tuple[int, ...]:
    return tuple(range(int(start), int(start) + int(count)))


def _validate_firewall(contract: dict[str, Any]) -> None:
    firewall = dict(contract["firewall"])
    for key, value in firewall.items():
        if key == "PPG_firewall_preserved":
            if not bool(value):
                raise RuntimeError("M3 PPG firewall must remain preserved")
        elif bool(value):
            raise RuntimeError(f"M3 local contract unexpectedly allows {key}")


def _prepare_candidate_bank(
    *,
    contract: dict[str, Any],
    output_root: Path,
    contract_path: Path,
) -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    support = dict(contract["provider_support"])
    source_manifest_path = (HERE / str(support["source_manifest"])).resolve()
    source_design_path = (HERE / str(support["source_design"])).resolve()

    source_manifest = _read_json(source_manifest_path)
    if source_manifest.get("status") != str(support["required_source_manifest_status"]):
        raise RuntimeError(
            "M3 requires the completed M2-A2 non-adaptive coverage manifest"
        )
    if "design_sha256" in source_manifest:
        if _sha256(source_design_path) != str(source_manifest["design_sha256"]):
            raise RuntimeError("M2-A2 LHS design hash mismatch")

    design = pd.read_csv(source_design_path)
    required = {
        "provider",
        "candidate_id",
        "lhs_index",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
        "mean_service_time",
        "cost_rate",
        "service_cv",
    }
    missing = sorted(required.difference(design.columns))
    if missing:
        raise ValueError("M2-A2 LHS design missing fields: " + ", ".join(missing))

    expected_per_provider = int(support["n_candidates_per_provider"])
    expected_total = int(support["n_candidates_total"])
    if len(design) != expected_total:
        raise RuntimeError(
            f"M3 support expected {expected_total} candidates, found {len(design)}"
        )
    if design["candidate_id"].astype(str).duplicated().any():
        raise RuntimeError("M3 provider candidate IDs are not unique")

    frames: list[pd.DataFrame] = []
    for provider in PROVIDERS:
        g = design[design["provider"].astype(str) == provider].copy()
        if len(g) != expected_per_provider:
            raise RuntimeError(
                f"{provider}: expected {expected_per_provider} LHS points, found {len(g)}"
            )
        coords = g[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
        if np.any(coords < -TOL) or np.any(coords > 1.0 + TOL):
            raise RuntimeError(f"{provider}: LHS normalized coordinate outside [0,1]")
        g["m3_prior_mass"] = 1.0 / float(expected_per_provider)
        g["m3_support_role"] = "NONADAPTIVE_LHS_UNIFORM_FINITE_SUPPORT"
        frames.append(g)

    bank = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["provider", "lhs_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    bank_path = output_root / "m3_provider_candidate_bank.csv"
    bank.to_csv(bank_path, index=False)

    summary_rows = []
    for provider in PROVIDERS:
        g = bank[bank["provider"].astype(str) == provider]
        summary_rows.append(
            {
                "provider": provider,
                "n_candidates": int(len(g)),
                "min_z_log_mu": float(g["z_log_mu"].min()),
                "max_z_log_mu": float(g["z_log_mu"].max()),
                "min_z_log_kappa": float(g["z_log_kappa"].min()),
                "max_z_log_kappa": float(g["z_log_kappa"].max()),
                "min_z_cv": float(g["z_cv"].min()),
                "max_z_cv": float(g["z_cv"].max()),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_root / "m3_provider_candidate_bank_summary.csv", index=False)

    local_cfg = dict(contract["local_rescoring"])
    prepare_manifest = {
        "status": "PHASE4_M3_PROVIDER_SUPPORT_PREPARED_V1",
        "contract_sha256": _sha256(contract_path),
        "source_a2_manifest_sha256": _sha256(source_manifest_path),
        "source_a2_design_sha256": _sha256(source_design_path),
        "candidate_bank_sha256": _sha256(bank_path),
        "n_candidates_total": int(len(bank)),
        "n_candidates_per_provider": expected_per_provider,
        "local_seed_start_frozen": int(local_cfg["trajectory_seed_start"]),
        "local_seed_end_inclusive_frozen": int(
            local_cfg["trajectory_seed_end_inclusive"]
        ),
        "local_n_trajectories_per_candidate_frozen": int(
            local_cfg["n_trajectories_per_candidate"]
        ),
        "a2_loss_read_or_used": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    prepare_manifest_path = output_root / "m3_0_prepare_manifest_v1.json"
    _write_json(prepare_manifest_path, prepare_manifest)

    return bank, bank_path, prepare_manifest


def _smoothed_probability(probability: np.ndarray, n: int) -> np.ndarray:
    p = np.asarray(probability, dtype=float)
    if np.any(p < -1e-10) or np.any(p > 1.0 + 1e-10):
        raise ValueError("sigma probability outside [0,1]")
    p = np.clip(p, 0.0, 1.0)
    effective_successes = p * float(n)
    return (effective_successes + 0.5) / (float(n) + 1.0)


def _bernoulli_kl(p: np.ndarray, r: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    r = np.asarray(r, dtype=float)
    return p * np.log(p / r) + (1.0 - p) * np.log((1.0 - p) / (1.0 - r))


def _energy_from_comparison(
    comparison: pd.DataFrame,
    *,
    public_n: int,
    candidate_n: int,
) -> tuple[float, pd.DataFrame]:
    required = {
        "provider_id",
        "region_id",
        "horizon",
        "region_rho",
        "rho",
        "sigma_i1",
        "sigma_m1_local",
    }
    missing = sorted(required.difference(comparison.columns))
    if missing:
        raise ValueError("local comparison missing fields: " + ", ".join(missing))

    pointwise = comparison[
        [
            "provider_id",
            "region_id",
            "horizon",
            "region_rho",
            "rho",
            "sigma_i1",
            "sigma_m1_local",
        ]
    ].copy()
    p = _smoothed_probability(pointwise["sigma_i1"].to_numpy(float), public_n)
    r = _smoothed_probability(
        pointwise["sigma_m1_local"].to_numpy(float), candidate_n
    )
    kl = _bernoulli_kl(p, r)
    pointwise["p_i1_jeffreys"] = p
    pointwise["p_candidate_jeffreys"] = r
    pointwise["bernoulli_kl_i1_to_candidate"] = kl
    return float(np.mean(kl)), pointwise


def _rescore_candidates(
    *,
    bank: pd.DataFrame,
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    contract: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    output_root: Path,
) -> pd.DataFrame:
    local_cfg = dict(contract["local_rescoring"])
    weighting = dict(contract["weighting"])
    n_local = int(local_cfg["n_trajectories_per_candidate"])
    seed_start = int(local_cfg["trajectory_seed_start"])
    seed_end = int(local_cfg["trajectory_seed_end_inclusive"])
    seeds = _seed_bank(seed_start, n_local)
    if seeds[-1] != seed_end:
        raise RuntimeError("M3 local seed range and trajectory count disagree")

    public_n = int(weighting["public_i1_trajectory_count"])
    if n_local != int(weighting["candidate_trajectory_count"]):
        raise RuntimeError("M3 candidate trajectory count disagrees with weighting contract")

    results_path = output_root / "m3_local_rescore_results.csv"
    if results_path.exists():
        existing = pd.read_csv(results_path)
        completed = set(existing["candidate_id"].astype(str))
        print(f"M3 local resume: {len(completed)} candidates already complete", flush=True)
    else:
        existing = pd.DataFrame()
        completed: set[str] = set()

    surface_root = output_root / "local_surfaces"
    surface_root.mkdir(parents=True, exist_ok=True)

    total = len(bank)
    for ordinal, rec in enumerate(bank.itertuples(index=False), start=1):
        candidate_id = str(rec.candidate_id)
        if candidate_id in completed:
            continue
        provider = str(rec.provider)
        print(f"M3 local {ordinal}/{total} {candidate_id}", flush=True)
        metrics, _, comparison = _simulate_and_score(
            metadata=metadata_by_provider[provider],
            public_surface=surfaces[provider],
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            trajectory_seeds=seeds,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
            quiet=True,
        )
        energy, pointwise = _energy_from_comparison(
            comparison,
            public_n=public_n,
            candidate_n=n_local,
        )
        pointwise.insert(0, "candidate_id", candidate_id)
        pointwise.insert(0, "provider", provider)
        pointwise.to_csv(
            surface_root / f"{candidate_id}_comparison.csv", index=False
        )

        row = pd.DataFrame(
            [
                {
                    "provider": provider,
                    "candidate_id": candidate_id,
                    "lhs_index": int(rec.lhs_index),
                    "z_log_mu": float(rec.z_log_mu),
                    "z_log_kappa": float(rec.z_log_kappa),
                    "z_cv": float(rec.z_cv),
                    "mean_service_time": float(rec.mean_service_time),
                    "cost_rate": float(rec.cost_rate),
                    "service_cv": float(rec.service_cv),
                    "mse": float(metrics["mse"]),
                    "rmse": float(metrics["rmse"]),
                    "mae": float(metrics["mae"]),
                    "bias": float(metrics["bias"]),
                    "max_abs_error": float(metrics["max_abs_error"]),
                    "mean_bernoulli_kl": float(energy),
                    "log_unnormalized_weight": -float(public_n) * float(energy),
                    "n_local_trajectories": n_local,
                    "local_seed_start": seed_start,
                    "local_seed_end_inclusive": seed_end,
                }
            ]
        )
        existing = pd.concat([existing, row], ignore_index=True)
        existing = (
            existing.drop_duplicates("candidate_id", keep="last")
            .sort_values(["provider", "lhs_index"], kind="mergesort")
            .reset_index(drop=True)
        )
        existing.to_csv(results_path, index=False)
        completed.add(candidate_id)

    if len(existing) != len(bank):
        raise RuntimeError(
            f"M3 local rescoring incomplete: expected {len(bank)}, found {len(existing)}"
        )
    return existing


def _normalize_weights(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        g = results[results["provider"].astype(str) == provider].copy()
        if g.empty:
            raise RuntimeError(f"{provider}: no M3 local rescoring rows")
        logu = g["log_unnormalized_weight"].to_numpy(float)
        shift = float(np.max(logu))
        u = np.exp(logu - shift)
        w = u / np.sum(u)
        g["weight"] = w
        g["log_weight"] = np.log(w)
        frames.append(g)

        ess = float(1.0 / np.sum(np.square(w)))
        entropy = float(-np.sum(w * np.log(w)))
        mean_log_mu = float(np.sum(w * np.log(g["mean_service_time"].to_numpy(float))))
        mean_log_k = float(np.sum(w * np.log(g["cost_rate"].to_numpy(float))))
        mean_cv = float(np.sum(w * g["service_cv"].to_numpy(float)))
        diagnostics.append(
            {
                "provider": provider,
                "effective_sample_size": ess,
                "entropy_nats": entropy,
                "perplexity": float(math.exp(entropy)),
                "max_weight": float(np.max(w)),
                "min_weight": float(np.min(w)),
                "weighted_mean_log_mu": mean_log_mu,
                "weighted_mean_log_kappa": mean_log_k,
                "weighted_mean_cv": mean_cv,
            }
        )

    weights = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["provider", "lhs_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    diag = pd.DataFrame(diagnostics)
    joint_ess = float(np.prod(diag["effective_sample_size"].to_numpy(float)))
    joint_row = {
        "provider": "JOINT_PRODUCT",
        "effective_sample_size": joint_ess,
        "entropy_nats": float(diag["entropy_nats"].sum()),
        "perplexity": float(np.prod(diag["perplexity"].to_numpy(float))),
        "max_weight": float(np.prod(diag["max_weight"].to_numpy(float))),
        "min_weight": float(np.prod(diag["min_weight"].to_numpy(float))),
        "weighted_mean_log_mu": np.nan,
        "weighted_mean_log_kappa": np.nan,
        "weighted_mean_cv": np.nan,
    }
    diag = pd.concat([diag, pd.DataFrame([joint_row])], ignore_index=True)
    return weights, diag


def _weighted_i1_reconstruction(
    *,
    weights: pd.DataFrame,
    output_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    surface_root = output_root / "local_surfaces"

    for provider in PROVIDERS:
        wp = weights[weights["provider"].astype(str) == provider].copy()
        for rec in wp.itertuples(index=False):
            path = surface_root / f"{rec.candidate_id}_comparison.csv"
            pointwise = pd.read_csv(path)
            pointwise["component_weight"] = float(rec.weight)
            pointwise["weighted_sigma_component"] = (
                pointwise["sigma_m1_local"].astype(float) * float(rec.weight)
            )
            rows.append(pointwise)

    all_points = pd.concat(rows, ignore_index=True)
    keys = ["provider", "provider_id", "region_id", "horizon", "region_rho", "rho"]
    public_consistency = (
        all_points.groupby(keys, as_index=False)["sigma_i1"]
        .agg(["min", "max"])
        .reset_index()
    )
    if np.max(
        np.abs(
            public_consistency["max"].to_numpy(float)
            - public_consistency["min"].to_numpy(float)
        )
    ) > 1e-12:
        raise RuntimeError("public I1 sigma differs across candidate pointwise files")

    reconstruction = (
        all_points.groupby(keys, as_index=False)
        .agg(
            sigma_i1=("sigma_i1", "first"),
            sigma_m3_local_weighted=("weighted_sigma_component", "sum"),
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
        raise RuntimeError("M3 provider weights do not sum to one at every I1 point")

    reconstruction["error"] = (
        reconstruction["sigma_m3_local_weighted"].astype(float)
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


def _sample_joint_bank(
    *,
    weights: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    cfg = dict(contract["joint_sampling"])
    k = int(cfg["ordered_bank_size"])
    rng = np.random.default_rng(int(cfg["rng_seed"]))

    by_provider: dict[str, pd.DataFrame] = {}
    chosen: dict[str, np.ndarray] = {}
    for provider in PROVIDERS:
        g = (
            weights[weights["provider"].astype(str) == provider]
            .sort_values("lhs_index")
            .reset_index(drop=True)
        )
        p = g["weight"].to_numpy(float)
        by_provider[provider] = g
        chosen[provider] = rng.choice(len(g), size=k, replace=True, p=p)

    rows = []
    for draw_id in range(k):
        row: dict[str, Any] = {
            "joint_draw_id": int(draw_id),
            "m3_100x20_member": bool(draw_id < 100),
            "m3_200x10_member": True,
            "monte_carlo_draw_weight_K100": 0.01 if draw_id < 100 else np.nan,
            "monte_carlo_draw_weight_K200": 0.005,
        }
        mass = 1.0
        joint_ids = []
        for provider in PROVIDERS:
            rec = by_provider[provider].iloc[int(chosen[provider][draw_id])]
            prefix = provider.replace("Provider", "").lower()
            row[f"{prefix}_candidate_id"] = str(rec["candidate_id"])
            row[f"{prefix}_lhs_index"] = int(rec["lhs_index"])
            row[f"{prefix}_mean_service_time"] = float(rec["mean_service_time"])
            row[f"{prefix}_cost_rate"] = float(rec["cost_rate"])
            row[f"{prefix}_service_cv"] = float(rec["service_cv"])
            row[f"{prefix}_provider_weight"] = float(rec["weight"])
            mass *= float(rec["weight"])
            joint_ids.append(str(rec["candidate_id"]))
        row["joint_target_mass"] = float(mass)
        row["joint_latent_id"] = "|".join(joint_ids)
        rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M3 local weighting stage")
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_local_weighting_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_local_weighting_v1",
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    contract_path = args.contract.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M3 local weighting contract status")
    _validate_firewall(contract)

    bank, bank_path, prepare_manifest = _prepare_candidate_bank(
        contract=contract,
        output_root=output_root,
        contract_path=contract_path,
    )

    print("M3_0_PROVIDER_BANK_FROZEN_PASS")
    print(
        bank.groupby("provider")
        .agg(
            n=("candidate_id", "size"),
            z_mu_min=("z_log_mu", "min"),
            z_mu_max=("z_log_mu", "max"),
            z_k_min=("z_log_kappa", "min"),
            z_k_max=("z_log_kappa", "max"),
            z_cv_min=("z_cv", "min"),
            z_cv_max=("z_cv", "max"),
        )
        .to_string()
    )
    if args.prepare_only:
        print("M3_0_PREPARE_ONLY_COMPLETE")
        print(f"output={output_root}")
        return

    inputs = dict(contract["frozen_inputs"])
    card_root = (HERE / str(inputs["public_i1_root"])).resolve()
    metadata_by_provider, surfaces, public_manifest = load_verified_public_i1_cards(
        card_root
    )
    closure_path = (HERE / str(inputs["pilot_closure_source"])).resolve()
    closure = _read_json(closure_path)
    canonical_ipt = float(closure["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(closure["pilot_scope"]["execution_fraction"])

    results = _rescore_candidates(
        bank=bank,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        contract=contract,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        output_root=output_root,
    )

    weights, diagnostics = _normalize_weights(results)
    weights_path = output_root / "m3_provider_weights.csv"
    diagnostics_path = output_root / "m3_weight_diagnostics.csv"
    weights.to_csv(weights_path, index=False)
    diagnostics.to_csv(diagnostics_path, index=False)

    reconstruction, reconstruction_summary = _weighted_i1_reconstruction(
        weights=weights,
        output_root=output_root,
    )
    reconstruction_path = output_root / "m3_weighted_i1_reconstruction.csv"
    reconstruction_summary_path = (
        output_root / "m3_weighted_i1_reconstruction_summary.csv"
    )
    reconstruction.to_csv(reconstruction_path, index=False)
    reconstruction_summary.to_csv(reconstruction_summary_path, index=False)

    joint = _sample_joint_bank(weights=weights, contract=contract)
    joint_path = output_root / "m3_joint_latent_draws_200.csv"
    joint.to_csv(joint_path, index=False)

    duplicate_count = int(len(joint) - joint["joint_latent_id"].nunique())
    unique_joint_count = int(joint["joint_latent_id"].nunique())

    elapsed = time.perf_counter() - started
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    local_cfg = dict(contract["local_rescoring"])
    manifest = {
        "status": "FROZEN_PHASE4_M3_WEIGHTED_PROVIDER_DISTRIBUTION_AND_JOINT_BANK_V1",
        "contract_sha256": _sha256(contract_path),
        "prepare_manifest_status": prepare_manifest["status"],
        "candidate_bank_sha256": _sha256(bank_path),
        "public_i1_manifest_status": public_manifest.get("status"),
        "public_i1_manifest_sha256": _sha256(
            card_root / "i1_rho_conditioned_manifest_v1.json"
        ),
        "pilot_closure_sha256": _sha256(closure_path),
        "n_provider_candidates_total": int(len(bank)),
        "n_provider_candidates_per_provider": int(
            contract["provider_support"]["n_candidates_per_provider"]
        ),
        "local_seed_start": int(local_cfg["trajectory_seed_start"]),
        "local_seed_end_inclusive": int(local_cfg["trajectory_seed_end_inclusive"]),
        "local_n_trajectories_per_candidate": int(
            local_cfg["n_trajectories_per_candidate"]
        ),
        "total_provider_local_trajectories": int(
            len(bank) * int(local_cfg["n_trajectories_per_candidate"])
        ),
        "weighting_family": contract["weighting"]["family"],
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
        "joint_sampling_seed": int(contract["joint_sampling"]["rng_seed"]),
        "ordered_joint_draws": int(len(joint)),
        "unique_joint_latent_ids": unique_joint_count,
        "duplicate_joint_draws_retained": duplicate_count,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "weights_sha256": _sha256(weights_path),
        "weight_diagnostics_sha256": _sha256(diagnostics_path),
        "weighted_i1_reconstruction_sha256": _sha256(reconstruction_path),
        "weighted_i1_reconstruction_summary_sha256": _sha256(
            reconstruction_summary_path
        ),
        "joint_latent_draws_sha256": _sha256(joint_path),
        "python_wall_seconds": float(elapsed),
        "peak_rss_platform_units": peak_rss,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": contract["next_gate"],
    }
    _write_json(output_root / "m3_local_weighting_manifest_v1.json", manifest)

    print("\nM3_PROVIDER_WEIGHT_DIAGNOSTICS")
    print(diagnostics.to_string(index=False))
    print("\nM3_WEIGHTED_I1_RECONSTRUCTION")
    print(reconstruction_summary.to_string(index=False))
    print(
        f"\nM3 joint draws: total={len(joint)} unique={unique_joint_count} "
        f"duplicates_retained={duplicate_count}"
    )
    print("M3_LOCAL_WEIGHTING_AND_JOINT_BANK_FROZEN_PASS")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
