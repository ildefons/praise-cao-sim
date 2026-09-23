#!/usr/bin/env python3
"""Plot final PRAISE sigma curves after the closed M3-v4 evaluation.

Outputs:
  1. sigma_final_5x3.png
     Five rho rows x three regime columns. Shows WB, M1, M2 mean + M2
     finite-portfolio range, and M3 B=1400/B=2000. M0 is shown only where
     applicable.

  2. sigma_final_5x3_compact.png
     Paper-oriented compact view: WB, M2 mean + M2 range, M3 B=1400/B=2000.

  3. individual/*.png
     One larger panel for each of the 15 (rho, regime) queries.

M2 min/max is a finite portfolio ambiguity range, not a confidence interval.
M3 retained-member min/max is optional and is likewise a finite latent-support
range, not a confidence interval. The deterministic M3 truncation interval is
shown separately when requested.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TOL = 1e-12


def _load(args):
    comparison = pd.read_csv(args.comparison.resolve())
    m3_member = pd.read_csv(args.m3_member_curves.resolve())

    required = {
        "rho_global", "regime", "horizon", "sigma_whitebox",
        "sigma_m0", "sigma_m1", "sigma_m2_mean", "sigma_m2_min", "sigma_m2_max",
        "sigma_m3_B1400", "sigma_m3_B2000",
    }
    missing = sorted(required.difference(comparison.columns))
    if missing:
        raise RuntimeError("final comparison missing columns: " + ", ".join(missing))

    member_required = {
        "budget", "rho_global", "regime", "horizon",
        "sigma_member", "alpha_renormalized",
    }
    missing = sorted(member_required.difference(m3_member.columns))
    if missing:
        raise RuntimeError("M3 member curves missing columns: " + ", ".join(missing))

    return comparison, m3_member


def _m3_support_ranges(member: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (budget, rho, regime, horizon), g in member.groupby(
        ["budget", "rho_global", "regime", "horizon"], sort=True
    ):
        rows.append(
            {
                "budget": int(budget),
                "rho_global": float(rho),
                "regime": str(regime),
                "horizon": float(horizon),
                "m3_member_min": float(g["sigma_member"].min()),
                "m3_member_max": float(g["sigma_member"].max()),
            }
        )
    return pd.DataFrame(rows)


def _augment_m3_bounds(comparison: pd.DataFrame, member: pd.DataFrame) -> pd.DataFrame:
    out = comparison.copy()

    # Finite retained-member ranges, one per M3 budget.
    ranges = _m3_support_ranges(member)
    keys = ["rho_global", "regime", "horizon"]
    for budget in (1400, 2000):
        g = ranges[ranges["budget"] == budget][
            keys + ["m3_member_min", "m3_member_max"]
        ].rename(
            columns={
                "m3_member_min": f"m3_B{budget}_member_min",
                "m3_member_max": f"m3_B{budget}_member_max",
            }
        )
        out = out.merge(g, on=keys, how="left", validate="one_to_one")

    # Deterministic full-mixture bounds induced only by omitted latent mass.
    # These are centered asymmetrically around the retained renormalized estimate:
    # full sigma is in [m*sigma_S, m*sigma_S + (1-m)].
    if "retained_mass" in out.columns:
        m = out["retained_mass"].astype(float)
        for budget in (1400, 2000):
            col = f"sigma_m3_B{budget}"
            out[f"m3_B{budget}_trunc_low"] = m * out[col].astype(float)
            out[f"m3_B{budget}_trunc_high"] = (
                m * out[col].astype(float) + (1.0 - m)
            )

    return out


def _plot_panel(
    ax,
    sub: pd.DataFrame,
    *,
    compact: bool,
    show_m3_member_range: bool,
    show_m3_truncation: bool,
):
    x = sub["horizon"].astype(float).to_numpy()

    # M2 finite portfolio ambiguity range.
    ax.fill_between(
        x,
        sub["sigma_m2_min"].astype(float).to_numpy(),
        sub["sigma_m2_max"].astype(float).to_numpy(),
        alpha=0.16,
        label="M2 finite range",
    )

    # Optional M3 retained-member range for B=2000. This is often wide and is
    # not the same object as the truncation bound.
    if show_m3_member_range:
        ax.fill_between(
            x,
            sub["m3_B2000_member_min"].astype(float).to_numpy(),
            sub["m3_B2000_member_max"].astype(float).to_numpy(),
            alpha=0.08,
            label="M3 retained-member range",
        )

    # Optional deterministic truncation interval around the B=2000 quadrature.
    if show_m3_truncation and "m3_B2000_trunc_low" in sub.columns:
        ax.fill_between(
            x,
            sub["m3_B2000_trunc_low"].astype(float).to_numpy(),
            sub["m3_B2000_trunc_high"].astype(float).to_numpy(),
            alpha=0.18,
            label="M3 truncation bound",
        )

    ax.plot(x, sub["sigma_whitebox"], linewidth=2.2, label="WB")
    ax.plot(x, sub["sigma_m2_mean"], linewidth=1.8, label="M2 mean")
    ax.plot(x, sub["sigma_m3_B1400"], linewidth=1.6, linestyle="--", label="M3 B=1400")
    ax.plot(x, sub["sigma_m3_B2000"], linewidth=2.0, label="M3 B=2000")

    if not compact:
        ax.plot(x, sub["sigma_m1"], linewidth=1.3, linestyle=":", label="M1")
        m0 = sub["sigma_m0"].notna()
        if bool(m0.any()):
            ax.plot(
                x[m0.to_numpy()],
                sub.loc[m0, "sigma_m0"].astype(float).to_numpy(),
                linewidth=1.3,
                linestyle="-.",
                label="M0",
            )

    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.20)


def _summary_5x3(
    df: pd.DataFrame,
    output: Path,
    *,
    compact: bool,
    show_m3_member_range: bool,
    show_m3_truncation: bool,
):
    rhos = sorted(df["rho_global"].astype(float).unique())
    regimes = ["G0", "G1", "G2"]
    if len(rhos) != 5:
        raise RuntimeError(f"expected five rho values, found {len(rhos)}")

    fig, axes = plt.subplots(
        len(rhos),
        len(regimes),
        figsize=(13.5, 15.2),
        sharex=True,
        sharey=True,
    )

    for i, rho in enumerate(rhos):
        for j, regime in enumerate(regimes):
            ax = axes[i, j]
            sub = df[
                np.isclose(df["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)
                & (df["regime"].astype(str) == regime)
            ].sort_values("horizon")
            if sub.empty:
                ax.axis("off")
                continue
            _plot_panel(
                ax,
                sub,
                compact=compact,
                show_m3_member_range=show_m3_member_range,
                show_m3_truncation=show_m3_truncation,
            )
            if i == 0:
                ax.set_title(regime)
            if j == 0:
                ax.set_ylabel(f"rho={rho:.6g}\nSigma")
            if i == len(rhos) - 1:
                ax.set_xlabel("Horizon H (s)")

    # One global legend only.
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=min(6, len(labels)),
        frameon=False,
        bbox_to_anchor=(0.5, 0.995),
    )
    title = (
        "Final graph-survival predictions: WB, M2 and M3"
        if compact
        else "Final graph-survival predictions across methods"
    )
    fig.suptitle(title, y=0.999)
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.965))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _individual(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    show_m3_member_range: bool,
    show_m3_truncation: bool,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    rhos = sorted(df["rho_global"].astype(float).unique())
    for rho in rhos:
        for regime in ("G0", "G1", "G2"):
            sub = df[
                np.isclose(df["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)
                & (df["regime"].astype(str) == regime)
            ].sort_values("horizon")
            if sub.empty:
                continue

            fig, ax = plt.subplots(figsize=(8.8, 5.4))
            _plot_panel(
                ax,
                sub,
                compact=False,
                show_m3_member_range=show_m3_member_range,
                show_m3_truncation=show_m3_truncation,
            )
            ax.set_title(f"rho={rho:.6g}, {regime}")
            ax.set_xlabel("Horizon H (s)")
            ax.set_ylabel("Sigma")
            ax.legend(frameon=False, fontsize=9, ncol=2)
            fig.tight_layout()
            fig.savefig(
                output_dir / f"sigma_rho_{rho:.6f}_{regime}.png",
                dpi=220,
                bbox_inches="tight",
            )
            plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Plot final M0/M1/M2/M3 sigma curves")
    p.add_argument(
        "--comparison",
        type=Path,
        default=HERE
        / "results"
        / "m3_v4_final_evaluation_v1"
        / "m3_v4_final_comparison.csv",
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
        "--output-dir",
        type=Path,
        default=HERE / "results" / "m3_v4_final_evaluation_v1" / "plots",
    )
    p.add_argument(
        "--show-m3-member-range",
        action="store_true",
        help="also shade min-max of the 14 retained M3 member curves (B=2000)",
    )
    p.add_argument(
        "--show-m3-truncation",
        action="store_true",
        help="also shade the deterministic full-mixture truncation interval (B=2000)",
    )
    args = p.parse_args()

    comparison, member = _load(args)
    df = _augment_m3_bounds(comparison, member)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    _summary_5x3(
        df,
        out / "sigma_final_5x3.png",
        compact=False,
        show_m3_member_range=args.show_m3_member_range,
        show_m3_truncation=args.show_m3_truncation,
    )
    _summary_5x3(
        df,
        out / "sigma_final_5x3_compact.png",
        compact=True,
        show_m3_member_range=args.show_m3_member_range,
        show_m3_truncation=args.show_m3_truncation,
    )
    _individual(
        df,
        out / "individual",
        show_m3_member_range=args.show_m3_member_range,
        show_m3_truncation=args.show_m3_truncation,
    )

    print("SIGMA_FINAL_PLOTS_COMPLETE")
    print(f"summary={out / 'sigma_final_5x3.png'}")
    print(f"compact={out / 'sigma_final_5x3_compact.png'}")
    print(f"individual={out / 'individual'}")
    print("M2 shaded range = frozen 27-member finite portfolio min-max, not CI.")
    if args.show_m3_member_range:
        print("M3 shaded member range = retained 14-member min-max, not CI.")
    if args.show_m3_truncation:
        print("M3 truncation band = deterministic omitted-mass bound, not CI.")


if __name__ == "__main__":
    main()
