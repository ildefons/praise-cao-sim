#!/usr/bin/env python3
"""KG acquisition-decomposition study using the frozen B1 loss catalogue.

Development-only retrospective replay; does not modify historical B1 outputs.
Five policies independently acquire method-condition outcomes and update their
own posterior histories. This is not new-provider-world validation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

POLICIES = (
    "joint_kg", "method_first_adaptive", "condition_first_adaptive",
    "method_first_uniform", "condition_first_uniform",
)
BUDGETS = (10, 15, 20, 30, 40)
SEED = 20261110


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def save_csv(path, rows):
    if not rows:
        raise ValueError(f"Empty output: {path}")
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def tie_best(indices, scores, rng):
    scores = np.asarray(scores, dtype=float)
    winners = np.flatnonzero(scores >= np.max(scores) - 1e-12)
    return indices[int(rng.choice(winners))]


def select(policy, matrix, rng):
    """Choose an unused (method, condition) pair from a NaN-masked KG matrix.

    Only currently unevaluated cells contribute to first-stage means.
    """
    valid = np.isfinite(matrix)
    aa, cc = np.where(valid)
    if len(aa) == 0:
        raise ValueError("No unused evaluation")
    pair_indices = list(range(len(aa)))
    j = int(tie_best(pair_indices, matrix[aa, cc], rng))
    joint = (int(aa[j]), int(cc[j]))

    avg_a = np.array([
        float(np.mean(matrix[a, valid[a]])) if np.any(valid[a]) else -np.inf
        for a in range(matrix.shape[0])
    ])
    avg_c = np.array([
        float(np.mean(matrix[valid[:, c], c])) if np.any(valid[:, c]) else -np.inf
        for c in range(matrix.shape[1])
    ])
    a = int(tie_best(list(range(len(avg_a))), avg_a, rng))
    c = int(tie_best(list(range(len(avg_c))), avg_c, rng))
    available_c = np.flatnonzero(valid[a])
    available_a = np.flatnonzero(valid[:, c])
    method_pair = (a, int(tie_best(list(available_c), matrix[a, available_c], rng)))
    condition_pair = (int(tie_best(list(available_a), matrix[available_a, c], rng)), c)

    if policy == "joint_kg":
        selected = joint
    elif policy == "method_first_adaptive":
        selected = method_pair
    elif policy == "condition_first_adaptive":
        selected = condition_pair
    elif policy == "method_first_uniform":
        selected = (a, int(rng.choice(available_c)))
    elif policy == "condition_first_uniform":
        selected = (int(rng.choice(available_a)), c)
    else:
        raise ValueError(policy)

    dispersion_a = max(
        float(np.max(matrix[x, valid[x]]) - avg_a[x])
        for x in range(matrix.shape[0]) if np.any(valid[x])
    )
    dispersion_c = max(
        float(np.max(matrix[valid[:, x], x]) - avg_c[x])
        for x in range(matrix.shape[1]) if np.any(valid[:, x])
    )
    joint_value = float(matrix[joint])
    method_value = float(matrix[method_pair])
    condition_value = float(matrix[condition_pair])
    if joint_value - method_value > dispersion_a + 1e-10:
        raise AssertionError("Method-first one-step bound failed")
    if joint_value - condition_value > dispersion_c + 1e-10:
        raise AssertionError("Condition-first one-step bound failed")
    diagnostics = dict(
        joint_a=joint[0], joint_c=joint[1],
        method_a=method_pair[0], method_c=method_pair[1],
        condition_a=condition_pair[0], condition_c=condition_pair[1],
        joint_kg=joint_value, selected_kg=float(matrix[selected]),
        method_kg=method_value, condition_kg=condition_value,
        method_kg_gap=joint_value-method_value,
        condition_kg_gap=joint_value-condition_value,
        method_dispersion_bound=dispersion_a,
        condition_dispersion_bound=dispersion_c,
        method_disagrees=int(method_pair != joint),
        condition_disagrees=int(condition_pair != joint),
        methods_vs_conditions_disagree=int(method_pair != condition_pair),
    )
    return selected, diagnostics


def episode(losses, policy, budget, start, rep, frozen, kg):
    rng = np.random.default_rng(
        np.random.SeedSequence([SEED, budget, start, rep, POLICIES.index(policy)])
    )
    n_methods, n_conditions = losses.shape
    seen = [(a, start, float(losses[a, start])) for a in range(n_methods)]
    trace = []
    while len(seen) < budget:
        means, _, covariances = frozen.posterior(seen, n_methods)
        acquired = {(a, c) for a, c, _ in seen}
        available = [
            (a, c, 0) for a in range(n_methods)
            for c in range(n_conditions) if (a, c) not in acquired
        ]
        values = kg.scores_from_posterior(means, covariances, available)
        matrix = np.full((n_methods, n_conditions), np.nan)
        for (a, c, _), value in zip(available, values):
            matrix[a, c] = value
        (a, c), diag = select(policy, matrix, rng)
        trace.append(dict(
            policy=policy, budget=budget, start=start, rep=rep,
            step=len(seen) + 1, method=a, condition=c, **diag
        ))
        seen.append((a, c, float(losses[a, c])))
    means, _, _ = frozen.posterior(seen, n_methods)
    recommended = int(np.argmin(means))
    true_means = losses.mean(axis=1)
    best = int(np.argmin(true_means))
    terminal = dict(
        policy=policy, budget=budget, start=start, rep=rep,
        selected=recommended, best=best, correct=int(recommended == best),
        regret=max(0., float(true_means[recommended] - true_means[best])),
    )
    return terminal, trace


def summarize(rows, traces, budgets):
    result = []
    for budget in budgets:
        for policy in POLICIES:
            terminals = [r for r in rows if r["budget"] == budget and r["policy"] == policy]
            actions = [r for r in traces if r["budget"] == budget and r["policy"] == policy]
            result.append(dict(
                budget=budget, policy=policy, n=len(terminals),
                mean_regret=float(np.mean([r["regret"] for r in terminals])),
                p_correct=float(np.mean([r["correct"] for r in terminals])),
                mean_selected_kg_gap=float(np.mean([
                    r["joint_kg"] - r["selected_kg"] for r in actions
                ])),
                disagreement_from_joint=float(np.mean([
                    int((r["method"], r["condition"]) != (r["joint_a"], r["joint_c"]))
                    for r in actions
                ])),
                method_dispersion=float(np.mean([
                    r["method_dispersion_bound"] for r in actions
                ])),
                condition_dispersion=float(np.mean([
                    r["condition_dispersion_bound"] for r in actions
                ])),
            ))
    return result


def paired_contrasts(rows, budgets, repeats, bootstrap):
    lookup = {(r["policy"], r["budget"], r["start"], r["rep"]): r for r in rows}
    rng = np.random.default_rng(SEED + 1)
    result = []
    for budget in budgets:
        for policy in POLICIES[1:]:
            delta = np.array([
                [
                    lookup[(policy, budget, start, rep)]["regret"] -
                    lookup[("joint_kg", budget, start, rep)]["regret"]
                    for rep in range(repeats)
                ]
                for start in range(12)
            ])
            sampled = rng.integers(repeats, size=(bootstrap, 12, repeats))
            boot_means = np.take_along_axis(
                delta[None, :, :], sampled, axis=2
            ).mean(axis=(1, 2))
            result.append(dict(
                budget=budget, policy=policy, vs="joint_kg",
                mean_regret_difference=float(delta.mean()),
                ci_low=float(np.quantile(boot_means, .025)),
                ci_high=float(np.quantile(boot_means, .975)),
            ))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, help="Frozen B1 seven_method_matrix.csv")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--smoke-synthetic", action="store_true",
                        help="Synthetic execution test; NOT scientific evidence")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import b1_budget_comparison_v1 as frozen
    import b1_kg_one_step_v1 as kg

    if args.smoke_synthetic:
        rng = np.random.default_rng(104)
        losses = np.clip(.13 + rng.normal(0, .03, (7, 12)), 0., 1.)
        budgets = (10, 15)
    else:
        if args.matrix is None:
            parser.error("--matrix is required unless --smoke-synthetic")
        losses = kg.load_frozen_matrix(args.matrix.expanduser().resolve())
        budgets = BUDGETS

    if args.out.exists():
        raise FileExistsError(f"Output directory exists: {args.out}")
    if losses.shape != (7, 12) or args.repeats < 1 or args.bootstrap < 100:
        raise ValueError("Expected 7 x 12 losses, positive repeats and bootstrap >= 100")

    terminals, diagnostics = [], []
    for budget in budgets:
        for start in range(12):
            for rep in range(args.repeats):
                for policy in POLICIES:
                    record, trace = episode(losses, policy, budget, start, rep, frozen, kg)
                    terminals.append(record)
                    diagnostics.extend(trace)
        print("COMPLETED", budget, len(terminals), "episodes", flush=True)

    args.out.mkdir(parents=True)
    save_csv(args.out / "terminals.csv", terminals)
    save_csv(args.out / "acquisition_diagnostics.csv", diagnostics)
    summary = summarize(terminals, diagnostics, budgets)
    save_csv(args.out / "summary.csv", summary)
    if not args.smoke_synthetic:
        save_csv(args.out / "paired_vs_joint.csv",
                 paired_contrasts(terminals, budgets, args.repeats, args.bootstrap))

    manifest = dict(
        status=("SYNTHETIC_SMOKE_TEST_NOT_EVIDENCE" if args.smoke_synthetic
                else "FROZEN_B1_RETROSPECTIVE_DECOMPOSITION_DEVELOPMENT"),
        matrix_sha256=(sha(args.matrix.expanduser().resolve())
                       if args.matrix and not args.smoke_synthetic else None),
        seed=SEED, budgets=budgets, repeats=args.repeats, policies=POLICIES,
        source_sha256=sha(Path(__file__)), episodes=len(terminals),
        actions=len(diagnostics),
        files_sha256={p.name: sha(p) for p in args.out.glob("*.csv")},
    )
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("KG_DECOMPOSITION_PASS", manifest["status"])
    print("OUTPUT", args.out.resolve())
    for item in summary:
        print("SUMMARY", item)


if __name__ == "__main__":
    main()
