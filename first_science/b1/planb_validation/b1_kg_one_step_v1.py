#!/usr/bin/env python3
"""One-step Gaussian knowledge gradient for the frozen PRAISE B1 setup.

Does not alter or recompute existing B1 policies, predictor outputs, or WB data.
Only uses the existing read-only Gaussian posterior. No simulator imports.
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

NAME = "kg_one_step"
KG_POLICY_ID = len(frozen.POLICIES)
EXPECTED_MATRIX_SHA256 = "0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d"
EXPECTED_BASELINE_EPISODES_SHA256 = "c219b700d55683899867051f3cf1f154cea54655853026c47fda814c887d9f12"
EXPECTED_BUDGETS = (10, 15, 20, 30, 40)
EXPECTED_REPEATS = 20
EXPECTED_BOOTSTRAPS = 2000
EXPECTED_SEED = 20261105
ROOT2PI = math.sqrt(2.0 * math.pi)
ROOT2 = math.sqrt(2.0)


def kg_gain(gap: float, shift_std: float) -> float:
    """Exact one-step Gaussian KG under independent posterior algorithm means.

    gap = abs(posterior mean of a - minimum other posterior mean).
    shift_std = SD of the would-be UPDATED posterior mean of a.
    The score is expected reduction in minimum posterior mean (loss).
    """
    if not (math.isfinite(gap) and math.isfinite(shift_std)):
        raise ValueError("Nonfinite KG input")
    if gap < 0 or shift_std < 0:
        raise ValueError("KG requires nonnegative gap/shift_std")
    if shift_std == 0:
        return 0.0
    z = gap / shift_std
    pdf = math.exp(-0.5 * z * z) / ROOT2PI
    sf = 0.5 * math.erfc(z / ROOT2)
    return max(0.0, shift_std * pdf - gap * sf)


def scores_from_posterior(means, covs, available):
    """KG scores of available (algorithm, cell, placeholder) triples.

    Frozen B1 assumes independent parameter vectors across algorithms;
    observation of a/c updates only its own algorithm's posterior mean.
    """
    means = np.asarray(means, dtype=float)
    covs = np.asarray(covs, dtype=float)
    if means.ndim != 1 or means.size < 2:
        raise ValueError("Need at least two candidate algorithms")
    if covs.shape != (means.size, 8, 8):
        raise ValueError("Posterior covariance shape inconsistent with B1 design")
    if not (np.isfinite(means).all() and np.isfinite(covs).all()):
        raise ValueError("Nonfinite Gaussian posterior")
    if not available:
        raise ValueError("No remaining actions")
    competitor = np.array([min(means[b] for b in range(means.size) if b != a)
                           for a in range(means.size)])
    gap = np.abs(means - competitor)
    gains = np.empty(len(available), dtype=float)
    v = frozen.V
    for i, (a, cell, _placeholder) in enumerate(available):
        if not (0 <= a < means.size and 0 <= cell < len(frozen.CELLS)):
            raise ValueError("Action outside frozen B1 catalogue")
        x = frozen.XX[cell]
        s = covs[a]
        predictive_variance = frozen.NOISE**2 + float(x @ s @ x)
        if predictive_variance <= 0:
            raise ValueError("Nonpositive predictive observation variance")
        posterior_mean_shift_sd = abs(float(v @ s @ x)) / math.sqrt(predictive_variance)
        gains[i] = kg_gain(float(gap[a]), posterior_mean_shift_sd)
    return gains


def select_kg(seen, rng, methods=7):
    observed = {(a, c) for a, c, _ in seen}
    if len(observed) != len(seen):
        raise ValueError("An action was observed twice")
    available = [(a, c, 0) for a in range(methods)
                 for c in range(len(frozen.CELLS)) if (a, c) not in observed]
    if not available:
        raise ValueError("No remaining actions")
    posterior_means, _, covs = frozen.posterior(seen, methods)
    return frozen.choose_tie(available,
                             scores_from_posterior(posterior_means, covs, available), rng)


def episode(matrix, budget, starting_cell, repeat, seed=EXPECTED_SEED):
    if matrix.shape != (len(frozen.METHODS), len(frozen.CELLS)):
        raise ValueError("KG benchmark requires verified 7x12 matrix")
    if budget not in EXPECTED_BUDGETS:
        raise ValueError("Must use an original frozen evaluation budget")
    if not 0 <= starting_cell < len(frozen.CELLS) or not 0 <= repeat < EXPECTED_REPEATS:
        raise ValueError("Initial cell or repetition outside frozen B1 design")
    rng = np.random.default_rng(
        np.random.SeedSequence([seed, budget, starting_cell, repeat, KG_POLICY_ID]))
    seen = [(a, starting_cell, float(matrix[a, starting_cell]))
            for a in range(len(frozen.METHODS))]
    for step in range(len(frozen.METHODS), budget):
        a, c = select_kg(seen, rng, len(frozen.METHODS))
        if (a, c) in {(aa, cc) for aa, cc, _ in seen}:
            raise AssertionError("KG selected an already evaluated action")
        seen.append((a, c, float(matrix[a, c])))
    final_mu, _, _ = frozen.posterior(seen)
    selected = int(np.argmin(final_mu))
    truth = matrix.mean(axis=1)
    best = int(np.argmin(truth))
    terminal = dict(budget=budget,
                    start_cell=f"{frozen.CELLS[starting_cell][0]}__{frozen.CELLS[starting_cell][1]}",
                    start_index=starting_cell, replicate=repeat, policy=NAME,
                    evaluations=len(seen), recommended=frozen.METHODS[selected],
                    correct=int(selected == best),
                    simple_regret=max(0.0, float(truth[selected] - truth[best])))
    trace = [dict(budget=budget, start_index=starting_cell, replicate=repeat,
                  policy=NAME, step=j + 1, method=frozen.METHODS[a],
                  world=frozen.CELLS[c][0], graph=frozen.CELLS[c][1], mae=value)
             for j, (a, c, value) in enumerate(seen)]
    return terminal, trace


def load_frozen_matrix(path: Path):
    if frozen.digest(path) != EXPECTED_MATRIX_SHA256:
        raise ValueError("Seven-method matrix SHA-256 does not match B1 freeze")
    data = np.full((7, 12), np.nan)
    rows = frozen.read_csv(path)
    for item in rows:
        m = item["method"]
        key = (item["world"], item["graph"])
        if m not in frozen.METHODS or key not in frozen.CELLS:
            raise ValueError("Unknown algorithm or cell in B1 matrix")
        i, j = frozen.METHODS.index(m), frozen.CELLS.index(key)
        if math.isfinite(float(data[i, j])):
            raise ValueError("Duplicate method/cell")
        data[i, j] = float(item["mae"])
    if len(rows) != 84 or not np.isfinite(data).all():
        raise ValueError("B1 matrix must contain exactly 84 finite distinct MAEs")
    return data


def load_frozen_episodes(path: Path):
    if frozen.digest(path) != EXPECTED_BASELINE_EPISODES_SHA256:
        raise ValueError("Original B1 episode file SHA-256 does not match frozen evidence")
    baseline = {}
    for row in frozen.read_csv(path):
        policy = row["policy"]
        budget, start, rep = (int(row["budget"]), int(row["start_index"]),
                              int(row["replicate"]))
        if (policy not in frozen.POLICIES or budget not in EXPECTED_BUDGETS or
                not 0 <= start < 12 or not 0 <= rep < EXPECTED_REPEATS or
                int(row["evaluations"]) != budget):
            raise ValueError("Unrecognized original B1 episode")
        key = (budget, start, rep, policy)
        if key in baseline:
            raise ValueError("Duplicate original B1 episode")
        baseline[key] = dict(regret=float(row["simple_regret"]),
                             correct=int(row["correct"]))
    if len(baseline) != 4800:
        raise ValueError("Original four-policy replay must contain 4800 episodes")
    return baseline


def bootstrap_summary(kg_rows, baseline, repetitions=EXPECTED_BOOTSTRAPS, seed=EXPECTED_SEED):
    """Separate *supplementary* B1 KG vs frozen baseline comparison.

    Conditions on the fixed archive, 12 starting cells, matched replicate IDs.
    Uses new, documented bootstrap RNG; never changes B1 v1 bootstrap files.
    """
    rng = np.random.default_rng(seed + 913)
    grouped = {(int(x["budget"]), int(x["start_index"]), int(x["replicate"])): x
               for x in kg_rows}
    if len(grouped) != 1200:
        raise ValueError("KG requires exactly 1200 episodes")
    summaries, contrasts = [], []
    for B in EXPECTED_BUDGETS:
        current = [grouped[(B, c, rep)] for c in range(12) for rep in range(EXPECTED_REPEATS)]
        regret = np.asarray([float(x["simple_regret"]) for x in current]).reshape(12, EXPECTED_REPEATS)
        correct = np.asarray([int(x["correct"]) for x in current]).reshape(12, EXPECTED_REPEATS)
        draws = rng.integers(EXPECTED_REPEATS, size=(repetitions, 12, EXPECTED_REPEATS))
        rboot = np.take_along_axis(regret[None, :, :], draws, axis=2).mean(axis=(1, 2))
        cboot = np.take_along_axis(correct[None, :, :], draws, axis=2).mean(axis=(1, 2))
        summaries.append(dict(budget=B,policy=NAME,episodes=240,
                              mean_regret=float(regret.mean()),
                              regret_low=float(np.quantile(rboot,.025)),
                              regret_high=float(np.quantile(rboot,.975)),
                              p_correct=float(correct.mean()),
                              p_low=float(np.quantile(cboot,.025)),
                              p_high=float(np.quantile(cboot,.975)),
                              regret_p90=float(np.quantile(regret,.90))))
        for policy in frozen.POLICIES:
            other = np.array([baseline[(B,c,rep,policy)]["regret"]
                              for c in range(12) for rep in range(EXPECTED_REPEATS)]).reshape(12,EXPECTED_REPEATS)
            diff = regret - other
            bdiff = np.take_along_axis(diff[None,:,:],draws,axis=2).mean(axis=(1,2))
            contrasts.append(dict(budget=B,contrast=f"{NAME} minus {policy}",
                                  mean_regret_diff=float(diff.mean()),
                                  low=float(np.quantile(bdiff,.025)),
                                  high=float(np.quantile(bdiff,.975))))
    # Whole matched starting-cell/repetition draws across all five budgets.
    draws = rng.integers(EXPECTED_REPEATS,size=(repetitions,12,EXPECTED_REPEATS))
    for policy in frozen.POLICIES:
        per_budget = []
        for B in EXPECTED_BUDGETS:
            val = np.array([grouped[(B,c,rep)]["simple_regret"] -
                           baseline[(B,c,rep,policy)]["regret"]
                           for c in range(12) for rep in range(EXPECTED_REPEATS)]).reshape(12,EXPECTED_REPEATS)
            per_budget.append(val)
        arr = np.array(per_budget)
        bdiff = np.stack([np.take_along_axis(v[None,:,:],draws,axis=2).mean(axis=(1,2))
                          for v in arr],axis=1).mean(axis=1)
        contrasts.append(dict(budget="MEAN_OVER_5_BUDGETS",contrast=f"{NAME} minus {policy}",
                              mean_regret_diff=float(arr.mean()),
                              low=float(np.quantile(bdiff,.025)),
                              high=float(np.quantile(bdiff,.975))))
    return summaries, contrasts


def write_csv(path,rows):
    if not rows:
        raise ValueError("Cannot write an empty evidence file")
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.DictWriter(f,fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)


def run(matrix_path: Path, baseline_path: Path, output_root: Path, repetitions=EXPECTED_BOOTSTRAPS):
    if repetitions != EXPECTED_BOOTSTRAPS:
        raise ValueError("KG preflight freezes 2000 bootstrap replicates")
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing KG output: {output_root}")
    matrix = load_frozen_matrix(matrix_path)
    baseline = load_frozen_episodes(baseline_path)
    terminals, actions = [], []
    for B in EXPECTED_BUDGETS:
        for c in range(12):
            for rep in range(EXPECTED_REPEATS):
                terminal, trace = episode(matrix, B, c, rep)
                terminals.append(terminal)
                actions.extend(trace)
    if len(terminals) != 1200 or len(actions) != 27600:
        raise AssertionError("Unexpected KG episode/action count")
    summaries, contrasts = bootstrap_summary(terminals, baseline, repetitions)
    output_root.mkdir(parents=True)
    write_csv(output_root/"kg_terminal_episodes.csv",terminals)
    write_csv(output_root/"kg_action_history.csv",actions)
    write_csv(output_root/"kg_budget_summary.csv",summaries)
    write_csv(output_root/"kg_vs_frozen_b1_contrasts.csv",contrasts)
    source = Path(__file__).resolve()
    frozen_code = Path(frozen.__file__).resolve()
    files = sorted(output_root.glob("*.csv"))
    manifest = dict(status="B1_SUPPLEMENTARY_ONE_STEP_KG_DEVELOPMENT_V1",
                    protocol="B1_KG_ONE_STEP_SPECIFICATION_V1",
                    meaning="retrospective supplemental comparison on original B1 archive, NOT independent validation",
                    source_sha256={str(source):frozen.digest(source),str(frozen_code):frozen.digest(frozen_code)},
                    baseline_matrix_sha256=frozen.digest(matrix_path),
                    baseline_terminal_episodes_sha256=frozen.digest(baseline_path),
                    policy=NAME, policy_id=KG_POLICY_ID,
                    budgets=EXPECTED_BUDGETS, repeats_per_start=EXPECTED_REPEATS,
                    bootstrap_replicates=repetitions,seed=EXPECTED_SEED,
                    bootstrap_seed=EXPECTED_SEED+913,
                    same_terminal_estimator_as_B1=True,
                    original_B1_four_policies_mutated=False,
                    reference_best=frozen.METHODS[int(np.argmin(matrix.mean(axis=1)))],
                    output_sha256={p.name:frozen.digest(p) for p in files})
    (output_root/"kg_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("B1_KG_SUPPLEMENTARY_REPLAY_PASS")
    for r in summaries:print("KG",r)
    for c in contrasts:
        if c["budget"] == "MEAN_OVER_5_BUDGETS":print("KG_CONTRAST",c)
    print("OUTPUT",output_root)
    return summaries, contrasts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--baseline-terminal",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mode",choices=("inspect","replay"),default="inspect")
    args=p.parse_args()
    matrix,baseline,out=(x.expanduser().resolve() for x in
                         (args.matrix,args.baseline_terminal,args.out))
    if args.mode == "inspect":
        print("KG_MATRIX_HASH",frozen.digest(matrix),"PASS" if frozen.digest(matrix) == EXPECTED_MATRIX_SHA256 else "FAIL")
        print("KG_ORIGINAL_EPISODES_HASH",frozen.digest(baseline),"PASS" if frozen.digest(baseline) == EXPECTED_BASELINE_EPISODES_SHA256 else "FAIL")
        print("B1_KG_INSPECT_ONLY_NO_REPLAY")
        return
    run(matrix,baseline,out)


if __name__ == "__main__":
    main()
