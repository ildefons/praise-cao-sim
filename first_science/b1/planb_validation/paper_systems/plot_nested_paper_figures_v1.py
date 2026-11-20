#!/usr/bin/env python3
"""Render the manuscript's two nine-policy figures from frozen summary CSVs.

There is no access to raw terminal episodes, no posterior update, and no
acquisition/policy execution. All plotted quantities are read from committed
summary rows with known provenance and checked against the paper's contrasts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import plot_b1_nested_with_frozen_top2_v1 as plotting  # noqa: E402


SOURCE = HERE / "data/combined_nine_policy_budget_summary.csv"
SOURCE_MANIFEST = HERE / "data/nested_six_plus_frozen_top2_plot_manifest.json"
ADAPTIVITY = HERE / "data/kg_condition_adaptivity_aggregate_contrasts.csv"
ADAPTIVITY_MANIFEST = HERE / "data/kg_condition_adaptivity_manifest.json"
TOP2_CONTRASTS = {
    "fresh_reference": HERE / "data/kg_vs_top2_fresh_aggregate_contrasts.csv",
    "historical": HERE / "data/kg_vs_top2_historical_aggregate_contrasts.csv",
}
TOP2_MANIFESTS = {
    "fresh_reference": HERE / "data/kg_vs_top2_fresh_manifest.json",
    "historical": HERE / "data/kg_vs_top2_historical_manifest.json",
}
YMAX = {"historical": .025, "fresh_reference": .012}
FIGURE_NAMES = {
    "historical": "historical_nested6_plus_top2_13_budgets.pdf",
    "fresh_reference": "fresh_reference_nested6_plus_top2_13_budgets.pdf",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def checked_sources() -> dict[str, list[dict]]:
    """Reconcile figure source, policy types, and both statistical ledgers."""
    source_manifest = json.loads(SOURCE_MANIFEST.read_text())
    if (source_manifest.get("status") != "B1_NESTED6_PLUS_FROZEN_TOP2_FIGURES_V1_PASS"
            or source_manifest.get("output_sha256", {}).get(SOURCE.name) != digest(SOURCE)
            or tuple(source_manifest.get("budgets", ())) != plotting.BUDGETS
            or tuple(source_manifest.get("nested_policies", ())) != plotting.NESTED
            or tuple(source_manifest.get("budget_specific_frozen_policies", ())) != plotting.TOP2):
        raise ValueError("Manuscript figure source manifest/hash/policy design mismatch")

    all_rows = plotting.csv_rows(SOURCE)
    if len(all_rows) != len(plotting.ARCHIVES) * len(plotting.POLICIES) * len(plotting.BUDGETS):
        raise ValueError("Expected 234 nine-policy summary rows")
    selected = {}
    means = {}
    for archive in plotting.ARCHIVES:
        rows = [r for r in all_rows if r["archive"] == archive]
        validated = plotting.validated_rows(rows, "paper figure", plotting.POLICIES, archive)
        # csv.DictReader keeps numeric keys as strings; validated_rows
        # normalizes budget to int. Reconcile using the same typed key.
        by_key = {(r["policy"], int(r["budget"])): r for r in rows}
        for row in validated:
            kind = ("nested_80_step_prefix" if row["policy"] in plotting.NESTED
                    else "budget_specific_frozen")
            if by_key[row["policy"], row["budget"]]["source_design"] != kind:
                raise ValueError("A budget-specific policy is incorrectly labeled as nested")
        selected[archive] = validated
        means[archive] = {p: sum(x["mean_regret"] for x in validated if x["policy"] == p)
                          / len(plotting.BUDGETS) for p in plotting.POLICIES}

    adapt_manifest = json.loads(ADAPTIVITY_MANIFEST.read_text())
    if (adapt_manifest.get("status") != "B1_NESTED_KG_CONDITION_ADAPTIVITY_INFERENCE_V1_PASS"
            or digest(ADAPTIVITY) != adapt_manifest.get("output_sha256", {}).get(ADAPTIVITY.name)
            or adapt_manifest.get("source_nested_summary_sha256")
            != source_manifest.get("source_sha256", {}).get("nested_budget_summary.csv")):
        raise ValueError("Adaptivity inference source does not match the plotted nested replay")
    adapt_rows = plotting.csv_rows(ADAPTIVITY)
    adapt_primary = [r for r in adapt_rows if r["budget_set"] == "MEAN_OVER_13_BUDGETS"]
    if len(adapt_primary) != len(plotting.ARCHIVES):
        raise ValueError("Expected one primary adaptive-vs-uniform contrast per archive")
    for row in adapt_primary:
        archive = row["archive"]
        expected = means[archive]["kg_two_stage_adaptive"] - means[archive]["kg_two_stage_uniform"]
        if abs(float(row["mean_regret_diff"]) - expected) > 1e-12:
            raise ValueError("Adaptive KG aggregate does not reconcile with figure")

    for archive, path in TOP2_CONTRASTS.items():
        manifest = json.loads(TOP2_MANIFESTS[archive].read_text())
        if (manifest.get("status") != "B1_NESTED_ADAPTIVE_KG_VS_FROZEN_TOP2_INFERENCE_V1_PASS"
                or digest(path) != manifest.get("output_sha256", {}).get("cross_design_aggregate_contrasts.csv")
                or manifest.get("nested_terminal_sha256")
                != adapt_manifest.get("source_nested_terminal_sha256")):
            raise ValueError(f"{archive}: Top2 inference provenance/hash mismatch")
        primary = [r for r in plotting.csv_rows(path)
                   if r["budget_set"] == "MEAN_OVER_13_BUDGETS"]
        if len(primary) != len(plotting.TOP2):
            raise ValueError(f"{archive}: expected all three Top2 primary contrasts")
        seen = set()
        for row in primary:
            opponent = row["contrast"].split(" minus ")
            if (len(opponent) != 2 or opponent[0] != "kg_two_stage_adaptive"
                    or opponent[1] not in plotting.TOP2 or opponent[1] in seen):
                raise ValueError(f"{archive}: invalid or duplicate Top2 comparison")
            seen.add(opponent[1])
            expected = means[archive]["kg_two_stage_adaptive"] - means[archive][opponent[1]]
            if abs(float(row["mean_regret_diff"]) - expected) > 1e-12:
                raise ValueError(f"{archive}: Top2 contrast does not reconcile with figure")
    return selected


def render(archive: str, rows: list[dict]) -> Path:
    import matplotlib.pyplot as plt

    ymax = plotting.axis_max(rows, YMAX[archive])
    if ymax > YMAX[archive] + 1e-12:
        raise ValueError(f"{archive}: planned paper axis would clip an interval")
    fig, ax = plt.subplots(figsize=(12.4, 7.2))
    plotting.draw(ax, rows, archive, ymax, legend=True)
    fig.subplots_adjust(left=.09, right=.98, top=.92, bottom=.27)
    target = HERE / "figures" / FIGURE_NAMES[archive]
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=220, bbox_inches="tight", pad_inches=.12)
    plt.close(fig)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    series = checked_sources()
    for archive in plotting.ARCHIVES:
        print(f"PAPER_FIGURE_INPUT_OK {archive} nine_policies=YES "
              "budgets=13 statistical_contrasts_reconciled=YES", flush=True)
    if args.preflight_only:
        print("PAPER_FIGURE_PREFLIGHT_PASS no files written")
        return
    for archive, rows in series.items():
        print(f"PAPER_FIGURE_RENDERED {archive} {render(archive, rows)}", flush=True)
    print("PAPER_FIGURES_PASS no episodes or statistical resamples executed")


if __name__ == "__main__":
    main()
