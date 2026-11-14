#!/usr/bin/env python3
"""B0001 independent-world three-arm Plan-B TRANSFER replay, not seven-arm confirmation.

Read-only B0001 deterministic evaluation plus fully frozen provenance.
Transfers unchanged original B1 Gaussian prior, posterior and joint-action
acquisition rules for Random/Balanced/Informed/BudgetedTop2, plus original
one-step KG, to m=3 supported methods. Deliberate domain changes:
  * 3, not 7, arms and initial common-cell observations
  * budgets 10,15,20,30 (40 invalid since 3x12=36)
  * no original/fixed-CV arms, no original 7-arm confirmation
  * no original seven-policy (two-stage) condition ablation
This file never imports a simulator, resamples observations, or modifies inputs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import b1_budget_comparison_v1 as b1
import b1_kg_one_step_v1 as kg

METHODS=("M1","M2","M3_FULL343")
POLICIES=("random","balanced","informed","budgeted_top2","kg_one_step")
BUDGETS=(10,15,20,30)
SEED=20261105
REPS=20
NBOOT=2000
STATUS="B0001_THREE_ARM_INDEPENDENT_TRANSFER_EXPLORATORY_V1"
FIELDS=("method_id","scope","scope_value","n_points","MAE")


def require(ok,info):
    if not bool(ok):raise RuntimeError("B0001 3-ARM TRANSFER: "+info)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write(path,rows):
    require(rows,"Refusing empty output: "+str(path))
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def matrix(a):
    mf=a.evaluation/"b0001_deterministic_evaluation_freeze.json"
    j=load(mf)
    require(j["status"]=="B0001_FULL343_DETERMINISTIC_EVALUATION_FROZEN"
            and j["n_cells"]==12 and j["primary_points_per_method"]==6660,
            "B0001 deterministic freeze not established")
    metrics=a.evaluation/"primary_metrics.csv"
    require(j["output_hashes_sha256"]["primary_metrics"]==digest(metrics),
            "Primary metrics changed since freeze")
    require(j["reference_mechanical_audit_sha256"]==
            digest(a.refaudit/"b0001_final_reference_mechanical_audit.json"),
            "Reference mechanical audit hash changed")
    require(j["blind_global_prediction_freeze_sha256"]==
            digest(a.graph/"scientific"/"b0001_full343_global_prediction_freeze.json"),
            "Blind graph freeze hash changed")
    require(j["final_reference_global_freeze_sha256"]==
            digest(a.reference/"b0001_final_wb_global_freeze.json"),
            "Final reference global freeze hash changed")
    tab=pd.read_csv(metrics)
    tab=tab.loc[tab["scope"]=="provider_world_x_graph"].copy()
    require(set(tab.method_id)=={"M0",*METHODS},
            "Unexpected primary method set")
    entries={}
    for row in tab.itertuples(index=False):
        if row.method_id not in METHODS:
            continue
        cell=b1.cell_from(row.scope_value)
        key=(row.method_id,cell)
        require(key not in entries,"Duplicate method/cell observation: "+str(key))
        require(int(row.n_points)==555 and math.isfinite(float(row.MAE))
                and 0<=float(row.MAE)<=1,"Invalid cell MAE: "+str(key))
        entries[key]=float(row.MAE)
    require(len(entries)==36,"Expected exactly 3 x 12 observations")
    Y=np.array([[entries[(method,cell)] for cell in b1.CELLS]
                for method in METHODS],dtype=float)
    require(Y.shape==(3,12) and np.isfinite(Y).all(),
            "Incomplete independent MAE matrix")
    # Mean must match frozen overall summary, giving a second aggregation check.
    for i,method in enumerate(METHODS):
        allrow=tab.iloc[0:0]
        orig=pd.read_csv(metrics)
        allrow=orig[(orig.method_id==method)&(orig.scope=="ALL")&
                    (orig.scope_value=="ALL")]
        require(len(allrow)==1 and abs(Y[i].mean()-float(allrow.iloc[0].MAE))<1e-11,
                "Global versus cell MAE mismatch: "+method)
    return Y,{
        "source_evaluation_manifest_sha256":digest(mf),
        "source_primary_metrics_sha256":digest(metrics),
        "reference_audit_sha256":digest(
            a.refaudit/"b0001_final_reference_mechanical_audit.json"),
    }


def episode(Y,policy,B,start,rep):
    m=len(METHODS)
    pid=POLICIES.index(policy)
    rng=np.random.default_rng(np.random.SeedSequence([SEED,B,start,rep,pid]))
    seen=[(arm,start,float(Y[arm,start])) for arm in range(m)]
    while len(seen)<B:
        if policy=="kg_one_step":
            aa,cc=kg.select_kg(seen,rng,m)
        else:
            aa,cc=b1.select_action(policy,seen,B,rng,m)
        require((aa,cc) not in {(a,c) for a,c,_ in seen},
                "Repeated action in episode")
        seen.append((aa,cc,float(Y[aa,cc])))
    mu,_,_=b1.posterior(seen,m)
    choice=int(np.argmin(mu))
    means=Y.mean(axis=1)
    winner=int(np.argmin(means))
    terminal={
        "policy":policy,"budget":B,"start_index":start,
        "start_cell":"__".join(b1.CELLS[start]),"replicate":rep,
        "evaluations":B,"recommended":METHODS[choice],
        "reference_best":METHODS[winner],"correct":int(choice==winner),
        "simple_regret":max(0.0,float(means[choice]-means[winner])),
    }
    history=[
        {"policy":policy,"budget":B,"start_index":start,"replicate":rep,
         "step":t+1,"method":METHODS[arm],"world":b1.CELLS[cell][0],
         "graph":b1.CELLS[cell][1],"mae":float(val)}
        for t,(arm,cell,val) in enumerate(seen)
    ]
    require(len(history)==B and
            len({(r["method"],r["world"],r["graph"]) for r in history})==B,
            "Episode distinct-action invariant")
    return terminal,history


def summary(terminal):
    lookup={(r["budget"],r["start_index"],r["replicate"],r["policy"]):r
            for r in terminal}
    require(len(lookup)==len(terminal),"Duplicate replay episode")
    rng=np.random.default_rng(SEED+2706)
    summaries=[]
    differences=[]
    by_budget={}
    for B in BUDGETS:
        values={}
        for policy in POLICIES:
            records=[lookup[(B,s,rep,policy)]
                     for s in range(12) for rep in range(REPS)]
            regret=np.array([r["simple_regret"] for r in records],
                            dtype=float).reshape(12,REPS)
            correct=np.array([r["correct"] for r in records],
                             dtype=float).reshape(12,REPS)
            values[policy]=regret
            picks=rng.integers(REPS,size=(NBOOT,12,REPS))
            breg=np.take_along_axis(regret[None,:,:],picks,axis=2).mean(axis=(1,2))
            bcor=np.take_along_axis(correct[None,:,:],picks,axis=2).mean(axis=(1,2))
            summaries.append({
                "budget":B,"policy":policy,"episodes":len(records),
                "mean_regret":float(regret.mean()),
                "regret_low":float(np.quantile(breg,.025)),
                "regret_high":float(np.quantile(breg,.975)),
                "p_correct":float(correct.mean()),
                "p_low":float(np.quantile(bcor,.025)),
                "p_high":float(np.quantile(bcor,.975)),
                "regret_p90":float(np.quantile(regret,.9)),
            })
        for policy in POLICIES:
            if policy=="balanced":continue
            delta=values[policy]-values["balanced"]
            draws=rng.integers(REPS,size=(NBOOT,12,REPS))
            bdelta=np.take_along_axis(delta[None,:,:],draws,axis=2).mean(axis=(1,2))
            differences.append({
                "budget":str(B),"contrast":policy+" minus balanced",
                "mean_regret_diff":float(delta.mean()),
                "low":float(np.quantile(bdelta,.025)),
                "high":float(np.quantile(bdelta,.975)),
            })
            by_budget[B,policy]=delta
    for policy in POLICIES:
        if policy=="balanced":continue
        deltas=np.stack([by_budget[B,policy] for B in BUDGETS])
        # Matched stratified episode resampling reused across all budgets.
        draws=rng.integers(REPS,size=(NBOOT,12,REPS))
        boot=np.stack([
            np.take_along_axis(d[None,:,:],draws,axis=2).mean(axis=(1,2))
            for d in deltas],axis=1).mean(axis=1)
        differences.append({
            "budget":"MEAN_OVER_4_BUDGETS",
            "contrast":policy+" minus balanced",
            "mean_regret_diff":float(deltas.mean()),
            "low":float(np.quantile(boot,.025)),
            "high":float(np.quantile(boot,.975)),
        })
    return summaries,differences


def run(a):
    require(not a.out.exists(),"Refusing to overwrite output directory")
    for source in (a.evaluation,a.refaudit,a.graph,a.reference):
        require(a.out!=source and source not in a.out.parents,
                "Output overlaps frozen inputs")
    Y,provenance=matrix(a)
    print("B0001_3x12_MATRIX_VERIFIED",
          "arms="+",".join(METHODS),"actions=36",flush=True)
    for i,method in enumerate(METHODS):
        print("B0001_REFERENCE_MEAN",method,f"{Y[i].mean():.8f}",flush=True)
    print("B0001_REFERENCE_BEST",METHODS[int(np.argmin(Y.mean(axis=1)))],
          flush=True)
    terminals=[];actions=[]
    for B in BUDGETS:
        for start in range(12):
            for rep in range(REPS):
                for policy in POLICIES:
                    t,h=episode(Y,policy,B,start,rep)
                    terminals.append(t);actions.extend(h)
        print("B0001_TRANSFER_BUDGET_COMPLETE",B,"240 episodes/policy",flush=True)
    require(len(terminals)==len(BUDGETS)*12*REPS*len(POLICIES),
            "Wrong replay episode count")
    summaries,contrasts=summary(terminals)
    a.out.mkdir(parents=True,exist_ok=False)
    matrix_rows=[
        {"method":METHODS[i],"world":w,"graph":g,"mae":float(Y[i,j])}
        for i in range(3) for j,(w,g) in enumerate(b1.CELLS)
    ]
    outputs={
        "three_arm_matrix.csv":matrix_rows,
        "terminal_episodes.csv":terminals,
        "action_history.csv":actions,
        "budget_summary.csv":summaries,
        "paired_contrasts.csv":contrasts,
    }
    hashes={}
    for name,records in outputs.items():
        path=a.out/name
        write(path,records)
        hashes[name]=digest(path)
    manifest={
        "status":STATUS,
        "study_class":"SUPPLEMENTARY_EXPLORATORY_THREE_ARM_TRANSFER_NOT_SEVEN_ARM_CONFIRMATION",
        "original_seven_arm_benchmark_completed":False,
        "models":list(METHODS),
        "conditions":[list(c) for c in b1.CELLS],
        "policies":list(POLICIES),
        "budgets":list(BUDGETS),
        "initial_common_cell_observations":3,
        "distinct_action_count":36,
        "terminal_target":"Equal-cell mean MAE across all 12 independent B0001 cells",
        "repeats_per_start":REPS,
        "bootstrap_reps":NBOOT,
        "seed":SEED,
        "posterior_and_acquisition":"Unchanged B1 Gaussian priors and joint-action policy math",
        "departure_from_original":"3 versus 7 arms; common initialization 3 versus 7; excludes budget 40; no two-stage ablation",
        "fixed_reference_best":METHODS[int(np.argmin(Y.mean(axis=1)))],
        "reference_best_mean_MAE":float(np.min(Y.mean(axis=1))),
        "frozen_source_provenance":provenance,
        "code_sha256":{
            "b1_budget_comparison_v1.py":digest(Path(b1.__file__)),
            "b1_kg_one_step_v1.py":digest(Path(kg.__file__)),
            "this_adapter":digest(Path(__file__)),
        },
        "n_episodes":len(terminals),
        "n_action_observations":len(actions),
        "output_sha256":hashes,
        "no_graph_simulations":True,
        "no_predictor_retraining":True,
        "world_generalization_uncertainty_not_estimated":True,
    }
    path=a.out/"transfer_manifest.json"
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",
                    encoding="utf-8")
    print("B0001_THREE_ARM_TRANSFER_REPLAY_PASS",flush=True)
    for r in summaries:
        print("SUMMARY",r["budget"],r["policy"],
              f"regret={r['mean_regret']:.8f}",
              f"correct={r['p_correct']:.4f}",flush=True)
    print("SEVEN_ARM_CONFIRMATION_NOT_RUN",flush=True)
    print("MANIFEST",path,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("evaluation","refaudit","graph","reference","out"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args()
    for key in ("evaluation","refaudit","graph","reference","out"):
        setattr(a,key,getattr(a,key).expanduser().resolve())
    run(a)


if __name__=="__main__":
    main()
