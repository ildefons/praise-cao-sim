#!/usr/bin/env python3
"""Post-hoc robustness audit: finite-white-box reference noise.

This analysis does NOT change or re-fit M0/M1/M2/M3. It conditions on the
already-frozen method predictions and resamples only the N=200 fresh white-box
trajectory clusters from the closed M3-v4 evaluation.

The same bootstrap trajectory multiplicities are used simultaneously for all
15 (rho, regime) queries and all horizons. This preserves the dependence
induced by evaluating every query on the same white-box ledger.

Primary quantity:
    Delta_MAE = MAE(M2, WB*) - MAE(M3, WB*)
where WB* is one clustered bootstrap resample of the fresh white-box bank.
Positive Delta_MAE means lower MAE for M3 in that resample.

The audit isolates uncertainty due to the finite WB reference. It does not
include M2/M3 graph-Monte-Carlo uncertainty, latent-model uncertainty, or
uncertainty from method construction.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE1, PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import load_rho_conditioned_i1_cards
from run_m1_graph_prediction_v2 import _common_workload_contract
from sla_compliance_analysis import (
    SlaComplianceDefinition,
    calculate_empirical_sla_sigma_from_ledgers,
)
from m2_b2_remote_graph import _sha256, _write_json

TOL = 1e-10


def _query_rows(comparison: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "rho_global", "regime", "scale",
        "A_G_l_max", "A_G_c_max", "A_G_q_min",
    ]
    missing = sorted(set(cols).difference(comparison.columns))
    if missing:
        raise RuntimeError("comparison lacks query fields: " + ", ".join(missing))
    q = (
        comparison[cols]
        .drop_duplicates()
        .sort_values(["rho_global", "regime"])
        .reset_index(drop=True)
    )
    if len(q) != 15:
        raise RuntimeError(f"expected 15 frozen queries, found {len(q)}")
    return q


def _trajectory_pass_matrix(
    *,
    ledger: pd.DataFrame,
    queries: pd.DataFrame,
    horizons: list[float],
    workload: dict[str, float],
) -> tuple[np.ndarray, list[tuple[float, str, float]], list[int]]:
    required = {"trajectory", "trajectory_seed"}
    missing = sorted(required.difference(ledger.columns))
    if missing:
        raise RuntimeError("fresh WB ledger missing: " + ", ".join(missing))

    trajectory_ids = sorted(ledger["trajectory"].astype(int).unique().tolist())
    if trajectory_ids != list(range(len(trajectory_ids))):
        raise RuntimeError("fresh WB trajectory IDs must be 0..N-1")

    seed_map = (
        ledger[["trajectory", "trajectory_seed"]]
        .drop_duplicates()
        .sort_values("trajectory")
    )
    if len(seed_map) != len(trajectory_ids):
        raise RuntimeError("fresh WB trajectory/seed mapping is not one-to-one")
    seeds = seed_map["trajectory_seed"].astype(int).tolist()

    pieces: list[np.ndarray] = []
    keys: list[tuple[float, str, float]] = []
    for query in queries.itertuples(index=False):
        rho = float(query.rho_global)
        regime = str(query.regime)
        definition = SlaComplianceDefinition(
            rho=rho,
            accounting_origin=float(workload["accounting_origin"]),
            zero_decision_compliance=1.0,
        )
        sigma, curves, _ = calculate_empirical_sla_sigma_from_ledgers(
            ledger,
            latency_threshold=float(query.A_G_l_max),
            cost_threshold=float(query.A_G_c_max),
            quality_threshold=float(query.A_G_q_min),
            horizons=[float(h) for h in horizons],
            stop_time=float(workload["horizon_max"]),
            sla_definition=definition,
        )
        pivot = (
            curves
            .pivot(index="trajectory", columns="horizon", values="sla_compliant")
            .reindex(index=trajectory_ids, columns=horizons)
        )
        if pivot.isna().any().any():
            raise RuntimeError(f"incomplete WB pass matrix for {rho}, {regime}")
        x = pivot.astype(float).to_numpy()
        sigma_vec = (
            sigma.set_index("horizon")
            .reindex(horizons)["sigma"]
            .astype(float)
            .to_numpy()
        )
        if not np.allclose(x.mean(axis=0), sigma_vec, atol=TOL, rtol=0.0):
            raise RuntimeError(f"WB trajectory mean mismatch for {rho}, {regime}")
        pieces.append(x)
        keys.extend((rho, regime, float(h)) for h in horizons)

    # Concatenate query/horizon columns. One row = one shared WB trajectory.
    matrix = np.concatenate(pieces, axis=1)
    return matrix, keys, seeds


def _method_vector(
    comparison: pd.DataFrame,
    keys: list[tuple[float, str, float]],
    column: str,
) -> np.ndarray:
    lookup = comparison.set_index(["rho_global", "regime", "horizon"])[column]
    values = []
    for key in keys:
        try:
            value = lookup.loc[key]
        except KeyError as exc:
            raise RuntimeError(f"missing frozen prediction {column} at {key}") from exc
        values.append(float(value) if pd.notna(value) else np.nan)
    return np.asarray(values, dtype=float)


def _scope_masks(
    keys: list[tuple[float, str, float]],
    *,
    h_min: float,
    h_max: float,
) -> dict[str, np.ndarray]:
    rho = np.asarray([k[0] for k in keys], dtype=float)
    regime = np.asarray([k[1] for k in keys], dtype=object)
    horizon = np.asarray([k[2] for k in keys], dtype=float)
    base = (horizon >= h_min - TOL) & (horizon <= h_max + TOL)
    masks = {"ALL": base}
    for name in ("G0", "G1", "G2"):
        masks[name] = base & (regime == name)
    return masks


def _summary_interval(x: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "q025": float(np.quantile(x, 0.025)),
        "q975": float(np.quantile(x, 0.975)),
        "prob_gt_zero": float(np.mean(x > 0.0)),
        "prob_ge_zero": float(np.mean(x >= 0.0)),
    }


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()

    comparison_path = args.comparison.resolve()
    ledger_path = args.whitebox_ledger.resolve()
    comparison = pd.read_csv(comparison_path)
    ledger = pd.read_csv(ledger_path)

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
    n = wb_matrix.shape[0]
    if n != 200:
        raise RuntimeError(f"expected frozen fresh WB N=200, found {n}")
    if seeds != list(range(38000, 38200)):
        raise RuntimeError("fresh WB seed bank is not frozen 38000..38199")

    # Verify reconstruction against the frozen comparison before bootstrapping.
    frozen_wb = _method_vector(comparison, keys, "sigma_whitebox")
    if not np.allclose(wb_matrix.mean(axis=0), frozen_wb, atol=TOL, rtol=0.0):
        delta = float(np.max(np.abs(wb_matrix.mean(axis=0) - frozen_wb)))
        raise RuntimeError(f"reconstructed WB differs from frozen curves: {delta}")

    pred = {
        "M1": _method_vector(comparison, keys, "sigma_m1"),
        "M2": _method_vector(comparison, keys, "sigma_m2_mean"),
        "M3_B1400": _method_vector(comparison, keys, "sigma_m3_B1400"),
        "M3_B2000": _method_vector(comparison, keys, "sigma_m3_B2000"),
    }
    masks = _scope_masks(keys, h_min=float(args.h_min), h_max=float(args.h_max))

    rng = np.random.default_rng(int(args.bootstrap_seed))
    counts = rng.multinomial(
        n,
        np.full(n, 1.0 / n, dtype=float),
        size=int(args.bootstrap_reps),
    )
    wb_boot = (counts @ wb_matrix) / float(n)

    replicate_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for scope, mask in masks.items():
        if not bool(np.any(mask)):
            raise RuntimeError(f"empty scope: {scope}")
        mae_boot: dict[str, np.ndarray] = {}
        point_mae: dict[str, float] = {}

        for method, vector in pred.items():
            valid = mask & np.isfinite(vector)
            if not bool(np.any(valid)):
                raise RuntimeError(f"{scope}: no valid points for {method}")
            mae_boot[method] = np.mean(
                np.abs(wb_boot[:, valid] - vector[valid][None, :]),
                axis=1,
            )
            point_mae[method] = float(
                np.mean(np.abs(frozen_wb[valid] - vector[valid]))
            )
            stats = _summary_interval(mae_boot[method])
            summary_rows.append({
                "scope": scope,
                "quantity": f"MAE_{method}",
                "point_estimate": point_mae[method],
                **stats,
                "bootstrap_reps": int(args.bootstrap_reps),
                "n_wb_trajectories": int(n),
            })

        for m3 in ("M3_B1400", "M3_B2000"):
            delta = mae_boot["M2"] - mae_boot[m3]
            point_delta = point_mae["M2"] - point_mae[m3]
            stats = _summary_interval(delta)
            summary_rows.append({
                "scope": scope,
                "quantity": f"DELTA_MAE_M2_MINUS_{m3}",
                "point_estimate": point_delta,
                **stats,
                "bootstrap_reps": int(args.bootstrap_reps),
                "n_wb_trajectories": int(n),
            })

        for b in range(int(args.bootstrap_reps)):
            replicate_rows.append({
                "bootstrap_id": b,
                "scope": scope,
                "mae_M1": float(mae_boot["M1"][b]),
                "mae_M2": float(mae_boot["M2"][b]),
                "mae_M3_B1400": float(mae_boot["M3_B1400"][b]),
                "mae_M3_B2000": float(mae_boot["M3_B2000"][b]),
                "delta_mae_M2_minus_M3_B1400": float(
                    mae_boot["M2"][b] - mae_boot["M3_B1400"][b]
                ),
                "delta_mae_M2_minus_M3_B2000": float(
                    mae_boot["M2"][b] - mae_boot["M3_B2000"][b]
                ),
            })

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rep_path = output / "wb_reference_bootstrap_replicates.csv"
    summary_path = output / "wb_reference_bootstrap_summary.csv"
    pd.DataFrame(replicate_rows).to_csv(rep_path, index=False)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(summary_path, index=False)

    # Two simple diagnostic figures, one per frozen M3 budget.
    all_rep = pd.DataFrame(replicate_rows)
    for m3 in ("M3_B1400", "M3_B2000"):
        col = f"delta_mae_M2_minus_{m3}"
        g = all_rep[all_rep["scope"] == "ALL"][col].astype(float)
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.hist(g.to_numpy(), bins=50)
        ax.axvline(0.0, linestyle="--", linewidth=1.2)
        ax.set_xlabel(f"MAE(M2) - MAE({m3})")
        ax.set_ylabel("Bootstrap replicates")
        ax.set_title("Fresh-WB clustered bootstrap of paired MAE difference")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(output / f"wb_bootstrap_delta_M2_minus_{m3}.png", dpi=220)
        plt.close(fig)

    manifest = {
        "status": "POSTHOC_M3_V4_WB_REFERENCE_BOOTSTRAP_COMPLETE_V1",
        "scientific_role": (
            "Robustness audit of finite fresh-WB reference noise; "
            "no method fitting, selection, repair, or simulation."
        ),
        "comparison_sha256": _sha256(comparison_path),
        "fresh_whitebox_ledger_sha256": _sha256(ledger_path),
        "bootstrap_reps": int(args.bootstrap_reps),
        "bootstrap_seed": int(args.bootstrap_seed),
        "resampling_unit": "fresh white-box trajectory cluster",
        "shared_resample_across_all_queries_and_horizons": True,
        "horizon_window": [float(args.h_min), float(args.h_max)],
        "M0_changed": False,
        "M1_changed": False,
        "M2_changed": False,
        "M3_changed": False,
        "new_graph_simulation": False,
        "new_whitebox_simulation": False,
        "output_replicates_sha256": _sha256(rep_path),
        "output_summary_sha256": _sha256(summary_path),
        "python_wall_seconds": float(time.perf_counter() - started),
    }
    manifest_path = output / "wb_reference_bootstrap_manifest.json"
    _write_json(manifest_path, manifest)

    print("\nWB_REFERENCE_BOOTSTRAP_SUMMARY")
    print(summary.to_string(index=False))
    print("\nPOSTHOC_M3_V4_WB_REFERENCE_BOOTSTRAP_COMPLETE")
    print(f"summary={summary_path}")
    print(f"replicates={rep_path}")
    print(f"manifest={manifest_path}")
    print(
        "INTERPRETATION: positive DELTA_MAE_M2_MINUS_M3 means M3 has lower "
        "MAE than M2 under that fresh-WB resample."
    )
    print(
        "CAUTION: this audit isolates finite-WB reference noise only; it is "
        "not a joint CI over all method uncertainties."
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Cluster-bootstrap the frozen fresh-WB bank for paired M2/M3 MAE"
    )
    p.add_argument(
        "--comparison",
        type=Path,
        default=HERE / "results" / "m3_v4_final_evaluation_v1"
        / "m3_v4_final_comparison.csv",
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
        default=HERE / "results" / "m3_v4_wb_reference_bootstrap_v1",
    )
    p.add_argument("--bootstrap-reps", type=int, default=10000)
    p.add_argument("--bootstrap-seed", type=int, default=2026092401)
    p.add_argument("--h-min", type=float, default=60.0)
    p.add_argument("--h-max", type=float, default=240.0)
    args = p.parse_args()
    if int(args.bootstrap_reps) < 2000:
        raise ValueError("--bootstrap-reps should be at least 2000")
    run(args)


if __name__ == "__main__":
    main()
