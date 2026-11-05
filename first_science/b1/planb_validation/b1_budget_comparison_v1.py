#!/usr/bin/env python3
"""PRAISE B1 v1: read-only seven-method matrix + fixed-budget policy replay.

Does not import PRAISE simulators, change frozen files, or consult hidden outcomes
inside a policy. Results on the historical archive are DEVELOPMENT evidence.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import numpy as np

WORLDS=('P1','P3','P4')
GRAPHS=('G_PAR','G_PARSEQ','G_SEQ','G_SEQPAR')
CELLS=tuple((w,g) for w in WORLDS for g in GRAPHS)
METHODS=('M1','M2','M3_FULL343','ORIGINAL_TOP14_B1400',
         'ORIGINAL_TOP1_B1400','FIXED_CV_TOP14','FIXED_CV_TOP1')
BUDGETS=(10,15,20,30,40)
POLICIES=('random','balanced','informed','budgeted_top2')
SOURCE_MEANS={
    'M1':.157015, 'M2':.133951, 'M3_FULL343':.121890,
    'ORIGINAL_TOP14_B1400':.154155,
    'ORIGINAL_TOP1_B1400':.162280,
    'FIXED_CV_TOP14':.160948, 'FIXED_CV_TOP1':.192105,
}
NOISE=.055
PRIOR_VAR=np.array([.12**2]+[.07**2]*3+[.045**2]*4)
PRIOR_MEAN=np.array([.17]+[0.]*7)
XX=np.array([[1.,*[float(w==w0) for w0 in WORLDS],
                  *[float(g==g0) for g0 in GRAPHS]] for w,g in CELLS])
V=XX.mean(axis=0)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for b in iter(lambda:handle.read(1048576),b''):h.update(b)
    return h.hexdigest()


def read_csv(path):
    with Path(path).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def cell_from(value):
    s=str(value).upper()
    w=re.search(r'(?<![A-Z0-9])P[134](?![A-Z0-9])',s)
    g=re.search(r'G_(PARSEQ|SEQPAR|PAR|SEQ)(?![A-Z])',s)
    if not w or not g:raise ValueError(f'Unrecognized cell: {value!r}')
    return w.group(),g.group()


def source_locations(repo):
    base=repo/'first_science'/'phase5'/'results'
    return {
        'phaseII':(base/'06_evaluation_v3b_fullsupport'/'primary_metrics.csv',
          base/'06_evaluation_v3b_fullsupport'/'phase5_v3b_fullsupport_deterministic_evaluation_manifest.json'),
        'original':(base/'b1_pilot_m3_retrospective_v1'/'evaluation'/'metrics_retrospective.csv',
          base/'b1_pilot_m3_retrospective_v1'/'evaluation'/'evaluation_manifest.json'),
        'fixedCV':(base/'b1_fixed_cv_top1_top14_b1400_v1'/'evaluation'/'metrics.csv',
          base/'b1_fixed_cv_top1_top14_b1400_v1'/'evaluation'/'evaluation_manifest.json'),
    }


def verify_source(label,metrics,manifest):
    if not metrics.is_file() or not manifest.is_file():
        raise FileNotFoundError(f'{label}: missing archived evidence: {metrics} or {manifest}')
    m=json.loads(manifest.read_text())
    expected={'phaseII':'FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION',
              'original':'B1_RETROSPECTIVE_EVALUATION_COMPLETE',
              'fixedCV':'B1_FIXED_CV_12_CELL_EVALUATION_COMPLETE'}[label]
    if m.get('status')!=expected:
        raise ValueError(f'{label}: unexpected evaluation manifest status {m.get("status")!r}')
    if label=='phaseII':
        recorded=m.get('output_hashes_sha256',{}).get('primary_metrics')
    else:recorded=m.get('metrics_sha256')
    if recorded!=digest(metrics):
        raise ValueError(f'{label}: metrics SHA-256 does not match frozen evaluation manifest')
    if label=='phaseII' and (m.get('eligible_cells')!=12 or m.get('primary_window')!='H60..H240'):
        raise ValueError('Phase II domain or evaluation window changed')
    if label=='original':
        freeze=metrics.parents[1]/'global_prediction_freeze.json'
        if not freeze.is_file() or digest(freeze)!=m.get('prediction_freeze_sha256'):
            raise ValueError('Original-style global prediction freeze missing or changed')
        if json.loads(freeze.read_text()).get('status')!='B1_RETROSPECTIVE_ALL_12_PREDICTIONS_FROZEN':
            raise ValueError('Original-style prediction freeze status changed')
    if label=='fixedCV':
        freeze=metrics.parents[1]/'global_prediction_freeze.json'
        if not freeze.is_file() or digest(freeze)!=m.get('global_freeze_sha256'):
            raise ValueError('Fixed-CV global prediction freeze missing or changed')
    return {'metrics':str(metrics),'manifest':str(manifest),
            'metrics_sha256':digest(metrics),'manifest_sha256':digest(manifest)}


def build_matrix(repo):
    paths=source_locations(repo)
    checked={k:verify_source(k,*p) for k,p in paths.items()}
    obs={}
    required={'phaseII':{'M1','M2','M3_FULL343'},
              'original':{'ORIGINAL_TOP14_B1400','ORIGINAL_TOP1_B1400'},
              'fixedCV':{'FIXED_CV_TOP14','FIXED_CV_TOP1'}}
    for kind,(file,_) in paths.items():
        rows=read_csv(file)
        for r in rows:
            if kind=='phaseII':
                name=r.get('method_id')
                if name not in required[kind] or r.get('scope')!='provider_world_x_graph':continue
                cell=cell_from(r['scope_value']);v=float(r['MAE']); count=int(r['n_points'])
            else:
                name=r.get('method')
                if kind=='fixedCV':
                    name={'B1_FIXED_CV_TOP14_B1400':'FIXED_CV_TOP14',
                          'B1_FIXED_CV_TOP1_B1400':'FIXED_CV_TOP1'}.get(name)
                if name not in required[kind] or r.get('scope')!='cell':continue
                cell=cell_from(r['cell']);v=float(r['mae']);count=int(r['n_points'])
            key=(name,cell)
            if key in obs:raise ValueError(f'Duplicate archived result: {key}')
            if count!=555 or not np.isfinite(v) or not 0<=v<=1:
                raise ValueError(f'Bad observation for {key}: n={count}, mae={v}')
            obs[key]=v
        for name in required[kind]:
            for cell in CELLS:
                if (name,cell) not in obs:raise ValueError(f'{kind}: missing {name} on {cell}')
    if len(obs)!=84:raise AssertionError(f'Expected 84 distinct actions; got {len(obs)}')
    Y=np.array([[obs[(a,c)] for c in CELLS] for a in METHODS])
    for i,name in enumerate(METHODS):
        actual=float(Y[i].mean())
        if abs(actual-SOURCE_MEANS[name])>0.00006:
            raise ValueError(f'{name}: archived mean {actual} disagrees with report {SOURCE_MEANS[name]}')
    return Y,checked


def posterior(seen, methods=7):
    """Independent per-algorithm conjugate Gaussian model, fixed hyperparameters."""
    S=np.empty((methods,8,8)); means=np.empty(methods); covs=np.empty(methods)
    for a in range(methods):
        subset=[(c,y) for aa,c,y in seen if aa==a]
        precision=np.diag(1/PRIOR_VAR)
        rhs=PRIOR_MEAN/PRIOR_VAR
        if subset:
            x=XX[[c for c,_ in subset]]
            y=np.array([v for _,v in subset])
            precision=precision+x.T@x/(NOISE**2)
            rhs=rhs+x.T@y/(NOISE**2)
        sa=np.linalg.inv(precision)
        th=sa@rhs
        S[a]=sa
        means[a]=float(V@th)
        covs[a]=float(V@sa@V)
    return means,covs,S


def balanced_score(seen, available, rng):
    m=max(a for a,c,y in available)+1 if available else max(a for a,c,y in seen)+1
    k=np.zeros((m,12),dtype=int)
    for a,c,y in seen:k[a,c]=1
    by_a=k.sum(axis=1)
    w_counts=np.array([[int(k[a,[i for i,(w,g) in enumerate(CELLS) if w==world]].sum())
                       for world in WORLDS] for a in range(m)])
    g_counts=np.array([[int(k[a,[i for i,(w,g) in enumerate(CELLS) if g==graph]].sum())
                       for graph in GRAPHS] for a in range(m)])
    scores=np.array([-100*by_a[a]-10*w_counts[a,WORLDS.index(CELLS[c][0])]
                     -2*g_counts[a,GRAPHS.index(CELLS[c][1])] for a,c,_ in available])
    return choose_tie(available,scores,rng)


def choose_tie(available,scores,rng):
    best=np.flatnonzero(scores>=np.max(scores)-1e-12)
    return available[int(rng.choice(best))][:2]


def informed_score(available,means,var,S,rng):
    m=len(means)
    score=[]
    for a,c,_ in available:
        x=XX[c];s=S[a]; denom=NOISE**2+float(x@s@x)
        gain=float(V@s@x)**2/denom
        total=0.
        for b in range(m):
            if b==a:continue
            gap=means[a]-means[b]
            v=max(1e-10,var[a]+var[b])
            total+=math.exp(-.5*gap*gap/v)*gain
        score.append(total)
    return choose_tie(available,np.asarray(score),rng)


def select_action(policy,seen,budget,rng,methods):
    visited={(a,c) for a,c,y in seen}
    available=[(a,c,0) for a in range(methods) for c in range(12) if (a,c) not in visited]
    if not available:raise ValueError('No remaining actions')
    if policy=='random':return available[int(rng.integers(len(available)))][:2]
    if policy=='balanced':return balanced_score(seen,available,rng)
    if policy=='budgeted_top2':
        # Precommitted 50% balanced / 50% decision-focused schedule.
        extra=budget-methods
        coverage_steps=(extra+1)//2
        if len(seen)<methods+coverage_steps:
            return balanced_score(seen,available,rng)
    mu,v,S=posterior(seen,methods)
    if policy=='informed':return informed_score(available,mu,v,S,rng)
    if policy=='budgeted_top2':
        top=np.argsort(mu,kind='stable')[:2]
        candidates=[(a,c,z) for a,c,z in available if a in top]
        scores=[float(V@S[a]@XX[c])**2/
                (NOISE**2+float(XX[c]@S[a]@XX[c])) for a,c,_ in candidates]
        if candidates:return choose_tie(candidates,np.array(scores),rng)
        return balanced_score(seen,available,rng)
    raise ValueError(f'Unknown policy {policy}')


def evaluate_episode(Y,policy,B,start,rep,seed):
    m=Y.shape[0]
    rng=np.random.default_rng(np.random.SeedSequence([seed,B,start,rep,POLICIES.index(policy)]))
    seen=[(a,start,float(Y[a,start])) for a in range(m)]
    if B<m or B>=m*12:raise ValueError('Episode budget out of admissible range')
    for t in range(m,B):
        a,c=select_action(policy,seen,B,rng,m)
        if (a,c) in [(i,j) for i,j,_ in seen]:raise AssertionError('Repeated action')
        seen.append((a,c,float(Y[a,c])))
    final_mu,_,_=posterior(seen,m)
    choice=int(np.argmin(final_mu))
    truth=Y.mean(axis=1)
    best=int(np.argmin(truth))
    record=dict(budget=B,start_cell=f'{CELLS[start][0]}__{CELLS[start][1]}',
        start_index=start,replicate=rep,policy=policy,evaluations=len(seen),
        recommended=METHODS[choice],correct=int(choice==best),
        simple_regret=max(0.,float(truth[choice]-truth[best])))
    trace=[dict(budget=B,start_index=start,replicate=rep,policy=policy,
        step=t+1,method=METHODS[a],world=CELLS[c][0],graph=CELLS[c][1],mae=val)
        for t,(a,c,val) in enumerate(seen)]
    return record,trace


def _boot(values, rng, replicates, repeats):
    # Stratify at the 12 fixed initial cells; independent random episodes within each.
    arr=np.asarray(values).reshape(12,repeats)
    picks=rng.integers(repeats,size=(replicates,12,repeats))
    return np.take_along_axis(arr[None,:,:],picks,axis=2).mean(axis=(1,2))


def summarize(rows, budgets, repeats, nboot, seed):
    key={(r['budget'],r['start_index'],r['replicate'],r['policy']):r for r in rows}
    summaries=[]; contrasts=[]
    rng=np.random.default_rng(seed+724)
    for B in budgets:
        scores={}
        for policy in POLICIES:
            ordered=[key[(B,s,rep,policy)] for s in range(12) for rep in range(repeats)]
            regrets=np.array([r['simple_regret'] for r in ordered]);correct=np.array([r['correct'] for r in ordered])
            scores[policy]=regrets
            br=_boot(regrets,rng,nboot,repeats)
            bc=_boot(correct,rng,nboot,repeats)
            summaries.append(dict(budget=B,policy=policy,episodes=len(ordered),
                mean_regret=float(regrets.mean()),regret_low=float(np.quantile(br,.025)),
                regret_high=float(np.quantile(br,.975)),
                p_correct=float(correct.mean()),p_low=float(np.quantile(bc,.025)),
                p_high=float(np.quantile(bc,.975)),regret_p90=float(np.quantile(regrets,.90))))
        for p in ('random','informed','budgeted_top2'):
            diff=scores[p]-scores['balanced']
            bd=_boot(diff,rng,nboot,repeats)
            contrasts.append(dict(budget=B,contrast=f'{p} minus balanced',
                mean_regret_diff=float(diff.mean()),low=float(np.quantile(bd,.025)),
                high=float(np.quantile(bd,.975))))
    # A single, predeclared across-budget primary comparison: equal-budget mean regret.
    for p in ('random','informed','budgeted_top2'):
        cells=[]
        for B in budgets:
            delta=np.array([key[(B,s,rep,p)]['simple_regret']-
                     key[(B,s,rep,'balanced')]['simple_regret']
                     for s in range(12) for rep in range(repeats)]).reshape(12,repeats)
            cells.append(delta)
        all_budget=np.array(cells) # B x 12 starts x repeats
        # Bootstrap whole matched initial conditions consistently across budgets.
        draws=rng.integers(repeats,size=(nboot,12,repeats))
        means=np.stack([np.take_along_axis(cells0[None,:,:],draws,axis=2).mean(axis=(1,2))
                        for cells0 in all_budget],axis=1).mean(axis=1)
        contrasts.append(dict(budget='MEAN_OVER_5_BUDGETS',contrast=f'{p} minus balanced',
            mean_regret_diff=float(all_budget.mean()),low=float(np.quantile(means,.025)),
            high=float(np.quantile(means,.975))))
    return summaries,contrasts


def run(Y,checked,out,budgets,repeats,bootstrap,seed):
    if Y.shape!=(7,12):raise ValueError('Seven-method replay requires 7 x 12 verified data')
    out.mkdir(parents=True,exist_ok=True)
    rows=[];traces=[]
    for B in budgets:
        for s in range(12):
            for rep in range(repeats):
                for p in POLICIES:
                    row,trace=evaluate_episode(Y,p,B,s,rep,seed)
                    rows.append(row);traces.extend(trace)
        print(f'BUDGET {B} COMPLETE: {12*repeats} episodes/policy',flush=True)
    summary,contrasts=summarize(rows,budgets,repeats,bootstrap,seed)
    matrix_rows=[dict(method=METHODS[a],world=w,graph=g,mae=float(Y[a,c]))
                 for a in range(7) for c,(w,g) in enumerate(CELLS)]
    write_csv(out/'seven_method_matrix.csv',matrix_rows,['method','world','graph','mae'])
    write_csv(out/'terminal_episodes.csv',rows,list(rows[0]))
    write_csv(out/'episode_action_history.csv',traces,list(traces[0]))
    write_csv(out/'budget_summary.csv',summary,list(summary[0]))
    write_csv(out/'paired_regret_contrasts.csv',contrasts,list(contrasts[0]))
    manifest=dict(status='B1_FIXED_BUDGET_DEVELOPMENT_REPLAY_V1',
        design='B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1',
        methods=METHODS,cells=CELLS,budgets=budgets,policies=POLICIES,
        repeats_per_start_cell=repeats,episodes_per_policy_per_budget=12*repeats,
        bootstrap_replicates=bootstrap,seed=seed,
        primary_outcome='simple_regret',primary_contrast='budgeted_top2 minus balanced, mean across five frozen budgets',
        baseline_recommendation='posterior mean minimum shared across policies',
        budgeted_top2='ceil((B-7)/2) balanced extra evaluations, then maximize variance reduction of current posterior top-two gap',
        note='Retrospective finite-archive development; NOT independent world-level confirmation',
        source_evidence=checked,
        inputs_sha256={s:checked[s]['metrics_sha256'] for s in checked},
        outputs_sha256={p.name:digest(p) for p in out.glob('*.csv')})
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('\nREFERENCE BEST',METHODS[int(np.argmin(Y.mean(axis=1)))])
    print('METHOD MEANS',dict(zip(METHODS,[round(float(v),6) for v in Y.mean(axis=1)])))
    for B in budgets:
        print('BUDGET',B,' | '.join(f"{r['policy']} regret={r['mean_regret']:.5f} pbest={r['p_correct']:.3f}"
                              for r in summary if r['budget']==B))
    print('ACROSS BUDGETS',next(x for x in contrasts if x['budget']=='MEAN_OVER_5_BUDGETS' and x['contrast'].startswith('budgeted_top2')))
    print('OUTPUT',out.resolve())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path.cwd())
    p.add_argument('--mode',choices=('inspect','all'),default='all')
    p.add_argument('--out',type=Path,default=Path.home()/'praise/planb_b1_fixed_budget_v1')
    p.add_argument('--repeats-per-cell',type=int,default=20)
    p.add_argument('--bootstrap',type=int,default=2000)
    p.add_argument('--seed',type=int,default=20261105)
    args=p.parse_args();args.repo=args.repo.resolve()
    loc=source_locations(args.repo)
    if args.mode=='inspect':
        for k,(a,b) in loc.items():
            print(f'SOURCE {k} metrics={"FOUND" if a.is_file() else "MISSING"} {a}')
            print(f'           manifest={"FOUND" if b.is_file() else "MISSING"} {b}')
        return
    if args.repeats_per_cell<2 or args.bootstrap<100:raise ValueError('Need >=2 repeats and >=100 bootstrap draws')
    Y,checked=build_matrix(args.repo)
    run(Y,checked,args.out,BUDGETS,args.repeats_per_cell,args.bootstrap,args.seed)

if __name__=='__main__':main()
