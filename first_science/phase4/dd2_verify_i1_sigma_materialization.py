#!/usr/bin/env python3
"""DD-2: verify public rho-conditioned I1 sigma materialization from frozen T_i^sigma.

Read-only scientific audit. No simulator is imported or executed.

For each provider:
1. verify the frozen private T_i^sigma ledger hash/row/trajectory count;
2. verify the public card/card-surface hashes against the public manifest;
3. take the already-public frozen A_i(rho_region) regions as fixed inputs;
4. independently recompute the complete sigma_i(A_i,H;rho_query) surface
   directly from private T_i^sigma arrays, without calling the original
   materialization routine;
5. compare every published point, count, CI and boundary field against the
   recomputed surface.

This intentionally does NOT refit or reconstruct A_i. DD-2 isolates the
T_i^sigma -> public sigma-surface materialization boundary.

Outputs are audit-only and written under phase4/results/dd2_...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
if str(PHASE2) not in sys.path:
    sys.path.insert(0, str(PHASE2))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa: E402

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_FREEZE_STATUS = "FROZEN_PHASE2_I1_RHO_CONDITIONED_V1"
EXPECTED_SIGMA_ACQ_STATUS = "FROZEN_PHASE2_I1_PRIVATE_ACQUISITION_CORPUS_V1"
TOL = 1e-12


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snap(values: pd.Series, reference: list[float], label: str) -> pd.Series:
    ref = np.asarray(reference, dtype=float)
    out: list[float] = []
    for raw in values.astype(float).to_numpy():
        matches = np.flatnonzero(np.abs(ref - float(raw)) <= TOL)
        if len(matches) != 1:
            raise RuntimeError(
                f"{label}: value {raw!r} has {len(matches)} matches within atol={TOL}"
            )
        out.append(float(ref[int(matches[0])]))
    return pd.Series(out, index=values.index, dtype=float)


def _normalize_surface(
    frame: pd.DataFrame,
    *,
    region_rhos: list[float],
    query_rhos: list[float],
    horizons: list[float],
    label: str,
) -> pd.DataFrame:
    out = frame.copy()
    out["region_rho"] = _snap(out["region_rho"], region_rhos, f"{label} region_rho")
    out["rho"] = _snap(out["rho"], query_rhos, f"{label} rho")
    out["horizon"] = _snap(out["horizon"], horizons, f"{label} horizon")
    keys = ["provider_id", "region_id", "region_rho", "rho", "horizon"]
    if out.duplicated(keys).any():
        raise RuntimeError(f"{label}: duplicate public-support points")
    return out.sort_values(keys).reset_index(drop=True)


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = float(successes) / float(trials)
    z2 = z * z
    denom = 1.0 + z2 / float(trials)
    center = (p + z2 / (2.0 * float(trials))) / denom
    half = (
        z
        * np.sqrt(
            p * (1.0 - p) / float(trials)
            + z2 / (4.0 * float(trials) * float(trials))
        )
        / denom
    )
    return max(0.0, float(center - half)), min(1.0, float(center + half))


def _recompute_surface(
    *,
    provider: str,
    sigma_ledger: pd.DataFrame,
    public_metadata: dict[str, Any],
) -> pd.DataFrame:
    """Independent vectorized rematerialization of the public sigma surface.

    This deliberately does not call build_i1_provider_card or the original
    materialization routine. It reproduces the frozen SLA semantics directly
    from the ledger arrays, which makes DD-2 both faster and less circular.
    """
    regions = [dict(v) for v in public_metadata["rho_conditioned_regions"]]
    query_rhos = np.asarray(
        [float(v) for v in public_metadata["supported_query_rho_values"]],
        dtype=float,
    )
    horizons = np.asarray(
        [float(v) for v in public_metadata["supported_horizons"]],
        dtype=float,
    )
    workload = dict(public_metadata["workload_contract"])
    stop_time = float(workload["horizon_max"])
    accounting_origin = float(workload["accounting_origin"])
    if abs(accounting_origin) > TOL:
        raise RuntimeError("DD-2 expects frozen accounting_origin=0")

    trajectories = [
        frame.sort_values(["emission", "request_id"]).copy()
        for _, frame in sigma_ledger.groupby("trajectory", sort=True)
    ]
    n_traj = len(trajectories)
    if n_traj <= 0:
        raise RuntimeError(f"{provider}: no T_i^sigma trajectories")

    rows: list[dict[str, Any]] = []
    for region in regions:
        l_max = float(region["l_max"])
        c_max = float(region["c_max"])
        q_min = float(region["q_min"])

        # pass_counts[rho_index, horizon_index]
        pass_counts = np.zeros((len(query_rhos), len(horizons)), dtype=np.int32)

        for frame in trajectories:
            emission = frame["emission"].astype(float).to_numpy()
            completion = pd.to_numeric(
                frame["completion"], errors="coerce"
            ).to_numpy(dtype=float)
            cost = pd.to_numeric(frame["C"], errors="coerce").to_numpy(dtype=float)
            quality = pd.to_numeric(frame["Q"], errors="coerce").to_numpy(dtype=float)

            deadline = emission + l_max
            completed_in_time = np.isfinite(completion) & (
                completion <= deadline + TOL
            )
            decision_time = np.where(completed_in_time, completion, deadline)

            # Only decisions observable by the frozen simulation stop can ever
            # enter c_i(A_i,H) for H<=stop_time.
            observable = decision_time <= stop_time + TOL
            dt = decision_time[observable]
            compliant = (
                completed_in_time[observable]
                & np.isfinite(cost[observable])
                & np.isfinite(quality[observable])
                & (cost[observable] <= c_max)
                & (quality[observable] >= q_min)
            )

            order = np.argsort(dt, kind="mergesort")
            dt = dt[order]
            compliant = compliant[order].astype(np.int32)
            cumulative_compliant = np.cumsum(compliant, dtype=np.int32)

            n_decided = np.searchsorted(
                dt, horizons + TOL, side="right"
            ).astype(np.int32)
            n_compliant = np.zeros(len(horizons), dtype=np.int32)
            nonzero = n_decided > 0
            n_compliant[nonzero] = cumulative_compliant[n_decided[nonzero] - 1]

            fractions = np.ones(len(horizons), dtype=float)
            fractions[nonzero] = (
                n_compliant[nonzero].astype(float)
                / n_decided[nonzero].astype(float)
            )
            pass_counts += (
                fractions[None, :] + TOL >= query_rhos[:, None]
            ).astype(np.int32)

        for ri, rho in enumerate(query_rhos):
            for hi, horizon in enumerate(horizons):
                success = int(pass_counts[ri, hi])
                lower, upper = _wilson_interval(success, n_traj)
                rows.append(
                    {
                        "provider_id": provider,
                        "region_id": str(region["region_id"]),
                        "region_rho": float(region["region_rho"]),
                        "l_max": l_max,
                        "c_max": c_max,
                        "q_min": q_min,
                        "rho": float(rho),
                        "horizon": float(horizon),
                        "sigma_hat": float(success / n_traj),
                        "sigma_ci95_lower": float(lower),
                        "sigma_ci95_upper": float(upper),
                        "n_success": success,
                        "n_trajectories": n_traj,
                    }
                )

    return pd.DataFrame(rows).sort_values(
        ["region_id", "rho", "horizon"]
    ).reset_index(drop=True)


def _compare_surfaces(
    published: pd.DataFrame,
    recomputed: pd.DataFrame,
    *,
    provider: str,
    region_rhos: list[float],
    query_rhos: list[float],
    horizons: list[float],
) -> tuple[dict[str, Any], pd.DataFrame]:
    pub = _normalize_surface(
        published,
        region_rhos=region_rhos,
        query_rhos=query_rhos,
        horizons=horizons,
        label=f"{provider} published",
    )
    rec = _normalize_surface(
        recomputed,
        region_rhos=region_rhos,
        query_rhos=query_rhos,
        horizons=horizons,
        label=f"{provider} recomputed",
    )

    keys = ["provider_id", "region_id", "region_rho", "rho", "horizon"]
    merged = pub.merge(
        rec,
        on=keys,
        how="outer",
        suffixes=("_published", "_recomputed"),
        indicator=True,
        validate="one_to_one",
    )
    missing_points = int((merged["_merge"] != "both").sum())

    expected_numeric = [
        "l_max",
        "c_max",
        "q_min",
        "sigma_hat",
        "sigma_ci95_lower",
        "sigma_ci95_upper",
        "n_success",
        "n_trajectories",
    ]
    missing_columns = [
        col
        for col in expected_numeric
        if col not in pub.columns or col not in rec.columns
    ]
    if missing_columns:
        raise RuntimeError(
            f"{provider}: expected comparison columns missing: {missing_columns}"
        )

    mismatch_rows: list[dict[str, Any]] = []
    max_abs: dict[str, float] = {}
    exact_count_mismatches: dict[str, int] = {}

    both = merged[merged["_merge"] == "both"].copy()
    for col in expected_numeric:
        a = pd.to_numeric(both[f"{col}_published"], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(both[f"{col}_recomputed"], errors="coerce").to_numpy(dtype=float)
        if np.any(~np.isfinite(a)) or np.any(~np.isfinite(b)):
            raise RuntimeError(f"{provider}: non-finite values in compared column {col}")
        delta = np.abs(a - b)
        max_abs[col] = float(np.max(delta)) if len(delta) else float("nan")

        if col in ("n_success", "n_trajectories"):
            bad = delta != 0.0
            exact_count_mismatches[col] = int(np.count_nonzero(bad))
        else:
            bad = delta > TOL

        bad_idx = np.flatnonzero(bad)
        for idx in bad_idx[:100]:
            row = both.iloc[int(idx)]
            mismatch_rows.append(
                {
                    "provider": provider,
                    "provider_id": row["provider_id"],
                    "region_id": row["region_id"],
                    "region_rho": row["region_rho"],
                    "rho": row["rho"],
                    "horizon": row["horizon"],
                    "column": col,
                    "published": float(a[int(idx)]),
                    "recomputed": float(b[int(idx)]),
                    "abs_delta": float(delta[int(idx)]),
                }
            )

    n_numeric_mismatches = len(mismatch_rows)
    passed = (
        missing_points == 0
        and all(v <= TOL for k, v in max_abs.items() if k not in ("n_success", "n_trajectories"))
        and all(v == 0 for v in exact_count_mismatches.values())
    )

    summary = {
        "provider": provider,
        "n_published_points": int(len(pub)),
        "n_recomputed_points": int(len(rec)),
        "missing_or_extra_support_points": missing_points,
        "max_abs_delta": max_abs,
        "exact_count_mismatches": exact_count_mismatches,
        "comparison_tolerance": TOL,
        "pass": bool(passed),
    }
    return summary, pd.DataFrame(mismatch_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DD-2 zero-simulation verification of public I1 sigma surfaces"
    )
    parser.add_argument(
        "--freeze-manifest",
        type=Path,
        default=PHASE2 / "phase2_i1_rho_conditioned_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--sigma-contract",
        type=Path,
        default=PHASE2 / "config_phase2_i1_sigma_acquisition_v1.json",
    )
    parser.add_argument(
        "--sigma-private-root",
        type=Path,
        default=PHASE2 / "results" / "i1_sigma_acquisition_v1" / "private",
    )
    parser.add_argument(
        "--public-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "dd2_i1_sigma_materialization_v1",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    freeze_path = args.freeze_manifest.resolve()
    sigma_contract_path = args.sigma_contract.resolve()
    sigma_private_root = args.sigma_private_root.resolve()
    public_root = args.public_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise RuntimeError("unexpected rho-conditioned I1 freeze-manifest status")

    sigma_contract = _read_json(sigma_contract_path)
    sigma_manifest_path = sigma_private_root / "acquisition_manifest.json"
    sigma_manifest = _read_json(sigma_manifest_path)
    if sigma_manifest.get("status") != EXPECTED_SIGMA_ACQ_STATUS:
        raise RuntimeError("unexpected T_i^sigma acquisition-manifest status")
    if sigma_manifest.get("acquisition_config") != sigma_contract:
        raise RuntimeError("T_i^sigma acquisition manifest does not match frozen contract")

    acq = dict(sigma_contract["acquisition"])
    expected_seeds = list(
        range(int(acq["seed_start"]), int(acq["seed_end_inclusive"]) + 1)
    )
    recorded_seeds = [int(v) for v in sigma_manifest["seed_bank"]]
    if recorded_seeds != expected_seeds:
        raise RuntimeError("T_i^sigma recorded seed bank differs from contract")
    if expected_seeds != list(range(6100, 6200)):
        raise RuntimeError("DD-2 expected frozen T_i^sigma seed bank 6100..6199")

    public_manifest_path = public_root / "i1_rho_conditioned_manifest_v1.json"
    expected_public_manifest_hash = str(freeze["public_i1_manifest"]["sha256"])
    actual_public_manifest_hash = _sha256(public_manifest_path)
    if actual_public_manifest_hash != expected_public_manifest_hash:
        raise RuntimeError(
            "public I1 manifest SHA-256 differs from rho-conditioned freeze manifest"
        )
    public_manifest = _read_json(public_manifest_path)

    provider_summaries: list[dict[str, Any]] = []
    mismatch_frames: list[pd.DataFrame] = []
    evidence_rows: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        ledger_path = sigma_private_root / provider / "provider_request_ledgers.csv"
        if not ledger_path.exists():
            raise FileNotFoundError(f"missing frozen T_i^sigma ledger: {ledger_path}")
        actual_ledger_hash = _sha256(ledger_path)
        expected_ledger_hash = str(sigma_manifest["provider_sha256"][provider])
        if actual_ledger_hash != expected_ledger_hash:
            raise RuntimeError(f"{provider}: T_i^sigma ledger SHA-256 mismatch")

        sigma_ledger = pd.read_csv(ledger_path)
        expected_rows = int(sigma_manifest["provider_rows"][provider])
        expected_trajectories = int(sigma_manifest["provider_trajectories"][provider])
        if len(sigma_ledger) != expected_rows:
            raise RuntimeError(f"{provider}: T_i^sigma row count mismatch")
        if int(sigma_ledger["trajectory"].nunique()) != expected_trajectories:
            raise RuntimeError(f"{provider}: T_i^sigma trajectory count mismatch")

        card_dir = public_root / provider
        card_path = card_dir / "card.json"
        surface_path = card_dir / "sigma_surface.csv"
        card_manifest = public_manifest["cards"][provider]
        if _sha256(card_path) != str(card_manifest["card_json_sha256"]):
            raise RuntimeError(f"{provider}: public card.json SHA-256 mismatch")
        if _sha256(surface_path) != str(card_manifest["sigma_surface_sha256"]):
            raise RuntimeError(f"{provider}: public sigma_surface.csv SHA-256 mismatch")

        metadata, published = load_rho_conditioned_i1_provider_card(card_dir)
        recomputed = _recompute_surface(
            provider=provider,
            sigma_ledger=sigma_ledger,
            public_metadata=metadata,
        )

        region_rhos = [float(v) for v in metadata["supported_region_rho_values"]]
        query_rhos = [float(v) for v in metadata["supported_query_rho_values"]]
        horizons = [float(v) for v in metadata["supported_horizons"]]

        summary, mismatches = _compare_surfaces(
            published,
            recomputed,
            provider=provider,
            region_rhos=region_rhos,
            query_rhos=query_rhos,
            horizons=horizons,
        )
        provider_summaries.append(summary)
        if not mismatches.empty:
            mismatch_frames.append(mismatches)

        recomputed_path = output / f"{provider}_recomputed_sigma_surface.csv"
        recomputed.to_csv(recomputed_path, index=False)
        evidence_rows.append(
            {
                "provider": provider,
                "sigma_ledger_sha256": actual_ledger_hash,
                "sigma_ledger_rows": int(len(sigma_ledger)),
                "sigma_ledger_trajectories": int(sigma_ledger["trajectory"].nunique()),
                "public_card_sha256": _sha256(card_path),
                "public_surface_sha256": _sha256(surface_path),
                "recomputed_surface_sha256": _sha256(recomputed_path),
                "n_surface_points": int(len(recomputed)),
                "pass": bool(summary["pass"]),
            }
        )

    summary_df = pd.DataFrame(
        [
            {
                "provider": item["provider"],
                "n_published_points": item["n_published_points"],
                "n_recomputed_points": item["n_recomputed_points"],
                "missing_or_extra_support_points": item["missing_or_extra_support_points"],
                "max_abs_l_max": item["max_abs_delta"]["l_max"],
                "max_abs_c_max": item["max_abs_delta"]["c_max"],
                "max_abs_q_min": item["max_abs_delta"]["q_min"],
                "max_abs_sigma_hat": item["max_abs_delta"]["sigma_hat"],
                "max_abs_ci_lower": item["max_abs_delta"]["sigma_ci95_lower"],
                "max_abs_ci_upper": item["max_abs_delta"]["sigma_ci95_upper"],
                "n_success_mismatches": item["exact_count_mismatches"]["n_success"],
                "n_trajectory_count_mismatches": item["exact_count_mismatches"]["n_trajectories"],
                "pass": item["pass"],
            }
            for item in provider_summaries
        ]
    )
    summary_path = output / "dd2_provider_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    evidence_df = pd.DataFrame(evidence_rows)
    evidence_path = output / "dd2_evidence_hashes.csv"
    evidence_df.to_csv(evidence_path, index=False)

    if mismatch_frames:
        mismatch_df = pd.concat(mismatch_frames, ignore_index=True)
    else:
        mismatch_df = pd.DataFrame(
            columns=[
                "provider", "provider_id", "region_id", "region_rho", "rho",
                "horizon", "column", "published", "recomputed", "abs_delta",
            ]
        )
    mismatch_path = output / "dd2_mismatches.csv"
    mismatch_df.to_csv(mismatch_path, index=False)

    overall_pass = bool(summary_df["pass"].all())
    result = {
        "status": (
            "DD2_I1_SIGMA_MATERIALIZATION_PASS"
            if overall_pass
            else "DD2_I1_SIGMA_MATERIALIZATION_FAIL"
        ),
        "scientific_role": "read-only independent vectorized rematerialization audit; zero simulation",
        "T_i_sigma_seed_start": int(expected_seeds[0]),
        "T_i_sigma_seed_end_inclusive": int(expected_seeds[-1]),
        "T_i_sigma_n_trajectories": len(expected_seeds),
        "public_i1_manifest_sha256_expected": expected_public_manifest_hash,
        "public_i1_manifest_sha256_actual": actual_public_manifest_hash,
        "providers": provider_summaries,
        "overall_pass": overall_pass,
        "comparison_tolerance": TOL,
        "new_simulation_run": False,
        "regions_refit": False,
        "regions_source": "already-frozen public rho_conditioned_regions",
        "sigma_recomputed_from": "frozen private T_i^sigma only; independent vectorized implementation",
    }
    result_path = output / "dd2_i1_sigma_materialization_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(result["status"])
    print(
        f"T_i_sigma_seeds={expected_seeds[0]}..{expected_seeds[-1]} "
        f"n={len(expected_seeds)}"
    )
    print(
        f"public_manifest_hash_match="
        f"{actual_public_manifest_hash == expected_public_manifest_hash}"
    )
    print("\nPROVIDER_SUMMARY")
    print(summary_df.to_string(index=False))
    print(f"\nnew_simulation_run=false")
    print(f"regions_refit=false")
    print(f"mismatch_rows={len(mismatch_df)}")
    print(f"result={result_path}")
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")

    if not overall_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
