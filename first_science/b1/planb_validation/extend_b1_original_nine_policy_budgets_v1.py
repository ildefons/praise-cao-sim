#!/usr/bin/env python3
"""Extend the ORIGINAL B1 nine-policy experiment to eight new budgets.

Policy implementations and their Gaussian posterior are imported from
b1_budget_comparison_v1, b1_kg_one_step_v1 and
b1_condition_selection_controlled_v1. Only the budget membership guard and
the bootstrap *loop length* are generalized, apart from a compatibility guard
for the original balanced_score: when the last method has no unevaluated
cells, its scratch array must still have seven rows. This is the same balance
score and tie-break, with a fixed catalogue size. Existing 10--40 evidence
is never overwritten or recomputed by this runner.

Inputs are exactly one of the two previously frozen 7x12 accuracy matrices.
No white-box simulation, prediction changes, policy tuning, or noise draws.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

import b1_budget_comparison_v1 as f
import b1_kg_one_step_v1 as kg
import b1_condition_selection_controlled_v1 as ctl


NEW_BUDGETS = (25, 35, 45, 55, 65, 70, 75, 80)
HISTORICAL_BUDGETS = (10, 15, 20, 30, 40)
SEED, REPEATS, BOOTSTRAPS = 20261105, 20, 2000
MATRIX_SHAS = {
    "historical": "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d",
    "b0001": "0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b",
}
OUTPUTS = {
    "baseline": ("terminal_episodes.csv", "episode_action_history.csv", "budget_summary.csv", "paired_regret_contrasts.csv"),
    "kg": ("kg_terminal_episodes.csv", "kg_action_history.csv", "kg_budget_summary.csv", "kg_vs_baseline_contrasts.csv"),
    "controlled": ("controlled_terminal_episodes.csv", "controlled_action_history.csv", "controlled_budget_summary.csv", "controlled_paired_contrasts.csv"),
}
FROZEN_BALANCED_SCORE = f.balanced_score


def balanced_score_full_catalog(seen, available, rng):
    """Identical original balance score; fix its dimension at near-full budget.

    Original allocates rows using max(method_id in *available*) + 1 but then
    indexes *seen*. If method 7 is exhausted at budget 80, this raises an
    IndexError. All original weights, candidates, and RNG tie-breaks are kept.
    For states with the last method still available, call original verbatim.
    """
    if max(a for a, _, _ in available) == len(f.METHODS) - 1:
        return FROZEN_BALANCED_SCORE(seen, available, rng)
    catalogue_size = len(f.METHODS)
    k = np.zeros((catalogue_size, len(f.CELLS)), dtype=int)
    for a, c, _ in seen:
        k[a, c] = 1
    by_a = k.sum(axis=1)
    w_counts = np.array([
        [int(k[a, [i for i, (w, _) in enumerate(f.CELLS) if w == world]].sum())
         for world in f.WORLDS] for a in range(catalogue_size)
    ])
    g_counts = np.array([
        [int(k[a, [i for i, (_, g) in enumerate(f.CELLS) if g == graph]].sum())
         for graph in f.GRAPHS] for a in range(catalogue_size)
    ])
    scores = np.array([
        -100 * by_a[a]
        - 10 * w_counts[a, f.WORLDS.index(f.CELLS[c][0])]
        - 2 * g_counts[a, f.GRAPHS.index(f.CELLS[c][1])]
        for a, c, _ in available
    ])
    return f.choose_tie(available, scores, rng)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def save_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("Cannot write empty result " + str(path))
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class StreamRows:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.f = path.open("w", newline="")
        self.writer = None
        self.n = 0

    def write(self, rows: list[dict]) -> None:
        if not rows:
            return
        if self.writer is None:
            self.writer = csv.DictWriter(
                self.f, fieldnames=list(rows[0]), lineterminator="\n"
            )
            self.writer.writeheader()
        self.writer.writerows(rows)
        self.n += len(rows)

    def close(self) -> None:
        self.f.close()


def kg_statistics(kg_rows: list[dict], baseline_rows: list[dict],
                  budgets: tuple[int, ...]) -> tuple[list[dict], list[dict]]:
    """Generalize only the budget count in original KG bootstrap_summary.

    RNG, draw order, stratification, paired differences, percentiles and seed
    are identical to b1_kg_one_step_v1.bootstrap_summary. Regression-tested
    against its original five-budget B0001 output to 1e-12.
    """
    rng = np.random.default_rng(SEED + 913)
    grouped = {
        (int(r["budget"]), int(r["start_index"]), int(r["replicate"])): r
        for r in kg_rows
    }
    base = {
        (int(r["budget"]), int(r["start_index"]), int(r["replicate"]), r["policy"]): r
        for r in baseline_rows
    }
    expected = len(budgets) * 12 * REPEATS
    if len(grouped) != expected or len(base) != expected * len(f.POLICIES):
        raise AssertionError("Missing KG or baseline terminal episode")
    summaries, contrasts = [], []
    for budget in budgets:
        rows = [grouped[budget, c, rep] for c in range(12) for rep in range(REPEATS)]
        regret = np.asarray([float(x["simple_regret"]) for x in rows]).reshape(12, REPEATS)
        correct = np.asarray([int(x["correct"]) for x in rows]).reshape(12, REPEATS)
        draws = rng.integers(REPEATS, size=(BOOTSTRAPS, 12, REPEATS))
        rboot = np.take_along_axis(regret[None, :, :], draws, axis=2).mean(axis=(1, 2))
        cboot = np.take_along_axis(correct[None, :, :], draws, axis=2).mean(axis=(1, 2))
        summaries.append(dict(
            budget=budget, policy=kg.NAME, episodes=240,
            mean_regret=float(regret.mean()),
            regret_low=float(np.quantile(rboot, .025)),
            regret_high=float(np.quantile(rboot, .975)),
            p_correct=float(correct.mean()),
            p_low=float(np.quantile(cboot, .025)),
            p_high=float(np.quantile(cboot, .975)),
            regret_p90=float(np.quantile(regret, .90)),
        ))
        for policy in f.POLICIES:
            other = np.array([
                float(base[budget, c, rep, policy]["simple_regret"])
                for c in range(12) for rep in range(REPEATS)
            ]).reshape(12, REPEATS)
            difference = regret - other
            bdiff = np.take_along_axis(difference[None, :, :], draws, axis=2).mean(axis=(1, 2))
            contrasts.append(dict(
                budget=budget, contrast=f"{kg.NAME} minus {policy}",
                mean_regret_diff=float(difference.mean()),
                low=float(np.quantile(bdiff, .025)), high=float(np.quantile(bdiff, .975))
            ))
    draws = rng.integers(REPEATS, size=(BOOTSTRAPS, 12, REPEATS))
    for policy in f.POLICIES:
        across = np.array([
            np.array([
                float(grouped[budget, c, rep]["simple_regret"])
                - float(base[budget, c, rep, policy]["simple_regret"])
                for c in range(12) for rep in range(REPEATS)
            ]).reshape(12, REPEATS)
            for budget in budgets
        ])
        bdiff = np.stack([
            np.take_along_axis(a[None, :, :], draws, axis=2).mean(axis=(1, 2))
            for a in across
        ], axis=1).mean(axis=1)
        contrasts.append(dict(
            budget=(
                "MEAN_OVER_5_BUDGETS" if tuple(budgets) == HISTORICAL_BUDGETS
                else f"MEAN_OVER_{len(budgets)}_NEW_BUDGETS"
            ),
            contrast=f"{kg.NAME} minus {policy}",
            mean_regret_diff=float(across.mean()),
            low=float(np.quantile(bdiff, .025)), high=float(np.quantile(bdiff, .975))
        ))
    return summaries, contrasts


def run(matrix_path: Path, label: str, out: Path) -> None:
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite earlier experiment: {out}")
    expected_sha = MATRIX_SHAS[label]
    if digest(matrix_path) != expected_sha:
        raise ValueError("Input does not match frozen " + label + " 7x12 matrix SHA")

    kg.EXPECTED_MATRIX_SHA256 = expected_sha
    kg.EXPECTED_BUDGETS = NEW_BUDGETS  # original episode budget membership guard only
    ctl.BUDGETS = NEW_BUDGETS  # original control bootstrap's budget iteration only
    f.balanced_score = balanced_score_full_catalog  # catalogue dimension fix at B=80
    y = kg.load_frozen_matrix(matrix_path)
    if y.shape != (7, 12) or max(NEW_BUDGETS) >= y.size:
        raise ValueError("Invalid new budgets for 84 original arms")

    for stage in OUTPUTS:
        (out / stage).mkdir(parents=True, exist_ok=False)

    # Original episode and bootstrap functions; only edge-case balance-array
    # shape is corrected by the wrapper, without changing policy scores.
    baseline_rows = []
    trace = StreamRows(out / "baseline/episode_action_history.csv")
    for B in NEW_BUDGETS:
        for s in range(12):
            for rep in range(REPEATS):
                for policy in f.POLICIES:
                    row, actions = f.evaluate_episode(y, policy, B, s, rep, SEED)
                    baseline_rows.append(row)
                    trace.write(actions)
        print("B1_EXTENSION_BASELINE_PASS", label, B, flush=True)
    trace.close()
    base_summary, base_contrasts = f.summarize(
        baseline_rows, NEW_BUDGETS, REPEATS, BOOTSTRAPS, SEED
    )
    for row in base_contrasts:
        if row["budget"] == "MEAN_OVER_5_BUDGETS":
            row["budget"] = f"MEAN_OVER_{len(NEW_BUDGETS)}_NEW_BUDGETS"
    save_rows(out / "baseline/terminal_episodes.csv", baseline_rows)
    save_rows(out / "baseline/budget_summary.csv", base_summary)
    save_rows(out / "baseline/paired_regret_contrasts.csv", base_contrasts)

    # Original KG episode selector, unchanged. Budget count in its bootstrap
    # wrapper is parameterized by kg_statistics() above.
    kg_rows = []
    trace = StreamRows(out / "kg/kg_action_history.csv")
    for B in NEW_BUDGETS:
        for s in range(12):
            for rep in range(REPEATS):
                row, actions = kg.episode(y, B, s, rep)
                kg_rows.append(row)
                trace.write(actions)
        print("B1_EXTENSION_KG_PASS", label, B, flush=True)
    trace.close()
    kg_summary, kg_contrasts = kg_statistics(kg_rows, baseline_rows, NEW_BUDGETS)
    save_rows(out / "kg/kg_terminal_episodes.csv", kg_rows)
    save_rows(out / "kg/kg_budget_summary.csv", kg_summary)
    save_rows(out / "kg/kg_vs_baseline_contrasts.csv", kg_contrasts)

    # Original two-stage policies and original bootstrap procedure, unchanged.
    controlled_rows = []
    trace = StreamRows(out / "controlled/controlled_action_history.csv")
    for policy in ctl.POLICIES:
        for B in NEW_BUDGETS:
            for s in range(12):
                for rep in range(REPEATS):
                    row, actions = ctl.episode(y, policy, B, s, rep, f, kg)
                    controlled_rows.append(row)
                    trace.write(actions)
            print("B1_EXTENSION_CONTROLLED_PASS", label, policy, B, flush=True)
    trace.close()
    control_summary, control_contrasts = ctl.statistics(controlled_rows)
    for row in control_contrasts:
        if row["budget"] == "MEAN_OVER_5_BUDGETS":
            row["budget"] = f"MEAN_OVER_{len(NEW_BUDGETS)}_NEW_BUDGETS"
    save_rows(out / "controlled/controlled_terminal_episodes.csv", controlled_rows)
    save_rows(out / "controlled/controlled_budget_summary.csv", control_summary)
    save_rows(out / "controlled/controlled_paired_contrasts.csv", control_contrasts)

    counts = {
        "baseline": (len(baseline_rows), REPEATS * 12 * sum(NEW_BUDGETS) * len(f.POLICIES)),
        "kg": (len(kg_rows), REPEATS * 12 * sum(NEW_BUDGETS)),
        "controlled": (len(controlled_rows), REPEATS * 12 * sum(NEW_BUDGETS) * len(ctl.POLICIES)),
    }
    assert counts["baseline"][0] == len(NEW_BUDGETS) * 240 * 4
    assert counts["kg"][0] == len(NEW_BUDGETS) * 240
    assert counts["controlled"][0] == len(NEW_BUDGETS) * 240 * 4

    inputs = {
        "matrix_sha256": expected_sha, "matrix_source": str(matrix_path),
        "policy_code_sha256": {name: digest(path) for name, path in {
            "baseline": Path(f.__file__), "kg": Path(kg.__file__),
            "controlled": Path(ctl.__file__),
        }.items()},
        "new_budgets_only": NEW_BUDGETS, "existing_budgets_untouched": HISTORICAL_BUDGETS,
        "repeats_per_start_condition": REPEATS, "bootstrap_draws": BOOTSTRAPS,
        "seed": SEED, "policy_episode_functions_unchanged": True,
        "balanced_policy_compatibility": (
            "same -100/-10/-2 score and original tie-break; seven-row array "
            "when the final method has zero available cells"
        ),
        "no_physical_simulations": True, "no_predictions_modified": True,
        "terminal_and_action_counts": counts,
        "file_sha256": {
            str(path.relative_to(out)): digest(path)
            for path in sorted(out.rglob("*.csv"))
        },
    }
    (out / "manifest.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print("B1_NINE_POLICY_NEW_BUDGETS_PASS", label, out, flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--dataset", required=True, choices=tuple(MATRIX_SHAS))
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    run(a.matrix.resolve(), a.dataset, a.out.resolve())


if __name__ == "__main__":
    main()
