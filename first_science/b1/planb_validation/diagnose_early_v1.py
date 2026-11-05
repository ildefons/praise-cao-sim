#!/usr/bin/env python3
"""Read-only B1.2 diagnostic: reconstruct the *exact* Gate1 policy action sequences.

Requires original planb_gate1.py and the replay output folder. The existing
replay_trial_trace.csv records decisions but NOT which actions were visited;
therefore deterministic reconstruction is needed before coverage can be audited.
No simulations, new policy fitting, or model development are performed.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import numpy as np
import pandas as pd

POLICIES=('random','balanced','informed')
FIELDS=('distinct_cells','distinct_worlds','distinct_graphs',
        'mean_worlds_per_algorithm','mean_graphs_per_algorithm',
        'world_imbalance','graph_imbalance','algorithm_imbalance',
        'same_cell_pair_count','full_algorithm_cells','heldout_model_mae')


def load_gate(path):
    spec=importlib.util.spec_from_file_location('planb_gate1_original',str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot import original script: {path}')
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def load_records(gate,root):
    meta=json.loads((root/'replay_run_metadata.json').read_text())
    names=tuple(meta['methods'])
    rows=pd.read_csv(root/'source_cell_mae.csv')
    lookup={}
    for r in rows.itertuples(index=False):
        key=(str(r.method),gate.norm_cell(f'{r.world} {r.graph}'))
        if key in lookup:raise ValueError(f'Duplicate measurement: {key}')
        lookup[key]=float(r.mae)
    missing=[(a,c) for a in names for c in gate.CELLS if (a,c) not in lookup]
    if missing:raise ValueError(f'Missing data: {missing[:10]}')
    Y=np.array([[lookup[(a,c)] for c in gate.CELLS] for a in names],dtype=float)
    tr=pd.read_csv(root/'replay_trial_trace.csv')
    index=tr.set_index(['trial','policy','actions'])
    assert index.index.is_unique, 'Duplicate replay-trace coordinates'
    return names,Y,tr,index,meta


def coverage(seen,gate,Y,X,theta):
    m,n=Y.shape
    ctr=np.zeros((m,n),dtype=int)
    for (a,c),val in seen:
        if ctr[a,c]:raise AssertionError('Repeated action')
        ctr[a,c]=1
    cells=np.flatnonzero(ctr.sum(axis=0))
    world_ix=np.array([gate.WORLDS.index(w) for w,g in gate.CELLS])
    graph_ix=np.array([gate.GRAPHS.index(g) for w,g in gate.CELLS])
    world_counts=np.array([int(ctr[:,world_ix==w].sum()) for w in range(3)])
    graph_counts=np.array([int(ctr[:,graph_ix==g].sum()) for g in range(4)])
    algo_counts=ctr.sum(axis=1)
    worlds_per_alg=np.array([(np.bincount(world_ix[ctr[a].astype(bool)],minlength=3)>0).sum() for a in range(m)])
    graphs_per_alg=np.array([(np.bincount(graph_ix[ctr[a].astype(bool)],minlength=4)>0).sum() for a in range(m)])
    k=ctr.sum(axis=0)
    # Retrospective model discrepancy on entries not yet revealed: diagnostic only.
    predicted=np.einsum('acd,d->ac',X,theta)
    unseen=ctr==0
    withheld=float(np.mean(np.abs(predicted[unseen]-Y[unseen]))) if unseen.any() else 0.
    return dict(distinct_cells=int(len(cells)),
        distinct_worlds=int((world_counts>0).sum()),
        distinct_graphs=int((graph_counts>0).sum()),
        mean_worlds_per_algorithm=float(worlds_per_alg.mean()),
        mean_graphs_per_algorithm=float(graphs_per_alg.mean()),
        world_imbalance=int(world_counts.max()-world_counts.min()),
        graph_imbalance=int(graph_counts.max()-graph_counts.min()),
        algorithm_imbalance=int(algo_counts.max()-algo_counts.min()),
        same_cell_pair_count=int(sum(v*(v-1)//2 for v in k)),
        full_algorithm_cells=int((k==m).sum()),
        heldout_model_mae=withheld)


def frame_table(df):
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return '\n'+df.to_string(index=False)+'\n'


def means_by(table,cols):
    out=(table.groupby(cols,sort=True)
        .agg(trials=('trial','nunique'),accuracy=('correct','mean'),
             mean_regret=('simple_regret','mean'),
             **{f: (f,'mean') for f in FIELDS})
        .reset_index())
    return out


def bootstrap_paired(x,seed=20261107,B=4000):
    rng=np.random.default_rng(seed)
    n=len(x)
    idx=rng.integers(n,size=(B,n))
    boot=x[idx].mean(axis=1)
    return float(x.mean()),float(np.quantile(boot,.025)),float(np.quantile(boot,.975))


def run(root,gate_path,out,budgets,seed):
    gate=load_gate(gate_path)
    names,Y,trace,index,meta=load_records(gate,root)
    m,n=Y.shape
    assert n==12
    if not set(POLICIES).issubset(set(meta['policies'])):
        raise ValueError('Replay policy set differs from expected original')
    trials=sorted(trace.trial.unique())
    if not trials or trials!=list(range(len(trials))):
        raise ValueError('Nonconsecutive trial IDs')
    if max(budgets)>m*n or min(budgets)<m:
        raise ValueError('Budgets outside recorded range')
    X=gate.feature_matrix(m)
    selected=set(budgets)
    max_budget=max(budgets)
    rec=[];act=[]
    validated=0
    for trial in trials:
        first=int(np.random.default_rng(seed+int(trial)).integers(n))
        initial=[((a,first),float(Y[a,first])) for a in range(m)]
        for pi,policy in enumerate(POLICIES):
            rng=np.random.default_rng(seed+int(trial)*20+pi*987654+17)
            seen=initial.copy()
            for t in range(m,max_budget+1):
                theta,S,V,mu=gate.bayes_fit(X,seen)
                chosen=int(np.argmin(mu))
                original=index.loc[(trial,policy,t)]
                if chosen != int(original['recommended_method_index']):
                    raise AssertionError(f'Replay mismatch: trial={trial}, policy={policy}, budget={t}: predicted={chosen}, archived={original["recommended_method_index"]}')
                if t in selected:
                    stats=coverage(seen,gate,Y,X,theta)
                    rec.append(dict(trial=int(trial),policy=policy,actions=t,
                              starting_world=gate.CELLS[first][0],starting_graph=gate.CELLS[first][1],
                              selected_algorithm=names[chosen],
                              correct=int(original['correct']),simple_regret=float(original['simple_regret']),
                              **stats))
                validated+=1
                if t<max_budget:
                    a,c=gate.policy_action(policy,X,seen,rng)
                    w,g=gate.CELLS[c]
                    act.append(dict(trial=int(trial),policy=policy,after_action=t+1,
                               algorithm=names[a],world=w,graph=g,
                               new_cell=int(c not in [c0 for (a0,c0),_ in seen]),
                               current_accuracy=int(original['correct'])))
                    seen.append(((a,c),float(Y[a,c])))
        if (trial+1)%30==0:print(f'RECONSTRUCTED {trial+1}/{len(trials)} trials',flush=True)
    # Enforce faithful reproduction of the entire replay prefix, not merely selected budgets.
    print(f'REPLAY_PREFIX_VERIFIED {validated} decision states through budget {max_budget}')
    states=pd.DataFrame(rec);actions=pd.DataFrame(act)
    summary=means_by(states,['actions','policy'])
    paired=[];strata=[];failure=[]
    for t in budgets:
        subt=states[states.actions==t]
        arr={p:subt[subt.policy==p].set_index('trial') for p in POLICIES}
        for left,right in [('informed','balanced'),('balanced','random'),('informed','random')]:
            aa,bb=arr[left],arr[right]
            assert list(aa.index)==list(bb.index)
            for field in ('correct','simple_regret')+FIELDS:
                vals=(aa[field]-bb[field]).to_numpy(dtype=float)
                avg,lo,hi=bootstrap_paired(vals,seed=seed+int(t)+len(field)+len(left))
                paired.append(dict(actions=t,contrast=f'{left} - {right}',measure=field,
                                   difference=avg,ci025=lo,ci975=hi,
                                   n_trials=len(vals)))
        a,b=arr['informed'],arr['balanced']
        for i in a.index:
            if a.loc[i,'correct'] and not b.loc[i,'correct']:
                status='informed_only_correct'
            elif b.loc[i,'correct'] and not a.loc[i,'correct']:
                status='balanced_only_correct'
            elif a.loc[i,'correct']:
                status='both_correct'
            else:status='both_wrong'
            item={'actions':t,'trial':i,'result_group':status}
            for k in FIELDS:
                item[f'informed_minus_balanced_{k}']=float(a.loc[i,k]-b.loc[i,k])
            strata.append(item)
        for policy,p in arr.items():
            wrong=p[p.correct==0]
            for algo,cnt in wrong.selected_algorithm.value_counts().items():
                failure.append({'actions':t,'policy':policy,'wrong_algorithm':algo,'count':int(cnt)})
    paired=pd.DataFrame(paired);strata=pd.DataFrame(strata)
    rescue=means_by(states,['actions','policy','correct'])
    strata_summary=(strata.groupby(['actions','result_group'])
       .agg(n=('trial','count'),
            **{f:(f'informed_minus_balanced_{f}','mean') for f in FIELDS})
       .reset_index())
    summary.to_csv(out/'coverage_by_budget_policy.csv',index=False)
    states.to_csv(out/'reconstructed_state_diagnostic.csv',index=False)
    actions.to_csv(out/'reconstructed_selected_actions.csv',index=False)
    paired.to_csv(out/'paired_differences.csv',index=False)
    rescue.to_csv(out/'correct_vs_wrong_coverage.csv',index=False)
    strata_summary.to_csv(out/'informed_vs_balanced_disagreement.csv',index=False)
    pd.DataFrame(failure).to_csv(out/'wrong_algorithm_counts.csv',index=False)
    # A concise output focusing on the hypothesis, not 20 unrelated diagnostics.
    lines=["# B1.2 early-budget selection diagnostic",'',
        f'Source: {meta.get("source", "unknown")}',
        f'{len(trials)} trials; {m} algorithms; 12 cells; budgets {budgets}.',
        f'Original replay prefixes validated at {validated} states against archived recommendations.',
        '',
        '## Coverage and results (means by policy)', '']
    for t in budgets:
        lines.append(f'### {t} actions')
        ss=summary[summary.actions==t]
        cols=['policy','accuracy','mean_regret','distinct_cells','distinct_worlds','distinct_graphs',
              'mean_worlds_per_algorithm','mean_graphs_per_algorithm','same_cell_pair_count','heldout_model_mae']
        lines.append(frame_table(ss[cols].round(4)))
        lines.append('')
        pair=paired[(paired.actions==t)&(paired.contrast=='informed - balanced')&
                    (paired.measure.isin(['correct','distinct_cells','distinct_worlds','distinct_graphs',
                              'mean_worlds_per_algorithm','mean_graphs_per_algorithm','heldout_model_mae']))]
        lines.append('Paired informed minus balanced differences (trial-bootstrap intervals):')
        lines.append(frame_table(pair[['measure','difference','ci025','ci975']].round(4)))
        lines.append('')
        grp=strata_summary[strata_summary.actions==t]
        cols2=['result_group','n','distinct_cells','mean_worlds_per_algorithm','heldout_model_mae']
        lines.append('Results when the policies agree or disagree:')
        lines.append(frame_table(grp[cols2].round(4)))
        lines.append('')
    lines.extend(['## Interpretation limits','',
        '- This is an observational diagnosis of a retrospective sequence, not a causal test of coverage.',
        '- Original replay used a shared additive Bayesian model for *all* policies; differences concern action order.',
        '- The 180 trials randomize initial cell and policy action choices, not provider worlds.',
        '- All recorded MAEs are frozen summaries; not independently split from the reference trajectories.',
        '- Held-out model MAE is calculated *after* each decision only for diagnosis; it is never passed to a policy.',
        '- Coverage across algorithms is always complete at initialization, because the replay starts by evaluating all algorithms on one cell.',
        '- The intervals describe variation in replay starts and tie-breaking, not uncertainty across new worlds.',
        '- Do not infer causal mediation or tune a new policy using these results without a new holdout.',
    ])
    (out/'B1_2_DIAGNOSTIC.md').write_text('\n'.join(lines)+'\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        f,axs=plt.subplots(2,2,figsize=(10,7))
        specs=[('accuracy','Selection accuracy'),('distinct_cells','Distinct world-graph cells'),
               ('mean_worlds_per_algorithm','Mean worlds evaluated / algorithm'),
               ('heldout_model_mae','Prediction error on hidden entries (diagnostic)')]
        for ax,(key,title) in zip(axs.ravel(),specs):
            for policy in POLICIES:
                ss=summary[summary.policy==policy].sort_values('actions')
                ax.plot(ss.actions,ss[key],marker='o',label=policy)
            ax.set_title(title);ax.set_xlabel('Evaluations completed');ax.grid(alpha=.25)
        axs[0,0].legend()
        f.suptitle('PRAISE B1.2: early-budget coverage versus selection')
        f.tight_layout();f.savefig(out/'early_coverage_diagnostic.png',dpi=180);plt.close(f)
    except ImportError: pass
    print('\nEARLY COVERAGE SUMMARY')
    print(summary[['actions','policy','accuracy','distinct_cells','distinct_worlds','distinct_graphs','mean_worlds_per_algorithm','heldout_model_mae']].round(3).to_string(index=False))
    print('\nINFORMED MINUS BALANCED: PAIRED EARLY CONTRASTS')
    print(paired[(paired.contrast=='informed - balanced')&
                 (paired.measure.isin(['correct','distinct_cells','mean_worlds_per_algorithm','heldout_model_mae']))]
            [['actions','measure','difference','ci025','ci975']].round(3).to_string(index=False))
    print('DIAGNOSTIC_OUTPUT',out.resolve())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=Path.home()/'praise/planb_gate1_local_outputs')
    p.add_argument('--gate',type=Path,default=Path.home()/'praise/planb_gate1/planb_gate1.py')
    p.add_argument('--out',type=Path,default=Path.home()/'praise/planb_gate1_early_diagnostic')
    p.add_argument('--budgets',default='8,14,17',help='Comma-separated budgets of completed evaluations')
    p.add_argument('--seed',type=int,default=20261105)
    args=p.parse_args()
    budgets=sorted(set(map(int,args.budgets.split(','))))
    if not args.gate.is_file(): p.error(f'Original replay script not found: {args.gate}')
    if not args.results.is_dir():p.error(f'Replay output folder not found: {args.results}')
    args.out.mkdir(parents=True,exist_ok=True)
    run(args.results,args.gate,args.out,budgets,args.seed)

if __name__=='__main__':main()
