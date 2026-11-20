#!/usr/bin/env python3
"""Overlay six nested B1 policies with three FROZEN budget-specific Top2 policies.

Reads existing summary CSVs. Does not run acquisitions, bootstrap, white-box
simulations, or modify the earlier policy/paper results. The three Top2
policies are NOT relabeled as nested: they have different B-dependent schedules.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BUDGETS = (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80)
NESTED = (
    "random", "balanced", "informed", "kg_one_step",
    "kg_two_stage_adaptive", "kg_two_stage_uniform",
)
TOP2 = ("budgeted_top2", "top2_two_stage_adaptive", "top2_two_stage_uniform")
POLICIES = NESTED + TOP2
ARCHIVES = ("historical", "fresh_reference")
OLD_ARCHIVE = {"historical": "historical", "fresh_reference": "b0001"}
EXPECTED_FROZEN_FIVE_BUDGET_SHA = {
    "historical": "e0c1e58ce733a07063153357a81094c663001537cb083fa64e5c0d6335343572",
    "b0001": "4a36235a5e689470dc8931aadac4ebd664a7fdc6a9459641dd9d9f4a5c871730",
}
EXPECTED_MATRIX_SHA = {
    "historical": "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",
    "fresh_reference": "5c81f50af9fad98596f0eac17ec3e9afc7848661acf476740af48663119606a3",
}
EXPECTED_ORIGINAL_B0001_SOURCE_SHA = (
    "0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b"
)
FIELDS = (
    "archive", "budget", "policy", "source_design", "episodes", "mean_regret",
    "regret_low", "regret_high", "p_correct", "p_low", "p_high", "regret_p90",
)
STYLES = {
    "random": ("Random", "#64748b", "o", "-"),
    "balanced": ("Balanced", "#059669", "s", "-"),
    "informed": ("Informed", "#9333ea", "^", "-"),
    "kg_one_step": ("KG: joint", "#2563eb", "D", ":"),
    "kg_two_stage_adaptive": ("KG: two-stage adaptive", "#2563eb", "v", "-"),
    "kg_two_stage_uniform": ("KG: two-stage uniform", "#2563eb", "P", "--"),
    "budgeted_top2": ("Top2: joint (B-specific)", "#ea580c", "X", ":"),
    "top2_two_stage_adaptive": ("Top2: two-stage adaptive (B-specific)", "#ea580c", "h", "-"),
    "top2_two_stage_uniform": ("Top2: two-stage uniform (B-specific)", "#ea580c", "*", "--"),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as inp:
        return list(csv.DictReader(inp))


def validated_rows(rows: list[dict], label: str, policies: tuple[str, ...],
                   archive: str) -> list[dict]:
    """Reject incomplete, duplicated, invalid, or mismatched source curves."""
    expected = {(p, b) for p in policies for b in BUDGETS}
    if len(rows) != len(expected):
        raise ValueError(f"{label}: expected exactly {len(expected)} rows, got {len(rows)}")
    keyed = {}
    for raw in rows:
        policy = raw["policy"]
        budget = int(raw["budget"])
        key = (policy, budget)
        if key not in expected or key in keyed or int(raw["episodes"]) != 240:
            raise ValueError(f"{label}: invalid policy, budget, episode count, or duplicate: {key}")
        if "archive" in raw and raw["archive"] != archive:
            raise ValueError(f"{label}: source archive differs from expected {archive}")
        values = {name: float(raw[name]) for name in (
            "mean_regret", "regret_low", "regret_high", "p_correct", "p_low",
            "p_high", "regret_p90",
        )}
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError(f"{label}: nonfinite metric for {key}")
        if not (0 <= values["regret_low"] <= values["mean_regret"] <= values["regret_high"]
                and values["regret_p90"] >= 0
                and 0 <= values["p_low"] <= values["p_correct"] <= values["p_high"] <= 1):
            raise ValueError(f"{label}: incompatible point estimate or 95% interval for {key}")
        keyed[key] = dict(archive=archive, policy=policy, budget=budget,
                          episodes=240, **values)
    if set(keyed) != expected:
        raise ValueError(f"{label}: missing policy/budget combinations")
    return [keyed[p, b] for p in policies for b in BUDGETS]


def combine(nested_rows: list[dict], old_rows: list[dict], archive: str) -> list[dict]:
    """Keep all six nested rows; import only the three B-specific Top2 rows."""
    n = validated_rows(nested_rows, "nested", NESTED, archive)
    t = validated_rows(old_rows, "archived Top2", TOP2, archive)
    for row in n:
        row["source_design"] = "nested_80_step_prefix"
    for row in t:
        row["source_design"] = "budget_specific_frozen"
    return sorted(n + t, key=lambda r: (r["budget"], POLICIES.index(r["policy"])))


def load_checked_sources(nested_dir: Path, original_dir: Path, repo: Path):
    nested_manifest_path = nested_dir / "nested_manifest.json"
    if not (original_dir / "plot_manifest.json").is_file() and (original_dir.parent / "plot_manifest.json").is_file():
        # Also accept the tables/ subdirectory as the user-supplied location.
        original_dir = original_dir.parent
    original_manifest_path = original_dir / "plot_manifest.json"
    nm = json.loads(nested_manifest_path.read_text())
    om = json.loads(original_manifest_path.read_text())
    if (nm.get("status") != "B1_NESTED_BUDGET_REPLAY_V1_COMPLETE"
            or tuple(nm.get("budgets", ())) != BUDGETS
            or tuple(nm.get("policies", ())) != NESTED
            or nm.get("budget_in_seed") is not False
            or nm.get("repeats_per_start") != 20):
        raise ValueError("Unexpected nested replay design or status")
    if (om.get("status") != "B1_HISTORICAL_AND_B0001_NINE_POLICY_13_BUDGET_COMMON_AXIS_PASS"
            or tuple(om.get("budgets", ())) != BUDGETS
            or set(om.get("policies", ())) != set(POLICIES)
            or om.get("per_policy_budget_episodes") != 240
            or om.get("bootstrap_draws") != 2000):
        raise ValueError("Unexpected original nine-policy figure provenance")
    # The frozen B0001 source matrix (035...) is the source recorded by the
    # five-budget baseline run that exported the CSV (5c81...) used by nested.
    # This provenance bridge is audited rather than assuming equal data from
    # archive names or comparing unrelated CSV hashes.
    b0001_baseline = repo / "results/b0001_original_policies_v1/01_baseline/run_manifest.json"
    baseline = json.loads(b0001_baseline.read_text())
    if (baseline.get("inputs_sha256", {}).get("B0001_new_reference")
            != EXPECTED_ORIGINAL_B0001_SOURCE_SHA
            or baseline.get("outputs_sha256", {}).get("seven_method_matrix.csv")
            != EXPECTED_MATRIX_SHA["fresh_reference"]):
        raise ValueError("Cannot reconcile the source/export B0001 matrix hashes")
    files, combined = {}, {}
    for archive in ARCHIVES:
        old_label = OLD_ARCHIVE[archive]
        if nm.get("archive_sources", {}).get(archive, {}).get("sha256") != EXPECTED_MATRIX_SHA[archive]:
            raise ValueError(f"{archive}: nested matrix is not the frozen matrix")
        npath = nested_dir / "nested_budget_summary.csv"
        filename = f"{old_label}_nine_policy_13_budget_regret.csv"
        opath = original_dir / filename
        if not opath.is_file():
            # The tracked archive stores plot data in tables/ while retaining
            # plot_manifest.json at the archive root. Original hashes remain
            # valid because the CSV contents were not modified during archiving.
            opath = original_dir / "tables" / filename
        if digest(npath) != nm["outputs_sha256"][npath.name]:
            raise ValueError("Nested budget summary checksum mismatch")
        if digest(opath) != om["output_sha256"][opath.name]:
            raise ValueError(f"{archive}: original nine-policy CSV checksum mismatch")
        if om.get("source_sha256", {}).get(f"{old_label}_frozen") != EXPECTED_FROZEN_FIVE_BUDGET_SHA[old_label]:
            raise ValueError(f"{archive}: original five-budget source changed")
        n = [r for r in csv_rows(npath) if r.get("archive") == archive]
        old = [r for r in csv_rows(opath) if r.get("policy") in TOP2]
        combined[archive] = combine(n, old, archive)
        files[npath.name] = npath
        files[opath.name] = opath
    files["nested_manifest.json"] = nested_manifest_path
    files["original_plot_manifest.json"] = original_manifest_path
    files["b0001_baseline_run_manifest.json"] = b0001_baseline
    return combined, files


def axis_max(rows: list[dict], requested: float) -> float:
    """Prefer the requested limits but never crop a reported 95% upper bound."""
    high = max(row["regret_high"] for row in rows)
    if requested <= 0:
        raise ValueError("Requested y-axis maximum must be positive")
    return max(requested, math.ceil(high * 1.02 / .001) * .001)


def draw(ax, rows: list[dict], archive: str, ymax: float, legend: bool = True) -> None:
    for policy in POLICIES:
        frame = sorted((row for row in rows if row["policy"] == policy),
                       key=lambda r: r["budget"])
        if len(frame) != len(BUDGETS):
            raise ValueError(f"No complete 13-budget trajectory for {policy}")
        label, color, marker, line = STYLES[policy]
        y = [row["mean_regret"] for row in frame]
        low = [row["mean_regret"] - row["regret_low"] for row in frame]
        high = [row["regret_high"] - row["mean_regret"] for row in frame]
        ax.errorbar(
            [row["budget"] for row in frame], y, yerr=(low, high),
            color=color, linestyle=line, marker=marker,
            markersize=4.4, linewidth=1.65, elinewidth=.85, capsize=2,
            alpha=.88, label=label,
        )
    ax.set_xlim(8, 82)
    ax.set_ylim(0, ymax)
    ax.set_xticks(BUDGETS)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel("Validation budget (distinct method–condition evaluations)")
    ax.set_ylabel("Mean terminal simple regret (MAE; lower is better)")
    ax.set_title("Historical archive" if archive == "historical" else "Fresh-reference archive")
    ax.grid(axis="y", alpha=.24)
    if legend:
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.16), ncol=3,
                  fontsize=8, frameon=False, columnspacing=1.8)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_all(series: dict, out: Path, ymax: dict) -> None:
    for archive in ARCHIVES:
        fig, ax = plt.subplots(figsize=(12.4, 7.2))
        draw(ax, series[archive], archive, ymax[archive], legend=True)
        fig.subplots_adjust(left=.09, right=.98, top=.92, bottom=.27)
        for ext in ("pdf", "png", "svg"):
            fig.savefig(out / f"{archive}_nested6_plus_top2_13_budgets.{ext}",
                        dpi=220, bbox_inches="tight", pad_inches=.12)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nested-dir", required=True, type=Path)
    parser.add_argument("--original-nine-dir", type=Path,
                        default=Path(__file__).resolve().parent
                        / "results/b1_nine_policy_13_budget_extension_v1",
                        help="Original nine-policy archive; defaults to the tracked results directory")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--historical-ymax", type=float, default=.025)
    parser.add_argument("--fresh-ymax", type=float, default=.012)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent
    nested_dir = args.nested_dir.expanduser().resolve()
    original_dir = args.original_nine_dir.expanduser().resolve()
    series, sources = load_checked_sources(nested_dir, original_dir, repo)
    ymax = {
        "historical": axis_max(series["historical"], args.historical_ymax),
        "fresh_reference": axis_max(series["fresh_reference"], args.fresh_ymax),
    }
    for archive in ARCHIVES:
        assert len(series[archive]) == 9 * len(BUDGETS)
        print(f"TOP2_OVERLAY_INPUT_OK {archive} nested=78 frozen_top2=39 "
              f"ymax={ymax[archive]:.4f}", flush=True)
    if args.preflight_only:
        print("TOP2_OVERLAY_PREFLIGHT_PASS no outputs written")
        return
    if args.out is None:
        parser.error("--out is required unless --preflight-only")
    out = args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing figure directory: {out}")
    out.mkdir(parents=True, exist_ok=False)
    all_rows = []
    for archive in ARCHIVES:
        all_rows.extend(series[archive])
    write_csv(out / "combined_nine_policy_budget_summary.csv", all_rows)
    plot_all(series, out, ymax)
    manifest = dict(
        status="B1_NESTED6_PLUS_FROZEN_TOP2_FIGURES_V1_PASS",
        budgets=BUDGETS, policies=POLICIES, archives=ARCHIVES,
        nested_policies=NESTED, budget_specific_frozen_policies=TOP2,
        mean_regret_and_95pct_intervals_from_original_summaries=True,
        no_policy_replay=True, no_bootstrap_rerun=True,
        no_simulation=True, no_paper_changes=True,
        y_axis_limits=ymax,
        source_sha256={name: digest(path) for name, path in sources.items()},
        output_sha256={p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()},
        interpretation=("Six curves use B-independent nested histories. Three Top2 "
                        "curves reuse original B-dependent episodes. Error bars are "
                        "archive-conditional 95% bootstrap intervals; cross-design "
                        "pairs have not been tested for significance here."),
    )
    (out / "plot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"B1_NESTED6_FROZEN_TOP2_FIGURES_PASS {out}", flush=True)


if __name__ == "__main__":
    main()
