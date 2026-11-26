import argparse, hashlib, json, zipfile
from pathlib import Path
import pandas as pd
import numpy as np
COST={'M1':100,'M2':2700,'M3_FULL343':1400,'ORIGINAL_TOP14_B1400':1400,'ORIGINAL_TOP1_B1400':1400,'FIXED_CV_TOP14':1400,'FIXED_CV_TOP1':1400}
KEY=['archive','policy','start_index','replicate']
def run(source,out):
    p='planb_b1_nested_budget_2026_11_20_v1/'
    with zipfile.ZipFile(source) as z:
        m=json.loads(z.read(p+'nested_manifest.json'))
        for f,d in m['outputs_sha256'].items(): assert hashlib.sha256(z.read(p+f)).hexdigest()==d,f
        h=pd.read_csv(z.open(p+'nested_action_history.csv')); t=pd.read_csv(z.open(p+'nested_terminal_episodes.csv'))
    assert len(h)==230400 and len(t)==37440
    assert set(h.method)==set(COST) and set(h.policy)==set(m['policies'])
    assert not h.duplicated(KEY+['step']).any() and not h.duplicated(KEY+['method','world','graph']).any()
    assert (h.groupby(KEY).size()==80).all() and (h.groupby(KEY).step.agg(['min','max'])==[1,80]).all().all()
    assert (h[h.step<=7].groupby(KEY).method.nunique()==7).all()
    h=h.sort_values(KEY+['step']); h['work']=h.method.map(COST); h['trajectories']=h.groupby(KEY).work.cumsum()
    assert (h.loc[h.step==7,'trajectories']==9800).all()
    d=t.merge(h[KEY+['step','trajectories']].rename(columns={'step':'budget'}),on=KEY+['budget'],validate='one_to_one'); assert len(d)==len(t)
    s=d.groupby(['archive','policy','budget']).agg(episodes=('trajectories','size'),mean_trajectories=('trajectories','mean'),sd_trajectories=('trajectories','std'),mean_regret=('simple_regret','mean'),pcs=('correct','mean')).reset_index(); assert (s.episodes==240).all()
    # First checkpoint whose regret and every later checkpoint meet target, not a trajectory-budget policy.
    rows=[]
    for (a,p),g in s.groupby(['archive','policy']):
        g=g.sort_values('budget'); ok=g.mean_regret.iloc[::-1].cummax().iloc[::-1]<=.002
        if ok.any():
            v=g[ok].iloc[0]; rows.append(dict(archive=a,policy=p,budget=int(v.budget),mean_trajectories=v.mean_trajectories,mean_regret=v.mean_regret,pcs=v.pcs))
        else: rows.append(dict(archive=a,policy=p,budget=None,mean_trajectories=None,mean_regret=None,pcs=None))
    q=pd.DataFrame(rows); agg=s.groupby(['archive','policy'])[['mean_trajectories','mean_regret','pcs']].mean().reset_index()
    out.mkdir(parents=True,exist_ok=False)
    for name,obj in [('episodes',d),('budget_summary',s),('threshold_summary',q),('aggregate_summary',agg)]: obj.to_csv(out/(name+'.csv'),index=False)
    (out/'manifest.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'archive_hashes_verified':True,'cost':COST,'full_catalogue_prediction_trajectories':12*sum(COST.values()),'scope':'nominal prediction graph trajectories; excludes shared preparation, WB, timing, overhead and cached execution effects','top2':'missing action histories','threshold':.002,'output_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.csv')}},indent=2))
    print(q.to_string(index=False)); print(agg.to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path);a=p.parse_args();run(a.source,a.out)
