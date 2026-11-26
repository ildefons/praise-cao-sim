#!/usr/bin/env python3
"""WP2: paired terminal-estimator diagnostic on frozen nested histories."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

METHODS=['M1','M2','M3_FULL343','ORIGINAL_TOP14_B1400','ORIGINAL_TOP1_B1400','FIXED_CV_TOP14','FIXED_CV_TOP1']
CELLS=[(w,g) for w in ['P1','P3','P4'] for g in ['G_PAR','G_PARSEQ','G_SEQ','G_SEQPAR']]
X=np.array([[1]+[w==v for v in ['P1','P3','P4']]+[g==v for v in ['G_PAR','G_PARSEQ','G_SEQ','G_SEQPAR']] for w,g in CELLS],float)
K=(X*np.array([.12**2]+[.07**2]*3+[.045**2]*4))@X.T
SIGMA=.055

def run(source,out):
    out.mkdir(exist_ok=False,parents=True)
    with zipfile.ZipFile(source) as z:
        prefix='planb_b1_nested_budget_2026_11_20_v1/'
        manifest=json.loads(z.read(prefix+'nested_manifest.json'))
        for f,sha in manifest['outputs_sha256'].items():
            assert hashlib.sha256(z.read(prefix+f)).hexdigest()==sha,f
        with z.open(prefix+'nested_action_history.csv') as f: h=pd.read_csv(f,float_precision='round_trip')
        with z.open(prefix+'nested_terminal_episodes.csv') as f: old=pd.read_csv(f,float_precision='round_trip')
    budgets=manifest['budgets']; policies=manifest['policies']; archives=list(manifest['archive_sources'])
    assert len(h)==230400 and len(old)==37440
    h['a']=h.method.map({m:i for i,m in enumerate(METHODS)})
    h['c']=[CELLS.index(x) for x in zip(h.world,h.graph)]
    assert h.a.notna().all()
    keys=['archive','policy','start_index','replicate']
    assert not h.duplicated(keys+['step']).any() and not h.duplicated(keys+['a','c']).any()
    assert (h.groupby(keys).size()==80).all()
    assert (h.groupby(keys).step.agg(['min','max'])==[1,80]).all().all()
    assert (h.groupby(['archive','a','c']).mae.nunique()==1).all()
    truth={a:h[h.archive==a].drop_duplicates(['a','c']).pivot(index='a',columns='c',values='mae').reindex(index=range(7),columns=range(12)).to_numpy() for a in archives}
    assert all(np.isfinite(y).all() for y in truth.values())
    assert [METHODS[np.argmin(truth[a].mean(1))] for a in archives]==['M3_FULL343','M1']
    cache={}
    def prediction(y,mask):
        key=sum(1<<int(i) for i in mask)
        if key not in cache:
            cache[key]=K[:,mask]@np.linalg.inv(K[np.ix_(mask,mask)]+SIGMA**2*np.eye(len(mask)))
        return .17+cache[key]@(y-.17)
    for y in truth.values():
        for row in y:
            p=prediction(row,np.arange(12)); p[:]=row
            assert abs(p.mean()-row.mean())<1e-14
    result=[]
    for key,g in h.groupby(keys,sort=False):
        archive,policy,start,rep=key; t=truth[archive].mean(1); best=np.argmin(t)
        g=g.sort_values('step'); aa=g.a.to_numpy(int); cc=g.c.to_numpy(int); vv=g.mae.to_numpy()
        for B in budgets:
            e1=[];e2=[]
            for a in range(7):
                idx=np.where(aa[:B]==a)[0]; order=np.argsort(cc[idx]); idx=idx[order]
                mask=cc[idx]; obs=vv[idx]; p=prediction(obs,mask)
                e1.append(p.mean()); p[mask]=obs; e2.append(p.mean())
            r1,r2=np.argmin(e1),np.argmin(e2)
            result.append(dict(zip(keys,key))|dict(budget=B,recommended_1=METHODS[r1],recommended_2=METHODS[r2],regret_1=t[r1]-t[best],regret_2=t[r2]-t[best],correct_1=int(r1==best),correct_2=int(r2==best),mse_1=np.mean((np.array(e1)-t)**2),mse_2=np.mean((np.array(e2)-t)**2),disagree=int(r1!=r2)))
    d=pd.DataFrame(result); j=d.merge(old,on=keys+['budget'],validate='one_to_one'); assert len(j)==len(old)
    assert (j.recommended_1==j.recommended).all(); assert (j.correct_1==j.correct).all(); assert np.max(abs(j.regret_1-j.simple_regret))<1e-12
    d.to_csv(out/'paired_episodes.csv',index=False)
    for a,y in truth.items(): pd.DataFrame(y,index=METHODS,columns=['__'.join(c) for c in CELLS]).to_csv(out/f'{a}_reconstructed_matrix.csv')
    rng=np.random.default_rng(20261126); draws=rng.integers(20,size=(2000,12,20)); rows=[]
    for (a,p),g in d.groupby(['archive','policy']):
        for B in [*budgets,'all']:
            q=g if B=='all' else g[g.budget==B]; row=dict(archive=a,policy=p,budget=B)
            for metric in ['regret','correct','mse']:
                for e in [1,2]: row[f'{metric}_{e}']=q[f'{metric}_{e}'].mean()
                diff=q.assign(delta=q[f'{metric}_2']-q[f'{metric}_1']).groupby(['start_index','replicate']).delta.mean().unstack().reindex(index=range(12),columns=range(20)).to_numpy()
                boot=np.take_along_axis(diff[None,:,:],draws,axis=2).mean((1,2)); row[f'{metric}_delta']=diff.mean(); row[f'{metric}_lo'],row[f'{metric}_hi']=np.quantile(boot,[.025,.975])
            row['rmse_1']=np.sqrt(row['mse_1']); row['rmse_2']=np.sqrt(row['mse_2']); row['disagree']=q.disagree.mean(); rows.append(row)
    s=pd.DataFrame(rows); s.to_csv(out/'summary.csv',index=False)
    (out/'manifest.json').write_text(json.dumps({'source_zip_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'ledger_hashes_verified':True,'baseline_decisions_reproduced':len(j),'max_baseline_regret_error':float(np.max(abs(j.regret_1-j.simple_regret))),'matrix_provenance':'reconstructed from complete union of consistent hashed nested ledger cells; original matrix file hashes not reverified','top2':'not included: missing action histories','bootstrap':'paired within start, common replicate draws across budgets, nominal intervals conditional on fixed matrices','output_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.csv')}},indent=2))
    print(s[s.budget=='all'][['archive','policy','regret_1','regret_2','regret_lo','regret_hi','correct_1','correct_2','rmse_1','rmse_2','disagree']].to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path);a=p.parse_args();run(a.source,a.out)
