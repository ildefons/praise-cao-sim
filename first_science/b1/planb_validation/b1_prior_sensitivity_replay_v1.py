#!/usr/bin/env python3
"""Fixed-grid prior-sensitivity replay for the nine PRAISE B1 acquisition policies.

No provider simulation or reference generation is performed. Every scenario
reruns acquisition, rather than merely rescoring actions acquired with the
original prior. This is retrospective sensitivity analysis, not an independent
confirmation or a data-independent calibration of the original prior.

One invocation can run all scenarios, or selected scenarios for recoverable
local execution. A separate --analyse-only invocation reads the completed
scenario ledgers and produces a fixed-grid robustness audit.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import json
from pathlib import Path
from tempfile import mkdtemp

import numpy as np

import b1_budget_comparison_v1 as frozen
import b1_condition_selection_controlled_v1 as controlled
import b1_kg_one_step_v1 as kg
import b1_nested_budget_replay_v1 as nested
from extend_b1_original_nine_policy_budgets_v1 import balanced_score_full_catalog


ARCHIVES = ("historical", "fresh_reference")
BUDGETS = nested.BUDGETS
NESTED = nested.POLICIES
TOP2 = ("budgeted_top2", "top2_two_stage_adaptive", "top2_two_stage_uniform")
POLICIES = NESTED + TOP2
REPEATS = 20
SEED = nested.SEED
BOOTSTRAPS = 3000
BASE = (0.12, 0.07, 0.045, 0.055, 0.17)

# Predeclared before sensitivity outputs are inspected. Entries are
# (intercept SD, world SD, graph SD, residual SD, intercept mean).
SCENARIOS = {
    "base": BASE,
    "intercept_half": (0.06, 0.07, 0.045, 0.055, 0.17),
    "intercept_double": (0.24, 0.07, 0.045, 0.055, 0.17),
    "world_half": (0.12, 0.035, 0.045, 0.055, 0.17),
    "world_double": (0.12, 0.14, 0.045, 0.055, 0.17),
    "graph_half": (0.12, 0.07, 0.0225, 0.055, 0.17),
    "graph_double": (0.12, 0.07, 0.09, 0.055, 0.17),
    "noise_half": (0.12, 0.07, 0.045, 0.0275, 0.17),
    "noise_double": (0.12, 0.07, 0.045, 0.11, 0.17),
    "world_graph_swap": (0.12, 0.045, 0.07, 0.055, 0.17),
    "all_prior_half": (0.06, 0.035, 0.0225, 0.055, 0.17),
    "all_prior_double": (0.24, 0.14, 0.09, 0.055, 0.17),
    "mean_low": (0.12, 0.07, 0.045, 0.055, 0.10),
    "mean_high": (0.12, 0.07, 0.045, 0.055, 0.24),
}

TERMINAL_FIELDS = (
    "scenario", "archive", "policy", "budget", "start_index", "replicate",
    "recommended", "correct", "simple_regret",
)
SUMMARY_FIELDS = (
    "scenario", "archive", "policy", "budget", "episodes", "mean_regret", "p_correct",
)
CONTRASTS = tuple(("kg_two_stage_adaptive", p) for p in POLICIES
                  if p != "kg_two_stage_adaptive")
CONTRAST_FIELDS = (
    "scenario", "archive", "left", "right", "mean_regret_diff",
    "low95", "high95", "bootstrap_draws",
)
ROBUST_FIELDS = (
    "scenario", "archive", "adaptive_regret", "uniform_regret",
    "random_regret", "balanced_regret", "kg_joint_regret",
    "best_top2_regret", "best_top2_policy", "adaptive_minus_uniform",
    "adaptive_minus_best_top2", "adaptive_to_best_top2_ratio",
    "adaptive_rank_of_nine", "adaptive_better_than_uniform",
    "adaptive_better_than_random", "adaptive_better_than_balanced",
)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@contextmanager
def prior_configuration(name: str):
    """Change all policy posterior hyperparameters together; restore on exit."""
    if name not in SCENARIOS:
        raise ValueError("Unknown sensitivity scenario: " + name)
    alpha, world, graph, noise, mean = SCENARIOS[name]
    if min(alpha, world, graph, noise) <= 0 or not 0 <= mean <= 1:
        raise ValueError("Invalid Gaussian hyperparameters")
    old_variance = frozen.PRIOR_VAR.copy()
    old_mean = frozen.PRIOR_MEAN.copy()
    old_noise = frozen.NOISE
    old_balance = frozen.balanced_score
    try:
        frozen.PRIOR_VAR = np.array([alpha**2] + [world**2] * 3 + [graph**2] * 4)
        frozen.PRIOR_MEAN = np.array([mean] + [0.] * 7)
        frozen.NOISE = noise
        # Existing B=80 compatibility fix; original coverage score is unchanged.
        frozen.balanced_score = balanced_score_full_catalog
        yield
    finally:
        frozen.PRIOR_VAR = old_variance
        frozen.PRIOR_MEAN = old_mean
        frozen.NOISE = old_noise
        frozen.balanced_score = old_balance


def episodes(y: np.ndarray, archive: str, scenario: str, repeats: int):
    """Rerun each distinct acquisition rule under one prior scenario."""
    if y.shape != (len(frozen.METHODS), len(frozen.CELLS)):
        raise ValueError("Expected a complete 7x12 reference matrix")
    with prior_configuration(scenario):
        for policy in POLICIES:
            if policy in NESTED:
                for start in range(len(frozen.CELLS)):
                    for rep in range(repeats):
                        terminal, _ = nested.episode(y, archive, policy, start, rep, SEED)
                        for row in terminal:
                            yield {k: row[k] for k in TERMINAL_FIELDS if k != "scenario"} | {"scenario": scenario}
            else:
                for budget in BUDGETS:
                    for start in range(len(frozen.CELLS)):
                        for rep in range(repeats):
                            if policy == "budgeted_top2":
                                row, _ = frozen.evaluate_episode(y, policy, budget, start, rep, SEED)
                            else:
                                row, _ = controlled.episode(y, policy, budget, start, rep, frozen, kg)
                            yield {
                                "scenario": scenario, "archive": archive, "policy": policy,
                                "budget": budget, "start_index": start, "replicate": rep,
                                "recommended": row["recommended"], "correct": row["correct"],
                                "simple_regret": row["simple_regret"],
                            }


def normalized_matrices(rows: list[dict], scenario: str, repeats: int):
    """Require one exact 12xrepeats matrix per archive/policy/budget."""
    expected = len(ARCHIVES) * len(POLICIES) * len(BUDGETS) * 12 * repeats
    if len(rows) != expected:
        raise ValueError(f"Incorrect terminal count: {len(rows)} != {expected}")
    matrix = {
        (archive, policy, budget): np.full((12, repeats), np.nan)
        for archive in ARCHIVES for policy in POLICIES for budget in BUDGETS
    }
    correct = {key: np.full((12, repeats), np.nan) for key in matrix}
    for row in rows:
        if row["scenario"] != scenario:
            raise ValueError("Scenario mismatch in terminal rows")
        key = (row["archive"], row["policy"], int(row["budget"]))
        if key not in matrix:
            raise ValueError(f"Unknown key: {key}")
        start, rep = int(row["start_index"]), int(row["replicate"])
        if not (0 <= start < 12 and 0 <= rep < repeats):
            raise ValueError("Start or replicate outside declared design")
        if np.isfinite(matrix[key][start, rep]):
            raise ValueError("Duplicate terminal episode")
        regret = float(row["simple_regret"])
        corr = float(row["correct"])
        if not np.isfinite(regret) or regret < -1e-12 or corr not in (0, 1):
            raise ValueError("Invalid terminal regret/correctness")
        matrix[key][start, rep] = regret
        correct[key][start, rep] = corr
    if any(not np.isfinite(a).all() for a in (*matrix.values(), *correct.values())):
        raise ValueError("Missing terminal episodes")
    return matrix, correct


def summarize(rows: list[dict], scenario: str, repeats: int):
    matrices, correctness = normalized_matrices(rows, scenario, repeats)
    summary = [dict(
        scenario=scenario, archive=archive, policy=policy, budget=budget,
        episodes=12 * repeats,
        mean_regret=float(matrices[archive, policy, budget].mean()),
        p_correct=float(correctness[archive, policy, budget].mean()),
    ) for archive in ARCHIVES for policy in POLICIES for budget in BUDGETS]
    return summary, matrices


def compare_base(summary: list[dict], reference: Path) -> None:
    """Base case must reproduce all 234 published nine-policy mean regrets."""
    archive = {(r["archive"], r["policy"], int(r["budget"])): float(r["mean_regret"])
               for r in read_csv(reference)}
    expected = len(ARCHIVES) * len(POLICIES) * len(BUDGETS)
    if len(archive) != expected or len(summary) != expected:
        raise ValueError("Published baseline summary is incomplete")
    for row in summary:
        key = (row["archive"], row["policy"], int(row["budget"]))
        if key not in archive or abs(row["mean_regret"] - archive[key]) > 1e-11:
            raise ValueError(f"Baseline regeneration disagrees with paper at {key}")


def scenario_run(name: str, matrices: dict, inputs: dict, root: Path, repeats: int):
    output = root / name
    if output.exists():
        verify_scenario(output, name, repeats, inputs)
        print(f"PRIOR_SCENARIO_ALREADY_VERIFIED {name}", flush=True)
        return
    temporary = Path(mkdtemp(prefix=f".{name}_incomplete_", dir=root))
    rows = []
    for archive in ARCHIVES:
        batch = list(episodes(matrices[archive], archive, name, repeats))
        rows.extend(batch)
        print(f"PRIOR_SCENARIO_TRAJECTORIES_OK {name} {archive} count={len(batch)}", flush=True)
    summary, _ = summarize(rows, name, repeats)
    if name == "base" and repeats == REPEATS:
        paper = Path(__file__).resolve().parent / "paper_systems/data/combined_nine_policy_budget_summary.csv"
        compare_base(summary, paper)
        print("PRIOR_BASE_REPRODUCES_ALL_234_PAPER_MEANS", flush=True)
    terminal_path = temporary / "terminal_episodes.csv"
    summary_path = temporary / "policy_budget_summary.csv"
    write_csv(terminal_path, rows, TERMINAL_FIELDS)
    write_csv(summary_path, summary, SUMMARY_FIELDS)
    params = SCENARIOS[name]
    manifest = dict(
        status="B1_PRIOR_SENSITIVITY_SCENARIO_V1_COMPLETE", scenario=name,
        hyperparameters=dict(zip(("tau_alpha", "tau_world", "tau_graph", "sigma", "intercept_mean"), params)),
        archives=ARCHIVES, budgets=BUDGETS, policies=POLICIES,
        repeats_per_start=repeats, seed=SEED,
        source_matrices=inputs, baseline_reference_checked=(name == "base" and repeats == REPEATS),
        policy_rules="six nested 80-step rules and three original budget-specific Top2 rules",
        policy_prior="common to all policies within each scenario",
        no_original_episodes_reused=True, no_whitebox_or_predictor_execution=True,
        interpretation="post-hoc sensitivity of retrospective fixed-domain replay; not prospective calibration",
        outputs_sha256={p.name: frozen.digest(p) for p in (terminal_path, summary_path)},
    )
    (temporary / "scenario_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.rename(output)
    print(f"PRIOR_SCENARIO_COMPLETE {name} {output}", flush=True)


def verify_scenario(output: Path, name: str, repeats: int, inputs: dict):
    marker = output / "scenario_manifest.json"
    if not marker.is_file():
        raise ValueError(f"Existing incomplete scenario output (left untouched): {output}")
    manifest = json.loads(marker.read_text())
    if (manifest.get("status") != "B1_PRIOR_SENSITIVITY_SCENARIO_V1_COMPLETE"
            or manifest.get("scenario") != name
            or manifest.get("repeats_per_start") != repeats
            or manifest.get("seed") != SEED
            or tuple(manifest.get("budgets", [])) != BUDGETS
            or tuple(manifest.get("policies", [])) != POLICIES
            or manifest.get("source_matrices") != inputs):
        raise ValueError(f"Existing scenario manifest conflicts with requested design: {output}")
    for filename in ("terminal_episodes.csv", "policy_budget_summary.csv"):
        path = output / filename
        if not path.is_file() or frozen.digest(path) != manifest["outputs_sha256"][filename]:
            raise ValueError(f"Invalid scenario source SHA: {path}")
    return manifest


def one_policy_bootstrap(matrices: dict, archive: str, policy: str, repeats: int,
                         nboot: int, rng: np.random.Generator):
    """Nested policies reuse budget draws; Top2 draws vary independently by B."""
    path = []
    nested_draws = rng.integers(repeats, size=(nboot, 12, repeats)) if policy in NESTED else None
    for budget in BUDGETS:
        draws = nested_draws if nested_draws is not None else rng.integers(
            repeats, size=(nboot, 12, repeats))
        arr = matrices[archive, policy, budget]
        path.append(np.take_along_axis(arr[None, :, :], draws, axis=2).mean(axis=(1, 2)))
    return np.stack(path, axis=1).mean(axis=1)


def scenario_inference(name: str, matrices: dict, repeats: int, nboot: int):
    contrast_rows, robust_rows = [], []
    for archive_id, archive in enumerate(ARCHIVES):
        aggregate = {policy: float(np.mean([
            matrices[archive, policy, b].mean() for b in BUDGETS
        ])) for policy in POLICIES}
        rng = np.random.default_rng(np.random.SeedSequence([20261120, archive_id,
                                            list(SCENARIOS).index(name), nboot]))
        sampled = {p: one_policy_bootstrap(matrices, archive, p, repeats, nboot, rng)
                   for p in POLICIES}
        for left, right in CONTRASTS:
            boot = sampled[left] - sampled[right]
            contrast_rows.append(dict(
                scenario=name, archive=archive, left=left, right=right,
                mean_regret_diff=aggregate[left] - aggregate[right],
                low95=float(np.quantile(boot, .025)),
                high95=float(np.quantile(boot, .975)),
                bootstrap_draws=nboot,
            ))
        best_top2 = min(TOP2, key=lambda p: aggregate[p])
        adap = aggregate["kg_two_stage_adaptive"]
        best_regret = aggregate[best_top2]
        robust_rows.append(dict(
            scenario=name, archive=archive,
            adaptive_regret=adap, uniform_regret=aggregate["kg_two_stage_uniform"],
            random_regret=aggregate["random"], balanced_regret=aggregate["balanced"],
            kg_joint_regret=aggregate["kg_one_step"], best_top2_regret=best_regret,
            best_top2_policy=best_top2,
            adaptive_minus_uniform=adap - aggregate["kg_two_stage_uniform"],
            adaptive_minus_best_top2=adap - best_regret,
            adaptive_to_best_top2_ratio=(adap / best_regret if best_regret > 0 else float("nan")),
            adaptive_rank_of_nine=1 + sum(aggregate[p] < adap - 1e-12 for p in POLICIES),
            adaptive_better_than_uniform=int(adap < aggregate["kg_two_stage_uniform"]),
            adaptive_better_than_random=int(adap < aggregate["random"]),
            adaptive_better_than_balanced=int(adap < aggregate["balanced"]),
        ))
    return contrast_rows, robust_rows


def analyse(root: Path, out: Path, repeats: int, nboot: int):
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite a previous analysis: {out}")
    matrix_inputs = {archive: {"sha256": nested.EXPECTED_SHAS[archive][0]}
                     for archive in ARCHIVES}
    all_robust, all_contrasts = [], []
    for name in SCENARIOS:
        src = root / name
        verify_scenario(src, name, repeats, matrix_inputs)
        rows = read_csv(src / "terminal_episodes.csv")
        _, matrices = summarize(rows, name, repeats)
        if name == "base" and repeats == REPEATS:
            summary = read_csv(src / "policy_budget_summary.csv")
            baseline = Path(__file__).resolve().parent / "paper_systems/data/combined_nine_policy_budget_summary.csv"
            compare_base([dict(r, mean_regret=float(r["mean_regret"])) for r in summary], baseline)
        c, r = scenario_inference(name, matrices, repeats, nboot)
        all_contrasts.extend(c)
        all_robust.extend(r)
        print("PRIOR_ANALYSIS_CASE", name, "reconciled", flush=True)
    out.mkdir(parents=True, exist_ok=False)
    contrast_file = out / "all_scenario_aggregate_contrasts.csv"
    robust_file = out / "prior_sensitivity_decision_table.csv"
    write_csv(contrast_file, all_contrasts, CONTRAST_FIELDS)
    write_csv(robust_file, all_robust, ROBUST_FIELDS)
    manifest = dict(
        status="B1_PRIOR_SENSITIVITY_ANALYSIS_V1_COMPLETE",
        scenarios={name: params for name, params in SCENARIOS.items()},
        archives=ARCHIVES, budgets=BUDGETS, policies=POLICIES,
        repeats_per_start=repeats, bootstrap=nboot,
        contrast_intervals="nominal exploratory 95%; do not claim familywise significance across prior grid",
        bootstrap_design="independent streams by policy; nested budget-prefix dependence retained; Top2 independently resampled by budget",
        source_manifests_sha256={name: frozen.digest(root / name / "scenario_manifest.json")
                                  for name in SCENARIOS},
        outputs_sha256={p.name: frozen.digest(p) for p in (contrast_file, robust_file)},
        interpretation="finite-grid conditional robustness, not universal prior insensitivity or absence of historical tuning",
    )
    (out / "sensitivity_analysis_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for archive in ARCHIVES:
        subset = [r for r in all_robust if r["archive"] == archive]
        print("PRIOR_ROBUSTNESS", archive,
              f"adaptive_lt_uniform={sum(r['adaptive_better_than_uniform'] for r in subset)}/{len(subset)}",
              f"adaptive_lt_random={sum(r['adaptive_better_than_random'] for r in subset)}/{len(subset)}",
              f"adaptive_lt_balanced={sum(r['adaptive_better_than_balanced'] for r in subset)}/{len(subset)}",
              f"adaptive_best_rank={min(r['adaptive_rank_of_nine'] for r in subset)}..{max(r['adaptive_rank_of_nine'] for r in subset)}",
              f"max_adaptive_minus_best_top2={max(r['adaptive_minus_best_top2'] for r in subset):.8g}",
              flush=True)
    print(f"B1_PRIOR_SENSITIVITY_ANALYSIS_PASS {out}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-matrix", type=Path)
    parser.add_argument("--fresh-reference-matrix", type=Path)
    parser.add_argument("--out-root", type=Path)
    parser.add_argument("--scenarios", default="all", help="all or comma-separated prespecified case names")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--analyse-only", action="store_true")
    parser.add_argument("--analysis-out", type=Path)
    parser.add_argument("--repeats-per-start", type=int, default=REPEATS)
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAPS)
    args = parser.parse_args()
    if args.repeats_per_start < 2 or args.bootstrap < 1000:
        parser.error("Require at least 2 repeats and 1000 bootstrap draws")
    if args.out_root is None:
        parser.error("--out-root required")
    root = args.out_root.expanduser().resolve()
    if args.analyse_only:
        if args.analysis_out is None:
            parser.error("--analysis-out required for --analyse-only")
        analyse(root, args.analysis_out.expanduser().resolve(),
                args.repeats_per_start, args.bootstrap)
        return
    if args.historical_matrix is None or args.fresh_reference_matrix is None:
        parser.error("Both frozen reference matrices are required")
    paths = {"historical": args.historical_matrix.expanduser().resolve(),
             "fresh_reference": args.fresh_reference_matrix.expanduser().resolve()}
    sources, matrices = {}, {}
    for archive, path in paths.items():
        matrices[archive], checksum = nested.verify_matrix(path, archive)
        sources[archive] = {"sha256": checksum}
        print("PRIOR_INPUT_OK", archive, f"sha256={checksum}", flush=True)
    chosen = tuple(SCENARIOS) if args.scenarios == "all" else tuple(args.scenarios.split(","))
    if not chosen or len(set(chosen)) != len(chosen) or any(x not in SCENARIOS for x in chosen):
        parser.error("Unknown, repeated, or empty prior scenario")
    print(f"PRIOR_GRID_OK {len(SCENARIOS)}_fixed_cases={','.join(SCENARIOS)}")
    print(f"PRIOR_RUN_OK selected={','.join(chosen)} policies={','.join(POLICIES)}")
    if args.preflight_only:
        print("PRIOR_PREFLIGHT_PASS no outputs written")
        return
    if not root.exists():
        root.mkdir(parents=True)
    elif not root.is_dir():
        raise ValueError("Output root is not a directory")
    for name in chosen:
        scenario_run(name, matrices, sources, root, args.repeats_per_start)
    print(f"B1_PRIOR_SENSITIVITY_REPLAY_PASS {root}", flush=True)


if __name__ == "__main__":
    main()
