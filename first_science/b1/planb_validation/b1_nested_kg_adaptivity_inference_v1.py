#!/usr/bin/env python3
"""Read-only adaptive-versus-uniform two-stage KG inference on nested episodes.

The two policies have the same per-method Gaussian surrogate, first-stage
method selection, initial evidence, and terminal recommendation rule. They
differ in the second-stage choice of an unevaluated condition: highest KG
versus uniform. Their distinct policy-seeded RNG streams must not be paired
by an identically named replicate column.

One independent bootstrap index draw per policy is reused for all thirteen
budget checkpoints, preserving within-policy nested-trajectory dependence.
No acquisition function, simulator, or source episode is executed here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import b1_nested_kg_vs_frozen_top2_inference_v1 as common


ADAPTIVE = "kg_two_stage_adaptive"
UNIFORM = "kg_two_stage_uniform"
POLICIES = (ADAPTIVE, UNIFORM)
BUDGETS = common.BUDGETS
ARCHIVES = common.ARCHIVES
AGGREGATIONS = common.AGGREGATIONS
NSTART, REPEATS = common.NSTART, common.REPEATS
BOOTSTRAPS, SEED = 10000, 20261120

BUDGET_FIELDS = (
    "archive", "budget", "contrast", "episodes_per_policy",
    "mean_regret_adaptive", "mean_regret_uniform", "mean_regret_diff",
    "low95", "high95", "bootstrap_draws",
)
AGGREGATE_FIELDS = (
    "archive", "budget_set", "contrast", "mean_regret_adaptive",
    "mean_regret_uniform", "mean_regret_diff", "low95", "high95",
    "low_familywise95", "high_familywise95", "family_size",
    "bootstrap_draws",
)


def checked_input(nested_dir: Path) -> tuple[dict[str, list[dict]], dict]:
    """Read and reconcile the two unchanged nested policy ledgers."""
    manifest_path = nested_dir / "nested_manifest.json"
    terminals_path = nested_dir / "nested_terminal_episodes.csv"
    summary_path = nested_dir / "nested_budget_summary.csv"
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("status") != "B1_NESTED_BUDGET_REPLAY_V1_COMPLETE"
            or tuple(manifest.get("budgets", ())) != BUDGETS
            or manifest.get("budget_in_seed") is not False
            or manifest.get("archive_in_seed") is not False
            or manifest.get("repeats_per_start") != REPEATS
            or manifest.get("policy_seed_ids", {}).get(ADAPTIVE) != 4
            or manifest.get("policy_seed_ids", {}).get(UNIFORM) != 5
            or common.digest(terminals_path) != manifest.get("outputs_sha256", {}).get(terminals_path.name)
            or common.digest(summary_path) != manifest.get("outputs_sha256", {}).get(summary_path.name)):
        raise ValueError("Nested source protocol or file checksums did not pass")
    for archive in ARCHIVES:
        observed_sha = manifest.get("archive_sources", {}).get(archive, {}).get("sha256")
        if observed_sha != common.EXPECTED_MATRIX_SHA[archive]:
            raise ValueError(f"{archive}: incorrect fixed performance matrix provenance")

    raw = common.read_csv(terminals_path)
    expected_all = len(ARCHIVES) * len(manifest["policies"]) * len(BUDGETS) * NSTART * REPEATS
    if len(raw) != expected_all:
        raise ValueError("Unexpected nested terminal ledger size")
    means = {(r["archive"], r["policy"], int(r["budget"])): float(r["mean_regret"])
             for r in common.read_csv(summary_path)}
    result = {}
    for archive in ARCHIVES:
        selected = [r for r in raw if r["archive"] == archive and r["policy"] in POLICIES]
        selected = common.normalize_rows(selected, POLICIES, BUDGETS, f"nested KG {archive}")
        for policy in POLICIES:
            mat = common.matrix_by_budget(selected, policy)
            for budget in BUDGETS:
                key = (archive, policy, budget)
                if key not in means or abs(float(mat[budget].mean()) - means[key]) > 1e-12:
                    raise ValueError(f"Nested summary/episode mismatch at {key}")
        result[archive] = selected
    return result, manifest


def bootstrap_policy_path(matrices: dict[int, np.ndarray], draws: np.ndarray) -> dict[int, np.ndarray]:
    """Use one draw over (start, replicate) for all prefixes of a policy."""
    return {budget: common.stratified_bootstrap(matrices[budget], draws)
            for budget in BUDGETS}


def infer(rows: list[dict], archive: str, nboot: int, seed: int):
    """Independent policy streams; coherent within-policy budget resampling."""
    if archive not in ARCHIVES or nboot < 1000 or seed < 0:
        raise ValueError("Invalid archive or bootstrap configuration")
    matrices = {policy: common.matrix_by_budget(rows, policy) for policy in POLICIES}
    rng = np.random.default_rng(np.random.SeedSequence([seed, ARCHIVES.index(archive), 4702]))
    # Separate random streams for adaptive and uniform. Each stream is reused
    # across budgets only within its own nested 80-step trajectory.
    adaptive_draws = rng.integers(REPEATS, size=(nboot, NSTART, REPEATS))
    uniform_draws = rng.integers(REPEATS, size=(nboot, NSTART, REPEATS))
    if np.array_equal(adaptive_draws, uniform_draws):
        raise AssertionError("Expected independent policy bootstrap streams")
    adaptive_boot = bootstrap_policy_path(matrices[ADAPTIVE], adaptive_draws)
    uniform_boot = bootstrap_policy_path(matrices[UNIFORM], uniform_draws)

    point = {}
    boot = {}
    means_adaptive = {}
    means_uniform = {}
    by_budget = []
    contrast = f"{ADAPTIVE} minus {UNIFORM}"
    for budget in BUDGETS:
        means_adaptive[budget] = float(matrices[ADAPTIVE][budget].mean())
        means_uniform[budget] = float(matrices[UNIFORM][budget].mean())
        point[budget] = means_adaptive[budget] - means_uniform[budget]
        boot[budget] = adaptive_boot[budget] - uniform_boot[budget]
        lo, hi = np.quantile(boot[budget], (.025, .975))
        by_budget.append(dict(
            archive=archive, budget=budget, contrast=contrast,
            episodes_per_policy=NSTART * REPEATS,
            mean_regret_adaptive=means_adaptive[budget],
            mean_regret_uniform=means_uniform[budget],
            mean_regret_diff=point[budget], low95=float(lo), high95=float(hi),
            bootstrap_draws=nboot,
        ))

    aggregates = []
    for label, budgets in AGGREGATIONS:
        aggregate_boot = np.stack([boot[b] for b in budgets], axis=1).mean(axis=1)
        low, high = np.quantile(aggregate_boot, (.025, .975))
        # Simultaneous family across the two fixed reference archives for the
        # selected budget aggregate. The 10..40 analysis stays exploratory.
        low_f, high_f = np.quantile(aggregate_boot, (.0125, .9875))
        adaptive_mean = float(np.mean([means_adaptive[b] for b in budgets]))
        uniform_mean = float(np.mean([means_uniform[b] for b in budgets]))
        aggregates.append(dict(
            archive=archive, budget_set=label, contrast=contrast,
            mean_regret_adaptive=adaptive_mean,
            mean_regret_uniform=uniform_mean,
            mean_regret_diff=adaptive_mean - uniform_mean,
            low95=float(low), high95=float(high),
            low_familywise95=float(low_f), high_familywise95=float(high_f),
            family_size=len(ARCHIVES), bootstrap_draws=nboot,
        ))
    return by_budget, aggregates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nested-dir", type=Path,
                        default=Path.home() / "praise/planb_b1_nested_budget_2026_11_20_v1")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.bootstrap < 1000 or args.seed < 0:
        parser.error("Use at least 1000 bootstrap draws and a nonnegative seed")
    nested_dir = args.nested_dir.expanduser().resolve()
    inputs, source_manifest = checked_input(nested_dir)
    for archive in ARCHIVES:
        print(f"KG_ADAPTIVITY_INPUT_OK {archive} records={len(inputs[archive])} "
              "matched_nine_policy_nested_summary=YES budget_independent=YES", flush=True)
    if args.preflight_only:
        print("KG_ADAPTIVITY_PREFLIGHT_PASS no outputs written")
        return
    if args.out is None:
        parser.error("--out required unless --preflight-only")
    out = args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite previous analysis: {out}")
    out.mkdir(parents=True, exist_ok=False)
    budget_rows, aggregate_rows = [], []
    for archive in ARCHIVES:
        b, a = infer(inputs[archive], archive, args.bootstrap, args.seed)
        budget_rows.extend(b)
        aggregate_rows.extend(a)
    budget_file = out / "kg_condition_adaptivity_budget_contrasts.csv"
    aggregate_file = out / "kg_condition_adaptivity_aggregate_contrasts.csv"
    common.write_csv(budget_file, budget_rows, BUDGET_FIELDS)
    common.write_csv(aggregate_file, aggregate_rows, AGGREGATE_FIELDS)
    manifest = dict(
        status="B1_NESTED_KG_CONDITION_ADAPTIVITY_INFERENCE_V1_PASS",
        objective="two-stage adaptive KG minus two-stage uniform KG; negative favors adaptive",
        archives=ARCHIVES, primary_budget_set="MEAN_OVER_13_BUDGETS",
        exploratory_budget_set="MEAN_OVER_10_TO_40", budgets=BUDGETS,
        source_policies=POLICIES,
        policy_difference="maximum-KG versus uniform remaining-condition choice after identical first-stage method-selection rule",
        policy_streams="different fixed policy IDs; independently resampled; matched initial-condition strata",
        within_policy_dependence="one bootstrap index array reused across all 13 budget prefixes of each policy",
        familywise_intervals="Bonferroni 95% simultaneous coverage across the two archive-specific contrasts within each budget set",
        per_budget_intervals="nominal 95%, exploratory across 13 budgets",
        inference_scope="acquisition randomness conditional on two fixed 7x12 reference matrices",
        analysis_chosen_after_inspecting_previous_policy_curves=True,
        bootstrap_draws=args.bootstrap, seed=args.seed,
        source_nested_manifest_status=source_manifest["status"],
        source_nested_terminal_sha256=common.digest(nested_dir / "nested_terminal_episodes.csv"),
        source_nested_summary_sha256=common.digest(nested_dir / "nested_budget_summary.csv"),
        source_nested_manifest_sha256=common.digest(nested_dir / "nested_manifest.json"),
        output_sha256={p.name: common.digest(p) for p in (aggregate_file, budget_file)},
        no_policy_execution=True, no_simulation=True, no_whitebox_access=True,
        no_paper_changes=True,
    )
    (out / "kg_condition_adaptivity_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for row in aggregate_rows:
        if row["budget_set"] == "MEAN_OVER_13_BUDGETS":
            print("KG_ADAPTIVITY_AGGREGATE", row["archive"],
                  f"difference={row['mean_regret_diff']:.7g}",
                  f"familywise95=[{row['low_familywise95']:.7g},"
                  f"{row['high_familywise95']:.7g}]", flush=True)
    print(f"KG_ADAPTIVITY_INFERENCE_PASS {out}")


if __name__ == "__main__":
    main()
