#!/usr/bin/env python3
"""Freeze B0001 original-style and fixed-CV provider weights/supports, PUBLIC ONLY.

Reads the 18 immutable B0001 local-scoring banks (864 x 1200 curves).
Runs the actual original Gibbs and blocked five-fold CV functions unchanged.
Original-style uses lambda=30. Fixed-CV chooses lambda from the historic grid
per world using public I1 only. Top14 uses rank 1..14 of each 48^3 joint bank
and the original minimax integer allocation at B=1400. Top1 is separately
budgeted. Writes no physical-world predictions and never reads white-box.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
B1=REPO/"first_science"/"b1"/"retrospective_m3"
FAMILIES=("original","fixed_cv")
WORLDS=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
GLOBAL_INPUT_STATUS="B0001_48_LHS_ALL_864_CANDIDATES_PUBLIC_ONLY_FROZEN"
PROVIDER_INPUT_STATUS="B0001_48_LHS_PROVIDER_LOCAL_48x100_FROZEN"
STATUS="B0001_48_LHS_TWO_FAMILY_WEIGHTS_AND_TOP14_SUPPORT_FROZEN"
BUDGET=1400
SOURCE_LIST=(
 "first_science/phase5/phase5_reconstruction_v3_selection.py",
 "first_science/phase4/m3_lambda_cv_v3.py",
 "first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py",
 "first_science/b1/retrospective_m3/config_pilot_m3_generalization_v1.json",
 "first_science/b1/retrospective_m3/config_pilot_m3_policy_transfer_v1.json",
)


def require(ok,msg):
    if not bool(ok):raise RuntimeError("B0001 48-LHS weighting: "+msg)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.suffix==".json":
            require(read(path)==obj,"Existing manifest changed: "+str(path))
        else:
            raise RuntimeError("Refusing overwrite of frozen data: "+str(path))
        return
    if path.suffix==".json":
        path.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    else:
        obj.to_csv(path,index=False)


def imports():
    for folder in (REPO/"first_science"/"phase2",
                   REPO/"first_science"/"phase3",
                   REPO/"first_science"/"phase4",
                   REPO/"first_science"/"phase5",
                   B1):
        if str(folder) not in sys.path:sys.path.insert(0,str(folder))
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    from phase5_reconstruction_v3_selection import gibbs_weights,joint_product_support
    from m3_lambda_cv_v3 import (_fold_assignments,_cv_scores,
                                 _summarize_cv,_select_lambda)
    from _pilot_m3_policy_transfer_core_v1 import allocation
    return load_rho_conditioned_i1_provider_card,gibbs_weights,joint_product_support,allocation,_fold_assignments,_cv_scores,_summarize_cv,_select_lambda


def preflight(a):
    require(REPO not in a.out.parents and a.out!=REPO,
            "Out cannot write to source repository")
    for src in (a.local,a.design,a.staging):
        require(src.is_dir(),"Missing scientific input directory: "+str(src))
        require(src!=a.out and src not in a.out.parents and
                a.out not in src.parents,"Out overlaps immutable input")
    source=a.local/"b0001_48_lhs_global_local_scoring_freeze.json"
    glob=read(source)
    require(glob["status"]==GLOBAL_INPUT_STATUS and
            glob["n_candidates_total"]==864 and
            glob["n_local_trajectories_total"]==86400 and
            glob["whitebox_reference_opened"] is False and
            glob["graph_predictions_executed"]==0,
            "Global public-only local-scoring freeze invalid")
    design_file=a.design/"b0001_48_lhs_design_freeze.json"
    design=read(design_file)
    stage_file=a.staging/"b0001_public_inputs_manifest.json"
    stage=read(stage_file)
    require(glob["source_design_freeze_sha256"]==digest(design_file) and
            glob["source_staging_manifest_sha256"]==digest(stage_file),
            "Inputs differ from frozen local-scoring provenance")
    for f in SOURCE_LIST:
        require((REPO/f).is_file(),"Historical source missing: "+f)
    for family in FAMILIES:
        for world in WORLDS:
            for provider in PROVIDERS:
                key=f"{family}/{world}/{provider}"
                fp=a.local/key/"provider_local_bank_manifest.json"
                require(digest(fp)==glob["provider_local_freeze_sha256"][
                    key+"/provider_local_bank_manifest.json"],
                    "Local bank manifest hash drift: "+key)
                bank=read(fp)
                require(bank["status"]==PROVIDER_INPUT_STATUS and
                        bank["n_candidates"]==48 and
                        bank["trajectory_count_per_candidate"]==100 and
                        bank["n_simulations"]==4800 and
                        bank["whitebox_reference_opened"] is False,
                        "Unexpected local bank contract: "+key)
                design_csv=a.design/family/world/(provider+"_lhs_design.csv")
                require(digest(design_csv)==bank["design_sha256"],
                        "Candidate design modified: "+key)
                for name,expected in bank["curves_sha256"].items():
                    require(digest(a.local/key/"surfaces"/name)==expected,
                            "Local candidate curve drift: "+key+"/"+name)
                for name,field in (("card.json","public_card_sha256"),
                                   ("sigma_surface.csv","public_surface_sha256")):
                    require(digest(a.staging/"public_I1"/world/provider/name)==bank[field],
                            "Public I1 card changed: "+key)
    return source,glob


def curves(a,family,world,provider,load_card):
    base=a.local/family/world/provider
    design=pd.read_csv(a.design/family/world/(provider+"_lhs_design.csv"))
    meta,public=load_card(a.staging/"public_I1"/world/provider)
    ref=public.loc[public["horizon"].astype(float)>0].sort_values(
        ["region_rho","rho","horizon"],kind="mergesort").reset_index(drop=True)
    require(len(ref)==1200,"Original CV expects 1200 public observations")
    target=ref["sigma_hat"].to_numpy(float)
    model=[]
    for cid in design.candidate_id.astype(str):
        curve=pd.read_csv(base/"surfaces"/(cid+".csv"))
        require(len(curve)==1200 and
                np.allclose(curve.sigma_i1.to_numpy(float),target,
                            atol=1e-12,rtol=0),
                "Original public target/curve mismatch: "+cid)
        model.append(curve.sigma_m1_local.to_numpy(float))
    return design,ref,target,np.stack(model)


def cv_frames(design,ref,target,models):
    pp=(100*target+0.5)/101.
    frames={}
    for cid,qq in zip(design.candidate_id.astype(str),models):
        sm=(100*qq+0.5)/101.
        kl=pp*np.log(pp/sm)+(1-pp)*np.log((1-pp)/(1-sm))
        df=ref[["region_rho","rho","horizon"]].copy()
        df["p_i1_jeffreys"]=pp
        df["p_candidate_jeffreys"]=sm
        df["bernoulli_kl_i1_to_candidate"]=kl
        frames[cid]=df
    return frames


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("local","design","staging","out"):
        p.add_argument("--"+name,required=True,type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--run",action="store_true")
    a=p.parse_args()
    for name in ("local","design","staging","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    source,glob=preflight(a)
    original_cfg=read(B1/"config_pilot_m3_generalization_v1.json")
    pilot_cfg=read(B1/"config_pilot_m3_policy_transfer_v1.json")
    require(original_cfg["lambda"]==30 and original_cfg["top_k"]==14 and
            original_cfg["graph_budget"]==BUDGET and
            pilot_cfg["top_k"]==14 and
            pilot_cfg["graph_budget"]==BUDGET and
            pilot_cfg["target_mass"]==0.999 and
            len(pilot_cfg["lambda_grid"])==17,
            "Original method configuration changed")
    print("B0001_48_LHS_WEIGHT_PREFLIGHT_PASS 864 SHA-verified curves",flush=True)
    if a.check:
        print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ",flush=True)
        return
    require(not a.out.exists(),"Refusing overwrite of weighting output")
    funcs=imports()
    load_card,gibbs,joint,allocation,folds,cv_scores,cv_summary,choose=funcs
    a.out.mkdir(parents=True)
    results={}
    for family in FAMILIES:
        for world in WORLDS:
            all_provider={}
            frames={}
            ref_cv=None
            for provider in PROVIDERS:
                design,ref,target,models=curves(a,family,world,provider,load_card)
                all_provider[provider]=(design,target,models)
                if family=="fixed_cv":
                    frames[provider]=cv_frames(design,ref,target,models)
                    if ref_cv is None:ref_cv=next(iter(frames[provider].values()))
            cv_rec=None
            if family=="fixed_cv":
                assign=folds(ref_cv)
                scores=cv_scores(surfaces=frames,assignments=assign,
                                 lambda_grid=list(map(float,pilot_cfg["lambda_grid"])))
                summary=cv_summary(scores)
                best=choose(summary)
                lam=float(best["lambda"])
                cv_root=a.out/family/world/"cv"
                freeze(cv_root/"cv_assignments.csv",assign)
                freeze(cv_root/"cv_scores.csv",scores)
                freeze(cv_root/"cv_summary.csv",summary)
                cv_rec={
                    "selected_lambda":lam,
                    "mean_validation_bernoulli_kl":float(best["mean_validation_bernoulli_kl"]),
                    "cv_assignments_sha256":digest(cv_root/"cv_assignments.csv"),
                    "cv_scores_sha256":digest(cv_root/"cv_scores.csv"),
                    "cv_summary_sha256":digest(cv_root/"cv_summary.csv"),
                }
                freeze(cv_root/"cv_selection.json",cv_rec)
            else:
                lam=30.0
            tables={}
            files={}
            for provider,(design,target,models) in all_provider.items():
                weights=gibbs(design.candidate_id.astype(str),
                              models,target,n_public=100,n_candidate=100,lam=lam)
                combined=design.merge(weights,on="candidate_id",validate="one_to_one")
                combined["local_mse"]=[float(np.mean((target-r)**2)) for r in models]
                combined["curve_sha256"]=[
                    digest(a.local/family/world/provider/"surfaces"/(cid+".csv"))
                    for cid in combined.candidate_id.astype(str)]
                combined=combined.sort_values("weight_rank",kind="mergesort")
                require(len(combined)==48 and
                        np.isclose(combined.weight.sum(),1,atol=1e-12),
                        "Gibbs provider weights invalid")
                wpath=a.out/family/world/provider/"provider_weights.csv"
                freeze(wpath,combined)
                tables[provider]=combined
                files[provider]=digest(wpath)
            support=joint(tables)
            require(len(support)==48**3 and
                    np.isclose(support.joint_weight.sum(),1,atol=1e-10),
                    "Invalid joint product model support")
            top=support.iloc[:14].copy()
            retained=float(top.joint_weight.sum())
            top["alpha"]=top.joint_weight/retained
            top["n_trajectories"]=allocation(top.alpha.to_numpy(float),BUDGET)
            require(int(top.n_trajectories.sum())==BUDGET and
                    top.n_trajectories.min()>=1 and
                    np.isclose(top.alpha.sum(),1),
                    "Top14 minimax allocation invalid")
            top["retained_mass"]=retained
            top["omitted_mass"]=1-retained
            root=a.out/family/world/"support"
            freeze(root/"top14_support.csv",top)
            require(0<retained<=1,"Invalid retained Top14 mass")
            if family=="fixed_cv":
                cumulative=support.joint_weight.astype(float).cumsum().to_numpy()
                k=int(np.searchsorted(cumulative,0.999,side="left")+1)
                adaptive={"target_mass":0.999,
                          "adaptive_k":k,
                          "adaptive_feasible_at_b1400":k<=BUDGET,
                          "adaptive_retained_mass":float(cumulative[k-1])}
            else:adaptive=None
            record={
                "status":"B0001_48_LHS_WORLD_PUBLIC_WEIGHT_AND_TOP14_FROZEN",
                "family":family,"world":world,
                "lambda":lam,"candidate_count_per_provider":48,
                "joint_support_size":48**3,
                "top14_support_size":14,
                "top14_retained_mass":retained,
                "graph_budget_per_method":BUDGET,
                "top14_allocation_total":int(top.n_trajectories.sum()),
                "provider_weight_sha256":files,
                "top14_support_sha256":digest(root/"top14_support.csv"),
                "cv_selection":cv_rec,"adaptive_mass_audit":adaptive,
                "graph_simulations":0,
                "whitebox_reference_opened":False,
            }
            freeze(root/"world_support_manifest.json",record)
            results[f"{family}/{world}"]={
                "world_support_manifest_sha256":digest(root/"world_support_manifest.json"),
                "lambda":lam,"top14_retained_mass":retained,
                "adaptive_mass_audit":adaptive,
            }
            print("B0001_48_LHS_WORLD_WEIGHTS_FROZEN",family,world,
                  f"lambda={lam:g}",f"top14_mass={retained:.6f}",
                  flush=True)
    complete={
        "status":STATUS,
        "input_global_local_scoring_manifest_sha256":digest(source),
        "historical_sources_sha256":{p:digest(REPO/p) for p in SOURCE_LIST},
        "world_supports":results,
        "world_families":6,
        "models_per_provider":48,
        "graph_simulations":0,
        "whitebox_reference_opened":False,
        "next_stage":"isolate four historical B1400 graph predictors using these frozen supports and new graph RNG seeds",
    }
    out=a.out/"b0001_48_lhs_weight_and_support_freeze.json"
    freeze(out,complete)
    print("B0001_48_LHS_ALL_SIX_WORLD_SUPPORTS_FROZEN",flush=True)
    print("FREEZE",out,flush=True)


if __name__=="__main__":
    main()
