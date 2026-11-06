#!/usr/bin/env python3
"""Read-only seven-policy *reconstruction* comparison, not original Nov 6 ablation.

Combines frozen B1 four-policy, reproduced KG-adaptive, and two reconstructed
uniform-condition summary CSVs. 95% intervals are READ from the already
computed stratified 2,000-resample percentile-bootstrap summaries.
Does not alter source data, bootstrap, or run simulations/policies.
"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXPECTED_HASHES = {
    "original": "12a163b488266119f68391e96c8c63cebb4576516a312d3e48b5d4e77c657c80",
    "kg": "38deebbc19fc371817b5e7a5f9d9e2457a773de217010fb1da7ffb4e83cb792f",
}
POLICIES = (
    "random", "balanced", "informed", "budgeted_top2", "kg_one_step",
    "top2_uniform_reconstruction", "kg_uniform_reconstruction",
)
LABELS = (
    "Random", "Balanced", "Informed", "Top2 adaptive", "KG adaptive",
    "Top2 uniform (reconstructed)", "KG uniform (reconstructed)",
)
BUDGETS = (10, 15, 20, 30, 40)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(args):
    inputs = {
        "original": args.original_summary.expanduser().resolve(),
        "kg": args.kg_summary.expanduser().resolve(),
        "uniform_reconstruction": args.uniform_summary.expanduser().resolve(),
    }
    for name, expected in EXPECTED_HASHES.items():
        if digest(inputs[name]) != expected:
            raise ValueError("Frozen summary hash mismatch: " + name)
    frames = [pd.read_csv(path) for path in inputs.values()]
    result = pd.concat(frames, ignore_index=True)
    if len(result) != 35 or result.duplicated(["policy", "budget"]).any():
        raise ValueError("Require 35 unique policy-budget rows")
    if set(result.policy) != set(POLICIES):
        raise ValueError("Unexpected policy inventory")
    for policy in POLICIES:
        subset = result[result.policy == policy]
        if sorted(subset.budget.tolist()) != list(BUDGETS):
            raise ValueError("Missing budget for " + policy)
        if (subset.episodes.astype(int) != 240).any():
            raise ValueError("Wrong episode count for " + policy)
    for field in ("mean_regret", "regret_low", "regret_high"):
        if not np.isfinite(result[field].to_numpy(float)).all():
            raise ValueError("Non-finite " + field)
    if not ((result.regret_low <= result.mean_regret) &
            (result.mean_regret <= result.regret_high)).all():
        raise ValueError("Invalid bootstrap confidence interval")
    return result, inputs

def render(frame, path):
    fig, ax = plt.subplots(figsize=(11.5, 6.7), layout="constrained")
    markers = ("o", "s", "^", "D", "P", "v", "X")
    for i, policy in enumerate(POLICIES):
        df = frame[frame.policy == policy].sort_values("budget")
        y = df.mean_regret.to_numpy(float)
        low = df.regret_low.to_numpy(float)
        high = df.regret_high.to_numpy(float)
        style = "--" if "uniform" in policy else "-"
        ax.errorbar(df.budget, y, yerr=np.vstack((y-low, high-y)),
                    linestyle=style, marker=markers[i], markersize=5.0,
                    linewidth=1.65, capsize=2.7, label=LABELS[i])
    ax.set(xlim=(8,42), ylim=(0,0.024), xticks=BUDGETS,
           xlabel="Evaluation budget (distinct predictor–condition measurements)",
           ylabel="Mean terminal simple regret (MAE units; lower is better)",
           title="PRAISE B1: seven-policy retrospective comparison")
    ax.grid(axis="y", alpha=.25)
    ax.legend(fontsize=8.4, loc="upper right")
    fig.text(.5,-.015,
             "95% within-archive stratified percentile-bootstrap intervals (2,000 draws). "
             "Uniform policies are reconstructed variants, not a verified replication of the November 6 ablation.",
             ha="center", va="top", fontsize=8.0, wrap=True)
    fig.savefig(path,dpi=200,bbox_inches="tight",pad_inches=.15)
    plt.close(fig)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-summary",type=Path,required=True)
    p.add_argument("--kg-summary",type=Path,required=True)
    p.add_argument("--uniform-summary",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    out=args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError("Refusing overwrite: " + str(out))
    frame, inputs = load(args)
    out.mkdir(parents=True)
    frame[["policy","budget","episodes","mean_regret","regret_low","regret_high"]].to_csv(
        out/"b1_seven_policy_reconstruction_with_bootstrap_ci_v1.csv",index=False)
    for ext in ("png","svg"):
        render(frame,out/("b1_seven_policy_reconstruction_regret_vs_budget_ci_v1."+ext))
    files=sorted(out.glob("*"))
    manifest={
        "status":"B1_SEVEN_POLICY_RECONSTRUCTION_FIGURE_V1",
        "caveat":"Uniform policies use reconstructed arm-choice rules; not original Nov 6 ablation replication",
        "input_sha256":{name:digest(path) for name,path in inputs.items()},
        "policies":POLICIES,"budgets":BUDGETS,
        "episodes_per_policy_budget":240,"bootstrap_replicates":2000,
        "bootstrap":"existing stratified percentile intervals, no new resampling",
        "new_simulations":0,"new_policy_replays":0,"new_bootstraps":0,
        "output_sha256":{x.name:digest(x) for x in files}
    }
    (out/"plot_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("B1_SEVEN_POLICY_RECONSTRUCTION_FIGURE_PASS",out)

if __name__=="__main__":
    main()
