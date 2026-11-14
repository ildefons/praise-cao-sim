#!/usr/bin/env python3
"""B0001 two-family 48-LHS PUBLIC-I1 local-simulation evidence runner.

--check: read-only audit of design/smoke/seed/source, no simulation.
--benchmark: one 100-trajectory scientific candidate checkpoint, resumable.
--run: all 18 x 48 candidates, independently scored with 100 trajectories
each, using original run_m1_provider_lift_v2._simulate_and_score as invoked
by historical B1 original-style and fixed-CV preparation.

This stage does not choose lambda, compare errors against graph WB, or create
graph predictions. Only public B0001 cards are accessible. Historical Phase5
results are never mounted. Individual CSVs are resumable; complete 48-row
provider banks are frozen by SHA. Output must be outside repository.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
FAMILIES=("original","fixed_cv")
ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
DESIGN_STATUS="B0001_TWO_48_LHS_PUBLIC_DESIGN_BANKS_FROZEN_NO_SIMULATION"
SMOKE_STATUS="B0001_48_LHS_LOCAL_SCORING_ENGINEERING_SMOKE_PASS"
BANK_STATUS="B0001_48_LHS_PROVIDER_LOCAL_48x100_FROZEN"
GLOBAL_STATUS="B0001_48_LHS_ALL_864_CANDIDATES_PUBLIC_ONLY_FROZEN"
SRC_SCORER="first_science/phase3/run_m1_provider_lift_v2.py"


def require(ok,why):
    if not bool(ok):raise RuntimeError("B0001 48-LHS scoring: "+why)


def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as fd:
        for b in iter(lambda:fd.read(1048576),b""):h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        require(load(path)==data,"Refusing to replace differing frozen manifest: "+str(path))
        return
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n",encoding="utf-8")


def imports():
    for root in (REPO/"first_science"/"phase2",REPO/"first_science"/"phase3",
                 REPO/"first_science"/"phase4",REPO/"first_science"/"phase5"):
        if str(root) not in sys.path:sys.path.insert(0,str(root))
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    from run_m1_provider_lift_v2 import _simulate_and_score
    return load_rho_conditioned_i1_provider_card,_simulate_and_score


# Initialize worker input once per process. The worker sees only frozen public I1.
_CONTEXT=None
def init_worker(metadata,public,seeds):
    global _CONTEXT
    _CONTEXT=(metadata,public,tuple(seeds))


def worker(job):
    if _CONTEXT is None:raise RuntimeError("Provider-local worker not initialized")
    row,dest=job
    metadata,public,seeds=_CONTEXT
    start=time.perf_counter()
    _,simulate=imports()
    metrics,_,comparison=simulate(
        metadata=metadata,public_surface=public,
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
        trajectory_seeds=seeds,
        canonical_ipt=1000000.0,
        execution_fraction=0.5,
        quiet=True)
    require(len(comparison)==1200 and
            set(("sigma_i1","sigma_m1_local")).issubset(comparison.columns),
            "Original scorer returned unexpected public surface")
    curve=comparison[["sigma_i1","sigma_m1_local"]].copy()
    curve.insert(0,"point_index",np.arange(1200))
    require(np.isfinite(curve[["sigma_i1","sigma_m1_local"]]
                        .to_numpy(float)).all()
            and math.isfinite(float(metrics["mse"])),
            "Nonfinite result from original local scorer")
    path=Path(dest)
    path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.exists(),"Another process created same candidate checkpoint: "+str(path))
    tmp=path.with_name(path.name+f".{os.getpid()}.tmp")
    try:
        curve.to_csv(tmp,index=False)
        require(not path.exists(),"Concurrent checkpoint creation")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return str(row["candidate_id"]),float(time.perf_counter()-start)


def check_curve(path,public_vector):
    t=pd.read_csv(path)
    require(len(t)==1200 and
            list(t.columns)==["point_index","sigma_i1","sigma_m1_local"]
            and t.point_index.astype(int).tolist()==list(range(1200)),
            "Invalid candidate curve indexing/shape: "+str(path))
    v=t[["sigma_i1","sigma_m1_local"]].to_numpy(float)
    require(np.isfinite(v).all() and
            np.allclose(v[:,0],public_vector,atol=1e-12,rtol=0),
            "Candidate curve disagrees with frozen public I1: "+str(path))
    require(np.all((v>=0)&(v<=1)),
            "Candidate compliance estimates outside [0,1]")
    return sha(path)


def validate(a):
    for key in ("design","staging","smoke"):
        require(getattr(a,key).is_dir(),
                "Missing frozen prerequisite "+str(getattr(a,key)))
    for source in (a.design,a.staging,a.smoke):
        require(a.out!=source and source not in a.out.parents
                and a.out not in source.parents,
                "Output overlaps an input")
    require(a.out!=REPO and REPO not in a.out.parents,
            "Cannot write in Git checkout")
    df=a.design/"b0001_48_lhs_design_freeze.json"
    sf=a.staging/"b0001_public_inputs_manifest.json"
    mf=a.smoke/"b0001_48_lhs_local_scoring_smoke.json"
    design=load(df);smoke=load(mf)
    require(design["status"]==DESIGN_STATUS and
            smoke["status"]==SMOKE_STATUS,
            "48-LHS candidate design / scorer smoke not frozen")
    require(smoke["design_manifest_sha256"]==sha(df) and
            smoke["staging_manifest_sha256"]==sha(sf),
            "Local scorer smoke belongs to a different input bank")
    require(smoke["local_scoring_source_sha256"]==sha(REPO/SRC_SCORER),
            "Historical provider-local scorer source changed")
    require(smoke["engineering_simulations"]==2 and
            smoke["scientific_candidate_curves_created"]==0 and
            smoke["final_reference_opened"] is False,
            "Original engineering smoke audit invalid")
    require(len(smoke["planned_18_fresh_scientific_seed_banks"])==18,
            "Invalid planned local seed block count")
    stage=load(sf)
    lookup={item["path"]:item["staged_sha256"]
            for item in stage["staged_files"]}
    for family in FAMILIES:
        for role in ROLES:
            for provider in PROVIDERS:
                key=f"{family}/{role}/{provider}"
                rel=f"{key.rsplit('/',1)[0]}/{provider}_lhs_design.csv"
                require(sha(a.design/rel)==design["design_file_sha256"][rel],
                        "Candidate design changed: "+rel)
                block=smoke["planned_18_fresh_scientific_seed_banks"][key]
                require(block["candidate_design_sha256"]==sha(a.design/rel) and
                        int(block["end_inclusive"])-int(block["start"])+1==100,
                        "Original 100 trajectory seed plan changed: "+key)
                for name in ("card.json","sigma_surface.csv"):
                    relcard=f"public_I1/{role}/{provider}/{name}"
                    require(sha(a.staging/relcard)==lookup[relcard],
                            "Staged public I1 source changed: "+relcard)
    return df,sf,mf,design,smoke


def full_bank(a,family,role,provider,design,smoke,benchmark=False):
    base=a.out/family/role/provider
    source=a.design/family/role/(provider+"_lhs_design.csv")
    bank=pd.read_csv(source)
    card_root=a.staging/"public_I1"/role/provider
    load_card,_=imports()
    metadata,public=load_card(card_root)
    # Identical sorting rule to original CV and provider-local scoring.
    target=public.loc[public["horizon"].astype(float)>0].sort_values(
        ["region_rho","rho","horizon"],kind="mergesort").reset_index(drop=True)
    require(len(target)==1200,"Expected 1200 public I1 points")
    pv=target["sigma_hat"].to_numpy(float)
    key=f"{family}/{role}/{provider}"
    seed=smoke["planned_18_fresh_scientific_seed_banks"][key]
    seeds=tuple(range(int(seed["start"]),int(seed["end_inclusive"])+1))
    frozen_file=base/"provider_local_bank_manifest.json"
    selected=bank.iloc[:1] if benchmark else bank
    paths=[base/"surfaces"/(cid+".csv") for cid in selected.candidate_id.astype(str)]
    if frozen_file.exists():
        require(not benchmark,"Cannot benchmark a fully frozen bank")
        frozen=load(frozen_file)
        require(frozen["status"]==BANK_STATUS and
                frozen["design_sha256"]==sha(source) and
                frozen["public_card_sha256"]==sha(card_root/"card.json") and
                frozen["public_surface_sha256"]==sha(card_root/"sigma_surface.csv") and
                frozen["seed_start"]==seeds[0] and
                frozen["seed_end_inclusive"]==seeds[-1],
                "Completed provider bank provenance mismatch")
        for name,expected in frozen["curves_sha256"].items():
            path=base/"surfaces"/name
            require(check_curve(path,pv)==expected,
                    "Completed provider-local curve changed: "+name)
        require(len(frozen["curves_sha256"])==48,
                "Partial provider-local freeze")
        print("B0001_LOCAL_BANK_FROZEN_REUSED",key,flush=True)
        return
    existing=sum(path.exists() for path in paths)
    for p in paths:
        if p.exists():check_curve(p,pv)
    todo=[(row,str(base/"surfaces"/(str(row["candidate_id"])+".csv")))
          for row in selected.to_dict("records")
          if not (base/"surfaces"/(str(row["candidate_id"])+".csv")).exists()]
    print("B0001_LOCAL_BANK",key,"target",len(selected),
          "cached",existing,"new",len(todo),"workers",a.workers,flush=True)
    now=time.perf_counter()
    if todo:
        if a.workers==1:
            init_worker(metadata,public,seeds)
            iterator=(worker(job) for job in todo)
            pool=None
        else:
            pool=concurrent.futures.ProcessPoolExecutor(
                max_workers=a.workers,initializer=init_worker,
                initargs=(metadata,public,seeds))
            iterator=pool.map(worker,todo)
        try:
            for i,(_,elapsed) in enumerate(iterator,1):
                if i==1 or i%4==0 or i==len(todo):
                    wall=(time.perf_counter()-now)/60
                    remaining=(len(todo)-i)*wall/max(1,i)
                    print("B0001_LOCAL_PROGRESS",key,
                          f"{existing+i}/{len(selected)}",
                          f"wall_min={wall:.2f}",
                          f"remaining_min={remaining:.2f}",flush=True)
        finally:
            if pool is not None:pool.shutdown(wait=True,cancel_futures=True)
    for path in paths:check_curve(path,pv)
    if benchmark:
        print("B0001_LOCAL_BENCHMARK_CANDIDATE_PASS",key,
              "100 local trajectories; checkpoint reusable",flush=True)
        return
    all_paths=[base/"surfaces"/(cid+".csv") for cid in bank.candidate_id.astype(str)]
    require(len(all_paths)==48,"Incomplete candidate bank")
    digests={p.name:check_curve(p,pv) for p in all_paths}
    freeze={
        "status":BANK_STATUS,
        "family":family,"role":role,"provider":provider,
        "design_sha256":sha(source),
        "public_card_sha256":sha(card_root/"card.json"),
        "public_surface_sha256":sha(card_root/"sigma_surface.csv"),
        "seed_start":seeds[0],"seed_end_inclusive":seeds[-1],
        "trajectory_count_per_candidate":100,
        "n_candidates":48,"n_simulations":4800,
        "curves_sha256":digests,
        "whitebox_reference_opened":False,
        "graph_simulations":0,
        "weight_fitting_pending":True,
    }
    save(frozen_file,freeze)
    print("B0001_LOCAL_BANK_48x100_FROZEN",key,flush=True)


def run(a):
    df,sf,mf,design,smoke=validate(a)
    print("B0001_LOCAL_SCORING_PREFLIGHT_PASS",
          "18 banks x 48 candidates x 100 local trajectories",flush=True)
    if a.check:
        print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ",flush=True)
        return
    if a.benchmark:
        require(a.family and a.role and a.provider,
                "Benchmark requires --family --role --provider")
        full_bank(a,a.family,a.role,a.provider,design,smoke,benchmark=True)
        return
    total=0
    for family in FAMILIES:
        for role in ROLES:
            for provider in PROVIDERS:
                full_bank(a,family,role,provider,design,smoke)
                total+=1
    require(total==18,"Incomplete local scorer bank catalogue")
    frozen={}
    for family in FAMILIES:
        for role in ROLES:
            for provider in PROVIDERS:
                rel=f"{family}/{role}/{provider}/provider_local_bank_manifest.json"
                path=a.out/rel
                require(load(path)["status"]==BANK_STATUS,
                        "Incomplete local bank: "+rel)
                frozen[rel]=sha(path)
    manifest={
        "status":GLOBAL_STATUS,
        "source_design_freeze_sha256":sha(df),
        "source_smoke_sha256":sha(mf),
        "source_staging_manifest_sha256":sha(sf),
        "original_scoring_source_sha256":sha(REPO/SRC_SCORER),
        "n_provider_family_banks":18,"n_candidates_total":864,
        "n_local_trajectories_total":86400,
        "provider_local_freeze_sha256":frozen,
        "whitebox_reference_opened":False,
        "graph_predictions_executed":0,
        "next_stage":"Original lambda=30 Gibbs and fixed-CV public-I1 fivefold lambda weighting",
    }
    dest=a.out/"b0001_48_lhs_global_local_scoring_freeze.json"
    save(dest,manifest)
    print("B0001_48_LHS_ALL_LOCAL_864_CANDIDATES_FROZEN",flush=True)
    print("FREEZE",dest,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("design","staging","smoke","out"):
        p.add_argument("--"+key,type=Path,required=True)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check",action="store_true")
    modes.add_argument("--benchmark",action="store_true")
    modes.add_argument("--run",action="store_true")
    p.add_argument("--workers",type=int,default=1)
    p.add_argument("--family",choices=FAMILIES)
    p.add_argument("--role",choices=ROLES)
    p.add_argument("--provider",choices=PROVIDERS)
    a=p.parse_args()
    require(1<=a.workers<=8,"workers must be 1..8")
    for key in ("design","staging","smoke","out"):
        setattr(a,key,getattr(a,key).expanduser().resolve())
    run(a)


if __name__=="__main__":
    main()
