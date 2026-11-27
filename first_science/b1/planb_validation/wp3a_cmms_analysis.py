#!/usr/bin/env python3
"""WP3a frozen conditional inference; no acquisitions or new reference data."""
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import t as student
from wp3a_policy_core import POLICIES,NESTED
from wp3a_cmms_replay import (CAT,BUDGETS,REPEATS,SCENARIOS,STRUCTURES,STRUCT_POLICIES,
                               design,verify_case,sha,dump,require)

SEED=20261128
EARLY=BUDGETS[:7]
ADAPTIVE="kg_two_stage_adaptive"
TOP2=POLICIES[6:]
CASE_IDS={n:i for i,n in enumerate((*SCENARIOS,"balanced_runs",*STRUCTURES))}


def arrays(rows,policies):
    """Fixed budget x initial-condition x replicate shape, no missing keys."""
    index=pd.MultiIndex.from_product([BUDGETS,range(CAT.C),range(REPEATS)],
                                    names=["budget","start_index","replicate"])
    out={}
    for p in policies:
        g=rows[rows.policy==p].set_index(list(index.names))
        require(g.index.is_unique and len(g)==len(index) and set(g.index)==set(index),"Invalid terminal grid")
        g=g.reindex(index)
        for key in ("simple_regret","correct"):
            vals=g[key].to_numpy(dtype=float).reshape(len(BUDGETS),CAT.C,REPEATS)
            require(np.isfinite(vals).all(),"Nonfinite terminal outcome")
            out[p,key]=vals
    return out


def variance_components(x,nested):
    """x: budgets x fixed start strata x replicate. Independent budget
    streams for Top2; nested streams retain checkpoint dependence."""
    B,C,R=x.shape
    if nested:
        return x.mean(axis=0).var(axis=-1,ddof=1)/(R*C*C)
    return (x.var(axis=-1,ddof=1)/(R*C*C*B*B)).ravel()


def interval(mean,components,alpha=.05,R=REPEATS):
    components=np.asarray(components)
    var=float(components.sum())
    if var==0:
        return mean,mean,0.,None
    df=var**2/float((components**2).sum()/(R-1))
    se=np.sqrt(var)
    margin=float(student.ppf(1-alpha/2,df))*se
    return float(mean-margin),float(mean+margin),float(se),float(df)


def boot(x,nested,n,rng,draws=None):
    """Conditional replicate bootstrap. For nested use within-run means
    before resampling; budget-specific rules resample independently by B."""
    B,C,R=x.shape
    if nested:
        a=x.mean(axis=0)
        if draws is None:
            draws=rng.integers(R,size=(n,C,R))
        return np.take_along_axis(a[None,:,:],draws,axis=2).mean(axis=(1,2))
    ans=np.zeros(n)
    for a in x:
        idx=rng.integers(R,size=(n,C,R))
        ans+=np.take_along_axis(a[None,:,:],idx,axis=2).mean(axis=(1,2))/B
    return ans


def boot_rng(case,policy,metric,scope):
    return np.random.default_rng(np.random.SeedSequence(
        [SEED,CASE_IDS[case],POLICIES.index(policy),metric,scope]))


def q95(draws):
    return tuple(map(float,np.quantile(draws,[.025,.975])))


def summarize(case,arr,policies):
    rows=[]
    for p in policies:
        for i,b in enumerate(BUDGETS):
            r=arr[p,"simple_regret"][i:i+1]
            c=arr[p,"correct"][i:i+1]
            rm,cm=float(r.mean()),float(c.mean())
            lo,hi,se,df=interval(rm,variance_components(r,True))
            cl,ch,cse,cdf=interval(cm,variance_components(c,True))
            rows.append(dict(case=case,policy=p,budget=b,episodes=CAT.C*REPEATS,
                mean_regret=rm,regret_low95=lo,regret_high95=hi,regret_se=se,regret_df=df,
                pcs=cm,pcs_low95=max(0.,cl),pcs_high95=min(1.,ch),pcs_se=cse,pcs_df=cdf,
                regret_p90=float(np.quantile(r,.9))))
    return rows


def contrasts(case,arr):
    rows=[]
    others=[p for p in POLICIES if p!=ADAPTIVE]
    nboot=10000 if case=="base" else 3000
    for scope,ix in (("all",slice(None)),("early",slice(0,7))):
        for m,key in enumerate(("simple_regret","correct")):
            xs={p:arr[p,key][ix] for p in POLICIES}
            comps={p:variance_components(x,p in NESTED) for p,x in xs.items()}
            draws={p:boot(x,p in NESTED,nboot,boot_rng(case,p,m,0 if scope=="all" else 1))
                   for p,x in xs.items()}
            for p in others:
                diff=float(xs[ADAPTIVE].mean()-xs[p].mean())
                v=np.concatenate((comps[ADAPTIVE],comps[p]))
                lo,hi,se,df=interval(diff,v)
                # Only baseline all-budget regret family is primary.
                primary=case=="base" and scope=="all" and key=="simple_regret"
                flo,fhi,_,_=interval(diff,v,.05/len(others)) if primary else (None,None,None,None)
                blo,bhi=q95(draws[ADAPTIVE]-draws[p])
                rows.append(dict(case=case,scope=scope,metric=key,left=ADAPTIVE,right=p,
                                 difference=diff,low95=lo,high95=hi,se=se,df=df,
                                 familywise_low95=flo,familywise_high95=fhi,
                                 bootstrap_low95=blo,bootstrap_high95=bhi,bootstrap_draws=nboot,
                                 primary=primary))
    return rows


def budget_contrasts(case,arr):
    rows=[]
    for i,b in enumerate(BUDGETS):
        for metric in ("simple_regret","correct"):
            x=arr[ADAPTIVE,metric][i:i+1]
            for p in POLICIES:
                if p==ADAPTIVE:
                    continue
                z=arr[p,metric][i:i+1]
                diff=float(x.mean()-z.mean())
                lo,hi,se,df=interval(diff,np.r_[variance_components(x,True),variance_components(z,True)])
                rows.append(dict(case=case,budget=b,metric=metric,left=ADAPTIVE,right=p,
                                 difference=diff,low95=lo,high95=hi,se=se,df=df))
    return rows


def sensitivity(loaded):
    rows=[]; budget_rows=[]; direction=[]
    for name in SCENARIOS:
        arr=loaded[name]
        r={p:float(arr[p,"simple_regret"].mean()) for p in POLICIES}
        pcs={p:float(arr[p,"correct"].mean()) for p in POLICIES}
        best=min(TOP2,key=lambda p:r[p])
        for p in POLICIES:
            rows.append(dict(case=name,policy=p,mean_regret=r[p],mean_pcs=pcs[p],
                         rank=1+sum(v<r[p]-1e-12 for v in r.values()),
                         adaptive_minus_policy=r[ADAPTIVE]-r[p],
                         best_top2=best,adaptive_minus_best_top2=r[ADAPTIVE]-r[best],
                         adaptive_to_best_top2=r[ADAPTIVE]/r[best] if r[best]>0 else None))
            if p==ADAPTIVE:
                continue
            for i,b in enumerate(BUDGETS):
                delta=float(arr[ADAPTIVE,"simple_regret"][i].mean()-arr[p,"simple_regret"][i].mean())
                budget_rows.append(dict(case=name,budget=b,opponent=p,difference=delta))
    r=pd.DataFrame(rows); br=pd.DataFrame(budget_rows)
    for p in POLICIES:
        if p==ADAPTIVE:
            continue
        x=r[r.policy==p].adaptive_minus_policy.to_numpy()
        direction.append(dict(opponent=p,budget="all",wins=int((x < -1e-12).sum()),
            ties=int((abs(x)<=1e-12).sum()),losses=int((x>1e-12).sum()),min_difference=x.min(),max_difference=x.max()))
        for b in BUDGETS:
            x=br[(br.opponent==p)&(br.budget==b)].difference.to_numpy()
            direction.append(dict(opponent=p,budget=str(b),wins=int((x < -1e-12).sum()),
                ties=int((abs(x)<=1e-12).sum()),losses=int((x>1e-12).sum()),min_difference=x.min(),max_difference=x.max()))
    spread=[dict(budget=b,adaptive_regret_min=min(float(loaded[n][ADAPTIVE,"simple_regret"][i].mean()) for n in SCENARIOS),
                 adaptive_regret_max=max(float(loaded[n][ADAPTIVE,"simple_regret"][i].mean()) for n in SCENARIOS))
            for i,b in enumerate(BUDGETS)]
    return r,br,pd.DataFrame(direction),pd.DataFrame(spread)


def structural(loaded):
    """Same-policy/model common seed IDs permit matched-stream differences."""
    rows=[]
    for p in STRUCT_POLICIES:
        for m,(left,right) in enumerate((("base","exchangeable"),("base","independent"),("interaction25","base"))):
            for key in ("simple_regret","correct"):
                delta=loaded[left][p,key]-loaded[right][p,key]
                for scope,idx in [("all",slice(None))]+[(str(b),slice(i,i+1)) for i,b in enumerate(BUDGETS)]:
                    x=delta[idx]; mean=float(x.mean())
                    rng=np.random.default_rng(np.random.SeedSequence(
                        [SEED,91,POLICIES.index(p),m,int(key=="correct"),0 if scope=="all" else int(scope)]))
                    lo,hi=q95(boot(x,True,3000,rng))
                    rows.append(dict(policy=p,metric=key,left=left,right=right,budget=scope,
                                     difference=mean,matched_bootstrap_low95=lo,matched_bootstrap_high95=hi,
                                     primary_structural_contrast=left=="base" and right=="exchangeable" and key=="simple_regret" and scope=="all"))
    return pd.DataFrame(rows)


def analyse(root,hashes,prov):
    root=Path(root); dest=root/"analysis"
    cases=(*SCENARIOS,"balanced_runs",*STRUCTURES)
    manifests={}; loaded={}
    for case in cases:
        matrix,_,_,policies=design(case)
        verify_case(root,case,hashes[matrix+".csv"],prov)
        manifests[case]=sha(root/case/"manifest.json")
        rows=pd.read_csv(root/case/"terminals.csv",float_precision="round_trip")
        loaded[case]=arrays(rows,policies)
    marker=root/"additive_covariance_check.json"
    check=json.loads(marker.read_text())
    base=json.loads((root/"base/manifest.json").read_text())
    require(check["status"]=="PASS" and
            check["base_paths_sha256"]==base["outputs_sha256"]["paths.npz"] and
            check["base_terminals_sha256"]==base["outputs_sha256"]["terminals.csv"],
            "Additive covariance reproduction missing")
    manifests["additive_covariance_check"]=sha(marker)
    if dest.exists():
        m=json.loads((dest/"manifest.json").read_text())
        require(m["case_manifest_sha256"]==manifests and m["provenance"]["code_and_protocol_sha256"]==prov["code_and_protocol_sha256"],"Existing analysis mismatch")
        for f,h in m["outputs_sha256"].items():
            require(sha(dest/f)==h,"Analysis output hash mismatch")
        print("WP3A_ANALYSIS_ALREADY_VERIFIED")
        return
    summary=[]; allcontr=[]; budgets=[]
    for case in cases:
        _,_,_,policies=design(case)
        summary.extend(summarize(case,loaded[case],policies))
        if case in SCENARIOS or case=="balanced_runs":
            allcontr.extend(contrasts(case,loaded[case]))
            if case in ("base","balanced_runs"):
                budgets.extend(budget_contrasts(case,loaded[case]))
    r,br,direction,spread=sensitivity(loaded)
    # Sensitivity of the primary conclusions to unequal episode bundles.
    replication=[]
    for p in POLICIES:
        for key in ("simple_regret","correct"):
            for scope,ix in [("all",slice(None))]+[(str(b),slice(i,i+1)) for i,b in enumerate(BUDGETS)]:
                x=loaded["base"][p,key][ix]; z=loaded["balanced_runs"][p,key][ix]
                replication.append(dict(policy=p,metric=key,budget=scope,primary=float(x.mean()),
                                        balanced_runs=float(z.mean()),balanced_minus_primary=float(z.mean()-x.mean())))
    tables={"policy_budget_summary.csv":pd.DataFrame(summary),
            "aggregate_contrasts.csv":pd.DataFrame(allcontr),
            "budget_contrasts.csv":pd.DataFrame(budgets),
            "prior_sensitivity_aggregate.csv":r,
            "prior_sensitivity_budget_differences.csv":br,
            "prior_sensitivity_direction.csv":direction,
            "prior_sensitivity_spread.csv":spread,
            "replication_sensitivity.csv":pd.DataFrame(replication),
            "structural_contrasts.csv":structural(loaded)}
    tmp=Path(tempfile.mkdtemp(prefix=".analysis_incomplete_",dir=root))
    for f,table in tables.items():
        table.to_csv(tmp/f,index=False)
    dump(tmp/"manifest.json",{"status":"WP3A_ANALYSIS_COMPLETE","case_manifest_sha256":manifests,
        "provenance":prov,"primary":"base adaptive minus 8 opponents, 13-budget mean regret; Bonferroni 95% familywise",
        "scope":"conditional policy randomness only; nested dependency preserved; independent policy streams",
        "bootstrap_seed":SEED,"bootstrap_draws_base":10000,"bootstrap_draws_sensitivity":3000,
        "outputs_sha256":{f:sha(tmp/f) for f in tables}})
    tmp.rename(dest)
    print("WP3A_ANALYSIS_COMPLETE",dest,flush=True)
