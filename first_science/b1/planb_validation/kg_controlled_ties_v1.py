#!/usr/bin/env python3
"""Controlled tie-breaking audit for KG acquisition decomposition.

This is DEVELOPMENT evidence on the frozen B1 7x12 loss catalogue, not an
independent validation. It never changes the original replay or manuscript.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import b1_budget_comparison_v1 as frozen
import b1_kg_one_step_v1 as kg

POLICIES = ("joint_kg", "method_first_adaptive", "condition_first_adaptive")
BUDGETS = (10, 15, 20, 30, 40)
TOL = 1e-12
SEED = 20261110


def csv_write(path, rows):
    if not rows:
        raise ValueError("No rows: " + str(path))
    with path.open("w", newline="", encoding="utf-8") as h:
        writer = csv.DictWriter(h, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def priority(mode, budget, start, replicate, step, kind, item):
    # All policies use an identical order for a given named choice.
    if mode == "lexicographic":
        return item
    value = f"{SEED}|{budget}|{start}|{replicate}|{step}|{kind}|{item}"
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def best(items, values, mode, budget, start, rep, step, kind):
    items = list(items)
    if not items:
        raise ValueError("Empty choices")
    values = np.asarray(values, dtype=float)
    peak = float(np.max(values))
    candidates = [x for x, val in zip(items, values) if val >= peak - TOL]
    return min(candidates, key=lambda x: (priority(mode, budget, start, rep, step, kind, x), x))


def choice(scores, policy, mode, budget, start, rep, step):
    good = np.isfinite(scores)
    pairs = [(a, c) for a in range(scores.shape[0])
             for c in range(scores.shape[1]) if good[a, c]]
    joint = best(pairs, [scores[p] for p in pairs],
                 mode, budget, start, rep, step, "pair")

    mean_a = {a: float(np.mean(scores[a, good[a]]))
              for a in range(scores.shape[0]) if good[a].any()}
    mean_c = {c: float(np.mean(scores[good[:, c], c]))
              for c in range(scores.shape[1]) if good[:, c].any()}
    a = best(mean_a, mean_a.values(), mode, budget, start, rep, step, "method")
    c = best(mean_c, mean_c.values(), mode, budget, start, rep, step, "condition")
    cs = [i for i in range(scores.shape[1]) if good[a, i]]
    aa = [i for i in range(scores.shape[0]) if good[i, c]]
    method_pair = (a, best(cs, [scores[a, i] for i in cs],
                           mode, budget, start, rep, step, "condition_given_method"))
    condition_pair = (best(aa, [scores[i, c] for i in aa],
                           mode, budget, start, rep, step, "method_given_condition"), c)
    selected = {"joint_kg": joint, "method_first_adaptive": method_pair,
                "condition_first_adaptive": condition_pair}[policy]
    gap = float(scores[joint] - scores[selected])
    if gap < -1e-10:
        raise AssertionError("Joint KG not maximal")
    return selected, joint, gap, method_pair, condition_pair


def run_episode(Y, policy, B, start, rep, mode):
    n_methods, n_conditions = Y.shape
    seen = [(a, start, float(Y[a, start])) for a in range(n_methods)]
    events = []
    for step in range(n_methods, B):
        means, _, covs = frozen.posterior(seen, n_methods)
        used = {(a, c) for a, c, _ in seen}
        available = [(a, c, 0) for a in range(n_methods)
                     for c in range(n_conditions) if (a, c) not in used]
        gains = kg.scores_from_posterior(means, covs, available)
        matrix = np.full((n_methods, n_conditions), np.nan)
        for (a, c, _), val in zip(available, gains):
            matrix[a, c] = float(val)
        selected, joint, gap, method_pair, condition_pair = choice(
            matrix, policy, mode, B, start, rep, step)
        top = float(np.nanmax(matrix))
        n_tied = int(np.sum(np.isfinite(matrix) & (matrix >= top - TOL)))
        events.append(dict(
            mode=mode, policy=policy, budget=B, start=start, replicate=rep,
            step=step + 1, selected_method=selected[0],
            selected_condition=selected[1], joint_method=joint[0],
            joint_condition=joint[1], n_kg_tied_actions=n_tied,
            kg_gap=gap, tied_with_joint=int(gap <= TOL),
            disagrees=int(selected != joint),
            method_vs_condition_disagree=int(method_pair != condition_pair),
        ))
        a, c = selected
        seen.append((a, c, float(Y[a, c])))
    post, _, _ = frozen.posterior(seen, n_methods)
    chosen = int(np.argmin(post))
    truth = Y.mean(axis=1)
    optimal = int(np.argmin(truth))
    return dict(
        mode=mode, policy=policy, budget=B, start=start, replicate=rep,
        selected=chosen, correct=int(chosen == optimal),
        regret=max(0., float(truth[chosen] - truth[optimal]))), events


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--hashed-repeats", type=int, default=20)
    a = p.parse_args()
    matrix = a.matrix.expanduser().resolve()
    out = a.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}")
    if a.hashed_repeats < 1:
        p.error("--hashed-repeats must be >=1")
    Y = kg.load_frozen_matrix(matrix)
    terminals, actions = [], []
    for mode, reps in [("lexicographic", 1), ("shared_hash", a.hashed_repeats)]:
        for B in BUDGETS:
            for start in range(12):
                for rep in range(reps):
                    for policy in POLICIES:
                        row, trace = run_episode(Y, policy, B, start, rep, mode)
                        terminals.append(row)
                        actions.extend(trace)
            print("DONE", mode, B, flush=True)
    summary = []
    for mode in ("lexicographic", "shared_hash"):
        for B in BUDGETS:
            for policy in POLICIES:
                t = [r for r in terminals if (r["mode"], r["budget"], r["policy"]) == (mode, B, policy)]
                d = [r for r in actions if (r["mode"], r["budget"], r["policy"]) == (mode, B, policy)]
                summary.append(dict(
                    mode=mode, budget=B, policy=policy, episodes=len(t),
                    mean_regret=float(np.mean([x["regret"] for x in t])),
                    p_correct=float(np.mean([x["correct"] for x in t])),
                    disagreement=float(np.mean([x["disagrees"] for x in d])),
                    genuine_kg_loss_rate=float(np.mean([x["kg_gap"] > TOL for x in d])),
                    mean_kg_loss=float(np.mean([x["kg_gap"] for x in d])),
                    tied_action_fraction=float(np.mean([x["n_kg_tied_actions"] > 1 for x in d])),
                    mean_number_tied_actions=float(np.mean([x["n_kg_tied_actions"] for x in d])),
                ))
    out.mkdir(parents=True)
    csv_write(out / "terminals.csv", terminals)
    csv_write(out / "acquisitions.csv", actions)
    csv_write(out / "summary.csv", summary)
    manifest = dict(
        status="B1_KG_CONTROLLED_TIE_DEVELOPMENT_NOT_INDEPENDENT",
        matrix_sha256=frozen.digest(matrix),
        policies=POLICIES, budgets=BUDGETS, seed=SEED,
        methods=["lexicographic", "shared_hash"], hashed_repeats=a.hashed_repeats,
        tie_tolerance=TOL, episodes=len(terminals), actions=len(actions))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("KG_CONTROLLED_TIE_AUDIT_PASS", out)


if __name__ == "__main__":
    main()
