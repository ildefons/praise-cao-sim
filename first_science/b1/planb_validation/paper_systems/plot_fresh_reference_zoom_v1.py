#!/usr/bin/env python3
"""Render a paper-only, vertically zoomed fresh-reference regret figure.

Reads the immutable 13-budget summary CSV. No policy replay, bootstrap,
reference generation, or other experimental computation is performed.
The original shared-axis SVGs and their provenance manifests are untouched.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
DATA = (
    HERE.parent
    / "results/b1_nine_policy_13_budget_extension_v1/tables"
    / "b0001_nine_policy_13_budget_regret.csv"
)
EXPECTED_SHA256 = "01f5baf2c3cbb6e15ac9dd652b5905efb75584b84acfc6e1037b6a1458af76cd"
YMAX = 0.012
OUTPUT_STEM = HERE / "figures/fresh_reference_nine_policy_13_budget_y012"

# Reuse the original policy order, labels, markers, colors, and plotting
# function. Only the fresh-reference panel's vertical range changes.
sys.path.insert(0, str(HERE.parent))
import plot_b1_nine_policies_shared_axis_13budgets_v1 as source_plot  # noqa: E402


def main() -> None:
    if hashlib.sha256(DATA.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError("The archived fresh-reference summary CSV has changed")

    data = pd.read_csv(DATA)
    required = {"policy", "budget", "episodes", "mean_regret", "regret_low", "regret_high"}
    if not required.issubset(data.columns) or len(data) != 117:
        raise ValueError("Expected the complete nine-policy, thirteen-budget summary")
    if data.duplicated(["policy", "budget"]).any():
        raise ValueError("Repeated policy–budget entry in archived summary")
    if set(data.policy) != set(source_plot.frozen_plot.REFERENCE):
        raise ValueError("Unexpected policy catalogue")
    if set(data.budget) != set(source_plot.BUDGETS) or not (data.episodes == 240).all():
        raise ValueError("Unexpected budgets or number of episodes")
    for policy in source_plot.frozen_plot.REFERENCE:
        if set(data.loc[data.policy == policy, "budget"]) != set(source_plot.BUDGETS):
            raise ValueError(f"Incomplete budget curve: {policy}")

    bounds = data[["regret_low", "mean_regret", "regret_high"]].to_numpy(float)
    if not np.isfinite(bounds).all():
        raise ValueError("Nonfinite regret or interval")
    if (bounds[:, 0] > bounds[:, 1]).any() or (bounds[:, 1] > bounds[:, 2]).any():
        raise ValueError("Invalid interval ordering")
    max_upper = float(bounds[:, 2].max())
    if max_upper > YMAX:
        raise ValueError(f"Requested y-limit {YMAX} would clip interval upper bound {max_upper}")

    OUTPUT_STEM.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.1, 7.2), layout="constrained")
    source_plot.draw(
        ax, data, "Fresh-reference: nine-policy regret versus budget",
        YMAX, legend=True,
    )
    fig.text(
        .5, -.013,
        "95% stratified episode bootstrap (2,000 draws); conditional on this archive. "
        "Dotted original joint policies are not matched condition-choice controls.",
        ha="center", va="top", fontsize=8,
    )
    for ext in ("svg", "pdf"):
        fig.savefig(OUTPUT_STEM.with_suffix("." + ext), dpi=220,
                    bbox_inches="tight", pad_inches=.16)
    plt.close(fig)
    print(f"PRAISE_FIGURE4_ZOOM_PASS ymax={YMAX:.3f} max_interval_upper={max_upper:.9f}")


if __name__ == "__main__":
    main()
