"""Experimental four-output G_SEQPAR SLA extractor.

New diagnostic, NOT existing I1 and NOT a certified guarantee. Uses native
completed rows plus branch dependency timing validated against native receipts.
Exports pointwise cumulative SLA AND absorbing first-violation survival.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
for p in (HERE.parent/"phase1",HERE.parent/"phase3"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from sla_compliance_analysis import (SlaComplianceDefinition,
    build_request_sla_decision_table,calculate_trajectory_cumulative_sla_curve)
from phase5_runtime_v2 import load_phase5_contracts,graph_record
from phase5_graph_ast_v2 import assert_frozen_graph_compilation
from phase5_graph_simulator_v2 import execute_one_phase5_graph_trajectory
from run_phase5_step0_v2 import _hidden_surrogates,_local_boundary_at_rho,_base_boundary

PROVIDERS=("ProviderA","ProviderB","ProviderC")
OUT=HERE/"results"/"48_four_output_survival_validation"
TOL=1e-7

def _native_id_map(native,module):
    part=native[native.module==module]
    if part.id.duplicated().any():raise RuntimeError(f"Duplicate IDs for {module}")
    return {int(r.id):r for r in part.itertuples(index=False)}

def reconstruct_local(native,root,ast,invariants,stop,seed):
    """Reconstruct provider arrivals, with native-reception-based lag validation.

    For completed branches use native reception exactly. For branches whose
    predecessors have finished, infer arrivals from the same graph's constant
    observed predecessor-completion -> reception lag. Refuse unvalidated lags.
    No branch is created when dependency completion is absent.
    """
    plan=assert_frozen_graph_compilation("G_SEQPAR",ast)
    maps={p:_native_id_map(native,p) for p in (*PROVIDERS,"Fpre")}
    root_ids=set(root.request_id.astype(int))
    if not root_ids:raise RuntimeError("Empty root ledger")
    if set().union(*(set(maps[p]) for p in PROVIDERS))-root_ids:
        raise RuntimeError("Provider execution without root request")
    if set(maps["Fpre"])-root_ids:raise RuntimeError("Fpre execution without root request")
    # Predecessor timing: initial branches follow Fpre, dependent branches
    # follow the last completion among their explicitly declared predecessors.
    def release(rid,p):
        deps=plan.dependencies[p]
        keys=deps if deps else ("Fpre",)
        if not all(rid in maps[q] for q in keys):return None
        return max(float(maps[q][rid].time_out) for q in keys)
    lags={}
    for p in PROVIDERS:
        pairs=[(float(row.time_reception)-release(rid,p))
            for rid,row in maps[p].items() if release(rid,p) is not None]
        if len(pairs)==0:raise RuntimeError(f"No native reception lag calibrator for {p}")
        low,high=min(pairs),max(pairs)
        # Distinct lags imply unknown controller/network scheduling.
        # Abort rather than silently reconstruct queue arrivals incorrectly.
        if high-low>TOL:
            raise RuntimeError(f"{p} release-to-reception delay varies [{low},{high}]; "
                "cannot infer censored arrivals from fixed delay")
        if low < -TOL:raise RuntimeError(f"{p}: arrival precedes release")
        lags[p]=float(np.median(pairs))
    ledgers={}
    accounting=[]
    for p in PROVIDERS:
        rows=[]
        for rid in sorted(root_ids):
            release_time=release(rid,p)
            if release_time is None:
                accounting.append(dict(seed=seed,provider=p,request_id=rid,status="blocked_before_release"))
                continue
            predicted_arrival=release_time+lags[p]
            native_row=maps[p].get(rid)
            if native_row is not None:
                arrival=float(native_row.time_reception)
                if abs(arrival-predicted_arrival)>TOL:
                    raise RuntimeError(f"{p}/{rid}: native arrival mismatch")
                completed=float(native_row.time_out)
                if completed>stop+TOL:raise RuntimeError("Native completion past stop")
                service=float(native_row.service)
                if service<0:raise RuntimeError("negative native service")
                cost=float(invariants["provider_cost_rates"][p])*service
                quality=float(native_row.qos)
                if not np.isfinite(quality):raise RuntimeError("invalid quality")
                status="completed"
            else:
                arrival=predicted_arrival
                completed=cost=quality=None
                status="uncompleted_arrival" if arrival<=stop+TOL else "not_yet_arrived"
            accounting.append(dict(seed=seed,provider=p,request_id=rid,status=status))
            if arrival>stop+TOL:continue
            rows.append(dict(trajectory=seed,request_id=rid,emission=arrival,
                completion=completed,L=(completed-arrival if completed is not None else None),
                C=cost,Q=quality))
        if not rows:raise RuntimeError(f"No arrived requests for {p}")
        ledgers[p]=pd.DataFrame(rows)
        if ledgers[p].request_id.duplicated().any():raise RuntimeError("duplicate local IDs")
    return ledgers,pd.DataFrame(accounting),lags

def first_violation(decisions,rho,horizons):
    """Absorbing survival: first observed cumulative-fraction breach."""
    decided=decisions.loc[decisions.decision_time.notna(),["decision_time","compliant"]].copy()
    decided=decided.sort_values("decision_time")
    n=good=0
    first=float("inf")
    for t,group in decided.groupby("decision_time",sort=True):
        n+=len(group)
        good+=int(group.compliant.fillna(False).astype(bool).sum())
        if good/n+1e-12 < rho:
            first=float(t)
            break
    return [int(first>h+1e-12) for h in horizons],first

def validate_recovery():
    # A bad first decision followed by good decisions allows pointwise recovery,
    # but cannot restore first-violation survival.
    toy=pd.DataFrame(dict(decision_time=[1.,2.,3.],compliant=pd.array([False,True,True],dtype="boolean")))
    vals,t=first_violation(toy,0.5,[0,1,2,3])
    assert vals==[1,0,0,0] and t==1.0
    return True

def run(args):
    validate_recovery()
    c=load_phase5_contracts(HERE)
    graph=graph_record(c,"G_SEQPAR")
    cfg=c.battery
    family=cfg["provider_family"]
    inv=dict(cfg["graph_invariants"])
    inv["effective_IPT"]=float(family["effective_IPT"])
    inv["cost_rate"]=float(family["cost_rate"])
    truth=_hidden_surrogates(c,"P4")
    inv["provider_cost_rates"]={p:float(truth[p].cost_rate) for p in PROVIDERS}
    cards={p:json.loads((HERE/"results"/"01_i1"/"P4"/"public"/p/"card.json").read_text()) for p in PROVIDERS}
    rho=float(args.rho)
    boundaries={p:_local_boundary_at_rho(cards[p],rho) for p in PROVIDERS}
    gb=_base_boundary(c,graph_id="G_SEQPAR",cards=cards,rho=rho)
    stop=float(cfg["horizon"]["maximum_seconds"])
    horizons=np.arange(0.,stop+0.01,5.).tolist()
    by_object={p:[] for p in (*PROVIDERS,"G")}
    provenance=[];lags_all=[]
    for seed in range(args.seed_base,args.seed_base+args.seeds):
        root,_,native=execute_one_phase5_graph_trajectory(
            graph_id="G_SEQPAR",graph_ast=graph["ast"],
            provider_surrogates=truth,graph_invariants=inv,
            workload_period=float(cfg["workload"]["period_seconds"]),
            stop_time=stop,trajectory_seed=seed,
            canonical_ipt=float(family["effective_IPT"]),
            execution_fraction=float(family["execution_fraction_x"]),
            return_native_rows=True)
        if root.request_id.duplicated().any():raise RuntimeError("Duplicate root IDs")
        locals_,accounting,lags=reconstruct_local(native,root,graph["ast"],inv,stop,seed)
        provenance.append(accounting)
        lags_all.append(dict(seed=seed,**lags))
        for obj,ledger in {**locals_,"G":root}.items():
            b=gb if obj=="G" else boundaries[obj]
            decisions=build_request_sla_decision_table(ledger,
                float(b.l_max),float(b.c_max),float(b.q_min),stop)
            definition=SlaComplianceDefinition(rho=rho)
            point=calculate_trajectory_cumulative_sla_curve(decisions,horizons,definition)
            survival,first=first_violation(decisions,rho,horizons)
            if any(x>y for x,y in zip(survival,point.sla_compliant.astype(int))):
                raise RuntimeError("Absorbing survival exceeds pointwise SLA")
            if any(survival[i]<survival[i+1] for i in range(len(survival)-1)):
                raise RuntimeError("Absorbing survival is not monotone")
            for i,h in enumerate(horizons):
                by_object[obj].append(dict(seed=seed,object=obj,horizon=h,
                    pointwise_compliance=int(point.iloc[i].sla_compliant),
                    first_violation_survival=int(survival[i]),first_violation_time=first,
                    decided_requests=int(point.iloc[i].decided_requests)))
        print("VALIDATED_SEED",seed,flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    points=pd.DataFrame([r for group in by_object.values() for r in group])
    points.to_csv(OUT/"trajectory_four_output.csv",index=False)
    summary=points.groupby(["object","horizon"],as_index=False).agg(
        sigma_pointwise=("pointwise_compliance","mean"),
        sigma_first_violation=("first_violation_survival","mean"),
        n_trajectories=("seed","nunique"))
    summary.to_csv(OUT/"four_output_curves.csv",index=False)
    pd.concat(provenance,ignore_index=True).to_csv(OUT/"branch_accounting.csv",index=False)
    pd.DataFrame(lags_all).to_csv(OUT/"validated_release_lags.csv",index=False)
    if not (summary.sigma_first_violation<=summary.sigma_pointwise+1e-12).all():
        raise RuntimeError("mean survival > pointwise")
    report=dict(status="FOUR_OUTPUT_EXTRACTOR_VALIDATED_ON_TESTED_SEEDS",
       seeds=args.seeds,rho=rho,world="P4",graph="G_SEQPAR",
       estimated_only=True,not_original_I1=True,
       graph_and_provider_events="cumulative SLA decisions, separate absorbing first violation",
       note="Graph-conditioned local surfaces cannot be equated with W0/ParAll I1",
       outputs=["trajectory_four_output.csv","four_output_curves.csv","branch_accounting.csv","validated_release_lags.csv"])
    (OUT/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(report["status"])
    print(summary[summary.horizon.isin([60.,120.,180.,240.])].to_string(index=False))
    print("OUTPUT",OUT)
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",type=int,default=3)
    ap.add_argument("--seed-base",type=int,default=99001000)
    ap.add_argument("--rho",type=float,default=0.9)
    args=ap.parse_args()
    if args.seeds<1 or not 0<args.rho<=1:raise ValueError("Invalid seeds/rho")
    run(args)
