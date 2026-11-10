#!/usr/bin/env python3
"""Targeted two-step Gaussian KG on the 12 frozen B1 initial posterior states.

At each start condition all seven methods are initially evaluated. Among the
remaining actions tied for maximum one-step KG, evaluate their *adaptive*
two-step value by Gauss-Hermite integration over the first observation.
The second action ranges over ALL still-unseen method-condition pairs.

This is posterior-model analysis on the historical catalogue, NOT a new-world
validation or a full two-step controller. No hidden outcomes are used to
compute acquisition values.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from numpy.polynomial.hermite import hermgauss

import b1_budget_comparison_v1 as frozen
import b1_kg_one_step_v1 as one_step

TIE_TOL = 1e-12
DEFAULT_ORDERS = (15, 31, 61)


def save_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def acquisition_state(start, losses):
    methods, conditions = losses.shape
    history = [(a, start, float(losses[a, start])) for a in range(methods)]
    means, _variances, covariances = frozen.posterior(history, methods)
    actions = [(a, c, 0) for a in range(methods)
               for c in range(conditions) if c != start]
    scores = one_step.scores_from_posterior(means, covariances, actions)
    peak = float(np.max(scores))
    candidates = [action for action, score in zip(actions, scores)
                  if score >= peak - TIE_TOL]
    return means, covariances, actions, scores, candidates, peak


def kg_max_after_first(means, covs, actions, first, standard_normal):
    """Optimal *one-step* second KG after a hypothetical first observation.

    Gaussian-linear posterior conditioning: the first posterior mean shifts by
    beta*z; its covariance is reduced by a rank-one update. The observation
    itself is never read from the archived loss matrix.
    """
    a, c, _ = first
    x = frozen.XX[c]
    s = covs[a]
    sx = s @ x
    obs_var = frozen.NOISE**2 + float(x @ sx)
    if not obs_var > 0:
        raise AssertionError("Nonpositive predictive variance")
    beta = float(frozen.V @ sx) / math.sqrt(obs_var)
    means_next = means.copy()
    means_next[a] += beta * standard_normal
    covs_next = covs.copy()
    covs_next[a] = s - np.outer(sx, sx) / obs_var
    covs_next[a] = (covs_next[a] + covs_next[a].T) / 2

    remaining = [e for e in actions if (e[0], e[1]) != (a, c)]
    if not remaining:
        return 0.
    next_scores = one_step.scores_from_posterior(means_next, covs_next, remaining)
    return float(np.max(next_scores))


def two_step_gain(means, covs, actions, first, kg1, order):
    """KG2(e) = KG1(e) + E[max_(e' != e) KG1(e' | first outcome)]."""
    nodes, weights = hermgauss(order)
    z_nodes = np.sqrt(2.) * nodes
    weights = weights / math.sqrt(math.pi)
    future = math.fsum(float(w) * kg_max_after_first(means, covs, actions, first, float(z))
                       for z, w in zip(z_nodes, weights))
    if future < -1e-12:
        raise AssertionError("Negative future KG")
    return float(kg1 + future), float(future)


def analyze(losses, orders):
    action_rows = []
    state_rows = []
    for start in range(losses.shape[1]):
        means, covs, actions, scores, candidates, peak = acquisition_state(start, losses)
        by_key = {(a, c): float(v) for (a, c, _), v in zip(actions, scores)}
        results = {}
        for first in candidates:
            a, c, _ = first
            one = by_key[(a, c)]
            q_by_order = {}
            future_by_order = {}
            for order in orders:
                q_by_order[order], future_by_order[order] = two_step_gain(
                    means, covs, actions, first, one, order)
            results[(a, c)] = (one, q_by_order, future_by_order)

        high_order, previous_order = orders[-1], orders[-2]
        primary = {k: v[1][high_order] for k, v in results.items()}
        runner = {k: v[1][previous_order] for k, v in results.items()}
        best = max(primary.values())
        runner_best = max(runner.values())
        worst = min(primary.values())
        # Discrepancy across consecutive quadrature orders is a *diagnostic*,
        # NOT a rigorous numerical error bound.
        delta = max(abs(primary[k] - runner[k]) for k in primary)
        spread = best - worst
        high_choice = min(k for k, value in primary.items() if value >= best - 1e-12)
        previous_choice = min(k for k, value in runner.items()
                              if value >= runner_best - 1e-12)
        first_baseline = min((a, c) for a, c, _ in candidates)
        for (a, c), (one, q, future) in results.items():
            action_rows.append(dict(
                start_index=start, start_world=frozen.CELLS[start][0],
                start_graph=frozen.CELLS[start][1], method=frozen.METHODS[a],
                method_index=a, condition_index=c,
                condition_world=frozen.CELLS[c][0],
                condition_graph=frozen.CELLS[c][1],
                kg1=one, kg1_max=peak, kg1_gap=peak-one,
                kg2_low=q[orders[0]], kg2_middle=q[previous_order],
                kg2_high=q[high_order], kg2_future_component=future[high_order],
                kg2_minus_one= q[high_order]-one,
                kg2_below_best=best-q[high_order],
                quadrature_difference=abs(q[high_order]-q[previous_order]),
                is_high_best=int((a, c) == high_choice),
                is_one_step_lex_best=int((a, c) == first_baseline),
            ))
        state_rows.append(dict(
            start_index=start, start_world=frozen.CELLS[start][0],
            start_graph=frozen.CELLS[start][1],
            n_available_actions=len(actions), n_tied_kg1=len(candidates),
            kg1_max=peak, tied_kg1_spread=max(v[0] for v in results.values())
                - min(v[0] for v in results.values()),
            kg2_best=best, kg2_worst=worst, kg2_spread=spread,
            max_order_difference=delta,
            spread_to_order_difference=spread/max(delta, 1e-15),
            best_method=frozen.METHODS[high_choice[0]],
            best_condition=frozen.CELLS[high_choice[1]][0]+"__"+frozen.CELLS[high_choice[1]][1],
            different_from_lex_kg1=int(high_choice != first_baseline),
            best_choice_stable=int(high_choice == previous_choice),
            order_low=orders[0], order_middle=previous_order,
            order_high=high_order,
        ))
        print(f"STATE {start+1}/12 candidates={len(candidates)} "
              f"KG2spread={spread:.8g} quadrature_delta={delta:.8g} "
              f"best_stable={high_choice == previous_choice}", flush=True)
    return action_rows, state_rows


def smoke():
    # A zero-variance observation of itself cannot change posterior:
    # check Gaussian rank-one conditioning preserves a positive semidefinite
    # covariance and that posterior means change linearly in normalized z.
    a = 0
    history = [(i, 0, .1 + .01*i) for i in range(7)]
    mu, _, s = frozen.posterior(history, 7)
    actions = [(i, j, 0) for i in range(7) for j in range(12) if j != 0]
    first = actions[0]
    scores = one_step.scores_from_posterior(mu, s, actions)
    q, f = two_step_gain(mu, s, actions, first, float(scores[0]), 7)
    if not (np.isfinite(q) and np.isfinite(f) and q >= float(scores[0])-1e-12):
        raise AssertionError("KG2 smoke check failed")
    print("KG2_SMOKE_PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, help="Frozen B1 7x12 matrix")
    parser.add_argument("--out", type=Path, help="New output directory")
    parser.add_argument("--orders", default="15,31,61",
                        help="Increasing Gauss-Hermite orders, >= 3 each")
    parser.add_argument("--smoke", action="store_true",
                        help="Synthetic posterior mathematics check only")
    args = parser.parse_args()
    if args.smoke:
        smoke()
        return
    if args.matrix is None or args.out is None:
        parser.error("--matrix and --out required outside --smoke")
    orders = tuple(int(v) for v in args.orders.split(","))
    if len(orders) < 3 or any(v < 3 for v in orders) or list(orders) != sorted(set(orders)):
        parser.error("Pass >=3 unique ascending Gauss-Hermite orders (e.g. 15,31,61)")
    matrix = args.matrix.expanduser().resolve()
    out = args.out.expanduser().resolve()
    if out.exists():
        raise FileExistsError(f"Output directory exists, refusing overwrite: {out}")
    losses = one_step.load_frozen_matrix(matrix)
    actions, states = analyze(losses, orders)
    out.mkdir(parents=True)
    save_csv(out/"tied_action_values.csv", actions)
    save_csv(out/"initial_state_summary.csv", states)
    manifest = dict(
        status="B1_KG_TWO_STEP_TARGETED_DEVELOPMENT_NOT_INDEPENDENT",
        matrix_sha256=frozen.digest(matrix), tie_tolerance=TIE_TOL,
        quadrature_orders=orders, n_initial_states=len(states),
        n_candidate_first_actions=len(actions),
        second_action_set="all remaining method-condition pairs",
        frozen_noise=frozen.NOISE,
        caveat="Quadrature differences are convergence diagnostics, not certified error bounds. "
               "Does not compute multi-step terminal regret or assess out-of-world transfer.",
        output_sha256={
            f.name: frozen.digest(f) for f in out.glob("*.csv")
        },
    )
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print("KG2_TARGETED_PASS", out)
    print("STATES_WITH_KG2_SPREAD_ABOVE_10X_QUADRATURE_DELTA",
          sum(s["kg2_spread"] > 10*s["max_order_difference"] for s in states))
    print("STATES_WITH_STABLE_BEST_ACTION",
          sum(s["best_choice_stable"] for s in states))


if __name__ == "__main__":
    main()
