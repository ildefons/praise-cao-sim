#!/usr/bin/env python3
"""Plot historical and B0001 original nine policies across 13 budgets.

Reuses the frozen original plotting script's policy IDs, labels, colors,
markers and line styles. The single shared y range is computed from BOTH
archives, then applied identically to each nine-curve plot. No policy run,
resampling, or physical simulation is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import plot_b1_condition_selection_controlled_v1 as frozen_plot


BUDGETS = (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80)
NEW_BUDGETS = (25, 35, 45, 55, 65, 70, 75, 80)
MARKERS = ("o", "s", "^", "D", "v", "P", "X", "h", "*")
FROZEN_SUMMARY_SHA = {
    "historical": "e0c1e58ce733a07063153357a81094c663001537cb083fa64e5c0d6335343572",
    "b0001": "4a36235a5e689470dc8931aadac4ebd664a7fdc6a9459641dd9d9f4a5c871730",
}
MATRIX_SHA = {
    "historical": "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",
    "b0001": "0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_series(label: str, frozen: Path, extra_root: Path) -> pd.DataFrame:
    if digest(frozen) != FROZEN_SUMMARY_SHA[label]:
        raise ValueError(f"{label}: original 10–40 curve evidence was modified")
    manifest = json.loads((extra_root / "manifest.json").read_text())
    if (
        manifest.get("matrix_sha256") != MATRIX_SHA[label]
        or tuple(manifest.get("new_budgets_only", ())) != NEW_BUDGETS
        or tuple(manifest.get("existing_budgets_untouched", ())) != (10, 15, 20, 30, 40)
    ):
        raise ValueError(f"{label}: new policy run does not match approved inputs")
    for name in ("baseline/budget_summary.csv", "kg/kg_budget_summary.csv",
                 "controlled/controlled_budget_summary.csv"):
        if digest(extra_root / name) != manifest["file_sha256"][name]:
            raise ValueError(f"{label}: extension summary has changed: {name}")
    old = pd.read_csv(frozen)
    new = pd.concat([
        pd.read_csv(extra_root / "baseline/budget_summary.csv"),
        pd.read_csv(extra_root / "kg/kg_budget_summary.csv"),
        pd.read_csv(extra_root / "controlled/controlled_budget_summary.csv"),
    ], ignore_index=True)
    if (
        len(old) != 45 or len(new) != 72
        or set(old.budget) != set(BUDGETS) - set(NEW_BUDGETS)
        or set(new.budget) != set(NEW_BUDGETS)
    ):
        raise ValueError("Expected frozen five budgets plus precisely eight new budgets")
    full = pd.concat([old, new], ignore_index=True)
    full["budget"] = full["budget"].astype(int)
    if full.duplicated(["policy", "budget"]).any() or len(full) != 117:
        raise ValueError("Expected 9 distinct policies at each of 13 budgets")
    for policy in frozen_plot.REFERENCE:
        rows = full[full.policy == policy].sort_values("budget")
        if rows.budget.tolist() != list(BUDGETS) or not (rows.episodes == 240).all():
            raise ValueError("Missing episode budget for " + policy)
    vals = full[["mean_regret", "regret_low", "regret_high"]].to_numpy(float)
    if (
        not np.isfinite(vals).all() or (vals[:, 1] > vals[:, 0]).any()
        or (vals[:, 0] > vals[:, 2]).any() or (vals[:, 1] < -1e-12).any()
    ):
        raise ValueError("Invalid bootstrap uncertainty or negative regret")
    return full


def draw(ax, data: pd.DataFrame, title: str, ymax: float, legend: bool) -> None:
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, policy in enumerate(frozen_plot.REFERENCE):
        frame = data[data.policy == policy].sort_values("budget")
        y = frame.mean_regret.to_numpy(float)
        err = np.vstack((
            y - frame.regret_low.to_numpy(float),
            frame.regret_high.to_numpy(float) - y,
        ))
        color = (
            colors[0] if policy.startswith("kg_")
            else colors[1] if policy.startswith("top2_") or policy == "budgeted_top2"
            else colors[2 + i % 5]
        )
        style = (
            "--" if policy.endswith("_uniform")
            else ":" if policy in ("kg_one_step", "budgeted_top2")
            else "-"
        )
        ax.errorbar(
            frame.budget, y, yerr=err, linestyle=style, marker=MARKERS[i],
            color=color, markersize=4.5, capsize=2.5, linewidth=1.7,
            label=frozen_plot.LABELS[policy],
        )
    ax.set(
        title=title, xlim=(8, 82), ylim=(0, ymax), xticks=BUDGETS,
        xlabel="Evaluation budget (distinct predictor–condition measurements)",
        ylabel="Mean terminal simple regret (MAE units; lower is better)",
    )
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="y", alpha=.25)
    if legend:
        ax.legend(fontsize=8.2, loc="upper right")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historical-frozen", required=True, type=Path)
    p.add_argument("--b0001-frozen", required=True, type=Path)
    p.add_argument("--historical-extra", required=True, type=Path)
    p.add_argument("--b0001-extra", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError(f"Refusing to overwrite plots: {a.out}")
    sources = {
        "historical_frozen": a.historical_frozen.resolve(),
        "b0001_frozen": a.b0001_frozen.resolve(),
    }
    for label, root in [("historical", a.historical_extra), ("b0001", a.b0001_extra)]:
        for rel in ("baseline/budget_summary.csv", "kg/kg_budget_summary.csv",
                    "controlled/controlled_budget_summary.csv", "manifest.json"):
            sources[f"{label}_extra_{rel}"] = (root / rel).resolve()
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)

    series = {
        "historical": load_series("historical", a.historical_frozen, a.historical_extra),
        "b0001": load_series("b0001", a.b0001_frozen, a.b0001_extra),
    }
    all_high = max(float(v.regret_high.max()) for v in series.values())
    # One bound computed from both archives and applied to every figure.
    ymax = max(.024, math.ceil(all_high * 1.05 / .005) * .005)
    out = a.out.resolve()
    out.mkdir(parents=True)
    images = []
    for label, data in series.items():
        path = out / f"{label}_nine_policy_13_budget_regret.csv"
        data.sort_values(["policy", "budget"]).to_csv(path, index=False, lineterminator="\n")
        fig, ax = plt.subplots(figsize=(13.1, 7.2), layout="constrained")
        draw(ax, data, f"{label.capitalize()}: nine-policy regret versus budget",
             ymax, True)
        fig.text(
            .5, -.013,
            "95% stratified episode bootstrap (2,000 draws); conditional on this archive. "
            "Dotted original joint policies are not matched condition-choice controls.",
            ha="center", va="top", fontsize=8,
        )
        for ext in ("png", "svg", "pdf"):
            dest = out / f"{label}_nine_policy_13_budget_regret.{ext}"
            fig.savefig(dest, dpi=220, bbox_inches="tight", pad_inches=.16)
            images.append(dest)
        plt.close(fig)

    fig, (a_hist, a_b0001) = plt.subplots(
        1, 2, figsize=(22.5, 7.7), layout="constrained", sharey=True
    )
    draw(a_hist, series["historical"], "Historical archive", ymax, False)
    draw(a_b0001, series["b0001"], "Independent B0001 reference", ymax, False)
    a_b0001.set_ylabel("")
    handles, labels = a_hist.get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=5, fontsize=9)
    for ext in ("png", "svg", "pdf"):
        dest = out / f"historical_vs_b0001_nine_policy_shared_y_13_budget.{ext}"
        fig.savefig(dest, dpi=220, bbox_inches="tight", pad_inches=.12)
        images.append(dest)
    plt.close(fig)

    manifest = {
        "status": "B1_HISTORICAL_AND_B0001_NINE_POLICY_13_BUDGET_COMMON_AXIS_PASS",
        "budgets": BUDGETS,
        "shared_ymin": 0.0, "shared_ymax": ymax,
        "highest_observed_95pct_regret_bound": all_high,
        "policies": frozen_plot.REFERENCE, "per_policy_budget_episodes": 240,
        "bootstrap_draws": 2000,
        "old_five_budget_plots_reused_without_replay": True,
        "new_policy_datasets_from_original_episode_implementations": True,
        "no_new_simulations": True,
        "source_sha256": {name: digest(path) for name, path in sources.items()},
        "output_sha256": {
            path.name: digest(path)
            for path in sorted(out.iterdir()) if path.is_file()
        },
    }
    (out / "plot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        "B1_13_BUDGET_NINE_POLICY_SHARED_Y_PASS",
        "Y_RANGE", (0.0, ymax), "POINTS", 117, "PER_DATASET",
        "OUTPUT", out,
    )


if __name__ == "__main__":
    main()
