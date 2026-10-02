#!/usr/bin/env python3
"""Read-only clustered-bootstrap audit of signed bias in the closed pilot.

No method is re-fit or changed. The already-frozen method predictions remain
fixed and only the N=200 fresh white-box trajectory clusters are resampled.
The same trajectory multiplicities are used across all 15 queries and all
horizons, preserving the dependence induced by the shared WB ledger.

This audit isolates uncertainty from the finite WB reference only. It does not
include method Monte Carlo uncertainty, model ambiguity, reconstruction
uncertainty, or uncertainty from method construction.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"

from m3_v4_wb_reference_bootstrap import (  # noqa: E402
    TOL,
    _query_rows,
    _scope_masks,
    _sha256,
    _trajectory_pass_matrix,
    _write_json,
)
from diagnose_rho_conditioned_i1_m0 import load_rho_conditioned_i1_cards  # noqa: E402
from run_m1_graph_prediction_v2 import _common_workload_contract  # noqa: E402


def _vector(frame: pd.DataFrame, keys: list[tuple[float, str, float]], column: str) -> np.ndarray:
    lookup = frame.set_index(["rho_global", "regime", "horizon"])[column]
    values = []
    for key in keys:
        try:
            value = lookup.loc[key]
        except KeyError as exc:
            raise RuntimeError(f"missing frozen prediction {column} at {key}") from exc
        values.append(float(value) if pd.notna(value) else np.nan)
    return np.asarray(values, dtype=float)


def _interval(x: np.ndarray) -> dict[str, float]:
    return {
        "bootstrap_mean": float(np.mean(x)),
        "bootstrap_median": float(np.median(x)),
        "q025": float(np.quantile(x, 0.025)),
        "q975": float(np.quantile(x, 0.975)),
        "prob_bias_gt_zero": float(np.mean(x > 0.0)),
        "prob_bias_ge_zero": float(np.mean(x >= 0.0)),
    }


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()

    comparison = pd.read_csv(args.comparison.resolve())
    support = pd.read_csv(args.support_predictions.resolve())
    ledger = pd.read_csv(args.whitebox_ledger.resolve())

    queries = _query_rows(comparison)
    horizons = sorted(comparison["horizon"].astype(float).unique().tolist())

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(),
        args.i1_manifest.resolve(),
    )
    workload = _common_workload_contract(metadata)

    wb_matrix, keys, seeds = _trajectory_pass_matrix(
        ledger=ledger,
        queries=queries,
        horizons=horizons,
        workload=workload,
    )
    n = int(wb_matrix.shape[0])
    if n != 200:
        raise RuntimeError(f"expected frozen fresh WB N=200, found {n}")
    if seeds != list(range(38000, 38200)):
        raise RuntimeError("fresh WB seed bank is not frozen 38000..38199")

    frozen_wb = _vector(comparison, keys, "sigma_whitebox")
    if not np.allclose(wb_matrix.mean(axis=0), frozen_wb, atol=TOL, rtol=0.0):
        raise RuntimeError("reconstructed WB curves differ from frozen comparison")

    support_wb = _vector(support, keys, "sigma_whitebox")
    if not np.allclose(support_wb, frozen_wb, atol=TOL, rtol=0.0):
        raise RuntimeError("support-validation WB values differ from frozen comparison")

    pred = {
        "M1": _vector(comparison, keys, "sigma_m1"),
        "M2": _vector(comparison, keys, "sigma_m2_mean"),
        "M3_TOP1_B1400": _vector(support, keys, "sigma_top1_1400"),
        "M3_TOP3_B1400": _vector(support, keys, "sigma_top3_1400"),
        "M3_TOP14_B1400": _vector(comparison, keys, "sigma_m3_B1400"),
        "M3_TOP14_B2000": _vector(comparison, keys, "sigma_m3_B2000"),
    }

    masks = _scope_masks(keys, h_min=float(args.h_min), h_max=float(args.h_max))

    rng = np.random.default_rng(int(args.bootstrap_seed))
    counts = rng.multinomial(
        n,
        np.full(n, 1.0 / n, dtype=float),
        size=int(args.bootstrap_reps),
    )
    wb_boot = (counts @ wb_matrix) / float(n)

    rows = []
    replicate_rows = []
    for scope, mask in masks.items():
        for method, vector in pred.items():
            valid = mask & np.isfinite(vector)
            if not bool(np.any(valid)):
                continue
            point_bias = float(np.mean(vector[valid] - frozen_wb[valid]))
            bias_boot = np.mean(
                vector[valid][None, :] - wb_boot[:, valid],
                axis=1,
            )
            rows.append({
                "scope": scope,
                "method": method,
                "n_points": int(np.sum(valid)),
                "point_bias": point_bias,
                **_interval(bias_boot),
                "bootstrap_reps": int(args.bootstrap_reps),
                "n_wb_trajectories": n,
            })
            for b, value in enumerate(bias_boot):
                replicate_rows.append({
                    "bootstrap_id": int(b),
                    "scope": scope,
                    "method": method,
                    "bias": float(value),
                })

    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "signed_bias_wb_cluster_bootstrap_summary.csv"
    reps_path = out / "signed_bias_wb_cluster_bootstrap_replicates.csv"
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    pd.DataFrame(replicate_rows).to_csv(reps_path, index=False)

    manifest = {
        "status": "POSTHOC_PILOT_SIGNED_BIAS_WB_CLUSTER_BOOTSTRAP_COMPLETE_V1",
        "scientific_role": "read-only finite-WB reference audit of signed bias",
        "new_graph_simulation": False,
        "new_whitebox_simulation": False,
        "method_predictions_fixed": True,
        "resampling_unit": "fresh white-box trajectory cluster",
        "shared_resample_across_all_queries_and_horizons": True,
        "bootstrap_reps": int(args.bootstrap_reps),
        "bootstrap_seed": int(args.bootstrap_seed),
        "horizon_window": [float(args.h_min), float(args.h_max)],
        "comparison_sha256": _sha256(args.comparison.resolve()),
        "support_predictions_sha256": _sha256(args.support_predictions.resolve()),
        "fresh_whitebox_ledger_sha256": _sha256(args.whitebox_ledger.resolve()),
        "summary_sha256": _sha256(summary_path),
        "replicates_sha256": _sha256(reps_path),
        "python_wall_seconds": float(time.perf_counter() - started),
        "caution": (
            "Intervals isolate finite-WB reference uncertainty only; "
            "they are not joint confidence intervals over method uncertainty."
        ),
    }
    manifest_path = out / "signed_bias_wb_cluster_bootstrap_manifest.json"
    _write_json(manifest_path, manifest)

    print("\nSIGNED_BIAS_WB_CLUSTER_BOOTSTRAP")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nsummary={summary_path}")
    print(f"replicates={reps_path}")
    print(f"manifest={manifest_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Cluster-bootstrap frozen pilot signed bias")
    p.add_argument(
        "--comparison",
        type=Path,
        default=HERE / "results" / "m3_v4_final_evaluation_v1"
        / "m3_v4_final_comparison.csv",
    )
    p.add_argument(
        "--support-predictions",
        type=Path,
        default=HERE / "results" / "m3_top3_support_validation_v1"
        / "m3_top3_support_predictions.csv",
    )
    p.add_argument(
        "--whitebox-ledger",
        type=Path,
        default=HERE / "results" / "m3_v4_final_evaluation_v1"
        / "m3_v4_fresh_whitebox_ledger.csv",
    )
    p.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    p.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "pilot_signed_bias_wb_cluster_bootstrap_v1",
    )
    p.add_argument("--bootstrap-reps", type=int, default=10000)
    p.add_argument("--bootstrap-seed", type=int, default=2026100201)
    p.add_argument("--h-min", type=float, default=60.0)
    p.add_argument("--h-max", type=float, default=240.0)
    args = p.parse_args()
    if int(args.bootstrap_reps) < 2000:
        raise ValueError("--bootstrap-reps should be at least 2000")
    run(args)


if __name__ == "__main__":
    main()
