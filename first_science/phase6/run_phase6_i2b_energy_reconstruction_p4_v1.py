"""Matched Phase-6 I2b-v1 empirical-energy provider reconstruction for P4.

Everything in the inverse-search architecture is matched to the previously
frozen I1-strong and I2AFS controls except the public information/loss:

- same frozen public-derived parameter domains,
- same 64 scrambled-Sobol initial points,
- same 192 TPE adaptive trials,
- same sampler seeds,
- same N=25 search CRN bank,
- same top-24 shortlist,
- same fresh N=100 common rescore bank,
- same top-3/provider equal-weight M2 support.

The objective is the frozen I2b empirical bivariate energy V-statistic over
the frozen public temporal-pair representation.  No graph result, WB result,
private Phase-5 provider ledger, or hidden provider parameter is read.
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
    git_head,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from run_m1_provider_lift_v2 import _load_optuna  # noqa:E402
from run_phase5_m2_reconstruction_v2 import (  # noqa:E402
    _bounds,
    _domain_row,
    _load_public_card,
)
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import (  # noqa:E402
    _sobol_initial_points,
)
from run_phase6_i2a_genuine_reconstruction_p4_v1 import (  # noqa:E402
    _simulate_samples,
)
from i2b_energy_loss_v1 import (  # noqa:E402
    PreparedI2bTarget,
    prepare_public_target,
    score_candidate_windows,
)

CFG=HERE/"config_phase6_i2b_energy_reconstruction_p4_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
REP_CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
LOSS_FREEZE=HERE/"PHASE6_I2B_ENERGY_LOSS_FREEZE_2026-10-09.md"
PUBLIC_ROOT=HERE/"results"/"22_i2b_public_representation"
ROOT=HERE/"results"/"24_i2b_energy_reconstruction_p4"

WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I2B_ENERGY_RECONSTRUCTION_P4_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
EXPECTED_REP="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
LAGS=(20,30,40,50,75,100,150,200)
STRIDE=10
START_PHASE=5
HORIZON_END=240


def _seed_tuple(start:int,end_inclusive:int,n:int)->tuple[int,...]:
    out=tuple(range(int(start),int(end_inclusive)+1))
    if len(out)!=int(n):
        raise RuntimeError("invalid frozen seed block")
    return out


def _assert_contracts()->dict[str,Any]:
    cfg=read_json(CFG)
    sampling=read_json(SAMPLING_CFG)
    rep=read_json(REP_CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected I2b reconstruction config status")
    if sampling.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected I2b temporal-sampling status")
    if rep.get("status")!=EXPECTED_REP:
        raise RuntimeError("unexpected I2b public-representation status")
    if tuple(int(x) for x in sampling["temporal_sampling"]["lags_s"])!=LAGS:
        raise RuntimeError("frozen I2b lag set changed")
    if int(sampling["temporal_sampling"]["stride_s"])!=STRIDE:
        raise RuntimeError("frozen I2b stride changed")
    if int(sampling["temporal_sampling"]["canonical_start_phase_s"])!=START_PHASE:
        raise RuntimeError("frozen I2b start phase changed")
    if not LOSS_FREEZE.is_file():
        raise FileNotFoundError(LOSS_FREEZE)
    return cfg


def _load_i2b_target(provider:str)->tuple[dict[str,Any],PreparedI2bTarget,Path]:
    metadata,_,_=_load_public_card(WORLD,provider)
    pair_path=PUBLIC_ROOT/WORLD/provider/"i2b_public_temporal_pairs.csv"
    manifest_path=PUBLIC_ROOT/WORLD/provider/"i2b_public_representation_manifest.json"
    if not pair_path.is_file():
        raise FileNotFoundError(pair_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest=read_json(manifest_path)
    if manifest.get("status")!="PHASE6_I2B_PUBLIC_PROVIDER_COMPLETE":
        raise RuntimeError(f"{provider}: public I2b provider manifest is not complete")
    if sha256_file(pair_path)!=str(manifest["output_hashes_sha256"]["temporal_pairs"]):
        raise RuntimeError(f"{provider}: public I2b pair hash mismatch")
    pairs=pd.read_csv(pair_path)
    if set(pairs["provider_world_id"].astype(str))!={WORLD}:
        raise RuntimeError(f"{provider}: public I2b world mismatch")
    if set(pairs["provider_id"].astype(str))!={provider}:
        raise RuntimeError(f"{provider}: public I2b provider mismatch")
    target=prepare_public_target(pairs)
    return metadata,target,pair_path


def _candidate_windows_from_sample_groups(
    sample_groups:dict[tuple[str,float],np.ndarray],
)->dict[tuple[str,float,float,float],np.ndarray]:
    regions=sorted({str(k[0]) for k in sample_groups})
    horizons={float(k[1]) for k in sample_groups}
    if len(regions)!=5 or horizons!={float(x) for x in range(5,241,5)}:
        raise RuntimeError("candidate compliance sample support changed")
    sample_sizes={len(np.asarray(v)) for v in sample_groups.values()}
    if len(sample_sizes)!=1:
        raise RuntimeError("candidate compliance groups have inconsistent N")
    n=next(iter(sample_sizes))
    if n<1:
        raise RuntimeError("candidate compliance groups are empty")

    out={}
    for rid in regions:
        for lag in LAGS:
            start=START_PHASE
            while start+lag<=HORIZON_END:
                end=start+lag
                a=np.asarray(sample_groups[(rid,float(start))],dtype=float)
                b=np.asarray(sample_groups[(rid,float(end))],dtype=float)
                if len(a)!=n or len(b)!=n:
                    raise RuntimeError("candidate temporal pair sample count mismatch")
                # _simulate_samples appends every H in the same seed order, so
                # row index is the private same-trajectory correspondence.
                out[(rid,float(lag),float(start),float(end))]=np.column_stack((a,b))
                start+=STRIDE
    if len(out)!=630:
        raise RuntimeError(f"expected 630 candidate temporal windows, found {len(out)}")
    return out


def _score_i2b(
    *,
    metadata:dict[str,Any],
    target:PreparedI2bTarget,
    mean_service_time:float,
    cost_rate:float,
    service_cv:float,
    seeds:tuple[int,...],
)->tuple[float,pd.DataFrame]:
    samples=_simulate_samples(
        metadata=metadata,
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
        seeds=seeds,
    )
    windows=_candidate_windows_from_sample_groups(samples)
    overall,by_lag,_=score_candidate_windows(target,windows)
    if not math.isfinite(overall) or overall<0.0:
        raise RuntimeError("nonfinite/negative I2b energy score")
    return float(overall),by_lag


def _lag_attrs(by_lag:pd.DataFrame)->dict[str,float]:
    out={}
    for rec in by_lag.itertuples(index=False):
        lag=int(round(float(rec.lag_s)))
        out[f"lag_{lag}_mean_energy"]=float(rec.mean_energy_vstat)
    return out


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
        row={
            "trial_number":int(t.number),
            "search_i2b_energy_vstat":float(t.value),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        }
        for lag in LAGS:
            key=f"lag_{lag}_mean_energy"
            row[f"search_{key}"]=float(t.user_attrs[key])
        rows.append(row)
    return pd.DataFrame(rows)


def _run_search(
    *,
    provider:str,
    metadata:dict[str,Any],
    target:PreparedI2bTarget,
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
    study_name=f"phase6_i2benergy_{WORLD}_{provider}_v1"
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

    failed=sum(t.state==optuna.trial.TrialState.FAIL for t in study.trials)
    if failed:
        raise RuntimeError(f"{provider}: existing search contains {failed} failed trials")

    if len(study.trials)==0:
        initial=_sobol_initial_points(
            sobol_n,int(search["sobol_seed"]),bounds
        )
        for params in initial:
            study.enqueue_trial(params)
        print(
            f"I2B SEARCH {WORLD}/{provider}: enqueued {sobol_n} matched Sobol trials",
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
        score,by_lag=_score_i2b(
            metadata=metadata,
            target=target,
            mean_service_time=mu,
            cost_rate=cost,
            service_cv=cv,
            seeds=search_seeds,
        )
        for k,v in _lag_attrs(by_lag).items():
            trial.set_user_attr(k,float(v))
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
                f"I2B SEARCH {WORLD}/{provider} {phase} "
                f"{complete}/{total_trials} best_E={best[0]:.6g} "
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
        ["search_i2b_energy_vstat","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    trials.insert(0,"search_rank",np.arange(1,len(trials)+1,dtype=int))
    trials.to_csv(out/"search_trials_256.csv",index=False)
    return trials


def _rescore_shortlist(
    *,
    provider:str,
    metadata:dict[str,Any],
    target:PreparedI2bTarget,
    trials:pd.DataFrame,
    cfg:dict[str,Any],
    out:Path,
)->pd.DataFrame:
    search=cfg["search"]
    rescore=cfg["common_rescore"]
    shortlist_n=int(search["rescore_shortlist_count"])
    shortlist=trials.head(shortlist_n).copy()
    if len(shortlist)!=24:
        raise RuntimeError("I2b frozen shortlist is not 24")

    seeds=_seed_tuple(
        rescore["seed_start"],
        rescore["seed_end_inclusive"],
        rescore["n"],
    )
    cp_root=out/"rescore_checkpoints"
    cp_root.mkdir(parents=True,exist_ok=True)

    rows=[]
    lag_rows=[]
    for ordinal,rec in enumerate(shortlist.itertuples(index=False),start=1):
        trial_number=int(rec.trial_number)
        cp=cp_root/f"trial_{trial_number:04d}.json"
        lag_cp=cp_root/f"trial_{trial_number:04d}_by_lag.csv"

        if cp.is_file() and lag_cp.is_file():
            row=read_json(cp)
            if (
                row.get("status")!="PHASE6_I2B_ENERGY_RESCORE_COMPLETE"
                or int(row["trial_number"])!=trial_number
            ):
                raise RuntimeError(f"{provider}: incompatible I2b rescore checkpoint")
            one_lag=pd.read_csv(lag_cp)
            if len(one_lag)!=8:
                raise RuntimeError(f"{provider}: incompatible I2b lag checkpoint")
            rows.append(row)
            lag_rows.append(one_lag)
            print(
                f"I2B RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
                f"trial={trial_number} E={float(row['rescore_i2b_energy_vstat']):.6g} [cached]",
                flush=True,
            )
            continue

        score,by_lag=_score_i2b(
            metadata=metadata,
            target=target,
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            seeds=seeds,
        )
        candidate_id=f"P4_{provider}_I2B_T{trial_number:03d}"
        row={
            "status":"PHASE6_I2B_ENERGY_RESCORE_COMPLETE",
            "provider_world_id":WORLD,
            "provider_id":provider,
            "candidate_id":candidate_id,
            "trial_number":trial_number,
            "search_rank":int(rec.search_rank),
            "search_i2b_energy_vstat":float(rec.search_i2b_energy_vstat),
            "rescore_i2b_energy_vstat":float(score),
            "mean_service_time":float(rec.mean_service_time),
            "cost_rate":float(rec.cost_rate),
            "service_cv":float(rec.service_cv),
            "rescore_seed_start":int(seeds[0]),
            "rescore_seed_end_inclusive":int(seeds[-1]),
            "rescore_n":len(seeds),
        }
        for k,v in _lag_attrs(by_lag).items():
            row[f"rescore_{k}"]=float(v)
        write_json(cp,row)

        lag_out=by_lag.copy()
        lag_out.insert(0,"candidate_id",candidate_id)
        lag_out.insert(1,"trial_number",trial_number)
        lag_out.to_csv(lag_cp,index=False)

        rows.append(row)
        lag_rows.append(lag_out)
        print(
            f"I2B RESCORE {WORLD}/{provider} {ordinal}/{shortlist_n} "
            f"trial={trial_number} E={score:.6g}",
            flush=True,
        )

    scores=pd.DataFrame(rows).sort_values(
        ["rescore_i2b_energy_vstat","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    scores.insert(0,"i2b_quality_rank",np.arange(1,len(scores)+1,dtype=int))
    scores.to_csv(out/"rescore_top24.csv",index=False)

    lag_detail=pd.concat(lag_rows,ignore_index=True)
    lag_detail.to_csv(out/"rescore_top24_by_lag.csv",index=False)
    return scores


def run_provider(provider:str)->dict[str,Any]:
    cfg=_assert_contracts()

    out=ROOT/provider
    out.mkdir(parents=True,exist_ok=True)
    manifest_path=out/"provider_reconstruction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_I2B_ENERGY_PROVIDER_RECONSTRUCTION_COMPLETE":
            print(f"I2B RECON {WORLD}/{provider} cached",flush=True)
            return {
                "provider_id":provider,
                "best_candidate_id":str(m["m2_candidate_ids"][0]),
                "m2_candidate_ids":";".join(m["m2_candidate_ids"]),
                "wall_seconds":0.0,
                "manifest_sha256":sha256_file(manifest_path),
            }
        raise RuntimeError(f"{provider}: incompatible existing provider manifest")

    started=time.perf_counter()
    metadata,target,pair_path=_load_i2b_target(provider)
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
    m2.insert(0,"method_id","I2B_M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"i2b_m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    card=PHASE5/"results"/"01_i1"/WORLD/"public"/provider/"card.json"
    public_manifest=PUBLIC_ROOT/WORLD/provider/"i2b_public_representation_manifest.json"
    manifest={
        "status":"PHASE6_I2B_ENERGY_PROVIDER_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "code_commit":git_head(),
        "contracts_sha256":{
            "reconstruction_config":sha256_file(CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "public_representation_config":sha256_file(REP_CFG),
            "loss_freeze":sha256_file(LOSS_FREEZE),
        },
        "public_card_sha256":sha256_file(card),
        "public_i2b_temporal_pairs_sha256":sha256_file(pair_path),
        "public_i2b_provider_manifest_sha256":sha256_file(public_manifest),
        "loss":"empirical_energy_vstat_2d_equal_lag_equal_window",
        "total_search_trials":int(cfg["search"]["total_trials"]),
        "sobol_initial_trials":int(cfg["search"]["sobol_initial_trials"]),
        "tpe_adaptive_trials":int(cfg["search"]["tpe_adaptive_trials"]),
        "search_n":int(cfg["search"]["search_n"]),
        "rescore_shortlist_count":int(cfg["search"]["rescore_shortlist_count"]),
        "rescore_n":int(cfg["common_rescore"]["n"]),
        "selection_metric":"rescore_i2b_energy_vstat",
        "m2_candidate_ids":m2["candidate_id"].astype(str).tolist(),
        "graph_prediction_used":False,
        "graph_wb_used":False,
        "final_wb_used":False,
        "private_i1_ledger_used":False,
        "hidden_provider_parameters_used":False,
        "outputs":{
            "search_trials":str(out/"search_trials_256.csv"),
            "rescore_top24":str(out/"rescore_top24.csv"),
            "rescore_top24_by_lag":str(out/"rescore_top24_by_lag.csv"),
            "m2_provider_models":str(m2_path),
        },
        "output_hashes_sha256":{
            "search_trials":sha256_file(out/"search_trials_256.csv"),
            "rescore_top24":sha256_file(out/"rescore_top24.csv"),
            "rescore_top24_by_lag":sha256_file(out/"rescore_top24_by_lag.csv"),
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
        path=ROOT/provider/"i2b_m2_provider_models.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        t=pd.read_csv(path)
        if len(t)!=3:
            raise RuntimeError(f"{provider}: I2b M2 provider support !=3")
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
        raise RuntimeError("I2b M2 joint support !=27")

    support_path=ROOT/"m2_joint_support_27.csv"
    support.to_csv(support_path,index=False)

    summary=pd.DataFrame(provider_rows).sort_values(
        "provider_id",kind="mergesort"
    ).reset_index(drop=True)
    summary_path=ROOT/"provider_reconstruction_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest={
        "status":"PHASE6_I2B_ENERGY_P4_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_count":3,
        "m2_joint_models":27,
        "matched_i1strong_i2afs_search_architecture":True,
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
    path=ROOT/"p4_i2b_energy_reconstruction_manifest.json"
    write_json(path,manifest)

    print("\nPHASE6_I2B_ENERGY_P4_RECONSTRUCTION_PASS")
    print(summary.to_string(index=False))
    for provider in PROVIDERS:
        print(f"\n{provider} TOP3")
        print(
            tables[provider][[
                "candidate_id","trial_number",
                "rescore_i2b_energy_vstat",
                "mean_service_time","cost_rate","service_cv",
            ]].to_string(index=False)
        )
    print("\njoint_models 27")
    print("manifest",path)
    return path


def main():
    p=argparse.ArgumentParser(
        description="Matched I2b empirical-energy reconstruction for P4"
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
                        f"I2b energy reconstruction failed for {provider}"
                    ) from exc
    _freeze_world(rows)


if __name__=="__main__":
    main()
