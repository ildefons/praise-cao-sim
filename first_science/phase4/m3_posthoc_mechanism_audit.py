#!/usr/bin/env python3
"""Post-hoc, zero-simulation mechanism audit for the closed PRAISE M3 pilot.

This runner is deliberately read-only with respect to all frozen scientific
artifacts. It performs no provider simulation, graph simulation, or white-box
generation. It asks whether the already-frozen experiment contains direct
evidence of practical model non-identifiability and SLA decision consequences.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent

EXPECTED_STATUS = "FROZEN_PHASE4_M3_POSTHOC_MECHANISM_AUDIT_V1"
COMPLETE_STATUS = "PHASE4_M3_POSTHOC_MECHANISM_AUDIT_COMPLETE_V1"
TOL = 1e-12
Z975 = 1.959963984540054


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


def _require_columns(frame: pd.DataFrame, cols: set[str], label: str) -> None:
    missing = sorted(cols.difference(frame.columns))
    if missing:
        raise RuntimeError(f"{label} missing columns: {', '.join(missing)}")


def _validate_firewall(contract: dict[str, Any]) -> None:
    fw = dict(contract["firewall"])
    for key, value in fw.items():
        if key == "PPG_firewall_preserved":
            if not bool(value):
                raise RuntimeError("PPG firewall must remain preserved")
        elif bool(value):
            raise RuntimeError(f"post-hoc contract unexpectedly allows {key}")


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


def _spearman(x: pd.Series, y: pd.Series) -> float:
    xx = pd.Series(x, dtype=float)
    yy = pd.Series(y, dtype=float)
    ok = np.isfinite(xx.to_numpy()) & np.isfinite(yy.to_numpy())
    if int(ok.sum()) < 3:
        return float("nan")
    rx = xx[ok].rank(method="average")
    ry = yy[ok].rank(method="average")
    return float(rx.corr(ry, method="pearson"))


def _truth_candidate_audit(
    weights: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    cfg = dict(contract["hidden_provider_process_retrospective_audit_only"])
    dist_cfg = dict(contract["nearest_candidate_distance"])
    tol = float(dist_cfg["exact_match_tolerance"])
    rows: list[dict[str, Any]] = []

    for provider in ("ProviderA", "ProviderB", "ProviderC"):
        g = weights[weights["provider"].astype(str) == provider].copy()
        if len(g) != 48:
            raise RuntimeError(f"{provider}: expected 48 M3 candidates, found {len(g)}")
        truth = dict(cfg[provider])

        mu = g["mean_service_time"].astype(float).to_numpy()
        kappa = g["cost_rate"].astype(float).to_numpy()
        cv = g["service_cv"].astype(float).to_numpy()
        coords = np.column_stack([np.log(mu), np.log(kappa), cv])
        truth_coords = np.asarray(
            [
                math.log(float(truth["mean_service_time"])),
                math.log(float(truth["cost_rate"])),
                float(truth["service_cv"]),
            ],
            dtype=float,
        )
        ranges = np.ptp(coords, axis=0)
        safe_ranges = np.where(ranges > TOL, ranges, 1.0)
        d = np.sqrt(np.sum(np.square((coords - truth_coords) / safe_ranges), axis=1))
        g["normalized_truth_distance"] = d
        g["energy_rank"] = g["mean_bernoulli_kl"].astype(float).rank(
            method="min", ascending=True
        )
        g["weight_rank"] = g["weight_v3"].astype(float).rank(
            method="min", ascending=False
        )
        exact = (
            np.isclose(
                g["mean_service_time"].astype(float),
                float(truth["mean_service_time"]),
                atol=tol,
                rtol=0.0,
            )
            & np.isclose(
                g["cost_rate"].astype(float),
                float(truth["cost_rate"]),
                atol=tol,
                rtol=0.0,
            )
            & np.isclose(
                g["service_cv"].astype(float),
                float(truth["service_cv"]),
                atol=tol,
                rtol=0.0,
            )
        )
        best = g.sort_values(
            ["normalized_truth_distance", "mean_bernoulli_kl", "candidate_id"]
        ).iloc[0]
        rows.append(
            {
                "provider": provider,
                "hidden_process_id": str(cfg["provider_process_id"]),
                "exact_true_tuple_in_48_bank": bool(exact.any()),
                "n_exact_matches": int(exact.sum()),
                "nearest_candidate_id": str(best["candidate_id"]),
                "normalized_truth_distance": float(best["normalized_truth_distance"]),
                "true_mean_service_time": float(truth["mean_service_time"]),
                "candidate_mean_service_time": float(best["mean_service_time"]),
                "true_cost_rate": float(truth["cost_rate"]),
                "candidate_cost_rate": float(best["cost_rate"]),
                "true_service_cv": float(truth["service_cv"]),
                "candidate_service_cv": float(best["service_cv"]),
                "candidate_mean_bernoulli_kl": float(best["mean_bernoulli_kl"]),
                "candidate_weight_v3": float(best["weight_v3"]),
                "candidate_energy_rank_of_48": int(best["energy_rank"]),
                "candidate_weight_rank_of_48": int(best["weight_rank"]),
            }
        )
    return pd.DataFrame(rows)


def _top1_diagnostic(
    member: pd.DataFrame,
    comparison: pd.DataFrame,
    *,
    budget: int,
    rank: int,
    hmin: float,
    hmax: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["rho_global", "regime", "horizon"]
    top = member[
        (member["budget"].astype(int) == int(budget))
        & (member["rank"].astype(int) == int(rank))
        & (member["horizon"].astype(float) >= hmin - TOL)
        & (member["horizon"].astype(float) <= hmax + TOL)
    ][keys + ["sigma_member", "n_trajectories", "variant_id"]].copy()
    if top.empty:
        raise RuntimeError("frozen M3 rank-1 member curve is missing")
    top = top.rename(columns={"sigma_member": "sigma_m3_top1_existing"})
    ref = comparison[
        (comparison["horizon"].astype(float) >= hmin - TOL)
        & (comparison["horizon"].astype(float) <= hmax + TOL)
    ][keys + ["sigma_whitebox"]].copy()
    out = ref.merge(top, on=keys, how="left", validate="one_to_one")
    if out["sigma_m3_top1_existing"].isna().any():
        raise RuntimeError("top-1 diagnostic merge is incomplete")
    out["error_top1_existing"] = (
        out["sigma_m3_top1_existing"].astype(float)
        - out["sigma_whitebox"].astype(float)
    )
    out["abs_error_top1_existing"] = out["error_top1_existing"].abs()
    out["diagnostic_role"] = "NOT_COST_MATCHED_EXISTING_RANK1_MEMBER"

    rows = []
    scopes = [("ALL", out)]
    scopes.extend(
        (str(r), out[out["regime"].astype(str) == str(r)])
        for r in sorted(out["regime"].astype(str).unique())
    )
    for scope, g in scopes:
        e = g["error_top1_existing"].to_numpy(float)
        rows.append(
            {
                "scope": scope,
                "n_points": int(len(g)),
                "n_graph_trajectories_rank1": int(g["n_trajectories"].iloc[0]),
                "mae": float(np.mean(np.abs(e))),
                "rmse": float(np.sqrt(np.mean(np.square(e)))),
                "bias": float(np.mean(e)),
                "max_abs_error": float(np.max(np.abs(e))),
                "diagnostic_role": "NOT_COST_MATCHED_EXISTING_RANK1_MEMBER",
            }
        )
    return out, pd.DataFrame(rows)


def _decision_metrics(
    comparison: pd.DataFrame,
    top1: pd.DataFrame,
    contract: dict[str, Any],
) -> pd.DataFrame:
    cfg = dict(contract["analysis_window"])
    hmin = float(cfg["horizon_min"])
    hmax = float(cfg["horizon_max"])
    n_wb = int(cfg["whitebox_reference_n"])
    betas = [float(v) for v in cfg["decision_thresholds_beta"]]

    frame = comparison[
        (comparison["horizon"].astype(float) >= hmin - TOL)
        & (comparison["horizon"].astype(float) <= hmax + TOL)
    ].copy()
    frame = frame.merge(
        top1[["rho_global", "regime", "horizon", "sigma_m3_top1_existing"]],
        on=["rho_global", "regime", "horizon"],
        how="left",
        validate="one_to_one",
    )
    methods = {
        "M0": "sigma_m0",
        "M1": "sigma_m1",
        "M2": "sigma_m2_mean",
        "M3_B1400": "sigma_m3_B1400",
        "M3_B2000": "sigma_m3_B2000",
        "M3_TOP1_EXISTING": "sigma_m3_top1_existing",
    }

    rows = []
    for beta in betas:
        wb_intervals = frame["sigma_whitebox"].astype(float).apply(
            lambda p: _wilson_interval(float(p), n_wb)
        )
        wb_low = np.asarray([x[0] for x in wb_intervals], dtype=float)
        wb_high = np.asarray([x[1] for x in wb_intervals], dtype=float)
        ref_accept = frame["sigma_whitebox"].astype(float).to_numpy() >= beta
        ref_certain = (wb_low >= beta) | (wb_high < beta)

        for method, col in methods.items():
            pred = frame[col].astype(float).to_numpy()
            valid = np.isfinite(pred)
            if method == "M0":
                valid &= frame["m0_status"].astype(str).to_numpy() == "PREDICTED"

            for subset_name, subset_mask in (
                ("all_reference_points", np.ones(len(frame), dtype=bool)),
                ("wb_wilson95_certain_only", ref_certain),
            ):
                use = valid & subset_mask
                if int(use.sum()) == 0:
                    continue
                pa = pred[use] >= beta
                ra = ref_accept[use]
                false_accept = pa & ~ra
                false_reject = ~pa & ra
                n_pred_accept = int(pa.sum())
                n_pred_reject = int((~pa).sum())
                rows.append(
                    {
                        "beta": beta,
                        "method": method,
                        "subset": subset_name,
                        "n_evaluated": int(use.sum()),
                        "n_wb_uncertain_excluded": (
                            int((valid & ~ref_certain).sum())
                            if subset_name == "wb_wilson95_certain_only"
                            else 0
                        ),
                        "decision_agreement_rate": float(np.mean(pa == ra)),
                        "decision_disagreement_rate": float(np.mean(pa != ra)),
                        "false_accept_count": int(false_accept.sum()),
                        "false_accept_rate_all": float(np.mean(false_accept)),
                        "false_accept_rate_given_pred_accept": (
                            float(false_accept.sum() / n_pred_accept)
                            if n_pred_accept > 0
                            else float("nan")
                        ),
                        "false_reject_count": int(false_reject.sum()),
                        "false_reject_rate_all": float(np.mean(false_reject)),
                        "false_reject_rate_given_pred_reject": (
                            float(false_reject.sum() / n_pred_reject)
                            if n_pred_reject > 0
                            else float("nan")
                        ),
                        "reference_definition": "white-box point estimate",
                        "certainty_filter": (
                            "none"
                            if subset_name == "all_reference_points"
                            else "N=200 Wilson95 entirely one side of beta"
                        ),
                    }
                )
    return pd.DataFrame(rows)


def _ambiguity_tables(
    member: pd.DataFrame,
    comparison: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = dict(contract["analysis_window"])
    hmin = float(cfg["horizon_min"])
    hmax = float(cfg["horizon_max"])
    budget = int(cfg["m3_member_budget"])
    regime_map = dict(contract.get("regime_labels", {}))

    g = member[
        (member["budget"].astype(int) == budget)
        & (member["horizon"].astype(float) >= hmin - TOL)
        & (member["horizon"].astype(float) <= hmax + TOL)
    ].copy()
    if g.empty:
        raise RuntimeError("no M3 member curves in requested audit window")

    rows = []
    keys = ["rho_global", "regime", "horizon"]
    for key, q in g.groupby(keys, sort=True):
        if q["rank"].nunique() != 14:
            raise RuntimeError(f"{key}: expected 14 retained M3 hypotheses")
        q = q.sort_values("rank")
        w = q["alpha_renormalized"].astype(float).to_numpy()
        x = q["sigma_member"].astype(float).to_numpy()
        if not np.isclose(w.sum(), 1.0, atol=1e-10):
            raise RuntimeError(f"{key}: retained M3 weights do not sum to one")
        mean = float(np.sum(w * x))
        var = float(np.sum(w * np.square(x - mean)))
        rows.append(
            {
                "rho_global": float(key[0]),
                "regime": str(key[1]),
                "regime_label": regime_map.get(str(key[1]), str(key[1])),
                "horizon": float(key[2]),
                "sigma_weighted_member_mean": mean,
                "ambiguity_weighted_variance": var,
                "ambiguity_weighted_std": float(math.sqrt(max(0.0, var))),
                "ambiguity_member_min": float(np.min(x)),
                "ambiguity_member_max": float(np.max(x)),
                "ambiguity_member_range": float(np.max(x) - np.min(x)),
                "retained_weight_ess": float(1.0 / np.sum(np.square(w))),
                "n_retained_hypotheses": 14,
                "interpretation": "posthoc latent-member spread; not MC uncertainty",
            }
        )
    point = pd.DataFrame(rows)

    cmp_cols = keys + [
        "sigma_m1",
        "sigma_m2_mean",
        "sigma_m3_B2000",
        "sigma_whitebox",
    ]
    merged = point.merge(
        comparison[cmp_cols],
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if merged[["sigma_m1", "sigma_m2_mean", "sigma_m3_B2000", "sigma_whitebox"]].isna().any().any():
        raise RuntimeError("ambiguity/final-comparison merge is incomplete")
    if not np.allclose(
        merged["sigma_weighted_member_mean"].to_numpy(float),
        merged["sigma_m3_B2000"].to_numpy(float),
        atol=1e-10,
        rtol=0.0,
    ):
        raise RuntimeError("weighted member mean does not reproduce frozen M3 B2000")

    merged["abs_error_m1"] = np.abs(
        merged["sigma_m1"].astype(float) - merged["sigma_whitebox"].astype(float)
    )
    merged["abs_error_m2"] = np.abs(
        merged["sigma_m2_mean"].astype(float) - merged["sigma_whitebox"].astype(float)
    )
    merged["abs_error_m3_B2000"] = np.abs(
        merged["sigma_m3_B2000"].astype(float)
        - merged["sigma_whitebox"].astype(float)
    )

    summary = (
        merged.groupby(["rho_global", "regime", "regime_label"], as_index=False)
        .agg(
            ambiguity_variance_mean=("ambiguity_weighted_variance", "mean"),
            ambiguity_variance_max=("ambiguity_weighted_variance", "max"),
            ambiguity_std_mean=("ambiguity_weighted_std", "mean"),
            ambiguity_range_mean=("ambiguity_member_range", "mean"),
            ambiguity_range_max=("ambiguity_member_range", "max"),
            m1_mae=("abs_error_m1", "mean"),
            m2_mae=("abs_error_m2", "mean"),
            m3_B2000_mae=("abs_error_m3_B2000", "mean"),
        )
        .sort_values(["rho_global", "regime"])
        .reset_index(drop=True)
    )
    summary["m1_minus_m3_B2000_mae"] = (
        summary["m1_mae"] - summary["m3_B2000_mae"]
    )
    summary["m2_minus_m3_B2000_mae"] = (
        summary["m2_mae"] - summary["m3_B2000_mae"]
    )

    corr_rows = []
    targets = {
        "M1_MAE": "m1_mae",
        "M1_minus_M3_B2000_MAE": "m1_minus_m3_B2000_mae",
        "M2_minus_M3_B2000_MAE": "m2_minus_m3_B2000_mae",
    }
    for ambiguity_name in (
        "ambiguity_variance_mean",
        "ambiguity_std_mean",
        "ambiguity_range_mean",
    ):
        for target_name, target_col in targets.items():
            corr_rows.append(
                {
                    "ambiguity_measure": ambiguity_name,
                    "target": target_name,
                    "n_query_cells": int(len(summary)),
                    "spearman_rho": _spearman(
                        summary[ambiguity_name], summary[target_col]
                    ),
                    "interpretation": "posthoc descriptive correlation; no confirmatory p-value",
                }
            )
    return merged, summary, pd.DataFrame(corr_rows)


def _joint_energy_sigma(
    member: pd.DataFrame,
    design: pd.DataFrame,
    weights: pd.DataFrame,
    ambiguity_pointwise: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cfg = dict(contract["analysis_window"])
    hmin = float(cfg["horizon_min"])
    hmax = float(cfg["horizon_max"])
    budget = int(cfg["m3_member_budget"])

    lookup = {
        (str(r.provider), str(r.candidate_id)): float(r.mean_bernoulli_kl)
        for r in weights.itertuples(index=False)
    }
    design = design.copy().sort_values("rank")
    energy_rows = []
    for rec in design.itertuples(index=False):
        ea = lookup[("ProviderA", str(rec.ProviderA_candidate_id))]
        eb = lookup[("ProviderB", str(rec.ProviderB_candidate_id))]
        ec = lookup[("ProviderC", str(rec.ProviderC_candidate_id))]
        energy_rows.append(
            {
                "rank": int(rec.rank),
                "joint_public_i1_energy": float(ea + eb + ec),
                "ProviderA_candidate_id": str(rec.ProviderA_candidate_id),
                "ProviderB_candidate_id": str(rec.ProviderB_candidate_id),
                "ProviderC_candidate_id": str(rec.ProviderC_candidate_id),
                "alpha_renormalized_design": float(rec.alpha_renormalized),
                "joint_weight": float(rec.joint_weight),
            }
        )
    energy = pd.DataFrame(energy_rows)

    g = member[
        (member["budget"].astype(int) == budget)
        & (member["horizon"].astype(float) >= hmin - TOL)
        & (member["horizon"].astype(float) <= hmax + TOL)
    ].copy()
    points = g.merge(energy, on="rank", how="left", validate="many_to_one")
    if points["joint_public_i1_energy"].isna().any():
        raise RuntimeError("joint-energy merge failed")
    if not np.allclose(
        points["alpha_renormalized"].astype(float),
        points["alpha_renormalized_design"].astype(float),
        atol=1e-12,
        rtol=0.0,
    ):
        raise RuntimeError("design/member retained weights disagree")

    pair_rows: list[dict[str, Any]] = []
    for (rho, regime, horizon), q in points.groupby(
        ["rho_global", "regime", "horizon"], sort=True
    ):
        q = q.sort_values("rank").reset_index(drop=True)
        for i, j in itertools.combinations(range(len(q)), 2):
            a = q.iloc[i]
            b = q.iloc[j]
            pair_rows.append(
                {
                    "rho_global": float(rho),
                    "regime": str(regime),
                    "horizon": float(horizon),
                    "rank_a": int(a["rank"]),
                    "rank_b": int(b["rank"]),
                    "energy_a": float(a["joint_public_i1_energy"]),
                    "energy_b": float(b["joint_public_i1_energy"]),
                    "abs_energy_difference": float(
                        abs(a["joint_public_i1_energy"] - b["joint_public_i1_energy"])
                    ),
                    "sigma_a": float(a["sigma_member"]),
                    "sigma_b": float(b["sigma_member"]),
                    "abs_sigma_difference": float(
                        abs(a["sigma_member"] - b["sigma_member"])
                    ),
                    "alpha_a": float(a["alpha_renormalized"]),
                    "alpha_b": float(b["alpha_renormalized"]),
                }
            )
    pairs = pd.DataFrame(pair_rows).sort_values(
        ["abs_energy_difference", "abs_sigma_difference"],
        ascending=[True, False],
    ).reset_index(drop=True)

    maxrow = ambiguity_pointwise.sort_values(
        ["ambiguity_weighted_variance", "ambiguity_member_range"],
        ascending=[False, False],
    ).iloc[0]
    selected = {
        "rho_global": float(maxrow["rho_global"]),
        "regime": str(maxrow["regime"]),
        "horizon": float(maxrow["horizon"]),
        "ambiguity_weighted_variance": float(maxrow["ambiguity_weighted_variance"]),
        "ambiguity_member_range": float(maxrow["ambiguity_member_range"]),
        "selection_rule": "maximum retained-weight ambiguity variance within H60..240",
    }
    return points, pairs, selected


def _plot_ambiguity_vs_error(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    x = summary["ambiguity_std_mean"].astype(float)
    y = summary["m1_minus_m3_B2000_mae"].astype(float)
    ax.scatter(x, y)
    for rec in summary.itertuples(index=False):
        ax.annotate(
            f"{rec.regime_label}, rho={rec.rho_global:.4g}",
            (float(rec.ambiguity_std_mean), float(rec.m1_minus_m3_B2000_mae)),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax.set_xlabel("Mean retained-model ambiguity std over H=60..240")
    ax.set_ylabel("M1 MAE - M3(B=2000) MAE")
    ax.set_title("Post-hoc ambiguity versus gain from weighted integration")
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _plot_energy_sigma(
    points: pd.DataFrame,
    selected: dict[str, Any],
    path: Path,
) -> None:
    q = points[
        np.isclose(
            points["rho_global"].astype(float),
            float(selected["rho_global"]),
            atol=TOL,
            rtol=0.0,
        )
        & (points["regime"].astype(str) == str(selected["regime"]))
        & np.isclose(
            points["horizon"].astype(float),
            float(selected["horizon"]),
            atol=TOL,
            rtol=0.0,
        )
    ].sort_values("rank")
    if len(q) != 14:
        raise RuntimeError("selected energy-sigma point does not contain 14 hypotheses")

    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    sizes = 35.0 + 700.0 * q["alpha_renormalized"].astype(float).to_numpy()
    ax.scatter(
        q["joint_public_i1_energy"].astype(float),
        q["sigma_member"].astype(float),
        s=sizes,
        alpha=0.75,
    )
    for rec in q.itertuples(index=False):
        ax.annotate(
            str(int(rec.rank)),
            (float(rec.joint_public_i1_energy), float(rec.sigma_member)),
            fontsize=7,
            xytext=(2, 2),
            textcoords="offset points",
        )
    ax.set_xlabel("Joint public-I1 discrepancy (sum of provider mean KL)")
    ax.set_ylabel("Composed sigma for retained hypothesis")
    ax.set_title(
        "Practical non-identifiability diagnostic: "
        f"{selected['regime']}, rho={selected['rho_global']:.4g}, "
        f"H={selected['horizon']:.0f}s"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected post-hoc mechanism-audit contract status")
    _validate_firewall(contract)

    inputs = {
        key: (HERE / str(value)).resolve()
        for key, value in dict(contract["inputs"]).items()
    }
    for key, path in inputs.items():
        if not path.exists():
            raise FileNotFoundError(
                f"missing frozen input {key}: {path}\n"
                "This Stage-A audit expects local frozen result artifacts; "
                "it does not regenerate them."
            )

    comparison = pd.read_csv(inputs["final_comparison"])
    member = pd.read_csv(inputs["m3_member_curves"])
    design = pd.read_csv(inputs["m3_dominant_design"])
    weights = pd.read_csv(inputs["m3_provider_weights"])
    final_manifest = _read_json(inputs["final_manifest"])

    _require_columns(
        comparison,
        {
            "rho_global",
            "regime",
            "horizon",
            "sigma_m0",
            "m0_status",
            "sigma_m1",
            "sigma_m2_mean",
            "sigma_m3_B1400",
            "sigma_m3_B2000",
            "sigma_whitebox",
        },
        "final comparison",
    )
    _require_columns(
        member,
        {
            "budget",
            "rank",
            "variant_id",
            "rho_global",
            "regime",
            "horizon",
            "sigma_member",
            "n_trajectories",
            "alpha_renormalized",
        },
        "M3 member curves",
    )
    _require_columns(
        design,
        {
            "rank",
            "ProviderA_candidate_id",
            "ProviderB_candidate_id",
            "ProviderC_candidate_id",
            "alpha_renormalized",
            "joint_weight",
        },
        "M3 dominant design",
    )
    _require_columns(
        weights,
        {
            "provider",
            "candidate_id",
            "mean_service_time",
            "cost_rate",
            "service_cv",
            "mean_bernoulli_kl",
            "weight_v3",
        },
        "M3 provider weights",
    )

    expected_provider_sha = str(
        contract["hidden_provider_process_retrospective_audit_only"][
            "provider_process_sha256"
        ]
    )
    if str(final_manifest.get("provider_process_sha256")) != expected_provider_sha:
        raise RuntimeError("final evaluation provider-process hash differs from audit contract")
    if not bool(final_manifest.get("M3_v4_closed_after_evaluation")):
        raise RuntimeError("Stage-A audit requires a closed M3-v4 evaluation")

    if args.validate_only:
        print("M3_POSTHOC_MECHANISM_AUDIT_INPUT_VALIDATION_PASS")
        print("No simulation and no output analysis executed.")
        for key, path in inputs.items():
            print(f"{key}={path}")
        return

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    truth = _truth_candidate_audit(weights, contract)
    truth_path = out / "truth_candidate_audit.csv"
    truth.to_csv(truth_path, index=False)

    cfg = dict(contract["analysis_window"])
    top1, top1_summary = _top1_diagnostic(
        member,
        comparison,
        budget=int(cfg["m3_member_budget"]),
        rank=int(contract["top1_existing"]["rank"]),
        hmin=float(cfg["horizon_min"]),
        hmax=float(cfg["horizon_max"]),
    )
    top1_path = out / "top1_existing_diagnostic.csv"
    top1_summary_path = out / "top1_existing_summary.csv"
    top1.to_csv(top1_path, index=False)
    top1_summary.to_csv(top1_summary_path, index=False)

    decisions = _decision_metrics(comparison, top1, contract)
    decision_path = out / "decision_metrics.csv"
    decisions.to_csv(decision_path, index=False)

    ambiguity, ambiguity_summary, correlations = _ambiguity_tables(
        member, comparison, contract
    )
    ambiguity_path = out / "ambiguity_pointwise.csv"
    ambiguity_summary_path = out / "ambiguity_query_summary.csv"
    correlations_path = out / "ambiguity_correlations.csv"
    ambiguity.to_csv(ambiguity_path, index=False)
    ambiguity_summary.to_csv(ambiguity_summary_path, index=False)
    correlations.to_csv(correlations_path, index=False)

    energy_sigma, pairs, selected = _joint_energy_sigma(
        member, design, weights, ambiguity, contract
    )
    energy_sigma_path = out / "joint_energy_sigma_points.csv"
    pairs_path = out / "joint_energy_sigma_pairs.csv"
    energy_sigma.to_csv(energy_sigma_path, index=False)
    pairs.to_csv(pairs_path, index=False)

    ambiguity_fig = out / "ambiguity_vs_error.png"
    energy_fig = out / "joint_energy_vs_sigma_max_ambiguity.png"
    _plot_ambiguity_vs_error(ambiguity_summary, ambiguity_fig)
    _plot_energy_sigma(energy_sigma, selected, energy_fig)

    output_paths = [
        truth_path,
        decision_path,
        ambiguity_path,
        ambiguity_summary_path,
        correlations_path,
        energy_sigma_path,
        pairs_path,
        top1_path,
        top1_summary_path,
        ambiguity_fig,
        energy_fig,
    ]

    manifest_path = out / "posthoc_mechanism_audit_manifest.json"
    _write_json(
        manifest_path,
        {
            "status": COMPLETE_STATUS,
            "classification": str(contract["classification"]),
            "contract_sha256": _sha256(contract_path),
            "input_sha256": {key: _sha256(path) for key, path in inputs.items()},
            "output_sha256": {path.name: _sha256(path) for path in output_paths},
            "git_commit": _git_head(FIRST_SCIENCE.parent),
            "new_provider_simulation": False,
            "new_graph_simulation": False,
            "new_whitebox_simulation": False,
            "M3_changed": False,
            "selected_max_ambiguity_point": selected,
            "top1_existing_graph_trajectories": int(
                top1["n_trajectories"].astype(int).iloc[0]
            ),
            "n_query_cells": int(len(ambiguity_summary)),
            "n_decision_metric_rows": int(len(decisions)),
            "next_gate": str(contract["next_gate"]),
        },
    )

    print("M3_POSTHOC_MECHANISM_AUDIT_COMPLETE")
    print("\nTRUTH_CANDIDATE_AUDIT")
    print(truth.to_string(index=False))
    print("\nTOP1_EXISTING_DIAGNOSTIC")
    print(top1_summary.to_string(index=False))
    print("\nAMBIGUITY_CORRELATIONS")
    print(correlations.to_string(index=False))
    print("\nSELECTED_MAX_AMBIGUITY_POINT")
    print(json.dumps(selected, indent=2))
    print("\nDECISION_METRICS_CERTAIN_ONLY")
    print(
        decisions[
            decisions["subset"].astype(str) == "wb_wilson95_certain_only"
        ].to_string(index=False)
    )
    print(f"\noutput={out}")
    print("NOTE: Stage A is post-hoc explanatory analysis and performs zero simulation.")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Zero-simulation post-hoc mechanism audit for the closed M3 pilot"
    )
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_posthoc_mechanism_audit_v1.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_posthoc_mechanism_audit_v1",
    )
    p.add_argument(
        "--validate-only",
        action="store_true",
        help="validate all frozen local inputs and provenance without producing analyses",
    )
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
