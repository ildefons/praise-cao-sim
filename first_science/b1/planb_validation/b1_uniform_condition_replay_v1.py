#!/usr/bin/env python3
"""Retrospective uniform-condition reconstruction; NOT the original Nov 6 ablation.
Only archived 7x12 errors are read; no simulator calls or edits to frozen policies.
"""
import argparse, csv, hashlib, json, sys
from pathlib import Path
import numpy as np

BUDGETS=(10,15,20,30,40)
REPEATS=20
NBOOT=2000
SEED=20261105
POLICIES=("kg_uniform_reconstruction","top2_uniform_reconstruction")

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(path, rows):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def choose_max(values,rng):
    v=np.asarray(values,dtype=float)
    return int(rng.choice(np.flatnonzero(v>=np.max(v)-1e-12)))

def select_arm(seen,B,policy,rng,frozen,kg):
    m=len(frozen.METHODS)
    available=[(a,c,0) for a in range(m) for c in range(12)
               if not any(aa==a and cc==c for aa,cc,_ in seen)]
    if policy==POLICIES[0]:
        mu,_,S=frozen.posterior(seen,m)
        scores=kg.scores_from_posterior(mu,S,available)
        per_arm=np.full(m,-np.inf)
        for (a,c,_),score in zip(available,scores):
            per_arm[a]=max(per_arm[a],score)
        return choose_max(per_arm,rng)
    counts=np.bincount([a for a,_,_ in seen],minlength=m)
    # Preserve the precommitted 50% coverage / 50% decision phase schedule,
    # but reconstruct predictor choice separately from cell choice.
    if len(seen)<m+(B-m+1)//2:
        return int(rng.choice(np.flatnonzero(counts==counts.min())))
    mu,_,S=frozen.posterior(seen,m)
    top=np.argsort(mu,kind="stable")[:2]
    score=np.full(m,-np.inf)
    for a,c,_ in available:
        if a not in top:continue
        x=frozen.XX[c]
        cov=S[a]
        gain=float(frozen.V@cov@x)**2/(frozen.NOISE**2+float(x@cov@x))
        score[a]=max(score[a],gain)
    if not np.isfinite(score).any():
        return int(rng.choice(np.flatnonzero(counts==counts.min())))
    return choose_max(score,rng)

def run_episode(matrix,B,start,rep,policy,frozen,kg):
    pid=6 if policy==POLICIES[0] else 7
    rng=np.random.default_rng(np.random.SeedSequence([SEED,B,start,rep,pid]))
    seen=[(a,start,float(matrix[a,start])) for a in range(7)]
    while len(seen)<B:
        a=select_arm(seen,B,policy,rng,frozen,kg)
        remaining=[c for c in range(12) if not any(aa==a and cc==c for aa,cc,_ in seen)]
        if not remaining:raise AssertionError("Chosen arm exhausted")
        c=int(rng.choice(remaining))
        seen.append((a,c,float(matrix[a,c])))
    mu,_,_=frozen.posterior(seen,7)
    chosen=int(np.argmin(mu))
    truth=matrix.mean(axis=1)
    winner=int(np.argmin(truth))
    row=dict(budget=B,start_cell="__".join(frozen.CELLS[start]),start_index=start,
             replicate=rep,policy=policy,evaluations=B,
             recommended=frozen.METHODS[chosen],correct=int(chosen==winner),
             simple_regret=max(0.,float(truth[chosen]-truth[winner])))
    trace=[dict(budget=B,start_index=start,replicate=rep,policy=policy,step=i+1,
                method=frozen.METHODS[a],world=frozen.CELLS[c][0],
                graph=frozen.CELLS[c][1],mae=y)
           for i,(a,c,y) in enumerate(seen)]
    assert len(set((a,c) for a,c,_ in seen))==B
    return row,trace

def summarize(rows,baseline,kgrows):
    lookup={(r["policy"],int(r["budget"]),int(r["start_index"]),int(r["replicate"])):
            float(r["simple_regret"]) for r in rows}
    adapt={(r["policy"],int(r["budget"]),int(r["start_index"]),int(r["replicate"])):
           float(r["simple_regret"]) for r in baseline+kgrows}
    rng=np.random.default_rng(SEED+1106)
    summaries=[];contrasts=[]
    for policy,other in ((POLICIES[0],"kg_one_step"),(POLICIES[1],"budgeted_top2")):
        deviations=[]
        for B in BUDGETS:
            uniform=np.array([[lookup[(policy,B,s,r)] for r in range(REPEATS)]
                              for s in range(12)])
            adaptive=np.array([[adapt[(other,B,s,r)] for r in range(REPEATS)]
                               for s in range(12)])
            draws=rng.integers(REPEATS,size=(NBOOT,12,REPEATS))
            boot=np.take_along_axis(uniform[None,:,:],draws,axis=2).mean(axis=(1,2))
            delta=uniform-adaptive
            deviations.append(delta)
            paired=np.take_along_axis(delta[None,:,:],draws,axis=2).mean(axis=(1,2))
            summaries.append(dict(policy=policy,budget=B,episodes=240,
                                  mean_regret=float(uniform.mean()),
                                  regret_low=float(np.quantile(boot,.025)),
                                  regret_high=float(np.quantile(boot,.975))))
            contrasts.append(dict(contrast=policy+" minus "+other,budget=B,
                                  mean_regret_diff=float(delta.mean()),
                                  low=float(np.quantile(paired,.025)),
                                  high=float(np.quantile(paired,.975))))
        whole=np.array(deviations)
        draws=rng.integers(REPEATS,size=(NBOOT,12,REPEATS))
        paired=np.stack([np.take_along_axis(d[None,:,:],draws,axis=2).mean(axis=(1,2))
                         for d in whole],axis=1).mean(axis=1)
        contrasts.append(dict(contrast=policy+" minus "+other,budget="MEAN_OVER_5_BUDGETS",
                              mean_regret_diff=float(whole.mean()),
                              low=float(np.quantile(paired,.025)),
                              high=float(np.quantile(paired,.975))))
    return summaries,contrasts

def main():
    p=argparse.ArgumentParser()
    for name in ("matrix","baseline-terminal","kg-terminal","out"):
        p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    import b1_budget_comparison_v1 as frozen
    import b1_kg_one_step_v1 as kg
    dest=args.out.expanduser().resolve()
    if dest.exists():raise FileExistsError("Refusing to overwrite "+str(dest))
    matrix=kg.load_frozen_matrix(args.matrix.expanduser())
    baseline_path=args.baseline_terminal.expanduser()
    kg.load_frozen_episodes(baseline_path)
    baseline=frozen.read_csv(baseline_path)
    kgrows=frozen.read_csv(args.kg_terminal.expanduser())
    if len(kgrows)!=1200 or {r["policy"] for r in kgrows}!={"kg_one_step"}:
        raise ValueError("KG episodes invalid")
    if len({(r["budget"],r["start_index"],r["replicate"]) for r in kgrows})!=1200:
        raise ValueError("Duplicate KG episodes")
    terminals=[];history=[]
    for policy in POLICIES:
        for B in BUDGETS:
            for s in range(12):
                for rep in range(REPEATS):
                    terminal,trace=run_episode(matrix,B,s,rep,policy,frozen,kg)
                    terminals.append(terminal);history.extend(trace)
            print(policy,B,"complete",flush=True)
    if len(terminals)!=2400 or len(history)!=55200:
        raise AssertionError("Unexpected replay count")
    summary,contrasts=summarize(terminals,baseline,kgrows)
    dest.mkdir(parents=True)
    outputs={"uniform_terminal_episodes.csv":terminals,
             "uniform_action_history.csv":history,
             "uniform_budget_summary.csv":summary,
             "uniform_paired_contrasts.csv":contrasts}
    for name,rows in outputs.items():write(dest/name,rows)
    manifest=dict(status="B1_UNIFORM_CONDITION_RECONSTRUCTION_V1",
        caveat="Reconstructed arm-selection conventions; not verified exact Nov 6 ablation",
        matrix_sha256=digest(args.matrix.expanduser()),
        baseline_sha256=digest(baseline_path),
        kg_sha256=digest(args.kg_terminal.expanduser()),
        code_sha256=digest(__file__),
        frozen_code_sha256=digest(frozen.__file__),
        kg_code_sha256=digest(kg.__file__),
        budgets=BUDGETS,episodes=2400,actions=55200,repeats_per_start=REPEATS,
        bootstrap_replicates=NBOOT,bootstrap_seed=SEED+1106,
        output_sha256={name:digest(dest/name) for name in outputs})
    (dest/"uniform_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("B1_UNIFORM_CONDITION_RECONSTRUCTION_PASS")
    for row in summary:print("SUMMARY",row)
    for row in contrasts:
        if row["budget"]=="MEAN_OVER_5_BUDGETS":print("CONTRAST",row)
    print("OUTPUT",dest)

if __name__=="__main__":
    main()
