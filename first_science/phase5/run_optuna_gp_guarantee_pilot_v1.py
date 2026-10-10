"""Resumable *exploratory* Optuna GP optimization on G_SEQPAR.

This is a synthetic, graph-conditioned guarantee scenario, NOT inference from
frozen W0/ParAll I1. It does NOT certify a worst-case lower bound. Outputs
independent native first-violation curves, same definitions as diagnostic v1.
"""
from __future__ import annotations
import argparse, json, sys, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

import optuna
from optuna.trial import TrialState
from phase5_runtime_v2 import load_phase5_contracts, graph_record
from run_phase5_step0_v2 import _hidden_surrogates,_local_boundary_at_rho,_base_boundary
from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory
from run_four_output_survival_validation_v1 import reconstruct_local,first_violation
from m1_graph_simulator_v2 import GraphProviderSurrogate

HERE=Path(__file__).resolve().parent
OUT=HERE/"results"/"49_optuna_gp_guarantee_pilot"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
HORIZONS=(120.,240.)

def curves(theta,seeds,c,graph,boundaries,graph_boundary,rho):
    from sla_compliance_analysis import build_request_sla_decision_table
    cfg=c.battery;fam=cfg["provider_family"]
    stop=float(cfg["horizon"]["maximum_seconds"])
    inv=dict(cfg["graph_invariants"])
    inv["effective_IPT"]=float(fam["effective_IPT"])
    inv["cost_rate"]=float(fam["cost_rate"])
    inv["provider_cost_rates"]={p:theta[p].cost_rate for p in PROVIDERS}
    observations={p:[] for p in (*PROVIDERS,"G")}
    for seed in seeds:
        root,_,native=execute_one_phase5_graph_trajectory(
            graph_id="G_SEQPAR",graph_ast=graph["ast"],
            provider_surrogates=theta,graph_invariants=inv,
            workload_period=float(cfg["workload"]["period_seconds"]),
            stop_time=stop,trajectory_seed=seed,
            canonical_ipt=float(fam["effective_IPT"]),
            execution_fraction=float(fam["execution_fraction_x"]),
            return_native_rows=True)
        local,_,_=reconstruct_local(native,root,graph["ast"],inv,stop,seed)
        for p,ledger in {**local,"G":root}.items():
            b=graph_boundary if p=="G" else boundaries[p]
            decisions=build_request_sla_decision_table(
                ledger,float(b.l_max),float(b.c_max),float(b.q_min),stop)
            values,_=first_violation(decisions,rho,HORIZONS)
            observations[p].append(values)
    return {p:np.asarray(values,dtype=float).mean(axis=0).tolist()
            for p,values in observations.items()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--trials",type=int,default=12,help="New Optuna trials to run")
    ap.add_argument("--seeds-per-trial",type=int,default=6)
    ap.add_argument("--calibration-seeds",type=int,default=12)
    ap.add_argument("--rho",type=float,default=.95)
    ap.add_argument("--margin",type=float,default=.10,help="Subtract from calibration observed survival, floor at 0")
    ap.add_argument("--radius",type=float,default=.30,help="Relative bounds about P4 truth for synthetic pilot only")
    ap.add_argument("--seed-base",type=int,default=99010000)
    ap.add_argument("--sampler",choices=("gp","tpe"),default="gp")
    args=ap.parse_args()
    if not (args.trials>0 and args.seeds_per_trial>0 and args.calibration_seeds>0
        and 0<args.rho<=1 and 0<=args.margin<1 and 0<args.radius<1):
        raise ValueError("Invalid pilot parameters")
    if not hasattr(optuna.trial.Trial,"set_constraint"):
        raise RuntimeError("Require Optuna >=5 with trial.set_constraint(name,value)")
    c=load_phase5_contracts(HERE);graph=graph_record(c,"G_SEQPAR")
    truth=_hidden_surrogates(c,"P4")
    cards={p:json.loads((HERE/"results"/"01_i1"/"P4"/"public"/p/"card.json").read_text())
           for p in PROVIDERS}
    bounds={p:_local_boundary_at_rho(cards[p],args.rho) for p in PROVIDERS}
    gb=_base_boundary(c,graph_id="G_SEQPAR",cards=cards,rho=args.rho)
    OUT.mkdir(parents=True,exist_ok=True)
    config={k:v for k,v in vars(args).items() if k!="trials"}
    signature=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
    root=OUT/f"{args.sampler}_{signature}";root.mkdir(exist_ok=True)
    contract_path=root/"contract.json"
    if contract_path.exists():
        old=json.loads(contract_path.read_text())
        if old["config"]!=config:raise RuntimeError("Study config changed")
        disclosures=old["disclosures"]
    else:
        print("CALIBRATING_SYNTHETIC_DISCLOSURES",flush=True)
        reference=curves(truth,range(args.seed_base,args.seed_base+args.calibration_seeds),
                         c,graph,bounds,gb,args.rho)
        disclosures={p:{str(h):max(0.,reference[p][i]-args.margin)
                     for i,h in enumerate(HORIZONS)} for p in PROVIDERS}
        contract=dict(status="SYNTHETIC_GRAPH_CONDITIONED_NOT_I1",config=config,
                      calibration_curve=reference,disclosures=disclosures,
                      note="These are illustrative empirical thresholds, not certified probability bounds.")
        contract_path.write_text(json.dumps(contract,indent=2)+"\n")
    sampler=(optuna.samplers.GPSampler(seed=42,n_startup_trials=8)
             if args.sampler=="gp" else optuna.samplers.TPESampler(seed=42,n_startup_trials=8))
    db=root/"study.sqlite3"
    study=optuna.create_study(direction="minimize",sampler=sampler,
        storage="sqlite:///"+str(db),study_name="praise_pilot_"+signature,
        load_if_exists=True)
    def objective(trial):
        theta={}
        for p in PROVIDERS:
            t=truth[p]
            pars={}
            for name,value in (("mean_service_time",t.mean_service_time),
                               ("cost_rate",t.cost_rate),("service_cv",t.service_cv)):
                low=max(float(value)*(1-args.radius),1.e-5)
                high=max(float(value)*(1+args.radius),low+1.e-5)
                pars[name]=trial.suggest_float(f"{p}.{name}",low,high)
            theta[p]=GraphProviderSurrogate(**pars)
        # Distinct deterministic seed block per trial. Never use calibration seeds.
        base=args.seed_base+1000+trial.number*args.seeds_per_trial
        out=curves(theta,range(base,base+args.seeds_per_trial),c,graph,bounds,gb,args.rho)
        for p in PROVIDERS:
            for i,h in enumerate(HORIZONS):
                trial.set_constraint(f"{p}@{h}",
                    float(disclosures[p][str(h)]-out[p][i]))
        trial.set_user_attr("four_curves",out)
        trial.set_user_attr("seed_base",base)
        trial.set_user_attr("constraints_contract","SYNTHETIC_GRAPH_CONDITIONED_NOT_I1")
        value=float(out["G"][-1])
        print("TRIAL",trial.number,"GRAPH_FV_240",value,
              "MAX_VIOLATION",max(disclosures[p][str(h)]-out[p][i]
                  for p in PROVIDERS for i,h in enumerate(HORIZONS)),flush=True)
        return value
    study.optimize(objective,n_trials=args.trials,n_jobs=1)
    records=[]
    for t in study.trials:
        if t.state!=TrialState.COMPLETE:continue
        vals=list(t.constraints.values()) if t.constraints else []
        records.append(dict(trial=t.number,value=t.value,
            feasible=bool(vals) and max(vals)<=0,
            max_violation=max(vals) if vals else None,params=json.dumps(t.params),
            curves=json.dumps(t.user_attrs.get("four_curves"))))
    pd.DataFrame(records).to_csv(root/"trial_summary.csv",index=False)
    feasible=[r for r in records if r["feasible"]]
    print("OPTUNA_GP_PILOT_COMPLETE",len(records),"COMPLETED",len(feasible),"FEASIBLE")
    if feasible:
        best=min(feasible,key=lambda r:r["value"])
        print("BEST_OBSERVED_FEASIBLE_GRAPH_240",best["value"],"TRIAL",best["trial"])
    else:print("NO_FEASIBLE_TRIAL_DO_NOT_REPORT_LOWER_BOUND")
    print("OUTPUT",root)
if __name__=="__main__":main()
