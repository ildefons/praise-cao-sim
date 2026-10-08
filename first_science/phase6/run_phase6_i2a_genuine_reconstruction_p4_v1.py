"""Genuine Phase-6 I2a provider reconstruction for P4.

Unlike the earlier diagnostic re-ranking experiment, this runner uses I2a-full
as the objective inside each TPE inverse-reconstruction search. It reads only
the public I2a empirical CDF, public card metadata, frozen public-derived search
domains, and frozen candidate-simulation seed banks. It never reads graph WB,
final WB, hidden provider parameters, or the private I1 provider ledger.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE1=HERE.parent/"phase1"
PHASE3=HERE.parent/"phase3"
PHASE5=HERE.parent/"phase5"
for p in (PHASE1,PHASE3,PHASE5):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from sla_compliance_analysis import (  # noqa:E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_trajectory_cumulative_sla_curve,
)
from m1_single_provider_simulator import (  # noqa:E402
    SingleProviderSurrogateParameters,
    execute_one_single_provider_trajectory,
)
from run_m1_provider_lift_v2 import _load_optuna  # noqa:E402
from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row, _load_public_card  # noqa:E402
from phase5_runtime_v2 import (  # noqa:E402
    git_head, read_json, sha256_file, utc_now_iso, write_json,
)

CFG=HERE/"config_phase6_i2a_genuine_reconstruction_p4_v1.json"
SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
I2A_ROOT=HERE/"results"/"01_i2a_marginal_audit"/"P4"
ROOT=HERE/"results"/"04_i2a_genuine_reconstruction_p4"
WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_GENUINE_I2A_RECONSTRUCTION_P4_V1"
EXPECTED_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3"
TOL=1e-12


def empirical_w1(a:Iterable[float],b:Iterable[float])->float:
    """Exact W1 between two equally weighted 1D empirical distributions."""
    aa=np.sort(np.asarray(tuple(a),dtype=float))
    bb=np.sort(np.asarray(tuple(b),dtype=float))
    if len(aa)==0 or len(bb)==0:
        raise ValueError("empirical W1 requires two non-empty samples")
    x=np.sort(np.concatenate([aa,bb]))
    if len(x)<2:
        return 0.0
    dx=np.diff(x)
    fa=np.searchsorted(aa,x[:-1],side="right")/float(len(aa))
    fb=np.searchsorted(bb,x[:-1],side="right")/float(len(bb))
    return float(np.sum(np.abs(fa-fb)*dx))


def _seed_tuple(block:dict[str,Any])->tuple[int,...]:
    start=int(block["start"]); end=int(block["end_inclusive"]); n=int(block["n"])
    out=tuple(range(start,end+1))
    if len(out)!=n:
        raise RuntimeError("invalid frozen seed block")
    return out


def _regions(metadata:dict[str,Any])->list[dict[str,Any]]:
    rows=[dict(x) for x in metadata["rho_conditioned_regions"]]
    required={"region_id","region_rho","l_max","c_max","q_min"}
    if len(rows)!=5:
        raise RuntimeError("expected five frozen regions")
    for row in rows:
        missing=required.difference(row)
        if missing:
            raise RuntimeError(f"region metadata missing {sorted(missing)}")
    return sorted(rows,key=lambda r:(float(r["region_rho"]),str(r["region_id"])))


def _horizons(metadata:dict[str,Any])->tuple[float,...]:
    hs=tuple(sorted(float(x) for x in metadata["supported_horizons"] if float(x)>0.0))
    if len(hs)!=48 or hs[0]!=5.0 or hs[-1]!=240.0:
        raise RuntimeError("unexpected positive horizon grid")
    return hs


def _load_target(provider:str)->tuple[dict[str,Any],pd.DataFrame,dict[tuple[str,float],np.ndarray]]:
    metadata,_,_= _load_public_card(WORLD,provider)
    path=I2A_ROOT/provider/"i2a_public_empirical_cdf.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    target=pd.read_csv(path)
    required={"provider_id","region_id","region_rho","H","sample_rank","compliance_fraction"}
    missing=required.difference(target.columns)
    if missing:
        raise RuntimeError(f"{provider}: public I2a missing {sorted(missing)}")
    if set(target["provider_id"].astype(str))!={provider}:
        raise RuntimeError(f"{provider}: public I2a provider mismatch")
    groups={}
    for (rid,H),g in target.groupby(["region_id","H"],sort=True):
        vals=np.sort(g["compliance_fraction"].astype(float).to_numpy())
        if len(vals)!=100:
            raise RuntimeError(f"{provider}/{rid}/{H}: target N !=100")
        groups[(str(rid),float(H))]=vals
    if len(groups)!=5*48:
        raise RuntimeError(f"{provider}: expected 240 I2a groups, found {len(groups)}")
    return metadata,target,groups


def _simulate_samples(
    *,
    metadata:dict[str,Any],
    mean_service_time:float,
    cost_rate:float,
    service_cv:float,
    seeds:tuple[int,...],
)->dict[tuple[str,float],np.ndarray]:
    params=SingleProviderSurrogateParameters(
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
    )
    provider=str(metadata["provider_id"])
    workload=dict(metadata["workload_contract"])
    horizons=_horizons(metadata)
    regions=_regions(metadata)
    rows={(str(r["region_id"]),float(H)):[] for r in regions for H in horizons}

    with open(os.devnull,"w",encoding="utf-8") as devnull:
        with contextlib.redirect_stdout(devnull),contextlib.redirect_stderr(devnull):
            for seed in seeds:
                ledger=execute_one_single_provider_trajectory(
                    provider_id=provider,
                    parameters=params,
                    workload_contract=workload,
                    trajectory_seed=int(seed),
                    canonical_ipt=1_000_000.0,
                    execution_fraction=0.5,
                )
                for region in regions:
                    decisions=build_request_sla_decision_table(
                        ledger,
                        latency_threshold=float(region["l_max"]),
                        cost_threshold=float(region["c_max"]),
                        quality_threshold=float(region["q_min"]),
                        stop_time=float(workload["horizon_max"]),
                    )
                    curve=calculate_trajectory_cumulative_sla_curve(
                        decisions,
                        horizons,
                        SlaComplianceDefinition(
                            rho=0.5,
                            accounting_origin=float(workload["accounting_origin"]),
                            zero_decision_compliance=1.0,
                        ),
                    )
                    rid=str(region["region_id"])
                    for rec in curve.itertuples(index=False):
                        rows[(rid,float(rec.horizon))].append(float(rec.compliance_fraction))
    out={k:np.asarray(v,dtype=float) for k,v in rows.items()}
    if set(len(v) for v in out.values())!={len(seeds)}:
        raise RuntimeError("candidate compliance sample count mismatch")
    return out


def _score(
    target:dict[tuple[str,float],np.ndarray],
    candidate:dict[tuple[str,float],np.ndarray],
)->tuple[float,float,float]:
    if set(target)!=set(candidate):
        raise RuntimeError("I2a target/candidate group support mismatch")
    d=np.asarray([empirical_w1(target[k],candidate[k]) for k in sorted(target)],dtype=float)
    return float(d.mean()),float(np.median(d)),float(d.max())


def _fit_one(
    *,
    provider:str,
    fit_index:int,
    metadata:dict[str,Any],
    target:dict[tuple[str,float],np.ndarray],
    bounds,
    sampler_seed:int,
    search_seeds:tuple[int,...],
    out:Path,
    n_trials:int,
    n_startup:int,
)->dict[str,Any]:
    winner_path=out/"winner.json"
    trials_path=out/"trials.csv"
    if winner_path.is_file() and trials_path.is_file():
        w=read_json(winner_path)
        if (
            w.get("status")=="PHASE6_I2A_GENUINE_FIT_WINNER"
            and int(w["fit_index"])==fit_index
            and int(w["sampler_seed"])==sampler_seed
            and int(w["search_seed_start"])==search_seeds[0]
            and int(w["search_seed_end_inclusive"])==search_seeds[-1]
        ):
            return w
        raise RuntimeError(f"{provider}/fit{fit_index}: incompatible existing checkpoint")

    out.mkdir(parents=True,exist_ok=True)
    optuna=_load_optuna()
    sampler=optuna.samplers.TPESampler(seed=int(sampler_seed),n_startup_trials=int(n_startup))
    study=optuna.create_study(direction="minimize",sampler=sampler)
    started=time.perf_counter()
    best=[float("inf")]

    def objective(trial):
        mu=trial.suggest_float(
            "mean_service_time",
            bounds.mean_service_time_lower,bounds.mean_service_time_upper,log=True,
        )
        kappa=trial.suggest_float(
            "cost_rate",bounds.cost_rate_lower,bounds.cost_rate_upper,log=True,
        )
        cv=trial.suggest_float(
            "service_cv",bounds.service_cv_lower,bounds.service_cv_upper,log=False,
        )
        cand=_simulate_samples(
            metadata=metadata,
            mean_service_time=mu,cost_rate=kappa,service_cv=cv,
            seeds=search_seeds,
        )
        mean_w1,median_w1,max_w1=_score(target,cand)
        trial.set_user_attr("median_w1",median_w1)
        trial.set_user_attr("max_w1",max_w1)
        return mean_w1

    def progress(_,trial):
        if trial.value is None:
            return
        done=int(trial.number)+1
        value=float(trial.value)
        improved=value<best[0]-1e-15
        if improved:
            best[0]=value
        if improved or done==1 or done%5==0 or done==n_trials:
            elapsed=time.perf_counter()-started
            eta=(elapsed/done)*(n_trials-done)
            print(
                f"I2A SEARCH P4/{provider} fit {fit_index}/7 "
                f"trial {done}/{n_trials} best_W1={best[0]:.6g} "
                f"elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m",
                flush=True,
            )

    study.optimize(objective,n_trials=n_trials,callbacks=[progress],show_progress_bar=False)

    rows=[]
    for t in study.trials:
        if t.value is None or not t.params:
            continue
        rows.append({
            "trial_number":int(t.number),
            "search_mean_w1":float(t.value),
            "search_median_w1":float(t.user_attrs["median_w1"]),
            "search_max_w1":float(t.user_attrs["max_w1"]),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        })
    trials=pd.DataFrame(rows).sort_values(
        ["search_mean_w1","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    if len(trials)!=n_trials:
        raise RuntimeError(f"{provider}/fit{fit_index}: incomplete TPE trial table")
    trials.to_csv(trials_path,index=False)
    bestrow=trials.iloc[0]
    winner={
        "status":"PHASE6_I2A_GENUINE_FIT_WINNER",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "fit_index":int(fit_index),
        "candidate_id":f"P4_{provider}_I2A_FIT{fit_index}",
        "sampler_seed":int(sampler_seed),
        "search_seed_start":int(search_seeds[0]),
        "search_seed_end_inclusive":int(search_seeds[-1]),
        "search_n":len(search_seeds),
        "n_trials":int(n_trials),
        "n_startup_trials":int(n_startup),
        "selected_trial_number":int(bestrow["trial_number"]),
        "search_mean_w1":float(bestrow["search_mean_w1"]),
        "search_median_w1":float(bestrow["search_median_w1"]),
        "search_max_w1":float(bestrow["search_max_w1"]),
        "mean_service_time":float(bestrow["mean_service_time"]),
        "cost_rate":float(bestrow["cost_rate"]),
        "service_cv":float(bestrow["service_cv"]),
        "trials_sha256":sha256_file(trials_path),
    }
    write_json(winner_path,winner)
    return winner


def run_provider(provider:str,workers_unused:int=1)->dict[str,Any]:
    cfg=read_json(CFG)
    seeds_cfg=read_json(SEEDS)
    if cfg.get("status")!=EXPECTED_CFG or seeds_cfg.get("status")!=EXPECTED_SEEDS:
        raise RuntimeError("unexpected Phase-6 reconstruction contract/seed status")

    out=ROOT/provider
    manifest_path=out/"provider_reconstruction_manifest.json"
    if manifest_path.is_file():
        m=read_json(manifest_path)
        if m.get("status")=="PHASE6_GENUINE_I2A_PROVIDER_RECONSTRUCTION_COMPLETE":
            print(f"I2A RECON P4/{provider} cached",flush=True)
            return {
                "provider_id":provider,
                "best_candidate_id":m["m2_candidate_ids"][0],
                "m2_candidate_ids":";".join(m["m2_candidate_ids"]),
                "wall_seconds":0.0,
                "manifest_sha256":sha256_file(manifest_path),
            }
        raise RuntimeError(f"{provider}: unexpected existing manifest")

    started=time.perf_counter()
    out.mkdir(parents=True,exist_ok=True)
    metadata,_,target=_load_target(provider)
    domain=_domain_row(WORLD,provider)
    bounds=_bounds(domain)

    rec=cfg["candidate_generation"]
    sampler_seeds=[int(x) for x in rec["fit_sampler_seeds"]]
    winners=[]
    for fit_index in range(1,8):
        search_seeds=_seed_tuple(
            seeds_cfg["provider_reconstruction"][f"fit_{fit_index}_search"]
        )
        winners.append(_fit_one(
            provider=provider,
            fit_index=fit_index,
            metadata=metadata,
            target=target,
            bounds=bounds,
            sampler_seed=sampler_seeds[fit_index-1],
            search_seeds=search_seeds,
            out=out/"fits"/f"fit_{fit_index}",
            n_trials=int(rec["trials_per_fit"]),
            n_startup=int(rec["startup_trials_per_fit"]),
        ))

    rescore_seeds=_seed_tuple(seeds_cfg["provider_reconstruction"]["common_rescore"])
    rows=[]
    for index,w in enumerate(winners,start=1):
        cand=_simulate_samples(
            metadata=metadata,
            mean_service_time=float(w["mean_service_time"]),
            cost_rate=float(w["cost_rate"]),
            service_cv=float(w["service_cv"]),
            seeds=rescore_seeds,
        )
        mean_w1,median_w1,max_w1=_score(target,cand)
        rows.append({
            "candidate_id":str(w["candidate_id"]),
            "fit_index":int(w["fit_index"]),
            "search_mean_w1":float(w["search_mean_w1"]),
            "rescore_mean_w1":mean_w1,
            "rescore_median_w1":median_w1,
            "rescore_max_w1":max_w1,
            "mean_service_time":float(w["mean_service_time"]),
            "cost_rate":float(w["cost_rate"]),
            "service_cv":float(w["service_cv"]),
        })
        print(
            f"I2A RESCORE P4/{provider} {index}/7 "
            f"{w['candidate_id']} mean_W1={mean_w1:.6f}",
            flush=True,
        )

    scores=pd.DataFrame(rows).sort_values(
        ["rescore_mean_w1","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    scores.insert(0,"i2a_quality_rank",np.arange(1,8,dtype=int))
    scores_path=out/"i2a_candidate_rescore.csv"
    scores.to_csv(scores_path,index=False)

    m2=scores.head(3).copy()
    m2.insert(0,"method_id","I2A_M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"i2a_m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    manifest={
        "status":"PHASE6_GENUINE_I2A_PROVIDER_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_id":provider,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "phase5_seed_registry_sha256":sha256_file(SEEDS),
        "public_i2a_sha256":sha256_file(I2A_ROOT/provider/"i2a_public_empirical_cdf.csv"),
        "candidate_count":7,
        "search_trials_per_fit":int(rec["trials_per_fit"]),
        "search_n_per_trial":15,
        "rescore_n":len(rescore_seeds),
        "selection_metric":"rescore_mean_w1",
        "m2_candidate_ids":m2["candidate_id"].astype(str).tolist(),
        "graph_prediction_used":False,
        "graph_wb_used":False,
        "final_wb_used":False,
        "private_i1_ledger_used":False,
        "hidden_provider_parameters_used":False,
        "outputs":{
            "candidate_rescore":str(scores_path),
            "m2_provider_models":str(m2_path),
        },
        "output_hashes_sha256":{
            "candidate_rescore":sha256_file(scores_path),
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
        "wall_seconds":manifest["wall_seconds"],
        "manifest_sha256":sha256_file(manifest_path),
    }


def _freeze_world(provider_rows:list[dict[str,Any]])->Path:
    tables={}
    for p in PROVIDERS:
        path=ROOT/p/"i2a_m2_provider_models.csv"
        t=pd.read_csv(path)
        if len(t)!=3:
            raise RuntimeError(f"{p}: genuine I2a M2 provider support !=3")
        tables[p]=t
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
        raise RuntimeError("genuine I2a M2 joint support !=27")
    support_path=ROOT/"m2_joint_support_27.csv"
    support.to_csv(support_path,index=False)

    summary=pd.DataFrame(provider_rows).sort_values("provider_id").reset_index(drop=True)
    summary_path=ROOT/"provider_reconstruction_summary.csv"
    summary.to_csv(summary_path,index=False)
    manifest={
        "status":"PHASE6_GENUINE_I2A_P4_RECONSTRUCTION_COMPLETE",
        "provider_world_id":WORLD,
        "provider_count":3,
        "m2_joint_models":27,
        "provider_reconstruction_manifest_sha256":{
            p:sha256_file(ROOT/p/"provider_reconstruction_manifest.json") for p in PROVIDERS
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
    path=ROOT/"p4_i2a_reconstruction_manifest.json"
    write_json(path,manifest)
    print("\\nPHASE6_GENUINE_I2A_P4_RECONSTRUCTION_PASS")
    print(summary.to_string(index=False))
    print("joint_models 27")
    print("manifest",path)
    return path


def main():
    p=argparse.ArgumentParser(description="Genuine I2a reconstruction for P4")
    p.add_argument("--workers",type=int,default=3)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    tasks=list(PROVIDERS)
    rows=[]
    if args.workers==1:
        for provider in tasks:
            rows.append(run_provider(provider))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers,3)) as pool:
            futures={pool.submit(run_provider,p):p for p in tasks}
            for fut in concurrent.futures.as_completed(futures):
                p=futures[fut]
                try:
                    rows.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"genuine I2a reconstruction failed for {p}") from exc
    _freeze_world(rows)


if __name__=="__main__":
    main()
