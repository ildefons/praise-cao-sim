#!/usr/bin/env python3
"""Compute and plot pointwise graph-Monte-Carlo bands for the closed M3-v4 result.

This script intentionally keeps *member spread* separate from *Monte Carlo error*.

Pointwise 95% bands:
  WB:
    Wilson interval for the N=200 Bernoulli trajectory proportion.

  M1:
    Wilson interval for the N=100 BASE_M1 Bernoulli trajectory proportion.

  M2:
    Paired common-random-number (CRN) bootstrap. For each shared trajectory seed
    s and horizon H, first average the 27 frozen M2 member pass indicators,
        Y_s(H) = (1/27) sum_j Z_js(H).
    Then resample the N=100 shared seed units with replacement and recompute
    mean_s Y_s(H). This preserves the covariance induced by CRN across members.

  M3:
    The existing query-independent worst-case Bernoulli variance bound
        Var[hat sigma] <= (1/4) sum_j alpha_j^2 / N_j
    is propagated in two ways:
      * normal95: +/- 1.95996 * sqrt(var_bound), clipped to [0,1];
      * hoeffding95: the finite-sample Hoeffding bound
            eps = sqrt(2 * var_bound * log(40))
        for two-sided alpha=0.05, clipped to [0,1].
    The normal95 band is a conservative approximate pointwise 95% MC band.
    The Hoeffding band is distribution-free for the retained weighted mixture.
    Neither includes latent-support/model uncertainty. The deterministic M3
    omitted-mass truncation bound is a separate numerical approximation term.

All bands are pointwise in (rho, regime, H), not simultaneous bands over H.

The script writes a reproducible CSV plus summary figures into a new directory.
It never modifies the already frozen result tables or figures.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
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
from m0_analytic_composition import AdmissibilityBoundary
from run_m1_graph_prediction_v2 import _common_workload_contract
from sla_compliance_analysis import (
    SlaComplianceDefinition,
    calculate_empirical_sla_sigma_from_ledgers,
)

TOL = 1e-10
Z975 = 1.959963984540054
ALPHA = 0.05


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _wilson_interval(p: float, n: int, z: float = Z975) -> tuple[float, float]:
    """Wilson score interval reconstructed from an empirical proportion."""
    if n <= 0:
        raise ValueError("Wilson n must be positive")
    x = int(round(float(p) * int(n)))
    phat = float(x / n)
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (phat + z2 / (2.0 * n)) / den
    half = z * math.sqrt(
        phat * (1.0 - phat) / n + z2 / (4.0 * n * n)
    ) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _query_table(comparison: pd.DataFrame) -> pd.DataFrame:
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


def _m2_worker(payload: tuple) -> tuple[str, list[int], dict[str, np.ndarray]]:
    """Return per-shared-seed SLA pass matrices for one frozen M2 member."""
    (
        variant_id,
        ledger_path,
        query_records,
        horizons,
        stop_time,
        accounting_origin,
    ) = payload

    ledger = pd.read_csv(Path(ledger_path))
    required = {"trajectory", "trajectory_seed"}
    missing = sorted(required.difference(ledger.columns))
    if missing:
        raise RuntimeError(f"{variant_id}: ledger missing {missing}")

    trajectory_ids = sorted(ledger["trajectory"].astype(int).unique().tolist())
    if trajectory_ids != list(range(len(trajectory_ids))):
        raise RuntimeError(f"{variant_id}: trajectory IDs are not 0..N-1")

    seed_map = (
        ledger[["trajectory", "trajectory_seed"]]
        .drop_duplicates()
        .sort_values("trajectory")
    )
    if len(seed_map) != len(trajectory_ids):
        raise RuntimeError(f"{variant_id}: trajectory/seed mapping is not one-to-one")
    seeds = seed_map["trajectory_seed"].astype(int).tolist()

    output: dict[str, np.ndarray] = {}
    for query in query_records:
        rho = float(query["rho_global"])
        regime = str(query["regime"])
        boundary = AdmissibilityBoundary(
            l_max=float(query["A_G_l_max"]),
            c_max=float(query["A_G_c_max"]),
            q_min=float(query["A_G_q_min"]),
        )
        definition = SlaComplianceDefinition(
            rho=rho,
            accounting_origin=float(accounting_origin),
            zero_decision_compliance=1.0,
        )
        sigma, trajectory_curves, _ = calculate_empirical_sla_sigma_from_ledgers(
            ledger,
            latency_threshold=float(boundary.l_max),
            cost_threshold=float(boundary.c_max),
            quality_threshold=float(boundary.q_min),
            horizons=[float(h) for h in horizons],
            stop_time=float(stop_time),
            sla_definition=definition,
        )
        pivot = (
            trajectory_curves
            .pivot(index="trajectory", columns="horizon", values="sla_compliant")
            .reindex(index=trajectory_ids, columns=[float(h) for h in horizons])
        )
        if pivot.isna().any().any():
            raise RuntimeError(
                f"{variant_id}: incomplete trajectory curve for rho={rho}, {regime}"
            )
        values = pivot.astype(float).to_numpy()
        # Internal identity check: member mean must equal returned empirical sigma.
        sigma_vec = (
            sigma.set_index("horizon")
            .reindex([float(h) for h in horizons])["sigma"]
            .astype(float)
            .to_numpy()
        )
        if not np.allclose(values.mean(axis=0), sigma_vec, atol=TOL, rtol=0.0):
            raise RuntimeError(f"{variant_id}: trajectory/member sigma mismatch")
        key = f"{rho:.15g}|{regime}"
        output[key] = values

    return str(variant_id), seeds, output


def _compute_m2_crn_bands(
    *,
    comparison: pd.DataFrame,
    design_path: Path,
    ledger_dir: Path,
    queries: pd.DataFrame,
    horizons: list[float],
    workload: dict[str, float],
    bootstrap_reps: int,
    bootstrap_seed: int,
    workers: int,
) -> pd.DataFrame:
    design = pd.read_csv(design_path)
    required = {"variant_id", "ensemble_member"}
    missing = sorted(required.difference(design.columns))
    if missing:
        raise RuntimeError("M2 design missing: " + ", ".join(missing))

    m2_ids = (
        design.loc[design["ensemble_member"].astype(bool), "variant_id"]
        .astype(str)
        .tolist()
    )
    if len(m2_ids) != 27:
        raise RuntimeError(f"expected 27 frozen M2 members, found {len(m2_ids)}")

    query_records = queries.to_dict("records")
    tasks = []
    for variant_id in m2_ids:
        path = ledger_dir / f"{variant_id}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing M2 prediction ledger: {path}")
        tasks.append(
            (
                variant_id,
                str(path),
                query_records,
                horizons,
                float(workload["horizon_max"]),
                float(workload["accounting_origin"]),
            )
        )

    results = []
    if workers <= 1:
        for i, task in enumerate(tasks, start=1):
            results.append(_m2_worker(task))
            print(f"M2 MC trajectories reconstructed {i}/{len(tasks)}", flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            future_map = {pool.submit(_m2_worker, task): task[0] for task in tasks}
            done = 0
            for future in concurrent.futures.as_completed(future_map):
                results.append(future.result())
                done += 1
                print(
                    f"M2 MC trajectories reconstructed {done}/{len(tasks)} "
                    f"({future_map[future]})",
                    flush=True,
                )

    # Ensure every member used exactly the same CRN seed ordering.
    seed_ref = results[0][1]
    for variant_id, seeds, _ in results[1:]:
        if seeds != seed_ref:
            raise RuntimeError(f"{variant_id}: CRN seed ordering differs")
    n = len(seed_ref)
    if n <= 1:
        raise RuntimeError("M2 CRN bank too small")

    rng = np.random.default_rng(int(bootstrap_seed))
    rows: list[dict[str, Any]] = []
    for query in query_records:
        rho = float(query["rho_global"])
        regime = str(query["regime"])
        key = f"{rho:.15g}|{regime}"

        # Shape: members x shared-seeds x horizons.
        cube = np.stack([out[key] for _, _, out in results], axis=0)
        if cube.shape != (27, n, len(horizons)):
            raise RuntimeError(f"unexpected M2 trajectory cube shape {cube.shape}")

        # One CRN experimental unit is one shared seed across all 27 members.
        y = cube.mean(axis=0)  # n_shared_seeds x horizons
        estimate = y.mean(axis=0)

        frozen = (
            comparison[
                np.isclose(
                    comparison["rho_global"].astype(float),
                    rho,
                    atol=TOL,
                    rtol=0.0,
                )
                & (comparison["regime"].astype(str) == regime)
            ]
            .sort_values("horizon")
        )
        frozen = (
            frozen.set_index("horizon")
            .reindex(horizons)["sigma_m2_mean"]
            .astype(float)
            .to_numpy()
        )
        if not np.allclose(estimate, frozen, atol=1e-10, rtol=0.0):
            delta = float(np.max(np.abs(estimate - frozen)))
            raise RuntimeError(
                f"M2 reconstructed mean disagrees with freeze at {rho},{regime}; "
                f"max delta={delta}"
            )

        # Paired seed bootstrap. Multinomial counts avoid materializing
        # bootstrap_reps x n x n_horizon resampled arrays.
        counts = rng.multinomial(
            n,
            np.full(n, 1.0 / n, dtype=float),
            size=int(bootstrap_reps),
        )
        boot = (counts @ y) / float(n)
        lower = np.quantile(boot, ALPHA / 2.0, axis=0)
        upper = np.quantile(boot, 1.0 - ALPHA / 2.0, axis=0)
        se = np.std(boot, axis=0, ddof=1)

        for k, horizon in enumerate(horizons):
            rows.append(
                {
                    "rho_global": rho,
                    "regime": regime,
                    "horizon": float(horizon),
                    "m2_mc_point": float(estimate[k]),
                    "m2_mc_boot_se": float(se[k]),
                    "m2_mc95_low": float(lower[k]),
                    "m2_mc95_high": float(upper[k]),
                    "m2_crn_n_shared_seeds": int(n),
                    "m2_bootstrap_reps": int(bootstrap_reps),
                    "m2_bootstrap_seed": int(bootstrap_seed),
                }
            )

    return pd.DataFrame(rows)


def _compute_m3_bands(
    *,
    comparison: pd.DataFrame,
    m3_member_path: Path,
) -> pd.DataFrame:
    member = pd.read_csv(m3_member_path)
    required = {
        "budget", "rank", "rho_global", "regime", "horizon",
        "sigma_member", "n_trajectories", "alpha_renormalized",
    }
    missing = sorted(required.difference(member.columns))
    if missing:
        raise RuntimeError("M3 member curves missing: " + ", ".join(missing))

    rows: list[dict[str, Any]] = []
    for (budget, rho, regime, horizon), g in member.groupby(
        ["budget", "rho_global", "regime", "horizon"],
        sort=True,
    ):
        budget = int(budget)
        alpha = g["alpha_renormalized"].astype(float).to_numpy()
        n = g["n_trajectories"].astype(int).to_numpy()
        p = g["sigma_member"].astype(float).to_numpy()
        if np.any(n <= 0):
            raise RuntimeError("M3 contains non-positive trajectory allocation")
        if not np.isclose(alpha.sum(), 1.0, atol=1e-12, rtol=0.0):
            raise RuntimeError("M3 retained weights do not sum to one")

        point = float(np.sum(alpha * p))
        var_bound = float(0.25 * np.sum(alpha * alpha / n))
        se_bound = float(math.sqrt(var_bound))

        # Approximate 95% band from the rigorous variance upper bound.
        normal_half = Z975 * se_bound

        # Distribution-free two-sided Hoeffding bound:
        # P(|hat-mu - mu| >= eps) <=
        #   2 exp(-2 eps^2 / sum_j alpha_j^2/N_j).
        # Since var_bound = 1/4 * sum alpha_j^2/N_j:
        # eps = sqrt(2 * var_bound * log(2/alpha)).
        hoeffding_half = math.sqrt(
            2.0 * var_bound * math.log(2.0 / ALPHA)
        )

        frozen_col = f"sigma_m3_B{budget}"
        frozen = comparison[
            np.isclose(
                comparison["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
            & (comparison["regime"].astype(str) == str(regime))
            & np.isclose(
                comparison["horizon"].astype(float),
                float(horizon),
                atol=TOL,
                rtol=0.0,
            )
        ]
        if len(frozen) != 1:
            raise RuntimeError("M3 frozen point lookup is not unique")
        frozen_point = float(frozen.iloc[0][frozen_col])
        if abs(point - frozen_point) > 1e-10:
            raise RuntimeError(
                f"M3 B={budget} reconstructed weighted point differs from freeze"
            )

        rows.append(
            {
                "budget": budget,
                "rho_global": float(rho),
                "regime": str(regime),
                "horizon": float(horizon),
                "m3_mc_point": point,
                "m3_mc_var_bound": var_bound,
                "m3_mc_se_bound": se_bound,
                "m3_mc95_normal_low": max(0.0, point - normal_half),
                "m3_mc95_normal_high": min(1.0, point + normal_half),
                "m3_mc95_hoeffding_low": max(0.0, point - hoeffding_half),
                "m3_mc95_hoeffding_high": min(1.0, point + hoeffding_half),
                "m3_mc95_normal_halfwidth": normal_half,
                "m3_mc95_hoeffding_halfwidth": hoeffding_half,
            }
        )
    return pd.DataFrame(rows)


def _assemble_bands(
    *,
    comparison: pd.DataFrame,
    final_manifest: dict[str, Any],
    m2_manifest: dict[str, Any],
    m2_bands: pd.DataFrame,
    m3_bands: pd.DataFrame,
) -> pd.DataFrame:
    out = comparison.copy()

    n_wb = int(final_manifest["n_fresh_whitebox_trajectories"])
    n_m1 = int(m2_manifest["n_trajectories_per_variant"])
    wb_low, wb_high, m1_low, m1_high = [], [], [], []
    for rec in out.itertuples(index=False):
        lo, hi = _wilson_interval(float(rec.sigma_whitebox), n_wb)
        wb_low.append(lo)
        wb_high.append(hi)
        lo, hi = _wilson_interval(float(rec.sigma_m1), n_m1)
        m1_low.append(lo)
        m1_high.append(hi)
    out["wb_mc95_low"] = wb_low
    out["wb_mc95_high"] = wb_high
    out["m1_mc95_low"] = m1_low
    out["m1_mc95_high"] = m1_high
    out["wb_n_trajectories"] = n_wb
    out["m1_n_trajectories"] = n_m1

    keys = ["rho_global", "regime", "horizon"]
    out = out.merge(
        m2_bands,
        on=keys,
        how="left",
        validate="one_to_one",
    )

    for budget in (1400, 2000):
        g = m3_bands[m3_bands["budget"].astype(int) == budget].copy()
        rename = {
            c: f"m3_B{budget}_{c.removeprefix('m3_')}"
            for c in g.columns
            if c.startswith("m3_")
        }
        g = g.drop(columns=["budget"]).rename(columns=rename)
        out = out.merge(g, on=keys, how="left", validate="one_to_one")

    if out.filter(regex=r"_mc95_").isna().any().any():
        raise RuntimeError("band merge produced missing MC intervals")
    return out


def _plot_panel(
    ax,
    sub: pd.DataFrame,
    *,
    compact: bool,
    m3_band: str,
    show_member_ranges: bool,
    m3_member: pd.DataFrame | None,
):
    x = sub["horizon"].astype(float).to_numpy()

    if show_member_ranges:
        ax.fill_between(
            x,
            sub["sigma_m2_min"].astype(float).to_numpy(),
            sub["sigma_m2_max"].astype(float).to_numpy(),
            alpha=0.08,
            label="M2 member range",
        )
        if m3_member is not None:
            rho = float(sub["rho_global"].iloc[0])
            regime = str(sub["regime"].iloc[0])
            g = m3_member[
                (m3_member["budget"].astype(int) == 2000)
                & np.isclose(
                    m3_member["rho_global"].astype(float),
                    rho,
                    atol=TOL,
                    rtol=0.0,
                )
                & (m3_member["regime"].astype(str) == regime)
            ]
            if not g.empty:
                rg = (
                    g.groupby("horizon", as_index=False)
                    .agg(low=("sigma_member", "min"), high=("sigma_member", "max"))
                    .set_index("horizon")
                    .reindex(x)
                )
                ax.fill_between(
                    x,
                    rg["low"].astype(float).to_numpy(),
                    rg["high"].astype(float).to_numpy(),
                    alpha=0.045,
                    label="M3 member range",
                )

    # Pointwise MC bands. Keep alpha low because several bands overlap.
    ax.fill_between(
        x,
        sub["wb_mc95_low"].astype(float).to_numpy(),
        sub["wb_mc95_high"].astype(float).to_numpy(),
        alpha=0.13,
        label="WB 95% MC",
    )
    ax.fill_between(
        x,
        sub["m2_mc95_low"].astype(float).to_numpy(),
        sub["m2_mc95_high"].astype(float).to_numpy(),
        alpha=0.11,
        label="M2 95% MC (paired bootstrap)",
    )

    suffix = "mc95_normal" if m3_band == "normal" else "mc95_hoeffding"
    for budget, alpha in ((1400, 0.08), (2000, 0.10)):
        low = f"m3_B{budget}_{suffix}_low"
        high = f"m3_B{budget}_{suffix}_high"
        ax.fill_between(
            x,
            sub[low].astype(float).to_numpy(),
            sub[high].astype(float).to_numpy(),
            alpha=alpha,
            label=f"M3 B={budget} 95% MC",
        )

    ax.plot(x, sub["sigma_whitebox"], linewidth=2.2, label="WB")
    ax.plot(x, sub["sigma_m2_mean"], linewidth=1.8, label="M2 mean")
    ax.plot(
        x,
        sub["sigma_m3_B1400"],
        linewidth=1.6,
        linestyle="--",
        label="M3 B=1400",
    )
    ax.plot(x, sub["sigma_m3_B2000"], linewidth=2.0, label="M3 B=2000")

    if not compact:
        ax.fill_between(
            x,
            sub["m1_mc95_low"].astype(float).to_numpy(),
            sub["m1_mc95_high"].astype(float).to_numpy(),
            alpha=0.08,
            label="M1 95% MC",
        )
        ax.plot(x, sub["sigma_m1"], linewidth=1.3, linestyle=":", label="M1")
        m0 = sub["sigma_m0"].notna()
        if bool(m0.any()):
            ax.plot(
                x[m0.to_numpy()],
                sub.loc[m0, "sigma_m0"].astype(float).to_numpy(),
                linewidth=1.2,
                linestyle="-.",
                label="M0",
            )

    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.20)


def _plot_summary(
    frame: pd.DataFrame,
    output: Path,
    *,
    compact: bool,
    m3_band: str,
    show_member_ranges: bool,
    m3_member: pd.DataFrame | None,
):
    rhos = sorted(frame["rho_global"].astype(float).unique())
    regimes = ["G0", "G1", "G2"]
    if len(rhos) != 5:
        raise RuntimeError(f"expected five rho rows, found {len(rhos)}")

    fig, axes = plt.subplots(
        len(rhos),
        len(regimes),
        figsize=(13.8, 15.4),
        sharex=True,
        sharey=True,
    )
    for i, rho in enumerate(rhos):
        for j, regime in enumerate(regimes):
            ax = axes[i, j]
            sub = frame[
                np.isclose(
                    frame["rho_global"].astype(float),
                    rho,
                    atol=TOL,
                    rtol=0.0,
                )
                & (frame["regime"].astype(str) == regime)
            ].sort_values("horizon")
            _plot_panel(
                ax,
                sub,
                compact=compact,
                m3_band=m3_band,
                show_member_ranges=show_member_ranges,
                m3_member=m3_member,
            )
            if i == 0:
                ax.set_title(regime)
            if j == 0:
                ax.set_ylabel(f"rho={rho:.6g}\nSigma")
            if i == len(rhos) - 1:
                ax.set_xlabel("Horizon H (s)")

    # De-duplicate legend labels while preserving order.
    handles, labels = axes[0, 0].get_legend_handles_labels()
    dedup: dict[str, Any] = {}
    for h, label in zip(handles, labels):
        if label not in dedup:
            dedup[label] = h
    fig.legend(
        list(dedup.values()),
        list(dedup.keys()),
        loc="upper center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.5, 0.995),
        fontsize=8.5,
    )
    qualifier = (
        "M3 variance-bound normal bands"
        if m3_band == "normal"
        else "M3 Hoeffding bands"
    )
    title = (
        "Final graph-survival predictions with pointwise Monte Carlo bands"
        f" ({qualifier})"
    )
    fig.suptitle(title, y=0.999)
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.955))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()

    comparison = pd.read_csv(args.comparison.resolve())
    final_manifest = _read_json(args.final_manifest.resolve())
    m2_manifest = _read_json(args.m2_manifest.resolve())

    queries = _query_table(comparison)
    horizons = sorted(comparison["horizon"].astype(float).unique().tolist())

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(),
        args.i1_manifest.resolve(),
    )
    workload = _common_workload_contract(metadata)

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bands_path = output / "sigma_pointwise_mc_bands.csv"

    if bands_path.exists() and not args.force_recompute:
        print(f"Reusing cached bands: {bands_path}", flush=True)
        bands = pd.read_csv(bands_path)
    else:
        m2 = _compute_m2_crn_bands(
            comparison=comparison,
            design_path=args.m2_design.resolve(),
            ledger_dir=args.m2_ledger_dir.resolve(),
            queries=queries,
            horizons=horizons,
            workload=workload,
            bootstrap_reps=int(args.bootstrap_reps),
            bootstrap_seed=int(args.bootstrap_seed),
            workers=max(1, int(args.workers)),
        )
        m3 = _compute_m3_bands(
            comparison=comparison,
            m3_member_path=args.m3_member_curves.resolve(),
        )
        bands = _assemble_bands(
            comparison=comparison,
            final_manifest=final_manifest,
            m2_manifest=m2_manifest,
            m2_bands=m2,
            m3_bands=m3,
        )
        bands.to_csv(bands_path, index=False)
        print(f"Wrote bands: {bands_path}", flush=True)

    m3_member = None
    if args.show_member_ranges:
        m3_member = pd.read_csv(args.m3_member_curves.resolve())

    tag = "normal" if args.m3_band == "normal" else "hoeffding"
    suffix = "_with_ranges" if args.show_member_ranges else ""
    full_path = output / f"sigma_final_5x3_mc95_{tag}{suffix}.png"
    compact_path = output / f"sigma_final_5x3_mc95_{tag}_compact{suffix}.png"

    _plot_summary(
        bands,
        full_path,
        compact=False,
        m3_band=args.m3_band,
        show_member_ranges=bool(args.show_member_ranges),
        m3_member=m3_member,
    )
    _plot_summary(
        bands,
        compact_path,
        compact=True,
        m3_band=args.m3_band,
        show_member_ranges=bool(args.show_member_ranges),
        m3_member=m3_member,
    )

    # Concise diagnostics on band widths over H60..240.
    diag = bands[
        (bands["horizon"].astype(float) >= 60.0 - TOL)
        & (bands["horizon"].astype(float) <= 240.0 + TOL)
    ].copy()
    rows = [
        {
            "method": "WB Wilson95",
            "mean_width": float(
                np.mean(diag["wb_mc95_high"] - diag["wb_mc95_low"])
            ),
            "max_width": float(
                np.max(diag["wb_mc95_high"] - diag["wb_mc95_low"])
            ),
        },
        {
            "method": "M1 Wilson95",
            "mean_width": float(
                np.mean(diag["m1_mc95_high"] - diag["m1_mc95_low"])
            ),
            "max_width": float(
                np.max(diag["m1_mc95_high"] - diag["m1_mc95_low"])
            ),
        },
        {
            "method": "M2 paired-bootstrap95",
            "mean_width": float(
                np.mean(diag["m2_mc95_high"] - diag["m2_mc95_low"])
            ),
            "max_width": float(
                np.max(diag["m2_mc95_high"] - diag["m2_mc95_low"])
            ),
        },
    ]
    for budget in (1400, 2000):
        for kind in ("normal", "hoeffding"):
            lo = f"m3_B{budget}_mc95_{kind}_low"
            hi = f"m3_B{budget}_mc95_{kind}_high"
            rows.append(
                {
                    "method": f"M3 B={budget} {kind}95",
                    "mean_width": float(np.mean(diag[hi] - diag[lo])),
                    "max_width": float(np.max(diag[hi] - diag[lo])),
                }
            )
    width_table = pd.DataFrame(rows)
    width_path = output / "sigma_mc_band_width_summary_H60_H240.csv"
    width_table.to_csv(width_path, index=False)

    print("\nSIGMA_POINTWISE_MC_BANDS_COMPLETE")
    print(width_table.to_string(index=False))
    print(f"bands={bands_path}")
    print(f"figure={full_path}")
    print(f"compact={compact_path}")
    print(f"width_summary={width_path}")
    print(
        "NOTE: member min-max ranges are latent-model spread, not MC error bars."
    )
    print(
        "NOTE: all reported MC intervals/bounds are pointwise, not simultaneous over H."
    )
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Compute/plot pointwise MC bands for frozen M1/M2/M3 sigma curves"
    )
    p.add_argument(
        "--comparison",
        type=Path,
        default=HERE
        / "results"
        / "m3_v4_final_evaluation_v1"
        / "m3_v4_final_comparison.csv",
    )
    p.add_argument(
        "--final-manifest",
        type=Path,
        default=HERE
        / "results"
        / "m3_v4_final_evaluation_v1"
        / "m3_v4_final_evaluation_manifest.json",
    )
    p.add_argument(
        "--m2-manifest",
        type=Path,
        default=HERE
        / "results"
        / "sigma_regime_blind_prediction_v1"
        / "sigma_regime_prediction_manifest_v1.json",
    )
    p.add_argument(
        "--m2-design",
        type=Path,
        default=HERE
        / "results"
        / "sigma_regime_blind_prediction_v1"
        / "sigma_regime_variant_design.csv",
    )
    p.add_argument(
        "--m2-ledger-dir",
        type=Path,
        default=HERE
        / "results"
        / "sigma_regime_blind_prediction_v1"
        / "ledgers",
    )
    p.add_argument(
        "--m3-member-curves",
        type=Path,
        default=HERE
        / "results"
        / "m3_v4_dominant_mass_graph_v1"
        / "m3_v4_member_curves.csv",
    )
    p.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    p.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=HERE
        / "results"
        / "m3_v4_final_evaluation_v1"
        / "mc_bands",
    )
    p.add_argument("--bootstrap-reps", type=int, default=5000)
    p.add_argument("--bootstrap-seed", type=int, default=20260924)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument(
        "--m3-band",
        choices=("normal", "hoeffding"),
        default="normal",
        help=(
            "M3 plotting band: normal uses 1.96*worst-case-SE; "
            "hoeffding uses the distribution-free two-sided 95% bound"
        ),
    )
    p.add_argument(
        "--show-member-ranges",
        action="store_true",
        help="overlay faint M2 and M3 finite member min-max ranges",
    )
    p.add_argument(
        "--force-recompute",
        action="store_true",
        help="reconstruct M2 trajectory outcomes even if cached band CSV exists",
    )
    args = p.parse_args()
    if int(args.bootstrap_reps) < 1000:
        raise ValueError("--bootstrap-reps should be at least 1000")
    run(args)


if __name__ == "__main__":
    main()
