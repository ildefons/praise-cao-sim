#!/usr/bin/env python3
"""Budget-independent, nested-trajectory replay of six original B1 policies.

For each archive, policy, starting condition and replicate, draw the random
streams ONCE (without the terminal budget in the seed), acquire observations
through B=80, and score the *same prefix* at all 13 budgets. The archived
fixed-budget runs are never edited or read as inputs to this replay.

The three Top2 policies are deliberately excluded: their acquisition schedules
depend on the precommitted terminal budget, so they have no single common
trajectory over different budgets.

No simulator, predictor, calibration, or hidden-outcome query is run.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

import b1_budget_comparison_v1 as frozen
import b1_kg_one_step_v1 as kg
import b1_condition_selection_controlled_v1 as controlled
from extend_b1_original_nine_policy_budgets_v1 import balanced_score_full_catalog


BUDGETS = (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80)
POLICIES = (
    "random", "balanced", "informed", "kg_one_step",
    "kg_two_stage_adaptive", "kg_two_stage_uniform",
)
POLICY_IDS = {policy: i for i, policy in enumerate(POLICIES)}
CONTRAST_PAIRS = (
    ("kg_one_step", "balanced"),
    ("kg_one_step", "informed"),
    ("kg_one_step", "random"),
    ("kg_two_stage_adaptive", "kg_one_step"),
    ("kg_two_stage_uniform", "kg_one_step"),
    ("kg_two_stage_adaptive", "kg_two_stage_uniform"),
)
SEED = 20261105
REPEATS = 20
BOOTSTRAPS = 2000
EXPECTED_SHAS = {
    "historical": ("0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",),
    "fresh_reference": (
        "5c81f50af9fad98596f0eac17ec3e9afc7848661acf476740af48663119606a3",
    ),
}
TERMINAL_FIELDS = (
    "archive", "policy", "budget", "start_index", "start_cell", "replicate",
    "evaluations", "recommended", "correct", "simple_regret",
)
HISTORY_FIELDS = (
    "archive", "policy", "start_index", "replicate", "step",
    "method", "world", "graph", "mae",
)
SUMMARY_FIELDS = (
    "archive", "budget", "policy", "episodes", "mean_regret", "regret_low",
    "regret_high", "p_correct", "p_low", "p_high", "regret_p90",
)
CONTRAST_FIELDS = (
    "archive", "budget", "contrast", "mean_regret_diff", "low", "high",
)


def parse_matrix(path: Path) -> np.ndarray:
    """Read a complete frozen 7x12 MAE table, regardless of CSV row order."""
    values = np.full((len(frozen.METHODS), len(frozen.CELLS)), np.nan)
    rows = frozen.read_csv(path)
    if len(rows) != values.size:
        raise ValueError(f"Expected exactly {values.size} method/cell rows: {path}")
    for row in rows:
        name = row["method"]
        cell = (row["world"], row["graph"])
        if name not in frozen.METHODS or cell not in frozen.CELLS:
            raise ValueError(f"Unknown method or condition: {name}, {cell}")
        a, c = frozen.METHODS.index(name), frozen.CELLS.index(cell)
        if np.isfinite(values[a, c]):
            raise ValueError(f"Duplicate action in matrix: {name}, {cell}")
        value = float(row["mae"])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid MAE at {name}, {cell}: {value}")
        values[a, c] = value
    if not np.isfinite(values).all():
        raise ValueError("Matrix has missing actions or non-finite MAE")
    return values


def verify_matrix(path: Path, archive: str) -> tuple[np.ndarray, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    checksum = frozen.digest(path)
    if checksum not in EXPECTED_SHAS[archive]:
        raise ValueError(f"{archive}: matrix SHA256 not in frozen allowlist: {checksum}")
    y = parse_matrix(path)
    expected_best = "M3_FULL343" if archive == "historical" else "M1"
    actual_best = frozen.METHODS[int(np.argmin(y.mean(axis=1)))]
    if actual_best != expected_best:
        raise ValueError(f"{archive}: reference winner changed ({actual_best})")
    return y, checksum


def make_streams(seed: int, start: int, replicate: int, policy: str):
    """Never include archive or B: both are replay/scoring dimensions."""
    if policy not in POLICY_IDS:
        raise ValueError(f"Not a budget-independent policy: {policy}")
    base = [seed, start, replicate, POLICY_IDS[policy]]
    return (
        np.random.default_rng(np.random.SeedSequence([*base, 0])),
        np.random.default_rng(np.random.SeedSequence([*base, 33])),
        np.random.default_rng(np.random.SeedSequence([*base, 44])),
    )


def select_action(policy: str, seen: list[tuple[int, int, float]], streams):
    """Call the original acquisition criteria with only the observed history."""
    joint_rng, arm_rng, cell_rng = streams
    methods = len(frozen.METHODS)
    if policy in ("random", "informed"):
        # For both selectors, frozen.select_action does not inspect budget.
        return frozen.select_action(policy, seen, max(BUDGETS), joint_rng, methods)
    if policy == "balanced":
        visited = {(a, c) for a, c, _ in seen}
        available = [(a, c, 0) for a in range(methods)
                     for c in range(len(frozen.CELLS)) if (a, c) not in visited]
        if not available:
            raise ValueError("No remaining actions")
        # Identical balance scores and tie rule, with the documented B=80
        # seven-row array fix from the original budget extension.
        return balanced_score_full_catalog(seen, available, joint_rng)
    if policy == "kg_one_step":
        return kg.select_kg(seen, joint_rng, methods)
    if policy in ("kg_two_stage_adaptive", "kg_two_stage_uniform"):
        # Controlled acquisition's KG branch never uses its B parameter.
        arms, conditional, remaining = controlled.acquisition(
            seen, "kg", max(BUDGETS), frozen, kg
        )
        a = controlled.pick(arms, arm_rng)
        candidates = remaining[a]
        if policy == "kg_two_stage_adaptive":
            c = candidates[controlled.pick(conditional[a], cell_rng)]
        else:
            c = int(cell_rng.choice(candidates))
        return a, c
    raise ValueError(f"Unknown policy: {policy}")


def episode(y: np.ndarray, archive: str, policy: str, start: int, replicate: int,
            seed: int = SEED, checkpoints: tuple[int, ...] = BUDGETS):
    """Return scored checkpoints and a single unrepeated action history.

    Supplying a prefix of checkpoints for testing must produce identical
    actions and scores to the corresponding prefix of the full 80-step run.
    """
    if y.shape != (len(frozen.METHODS), len(frozen.CELLS)):
        raise ValueError("Expected exactly the frozen 7x12 catalogue")
    if policy not in POLICIES:
        raise ValueError(f"Policy cannot be nested: {policy}")
    if not 0 <= start < len(frozen.CELLS) or replicate < 0:
        raise ValueError("Invalid initial cell or replicate")
    if not checkpoints or tuple(sorted(set(checkpoints))) != tuple(checkpoints):
        raise ValueError("Checkpoints must be nonempty, sorted and unique")
    if min(checkpoints) <= len(frozen.METHODS) or max(checkpoints) >= y.size:
        raise ValueError("Checkpoint outside feasible distinct-action range")
    streams = make_streams(seed, start, replicate, policy)
    seen = [(a, start, float(y[a, start])) for a in range(len(frozen.METHODS))]
    visited = {(a, c) for a, c, _ in seen}
    checkpoints_set = set(checkpoints)
    truth = y.mean(axis=1)  # Only used for terminal scoring, never acquisition.
    best = int(np.argmin(truth))
    terminal = []
    while len(seen) < max(checkpoints):
        a, c = select_action(policy, seen, streams)
        if not (0 <= a < y.shape[0] and 0 <= c < y.shape[1]):
            raise AssertionError("Selector returned an out-of-catalogue action")
        if (a, c) in visited:
            raise AssertionError("Selector repeated a previously observed action")
        visited.add((a, c))
        seen.append((a, c, float(y[a, c])))
        budget = len(seen)
        if budget in checkpoints_set:
            posterior_means, _, _ = frozen.posterior(seen, y.shape[0])
            recommendation = int(np.argmin(posterior_means))
            terminal.append(dict(
                archive=archive, policy=policy, budget=budget,
                start_index=start,
                start_cell=f"{frozen.CELLS[start][0]}__{frozen.CELLS[start][1]}",
                replicate=replicate, evaluations=budget,
                recommended=frozen.METHODS[recommendation],
                correct=int(recommendation == best),
                simple_regret=max(0., float(truth[recommendation] - truth[best])),
            ))
    history = [dict(
        archive=archive, policy=policy, start_index=start,
        replicate=replicate, step=i + 1, method=frozen.METHODS[a],
        world=frozen.CELLS[c][0], graph=frozen.CELLS[c][1], mae=value,
    ) for i, (a, c, value) in enumerate(seen)]
    return terminal, history


def save_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def stratified_mean(values: np.ndarray, draws: np.ndarray) -> np.ndarray:
    """Stratify over 12 initial conditions, resample repeats within each."""
    if values.ndim != 2 or values.shape[0] != len(frozen.CELLS):
        raise ValueError("Expected 12 x repeats for stratified bootstrap")
    return np.take_along_axis(values[None, :, :], draws, axis=2).mean(axis=(1, 2))


def statistics(rows: list[dict], repeats: int, nboot: int, seed: int,
               checkpoints: tuple[int, ...] = BUDGETS):
    keyed = {
        (r["archive"], r["policy"], r["budget"], r["start_index"], r["replicate"]): r
        for r in rows
    }
    expected = 2 * len(POLICIES) * len(checkpoints) * len(frozen.CELLS) * repeats
    if len(rows) != expected or len(keyed) != expected:
        raise AssertionError(f"Missing or duplicate terminals: {len(rows)} vs {expected}")
    summaries, contrasts = [], []
    for archive_id, archive in enumerate(EXPECTED_SHAS):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 731, archive_id]))
        values_by_budget = {}
        for budget in checkpoints:
            draws = rng.integers(repeats, size=(nboot, len(frozen.CELLS), repeats))
            matrices = {}
            for policy in POLICIES:
                ordered = [keyed[archive, policy, budget, s, rep]
                           for s in range(len(frozen.CELLS)) for rep in range(repeats)]
                regrets = np.array([r["simple_regret"] for r in ordered]).reshape(12, repeats)
                correct = np.array([r["correct"] for r in ordered]).reshape(12, repeats)
                matrices[policy] = regrets
                br, bc = stratified_mean(regrets, draws), stratified_mean(correct, draws)
                summaries.append(dict(
                    archive=archive, budget=budget, policy=policy, episodes=len(ordered),
                    mean_regret=float(regrets.mean()),
                    regret_low=float(np.quantile(br, .025)),
                    regret_high=float(np.quantile(br, .975)),
                    p_correct=float(correct.mean()),
                    p_low=float(np.quantile(bc, .025)),
                    p_high=float(np.quantile(bc, .975)),
                    regret_p90=float(np.quantile(regrets, .90)),
                ))
            values_by_budget[budget] = matrices
            for left, right in CONTRAST_PAIRS:
                delta = matrices[left] - matrices[right]
                bd = stratified_mean(delta, draws)
                contrasts.append(dict(
                    archive=archive, budget=budget, contrast=f"{left} minus {right}",
                    mean_regret_diff=float(delta.mean()),
                    low=float(np.quantile(bd, .025)),
                    high=float(np.quantile(bd, .975)),
                ))
        # Reuse identical bootstrap indices across all budget checkpoints:
        # each replicate's outcomes at different budgets are correlated.
        draws = rng.integers(repeats, size=(nboot, len(frozen.CELLS), repeats))
        for left, right in CONTRAST_PAIRS:
            delta_by_budget = np.array([
                values_by_budget[budget][left] - values_by_budget[budget][right]
                for budget in checkpoints
            ])
            boot = np.stack([
                stratified_mean(delta, draws) for delta in delta_by_budget
            ], axis=1).mean(axis=1)
            contrasts.append(dict(
                archive=archive, budget=f"MEAN_OVER_{len(checkpoints)}_BUDGETS",
                contrast=f"{left} minus {right}",
                mean_regret_diff=float(delta_by_budget.mean()),
                low=float(np.quantile(boot, .025)),
                high=float(np.quantile(boot, .975)),
            ))
    return summaries, contrasts


def run(matrices: dict[str, np.ndarray], input_paths: dict[str, Path],
        checksums: dict[str, str], output: Path, repeats: int, nboot: int,
        seed: int = SEED) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite any earlier run: {output}")
    output.mkdir(parents=True, exist_ok=False)
    terminals = []
    history_path = output / "nested_action_history.csv"
    with history_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=HISTORY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for archive, y in matrices.items():
            for policy in POLICIES:
                for start in range(len(frozen.CELLS)):
                    for replicate in range(repeats):
                        scored, actions = episode(y, archive, policy, start, replicate, seed)
                        terminals.extend(scored)
                        writer.writerows(actions)
                print(f"NESTED_TRAJECTORIES_OK {archive} {policy} "
                      f"trajectories={len(frozen.CELLS) * repeats}", flush=True)
    summary, contrast = statistics(terminals, repeats, nboot, seed)
    save_csv(output / "nested_terminal_episodes.csv", terminals, TERMINAL_FIELDS)
    save_csv(output / "nested_budget_summary.csv", summary, SUMMARY_FIELDS)
    save_csv(output / "nested_paired_contrasts.csv", contrast, CONTRAST_FIELDS)
    csv_files = sorted(output.glob("*.csv"))
    manifest = dict(
        status="B1_NESTED_BUDGET_REPLAY_V1_COMPLETE",
        budgets=BUDGETS, policies=POLICIES, policy_seed_ids=POLICY_IDS,
        excluded_budget_dependent_policies=(
            "budgeted_top2", "top2_two_stage_adaptive", "top2_two_stage_uniform"
        ),
        initial_evaluations_per_trajectory=len(frozen.METHODS),
        maximum_evaluations_per_trajectory=max(BUDGETS),
        starts=len(frozen.CELLS), repeats_per_start=repeats,
        trajectories_per_policy_per_archive=len(frozen.CELLS) * repeats,
        terminal_episodes_per_policy_per_archive=len(frozen.CELLS) * repeats * len(BUDGETS),
        bootstrap_replicates=nboot, seed=seed,
        seed_components="[seed, start_index, replicate, fixed_policy_id, stream_id]",
        budget_in_seed=False, archive_in_seed=False,
        trajectory_rule="one 80-evaluation trajectory; score prefixes at all budgets",
        budget_criterion="six acquisition selectors do not use terminal B",
        baseline_recommendation="same argmin-posterior-mean rule at every checkpoint",
        population="conditional on each fixed seven-method x twelve-condition matrix",
        archive_sources={name: dict(path=str(input_paths[name]), sha256=checksums[name])
                         for name in matrices},
        policy_source_sha256={name: frozen.digest(Path(module.__file__)) for name, module in (
            ("baseline", frozen), ("joint_kg", kg), ("two_stage", controlled),
        )},
        compatibility_source_sha256=frozen.digest(
            Path(balanced_score_full_catalog.__code__.co_filename)),
        outputs_sha256={path.name: frozen.digest(path) for path in csv_files},
        no_simulation=True, frozen_runs_unchanged=True,
        note=("Paired intervals resample matched start/replicate indices, not paired "
              "action histories across policies. Across-budget resampling retains "
              "each trajectory's nested checkpoint dependence. Top2 can only be "
              "overlaid from its separate budget-specific archived summaries."),
    )
    (output / "nested_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"B1_NESTED_REPLAY_PASS {output.resolve()}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-matrix", required=True, type=Path)
    parser.add_argument("--fresh-reference-matrix", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--repeats-per-start", type=int, default=REPEATS)
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.repeats_per_start < 2 or args.bootstrap < 100 or args.seed < 0:
        parser.error("Need >=2 repeats, >=100 bootstrap draws and a nonnegative seed")
    matrices, checksums, inputs = {}, {}, {
        "historical": args.historical_matrix.resolve(),
        "fresh_reference": args.fresh_reference_matrix.resolve(),
    }
    for archive, path in inputs.items():
        matrices[archive], checksums[archive] = verify_matrix(path, archive)
        print(f"NESTED_INPUT_OK {archive} sha256={checksums[archive]} "
              f"best={frozen.METHODS[int(np.argmin(matrices[archive].mean(axis=1)))]}")
    print(f"NESTED_DESIGN_OK policies={','.join(POLICIES)} budgets={','.join(map(str, BUDGETS))}")
    if args.preflight_only:
        print("NESTED_PREFLIGHT_PASS no outputs written")
        return
    if args.out is None:
        parser.error("--out is required unless --preflight-only is specified")
    run(matrices, inputs, checksums, args.out.expanduser().resolve(),
        args.repeats_per_start, args.bootstrap, args.seed)


if __name__ == "__main__":
    main()
