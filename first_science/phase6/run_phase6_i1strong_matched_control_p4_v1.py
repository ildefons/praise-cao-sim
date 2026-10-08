"""Matched I1-strong provider reconstruction control for P4.

This is the reconstruction-budget control for the frozen I2AFS experiment.
Everything is matched to I2AFS except provider information/loss:

- same frozen parameter domains,
- same 64 Sobol initial points,
- same 192 TPE adaptive trials,
- same sampler seeds,
- same N=25 search CRN bank,
- same top-24 shortlist,
- same N=100 common rescore bank,
- same top-3/provider M2 support.

The objective is the original complete public-I1 sigma-surface MSE (H>0).
No I2a data, graph result, WB result, private I1 ledger, or hidden provider
parameter is read.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE3=HERE.parent/"phase3"
PHASE5=HERE.parent/"phase5"
for p in (PHASE3,PHASE5):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from phase5_runtime_v2 import (  # noqa:E402
    git_head, read_json, sha256_file, utc_now_iso, write_json,
)
from run_m1_provider_lift_v2 import _load_optuna, _simulate_and_score  # noqa:E402
from run_phase5_m2_reconstruction_v2 import (  # noqa:E402
    _bounds, _domain_row, _load_public_card,
)
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import (  # noqa:E402
    _sobol_initial_points,
)

CFG=HERE/"config_phase6_i1strong_matched_control_p4_v1.json"
ROOT=HERE/"results"/"18_i1strong_reconstruction_p4"
WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I1_STRONG_MATCHED_CONTROL_P4_V1"


def _seed_tuple(start:int,end_inclusive:int,n:int)->tuple[int,...]:
    out=tuple(range(int(start),int(end_inclusive)+1))
    if len(out)!=int(n):
        raise RuntimeError("invalid frozen seed block")
    return out


def _score_i1(
    *,
    metadata:dict[str,Any],
    public_surface:pd.DataFrame,
    mean_service_time:float,
    cost_rate:float,
    service_cv:float,
    seeds:tuple[int,...],
)->dict[str,float]:
    metrics,_,_=_simulate_and_score(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
        trajectory_seeds=seeds,
        canonical_ipt=1_000_000.0,
        execution_fraction=0.5,
        quiet=True,
    )
    required={"mse","rmse","mae","bias","max_abs_error"}
    if not required.issubset(metrics):
        raise RuntimeError("I1 full-surface scorer returned incomplete metrics")
    return {k:float(metrics[k]) for k in required}


def _study_rows(study,optuna)->pd.DataFrame:
    rows=[]
    for t in study.trials:
        if t.state!=optuna.trial.TrialState.COMPLETE:
            continue
        if t.value is None:
            raise RuntimeError("complete Optuna trial missing value")
        required={"mean_service_time","cost_rate","service_cv"}
        if not required.issubset(t.params):
            raise RuntimeError("complete Optuna trial missing parameters")
        rows.append({
            "trial_number":int(t.number),
            "search_i1_mse":float(t.value),
            "search_i1_rmse":float(math.sqrt(float(t.value))),
            "search_i1_mae":float(t.user_attrs["mae"]),
            "search_i1_bias":float(t.user_attrs["bias"]),
            "search_i1_max_abs_error":float(t.user_attrs["max_abs_error"]),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        })
    return pd.DataFrame(rows)


def _run_search(
    *,
    provider:str,
    metadata:dict[str,Any],
    public_surface:pd.DataFrame,
    bounds,
    cfg:dict[str,Any],
    out:Path,
)->pd.DataFrame:
    search=cfg["search"]
    total_trials=int(search["total_trials"])
    sobol_n=int(search["sobol_initial_trials"])
    adaptive_n=int(search["tpe_adaptive_trials"])
    if sobol_n+adaptive_n!=total_trials:
        raise RuntimeError("frozen trial counts do not add up")

    search_seeds=_seed_tuple(
        search["search_seed_start"],
        search["search_seed_end_inclusive"],
        search["search_n"],
    )

    optuna=_load_optuna()
    db_path=(out/"optuna_search.sqlite3").resolve()
    study_name=f"phase6_i1strong_{WORLD}_{provider}_v1"
    sampler=optuna.samplers.TPESampler(
        seed=int(search["tpe_sampler_seeds"][provider]),
        n_startup_trials=0,
    )
    study=optuna.create_study(
        direction="minimize",
        sampler=sampler,
        storage=f"sqlite:///{db_path}",
        study_name=study_name,
        load_if_exists=True,
    )

    failed=sum(
        t.state==optuna.trial.TrialState.FAIL for t in study.trials
    )
    if failed:
        raise RuntimeError(f"{provider}: existing search contains {failed} failed trials")

    if len(study.trials)==0:
        initial=_sobol_initial_points(
            sobol_n,int(search["sobol_seed"]),bounds
        )
        for params in initial:
            study.enqueue_trial(params)
        print(
            f"I1STRONG SEARCH {WORLD}/{provider}: enqueued {sobol_n} matched Sobol trials",
            flush=True,
        )

    complete_before=sum(
        t.state==optuna.trial.TrialState.COMPLETE for t in study.trials
    )
    if complete_before>total_trials:
        raise RuntimeError(
            f"{provider}: search already has {complete_before}>{total_trials} trials"
        )

    started=time.perf_counter()
    best=[float("inf")]

    def objective(trial):
        mu=trial.suggest_float(
            "mean_service_time",
            bounds.mean_service_time_lower,
            bounds.mean_service_time_upper,
            log=True,
        )
        cost=trial.suggest_float(
            "cost_rate",
            bounds.cost_rate_lower,
            bounds.cost_rate_upper,
            log=True,
        )
        cv=trial.suggest_float(
            "service_cv",
            bounds.service_cv_lower,
            bounds.service_cv_upper,
            log=False,
        )
        metrics=_score_i1(
            metadata=metadata,
            public_surface=public_surface,
            mean_service_time=mu,
            cost_rate=cost,
            service_cv=cv,
            seeds=search_seeds,
        )
        trial.set_user_attr("mae",metrics["mae"])
        trial.set_user_attr("bias",metrics["bias"])
        trial.set_user_attr("max_abs_error",metrics["max_abs_error"])
        return metrics["mse"]

    def progress(study_,trial):
        if trial.value is None:
            return
        complete=sum(
            t.state==optuna.trial.TrialState.COMPLETE
            for t in study_.trials
        )
        value=float(trial.value)
        improved=value<best[0]-1e-15
        if improved:
            best[0]=value
        if improved or complete%10==0 or complete==total_trials:
            elapsed=time.perf_counter()-started
            newly=max(1,complete-complete_before)
            remaining=max(0,total_trials-complete)
            eta=(elapsed/newly)*remaining
            phase="SOBOL" if int(trial.number)<sobol_n else "TPE"
            print(
                f"I1STRONG SEARCH {WORLD}/{provider} {phase} "
                f"{complete}/{total_trials} best_MSE={best[0]:.6g} "
                f"best_RMSE={math.sqrt(best[0]):.6g} "
                f"elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m",
                flush=True,
            )

    remaining=total_trials-complete_before
    if remaining>0:
        study.optimize(
            objective,
            n_trials=remaining,
            callbacks=[progress],
            show_progress_bar=False,
        )

    trials=_study_rows(study,optuna)
    if len(trials)!=total_trials:
        raise RuntimeError(
            f"{provider}: expected {total_trials} complete trials, found {len(trials)}"
        )
    trials=trials.sort_values(
        ["search_i1_mse","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    trials.insert(0,"search_rank",np.arange(1,len(trials)+1,dtype=int))
    path=out/"search_trials_256.csv"
    trials.to_csv(path,index=False)
    return trials


def _rescore_shortlist(
    *,
    provider:str,
    metadata:dict[str,Any],
    public_surface:pd.DataFrame,
    trials:pd.DataFrame,
    cfg:dict[str,Any],
    out:Path,
)->pd.DataFrame:
    search=cfg["search"]
    rescore=cfg["common_rescore"]
    shortlist_n=int(search["rescore_shortlist_count"])
    shortlist=trials.head(shortlist_n).copy()
    if len(shortlist)!=24:
        raise RuntimeError("matched control shortlist is not 24")

    seeds=_seed_tuple(
        rescore["seed_start"],
        rescore["seed_end_inclusive"],
        rescore["n"],
    )
    cp_root=out/"rescore_checkpoints"
    cp_root.mkdir(parents=True,exist_ok=True)

    rows=[]
    for ordinal,rec in enumerate(shortlist.itertuples(index=False),start=1):
        trial_number=int(rec.trial_number)
        cp=cp_root/f"trial_{trial_number:04d}.json"
        if cp.is_file():
            row=read_json(cp)
            if (
                row.get("status")!="PHASE6_I1STRONG_RESCORE_COMPLETE"
                or int(row["trial_number"])!=trial_number
            ):
                raise RuntimeError(f"{provider}: incompatible rescore checkpoint")
            rows.append(row)
            print(
                f"I1STRONG RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
                f"trial={trial_number} RMSE={float(row['rescore_i1_rmse']):.6g} [cached]",
                flush=True,
            )
            continue

        metrics=_score_i1(
            metadata=metadata,
            public_surface=public_surface,
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            seeds=seeds,
        )
        row={
            "status":"PHASE6_I1STRONG_RESCORE_COMPLETE",
            "provider_world_id":WORLD,
            "provider_id":provider,
            "candidate_id":f"P4_{provider}_I1STRONG_T{trial_number:03d}",
            "trial_number":trial_number,
            "search_rank":int(rec.search_rank),
            "search_i1_mse":float(rec.search_i1_mse),
            "search_i1_rmse":float(rec.search_i1_rmse),
            "rescore_i1_mse":metrics["mse"],
            "rescore_i1_rmse":metrics["rmse"],
            "rescore_i1_mae":metrics["mae"],
            "rescore_i1_bias":metrics["bias"],
            "rescore_i1_max_abs_error":metrics["max_abs_error"],
            "mean_service_time":float(rec.mean_service_time),
            "cost_rate":float(rec.cost_rate),
            "service_cv":float(rec.service_cv),
            "rescore_seed_start":int(seeds[0]),
            "rescore_seed_end_inclusive":int(seeds[-1]),
            "rescore_n":len(seeds),
        }
        write_json(cp,row)
        rows.append(row)
        print(
            f"I1STRONG RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
            f"trial={trial_number} RMSE={metrics['rmse']:.6g}",
            flush=True,
        )

    scores=pd.DataFrame(rows).sort_values(
        ["rescore_i1_mse","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    scores.insert(0,"i1strong_quality_rank",np.arange(1,len(scores)+1,dtype=int))
    scores.to_csv(out/"rescore_top24.csv",index=False)
    return scores


def run_provider(provider:str)->dict[str,Any]:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected matched-control config status")

    out=ROOT/provider
    out.mkdir(parents=True,exist_ok=True)
    manifest_path=out/"provider_reconstruction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_I1STRONG_PROVIDER_RECONSTRUCTION_COMPLETE":
            print(f"I1STRONG RECON {WORLD}/{provider} cached",flush=True)
            return {
                "provider_id":provider,
                "best_candidate_id":str(m["m2_candidate_ids"][0]),
                "m2_candidate_ids":";".join(m["m2_candidate_ids"]),
                "wall_seconds":0.0,
                "manifest_sha256":sha256_file(manifest_path),
            }
        raise RuntimeError(f"{provider}: incompatible existing manifest")

    started=time.perf_counter()
    metadata,public_surface,_=_load_public_card(WORLD,provider)
    domain=_domain_row(WORLD,provider)
    bounds=_bounds(domain)

    trials=_run_search(
        provider=provider,
        metadata=metadata,
        public_surface=public_surface,
        bounds=bounds,
        cfg=cfg,
        out=out,
    )
    scores=_rescore_shortlist(
        provider=provider,
        metadata=metadata,
        public_surface=public_surface,
        trials=trials,
        cfg=cfg,
        out=out,
    )

    m2=scores.head(3).copy()
    m2.insert(0,"method_id","I1STRONG_M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"i1strong_m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    card=PHASE5/"results"/"01_i1"/WORLD/"public"/provider/"card.json"
    sigma=PHASE5/"results"/"01_i1"/WORLD/"public"/provider/"sigma_surface.csv"
    manifest={
        "status":"PHASE6_I1STRONG_PROVIDER_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "public_card_sha256":sha256_file(card),
        "public_i1_sigma_surface_sha256":sha256_file(sigma),
        "loss":"original_public_I1_full_sigma_surface_MSE_H_gt_0",
        "total_search_trials":int(cfg["search"]["total_trials"]),
        "sobol_initial_trials":int(cfg["search"]["sobol_initial_trials"]),
        "tpe_adaptive_trials":int(cfg["search"]["tpe_adaptive_trials"]),
        "search_n":int(cfg["search"]["search_n"]),
        "rescore_shortlist_count":int(cfg["search"]["rescore_shortlist_count"]),
        "rescore_n":int(cfg["common_rescore"]["n"]),
        "selection_metric":"rescore_i1_mse",
        "m2_candidate_ids":m2["candidate_id"].astype(str).tolist(),
        "i2a_used":False,
        "graph_prediction_used":False,
        "graph_wb_used":False,
        "final_wb_used":False,
        "private_i1_ledger_used":False,
        "hidden_provider_parameters_used":False,
        "outputs":{
            "search_trials":str(out/"search_trials_256.csv"),
            "rescore_top24":str(out/"rescore_top24.csv"),
            "m2_provider_models":str(m2_path),
        },
        "output_hashes_sha256":{
            "search_trials":sha256_file(out/"search_trials_256.csv"),
            "rescore_top24":sha256_file(out/"rescore_top24.csv"),
            "m2_provider_models":sha256_file(m2_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    }
    write_json(manifest_path,manifest)
    return {
        "provider_id":provider,
        "best_candidate_id":str(m2.iloc[0]["candidate_id"]),
        "m2_candidate_ids":";".join(m2["candidate_id"].astype(str)),
        "wall_seconds":float(manifest["wall_seconds"]),
        "manifest_sha256":sha256_file(manifest_path),
    }


def _freeze_world(provider_rows:list[dict[str,Any]])->Path:
    tables={}
    for provider in PROVIDERS:
        path=ROOT/provider/"i1strong_m2_provider_models.csv"
        t=pd.read_csv(path)
        if len(t)!=3:
            raise RuntimeError(f"{provider}: I1-strong M2 support !=3")
        tables[provider]=t

    rows=[]
    rank=0
    for a in tables["ProviderA"].itertuples(index=False):
        for b in tables["ProviderB"].itertuples(index=False):
            for c in tables["ProviderC"].itertuples(index=False):
                rank+=1
                rows.append({
                    "joint_rank":rank,
                    "ProviderA_candidate_id":str(a.candidate_id),
                    "ProviderB_candidate_id":str(b.candidate_id),
                    "ProviderC_candidate_id":str(c.candidate_id),
                    "joint_weight":1.0/27.0,
                })
    support=pd.DataFrame(rows)
    if len(support)!=27:
        raise RuntimeError("I1-strong joint M2 support !=27")
    support_path=ROOT/"m2_joint_support_27.csv"
    support.to_csv(support_path,index=False)

    summary=pd.DataFrame(provider_rows).sort_values(
        "provider_id",kind="mergesort"
    ).reset_index(drop=True)
    summary_path=ROOT/"provider_reconstruction_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest={
        "status":"PHASE6_I1STRONG_P4_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_count":3,
        "m2_joint_models":27,
        "matched_i2afs_search_architecture":True,
        "provider_reconstruction_manifest_sha256":{
            p:sha256_file(ROOT/p/"provider_reconstruction_manifest.json")
            for p in PROVIDERS
        },
        "outputs":{
            "summary":str(summary_path),
            "m2_joint_support_27":str(support_path),
        },
        "output_hashes_sha256":{
            "summary":sha256_file(summary_path),
            "m2_joint_support_27":sha256_file(support_path),
        },
        "completed_utc":utc_now_iso(),
    }
    path=ROOT/"p4_i1strong_reconstruction_manifest.json"
    write_json(path,manifest)

    print("\nPHASE6_I1STRONG_P4_RECONSTRUCTION_PASS")
    print(summary.to_string(index=False))
    for provider in PROVIDERS:
        print(f"\n{provider} TOP3")
        print(
            tables[provider][[
                "candidate_id","trial_number",
                "rescore_i1_rmse",
                "mean_service_time","cost_rate","service_cv",
            ]].to_string(index=False)
        )
    print("\njoint_models 27")
    print("manifest",path)
    return path


def main():
    p=argparse.ArgumentParser(
        description="Matched I1-strong reconstruction control for P4"
    )
    p.add_argument("--workers",type=int,default=3)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")

    rows=[]
    if args.workers==1:
        for provider in PROVIDERS:
            rows.append(run_provider(provider))
    else:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=min(int(args.workers),3)
        ) as pool:
            futures={pool.submit(run_provider,p):p for p in PROVIDERS}
            for fut in concurrent.futures.as_completed(futures):
                provider=futures[fut]
                try:
                    rows.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(
                        f"I1-strong reconstruction failed for {provider}"
                    ) from exc
    _freeze_world(rows)


if __name__=="__main__":
    main()
