#!/usr/bin/env python3
"""B0001 48-LHS original-style and pilot-CV LOCAL scoring adapter.

--check validates the frozen PUBLIC designs, source and seed plan (no simulation).
--smoke runs two 1-trajectory engineering checks in an isolated directory.
No hidden physical parameters, Phase-5 historical outputs, graph WB, graph
predictions, or evaluation data are opened. Full 100-trajectory candidate
scoring is a distinct stage, not authorized by this smoke runner.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
DESIGN_STATUS="B0001_TWO_48_LHS_PUBLIC_DESIGN_BANKS_FROZEN_NO_SIMULATION"
FAMILIES=("original","fixed_cv")
ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SOURCE="first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py"
SEED_BASE={"original":38_000_000,"fixed_cv":38_100_000}
SMOKE_STATUS="B0001_48_LHS_LOCAL_SCORING_ENGINEERING_SMOKE_PASS"


def require(ok,message):
    if not bool(ok):raise RuntimeError("B0001 local scoring: "+message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def seed_start(family,role,provider):
    return (SEED_BASE[family]+ROLES.index(role)*10_000
            +PROVIDERS.index(provider)*1_000)


def verify(a):
    require(a.design.is_dir() and a.staging.is_dir(),
            "Missing frozen B0001 source directory")
    require(REPO not in a.out.parents and a.out!=REPO,
            "Outputs cannot be written inside source Git checkout")
    for src in (a.design,a.staging):
        require(src!=a.out and src not in a.out.parents
                and a.out not in src.parents,
                "Output directory overlaps scientific inputs")
    dm_path=a.design/"b0001_48_lhs_design_freeze.json"
    dm=read(dm_path)
    require(dm["status"]==DESIGN_STATUS
            and dm["candidate_models_total"]==864,
            "Unexpected 48-LHS candidate design freeze")
    stage_path=a.staging/"b0001_public_inputs_manifest.json"
    require(dm["public_input_stage_sha256"]==sha(stage_path),
            "Public stage hash drift")
    s=read(stage_path)
    require(s["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE",
            "Invalid public stage")
    verifyfiles={}
    seeds={}
    for family in FAMILIES:
        for role in ROLES:
            for provider in PROVIDERS:
                rel=f"{family}/{role}/{provider}_lhs_design.csv"
                path=a.design/rel
                require(sha(path)==dm["design_file_sha256"][rel],
                        "Frozen candidate design hash mismatch: "+rel)
                df=pd.read_csv(path)
                require(len(df)==48 and df.candidate_id.is_unique
                        and set(["candidate_id","mean_service_time",
                                 "cost_rate","service_cv"]).issubset(df.columns),
                        "Frozen candidate design has wrong shape: "+rel)
                require(np.isfinite(df[["mean_service_time","cost_rate",
                    "service_cv"]].to_numpy(float)).all(),
                    "Nonfinite candidate parameters: "+rel)
                verifyfiles[rel]=sha(path)
                start=seed_start(family,role,provider)
                # 100 local trajectories per candidate; common random numbers
                # across all 48 candidates in one provider-family bank.
                require((start+99)*100+3<=2**32-1,
                        "Native seed overflows uint32")
                seeds[f"{family}/{role}/{provider}"]={
                    "start":start,"end_inclusive":start+99,
                    "n":100,"candidate_design_sha256":sha(path)}
    require(len({v["start"] for v in seeds.values()})==18,
            "Overlapping local seed banks")
    staged={entry["path"]:entry["staged_sha256"]
            for entry in s["staged_files"]}
    for role in ROLES:
        for provider in PROVIDERS:
            for filename in ("card.json","sigma_surface.csv"):
                rel=f"public_I1/{role}/{provider}/{filename}"
                require(rel in staged and
                        sha(a.staging/rel)==staged[rel],
                        "Public I1 card modified: "+rel)
    require(dm["historical_source_sha256"][SOURCE]==sha(REPO/SOURCE),
            "Historical local scoring engine changed")
    return dm_path,stage_path,verifyfiles,seeds


def module():
    for folder in (REPO/"first_science"/"phase2",
                   REPO/"first_science"/"phase3",
                   REPO/"first_science"/"phase4",
                   REPO/"first_science"/"phase5",
                   REPO/"first_science"/"b1"/"retrospective_m3"):
        if str(folder) not in sys.path:
            sys.path.insert(0,str(folder))
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    from run_m1_provider_lift_v2 import _simulate_and_score
    return load_rho_conditioned_i1_provider_card,_simulate_and_score


def smoke(a,dm_path,stage_path,seeds):
    require(not a.out.exists(),"Refusing overwrite of engineering smoke output")
    load_card,simulate=module()
    records=[]
    # Exercise both design families on same public card but independently
    # chosen candidate parameters; these are disposable engineering seeds.
    for family in FAMILIES:
        role,provider="P1","ProviderA"
        df=pd.read_csv(a.design/family/role/(provider+"_lhs_design.csv"))
        r=df.iloc[0]
        meta,public=load_card(a.staging/"public_I1"/role/provider)
        eng_seed=38_900_001 if family=="original" else 38_900_002
        require(eng_seed*100+3<=2**32-1,"Engineering seed overflow")
        metrics,simulated,comparison=simulate(
            metadata=meta,public_surface=public,
            mean_service_time=float(r.mean_service_time),
            cost_rate=float(r.cost_rate),
            service_cv=float(r.service_cv),
            trajectory_seeds=(eng_seed,),canonical_ipt=1000000.0,
            execution_fraction=0.5,quiet=True)
        require(len(comparison)==1200 and
                set(("sigma_i1","sigma_m1_local")).issubset(comparison.columns)
                and np.isfinite(comparison[
                    ["sigma_i1","sigma_m1_local"]].to_numpy(float)).all()
                and math.isfinite(float(metrics["mse"])),
                "Original provider-local scorer incompatible with frozen B0001 public I1")
        records.append({"family":family,"role":role,"provider":provider,
                        "candidate_id":str(r.candidate_id),
                        "engineering_seed":eng_seed,
                        "n_trajectories":1,"n_public_points":len(comparison),
                        "local_mse":float(metrics["mse"])})
        print("B0001_48_LHS_LOCAL_SCORE_SMOKE_CELL_PASS",family,
              "N=1, public_points=1200",flush=True)
    a.out.mkdir(parents=True)
    manifest={
        "status":SMOKE_STATUS,
        "design_manifest_sha256":sha(dm_path),
        "staging_manifest_sha256":sha(stage_path),
        "local_scoring_source_sha256":sha(REPO/
            "first_science/phase3/run_m1_provider_lift_v2.py"),
        "planned_18_fresh_scientific_seed_banks":seeds,
        "tests":records,"engineering_simulations":2,
        "scientific_candidate_curves_created":0,
        "final_reference_opened":False,
        "graph_predictions_authorized":False,
        "next_stage":"Separate gated all-864-candidate local scoring runner",
    }
    save(a.out/"b0001_48_lhs_local_scoring_smoke.json",manifest)
    print("B0001_48_LHS_LOCAL_SCORING_SMOKE_PASS",flush=True)
    print("NO_GRAPH_SIMULATIONS / NO_FINAL_WB_READ",flush=True)
    print("SMOKE",a.out/"b0001_48_lhs_local_scoring_smoke.json",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--design",type=Path,required=True)
    p.add_argument("--staging",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--smoke",action="store_true")
    a=p.parse_args()
    for key in ("design","staging","out"):
        setattr(a,key,getattr(a,key).expanduser().resolve())
    dm,stage,files,seeds=verify(a)
    print("B0001_48_LHS_LOCAL_SCORING_CHECK_PASS",
          len(files),"frozen banks",len(seeds),"fresh local seed blocks",flush=True)
    if a.check:
        print("NO_SIMULATIONS / NO_WRITES / NO_WB_ACCESS",flush=True)
        return
    smoke(a,dm,stage,seeds)


if __name__=="__main__":
    main()
