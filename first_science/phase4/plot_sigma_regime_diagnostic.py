#!/usr/bin/env python3
"""Quick diagnostic plot of final sigma curves across G0/G1/G2.

For internal inspection only. Reads the already-frozen final comparison CSV.
No simulation, no refit, no white-box generation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--comparison",
        type=Path,
        default=HERE / "results" / "sigma_regime_final_evaluation_v1" / "sigma_regime_final_comparison.csv",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "sigma_regime_final_evaluation_v1" / "sigma_regime_curves_5x3.png",
    )
    p.add_argument(
        "--show-m0-raw",
        action="store_true",
        help="Also show the raw local-product diagnostic where operational M0 is not applicable.",
    )
    args = p.parse_args()

    d = pd.read_csv(args.comparison)
    required = {
        "rho_global", "regime", "horizon",
        "sigma_whitebox", "sigma_m0", "sigma_m0_raw_product",
        "sigma_m1", "sigma_m2_mean", "sigma_m2_min", "sigma_m2_max",
        "m0_status",
    }
    missing = sorted(required.difference(d.columns))
    if missing:
        raise RuntimeError("missing columns: " + ", ".join(missing))

    rhos = sorted(float(v) for v in d["rho_global"].unique())
    regimes = ["G0", "G1", "G2"]

    fig, axes = plt.subplots(
        len(rhos), len(regimes),
        figsize=(15, 14.5),
        sharex=True,
        sharey=True,
    )
    if len(rhos) == 1:
        axes = np.asarray([axes])

    handles = {}
    for i, rho in enumerate(rhos):
        for j, regime in enumerate(regimes):
            ax = axes[i, j]
            g = d[
                np.isclose(d["rho_global"].astype(float), rho, atol=1e-12, rtol=0.0)
                & (d["regime"].astype(str) == regime)
            ].sort_values("horizon")
            if g.empty:
                ax.set_visible(False)
                continue

            h = g["horizon"].astype(float).to_numpy()

            band = ax.fill_between(
                h,
                g["sigma_m2_min"].astype(float),
                g["sigma_m2_max"].astype(float),
                alpha=0.16,
                label="M2 range",
            )
            wb, = ax.plot(
                h, g["sigma_whitebox"].astype(float),
                lw=2.8, ls="-", label="WB"
            )
            m1, = ax.plot(
                h, g["sigma_m1"].astype(float),
                lw=2.0, ls="-.", label="M1"
            )
            m2, = ax.plot(
                h, g["sigma_m2_mean"].astype(float),
                lw=2.2, ls="-", label="M2 mean"
            )

            predicted = g["m0_status"].astype(str).eq("PREDICTED")
            if predicted.any():
                m0, = ax.plot(
                    h[predicted.to_numpy()],
                    g.loc[predicted, "sigma_m0"].astype(float),
                    lw=2.0,
                    ls="--",
                    label="M0",
                )
                handles["M0"] = m0
            else:
                ax.text(
                    0.03, 0.07, "M0: N/A",
                    transform=ax.transAxes,
                    fontsize=9,
                )
                if args.show_m0_raw:
                    raw, = ax.plot(
                        h,
                        g["sigma_m0_raw_product"].astype(float),
                        lw=1.2,
                        ls=":",
                        label="M0 raw diagnostic",
                    )
                    handles["M0 raw diagnostic"] = raw

            if args.show_m0_raw and predicted.any():
                raw_na = ~predicted
                if raw_na.any():
                    raw, = ax.plot(
                        h[raw_na.to_numpy()],
                        g.loc[raw_na, "sigma_m0_raw_product"].astype(float),
                        lw=1.2,
                        ls=":",
                        label="M0 raw diagnostic",
                    )
                    handles["M0 raw diagnostic"] = raw

            handles["WB"] = wb
            handles["M1"] = m1
            handles["M2 mean"] = m2
            handles["M2 range"] = band

            ax.set_ylim(-0.02, 1.02)
            ax.grid(alpha=0.22)
            if i == 0:
                ax.set_title(regime)
            if j == 0:
                ax.set_ylabel(f"rho={rho:.6g}\nsigma")
            if i == len(rhos) - 1:
                ax.set_xlabel("Horizon H (s)")

    # Use large proxy handles in a dedicated legend band. This makes the
    # mapping readable even when the actual curves overlap near sigma=1.
    legend_handles = [
        Line2D([0], [0], lw=3.2, ls="-", label="WB  (white-box truth)"),
        Line2D([0], [0], lw=2.6, ls="--", label="M0  (analytic product)"),
        Line2D([0], [0], lw=2.6, ls="-.", label="M1  (single surrogate)"),
        Line2D([0], [0], lw=2.8, ls="-", label="M2  (ensemble mean)"),
        Patch(alpha=0.20, label="M2  (min-max range)"),
    ]
    if args.show_m0_raw:
        legend_handles.append(
            Line2D([0], [0], lw=2.2, ls=":", label="M0 raw  (diagnostic only)")
        )

    fig.suptitle(
        "Frozen final sigma curves: WB vs M0 / M1 / M2",
        fontsize=15,
        y=0.995,
    )
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.965),
        ncol=3,
        fontsize=11,
        handlelength=3.6,
        handletextpad=0.8,
        columnspacing=2.4,
        borderpad=0.8,
        frameon=True,
    )
    fig.subplots_adjust(
        top=0.875,
        bottom=0.06,
        left=0.08,
        right=0.985,
        hspace=0.22,
        wspace=0.12,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"saved={args.output}")


if __name__ == "__main__":
    main()
