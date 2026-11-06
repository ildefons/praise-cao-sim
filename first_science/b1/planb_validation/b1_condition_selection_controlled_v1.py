#!/usr/bin/env python3
"""Matched two-stage KG/Top2 condition-choice ablation. No simulations.

The predictor chooser is identical for adaptive and uniform variants, conditional
on the history; subsequent histories and thus arm choices may diverge.
These are NEW two-stage policies, not the original joint-acquisition policies.
"""
import argparse,csv,hashlib,json,sys
from pathlib import Path
import numpy as np

BUDGETS=(10,15,20,30,40)
POLICIES=("kg_two_stage_adaptive","kg_two_stage_uniform",
          "top2_two_stage_adaptive","top2_two_stage_uniform")
SEED=20261105; REPEATS=20; NBOOT=2000

def hashfile(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,rows):
    with open(p,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def pick(s,rng):
    a=np.asarray(s,float)
    if not np.isfinite(a).any():raise ValueError("No feasible arm")
    return int(rng.choice(np.flatnonzero(a>=np.max(a)-1e-12)))
def options(seen):
    taken={(a,c) for a,c,_ in seen}
    return {a:[c for c in range(12) if (a,c) not in taken] for a in range(7)}
def gain(s,c,f):
    x=f.XX[c]
    return float(f.V@s@x)**2/(f.NOISE**2+float(x@s@x))
def acquisition(seen,family,B,f,kg):
    remaining=options(seen)
    mean,_,cov=f.posterior(seen,7)
    arms=np.full(7,-np.inf); conditional={}
    if family=="kg":
        for a,cells in remaining.items():
            if cells:
                scores=kg.scores_from_posterior(mean,cov,[(a,c,0) for c in cells])
                arms[a]=np.mean(scores);conditional[a]=scores
    else:
        coverage=len(seen)<7+(B-7+1)//2
        counts=np.bincount([a for a,_,_ in seen],minlength=7)
        leaders=range(7) if coverage else np.argsort(mean,kind="stable")[:2]
        for a in leaders:
            a=int(a);cells=remaining[a]
            if not cells:continue
            if coverage:
                prior=[c for aa,c,_ in seen if aa==a]
                scores=np.array([-10*sum(f.CELLS[d][0]==f.CELLS[c][0] for d in prior)
                                 -2*sum(f.CELLS[d][1]==f.CELLS[c][1] for d in prior)
                                 for c in cells],float)
                arms[a]=-counts[a]
            else:
                scores=np.array([gain(cov[a],c,f) for c in cells])
                arms[a]=np.mean(scores)
            conditional[a]=scores
        if not np.isfinite(arms).any():
            for a,cells in remaining.items():
                if cells:
                    arms[a]=-counts[a]
                    conditional[a]=np.array([0.]*len(cells))
    return arms,conditional,remaining
def episode(y,policy,B,start,rep,f,kg):
    family="kg" if policy.startswith("kg_") else "top2"
    adaptive=policy.endswith("_adaptive")
    family_id=0 if family=="kg" else 1
    armrng=np.random.default_rng(np.random.SeedSequence([SEED,B,start,rep,family_id,33]))
    cellrng=np.random.default_rng(np.random.SeedSequence([SEED,B,start,rep,family_id,44]))
    seen=[(a,start,float(y[a,start])) for a in range(7)]
    while len(seen)<B:
        arms,conditional,remaining=acquisition(seen,family,B,f,kg)
        a=pick(arms,armrng);cells=remaining[a]
        c=cells[pick(conditional[a],cellrng)] if adaptive else int(cellrng.choice(cells))
        if (a,c) in {(aa,cc) for aa,cc,_ in seen}:raise AssertionError("Duplicate action")
        seen.append((a,c,float(y[a,c])))
    mu,_,_=f.posterior(seen,7)
    choice=int(np.argmin(mu));truth=y.mean(axis=1);best=int(np.argmin(truth))
    term=dict(policy=policy,budget=B,start_index=start,replicate=rep,evaluations=B,
              recommended=f.METHODS[choice],correct=int(choice==best),
              simple_regret=max(0.,float(truth[choice]-truth[best])))
    hist=[dict(policy=policy,budget=B,start_index=start,replicate=rep,step=i+1,
               method=f.METHODS[a],world=f.CELLS[c][0],graph=f.CELLS[c][1],mae=v)
          for i,(a,c,v) in enumerate(seen)]
    return term,hist
def statistics(rows):
    keyed={(x["policy"],x["budget"],x["start_index"],x["replicate"]):x for x in rows}
    assert len(keyed)==len(rows)
    rng=np.random.default_rng(SEED+1206)
    summaries=[];contrasts=[]
    for family in ("kg","top2"):
        across=[]
        for B in BUDGETS:
            groups={}
            for variant in ("adaptive","uniform"):
                policy=family+"_two_stage_"+variant
                batch=[keyed[policy,B,s,r] for s in range(12) for r in range(REPEATS)]
                regrets=np.array([x["simple_regret"] for x in batch]).reshape(12,REPEATS)
                correct=np.array([x["correct"] for x in batch]).reshape(12,REPEATS)
                groups[variant]=regrets
                draws=rng.integers(REPEATS,size=(NBOOT,12,REPEATS))
                br=np.take_along_axis(regrets[None,:,:],draws,axis=2).mean(axis=(1,2))
                bc=np.take_along_axis(correct[None,:,:],draws,axis=2).mean(axis=(1,2))
                summaries.append(dict(policy=policy,budget=B,episodes=240,
                     mean_regret=float(regrets.mean()),
                     regret_low=float(np.quantile(br,.025)),regret_high=float(np.quantile(br,.975)),
                     p_correct=float(correct.mean()),p_low=float(np.quantile(bc,.025)),
                     p_high=float(np.quantile(bc,.975)),regret_p90=float(np.quantile(regrets,.9))))
            diff=groups["uniform"]-groups["adaptive"];across.append(diff)
            draws=rng.integers(REPEATS,size=(NBOOT,12,REPEATS))
            bd=np.take_along_axis(diff[None,:,:],draws,axis=2).mean(axis=(1,2))
            contrasts.append(dict(family=family,budget=B,contrast="uniform minus adaptive",
                    mean_regret_diff=float(diff.mean()),low=float(np.quantile(bd,.025)),
                    high=float(np.quantile(bd,.975))))
        draws=rng.integers(REPEATS,size=(NBOOT,12,REPEATS))
        bd=np.stack([np.take_along_axis(d[None,:,:],draws,axis=2).mean(axis=(1,2))
                     for d in across],axis=1).mean(axis=1)
        contrasts.append(dict(family=family,budget="MEAN_OVER_5_BUDGETS",
                 contrast="uniform minus adaptive",mean_regret_diff=float(np.array(across).mean()),
                 low=float(np.quantile(bd,.025)),high=float(np.quantile(bd,.975))))
    return summaries,contrasts
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--matrix",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args();dest=args.out.expanduser().resolve()
    if dest.exists():raise FileExistsError("Refusing overwrite: "+str(dest))
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import b1_budget_comparison_v1 as f
    import b1_kg_one_step_v1 as kg
    matrix=kg.load_frozen_matrix(args.matrix.expanduser())
    terms=[];hist=[]
    for policy in POLICIES:
        for B in BUDGETS:
            for s in range(12):
                for rep in range(REPEATS):
                    t,h=episode(matrix,policy,B,s,rep,f,kg);terms.append(t);hist.extend(h)
            print("COMPLETE",policy,B,flush=True)
    assert len(terms)==4800 and len(hist)==110400
    summary,contrasts=statistics(terms)
    dest.mkdir(parents=True)
    outputs={"controlled_terminal_episodes.csv":terms,"controlled_action_history.csv":hist,
             "controlled_budget_summary.csv":summary,"controlled_paired_contrasts.csv":contrasts}
    for name,rows in outputs.items():save(dest/name,rows)
    manifest=dict(status="B1_CONTROLLED_TWO_STAGE_CONDITION_ABLATION_V1",
         warning="New matched two-stage policies, not the original joint-acquisition policies",
         seed=SEED,bootstrap_seed=SEED+1206,bootstrap_replicates=NBOOT,
         budgets=BUDGETS,episodes=len(terms),actions=len(hist),
         input_matrix_sha256=hashfile(args.matrix.expanduser()),
         code_sha256=hashfile(__file__),original_policy_sha256=hashfile(f.__file__),
         kg_policy_sha256=hashfile(kg.__file__),
         output_sha256={name:hashfile(dest/name) for name in outputs})
    (dest/"controlled_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("B1_CONTROLLED_TWO_STAGE_CONDITION_ABLATION_PASS")
    for row in contrasts:
        if row["budget"]=="MEAN_OVER_5_BUDGETS":print("PAIRED",row)
    print("OUTPUT",dest)
if __name__=="__main__":main()
