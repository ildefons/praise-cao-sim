"""Prepare the Phase-4 M2-A local inverse-landscape diagnostic.

This script DOES NOT rerun Optuna and DOES NOT read any graph-level or white-box
result. It consumes only existing M1-v2 search-trial tables plus frozen public
I1 metadata/contracts. Its purpose is to expose whether parameter-diverse,
near-equivalent public-I1 fits already exist before any graph composition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
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

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_STATUS = "PHASE4_M2_A_LOCAL_LANDSCAPE_INSPECTION_V1"
REQUIRED_TRIAL_COLUMNS = {
    "trial_number",
    "search_mse",
    "mean_service_time",
    "cost_rate",
    "service_cv",
}


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


def _provider_from_path(path: Path) -> str | None:
    text = str(path)
    hits = [provider for provider in PROVIDERS if provider in text]
    if len(hits) == 1:
        return hits[0]
    return None


def _public_card_metadata(card_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    manifest_path = card_root / "i1_rho_conditioned_manifest_v1.json"
    manifest = _read_json(manifest_path)
    cards = manifest.get("cards")
    if not isinstance(cards, dict):
        raise ValueError("public I1 manifest lacks cards mapping")

    metadata: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        if provider not in cards:
            raise ValueError(f"public I1 manifest lacks {provider}")
        record = dict(cards[provider])
        directory = card_root / str(record["directory"])
        card_path = directory / "card.json"
        if "card_json_sha256" in record and _sha256(card_path) != str(record["card_json_sha256"]):
            raise RuntimeError(f"{provider} public card hash mismatch")
        metadata[provider] = _read_json(card_path)
    return metadata, manifest


def _normalization_contract(provider: str, base_contract: dict[str, Any], expanded_c_contract: dict[str, Any]) -> dict[str, Any]:
    return expanded_c_contract if provider == "ProviderC" else base_contract


def _normalize(frame: pd.DataFrame, bounds) -> pd.DataFrame:
    result = frame.copy()
    log_mu_lo = math.log(float(bounds.mean_service_time_lower))
    log_mu_hi = math.log(float(bounds.mean_service_time_upper))
    log_k_lo = math.log(float(bounds.cost_rate_lower))
    log_k_hi = math.log(float(bounds.cost_rate_upper))
    cv_lo = float(bounds.service_cv_lower)
    cv_hi = float(bounds.service_cv_upper)

    result["z_log_mu"] = (
        np.log(result["mean_service_time"].astype(float)) - log_mu_lo
    ) / (log_mu_hi - log_mu_lo)
    result["z_log_kappa"] = (
        np.log(result["cost_rate"].astype(float)) - log_k_lo
    ) / (log_k_hi - log_k_lo)
    result["z_cv"] = (
        result["service_cv"].astype(float) - cv_lo
    ) / (cv_hi - cv_lo)

    coords = result[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(dtype=float)
    if not np.all(np.isfinite(coords)):
        raise ValueError("non-finite normalized candidate coordinate")
    if np.any(coords < -1e-9) or np.any(coords > 1.0 + 1e-9):
        bad = result[
            (result[["z_log_mu", "z_log_kappa", "z_cv"]] < -1e-9).any(axis=1)
            | (result[["z_log_mu", "z_log_kappa", "z_cv"]] > 1.0 + 1e-9).any(axis=1)
        ]
        raise ValueError(
            "candidate lies outside declared normalization bounds; inspect source studies:\n"
            + bad.head(10).to_string(index=False)
        )
    return result


def _deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.sort_values(
        ["search_mse", "trial_number", "source_relpath"], kind="mergesort"
    ).copy()
    work["theta_key"] = work.apply(
        lambda row: "|".join(
            [
                format(float(row["mean_service_time"]), ".17g"),
                format(float(row["cost_rate"]), ".17g"),
                format(float(row["service_cv"]), ".17g"),
            ]
        ),
        axis=1,
    )
    duplicate_counts = work.groupby("theta_key").size().rename("duplicate_source_count")
    work = work.drop_duplicates("theta_key", keep="first").copy()
    work = work.merge(duplicate_counts, on="theta_key", how="left")
    return work.drop(columns=["theta_key"]).reset_index(drop=True)


def _max_pairwise_distance(coords: np.ndarray) -> float:
    if len(coords) <= 1:
        return 0.0
    best = 0.0
    for i in range(len(coords) - 1):
        distances = np.linalg.norm(coords[i + 1 :] - coords[i], axis=1)
        if len(distances):
            best = max(best, float(np.max(distances)))
    return best


def _farthest_point_preview(pool: pd.DataFrame, k: int) -> pd.DataFrame:
    ordered = pool.sort_values(
        ["search_mse", "trial_number", "source_relpath"], kind="mergesort"
    ).reset_index(drop=True)
    if ordered.empty:
        return ordered

    coords = ordered[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(dtype=float)
    selected = [0]
    min_distances = [np.nan]
    target = min(int(k), len(ordered))

    while len(selected) < target:
        remaining = [idx for idx in range(len(ordered)) if idx not in selected]
        candidates: list[tuple[float, float, int, str, int]] = []
        for idx in remaining:
            min_distance = min(
                float(np.linalg.norm(coords[idx] - coords[j])) for j in selected
            )
            row = ordered.iloc[idx]
            candidates.append(
                (
                    -min_distance,
                    float(row["search_mse"]),
                    int(row["trial_number"]),
                    str(row["source_relpath"]),
                    idx,
                )
            )
        candidates.sort()
        chosen = candidates[0][-1]
        selected.append(chosen)
        min_distances.append(-candidates[0][0])

    preview = ordered.iloc[selected].copy().reset_index(drop=True)
    preview.insert(0, "selection_order", np.arange(1, len(preview) + 1, dtype=int))
    preview["min_distance_to_previous_set"] = min_distances
    return preview


def run(
    *,
    contract_path: Path,
    trial_root: Path,
    card_root: Path,
    base_contract_path: Path,
    expanded_c_contract_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    start = time.perf_counter()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise ValueError("unexpected M2-A landscape contract status")

    metadata_by_provider, i1_manifest = _public_card_metadata(card_root)
    base_contract = _read_json(base_contract_path)
    expanded_c_contract = _read_json(expanded_c_contract_path)

    discovery = dict(contract["existing_search_landscape_policy"])
    filename = str(discovery["search_trial_filename"])
    min_trials = int(discovery["minimum_completed_trials_per_source"])
    discovered = sorted(trial_root.rglob(filename))
    if not discovered:
        raise FileNotFoundError(
            f"No {filename} files found under {trial_root}. "
            "The M1 result directories may not be present locally."
        )

    rows_by_provider: dict[str, list[pd.DataFrame]] = {p: [] for p in PROVIDERS}
    source_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []

    for path in discovered:
        provider = _provider_from_path(path)
        if provider is None:
            skipped_records.append({"path": str(path), "reason": "provider_not_identifiable_from_path"})
            continue
        frame = pd.read_csv(path)
        missing = sorted(REQUIRED_TRIAL_COLUMNS.difference(frame.columns))
        if missing:
            skipped_records.append({"path": str(path), "reason": f"missing_columns:{','.join(missing)}"})
            continue
        frame = frame.dropna(subset=list(REQUIRED_TRIAL_COLUMNS)).copy()
        if len(frame) < min_trials:
            skipped_records.append({"path": str(path), "reason": f"only_{len(frame)}_completed_trials"})
            continue

        frame = frame[list(REQUIRED_TRIAL_COLUMNS)].copy()
        frame["provider"] = provider
        frame["source_relpath"] = str(path.relative_to(FIRST_SCIENCE)) if path.is_relative_to(FIRST_SCIENCE) else str(path)
        rows_by_provider[provider].append(frame)
        source_records.append(
            {
                "provider": provider,
                "path": str(path),
                "n_completed_rows": int(len(frame)),
                "sha256": _sha256(path),
            }
        )

    all_frames: list[pd.DataFrame] = []
    provider_summaries: dict[str, Any] = {}
    band_rows: list[dict[str, Any]] = []
    preview_frames: list[pd.DataFrame] = []
    multipliers = [float(x) for x in contract["loss_bands"]["multipliers"]]
    preview_k = int(contract["diversity"]["preview_candidates_per_provider_per_band"])

    for provider in PROVIDERS:
        if not rows_by_provider[provider]:
            raise RuntimeError(
                f"No non-smoke >= {min_trials}-trial landscape found for {provider} under {trial_root}"
            )
        merged = pd.concat(rows_by_provider[provider], ignore_index=True)
        merged = _deduplicate(merged)
        normalization_contract = _normalization_contract(
            provider, base_contract, expanded_c_contract
        )
        bounds = build_search_bounds(metadata_by_provider[provider], normalization_contract)
        merged = _normalize(merged, bounds)
        merged = merged.sort_values(
            ["search_mse", "trial_number", "source_relpath"], kind="mergesort"
        ).reset_index(drop=True)
        best_loss = float(merged.iloc[0]["search_mse"])
        merged["loss_ratio_to_best"] = merged["search_mse"].astype(float) / best_loss
        merged["loss_delta_from_best"] = merged["search_mse"].astype(float) - best_loss
        merged["search_rank"] = np.arange(1, len(merged) + 1, dtype=int)
        all_frames.append(merged)

        provider_summaries[provider] = {
            "n_source_tables": int(len(rows_by_provider[provider])),
            "n_unique_candidates": int(len(merged)),
            "best_search_mse": best_loss,
            "normalization_bounds": bounds.as_dict(),
        }

        best_coord = merged.iloc[0][["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(dtype=float)
        for multiplier in multipliers:
            pool = merged[merged["loss_ratio_to_best"] <= multiplier + 1e-15].copy()
            coords = pool[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(dtype=float)
            if len(coords):
                max_from_best = float(np.max(np.linalg.norm(coords - best_coord, axis=1)))
                max_pairwise = _max_pairwise_distance(coords)
            else:
                max_from_best = float("nan")
                max_pairwise = float("nan")
            band_rows.append(
                {
                    "provider": provider,
                    "loss_multiplier": multiplier,
                    "n_candidates": int(len(pool)),
                    "best_search_mse": best_loss,
                    "worst_search_mse_in_band": float(pool["search_mse"].max()) if len(pool) else np.nan,
                    "max_distance_from_best": max_from_best,
                    "max_pairwise_distance": max_pairwise,
                    "z_log_mu_span": float(pool["z_log_mu"].max() - pool["z_log_mu"].min()) if len(pool) else np.nan,
                    "z_log_kappa_span": float(pool["z_log_kappa"].max() - pool["z_log_kappa"].min()) if len(pool) else np.nan,
                    "z_cv_span": float(pool["z_cv"].max() - pool["z_cv"].min()) if len(pool) else np.nan,
                }
            )
            preview = _farthest_point_preview(pool, preview_k)
            if len(preview):
                preview.insert(0, "loss_multiplier", multiplier)
                preview_frames.append(preview)

    output_directory.mkdir(parents=True, exist_ok=True)
    all_candidates = pd.concat(all_frames, ignore_index=True)
    all_candidates.to_csv(output_directory / "m2_a_all_candidates.csv", index=False)
    band_summary = pd.DataFrame(band_rows)
    band_summary.to_csv(output_directory / "m2_a_loss_band_summary.csv", index=False)
    diverse_preview = pd.concat(preview_frames, ignore_index=True)
    diverse_preview.to_csv(
        output_directory / "m2_a_diverse_candidate_preview.csv", index=False
    )

    elapsed = time.perf_counter() - start
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    manifest = {
        "status": EXPECTED_STATUS,
        "scientific_stage": "M2-A local landscape inspection only; no candidate compatibility threshold frozen yet",
        "reran_optuna": False,
        "graph_whitebox_read": False,
        "graph_prediction_read_for_selection": False,
        "contract": {
            "path": str(contract_path),
            "sha256": _sha256(contract_path),
        },
        "public_i1_manifest_status": i1_manifest.get("status"),
        "source_trial_tables": source_records,
        "skipped_trial_tables": skipped_records,
        "providers": provider_summaries,
        "loss_band_multipliers": multipliers,
        "cost": {
            "formal_source_trial_tables_read": int(len(source_records)),
            "formal_unique_candidate_rows_processed": int(len(all_candidates)),
            "wall_seconds": float(elapsed),
            "peak_rss_platform_units": peak_rss,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": contract["next_gate"],
    }
    _write_json(output_directory / "m2_a_landscape_manifest_v1.json", manifest)

    print("M2_A_LOCAL_LANDSCAPE_INSPECTION_PASS")
    print("\nLOSS BAND SUMMARY")
    print(band_summary.to_string(index=False))
    print(f"\noutput={output_directory.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect existing M1-v2 Optuna landscapes for M2-A without rerunning optimization"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_a_landscape_v1.json",
    )
    parser.add_argument(
        "--trial-root",
        type=Path,
        default=PHASE3 / "results",
    )
    parser.add_argument(
        "--card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--base-m1-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m1_contract_v2.json",
    )
    parser.add_argument(
        "--expanded-c-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m1_contract_v2_providerC_expanded_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_a_landscape_v1",
    )
    args = parser.parse_args()

    run(
        contract_path=args.contract.resolve(),
        trial_root=args.trial_root.resolve(),
        card_root=args.card_root.resolve(),
        base_contract_path=args.base_m1_contract.resolve(),
        expanded_c_contract_path=args.expanded_c_contract.resolve(),
        output_directory=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
