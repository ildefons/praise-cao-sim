#!/usr/bin/env python3
"""Read-only PRAISE B1 white-box robustness audit.

Uses immutable B1 v1 policies, frozen predictions and 1,000 complete WB
trajectories per cell. No new simulations, policy training or world sampling.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b1_budget_comparison_v1 as b1

SEED = 20261106
Q = 555
N = 1000
METHOD_SOURCES = {
    "M1": ("phaseII", "m1_predictions.csv", "M1"),
    "M2": ("phaseII", "m2_predictions.csv", "M2"),
    "M3_FULL343": ("phaseII", "m3_predictions_full343_and_nested.csv", "M3_FULL343"),
    "ORIGINAL_TOP14_B1400": ("original", "top14_predictions.csv", "ORIGINAL_TOP14_B1400"),
    "ORIGINAL_TOP1_B1400": ("original", "top1_predictions.csv", "ORIGINAL_TOP1_B1400"),
    "FIXED_CV_TOP14": ("fixedCV", "top14_predictions.csv", "B1_FIXED_CV_TOP14_B1400"),
    "FIXED_CV_TOP1": ("fixedCV", "top1_predictions.csv", "B1_FIXED_CV_TOP1_B1400"),
}


def source_paths(repo, kind, cell, filename):
    root = repo / "first_science/phase5/results"
    if kind == "phaseII":
        directory = root / "04_prediction_v3b_fullsupport" / cell
        key = {"m1_predictions.csv": "m1_predictions",
               "m2_predictions.csv": "m2_predictions",
               "m3_predictions_full343_and_nested.csv": "m3_predictions_full343_and_nested"}[filename]
        status = "FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION"
    elif kind == "original":
        directory = root / "b1_pilot_m3_retrospective_v1/predictions" / cell
        key = filename
        status = "B1_RETROSPECTIVE_CELL_PREDICTED"
    else:
        directory = root / "b1_fixed_cv_top1_top14_b1400_v1/predictions" / cell
        key = filename
        status = "B1_FIXED_CV_CELL_PREDICTED"
    return directory / filename, directory / "prediction_manifest.json", key, status


def verify_curve(repo, kind, cell, filename):
    curve, path, key, status = source_paths(repo, kind, cell, filename)
    if not curve.is_file() or not path.is_file():
        raise FileNotFoundError(f"Missing frozen prediction or manifest: {curve}, {path}")
    manifest = json.loads(path.read_text())
    if manifest.get("status") != status:
        raise ValueError(f"Prediction freeze status changed: {path}")
    if kind == "phaseII":
        if manifest.get("inputs", {}).get("final_WB_read") is not False:
            raise ValueError(f"White-box firewall invalid: {path}")
        recorded = manifest.get("output_hashes_sha256", {}).get(key)
    else:
        if manifest.get("reference_whitebox_read") is not False:
            raise ValueError(f"White-box firewall invalid: {path}")
        recorded = manifest.get("outputs_sha256", {}).get(key)
    if recorded is None or recorded != b1.digest(curve):
        raise ValueError(f"Prediction file changed since freeze: {curve}")
    return curve


def make_outcomes_from_ledgers(repo, out):
    """Derive binary outcomes from saved WB ledgers, never rerun simulations."""
    root = repo / "first_science/phase5"
    sys.path.insert(0, str(root))
    import run_phase5_wb_reference_bootstrap_v3b_fullsupport as original
    metas, arrays = [], []
    for world, graph in b1.CELLS:
        cell = f"{world}__{graph}"
        frame, block = original._cell_outcomes(cell)
        metas.append(frame)
        arrays.append(block)
        print("RECONSTRUCTED_FROM_ARCHIVED_WB_LEDGER", cell, flush=True)
    meta = pd.concat(metas, ignore_index=True)
    matrix = np.concatenate(arrays, axis=1)
    meta.insert(0, "point_index", np.arange(len(meta), dtype=int))
    cache = out / "_derived_binary_outcomes"
    cache.mkdir(parents=True, exist_ok=True)
    meta_path, matrix_path = cache / "wb_primary_outcome_columns.csv", cache / "wb_primary_trajectory_outcomes.npz"
    if meta_path.exists() or matrix_path.exists():
        raise FileExistsError("Refusing to replace an existing derived WB outcome cache")
    meta.to_csv(meta_path, index=False)
    np.savez_compressed(matrix_path, outcomes=matrix)
    return meta_path, matrix_path


def load_outcomes(meta_path, matrix_path):
    if not meta_path.is_file() or not matrix_path.is_file():
        raise FileNotFoundError(f"Missing WB outcome cache: {meta_path}, {matrix_path}")
    meta = pd.read_csv(meta_path)
    with np.load(matrix_path, allow_pickle=False) as z:
        if "outcomes" not in z.files:
            raise ValueError("WB NPZ missing 'outcomes'")
        outcomes = z["outcomes"]
    if outcomes.shape != (N, 12*Q) or len(meta) != 12*Q:
        raise ValueError(f"WB trajectory matrix must be 1000 x 6660; got {outcomes.shape}")
    needed = {"physical_cell_id", "query_id", "H", "sigma_wb"}
    if not needed.issubset(meta):
        raise ValueError(f"WB metadata columns missing {needed-set(meta)}")
    if "point_index" in meta and not np.array_equal(meta.point_index.to_numpy(), np.arange(12*Q)):
        raise ValueError("WB point_index does not match outcome-column order")
    if not np.issubdtype(outcomes.dtype, np.integer) or not np.all((outcomes == 0) | (outcomes == 1)):
        raise ValueError("WB outcomes must be binary")
    order = []
    for world, graph in b1.CELLS:
        cell = f"{world}__{graph}"
        take = np.flatnonzero(meta.physical_cell_id.astype(str).eq(cell).to_numpy())
        if len(take) != Q:
            raise ValueError(f"Expected exactly 555 WB columns for {cell}")
        block = meta.iloc[take]
        if block[["query_id", "H"]].duplicated().any() or not block.H.between(60,240).all() or block.H.nunique() != 37:
            raise ValueError(f"Invalid query/H keys in {cell}")
        order.extend(take.tolist())
    if len(set(order)) != 12*Q:
        raise ValueError("WB column partition incomplete")
    meta = meta.iloc[order].reset_index(drop=True)
    outcomes = outcomes[:, order]
    if not np.allclose(outcomes.mean(axis=0), meta.sigma_wb.to_numpy(float), atol=1e-10, rtol=0):
        raise ValueError("Binary WB outcome matrix fails to reproduce frozen WB sigma")
    return meta, outcomes


def cell_maes(pred, sigma):
    return np.abs(pred-sigma[None,:]).reshape(7,12,Q).mean(axis=2)


def load_predictions(repo, meta, original_matrix):
    pred = np.empty((7,12*Q), dtype=float)
    hashes = {}
    for a, name in enumerate(b1.METHODS):
        kind, filename, raw_method = METHOD_SOURCES[name]
        for c, (world, graph) in enumerate(b1.CELLS):
            cell = f"{world}__{graph}"
            path = verify_curve(repo, kind, cell, filename)
            frame = pd.read_csv(path)
            required = {"method_id", "query_id", "H", "sigma_hat"}
            if not required.issubset(frame):
                raise ValueError(f"Prediction columns missing in {path}")
            frame = frame.loc[frame.method_id.astype(str).eq(raw_method) & frame.H.between(60,240)].copy()
            if len(frame) != Q or frame[["query_id","H"]].duplicated().any():
                raise ValueError(f"Incomplete/duplicate frozen prediction: {path}")
            left = meta.iloc[c*Q:(c+1)*Q][["query_id","H"]].copy()
            left["query_id"] = left.query_id.astype(str)
            frame["query_id"] = frame.query_id.astype(str)
            aligned = left.merge(frame[["query_id","H","sigma_hat"]],
                                 on=["query_id","H"], validate="one_to_one", how="left", sort=False)
            values = aligned.sigma_hat.to_numpy(float)
            if len(values)!=Q or not np.isfinite(values).all() or np.any((values<0)|(values>1)):
                raise ValueError(f"Unmatched/invalid frozen probabilities: {path}")
            pred[a,c*Q:(c+1)*Q] = values
            hashes[str(path.relative_to(repo))] = b1.digest(path)
    actual = cell_maes(pred, meta.sigma_wb.to_numpy(float))
    error = np.max(np.abs(actual-original_matrix))
    if error > 2e-8:
        raise ValueError(f"Pointwise prediction / original 84-MAE matrix mismatch: {error:.9g}")
    return pred, hashes


def decision_frequencies(b1_results, matrix):
    path = b1_results / "run_manifest.json"
    manifest = json.loads(path.read_text())
    if manifest.get("status")!="B1_FIXED_BUDGET_DEVELOPMENT_REPLAY_V1":
        raise ValueError("Previous replay manifest status changed")
    if tuple(manifest.get("methods",[]))!=tuple(b1.METHODS) or tuple(manifest.get("budgets",[]))!=tuple(b1.BUDGETS) or tuple(manifest.get("policies",[]))!=tuple(b1.POLICIES):
        raise ValueError("Previous replay specification changed")
    for name, digest in manifest.get("outputs_sha256",{}).items():
        file = b1_results / name
        if not file.is_file() or b1.digest(file) != digest:
            raise ValueError(f"Frozen B1 replay output altered: {file}")
    episodes = pd.read_csv(b1_results/"terminal_episodes.csv")
    n = 12*int(manifest["repeats_per_start_cell"])
    if len(episodes)!=len(b1.BUDGETS)*len(b1.POLICIES)*n:
        raise ValueError("Wrong previous replay episode count")
    original_mu = matrix.mean(axis=1)
    names = {name:i for i,name in enumerate(b1.METHODS)}
    regret = np.array([original_mu[names[name]]-original_mu.min() for name in episodes.recommended])
    if not np.allclose(episodes.simple_regret.to_numpy(float),regret,atol=1e-10,rtol=0):
        raise ValueError("Previous episode regret does not match frozen matrix")
    counts = episodes.groupby(["budget","policy","recommended"]).size().unstack(fill_value=0)
    indices = pd.MultiIndex.from_product([b1.BUDGETS,b1.POLICIES],names=["budget","policy"])
    counts = counts.reindex(index=indices,columns=b1.METHODS,fill_value=0)
    if not (counts.sum(axis=1)==n).all():
        raise ValueError("Previous replay strata incomplete")
    return counts.to_numpy(float)/n, manifest


def reference_bootstrap(outcomes, predictions, frequencies, matrix, reps, seed):
    rng = np.random.default_rng(seed)
    original_winner = int(matrix.mean(axis=1).argmin())
    records = []
    for k in range(reps):
        sample = rng.integers(N,size=N)
        reference = outcomes[sample].mean(axis=0)
        means = cell_maes(predictions,reference).mean(axis=1)
        winner = int(np.argmin(means))
        r = {"replicate":k,"winner":b1.METHODS[winner],
             "original_winner_still_best":int(winner==original_winner),
             "margin_to_second":float(np.partition(means,1)[1]-means[winner])}
        for a,name in enumerate(b1.METHODS):
            r["mu_"+name]=float(means[a])
        for j,B in enumerate(b1.BUDGETS):
            regret = {}
            for i,policy in enumerate(b1.POLICIES):
                regret[policy] = float(frequencies[j*len(b1.POLICIES)+i]@means-means[winner])
            r[f"B{B}_top2_minus_balanced"] = regret["budgeted_top2"]-regret["balanced"]
            r[f"B{B}_top2_regret"] = regret["budgeted_top2"]
            r[f"B{B}_balanced_regret"] = regret["balanced"]
        r["primary_diff_mean_5B"] = float(np.mean([r[f"B{B}_top2_minus_balanced"] for B in b1.BUDGETS]))
        records.append(r)
        if (k+1)%100 == 0:print("WB_REFERENCE_BOOTSTRAP",k+1,"/",reps,flush=True)
    return pd.DataFrame.from_records(records)


def split_episode(training, scoring, policy, B, start, replicate, seed, split_id, orientation):
    rng=np.random.default_rng(np.random.SeedSequence(
        [seed,B,start,replicate,b1.POLICIES.index(policy),split_id,orientation]))
    m=7
    seen=[(a,start,float(training[a,start])) for a in range(m)]
    for _ in range(m,B):
        a,c=b1.select_action(policy,seen,B,rng,m)
        if any(aa==a and cc==c for aa,cc,_ in seen):
            raise AssertionError("Duplicate action in disjoint-reference replay")
        seen.append((a,c,float(training[a,c])))
    means,_,_=b1.posterior(seen,m)
    choice=int(means.argmin())
    truth=scoring.mean(axis=1)
    winner=int(truth.argmin())
    return max(0.,float(truth[choice]-truth[winner])),int(choice==winner),b1.METHODS[winner]


def split_replay(outcomes,pred,pairs,repeats,seed):
    rng=np.random.default_rng(seed+997)
    records=[]
    for split in range(pairs):
        ids=rng.permutation(N)
        train1=cell_maes(pred,outcomes[ids[:500]].mean(axis=0))
        train2=cell_maes(pred,outcomes[ids[500:]].mean(axis=0))
        for direction,(training,scoring) in enumerate(((train1,train2),(train2,train1))):
            for B in b1.BUDGETS:
                for start in range(12):
                    for rep in range(repeats):
                        for policy in b1.POLICIES:
                            regret,correct,best=split_episode(training,scoring,policy,B,start,rep,seed,split,direction)
                            records.append({"split":split,"direction":direction,
                                "budget":B,"start":start,"replicate":rep,
                                "policy":policy,"terminal_regret":regret,
                                "correct":correct,"reference_best":best})
        print("WB_DISJOINT_SPLIT_REPLAY",split+1,"/",pairs,"pairs",flush=True)
    return pd.DataFrame.from_records(records)


def write_results(out,ref,split,original_means,reps,pairs):
    ref.to_csv(out/"wb_reference_bootstrap_draws.csv",index=False)
    freq=ref.winner.value_counts().reindex(b1.METHODS,fill_value=0)
    pd.DataFrame({"winner":freq.index,"n_draws":freq.values,
                  "frequency":freq.to_numpy()/reps}).to_csv(out/"reference_winner_frequency.csv",index=False)
    contrasts=[]
    for B in b1.BUDGETS:
        d=ref[f"B{B}_top2_minus_balanced"].to_numpy(float)
        contrasts.append({"budget":B,"difference_mean":float(d.mean()),
                          "q025":float(np.quantile(d,.025)),
                          "q975":float(np.quantile(d,.975)),
                          "fraction_better":float(np.mean(d<0))})
    pd.DataFrame(contrasts).to_csv(out/"reference_sensitivity_by_budget.csv",index=False)
    split_difference = None
    if split is not None:
        split.to_csv(out/"disjoint_half_terminal_episodes.csv",index=False)
        split.groupby(["budget","policy"]).agg(
            episodes=("terminal_regret","size"),mean_regret=("terminal_regret","mean"),
            pbest=("correct","mean")).reset_index().to_csv(out/"disjoint_half_budget_summary.csv",index=False)
        paired=split.pivot(index=["split","direction","budget","start","replicate"],
                           columns="policy",values="terminal_regret")
        diff=paired["budgeted_top2"]-paired["balanced"]
        by=diff.groupby("budget").agg(["mean","std","count"]).reset_index()
        by.columns=["budget","difference_mean","episode_std","n_episodes"]
        by.to_csv(out/"disjoint_half_paired_regret.csv",index=False)
        split_difference=float(diff.mean())
    d=ref.primary_diff_mean_5B.to_numpy(float)
    lo,hi=np.quantile(d,[.025,.975])
    rank_fraction=float(ref.original_winner_still_best.mean())
    gap=ref["mu_M2"]-ref["mu_M3_FULL343"]
    gap_lo,gap_hi=np.quantile(gap,[.025,.975])
    # Screening gates were fixed before inspecting these WB robustness results.
    gates={"seven_method_source_reproduced":True,
           "reference_best_frequency_ge_0_90":rank_fraction>=.90,
           "rescored_primary_CI_entirely_negative":hi<0,
           "disjoint_halves_aggregate_mean_negative":split_difference is not None and split_difference<0}
    passed=all(gates.values())
    report=[
        "# B1 WB-reference uncertainty: results (development only)","",
        "All seven methods were scored using the same trajectory-resampled WB reference. "
        "All 84 original cell MAEs were reproduced exactly within numerical tolerance.",
        "",
        f"- Reference-original-best stability: **{rank_fraction:.1%}** of {reps} WB bootstrap draws.",
        f"- M2 minus M3 original MAE gap: **{original_means[1]-original_means[2]:.6f}**.",
        f"- M2 minus M3 bootstrap percentile 95% interval: **[{gap_lo:.6f}, {gap_hi:.6f}]**.",
        f"- Frozen-recommendation primary contrast Top2 minus balanced: **{d.mean():+.6f}**, "
        f"WB-resampling 95% interval **[{lo:+.6f}, {hi:+.6f}]**.",
        f"- Fraction of reference bootstrap draws favoring Top2: **{(d<0).mean():.1%}**.",
        "- The above rescores *original frozen recommendations*: it does not rerun allocation after WB noise.",
        "",
        "## Disjoint-half stress test","",
        f"- {pairs} random 500/500 partitions in both directions; policies rerun with unchanged rules."
        if split is not None else "- Not requested.",
        f"- Top2 minus balanced mean regret, half-reference scoring: **{split_difference:+.6f}**."
        if split_difference is not None else "- No split result.",
        "- These halves are independent at the trajectory-index level *within the same fixed worlds*; "
        "four overlapping random partitions do not constitute independent world samples.",
        "",
        "## Predeclared screening gate (not an independent-world hypothesis test)","",
    ]
    report.extend([f"- {k}: **{'PASS' if v else 'HOLD'}**" for k,v in gates.items()])
    report += ["",f"**Screening outcome: {'ELIGIBLE TO PLAN independent-world validation' if passed else 'HOLD independent-world validation pending review'}.**",
        "This does not authorize new simulations automatically. A prospective new-world "
        "protocol, budget and stopping rules must be independently specified before running.",
        "",
        "## Limitations","",
        "- Retrospective post-development robustness only. No new provider worlds or graph types.",
        "- Original 555 query–horizon observations per cell are correlated; only whole WB trajectories were resampled.",
        "- Original algorithm predictions are frozen; predictor-side Monte Carlo error is not resampled.",
        "- Fixed-recommendation reference uncertainty and split-sample policy instability are not a single joint CI.",
        "- The earlier 180 or 240 sequence trials are not 180 or 240 independent provider worlds.",
        "- Evaluation counts, not computational-hour costs. Future incremental-budget continuation postponed.",
    ]
    (out/"WB_REFERENCE_ROBUSTNESS_REPORT.md").write_text("\n".join(report)+"\n")
    print("WB_ORIGINAL_WINNER_FREQUENCY",f"{rank_fraction:.5f}")
    print("WB_REFERENCE_PRIMARY_DIFF",f"{d.mean():+.6f}",f"CI95 [{lo:+.6f},{hi:+.6f}]")
    if split_difference is not None:
        print("DISJOINT_HALF_PRIMARY_DIFF",f"{split_difference:+.6f}")
    print("INDEPENDENT_WORLD_STUDY_SCREEN", "PLAN_ELIGIBLE" if passed else "HOLD")
    return gates


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo",type=Path,default=Path.cwd())
    ap.add_argument("--b1-outputs",type=Path,default=Path.home()/"praise/planb_b1_fixed_budget_v1")
    ap.add_argument("--out",type=Path,default=Path.home()/"praise/planb_b1_wb_robustness_v1")
    ap.add_argument("--outcome-meta",type=Path)
    ap.add_argument("--outcome-npz",type=Path)
    ap.add_argument("--reconstruct-outcomes",action="store_true",
                    help="Derive missing binary WB outcomes from existing frozen ledgers; no simulations")
    ap.add_argument("--reference-reps",type=int,default=300)
    ap.add_argument("--split-pairs",type=int,default=4)
    ap.add_argument("--split-repeats",type=int,default=2)
    ap.add_argument("--seed",type=int,default=SEED)
    args=ap.parse_args()
    if args.reference_reps<50 or args.split_pairs<0 or args.split_repeats<1:
        ap.error("Need at least 50 reference draws; split pairs >=0; repeats >=1")
    repo=args.repo.resolve()
    out=args.out.resolve()
    # Fail closed on archives before any science computations.
    original_matrix,sources=b1.build_matrix(repo)
    default=repo/"first_science/phase5/results/06_evaluation_v3b_fullsupport/bootstrap_reference"
    meta_path=args.outcome_meta or default/"wb_primary_outcome_columns.csv"
    matrix_path=args.outcome_npz or default/"wb_primary_trajectory_outcomes.npz"
    if not meta_path.is_file() or not matrix_path.is_file():
        if not args.reconstruct_outcomes:
            raise FileNotFoundError("WB binary outcome cache missing; rerun with --reconstruct-outcomes to rebuild only from frozen ledgers")
        meta_path,matrix_path=make_outcomes_from_ledgers(repo,out)
    meta,outcomes=load_outcomes(meta_path,matrix_path)
    pred,pred_hashes=load_predictions(repo,meta,original_matrix)
    frequencies,old_manifest=decision_frequencies(args.b1_outputs.resolve(),original_matrix)
    out.mkdir(parents=True,exist_ok=True)
    ref=reference_bootstrap(outcomes,pred,frequencies,original_matrix,
                            args.reference_reps,args.seed)
    splits=split_replay(outcomes,pred,args.split_pairs,args.split_repeats,args.seed) if args.split_pairs else None
    gates=write_results(out,ref,splits,original_matrix.mean(axis=1),args.reference_reps,args.split_pairs)
    manifest={
        "status":"B1_WB_REFERENCE_ROBUSTNESS_V1",
        "original_policy_unchanged":True,"original_replay_unchanged":True,
        "conditional_on_original_worlds":True,
        "reference_reps":args.reference_reps,
        "split_pairs":args.split_pairs,"split_repeats_per_start_cell":args.split_repeats,
        "seed":args.seed,
        "methods":b1.METHODS,"budgets":b1.BUDGETS,
        "resampling_unit":"complete WB trajectory across 555 related query-horizon outcomes",
        "joint_sample_indices_across_12_cells":True,
        "original_reference_N":N,"disjoint_half_N":N//2,
        "wb_outcomes_sha256":b1.digest(matrix_path),
        "wb_metadata_sha256":b1.digest(meta_path),
        "previous_b1_run_manifest_sha256":b1.digest(args.b1_outputs/"run_manifest.json"),
        "previous_b1_matrix_sha256":b1.digest(args.b1_outputs/"seven_method_matrix.csv"),
        "source_metrics_sha256":{k:v["metrics_sha256"] for k,v in sources.items()},
        "pointwise_prediction_sha256":pred_hashes,
        "screening_gate":gates,
        "output_sha256":{p.name:b1.digest(p) for p in out.glob("*.csv")},
    }
    (out/"audit_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("WB_REFERENCE_INPUT_PASS", "7 methods x 12 cells; 1,000 trajectories x 6,660 query columns")
    print("AUDIT_OUTPUT",out)


if __name__=="__main__":
    main()
