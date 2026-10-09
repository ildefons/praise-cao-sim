"""Matched Phase-6 I2b-v4 hierarchical variability-weighted reconstruction for P4.

The frozen objective preserves equal total mass across the five SLA regions
and eight temporal lags, while redistributing weight only across start
horizons within each fixed (region, lag) block according to target temporal
public aggregate mean within-segment excursion V=mean_j(max_t c_j(t)-min_t c_j(t)).

All search architecture, parameter domains, seeds, shortlist and M2 support
sizes are matched to the existing controls. P4/G_SEQPAR informed this
weighting design and is therefore development-only for any later graph test.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import sys
import time
import zipfile
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
from run_m1_provider_lift_v2 import _load_optuna  # noqa:E402
from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row  # noqa:E402
from run_phase6_i2a_fullspectrum_reconstruction_p4_v1 import _sobol_initial_points  # noqa:E402
from run_phase6_i2a_genuine_reconstruction_p4_v1 import _simulate_samples  # noqa:E402
from run_phase6_i2b_energy_reconstruction_p4_v1 import (  # noqa:E402
    _load_i2b_target,
    _candidate_windows_from_sample_groups,
)
from i2b_energy_loss_v1 import score_candidate_windows  # noqa:E402

CFG=HERE/"config_phase6_i2b_v4_mean_range_reconstruction_p4_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
REP_CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
BASE_LOSS_FREEZE=HERE/"PHASE6_I2B_ENERGY_LOSS_FREEZE_2026-10-09.md"
HIER_LOSS_FREEZE=HERE/"PHASE6_I2B_V4_MEAN_RANGE_LOSS_FREEZE_2026-10-10.md"
HIER_AUDIT=HERE/"results"/"35_i2b_v4_mean_range_feasibility"/"i2b_v4_range_feasibility_manifest.json"
V4_WINDOWS=HERE/"results"/"35_i2b_v4_mean_range_feasibility"/"v3_v4_window_weights.csv"
ROOT=HERE/"results"/"36_i2b_v4_mean_range_reconstruction_p4"

WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I2B_V4_MEAN_RANGE_RECONSTRUCTION_P4_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
EXPECTED_REP="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
TOL=1e-12


def _seed_tuple(start:int,end_inclusive:int,n:int)->tuple[int,...]:
    out=tuple(range(int(start),int(end_inclusive)+1))
    if len(out)!=int(n):
        raise RuntimeError("invalid frozen seed block")
    return out


def _assert_contracts()->dict[str,Any]:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected I2b-v4 hierarchical reconstruction config status")
    sampling=read_json(SAMPLING_CFG)
    rep=read_json(REP_CFG)
    if sampling.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected I2b temporal sampling status")
    if rep.get("status")!=EXPECTED_REP:
        raise RuntimeError("unexpected I2b public representation status")
    for p in (BASE_LOSS_FREEZE,HIER_LOSS_FREEZE,HIER_AUDIT,V4_WINDOWS):
        if not p.is_file():
            raise FileNotFoundError(p)
    return cfg


def _target_weights(target,provider:str)->dict[tuple[str,float,float,float],float]:
    """Use ONLY the newly released, target-derived, aggregate mean-range weights."""
    audit=read_json(HIER_AUDIT)
    if audit.get("status")!="PHASE6_I2B_V4_MEAN_RANGE_FEASIBILITY_COMPLETE":
        raise RuntimeError("I2b-v4 aggregate publicization audit incomplete")
    df=pd.read_csv(V4_WINDOWS)
    df=df[(df["provider_world_id"]==WORLD)&(df["provider_id"]==provider)].copy()
    if len(df)!=630 or df["region_id"].nunique()!=5:
        raise RuntimeError("I2b-v4 public aggregate support mismatch")
    weights={}
    for r in df.itertuples(index=False):
        key=(str(r.region_id),float(r.lag_s),float(r.start_H),float(r.end_H))
        if key in weights:
            raise RuntimeError("duplicate v4 weight key")
        weights[key]=float(r.v4_mean_range_weight)
    if set(weights)!=set(target.windows):
        raise RuntimeError("I2b-v4 range weights do not match public endpoint window keys")
    vals=np.array(list(weights.values()),dtype=float)
    if not np.isfinite(vals).all() or (vals<0).any() or abs(vals.sum()-1)>1e-12:
        raise RuntimeError("invalid I2b-v4 weights")
    if any(abs(sum(v for k,v in weights.items() if k[0]==rid)-0.2)>1e-12
           for rid in {k[0] for k in weights}):
        raise RuntimeError("I2b-v4 region masses changed")
    if any(abs(sum(v for k,v in weights.items() if k[1]==lag)-0.125)>1e-12
           for lag in {k[1] for k in weights}):
        raise RuntimeError("I2b-v4 lag masses changed")
    return weights

def _score_weighted(target,weights,candidate_windows):
    _,_,detail=score_candidate_windows(target,candidate_windows)
    rows=[]
    total=0.0
    for rec in detail.itertuples(index=False):
        key=(str(rec.region_id),float(rec.lag_s),float(rec.start_H),float(rec.end_H))
        if key not in weights:
            raise RuntimeError(f"missing frozen target weight for {key}")
        w=float(weights[key])
        e=float(rec.energy_vstat)
        c=w*e
        total+=c
        rows.append({
            "region_id":key[0],
            "lag_s":key[1],
            "start_H":key[2],
            "end_H":key[3],
            "hierarchical_weight":w,
            "energy_vstat":e,
            "weighted_contribution":c,
        })
    d=pd.DataFrame(rows)
    if len(d)!=630:
        raise RuntimeError("I2b-v4 scorer did not produce 630 windows")
    by_lag=(
        d.groupby("lag_s",as_index=False,sort=True)
        .agg(
            window_count=("energy_vstat","size"),
            weight_mass=("hierarchical_weight","sum"),
            weighted_energy_contribution=("weighted_contribution","sum"),
            mean_energy_vstat=("energy_vstat","mean"),
        )
    )
    return float(total),by_lag,d


def _score_params(*,metadata,target,weights,mu,cost,cv,seeds):
    samples=_simulate_samples(
        metadata=metadata,
        mean_service_time=float(mu),
        cost_rate=float(cost),
        service_cv=float(cv),
        seeds=seeds,
    )
    windows=_candidate_windows_from_sample_groups(samples)
    return _score_weighted(target,weights,windows)


def _study_rows(study,optuna)->pd.DataFrame:
    rows=[]
    for t in study.trials:
        if t.state!=optuna.trial.TrialState.COMPLETE:
            continue
        if t.value is None:
            raise RuntimeError("complete trial missing value")
        rows.append({
            "trial_number":int(t.number),
            "search_i2b_v4_mean_range_energy":float(t.value),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        })
    return pd.DataFrame(rows)


def _run_search(*,provider,metadata,target,weights,bounds,cfg,out):
    s=cfg["search"]
    total=int(s["total_trials"])
    sobol_n=int(s["sobol_initial_trials"])
    if sobol_n+int(s["tpe_adaptive_trials"])!=total:
        raise RuntimeError("frozen trial counts changed")
    seeds=_seed_tuple(s["search_seed_start"],s["search_seed_end_inclusive"],s["search_n"])

    optuna=_load_optuna()
    db=(out/"optuna_search.sqlite3").resolve()
    sampler=optuna.samplers.TPESampler(
        seed=int(s["tpe_sampler_seeds"][provider]),
        n_startup_trials=0,
    )
    study=optuna.create_study(
        direction="minimize",
        sampler=sampler,
        storage=f"sqlite:///{db}",
        study_name=f"phase6_i2bv4_{WORLD}_{provider}_v1",
        load_if_exists=True,
    )
    failed=sum(t.state==optuna.trial.TrialState.FAIL for t in study.trials)
    if failed:
        raise RuntimeError(f"{provider}: existing study has {failed} failed trials")

    if len(study.trials)==0:
        for params in _sobol_initial_points(sobol_n,int(s["sobol_seed"]),bounds):
            study.enqueue_trial(params)
        print(f"I2B-V4 SEARCH {WORLD}/{provider}: enqueued {sobol_n} matched Sobol trials",flush=True)

    complete_before=sum(t.state==optuna.trial.TrialState.COMPLETE for t in study.trials)
    if complete_before>total:
        raise RuntimeError(f"{provider}: too many existing complete trials")

    started=time.perf_counter()
    best=[float("inf")]

    def objective(trial):
        mu=trial.suggest_float(
            "mean_service_time",bounds.mean_service_time_lower,bounds.mean_service_time_upper,log=True
        )
        cost=trial.suggest_float(
            "cost_rate",bounds.cost_rate_lower,bounds.cost_rate_upper,log=True
        )
        cv=trial.suggest_float(
            "service_cv",bounds.service_cv_lower,bounds.service_cv_upper,log=False
        )
        score,_,_=_score_params(
            metadata=metadata,target=target,weights=weights,
            mu=mu,cost=cost,cv=cv,seeds=seeds,
        )
        return score

    def progress(study_,trial):
        if trial.value is None:
            return
        complete=sum(t.state==optuna.trial.TrialState.COMPLETE for t in study_.trials)
        value=float(trial.value)
        improved=value<best[0]-1e-15
        if improved:
            best[0]=value
        if improved or complete%10==0 or complete==total:
            elapsed=time.perf_counter()-started
            newly=max(1,complete-complete_before)
            eta=(elapsed/newly)*max(0,total-complete)
            phase="SOBOL" if int(trial.number)<sobol_n else "TPE"
            print(
                f"I2B-V4 SEARCH {WORLD}/{provider} {phase} "
                f"{complete}/{total} best={best[0]:.6g} "
                f"elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m",
                flush=True,
            )

    remaining=total-complete_before
    if remaining>0:
        study.optimize(objective,n_trials=remaining,callbacks=[progress],show_progress_bar=False)

    trials=_study_rows(study,optuna)
    if len(trials)!=total:
        raise RuntimeError(f"{provider}: expected {total} complete trials, found {len(trials)}")
    trials=trials.sort_values(
        ["search_i2b_v4_mean_range_energy","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    trials.insert(0,"search_rank",np.arange(1,total+1,dtype=int))
    trials.to_csv(out/"search_trials_256.csv",index=False)
    return trials


def _rescore(*,provider,metadata,target,weights,trials,cfg,out):
    s=cfg["search"]; r=cfg["common_rescore"]
    shortlist=trials.head(int(s["rescore_shortlist_count"])).copy()
    if len(shortlist)!=24:
        raise RuntimeError("frozen shortlist !=24")
    seeds=_seed_tuple(r["seed_start"],r["seed_end_inclusive"],r["n"])
    cp_root=out/"rescore_checkpoints"; cp_root.mkdir(parents=True,exist_ok=True)
    rows=[]; lag_frames=[]
    for ordinal,rec in enumerate(shortlist.itertuples(index=False),start=1):
        tnum=int(rec.trial_number)
        cp=cp_root/f"trial_{tnum:04d}.json"
        lcp=cp_root/f"trial_{tnum:04d}_by_lag.csv"
        if cp.is_file() and lcp.is_file():
            row=read_json(cp)
            if row.get("status")!="PHASE6_I2B_V4_MEAN_RANGE_RESCORE_COMPLETE":
                raise RuntimeError(f"{provider}: incompatible rescore checkpoint")
            rows.append(row); lag_frames.append(pd.read_csv(lcp))
            print(
                f"I2B-V4 RESCORE {WORLD}/{provider} {ordinal}/24 "
                f"trial={tnum} E={float(row['rescore_i2b_v4_mean_range_energy']):.6g} [cached]",
                flush=True,
            )
            continue

        score,by_lag,_=_score_params(
            metadata=metadata,target=target,weights=weights,
            mu=float(rec.mean_service_time),cost=float(rec.cost_rate),
            cv=float(rec.service_cv),seeds=seeds,
        )
        cid=f"P4_{provider}_I2BV4_T{tnum:03d}"
        row={
            "status":"PHASE6_I2B_V4_MEAN_RANGE_RESCORE_COMPLETE",
            "provider_world_id":WORLD,
            "provider_id":provider,
            "candidate_id":cid,
            "trial_number":tnum,
            "search_rank":int(rec.search_rank),
            "search_i2b_v4_mean_range_energy":float(rec.search_i2b_v4_mean_range_energy),
            "rescore_i2b_v4_mean_range_energy":float(score),
            "mean_service_time":float(rec.mean_service_time),
            "cost_rate":float(rec.cost_rate),
            "service_cv":float(rec.service_cv),
            "rescore_seed_start":int(seeds[0]),
            "rescore_seed_end_inclusive":int(seeds[-1]),
            "rescore_n":len(seeds),
        }
        write_json(cp,row)
        lo=by_lag.copy()
        lo.insert(0,"candidate_id",cid)
        lo.insert(1,"trial_number",tnum)
        lo.to_csv(lcp,index=False)
        rows.append(row); lag_frames.append(lo)
        print(
            f"I2B-V4 RESCORE {WORLD}/{provider} {ordinal}/24 "
            f"trial={tnum} E={score:.6g}",
            flush=True,
        )

    scores=pd.DataFrame(rows).sort_values(
        ["rescore_i2b_v4_mean_range_energy","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    scores.insert(0,"i2bv4_quality_rank",np.arange(1,len(scores)+1,dtype=int))
    scores.to_csv(out/"rescore_top24.csv",index=False)
    pd.concat(lag_frames,ignore_index=True).to_csv(out/"rescore_top24_by_lag.csv",index=False)
    return scores


def run_provider(provider:str)->dict[str,Any]:
    cfg=_assert_contracts()
    out=ROOT/provider; out.mkdir(parents=True,exist_ok=True)
    mp=out/"provider_reconstruction_manifest.json"
    if mp.is_file():
        m=read_json(mp)
        if m.get("status")=="PHASE6_I2B_V4_MEAN_RANGE_PROVIDER_RECONSTRUCTION_COMPLETE":
            print(f"I2B-V4 RECON {WORLD}/{provider} cached",flush=True)
            return {
                "provider_id":provider,
                "best_candidate_id":str(m["m2_candidate_ids"][0]),
                "m2_candidate_ids":";".join(m["m2_candidate_ids"]),
                "wall_seconds":0.0,
                "manifest_sha256":sha256_file(mp),
            }
        raise RuntimeError(f"{provider}: incompatible existing manifest")

    started=time.perf_counter()
    metadata,target,pair_path=_load_i2b_target(provider)
    weights=_target_weights(target,provider)
    vals=np.asarray(list(weights.values()),dtype=float)
    neff=1.0/float(np.sum(vals*vals))
    bounds=_bounds(_domain_row(WORLD,provider))

    trials=_run_search(
        provider=provider,metadata=metadata,target=target,weights=weights,
        bounds=bounds,cfg=cfg,out=out,
    )
    scores=_rescore(
        provider=provider,metadata=metadata,target=target,weights=weights,
        trials=trials,cfg=cfg,out=out,
    )

    m2=scores.head(3).copy()
    m2.insert(0,"method_id","I2BV4_M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"i2bv4_m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    manifest={
        "status":"PHASE6_I2B_V4_MEAN_RANGE_PROVIDER_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "development_evidence":True,
        "development_note":"Weighting design informed by P4/G_SEQPAR; reconstruction itself reads no graph data.",
        "code_commit":git_head(),
        "contracts_sha256":{
            "reconstruction_config":sha256_file(CFG),
            "temporal_sampling":sha256_file(SAMPLING_CFG),
            "public_representation":sha256_file(REP_CFG),
            "base_loss_freeze":sha256_file(BASE_LOSS_FREEZE),
            "hierarchical_loss_freeze":sha256_file(HIER_LOSS_FREEZE),
            "hierarchical_weight_audit":sha256_file(HIER_AUDIT),
        },
        "public_i2b_temporal_pairs_sha256":sha256_file(pair_path),
        "weight_definition":"equal region 1/5 x equal lag 1/8 x target V-normalized starts within each region-lag block",
        "max_window_weight":float(vals.max()),
        "effective_window_count":float(neff),
        "loss":"sum hierarchical_weight * empirical_energy_vstat_2d",
        "total_search_trials":int(cfg["search"]["total_trials"]),
        "search_n":int(cfg["search"]["search_n"]),
        "rescore_shortlist_count":int(cfg["search"]["rescore_shortlist_count"]),
        "rescore_n":int(cfg["common_rescore"]["n"]),
        "selection_metric":"rescore_i2b_v4_mean_range_energy",
        "m2_candidate_ids":m2["candidate_id"].astype(str).tolist(),
        "graph_prediction_used":False,
        "graph_wb_used":False,
        "final_wb_used":False,
        "private_i1_ledger_used":False,
        "new_public_mean_range_aggregate_used_for_weights":True,
        "new_public_mean_range_sha256":sha256_file(V4_WINDOWS),
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
    write_json(mp,manifest)
    return {
        "provider_id":provider,
        "best_candidate_id":str(m2.iloc[0]["candidate_id"]),
        "m2_candidate_ids":";".join(m2["candidate_id"].astype(str)),
        "wall_seconds":float(manifest["wall_seconds"]),
        "manifest_sha256":sha256_file(mp),
    }


def _freeze_world(provider_rows):
    tables={}
    for p in PROVIDERS:
        t=pd.read_csv(ROOT/p/"i2bv4_m2_provider_models.csv")
        if len(t)!=3:
            raise RuntimeError(f"{p}: I2b-v4 hierarchical M2 support !=3")
        tables[p]=t
    rows=[]; rank=0
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
    support_path=ROOT/"m2_joint_support_27.csv"; support.to_csv(support_path,index=False)
    summary=pd.DataFrame(provider_rows).sort_values("provider_id").reset_index(drop=True)
    summary_path=ROOT/"provider_reconstruction_summary.csv"; summary.to_csv(summary_path,index=False)

    manifest={
        "status":"PHASE6_I2B_V4_MEAN_RANGE_P4_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_count":3,
        "m2_joint_models":27,
        "matched_search_architecture":True,
        "provider_manifest_sha256":{
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
    path=ROOT/"p4_i2b_v4_mean_range_reconstruction_manifest.json"
    write_json(path,manifest)

    bundle=ROOT/"i2b_v4_mean_range_reconstruction_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.write(summary_path,arcname=summary_path.name)
        z.write(support_path,arcname=support_path.name)
        z.write(path,arcname=path.name)
        for provider in PROVIDERS:
            for name in (
                "i2bv4_m2_provider_models.csv",
                "rescore_top24.csv",
                "rescore_top24_by_lag.csv",
                "provider_reconstruction_manifest.json",
            ):
                p=ROOT/provider/name
                z.write(p,arcname=f"{provider}/{name}")

    print("\nPHASE6_I2B_V4_MEAN_RANGE_P4_RECONSTRUCTION_PASS")
    print(summary.to_string(index=False))
    for p in PROVIDERS:
        print(f"\n{p} TOP3")
        print(
            tables[p][[
                "candidate_id","trial_number","rescore_i2b_v4_mean_range_energy",
                "mean_service_time","cost_rate","service_cv",
            ]].to_string(index=False)
        )
    print("\njoint_models 27")
    print("manifest",path)
    print("UPLOAD BUNDLE",bundle)
    return path


def main():
    p=argparse.ArgumentParser(description="Matched I2b-v4 hierarchical variability-weighted reconstruction for P4")
    p.add_argument("--workers",type=int,default=3)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    rows=[]
    if args.workers==1:
        for provider in PROVIDERS:
            rows.append(run_provider(provider))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers,3)) as pool:
            futures={pool.submit(run_provider,p):p for p in PROVIDERS}
            for fut in concurrent.futures.as_completed(futures):
                pvd=futures[fut]
                try:
                    rows.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"I2b-v4 reconstruction failed for {pvd}") from exc
    _freeze_world(rows)


if __name__=="__main__":
    main()