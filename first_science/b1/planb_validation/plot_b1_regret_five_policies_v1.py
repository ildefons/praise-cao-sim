#!/usr/bin/env python3
"""B1 4 frozen policies + one-step KG: regret–budget plot with 95% CIs.

Read only the two *frozen* policy-specific budget-summary CSVs. This code
does NOT re-run the B1/KG policies, simulations, or bootstrap. The error bars
are the original 2,000-replicate percentile intervals conditional on the
fixed historical 7x12 matrix, not independent-world intervals.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPECTED = {
    "original": "12a163b488266119f68391e96c8c63cebb4576516a312d3e48b5d4e77c657c80",
    "kg": "38deebbc19fc371817b5e7a5f9d9e2457a773de217010fb1da7ffb4e83cb792f",
}
ORDER = ("random", "balanced", "informed", "budgeted_top2", "kg_one_step")
LABELS = ("Random", "Balanced", "Informed", "Budget-aware Top2", "Knowledge Gradient")
BUDGETS = (10, 15, 20, 30, 40)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(original_path, kg_path):
    for path, expected in ((original_path, EXPECTED["original"]), (kg_path, EXPECTED["kg"])):
        if sha256(path) != expected:
            raise ValueError("Input budget-summary hash mismatch: " + str(path))
    a, b = pd.read_csv(original_path), pd.read_csv(kg_path)
    if set(a.policy) != set(ORDER[:4]) or set(b.policy) != {ORDER[-1]}:
        raise ValueError("Unexpected policy names")
    result = pd.concat([a, b], ignore_index=True)
    if len(result) != 25 or result.duplicated(["policy", "budget"]).any():
        raise ValueError("Expected 25 unique policy/budget rows")
    for policy in ORDER:
        subset = result[result.policy == policy]
        if sorted(subset.budget.tolist()) != list(BUDGETS):
            raise ValueError("Original five budgets missing")
    if (result.episodes != 240).any():
        raise ValueError("240 episodes per policy and budget required")
    keys = ["mean_regret", "regret_low", "regret_high"]
    if not np.isfinite(result[keys].to_numpy(dtype=float)).all():
        raise ValueError("Missing / nonfinite plotted result")
    if not ((result.regret_low <= result.mean_regret) &
            (result.mean_regret <= result.regret_high)).all():
        raise ValueError("Original bootstrap bounds inconsistent")
    return result


def render(data, target):
    fig, ax = plt.subplots(figsize=(10.8, 6.2), layout="constrained")
    markers = ("o", "s", "^", "D", "P")
    for i, policy in enumerate(ORDER):
        df = data[data.policy == policy].sort_values("budget")
        x = df.budget.to_numpy(float)
        y = df.mean_regret.to_numpy(float)
        err = np.vstack([y - df.regret_low.to_numpy(float),
                         df.regret_high.to_numpy(float) - y])
        # Retain Matplotlib default color cycle (markers distinguish policies).
        ax.errorbar(x, y, yerr=err, fmt="-" + markers[i],
                    markersize=5.4, capsize=3.3,
                    elinewidth=1.15, linewidth=1.8, label=LABELS[i])
    ax.set(title="Terminal regret versus evaluation budget",
           xlim=(8, 42), ylim=(0, 0.0222), xticks=BUDGETS,
           xlabel="Evaluation budget (number of algorithm–condition measurements)",
           ylabel="Mean terminal simple regret (MAE units; lower is better)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right", fontsize=9.3)
    ax.text(0.02, 0.975,
            "PRAISE B1 · 7 algorithms × 12 conditions · "
            "240 episodes per policy and budget",
            transform=ax.transAxes, ha="left", va="top", fontsize=9.3)
    fig.text(0.5, -0.015,
             "Error bars: 95% stratified percentile-bootstrap intervals (2,000 draws), "
             "conditional on one fixed archive.\n"
             "KG is a separate retrospective supplementary benchmark; "
             "intervals are not independent-world inference.",
             ha="center", va="top", fontsize=8.5)
    fig.savefig(target, dpi=220, bbox_inches="tight", pad_inches=0.17)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original-summary", type=Path, required=True)
    ap.add_argument("--kg-summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    original = args.original_summary.expanduser().resolve()
    kg = args.kg_summary.expanduser().resolve()
    out = args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError("Refusing to overwrite an existing figure directory: " + str(out))
    frame = load(original, kg)
    out.mkdir(parents=True)
    frame.to_csv(out / "all_policies_bootstrap_summary.csv", index=False)
    for ext in ("png", "svg"):
        render(frame, out / ("b1_five_policy_regret_vs_budget_ci_v1." + ext))
    manifest = {
        "status": "B1_FIVE_POLICY_FIGURE_REGENERATED",
        "original_summary_sha256": sha256(original),
        "kg_summary_sha256": sha256(kg),
        "policies": ORDER,
        "budgets": BUDGETS,
        "bootstrap_replicates": 2000,
        "original_episode_count": 4800,
        "kg_supplementary_episode_count": 1200,
        "new_simulations": 0,
        "new_bootstraps": 0,
        "outputs_sha256": {p.name: sha256(p) for p in out.iterdir() if p.is_file()},
    }
    (out / "plot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("B1_REGRET_FIVE_POLICIES_FIGURE_PASS", out)


if __name__ == "__main__":
    main()
