"""Best-shot Phase-6 I2a full-spectrum provider reconstruction for P4.

This runner implements the frozen protocol in
PHASE6_I2A_FULL_SPECTRUM_RECONSTRUCTION_PROTOCOL_2026-10-08.md.

The reconstruction objective is the full marginal survival-surface loss:

    sqrt(mean_{A,H} integral_0^1
         [sigma_candidate(A,H;rho)-sigma_I2a(A,H;rho)]^2 d rho)

with the integral evaluated exactly over pooled empirical breakpoints.

The search is one 256-trial study per provider:
- 64 deterministic scrambled-Sobol initial points in normalized parameter space,
- 192 TPE-adaptive trials,
- N=25 common-random-number search bank,
- best 24 trials rescored on a fresh common N=100 bank,
- best 3 N=100 candidates retained for M2.

No graph result, WB result, private I1 ledger, or hidden provider parameter is
read by this runner.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import os
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
    git_head,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from run_m1_provider_lift_v2 import _load_optuna  # noqa:E402
from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row  # noqa:E402
from run_phase6_i2a_genuine_reconstruction_p4_v1 import (  # noqa:E402
    _load_target,
    _simulate_samples,
)
from run_phase6_crossworld_full_spectrum_sigma_loss import (  # noqa:E402
    integrated_survival_sq,
)

CFG=HERE/"config_phase6_i2a_fullspectrum_reconstruction_p4_v1.json"
ROOT=HERE/"results"/"14_i2a_fullspectrum_reconstruction_p4"
WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I2A_FULL_SPECTRUM_RECONSTRUCTION_P4_V1"


def _seed_tuple(start:int,end_inclusive:int,n:int)->tuple[int,...]:
    out=tuple(range(int(start),int(end_inclusive)+1))
    if len(out)!=int(n):
        raise RuntimeError("invalid frozen seed block")
    return out


def _full_score(
    target:dict[tuple[str,float],np.ndarray],
    candidate:dict[tuple[str,float],np.ndarray],
)->tuple[float,float,float]:
    """Return RMSE-style full-spectrum score plus group diagnostics."""
    if set(target)!=set(candidate):
        raise RuntimeError("I2a target/candidate group support mismatch")
    vals=np.asarray(
        [
            integrated_survival_sq(target[k],candidate[k])
            for k in sorted(target,key=lambda x:(x[0],x[1]))
        ],
        dtype=float,
    )
    if len(vals)!=5*48 or np.any(vals<0.0):
        raise RuntimeError("invalid full-spectrum group losses")
    rmse=float(math.sqrt(float(vals.mean())))
    median_group_rmse=float(np.median(np.sqrt(vals)))
    max_group_rmse=float(np.sqrt(vals.max()))
    return rmse,median_group_rmse,max_group_rmse


def _unit_to_params(u:np.ndarray,bounds)->dict[str,float]:
    u=np.asarray(u,dtype=float)
    if u.shape!=(3,) or np.any(u<0.0) or np.any(u>1.0):
        raise ValueError("Sobol point must be in [0,1]^3")

    def log_map(x:float,lo:float,hi:float)->float:
        return float(math.exp(math.log(float(lo))+float(x)*(math.log(float(hi))-math.log(float(lo)))))

    return {
        "mean_service_time":log_map(
            u[0],bounds.mean_service_time_lower,bounds.mean_service_time_upper
        ),
        "cost_rate":log_map(
            u[1],bounds.cost_rate_lower,bounds.cost_rate_upper
        ),
        "service_cv":float(
            bounds.service_cv_lower
            +u[2]*(bounds.service_cv_upper-bounds.service_cv_lower)
        ),
    }


def _sobol_initial_points(n:int,seed:int,bounds)->list[dict[str,float]]:
    if n<=0 or n&(n-1):
        raise ValueError("Sobol initial count must be a power of two")
    try:
        from scipy.stats import qmc
    except Exception as exc:
        raise RuntimeError("scipy.stats.qmc is required for frozen Sobol initialization") from exc
    sampler=qmc.Sobol(d=3,scramble=True,seed=int(seed))
    m=int(round(math.log2(n)))
    pts=sampler.random_base2(m=m)
    if pts.shape!=(n,3):
        raise RuntimeError("unexpected Sobol design shape")
    return [_unit_to_params(row,bounds) for row in pts]


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
            "search_full_spectrum_rmse":float(t.value),
            "search_median_group_rmse":float(
                t.user_attrs["median_group_rmse"]
            ),
            "search_max_group_rmse":float(
                t.user_attrs["max_group_rmse"]
            ),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        })
    return pd.DataFrame(rows)


def _run_search(
    *,
    provider:str,
    metadata:dict[str,Any],
    target:dict[tuple[str,float],np.ndarray],
    bounds,
    cfg:dict[str,Any],
    out:Path,
)->pd.DataFrame:
    search=cfg["search"]
    total_trials=int(search["total_trials"])
    sobol_n=int(search["sobol_initial_trials"])
    adaptive_n=int(search["tpe_adaptive_trials"])
    if sobol_n+adaptive_n!=total_trials:
        raise RuntimeError("frozen search trial counts do not add up")

    search_seeds=_seed_tuple(
        search["search_seed_start"],
        search["search_seed_end_inclusive"],
        search["search_n"],
    )

    optuna=_load_optuna()
    db_path=(out/"optuna_search.sqlite3").resolve()
    study_name=f"phase6_i2afs_{WORLD}_{provider}_v1"
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

    states=[t.state for t in study.trials]
    failed=sum(s==optuna.trial.TrialState.FAIL for s in states)
    if failed:
        raise RuntimeError(f"{provider}: existing search contains {failed} failed trials")

    if len(study.trials)==0:
        initial=_sobol_initial_points(
            sobol_n,int(search["sobol_seed"]),bounds
        )
        for params in initial:
            study.enqueue_trial(params)
        print(
            f"I2AFS SEARCH {WORLD}/{provider}: enqueued {sobol_n} Sobol trials",
            flush=True,
        )

    complete_before=sum(
        t.state==optuna.trial.TrialState.COMPLETE for t in study.trials
    )
    if complete_before>total_trials:
        raise RuntimeError(
            f"{provider}: search already has {complete_before}>{total_trials} complete trials"
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
        cand=_simulate_samples(
            metadata=metadata,
            mean_service_time=mu,
            cost_rate=cost,
            service_cv=cv,
            seeds=search_seeds,
        )
        score,median_group,max_group=_full_score(target,cand)
        trial.set_user_attr("median_group_rmse",median_group)
        trial.set_user_attr("max_group_rmse",max_group)
        return score

    def progress(study_,trial):
        if trial.value is None:
            return
        complete=sum(
            t.state==optuna.trial.TrialState.COMPLETE for t in study_.trials
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
                f"I2AFS SEARCH {WORLD}/{provider} {phase} "
                f"{complete}/{total_trials} best={best[0]:.6g} "
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
        ["search_full_spectrum_rmse","trial_number"],
        kind="mergesort",
    ).reset_index(drop=True)
    trials.insert(0,"search_rank",np.arange(1,len(trials)+1,dtype=int))
    trials_path=out/"search_trials_256.csv"
    trials.to_csv(trials_path,index=False)
    return trials


def _rescore_shortlist(
    *,
    provider:str,
    metadata:dict[str,Any],
    target:dict[tuple[str,float],np.ndarray],
    trials:pd.DataFrame,
    cfg:dict[str,Any],
    out:Path,
)->pd.DataFrame:
    search=cfg["search"]
    rescore=cfg["common_rescore"]
    shortlist_n=int(search["rescore_shortlist_count"])
    if shortlist_n<3 or shortlist_n>len(trials):
        raise RuntimeError("invalid frozen rescore shortlist count")
    shortlist=trials.head(shortlist_n).copy()
    seeds=_seed_tuple(
        rescore["seed_start"],
        rescore["seed_end_inclusive"],
        rescore["n"],
    )

    rows=[]
    checkpoint_dir=out/"rescore_checkpoints"
    checkpoint_dir.mkdir(parents=True,exist_ok=True)

    for ordinal,rec in enumerate(shortlist.itertuples(index=False),start=1):
        trial_number=int(rec.trial_number)
        cp=checkpoint_dir/f"trial_{trial_number:04d}.json"
        if cp.is_file():
            row=read_json(cp)
            if (
                int(row["trial_number"])!=trial_number
                or row.get("status")!="PHASE6_I2AFS_RESCORE_COMPLETE"
            ):
                raise RuntimeError(f"{provider}: incompatible rescore checkpoint {cp}")
            rows.append(row)
            print(
                f"I2AFS RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
                f"trial={trial_number} score={float(row['rescore_full_spectrum_rmse']):.6g} [cached]",
                flush=True,
            )
            continue

        cand=_simulate_samples(
            metadata=metadata,
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            seeds=seeds,
        )
        score,median_group,max_group=_full_score(target,cand)
        row={
            "status":"PHASE6_I2AFS_RESCORE_COMPLETE",
            "provider_world_id":WORLD,
            "provider_id":provider,
            "candidate_id":f"P4_{provider}_I2AFS_T{trial_number:03d}",
            "trial_number":trial_number,
            "search_rank":int(rec.search_rank),
            "search_full_spectrum_rmse":float(rec.search_full_spectrum_rmse),
            "rescore_full_spectrum_rmse":score,
            "rescore_median_group_rmse":median_group,
            "rescore_max_group_rmse":max_group,
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
            f"I2AFS RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
            f"trial={trial_number} score={score:.6g}",
            flush=True,
        )

    scores=pd.DataFrame(rows).sort_values(
        ["rescore_full_spectrum_rmse","trial_number"],
        kind="mergesort",
    ).reset_index(drop=True)
    scores.insert(0,"i2afs_quality_rank",np.arange(1,len(scores)+1,dtype=int))
    scores_path=out/"rescore_top24.csv"
    scores.to_csv(scores_path,index=False)
    return scores


def run_provider(provider:str)->dict[str,Any]:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected I2a full-spectrum reconstruction config status")

    out=ROOT/provider
    out.mkdir(parents=True,exist_ok=True)
    manifest_path=out/"provider_reconstruction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_I2AFS_PROVIDER_RECONSTRUCTION_COMPLETE":
            print(f"I2AFS RECON {WORLD}/{provider} cached",flush=True)
            return {
                "provider_id":provider,
                "best_candidate_id":str(m["m2_candidate_ids"][0]),
                "m2_candidate_ids":";".join(m["m2_candidate_ids"]),
                "wall_seconds":0.0,
                "manifest_sha256":sha256_file(manifest_path),
            }
        raise RuntimeError(f"{provider}: incompatible existing provider manifest")

    started=time.perf_counter()
    metadata,_,target=_load_target(provider)
    domain=_domain_row(WORLD,provider)
    bounds=_bounds(domain)

    trials=_run_search(
        provider=provider,
        metadata=metadata,
        target=target,
        bounds=bounds,
        cfg=cfg,
        out=out,
    )
    scores=_rescore_shortlist(
        provider=provider,
        metadata=metadata,
        target=target,
        trials=trials,
        cfg=cfg,
        out=out,
    )

    m2=scores.head(3).copy()
    m2.insert(0,"method_id","I2AFS_M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"i2afs_m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    manifest={
        "status":"PHASE6_I2AFS_PROVIDER_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "public_i2a_sha256":sha256_file(
            HERE/"results"/"01_i2a_marginal_audit"/WORLD/provider/
            "i2a_public_empirical_cdf.csv"
        ),
        "loss":"full_spectrum_integrated_squared_survival_rmse",
        "total_search_trials":int(cfg["search"]["total_trials"]),
        "sobol_initial_trials":int(cfg["search"]["sobol_initial_trials"]),
        "tpe_adaptive_trials":int(cfg["search"]["tpe_adaptive_trials"]),
        "search_n":int(cfg["search"]["search_n"]),
        "rescore_shortlist_count":int(cfg["search"]["rescore_shortlist_count"]),
        "rescore_n":int(cfg["common_rescore"]["n"]),
        "selection_metric":"rescore_full_spectrum_rmse",
        "m2_candidate_ids":m2["candidate_id"].astype(str).tolist(),
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
        path=ROOT/provider/"i2afs_m2_provider_models.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        t=pd.read_csv(path)
        if len(t)!=3:
            raise RuntimeError(f"{provider}: I2AFS M2 provider support !=3")
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
        raise RuntimeError("I2AFS M2 joint support !=27")

    support_path=ROOT/"m2_joint_support_27.csv"
    support.to_csv(support_path,index=False)

    summary=pd.DataFrame(provider_rows).sort_values(
        "provider_id",kind="mergesort"
    ).reset_index(drop=True)
    summary_path=ROOT/"provider_reconstruction_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest={
        "status":"PHASE6_I2AFS_P4_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_count":3,
        "m2_joint_models":27,
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
    path=ROOT/"p4_i2afs_reconstruction_manifest.json"
    write_json(path,manifest)

    print("\nPHASE6_I2AFS_P4_RECONSTRUCTION_PASS")
    print(summary.to_string(index=False))
    for provider in PROVIDERS:
        print(f"\n{provider} TOP3")
        print(
            tables[provider][
                [
                    "candidate_id",
                    "trial_number",
                    "rescore_full_spectrum_rmse",
                    "mean_service_time",
                    "cost_rate",
                    "service_cv",
                ]
            ].to_string(index=False)
        )
    print("\njoint_models 27")
    print("manifest",path)
    return path


def main():
    p=argparse.ArgumentParser(
        description="Best-shot I2a full-spectrum reconstruction for P4"
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
                        f"I2AFS provider reconstruction failed for {provider}"
                    ) from exc
    _freeze_world(rows)


if __name__=="__main__":
    main()
