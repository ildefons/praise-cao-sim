"""Read-only analytical inference for fixed-condition validation experiments.
Usage: python audit_intervals.py /mnt/data /mnt/data/analytical_revision
"""
import sys, json, hashlib, zipfile, io
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import t
root,out=map(Path,sys.argv[1:]);out.mkdir(exist_ok=True,parents=True)
read=lambda name: pd.read_csv(root/name)
sha=lambda data: hashlib.sha256(data).hexdigest()
check=lambda name,digest: sha((root/name).read_bytes())==digest
nm=json.loads((root/'nested_manifest(1).json').read_text());sm=json.loads((root/'scenario_manifest.json').read_text())
for k,v in nm['outputs_sha256'].items():
    assert check(k.replace('.csv','(1).csv'),v),k
assert check('terminal_episodes(1).csv',sm['outputs_sha256']['terminal_episodes.csv'])
assert check('combined_nine_policy_budget_summary.csv',json.loads((root/'plot_manifest.json').read_text())['output_sha256']['combined_nine_policy_budget_summary.csv'])
B=nm['budgets']; AR=list(nm['archive_sources']); NEST=nm['policies']; POL=sm['policies']; TOP=[p for p in POL if p not in NEST]; n=nm['repeats_per_start']; C=nm['starts']
keys=['archive','policy','budget','start_index','replicate']
base=read('terminal_episodes(1).csv');assert set(base.scenario)=={'base'}
nested=read('nested_terminal_episodes(1).csv')
par=base[base.policy.isin(NEST)].merge(nested,on=keys,validate='one_to_one',suffixes=('_b','_n'))
assert len(par)==len(nested)==2*6*13*C*n
for col in ['recommended','correct']:
    assert (par[col+'_b']==par[col+'_n']).all()
assert np.allclose(par.simple_regret_b,par.simple_regret_n,rtol=0,atol=1e-12)
oldc=read('controlled_terminal_episodes.csv');assert check('controlled_terminal_episodes.csv',json.loads((root/'cross_design_manifest(1).json').read_text())['input_sources']['historical']['old_historical_controlled_sha256'])
oldc=oldc[oldc.policy.isin(TOP)].assign(archive='historical');p=base.merge(oldc,on=keys,validate='one_to_one',suffixes=('_b','_o'));assert len(p)==len(oldc)==2400
for col in ['recommended','correct']:
    assert (p[col+'_b']==p[col+'_o']).all(),col
assert np.allclose(p.simple_regret_b,p.simple_regret_o,rtol=0,atol=1e-12)
print('Original historical Top2 partial parity:',len(p))
data=pd.concat([nested,base[base.policy.isin(TOP)]],ignore_index=True)
summary=read('combined_nine_policy_budget_summary.csv');compare=data.groupby(['archive','policy','budget']).agg(mean_regret=('simple_regret','mean'),p_correct=('correct','mean'),n=('correct','size')).reset_index().merge(summary,on=['archive','policy','budget'],validate='one_to_one',suffixes=('_new','_old'));assert len(compare)==234 and (compare.n==240).all()
for col in ['mean_regret','p_correct']:
    assert np.allclose(compare[col+'_new'],compare[col+'_old'],rtol=0,atol=1e-12)
# Strata are fixed; all estimates are linear combinations of independent stratum means.
# For nested policies, average over budgets *within each run* before estimating variances.
# For Top2, separate budget-specific random streams imply independent means across budgets.
# Paired covariance-model contrasts average paired differences within each run.
def array(df):
    a=df.pivot(index=['start_index','replicate'],columns='budget',values='simple_regret').reindex(index=pd.MultiIndex.from_product([range(C),range(n)],names=['start_index','replicate']),columns=B).to_numpy().reshape(C,n,len(B));assert np.isfinite(a).all();return a
X={(a,p):array(data[(data.archive==a)&(data.policy==p)]) for a in AR for p in POL}
def components(x,ix,nested=True):
    y=x[:,:,ix];m=float(y.mean());
    if nested: v=y.mean(axis=2).var(axis=1,ddof=1)/(n*C*C)
    else: v=y.var(axis=1,ddof=1).ravel()/(n*C*C*len(ix)**2)
    return m,v
# Welch-Satterthwaite approximation using each independent variance component's 19 df.
def ci(m,v,family=1):
    v=np.asarray(v);se=float(np.sqrt(v.sum()));df=float(v.sum()**2/(np.sum(v**2)/(n-1))) if se else float('inf');half=float(t.ppf(1-.05/(2*family),df)*se);return dict(estimate=m,se=se,df=df,family_size=family,low=m-half,high=m+half)
rows=[]
for a in AR:
 for p in POL:
  for i,b in enumerate(B):
   m,v=components(X[a,p],[i]);r=ci(m,v);rows.append(dict(archive=a,policy=p,budget=b,**r,plot_low=max(0,r['low']),plot_high=r['high']))
f=pd.DataFrame(rows);f.to_csv(out/'analytical_curve_intervals.csv',index=False)
print('curve points',len(f),'negative lower bounds',sum(f.low<0));print(f.groupby('archive').agg(low=('low','min'),high=('high','max')))
rows=[]
for a in AR:
 for p in TOP+['kg_two_stage_uniform']:
  for label,ix in [('all',list(range(len(B)))),('10_to_40',[i for i,b in enumerate(B) if b<=40])]:
   m1,v1=components(X[a,'kg_two_stage_adaptive'],ix);m2,v2=components(X[a,p],ix,p in NEST);rows.append(dict(archive=a,comparator=p,budget_set=label,**ci(m1-m2,np.r_[v1,v2],3 if p in TOP else 2)))
g=pd.DataFrame(rows);g.to_csv(out/'analytical_main_contrasts.csv',index=False)
print(g.to_string(index=False))
with zipfile.ZipFile(root/'PRAISE_S1_S2_development_v1.zip') as z:
    man=json.loads(z.read('MANIFEST.json'));raw=z.read('results/s1_sequential_terminal.csv');assert sha(raw)==man['sha256']['results/s1_sequential_terminal.csv'];cov=pd.read_csv(io.BytesIO(raw));print('covariance models',cov.model.unique())
rows=[]
for a in AR:
 for p in ['kg_one_step','kg_two_stage_adaptive']:
  x={m:array(cov[(cov.archive==a)&(cov.policy==p)&(cov.model==m)]) for m in cov.model.unique()};bm=[m for m in x if m.startswith('B_')][0]
  for prefix in ['A_','D_']:
   other=[m for m in x if m.startswith(prefix)][0];m,v=components(x[bm]-x[other],list(range(len(B))));rows.append(dict(archive=a,policy=p,comparator=other,**ci(m,v)))
h=pd.DataFrame(rows);h.to_csv(out/'analytical_covariance_contrasts.csv',index=False);print(h.to_string(index=False))
