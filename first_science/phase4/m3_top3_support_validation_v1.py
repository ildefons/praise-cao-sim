#!/usr/bin/env python3
"""Validate frozen M3 Top1 / Top3 support sizes on the full pilot battery.

This is a retrospective support-size diagnostic. It does not change provider
candidates, public-I1 weights, lambda, SLA queries, or white-box data.

At total graph budget B=1400 it compares:
  - TOP1_1400: highest-weight joint reconstruction, 1400 graph trajectories;
  - TOP3_1400: ranks 1--3, renormalized frozen weights, integer-minimax
    allocation under the same M3 variance objective;
  - the frozen production M3 B=1400 and B=2000 predictions.

No new graph simulation is required when the existing frozen ledgers are
present. TOP1 reuses the Stage-B rank-1 ledger. TOP3 reuses prefixes of the
existing production M3 B=2000 ledgers; these prefixes already contain enough
trajectories for the cost-matched B=1400 Top3 allocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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
for directory in (PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import load_rho_conditioned_i1_cards  # noqa: E402
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m3_v4_dominant_mass_graph import _integer_minimax_allocations  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)

EXPECTED_STATUS = "FROZEN_PHASE4_M3_TOP3_SUPPORT_VALIDATION_V1"
COMPLETE_STATUS = "PHASE4_M3_TOP3_SUPPORT_VALIDATION_COMPLETE_V1"
Z975 = 1.959963984540054
TOL = 1e-10


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


def _wilson_interval(p: float, n: int) -> tuple[float, float]:
    x = int(round(float(p) * int(n)))
    phat = float(x / n)
    z2 = Z975 * Z975
    den = 1.0 + z2 / n
    centre = (phat + z2 / (2.0 * n)) / den
    half = Z975 * math.sqrt(
        phat * (1.0 - phat) / n + z2 / (4.0 * n * n)
    ) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _query_boundary(rec: pd.Series) -> AdmissibilityBoundary:
    return AdmissibilityBoundary(
        l_max=float(rec["A_G_l_max"]),
        c_max=float(rec["A_G_c_max"]),
        q_min=float(rec["A_G_q_min"]),
    )


def _load_curve_from_ledger(
    *,
    ledger_path: Path,
    n_trajectories: int,
    queries: pd.DataFrame,
    horizons: list[float],
    workload: dict[str, Any],
    output_column: str,
) -> pd.DataFrame:
    if not ledger_path.exists():
        raise FileNotFoundError(f"missing required ledger: {ledger_path}")
    ledger = pd.read_csv(ledger_path)
    if "trajectory" not in ledger.columns:
        raise RuntimeError(f"ledger lacks trajectory column: {ledger_path}")
    available = int(ledger["trajectory"].astype(int).nunique())
    if available < int(n_trajectories):
        raise RuntimeError(
            f"{ledger_path.name}: need {n_trajectories} trajectories, only {available} available"
        )
    subset = ledger[ledger["trajectory"].astype(int) < int(n_trajectories)].copy()
    if subset["trajectory"].astype(int).nunique() != int(n_trajectories):
        raise RuntimeError(f"{ledger_path.name}: trajectory prefix is incomplete")

    rows = []
    for _, query in queries.iterrows():
        curve = build_empirical_graph_sigma_curve(
            subset,
            boundary=_query_boundary(query),
            rho_global=float(query["rho_global"]),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column=output_column,
        )
        curve.insert(0, "rho_global", float(query["rho_global"]))
        curve.insert(1, "regime", str(query["regime"]))
        rows.append(curve)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "regime", "horizon"]
    ).reset_index(drop=True)


def _metrics(frame: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    rows = []
    scopes = [("ALL", frame)] + [
        (regime, frame[frame["regime"].astype(str) == regime])
        for regime in sorted(frame["regime"].astype(str).unique())
    ]
    for scope, sub in scopes:
        wb = sub["sigma_whitebox"].astype(float).to_numpy()
        for method, col in columns.items():
            y = sub[col].astype(float).to_numpy()
            e = y - wb
            rows.append(
                {
                    "scope": scope,
                    "method": method,
                    "n_points": int(len(sub)),
                    "mae": float(np.mean(np.abs(e))),
                    "rmse": float(np.sqrt(np.mean(np.square(e)))),
                    "bias": float(np.mean(e)),
                    "max_abs_error": float(np.max(np.abs(e))),
                }
            )
    return pd.DataFrame(rows)


def _decisions(
    frame: pd.DataFrame,
    columns: dict[str, str],
    *,
    beta: float,
    n_whitebox: int,
) -> pd.DataFrame:
    wb = frame["sigma_whitebox"].astype(float).to_numpy()
    intervals = [_wilson_interval(float(p), int(n_whitebox)) for p in wb]
    certain = np.asarray([(lo >= beta) or (hi < beta) for lo, hi in intervals])
    ref = wb >= beta
    rows = []
    for method, col in columns.items():
        pred = frame[col].astype(float).to_numpy() >= beta
        for subset, mask in (
            ("all_reference_points", np.ones(len(frame), dtype=bool)),
            ("whitebox_95pct_interval_does_not_cross_beta", certain),
        ):
            rows.append(
                {
                    "beta": float(beta),
                    "method": method,
                    "subset": subset,
                    "n_evaluated": int(mask.sum()),
                    "decision_agreement_rate": float(np.mean(pred[mask] == ref[mask])),
                    "decision_disagreement_rate": float(np.mean(pred[mask] != ref[mask])),
                    "false_accept_count": int(np.sum(pred[mask] & ~ref[mask])),
                    "false_reject_count": int(np.sum(~pred[mask] & ref[mask])),
                }
            )
    return pd.DataFrame(rows)


def _mc_width_summary(
    frame: pd.DataFrame,
    *,
    top1_n: int,
    top3_var_bound: float,
) -> pd.DataFrame:
    rows = []

    widths = []
    for p in frame["sigma_top1_1400"].astype(float):
        lo, hi = _wilson_interval(float(p), int(top1_n))
        widths.append(hi - lo)
    rows.append(
        {
            "method": "TOP1_1400",
            "mc_method": "Wilson 95% interval",
            "mean_pointwise_95pct_mc_width": float(np.mean(widths)),
            "max_pointwise_95pct_mc_width": float(np.max(widths)),
        }
    )

    half = Z975 * math.sqrt(float(top3_var_bound))
    widths = []
    for p in frame["sigma_top3_1400"].astype(float):
        lo = max(0.0, float(p) - half)
        hi = min(1.0, float(p) + half)
        widths.append(hi - lo)
    rows.append(
        {
            "method": "TOP3_1400",
            "mc_method": "normal 95% band from worst-case weighted variance bound",
            "mean_pointwise_95pct_mc_width": float(np.mean(widths)),
            "max_pointwise_95pct_mc_width": float(np.max(widths)),
        }
    )
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected Top3 support-validation contract status")

    inp = {k: (HERE / str(v)).resolve() for k, v in dict(contract["inputs"]).items()}
    for key, path in inp.items():
        if key.endswith("_root"):
            continue
        if not path.exists():
            raise FileNotFoundError(f"missing required input {key}: {path}")

    comparison = pd.read_csv(inp["final_comparison"])
    stage_b_design = pd.read_csv(inp["stage_b_design"]).sort_values("rank").reset_index(drop=True)
    if len(stage_b_design) != 14 or stage_b_design["rank"].astype(int).tolist() != list(range(1, 15)):
        raise RuntimeError("expected frozen retained M3 ranks 1..14")

    budget = int(contract["support_validation"]["graph_budget"])
    if budget != 1400:
        raise RuntimeError("v1 contract is frozen to graph budget B=1400")
    top3 = stage_b_design.head(3).copy()
    top3_mass = float(top3["joint_weight"].astype(float).sum())
    top14_mass = float(stage_b_design["joint_weight"].astype(float).sum())
    top1_mass = float(stage_b_design.iloc[0]["joint_weight"])
    alpha3 = top3["joint_weight"].astype(float).to_numpy() / top3_mass
    alloc = _integer_minimax_allocations(alpha3, [budget])
    allocation = alloc.set_index("rank")["n_trajectories"].astype(int).to_dict()
    top3_var_bound = float(alloc["worst_case_mc_variance_bound_budget"].iloc[0])

    query_cols = [
        "rho_global", "regime", "A_G_l_max", "A_G_c_max", "A_G_q_min"
    ]
    queries = comparison[query_cols].drop_duplicates().sort_values(
        ["rho_global", "regime"]
    ).reset_index(drop=True)
    if len(queries) != 15:
        raise RuntimeError(f"expected 15 frozen queries, found {len(queries)}")
    horizons = sorted(comparison["horizon"].astype(float).unique().tolist())

    metadata, _, _ = load_rho_conditioned_i1_cards(
        inp["i1_card_root"], inp["i1_manifest"]
    )
    workload = _common_workload_contract(metadata)

    # TOP1 B=1400 from the already frozen Stage-B rank-1 ledger.
    top1_curve = _load_curve_from_ledger(
        ledger_path=inp["stage_b_rank1_ledger"],
        n_trajectories=budget,
        queries=queries,
        horizons=horizons,
        workload=workload,
        output_column="sigma_top1_1400",
    )

    # TOP3 B=1400 from prefixes of the existing production M3 ledgers.
    member_frames = []
    for rank in (1, 2, 3):
        ledger_path = inp["production_ledger_root"] / f"M3Q_R{rank:02d}.csv"
        member = _load_curve_from_ledger(
            ledger_path=ledger_path,
            n_trajectories=int(allocation[rank]),
            queries=queries,
            horizons=horizons,
            workload=workload,
            output_column="sigma_member",
        )
        member.insert(0, "rank", rank)
        member["alpha_top3"] = float(alpha3[rank - 1])
        member["n_trajectories"] = int(allocation[rank])
        member_frames.append(member)
    members = pd.concat(member_frames, ignore_index=True)

    rows = []
    for key, g in members.groupby(["rho_global", "regime", "horizon"], sort=True):
        g = g.sort_values("rank")
        if g["rank"].astype(int).tolist() != [1, 2, 3]:
            raise RuntimeError(f"incomplete Top3 member set for {key}")
        rows.append(
            {
                "rho_global": float(key[0]),
                "regime": str(key[1]),
                "horizon": float(key[2]),
                "sigma_top3_1400": float(
                    np.sum(g["alpha_top3"].astype(float) * g["sigma_member"].astype(float))
                ),
            }
        )
    top3_curve = pd.DataFrame(rows)

    out = comparison[
        [
            "rho_global", "regime", "horizon", "sigma_whitebox",
            "sigma_m1", "sigma_m2_mean", "sigma_m3_B1400", "sigma_m3_B2000",
        ]
    ].copy()
    out = out.merge(
        top1_curve[["rho_global", "regime", "horizon", "sigma_top1_1400"]],
        on=["rho_global", "regime", "horizon"], how="left", validate="one_to_one",
    )
    out = out.merge(
        top3_curve,
        on=["rho_global", "regime", "horizon"], how="left", validate="one_to_one",
    )
    if out.isna().any().any():
        raise RuntimeError("support-validation merge produced missing values")

    eval_cfg = dict(contract["evaluation"])
    eval_frame = out[
        (out["horizon"].astype(float) >= float(eval_cfg["horizon_min"]) - TOL)
        & (out["horizon"].astype(float) <= float(eval_cfg["horizon_max"]) + TOL)
    ].copy().reset_index(drop=True)

    method_cols = {
        "TOP1_1400": "sigma_top1_1400",
        "TOP3_1400": "sigma_top3_1400",
        "M3_TOP14_1400": "sigma_m3_B1400",
        "M3_TOP14_2000": "sigma_m3_B2000",
    }
    metrics = _metrics(eval_frame, method_cols)
    decisions = _decisions(
        eval_frame,
        method_cols,
        beta=float(eval_cfg["beta"]),
        n_whitebox=int(eval_cfg["whitebox_n"]),
    )
    mc = _mc_width_summary(
        eval_frame,
        top1_n=budget,
        top3_var_bound=top3_var_bound,
    )

    support = pd.DataFrame(
        [
            {
                "support": "Top1",
                "n_joint_models": 1,
                "retained_full_gibbs_mass": top1_mass,
                "omitted_full_gibbs_mass": 1.0 - top1_mass,
                "deterministic_truncation_abs_error_bound": 1.0 - top1_mass,
            },
            {
                "support": "Top3",
                "n_joint_models": 3,
                "retained_full_gibbs_mass": top3_mass,
                "omitted_full_gibbs_mass": 1.0 - top3_mass,
                "deterministic_truncation_abs_error_bound": 1.0 - top3_mass,
            },
            {
                "support": "Top14",
                "n_joint_models": 14,
                "retained_full_gibbs_mass": top14_mass,
                "omitted_full_gibbs_mass": 1.0 - top14_mass,
                "deterministic_truncation_abs_error_bound": 1.0 - top14_mass,
            },
        ]
    )

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pred_path = output / "m3_top3_support_predictions.csv"
    member_path = output / "m3_top3_member_curves.csv"
    alloc_path = output / "m3_top3_allocation.csv"
    metrics_path = output / "m3_top3_error_metrics.csv"
    decisions_path = output / "m3_top3_decision_metrics.csv"
    mc_path = output / "m3_top3_mc_width_summary.csv"
    support_path = output / "m3_top3_support_mass_summary.csv"
    manifest_path = output / "m3_top3_support_manifest.json"

    out.to_csv(pred_path, index=False)
    members.to_csv(member_path, index=False)
    alloc.to_csv(alloc_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    decisions.to_csv(decisions_path, index=False)
    mc.to_csv(mc_path, index=False)
    support.to_csv(support_path, index=False)

    _write_json(
        manifest_path,
        {
            "status": COMPLETE_STATUS,
            "classification": "retrospective_support_size_validation",
            "graph_budget": budget,
            "new_graph_simulation": False,
            "provider_candidates_changed": False,
            "weights_changed": False,
            "lambda_changed": False,
            "queries_changed": False,
            "whitebox_changed": False,
            "top3_full_gibbs_mass": top3_mass,
            "top3_renormalized_weights": [float(x) for x in alpha3],
            "top3_allocation": {str(k): int(v) for k, v in allocation.items()},
            "top3_worst_case_mc_variance_bound": top3_var_bound,
            "contract_sha256": _sha256(contract_path),
            "predictions_sha256": _sha256(pred_path),
            "member_curves_sha256": _sha256(member_path),
            "allocation_sha256": _sha256(alloc_path),
            "error_metrics_sha256": _sha256(metrics_path),
            "decision_metrics_sha256": _sha256(decisions_path),
            "mc_width_summary_sha256": _sha256(mc_path),
            "support_mass_summary_sha256": _sha256(support_path),
            "git_commit": _git_head(FIRST_SCIENCE.parent),
            "python_wall_seconds": float(time.perf_counter() - started),
        },
    )

    print("M3_TOP3_SUPPORT_VALIDATION_COMPLETE")
    print(f"No new graph simulation was run. --workers={args.workers} is accepted but unused.")
    print(f"Top3 renormalized weights: {alpha3.tolist()}")
    print(f"Top3 B={budget} allocation: {allocation}")
    print("\nERROR METRICS (H=60..240)")
    print(metrics.to_string(index=False))
    print("\nDECISION AGREEMENT")
    print(
        decisions[
            decisions["subset"].astype(str)
            == "whitebox_95pct_interval_does_not_cross_beta"
        ].to_string(index=False)
    )
    print("\nMC WIDTH")
    print(mc.to_string(index=False))
    print("\nSUPPORT MASS")
    print(support.to_string(index=False))
    print(f"output={output}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Validate M3 Top1 and cost-matched Top3 support on the frozen pilot"
    )
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_top3_support_validation_v1.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_top3_support_validation_v1",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Accepted for CLI compatibility; v1 reuses frozen ledgers and runs no simulation.",
    )
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
