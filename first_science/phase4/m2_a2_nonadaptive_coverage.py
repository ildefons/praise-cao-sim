"""Audit whether adaptive M1-v2 TPE search concentrated compatible solutions.

This Phase-4 M2-A2 diagnostic samples each provider's final declared M1-v2
parameter domain with a non-adaptive Latin hypercube, evaluates those points
against the same public I1 objective and the same 25-trajectory seed bank used
by the original M1 search, and compares any compatible samples geometrically
with the existing TPE-compatible set.

It does not run Optuna, does not simulate the graph, and does not read graph
predictions or graph white-box outcomes.
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
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"

if str(PHASE3) not in sys.path:
    sys.path.insert(0, str(PHASE3))

from m1_joint_lift_v2 import build_search_bounds  # noqa: E402
from run_m1_provider_lift_v2 import (  # noqa: E402
    _simulate_and_score,
    load_verified_public_i1_cards,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_STATUS = "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_AUDIT_V1"
EXPECTED_FREEZE_STATUS = "FROZEN_PHASE3_I1_M1_V2_PILOT"
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


def _seed_bank(start: int, n: int) -> tuple[int, ...]:
    return tuple(range(int(start), int(start) + int(n)))


def _latin_hypercube(n: int, d: int, seed: int) -> np.ndarray:
    """Simple reproducible randomized Latin hypercube on [0,1)^d."""
    if n <= 0 or d <= 0:
        raise ValueError("Latin hypercube dimensions must be positive")
    rng = np.random.default_rng(int(seed))
    sample = np.empty((int(n), int(d)), dtype=float)
    for j in range(int(d)):
        permutation = rng.permutation(int(n))
        jitter = rng.random(int(n))
        sample[:, j] = (permutation + jitter) / float(n)
    return sample


def _map_unit_to_parameters(unit: np.ndarray, bounds) -> pd.DataFrame:
    if unit.ndim != 2 or unit.shape[1] != 3:
        raise ValueError("expected an N x 3 unit-cube sample")
    log_mu_lo = math.log(float(bounds.mean_service_time_lower))
    log_mu_hi = math.log(float(bounds.mean_service_time_upper))
    log_k_lo = math.log(float(bounds.cost_rate_lower))
    log_k_hi = math.log(float(bounds.cost_rate_upper))
    cv_lo = float(bounds.service_cv_lower)
    cv_hi = float(bounds.service_cv_upper)

    return pd.DataFrame(
        {
            "z_log_mu": unit[:, 0],
            "z_log_kappa": unit[:, 1],
            "z_cv": unit[:, 2],
            "mean_service_time": np.exp(log_mu_lo + unit[:, 0] * (log_mu_hi - log_mu_lo)),
            "cost_rate": np.exp(log_k_lo + unit[:, 1] * (log_k_hi - log_k_lo)),
            "service_cv": cv_lo + unit[:, 2] * (cv_hi - cv_lo),
        }
    )


def _normalize_parameters(mu: float, kappa: float, cv: float, bounds) -> np.ndarray:
    log_mu_lo = math.log(float(bounds.mean_service_time_lower))
    log_mu_hi = math.log(float(bounds.mean_service_time_upper))
    log_k_lo = math.log(float(bounds.cost_rate_lower))
    log_k_hi = math.log(float(bounds.cost_rate_upper))
    cv_lo = float(bounds.service_cv_lower)
    cv_hi = float(bounds.service_cv_upper)
    return np.asarray(
        [
            (math.log(float(mu)) - log_mu_lo) / (log_mu_hi - log_mu_lo),
            (math.log(float(kappa)) - log_k_lo) / (log_k_hi - log_k_lo),
            (float(cv) - cv_lo) / (cv_hi - cv_lo),
        ],
        dtype=float,
    )


def _max_pairwise_distance(coords: np.ndarray) -> float:
    if len(coords) <= 1:
        return 0.0
    best = 0.0
    for i in range(len(coords) - 1):
        dist = np.linalg.norm(coords[i + 1 :] - coords[i], axis=1)
        if len(dist):
            best = max(best, float(np.max(dist)))
    return best


def _span(coords: np.ndarray, axis: int) -> float:
    if len(coords) == 0:
        return float("nan")
    return float(np.max(coords[:, axis]) - np.min(coords[:, axis]))


def _existing_geometry(existing: pd.DataFrame, provider: str, ratio_max: float) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = existing[existing["provider"].astype(str) == provider].copy()
    if frame.empty:
        raise RuntimeError(f"{provider}: no existing M1 landscape candidates")
    required = {
        "search_mse",
        "loss_ratio_to_best",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
        "mean_service_time",
        "cost_rate",
        "service_cv",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"existing landscape missing columns: {missing}")

    compatible = frame[
        frame["loss_ratio_to_best"].astype(float) <= float(ratio_max) + TOL
    ].copy()
    if compatible.empty:
        raise RuntimeError(f"{provider}: no existing candidates inside compatibility band")

    coords = compatible[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(dtype=float)
    summary = {
        "provider": provider,
        "n_existing_total": int(len(frame)),
        "n_existing_compatible": int(len(compatible)),
        "existing_best_search_mse": float(frame["search_mse"].min()),
        "compatibility_mse_ceiling": float(frame["search_mse"].min()) * float(ratio_max),
        "existing_max_pairwise_distance": _max_pairwise_distance(coords),
        "existing_diameter_fraction_of_unit_cube": _max_pairwise_distance(coords) / math.sqrt(3.0),
        "existing_z_log_mu_span": _span(coords, 0),
        "existing_z_log_kappa_span": _span(coords, 1),
        "existing_z_cv_span": _span(coords, 2),
    }
    return compatible.reset_index(drop=True), summary


def _build_design(
    *,
    contract: dict[str, Any],
    metadata_by_provider: dict[str, dict[str, object]],
    base_contract: dict[str, Any],
    expanded_c_contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sampler = dict(contract["sampler"])
    n = int(sampler["n_points_per_provider"])
    seed = int(sampler["seed"])
    frames: list[pd.DataFrame] = []
    bounds_by_provider: dict[str, Any] = {}

    for provider_index, provider in enumerate(PROVIDERS):
        closure = expanded_c_contract if provider == "ProviderC" else base_contract
        bounds = build_search_bounds(metadata_by_provider[provider], closure)
        bounds_by_provider[provider] = bounds
        unit = _latin_hypercube(n, 3, seed + provider_index * 100003)
        frame = _map_unit_to_parameters(unit, bounds)
        frame.insert(0, "lhs_index", np.arange(n, dtype=int))
        frame.insert(0, "candidate_id", [f"{provider}_LHS_{idx:03d}" for idx in range(n)])
        frame.insert(0, "provider", provider)
        frames.append(frame)

    return pd.concat(frames, ignore_index=True), bounds_by_provider


def _evaluate_design(
    *,
    design: pd.DataFrame,
    existing: pd.DataFrame,
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    trajectory_seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
    ratio_max: float,
    output_root: Path,
) -> pd.DataFrame:
    results_path = output_root / "m2_a2_lhs_results.csv"
    if results_path.exists():
        results = pd.read_csv(results_path)
        completed_ids = set(results["candidate_id"].astype(str))
        print(f"M2-A2 resume: {len(completed_ids)} candidates already evaluated", flush=True)
    else:
        results = pd.DataFrame()
        completed_ids: set[str] = set()

    rows: list[dict[str, Any]] = []
    total = len(design)
    for ordinal, rec in enumerate(design.itertuples(index=False), start=1):
        candidate_id = str(rec.candidate_id)
        if candidate_id in completed_ids:
            continue
        provider = str(rec.provider)
        provider_existing = existing[existing["provider"].astype(str) == provider]
        best_search_mse = float(provider_existing["search_mse"].min())
        ceiling = best_search_mse * float(ratio_max)
        print(f"M2-A2 {ordinal}/{total} {candidate_id}", flush=True)

        metrics, simulated, comparison = _simulate_and_score(
            metadata=metadata_by_provider[provider],
            public_surface=surfaces[provider],
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            trajectory_seeds=trajectory_seeds,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
            quiet=True,
        )
        compatible = float(metrics["mse"]) <= ceiling + TOL
        row = {
            "provider": provider,
            "candidate_id": candidate_id,
            "lhs_index": int(rec.lhs_index),
            "z_log_mu": float(rec.z_log_mu),
            "z_log_kappa": float(rec.z_log_kappa),
            "z_cv": float(rec.z_cv),
            "mean_service_time": float(rec.mean_service_time),
            "cost_rate": float(rec.cost_rate),
            "service_cv": float(rec.service_cv),
            "lhs_mse": float(metrics["mse"]),
            "lhs_rmse": float(metrics["rmse"]),
            "lhs_mae": float(metrics["mae"]),
            "lhs_bias": float(metrics["bias"]),
            "lhs_max_abs_error": float(metrics["max_abs_error"]),
            "existing_best_search_mse": best_search_mse,
            "compatibility_mse_ceiling": ceiling,
            "lhs_loss_ratio_to_existing_best": float(metrics["mse"]) / best_search_mse,
            "lhs_compatible": bool(compatible),
        }
        rows.append(row)

        if compatible:
            candidate_dir = output_root / "compatible_surfaces" / candidate_id
            candidate_dir.mkdir(parents=True, exist_ok=True)
            simulated.to_csv(candidate_dir / "lhs_sigma_surface.csv", index=False)
            comparison.to_csv(candidate_dir / "lhs_comparison.csv", index=False)

        updated = pd.concat([results, pd.DataFrame(rows)], ignore_index=True)
        updated = updated.drop_duplicates("candidate_id", keep="last").sort_values(
            ["provider", "lhs_index"]
        )
        updated.to_csv(results_path, index=False)

    if rows:
        results = pd.concat([results, pd.DataFrame(rows)], ignore_index=True)
        results = results.drop_duplicates("candidate_id", keep="last").sort_values(
            ["provider", "lhs_index"]
        ).reset_index(drop=True)
    return results


def _annotate_compatible_geometry(
    *,
    compatible_lhs: pd.DataFrame,
    existing: pd.DataFrame,
    freeze: dict[str, Any],
    bounds_by_provider: dict[str, Any],
    ratio_max: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    annotated_frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        existing_compatible, base_summary = _existing_geometry(existing, provider, ratio_max)
        existing_coords = existing_compatible[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
        mins = existing_coords.min(axis=0)
        maxs = existing_coords.max(axis=0)

        provider_lhs = compatible_lhs[
            compatible_lhs["provider"].astype(str) == provider
        ].copy()
        bounds = bounds_by_provider[provider]
        frozen = freeze["provider_surrogates"][provider]
        frozen_coord = _normalize_parameters(
            float(frozen["mean_service_time"]),
            float(frozen["cost_rate"]),
            float(frozen["service_cv"]),
            bounds,
        )

        if not provider_lhs.empty:
            lhs_coords = provider_lhs[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
            distances = np.linalg.norm(
                lhs_coords[:, None, :] - existing_coords[None, :, :], axis=2
            )
            provider_lhs["nearest_existing_compatible_distance"] = distances.min(axis=1)
            provider_lhs["distance_from_frozen_m1"] = np.linalg.norm(
                lhs_coords - frozen_coord[None, :], axis=1
            )
            provider_lhs["outside_existing_compatible_bbox"] = (
                (lhs_coords < mins[None, :] - TOL).any(axis=1)
                | (lhs_coords > maxs[None, :] + TOL).any(axis=1)
            )
            union_coords = np.vstack([existing_coords, lhs_coords])
            max_nearest = float(provider_lhs["nearest_existing_compatible_distance"].max())
            max_from_m1 = float(provider_lhs["distance_from_frozen_m1"].max())
            n_outside = int(provider_lhs["outside_existing_compatible_bbox"].sum())
            annotated_frames.append(provider_lhs)
        else:
            union_coords = existing_coords
            max_nearest = float("nan")
            max_from_m1 = float("nan")
            n_outside = 0

        union_max_pairwise = _max_pairwise_distance(union_coords)
        summaries.append(
            {
                **base_summary,
                "n_lhs_compatible": int(len(provider_lhs)),
                "n_lhs_compatible_outside_existing_bbox": n_outside,
                "max_nearest_existing_compatible_distance": max_nearest,
                "max_lhs_compatible_distance_from_frozen_m1": max_from_m1,
                "union_max_pairwise_distance": union_max_pairwise,
                "union_diameter_fraction_of_unit_cube": union_max_pairwise / math.sqrt(3.0),
                "union_z_log_mu_span": _span(union_coords, 0),
                "union_z_log_kappa_span": _span(union_coords, 1),
                "union_z_cv_span": _span(union_coords, 2),
                "max_pairwise_expansion": union_max_pairwise - float(base_summary["existing_max_pairwise_distance"]),
            }
        )

    annotated = (
        pd.concat(annotated_frames, ignore_index=True)
        if annotated_frames
        else pd.DataFrame()
    )
    if not annotated.empty:
        annotated = annotated.sort_values(
            ["provider", "nearest_existing_compatible_distance"],
            ascending=[True, False],
        ).reset_index(drop=True)
    return annotated, pd.DataFrame(summaries)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run M2-A2 non-adaptive public-I1 coverage audit"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_a2_nonadaptive_coverage_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_a2_nonadaptive_coverage_v1",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="materialize the frozen LHS design and existing-geometry summary without simulations",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    contract_path = args.contract.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M2-A2 contract status")
    firewall = dict(contract["firewall"])
    if any(bool(firewall[key]) for key in firewall):
        raise RuntimeError("M2-A2 firewall contract must forbid all listed hidden/adaptive operations")

    inputs = dict(contract["inputs"])
    card_root = (HERE / str(inputs["public_i1_root"])).resolve()
    metadata_by_provider, surfaces, public_manifest = load_verified_public_i1_cards(card_root)
    base_contract_path = (HERE / str(inputs["base_m1_contract"])).resolve()
    expanded_contract_path = (HERE / str(inputs["providerC_expanded_contract"])).resolve()
    freeze_path = (HERE / str(inputs["frozen_m1"])).resolve()
    landscape_path = (HERE / str(inputs["existing_landscape"])).resolve()

    base_contract = _read_json(base_contract_path)
    expanded_contract = _read_json(expanded_contract_path)
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise RuntimeError("unexpected frozen M1-v2 manifest status")
    existing = pd.read_csv(landscape_path)

    ratio_max = float(contract["compatibility_rule"]["loss_ratio_max_to_existing_best_search_mse"])
    design, bounds_by_provider = _build_design(
        contract=contract,
        metadata_by_provider=metadata_by_provider,
        base_contract=base_contract,
        expanded_c_contract=expanded_contract,
    )
    design_path = output_root / "m2_a2_lhs_design.csv"
    design.to_csv(design_path, index=False)

    existing_summaries = []
    for provider in PROVIDERS:
        _, summary = _existing_geometry(existing, provider, ratio_max)
        existing_summaries.append(summary)
    existing_geometry = pd.DataFrame(existing_summaries)
    existing_geometry.to_csv(output_root / "m2_a2_existing_geometry.csv", index=False)

    print("M2_A2_NONADAPTIVE_DESIGN_FROZEN_PASS")
    print("\nEXISTING_TPE_COMPATIBLE_GEOMETRY")
    print(existing_geometry.to_string(index=False))
    if args.prepare_only:
        manifest = {
            "status": "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_DESIGN_PREPARED_V1",
            "contract_sha256": _sha256(contract_path),
            "design_sha256": _sha256(design_path),
            "graph_simulation": False,
            "graph_prediction_read": False,
            "graph_whitebox_read": False,
            "reran_optuna": False,
            "n_lhs_points_total": int(len(design)),
            "git_commit": _git_head(FIRST_SCIENCE.parent),
        }
        _write_json(output_root / "m2_a2_manifest_v1.json", manifest)
        print("M2_A2_PREPARE_ONLY_COMPLETE")
        print(f"output={output_root}")
        return

    scoring = dict(contract["local_scoring"])
    trajectory_seeds = _seed_bank(
        int(scoring["trajectory_seed_start"]),
        int(scoring["n_trajectories"]),
    )
    canonical_ipt = float(base_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(base_contract["pilot_scope"]["execution_fraction"])

    results = _evaluate_design(
        design=design,
        existing=existing,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        trajectory_seeds=trajectory_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        ratio_max=ratio_max,
        output_root=output_root,
    )
    expected_n = int(contract["sampler"]["n_points_per_provider"]) * len(PROVIDERS)
    if len(results) != expected_n:
        raise RuntimeError(f"M2-A2 incomplete: expected {expected_n} evaluated LHS points, found {len(results)}")

    compatible = results[results["lhs_compatible"].astype(bool)].copy()
    annotated, geometry_summary = _annotate_compatible_geometry(
        compatible_lhs=compatible,
        existing=existing,
        freeze=freeze,
        bounds_by_provider=bounds_by_provider,
        ratio_max=ratio_max,
    )
    annotated.to_csv(output_root / "m2_a2_compatible_lhs.csv", index=False)
    geometry_summary.to_csv(output_root / "m2_a2_geometry_summary.csv", index=False)

    elapsed = time.perf_counter() - started
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    manifest = {
        "status": "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_AUDIT_COMPLETE_V1",
        "contract_sha256": _sha256(contract_path),
        "design_sha256": _sha256(design_path),
        "existing_landscape_sha256": _sha256(landscape_path),
        "frozen_m1_sha256": _sha256(freeze_path),
        "public_i1_manifest_status": public_manifest.get("status"),
        "reran_optuna": False,
        "sampler_adaptive": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "private_phase2_provider_traces_read": False,
        "n_lhs_points_per_provider": int(contract["sampler"]["n_points_per_provider"]),
        "n_lhs_points_total": int(len(design)),
        "n_local_trajectories_per_point": int(len(trajectory_seeds)),
        "total_local_trajectories": int(len(design) * len(trajectory_seeds)),
        "same_seed_bank_as_original_m1_search": True,
        "compatibility_loss_ratio_max": ratio_max,
        "compatible_counts": {
            provider: int((compatible["provider"].astype(str) == provider).sum())
            for provider in PROVIDERS
        },
        "python_wall_seconds": float(elapsed),
        "peak_rss_platform_units": peak_rss,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "lhs_design": "m2_a2_lhs_design.csv",
            "existing_geometry": "m2_a2_existing_geometry.csv",
            "lhs_results": "m2_a2_lhs_results.csv",
            "compatible_lhs": "m2_a2_compatible_lhs.csv",
            "geometry_summary": "m2_a2_geometry_summary.csv",
            "compatible_surfaces": "compatible_surfaces/<candidate_id>/"
        },
        "interpretation_guard": contract["interpretation_guard"],
    }
    _write_json(output_root / "m2_a2_manifest_v1.json", manifest)

    print("\nM2_A2_NONADAPTIVE_GEOMETRY_SUMMARY")
    print(geometry_summary.to_string(index=False))
    if not annotated.empty:
        columns = [
            "provider",
            "candidate_id",
            "lhs_loss_ratio_to_existing_best",
            "nearest_existing_compatible_distance",
            "distance_from_frozen_m1",
            "outside_existing_compatible_bbox",
            "mean_service_time",
            "cost_rate",
            "service_cv",
        ]
        print("\nMOST_REMOTE_NONADAPTIVE_COMPATIBLE_POINTS")
        print(annotated[columns].groupby("provider", group_keys=False).head(5).to_string(index=False))
    else:
        print("\nNO_NONADAPTIVE_LHS_POINT_MET_THE_FROZEN_1.25X_COMPATIBILITY_CEILING")

    print("M2_A2_NONADAPTIVE_COVERAGE_AUDIT_COMPLETE")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
