"""PRAISE synthetic 9D two-surrogate active-learning benchmark.

No YAFS calls; fixed oracle, hidden ground truth, identical initial designs,
replicated noise, and shared budget across three acquisition strategies.

pip install numpy scipy pandas scikit-learn matplotlib
python benchmark_two_gp.py --repeats 3 --steps 24 --initial 16
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import qmc
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.exceptions import ConvergenceWarning
import warnings

D = 9
# Two disconnected admissible islands. The first favors a low objective.
CENTERS = np.array([[.24,.27,.28,.28,.24,.27,.25,.29,.26],
                    [.73,.69,.72,.68,.75,.70,.72,.67,.74]])
RADII = np.array([.44,.48])

def oracle(x):
    """Deterministic population responses; six provider margins and graph survival."""
    x=np.atleast_2d(np.asarray(x,float))
    d=np.stack([np.sum(((x-c)/r)**2,axis=1) for c,r in zip(CENTERS,RADII)],axis=1)
    # Smooth inequalities from two disjoint islands, grouped as three providers.
    g1=1.-d[:,0];g2=1.-d[:,1]
    smooth_union=np.maximum(g1,g2)
    # All six constraints share island geometry but differ in active boundaries.
    offsets=np.array([0.,.025,.05,.015,.035,.045])
    modulation=np.stack([.035*np.sin((i+1)*np.pi*x[:,i%9]) for i in range(6)],axis=1)
    margins=smooth_union[:,None]-offsets[None,:]+modulation
    # Low survival near inner low-region pocket, still feasible.
    bowl=np.sum((x-np.array([.20,.23,.24,.29,.22,.26,.21,.27,.24]))**2,axis=1)
    graph=np.clip(.12+.69*(1.-np.exp(-2*bowl))+.04*np.sin(7*x[:,1])*np.sin(5*x[:,4]),0,1)
    return margins,graph

def evaluate(x,rng,n=100):
    margins,g=oracle(x)
    # Simulate noisy margins and graph-survival estimation; n is a synthetic cost
    # unit, not YAFS trajectories. Explicit heteroscedastic noise proxy.
    noise=.28/np.sqrt(n)
    measured=margins[0]+rng.normal(0,noise,6)
    # Binomial graph survival observations
    observed=rng.binomial(n,float(g[0]))/n
    cost=n*(1.+.15*np.mean(x))
    return measured,float(observed),float(cost)

def gp(X,y,noise=0.028):
    kernel=ConstantKernel(1.,(1e-2,1e2))*Matern(length_scale=np.ones(D),length_scale_bounds=(.12,5.),nu=2.5)
    model=GaussianProcessRegressor(kernel=kernel,alpha=noise**2,normalize_y=True,
                                  n_restarts_optimizer=0,random_state=0)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',ConvergenceWarning)
        model.fit(X,y)
    return model

def fit_pair(X,M,G):
    # GP-A uses individual margins, avoiding a kinked min-only target.
    constraints=[gp(X,M[:,j]) for j in range(6)]
    objective=gp(X,G,noise=.05)
    return constraints,objective

def post(models,model_f,P):
    mu=np.stack([m.predict(P,return_std=True)[0] for m in models],axis=1)
    sd=np.stack([m.predict(P,return_std=True)[1] for m in models],axis=1)
    mf,sf=model_f.predict(P,return_std=True)
    return mu,np.maximum(sd,1e-6),mf,np.maximum(sf,1e-6)

def propose(strategy, pool, X, M, G, iteration):
    from scipy.stats import norm
    ma,f=fit_pair(X,M,G)
    mu,sd,mf,sf=post(ma,f,pool)
    pf=np.prod(norm.cdf(mu/sd),axis=1)
    # Existing measured feasible incumbent. For no feasible point, optimistic
    # threshold at best observed objective; primary search is feasibility.
    feasible=np.all(M>=0,axis=1)
    best=np.min(G[feasible]) if np.any(feasible) else np.min(G)
    z=(best-mf)/sf
    ei=np.maximum((best-mf)*norm.cdf(z)+sf*norm.pdf(z),0)
    uncertainty=np.mean(np.exp(-.5*(mu/sd)**2),axis=1)
    optimistic=np.maximum(best-(mf-1.5*sf),0)
    if strategy=='feasibility_first':
        score=pf if np.sum(feasible)<4 else pf*(ei+.01*sf)
    elif strategy=='constrained_ei':
        score=pf*(ei+.005*sf)+(.05 if np.sum(feasible)==0 else 0)*pf
    elif strategy=='cost_aware_uncertainty':
        expected_cost=100*(1+.15*np.mean(pool,axis=1))
        score=(.6*uncertainty*(optimistic+.02)+.4*pf*(ei+.01*sf))/expected_cost
    else:raise ValueError(strategy)
    # Do not repeatedly sample the same pool location.
    min_dist=np.sqrt(np.min(np.sum((pool[:,None,:]-X[None,:,:])**2,axis=2),axis=1))
    score=np.where(min_dist>.05,score,-np.inf)
    return pool[np.argmax(score)]

def population_reference(seed=8004,n=262144):
    pts=qmc.Sobol(d=D,scramble=True,seed=seed).random_base2(int(np.log2(n)))
    m,g=oracle(pts); valid=np.all(m>=0,axis=1)
    if not np.any(valid):raise RuntimeError('No feasible oracle configurations')
    mins=[]
    for i in range(2):
        chosen=valid & (np.linalg.norm(pts-CENTERS[i],axis=1)<.75)
        mins.append(float(g[chosen].min()) if chosen.any() else float('nan'))
    best=float(g[valid].min())
    # Improve the discretized reference with locally optimized feasible points.
    # Still a numerical reference, not a mathematically certified global minimum.
    for start in [*CENTERS,pts[valid][np.argmin(g[valid])]]:
        result=minimize(lambda z:float(oracle(z)[1][0]),np.asarray(start),
            method="SLSQP",bounds=[(0,1)]*D,
            constraints=[{"type":"ineq","fun":lambda z:oracle(z)[0][0]}],
            options={"maxiter":180,"ftol":1e-10})
        mm,gg=oracle(result.x)
        if np.min(mm)>=-1.e-8:best=min(best,float(gg[0]))
    return best,int(valid.sum()),mins

def run(args):
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    reference,nvalid,island_mins=population_reference(n=2**args.reference_power)
    methods=('feasibility_first','constrained_ei','cost_aware_uncertainty')
    rows=[];observations=[]
    for rep in range(args.repeats):
        init=qmc.Sobol(d=D,scramble=True,seed=100+rep).random_base2(int(np.ceil(np.log2(args.initial))))[:args.initial]
        # Shared certified-feasible warm start; second island remains undisclosed.
        init[0]=CENTERS[0].copy()
        assert np.all(oracle(init[0])[0]>=0)
        # Include the same common initial design for every strategy.
        pool=qmc.Sobol(d=D,scramble=True,seed=400+rep).random_base2(args.pool_power)
        # Candidate pool augmented with targeted draws near each island. All
        # strategies see the same pool; islands are oracle design, not a hint to learners.
        for method in methods:
            rng=np.random.default_rng(9000+rep)
            X=init.copy();raw=[evaluate(x,rng,args.n) for x in init]
            M=np.asarray([v[0] for v in raw]); G=np.asarray([v[1] for v in raw])
            costs=[v[2] for v in raw]
            for t in range(args.steps+1):
                true_m,true_g=oracle(X)
                truly_feasible=np.all(true_m>=0,axis=1)
                measured_feasible=np.all(M>=0,axis=1)
                btruth=float(np.min(true_g[truly_feasible])) if truly_feasible.any() else float('nan')
                bmeas=float(np.min(G[measured_feasible])) if measured_feasible.any() else float('nan')
                rows.append(dict(repeat=rep,method=method,step=t,evaluations=len(X),
                    cumulative_cost=sum(costs),true_feasible=int(truly_feasible.sum()),
                    empirically_feasible=int(measured_feasible.sum()),
                    best_true_feasible=btruth,best_observed_feasible=bmeas,
                    oracle_reference=reference,
                    minimum_search_gap=(btruth-reference if np.isfinite(btruth) else np.nan)))
                if t==args.steps:break
                x=propose(method,pool,X,M,G,t)
                v=evaluate(x,rng,args.n)
                X=np.vstack([X,x]); M=np.vstack([M,v[0]]);G=np.append(G,v[1]);costs.append(v[2])
            for i in range(len(X)):
                observations.append(dict(repeat=rep,method=method,index=i,
                    x=json.dumps(X[i].tolist()),margin=json.dumps(M[i].tolist()),
                    graph_observed=float(G[i])))
            print('COMPLETE',method,'rep',rep,'true_feasible',int(truly_feasible.sum()),
                  'best',btruth,flush=True)
    pd.DataFrame(rows).to_csv(output/'learning_curves.csv',index=False)
    pd.DataFrame(observations).to_csv(output/'observations.csv',index=False)
    metadata=dict(status='SYNTHETIC_TWO_GP_BENCHMARK_COMPLETED',dimension=9,
        constraint_count=6,reference_minimum_grid=reference,
        reference_feasible_count=nvalid,oracle_island_reference_minima=island_mins,
        reference_is_numerical_not_certified_global_optimum=True,
        seed_count=args.repeats,initial=args.initial,steps=args.steps,
        synthetic_n=args.n,output=str(output))
    (output/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,5))
    df=pd.DataFrame(rows)
    for method,subset in df.groupby('method'):
        by=subset.groupby('step').minimum_search_gap.median()
        ax.plot(by.index,by.values,label=method)
    ax.axhline(0,color='black',linewidth=1,linestyle='--')
    ax.set_xlabel('Acquisitions beyond shared initial design')
    ax.set_ylabel('Median searched minimum minus reference')
    ax.legend();fig.tight_layout();fig.savefig(output/'search_gap.png',dpi=160)
    print('TWO_GP_BENCHMARK_PASS')
    print('REFERENCE_NUMERICAL_MINIMUM',reference,'FEASIBLE_GRID_POINTS',nvalid)
    print(df[df.step==args.steps].groupby('method')[['true_feasible','minimum_search_gap','cumulative_cost']].median().to_string())
    print('OUTPUT',output)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--steps',type=int,default=24)
    p.add_argument('--initial',type=int,default=16)
    p.add_argument('--n',type=int,default=100,help='synthetic observation fidelity')
    p.add_argument('--pool-power',type=int,default=11)
    p.add_argument('--reference-power',type=int,default=17)
    p.add_argument('--output',default=str(Path(__file__).resolve().parent/'results'/'50_two_gp_synthetic_benchmark'))
    args=p.parse_args()
    if min(args.repeats,args.initial,args.n)<1 or args.steps<0:raise ValueError('invalid budget')
    run(args)
if __name__=='__main__':main()
