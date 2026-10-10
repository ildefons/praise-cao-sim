"""Scientific N>=100 contract gate and resumable Optuna GP experiment.

Independent calibration and optimization seed banks. Graph-conditioned synthetic
provider confidence bounds, NOT historic W0/ParAll I1 guarantees. Abort rather
than optimize a vacuous provider constraint. No universal lower-bound claims.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import beta
import optuna
from optuna.trial import TrialState

from run_optuna_gp_guarantee_pilot_v1 import curves,HORIZONS,PROVIDERS,HERE,OUT
from phase5_runtime_v2 import load_phase5_contracts,graph_record
from run_phase5_step0_v2 import _hidden_surrogates,_local_boundary_at_rho,_base_boundary
from m1_graph_simulator_v2 import GraphProviderSurrogate

NMIN=100
ALPHA=0.05
LABEL="EXPERIMENTAL_GRAPH_CONDITIONED_FIRST_VIOLATION_CP_BONFERRONI_V2"

def simultaneous_lower(k,n,alpha_per):
    """Exact one-sided Clopper-Pearson lower bound; Bonferroni over 6 queries."""
    if k==0:return 0.
    return float(beta.ppf(alpha_per,k,n-k+1))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--calibration-only",action="store_true")
    ap.add_argument("--allow-weak-information",action="store_true",help="Reuse calibrated nonzero bounds even if heuristic informativeness gate fails")
    ap.add_argument("--trials",type=int,default=8,help="Additional study trials")
    ap.add_argument("--seeds-per-trial",type=int,default=100)
    ap.add_argument("--calibration-seeds",type=int,default=200)
    ap.add_argument("--rho",type=float,default=.95)
    ap.add_argument("--min-provider-bound",type=float,default=.05)
    ap.add_argument("--radius",type=float,default=.30)
    ap.add_argument("--seed-base",type=int,default=99200000)
    ap.add_argument("--sampler",choices=("gp","tpe"),default="gp")
    args=ap.parse_args()
    if min(args.calibration_seeds,args.seeds_per_trial)<NMIN:
        ap.error("Scientific calibration and trial evaluations require N>=100")
    if args.trials<1 or not 0<args.rho<=1 or not 0<args.radius<1 or not 0<=args.min_provider_bound<1:
        ap.error("Invalid args")
    c=load_phase5_contracts(HERE);graph=graph_record(c,"G_SEQPAR")
    truth=_hidden_surrogates(c,"P4")
    cards={p:json.loads((HERE/"results"/"01_i1"/"P4"/"public"/p/"card.json").read_text()) for p in PROVIDERS}
    boundaries={p:_local_boundary_at_rho(cards[p],args.rho) for p in PROVIDERS}
    graph_boundary=_base_boundary(c,graph_id="G_SEQPAR",cards=cards,rho=args.rho)
    config={k:v for k,v in vars(args).items() if k not in ("trials","calibration_only")}
    signature=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
    root=OUT/f"scientific_{args.sampler}_{signature}";root.mkdir(parents=True,exist_ok=True)
    contract_path=root/"contract.json"
    if contract_path.exists():
        contract=json.loads(contract_path.read_text())
        if contract["configuration"]!=config or contract["label"]!=LABEL:
            raise RuntimeError("Frozen calibration contract mismatch")
    else:
        print("CALIBRATION_N",args.calibration_seeds,flush=True)
        ref=curves(truth,range(args.seed_base,args.seed_base+args.calibration_seeds),
                   c,graph,boundaries,graph_boundary,args.rho)
        disclosure={}
        for p in PROVIDERS:
            disclosure[p]={}
            for i,h in enumerate(HORIZONS):
                observed=float(ref[p][i])
                k=round(observed*args.calibration_seeds)
                if abs(k/args.calibration_seeds-observed)>1.e-9:
                    raise RuntimeError("Invalid empirical binomial fraction")
                disclosure[p][str(h)]=simultaneous_lower(k,args.calibration_seeds,
                    ALPHA/(len(PROVIDERS)*len(HORIZONS)))
        contract=dict(label=LABEL,configuration=config,reference_calibration=ref,
                      disclosure=disclosure,confidence_method="one-sided CP + Bonferroni",
                      familywise_error=ALPHA,
                      graph_conditional=True,not_original_I1=True,
                      not_certified_universal=True,
                      note="Calibration coverage pertains to the six fixed provider queries only; reference simulation is privileged and isolated from optimization.")
        contract_path.write_text(json.dumps(contract,indent=2)+"\n")
    disclosure=contract["disclosure"]
    table=pd.DataFrame([dict(provider=p,H=h,calibration=contract["reference_calibration"][p][i],
                             lower_bound=disclosure[p][str(h)])
                        for p in PROVIDERS for i,h in enumerate(HORIZONS)])
    table.to_csv(root/"calibration_bounds.csv",index=False)
    print("CALIBRATION_BOUNDS")
    print(table.to_string(index=False),flush=True)
    weak=table[table.lower_bound<args.min_provider_bound]
    if len(weak) and not args.allow_weak_information:
        print("CALIBRATION_GATE_FAILED_DEGENERATE_PROVIDER_DISCLOSURES",flush=True)
        print(weak.to_string(index=False))
        print("NO_OPTIMIZATION_PERFORMED; redesign provider SLA regions under the same graph context.")
        print("OUTPUT",root)
        return
    if len(weak):
        if (table.lower_bound<=0).any():
            raise RuntimeError("Vacuous zero lower bound: stop instead of optimizing")
        print("WEAK_INFORMATION_OVERRIDE_NONZERO_BOUNDS",flush=True)
        print(weak.to_string(index=False),flush=True)
    if args.calibration_only:
        print("CALIBRATION_GATE_PASSED_NO_OPTIMIZATION",flush=True)
        return
    sampler=(optuna.samplers.GPSampler(seed=42,n_startup_trials=8)
             if args.sampler=="gp" else optuna.samplers.TPESampler(seed=42,n_startup_trials=8))
    study=optuna.create_study(direction="minimize",sampler=sampler,
        storage="sqlite:///"+str(root/"study.sqlite3"),study_name="praise_scientific_"+signature,
        load_if_exists=True)
    def objective(trial):
        theta={}
        for p in PROVIDERS:
            t=truth[p]
            parameters={}
            for name,value in (("mean_service_time",t.mean_service_time),
                ("cost_rate",t.cost_rate),("service_cv",t.service_cv)):
                low=max(float(value)*(1-args.radius),1.e-5)
                high=max(float(value)*(1+args.radius),low+1.e-5)
                parameters[name]=trial.suggest_float(p+"."+name,low,high)
            theta[p]=GraphProviderSurrogate(**parameters)
        # Nonoverlapping calibration, exploration, verification seed blocks.
        # Fixed trial-to-seed mapping makes interrupted studies resumable.
        start=args.seed_base+100000+trial.number*args.seeds_per_trial
        if start+args.seeds_per_trial >= args.seed_base+10000000:
            raise RuntimeError("Exploration seed range exhausted")
        response=curves(theta,range(start,start+args.seeds_per_trial),
                        c,graph,boundaries,graph_boundary,args.rho)
        for p in PROVIDERS:
            for i,h in enumerate(HORIZONS):
                # Empirical constraints; uncertain feasibility is NOT a guarantee.
                trial.set_constraint(f"{p}@{h}",float(disclosure[p][str(h)]-response[p][i]))
        trial.set_user_attr("response",response)
        trial.set_user_attr("N",args.seeds_per_trial)
        trial.set_user_attr("weak_information_override",bool(args.allow_weak_information))
        trial.set_user_attr("first_seed",start)
        graph_survival=float(response["G"][-1])
        print("SCIENTIFIC_TRIAL",trial.number,"N",args.seeds_per_trial,
              "GRAPH_FV_240",graph_survival,flush=True)
        return graph_survival
    study.optimize(objective,n_trials=args.trials,n_jobs=1)
    data=[]
    for t in study.trials:
        if t.state!=TrialState.COMPLETE:continue
        constraints=t.constraints or {}
        data.append(dict(trial=t.number,graph_survival_240=t.value,
            nominally_feasible=(bool(constraints) and max(constraints.values())<=0),
            max_empirical_violation=(max(constraints.values()) if constraints else None),
            params=json.dumps(t.params),response=json.dumps(t.user_attrs.get("response"))))
    pd.DataFrame(data).to_csv(root/"trial_summary.csv",index=False)
    admissible=[d for d in data if d["nominally_feasible"]]
    print("SCIENTIFIC_PILOT_COMPLETE",len(data),"TRIALS",len(admissible),"EMPIRICALLY_FEASIBLE")
    if admissible:
        best=min(admissible,key=lambda d:d["graph_survival_240"])
        print("LOWEST_OBSERVED_NOT_CERTIFIED",best["graph_survival_240"],"TRIAL",best["trial"])
    print("OUTPUT",root)

if __name__=="__main__":main()
