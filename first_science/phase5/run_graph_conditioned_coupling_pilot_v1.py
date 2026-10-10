"""Matched-seed graph-conditioned coupling pilot. Full G_SEQPAR only.
Never uses original public I1 as if it were graph-conditioned evidence.
"""
from __future__ import annotations
import argparse,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from phase5_runtime_v2 import load_phase5_contracts,graph_record
from run_phase5_step0_v2 import _hidden_surrogates
from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory
from m1_graph_simulator_v2 import GraphProviderSurrogate

HERE=Path(__file__).resolve().parent
OUT=HERE/"results"/"46_graph_conditioned_coupling_pilot"
PROVIDERS=("ProviderA","ProviderB","ProviderC")

def parameters(base,change=None,scale=1.0):
    vals={}
    for provider in PROVIDERS:
        x=base[provider]
        mu=float(x.mean_service_time)*(scale if change==provider else 1.0)
        vals[provider]=GraphProviderSurrogate(mean_service_time=mu,cost_rate=float(x.cost_rate),service_cv=float(x.service_cv))
    return vals

def summarize_provider(rows,ledger,provider,horizons):
    # Native service duration is separate from graph-conditioned elapsed time.
    r=rows.loc[rows["module"]==provider].copy()
    ids=set(r["id"].astype(int))
    root=ledger[["request_id","emission"]]
    r=r.merge(root,left_on="id",right_on="request_id",how="left",validate="many_to_one")
    if r["emission"].isna().any():raise RuntimeError("Unmatched provider/root request ID")
    if r["id"].duplicated().any():raise RuntimeError("Duplicate provider visits not supported in pilot")
    service=pd.to_numeric(r["service"],errors="coerce")
    completion=pd.to_numeric(r["time_out"],errors="coerce")
    elapsed=completion-r["emission"].astype(float)
    if service.isna().any() or completion.isna().any():raise RuntimeError("Invalid native timestamps")
    # Fixed thresholds make changes comparable across configurations.
    result=[]
    nroot=len(ledger)
    for h in horizons:
        result.append(dict(provider=provider,H=h,n_root=nroot,n_reached=len(r),
           reach_rate=len(r)/nroot,
           mean_service=float(service.mean()) if len(r) else np.nan,
           mean_elapsed=float(elapsed.mean()) if len(r) else np.nan,
           service_le_h=float((service<=h).mean()) if len(r) else np.nan,
           reached_and_completed_le_h=float((elapsed<=h).sum()/nroot)))
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",type=int,default=8)
    ap.add_argument("--scale",type=float,default=1.25)
    args=ap.parse_args()
    if args.seeds<2 or args.scale<=0:raise ValueError("Invalid seeds or scale")
    OUT.mkdir(parents=True,exist_ok=True)
    contracts=load_phase5_contracts(HERE)
    graph=graph_record(contracts,"G_SEQPAR")
    truth=_hidden_surrogates(contracts,"P4") # diagnostic generating point, not inference
    cfg=contracts.battery
    inv=dict(cfg["graph_invariants"])
    family=cfg["provider_family"]
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    hlist=(30.,60.,120.,180.)
    allrows=[]
    variants=[("base",None)]+[("perturb_"+p,p) for p in PROVIDERS]
    for label,p in variants:
        for ordinal in range(args.seeds):
            seed=99000000+ordinal
            ret=execute_one_phase5_graph_trajectory(
                graph_id="G_SEQPAR",graph_ast=graph["ast"],
                provider_surrogates=parameters(truth,p,args.scale),
                graph_invariants=inv,
                workload_period=float(cfg["workload"]["period_seconds"]),
                stop_time=float(cfg["horizon"]["maximum_seconds"]),
                trajectory_seed=seed,canonical_ipt=float(family["effective_IPT"]),
                execution_fraction=float(family["execution_fraction_x"]),
                return_provider_rows=True)
            ledger,diag,provider_rows=ret
            for prov in PROVIDERS:
                for row in summarize_provider(provider_rows,ledger,prov,hlist):
                    allrows.append(dict(variant=label,perturbed=p or "NONE",
                                        seed=seed,**row))
        print("COMPLETE",label,flush=True)
    df=pd.DataFrame(allrows)
    df.to_csv(OUT/"matched_seed_provider_observations.csv",index=False)
    base=df[df.variant=="base"]
    output=[]
    for variant,p in variants[1:]:
        pert=df[df.variant==variant]
        joined=pert.merge(base,on=["seed","provider","H"],suffixes=("_test","_base"),validate="one_to_one")
        for (prov,h),g in joined.groupby(["provider","H"]):
            rec=dict(perturbed=p,observed=prov,H=h,n_seeds=len(g))
            for col in ("reach_rate","mean_service","mean_elapsed","service_le_h","reached_and_completed_le_h"):
                delta=g[col+"_test"].astype(float)-g[col+"_base"].astype(float)
                rec["delta_"+col]=float(delta.mean())
                rec["sd_delta_"+col]=float(delta.std(ddof=1))
            output.append(rec)
    summary=pd.DataFrame(output)
    summary.to_csv(OUT/"paired_sensitivity.csv",index=False)
    print("GRAPH_CONDITIONED_COUPLING_PILOT_PASS")
    print(summary[summary.H==120][["perturbed","observed","delta_reach_rate","delta_mean_service","delta_mean_elapsed","delta_reached_and_completed_le_h"]].to_string(index=False))
    with zipfile.ZipFile(OUT/"coupling_pilot_bundle.zip","w",zipfile.ZIP_DEFLATED) as z:
        for name in ("matched_seed_provider_observations.csv","paired_sensitivity.csv"):z.write(OUT/name,name)
    print("BUNDLE",OUT/"coupling_pilot_bundle.zip")
if __name__=="__main__":main()
