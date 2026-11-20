#!/usr/bin/env python3
"""Read-only cross-design inference: nested adaptive KG versus frozen Top2.

Each of 12 fixed starting conditions has 20 randomized episodes per policy.
Bootstrap the adaptive KG *same replicate indices across all budgets* (its
histories are nested). Bootstrap each budget-specific Top2 policy and budget
independently. Resampling of KG and Top2 is independent, not artificially
paired by a replicate number shared only by the CSV column names.

Tests all three Top2 variants with Bonferroni familywise intervals. Both the
13-budget average and the more informative 10..40 subset are reported, with
the latter explicitly exploratory. No acquisitions or simulators are run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import derive_b1_thirteen_budget_paired_contrasts_v1 as archived


BUDGETS = (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80)
OLD_BUDGETS = (10, 15, 20, 30, 40)
NEW_BUDGETS = (25, 35, 45, 55, 65, 70, 75, 80)
KG = "kg_two_stage_adaptive"
TOP2 = ("budgeted_top2", "top2_two_stage_adaptive", "top2_two_stage_uniform")
ARCHIVES = ("fresh_reference", "historical")
NSTART, REPEATS = 12, 20
BOOTSTRAPS, SEED = 10000, 20261120
AGGREGATIONS = (
    ("MEAN_OVER_13_BUDGETS", BUDGETS),
    ("MEAN_OVER_10_TO_40", (10, 15, 20, 25, 30, 35, 40)),
)
EXPECTED_MATRIX_SHA = {
    "fresh_reference": "5c81f50af9fad98596f0eac17ec3e9afc7848661acf476740af48663119606a3",
    "historical": "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",
}
EPISODE_FIELDS = ("budget", "start_index", "replicate", "policy", "simple_regret", "correct")
BY_BUDGET_FIELDS = (
    "archive", "budget", "contrast", "episodes_per_policy", "mean_regret_diff",
    "low95", "high95", "bootstrap_draws",
)
AGGREGATE_FIELDS = (
    "archive", "budget_set", "contrast", "mean_regret_diff", "low95", "high95",
    "low_familywise95", "high_familywise95", "family_size", "bootstrap_draws",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as src:
        return list(csv.DictReader(src))


def normalize_rows(rows: list[dict], policies: tuple[str, ...],
                   budgets: tuple[int, ...], label: str) -> list[dict]:
    """Every policy/budget/start/replicate exactly once, with finite regret."""
    expected = len(policies) * len(budgets) * NSTART * REPEATS
    if len(rows) != expected:
        raise ValueError(f"{label}: expected {expected} episodes, got {len(rows)}")
    seen = set()
    result = []
    for raw in rows:
        row = dict(
            policy=raw["policy"], budget=int(raw["budget"]),
            start_index=int(raw["start_index"]), replicate=int(raw["replicate"]),
            simple_regret=float(raw["simple_regret"]), correct=int(raw["correct"]),
        )
        key = (row["policy"], row["budget"], row["start_index"], row["replicate"])
        if (row["policy"] not in policies or row["budget"] not in budgets
                or not 0 <= row["start_index"] < NSTART
                or not 0 <= row["replicate"] < REPEATS
                or row["correct"] not in (0, 1)
                or not math.isfinite(row["simple_regret"])
                or row["simple_regret"] < 0 or key in seen):
            raise ValueError(f"{label}: invalid or duplicate episode: {key}")
        seen.add(key)
        result.append(row)
    return result


def matrix_by_budget(rows: list[dict], policy: str) -> dict[int, np.ndarray]:
    out = {b: np.full((NSTART, REPEATS), np.nan) for b in BUDGETS}
    for row in rows:
        if row["policy"] != policy:
            continue
        b, s, rep = row["budget"], row["start_index"], row["replicate"]
        if math.isfinite(out[b][s, rep]):
            raise ValueError("Duplicate policy/budget/start/replicate")
        out[b][s, rep] = row["simple_regret"]
    if not all(np.isfinite(x).all() for x in out.values()):
        raise ValueError(f"Missing terminal outcomes for {policy}")
    return out


def check_against_frozen_summary(rows: list[dict], archive: str, root: Path) -> None:
    label = "b0001" if archive == "fresh_reference" else "historical"
    path = root / f"results/b1_nine_policy_13_budget_extension_v1/tables/{label}_nine_policy_13_budget_regret.csv"
    archived_means = {(r["policy"], int(r["budget"])): float(r["mean_regret"])
                      for r in read_csv(path) if r["policy"] in TOP2}
    if len(archived_means) != len(TOP2) * len(BUDGETS):
        raise ValueError("Archived Top2 plot table incomplete")
    for policy in TOP2:
        mat = matrix_by_budget(rows, policy)
        for budget in BUDGETS:
            if abs(float(mat[budget].mean()) - archived_means[policy, budget]) > 1e-12:
                raise ValueError(f"{archive}: original Top2 episodes disagree with plotted mean for {policy}, B={budget}")


def load_nested(nested_dir: Path, archive: str) -> tuple[list[dict], dict]:
    manifest = json.loads((nested_dir / "nested_manifest.json").read_text())
    path = nested_dir / "nested_terminal_episodes.csv"
    if (manifest.get("status") != "B1_NESTED_BUDGET_REPLAY_V1_COMPLETE"
            or manifest.get("budget_in_seed") is not False
            or tuple(manifest.get("budgets", ())) != BUDGETS
            or manifest.get("repeats_per_start") != REPEATS
            or manifest.get("archive_sources", {}).get(archive, {}).get("sha256") != EXPECTED_MATRIX_SHA[archive]
            or digest(path) != manifest.get("outputs_sha256", {}).get(path.name)):
        raise ValueError("Nested source design or checksum did not pass")
    all_rows = [r for r in read_csv(path) if r["archive"] == archive and r["policy"] == KG]
    return normalize_rows(all_rows, (KG,), BUDGETS, f"nested {archive}"), manifest


def load_old_local(path: Path, expected_policies: tuple[str, ...],
                   expected_sha: str, label: str) -> list[dict]:
    if not path.is_file() or digest(path) != expected_sha:
        raise ValueError(f"{label}: original five-budget ledger absent or SHA mismatch: {path}")
    return normalize_rows(read_csv(path), expected_policies, OLD_BUDGETS, label)


def load_top2(archive: str, root: Path, historical_baseline: Path | None,
              historical_controlled: Path | None) -> tuple[list[dict], dict]:
    extension = root / "results/b1_nine_policy_13_budget_extension_v1"
    fresh = archive == "fresh_reference"
    new_zip = extension / ("b0001_eight_added_budgets_full_replay.zip" if fresh
                           else "historical_eight_added_budgets_full_replay.zip")
    provenance = {"new_eight_budget_zip": str(new_zip), "new_sha256": digest(new_zip)}
    if fresh:
        old_zip = root / "results/b0001_original_policies_v1/b0001_original_policy_replay_v1_complete.zip"
        source_manifest = json.loads((extension / "b0001_13_budget_contrast_manifest.json").read_text())
        if (digest(old_zip) != source_manifest["old_five_budget_archive_sha256"]
                or digest(new_zip) != source_manifest["new_eight_budget_archive_sha256"]):
            raise ValueError("Fresh-reference frozen episode ZIP checksums differ from published provenance")
        old_base = archived.read_terminal(old_zip, "baseline", OLD_BUDGETS)
        old_control = archived.read_terminal(old_zip, "controlled", OLD_BUDGETS)
        provenance.update(old_five_budget_zip=str(old_zip), old_sha256=digest(old_zip))
    else:
        if historical_baseline is None or historical_controlled is None:
            raise ValueError("Historical archive needs original five-budget baseline and controlled terminal CSVs")
        # The five-budget control ledger is frozen in the tracked manifest,
        # while the baseline is frozen by its original run manifest alongside it.
        bm = json.loads((historical_baseline.parent / "run_manifest.json").read_text())
        cm = json.loads((root / "results/controlled_condition_ablation_v1/controlled_manifest.json").read_text())
        old_base = load_old_local(
            historical_baseline,
            ("random", "balanced", "informed", "budgeted_top2"),
            bm["outputs_sha256"]["terminal_episodes.csv"], "historical baseline",
        )
        old_control = load_old_local(
            historical_controlled,
            ("kg_two_stage_adaptive", "kg_two_stage_uniform",
             "top2_two_stage_adaptive", "top2_two_stage_uniform"),
            cm["output_sha256"]["controlled_terminal_episodes.csv"],
            "historical two-stage controls",
        )
        provenance.update(
            old_historical_baseline=str(historical_baseline),
            old_historical_baseline_sha256=digest(historical_baseline),
            old_historical_controlled=str(historical_controlled),
            old_historical_controlled_sha256=digest(historical_controlled),
        )
    new_base = archived.read_terminal(new_zip, "baseline", NEW_BUDGETS)
    new_control = archived.read_terminal(new_zip, "controlled", NEW_BUDGETS)
    raw = [r for r in old_base + old_control + new_base + new_control
           if r["policy"] in TOP2]
    result = normalize_rows(raw, TOP2, BUDGETS, f"Top2 {archive}")
    check_against_frozen_summary(result, archive, root)
    return result, provenance


def stratified_bootstrap(arr: np.ndarray, draws: np.ndarray) -> np.ndarray:
    if arr.shape != (NSTART, REPEATS) or draws.ndim != 3 or draws.shape[1:] != arr.shape:
        raise ValueError("Need 12x20 regrets and bootstrap indices")
    return np.take_along_axis(arr[None, :, :], draws, axis=2).mean(axis=(1, 2))


def infer(nested_rows: list[dict], top2_rows: list[dict], archive: str,
          nboot: int, seed: int) -> tuple[list[dict], list[dict]]:
    """Independent policy RNG, common KG budget prefixes, separate Top2 budgets."""
    kg_mat = matrix_by_budget(nested_rows, KG)
    top2_mats = {p: matrix_by_budget(top2_rows, p) for p in TOP2}
    archive_id = ARCHIVES.index(archive)
    rng = np.random.default_rng(np.random.SeedSequence([seed, archive_id, 991]))
    # This draw is reused at *every* budget in each KG trajectory.
    kg_draws = rng.integers(REPEATS, size=(nboot, NSTART, REPEATS))
    kg_boot = {b: stratified_bootstrap(kg_mat[b], kg_draws) for b in BUDGETS}
    per_budget, aggregates = [], []
    for policy in TOP2:
        diff_boot = {}
        point = {}
        for budget in BUDGETS:
            # The old Top2 selector was seeded by B. It is NOT a nested path.
            separate_draws = rng.integers(REPEATS, size=(nboot, NSTART, REPEATS))
            other_boot = stratified_bootstrap(top2_mats[policy][budget], separate_draws)
            diff_boot[budget] = kg_boot[budget] - other_boot
            point[budget] = float((kg_mat[budget] - top2_mats[policy][budget]).mean())
            lo, hi = np.quantile(diff_boot[budget], (.025, .975))
            per_budget.append(dict(
                archive=archive, budget=budget, contrast=f"{KG} minus {policy}",
                episodes_per_policy=NSTART * REPEATS,
                mean_regret_diff=point[budget], low95=float(lo), high95=float(hi),
                bootstrap_draws=nboot,
            ))
        for label, budgets in AGGREGATIONS:
            draws = np.stack([diff_boot[b] for b in budgets], axis=1).mean(axis=1)
            mean_diff = float(np.mean([point[b] for b in budgets]))
            low95, high95 = np.quantile(draws, (.025, .975))
            # Bonferroni across all three Top2 variants within this archive.
            # Three 98.33% intervals form a >=95% simultaneous family.
            adjusted = .05 / len(TOP2)
            low_sim, high_sim = np.quantile(draws, (adjusted / 2, 1 - adjusted / 2))
            aggregates.append(dict(
                archive=archive, budget_set=label, contrast=f"{KG} minus {policy}",
                mean_regret_diff=mean_diff, low95=float(low95), high95=float(high95),
                low_familywise95=float(low_sim), high_familywise95=float(high_sim),
                family_size=len(TOP2), bootstrap_draws=nboot,
            ))
    return per_budget, aggregates


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]):
    with path.open("w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parent
    parser.add_argument("--archive", choices=("fresh_reference", "historical", "both"),
                        default="fresh_reference")
    parser.add_argument("--nested-dir", type=Path, default=Path.home()
                        / "praise/planb_b1_nested_budget_2026_11_20_v1")
    parser.add_argument("--historical-five-baseline", type=Path,
                        default=Path.home() / "praise/planb_b1_fixed_budget_v1/terminal_episodes.csv")
    parser.add_argument("--historical-five-controlled", type=Path,
                        help="Local 5-budget controlled_terminal_episodes.csv for historical archive")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.bootstrap < 1000 or args.seed < 0:
        parser.error("Use at least 1000 bootstrap draws and nonnegative seed")
    target_archives = ARCHIVES if args.archive == "both" else (args.archive,)
    nested_dir = args.nested_dir.expanduser().resolve()
    inputs, rows = {}, {}
    for archive in target_archives:
        n, nm = load_nested(nested_dir, archive)
        t, provenance = load_top2(
            archive, repo,
            args.historical_five_baseline.expanduser().resolve(),
            args.historical_five_controlled.expanduser().resolve()
            if args.historical_five_controlled else None,
        )
        rows[archive] = (n, t)
        inputs[archive] = provenance
        print(f"CROSS_DESIGN_INPUT_OK {archive} nested={len(n)} Top2={len(t)} "
              "all_13_budgets=YES plotted_means_match=YES", flush=True)
    if args.preflight_only:
        print("CROSS_DESIGN_PREFLIGHT_PASS no outputs written")
        return
    if args.out is None:
        parser.error("--out required unless --preflight-only")
    out = args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite earlier statistics: {out}")
    out.mkdir(parents=True, exist_ok=False)
    per_budget, aggregate = [], []
    for archive in target_archives:
        budget_rows, aggregate_rows = infer(*rows[archive], archive,
                                            args.bootstrap, args.seed)
        per_budget.extend(budget_rows)
        aggregate.extend(aggregate_rows)
    write_csv(out / "cross_design_budget_contrasts.csv", per_budget, BY_BUDGET_FIELDS)
    write_csv(out / "cross_design_aggregate_contrasts.csv", aggregate, AGGREGATE_FIELDS)
    manifest = dict(
        status="B1_NESTED_ADAPTIVE_KG_VS_FROZEN_TOP2_INFERENCE_V1_PASS",
        archives=target_archives, budgets=BUDGETS,
        primary_comparison=KG, competitors=TOP2,
        primary_aggregate="MEAN_OVER_13_BUDGETS",
        secondary_exploratory_aggregate="MEAN_OVER_10_TO_40",
        comparison_chosen_after_inspecting_previous_summary_curves=True,
        sampling="12 fixed initial conditions, independently resampled 20 repetitions per policy",
        kg_budget_resampling="same bootstrap replicate indices across all nested budget prefixes",
        top2_budget_resampling="independent replicate indices for each separate B-dependent episode",
        familywise_intervals="Bonferroni 95% coverage for three Top2 comparisons within each archive and budget aggregate",
        per_budget_intervals="nominal 95%; exploratory over 13 budgets",
        uncertainty_scope="acquisition randomization conditional on each frozen 7x12 archive",
        bootstrap_draws=args.bootstrap, seed=args.seed,
        input_sources=inputs,
        nested_terminal_sha256=digest(nested_dir / "nested_terminal_episodes.csv"),
        output_sha256={p.name: digest(p) for p in sorted(out.glob("*.csv"))},
        no_simulation=True, no_policy_replay=True, no_paper_changes=True,
    )
    (out / "cross_design_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for r in aggregate:
        if r["budget_set"] == "MEAN_OVER_13_BUDGETS":
            print("CROSS_DESIGN_AGGREGATE", r["archive"], r["contrast"],
                  f"difference={r['mean_regret_diff']:.6g}",
                  f"familywise95=[{r['low_familywise95']:.6g},{r['high_familywise95']:.6g}]",
                  flush=True)
    print(f"CROSS_DESIGN_INFERENCE_PASS {out}", flush=True)


if __name__ == "__main__":
    main()
