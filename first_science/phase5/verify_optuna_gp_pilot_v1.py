"""Independent native verification of Optuna pilot candidates.

Compares best observed feasible candidate to P4 truth using matching fresh seeds.
Pilot disclosures are synthetic empirical thresholds, not certified guarantees.
"""
from __future__ import annotations
import argparse,json,sqlite3
from pathlib import Path
from math import sqrt
import numpy as np
import pandas as pd
import optuna
from optuna.trial import TrialState
from phase5_runtime_v2 import load_phase5_contracts,graph_record
from run_phase5_step0_v2 import _hidden_surrogates,_local_boundary_at_rho,_base_boundary
from run_optuna_gp_guarantee_pilot_v1 import curves,HORIZONS,PROVIDERS,HERE,OUT
from m1_graph_simulator_v2 import GraphProviderSurrogate

def wilson(k,n,z=1.959963984540054):
    p=k/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den
    d=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0.,c-d),min(1.,c+d)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--study-dir",type=Path,required=True)
    ap.add_argument("--seeds",type=int,default=60)
    ap.add_argument("--seed-base",type=int,default=99100000)
    ap.add_argument("--trial-number",type=int,default=None)
    args=ap.parse_args()
    if args.seeds<2:raise ValueError("Need >=2 independent trajectories")
    root=args.study_dir.resolve()
    config=json.loads((root/"contract.json").read_text())
    if config.get("status")!="SYNTHETIC_GRAPH_CONDITIONED_NOT_I1":
        raise RuntimeError("Wrong contract")
    study=optuna.load_study(study_name="praise_pilot_"+root.name.split("_")[-1],
                            storage="sqlite:///"+str(root/"study.sqlite3"))
    trials=[t for t in study.trials if t.state==TrialState.COMPLETE]
    if args.trial_number is not None:
        chosen=[t for t in trials if t.number==args.trial_number]
        if len(chosen)!=1:raise ValueError("trial number not complete")
        target=chosen[0]
    else:
        feasible=[t for t in trials if t.constraints is not None and
                  len(t.constraints)>0 and max(t.constraints.values())<=0]
        if not feasible:raise RuntimeError("No nominally feasible completed trial")
        target=min(feasible,key=lambda x:x.value)
    c=load_phase5_contracts(HERE);g=graph_record(c,"G_SEQPAR")
    truth=_hidden_surrogates(c,"P4")
    rho=float(config["config"]["rho"])
    cards={p:json.loads((HERE/"results"/"01_i1"/"P4"/"public"/p/"card.json").read_text()) for p in PROVIDERS}
    bounds={p:_local_boundary_at_rho(cards[p],rho) for p in PROVIDERS}
    gb=_base_boundary(c,graph_id="G_SEQPAR",cards=cards,rho=rho)
    candidate={}
    for p in PROVIDERS:
        candidate[p]=GraphProviderSurrogate(**{x:float(target.params[p+"."+x])
            for x in ("mean_service_time","cost_rate","service_cv")})
    # Both evaluations use the same fresh seed block for a paired comparison.
    train_lo=int(config["config"]["seed_base"])
    train_hi=train_lo+1000+(max(t.number for t in trials)+1)*int(config["config"]["seeds_per_trial"])
    fresh=set(range(args.seed_base,args.seed_base+args.seeds))
    if fresh.intersection(range(train_lo,train_hi)):
        raise RuntimeError("Verification seeds overlap calibration/optimization")
    disclosure=config["disclosures"]
    records=[]
    for label,theta in [("P4_truth",truth),("candidate",candidate)]:
        # Preserve each trajectory separately to construct Wilson intervals.
        for seed in sorted(fresh):
            s=curves(theta,[seed],c,g,bounds,gb,rho)
            for p in (*PROVIDERS,"G"):
                for i,h in enumerate(HORIZONS):
                    records.append(dict(model=label,seed=seed,object=p,horizon=h,
                                        survived=int(round(s[p][i]))))
            if (seed-args.seed_base+1)%10==0:print("VALIDATED",label,seed-args.seed_base+1,flush=True)
    df=pd.DataFrame(records)
    summary=[]
    for (label,p,h),part in df.groupby(["model","object","horizon"]):
        k=int(part.survived.sum());n=len(part)
        low,high=wilson(k,n)
        b=None if p=="G" else float(disclosure[p][str(float(h))])
        summary.append(dict(model=label,object=p,horizon=h,
            successes=k,n=n,survival=k/n,wilson_low=low,wilson_high=high,
            synthetic_threshold=b,
            empirical_margin=None if b is None else k/n-b,
            confident_above_threshold=None if b is None else bool(low>=b),
            possibly_below_threshold=None if b is None else bool(low<b)))
    report=pd.DataFrame(summary)
    out=root/"independent_verification"
    out.mkdir(exist_ok=True)
    df.to_csv(out/"seed_outcomes.csv",index=False)
    report.to_csv(out/"verification_summary.csv",index=False)
    meta=dict(status="INDEPENDENT_VERIFICATION_COMPLETED",
              chosen_trial=target.number,nominal_training_objective=target.value,
              verification_seeds=args.seeds,verification_seed_base=args.seed_base,
              warning="Wilson intervals are pointwise, not simultaneous across p/H",
              synthetic_only=True,not_certified=True)
    (out/"verification.json").write_text(json.dumps(meta,indent=2)+"\n")
    print("INDEPENDENT_VERIFICATION_COMPLETED")
    print(report.to_string(index=False))
    print("OUTPUT",out)
if __name__=="__main__":main()
