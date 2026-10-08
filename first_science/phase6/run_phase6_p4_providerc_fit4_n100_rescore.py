"""Focused Phase-6 diagnostic: rescore all 25 P4/ProviderC I2a fit-4 trials at N=100.

Purpose
-------
The static audit showed that fit 4 visited a parameter point much closer to the
hidden truth, but its noisy N=15 I2a search score ranked that point poorly.
This diagnostic asks whether the ranking changes when *every one* of the 25
already-generated fit-4 parameter points is evaluated on the common N=100 bank.

No new parameter point is generated. No graph simulation is run. Hidden truth
is used only for post-hoc distance diagnostics, never for ranking or selection.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in __import__("sys").path:
    __import__("sys").path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402
from run_phase5_m2_reconstruction_v2 import _domain_row, _load_public_card  # noqa:E402
from run_phase6_i2a_genuine_reconstruction_p4_v1 import (  # noqa:E402
    _load_target as _load_i2a_target,
    _score as _score_i2a,
    _seed_tuple,
    _simulate_samples as _simulate_i2a_samples,
)

WORLD="P4"
PROVIDER="ProviderC"
FIT_INDEX=4
TRIALS=HERE/"results"/"04_i2a_genuine_reconstruction_p4"/PROVIDER/"fits"/f"fit_{FIT_INDEX}"/"trials.csv"
BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
OUT=HERE/"results"/"10_p4_providerc_fit4_n100_rescore"


def _truth()->dict[str,float]:
    cfg=read_json(BATTERY)
    world=[w for w in cfg["provider_worlds"] if str(w["id"])==WORLD]
    if len(world)!=1:
        raise RuntimeError("P4 world not uniquely defined")
    fam=cfg["provider_family"]
    x=float(fam["execution_fraction_x"])
    ipt=float(fam["effective_IPT"])
    return {
        "mean_service_time":float(world[0]["provider_means"][PROVIDER])*x/ipt,
        "cost_rate":float(fam["cost_rate"]),
        "service_cv":float(fam["instruction_cv"]),
    }


def _znorm(theta:dict[str,float],domain:pd.Series)->np.ndarray:
    def zl(v,lo,hi):
        return (math.log(float(v))-math.log(float(lo)))/(math.log(float(hi))-math.log(float(lo)))
    return np.asarray([
        zl(theta["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"]),
        zl(theta["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"]),
        (float(theta["service_cv"])-float(domain["service_cv_lower"]))/
        (float(domain["service_cv_upper"])-float(domain["service_cv_lower"])),
    ],dtype=float)


def _distance(theta:dict[str,float],truth:dict[str,float],domain:pd.Series)->float:
    return float(np.linalg.norm(_znorm(theta,domain)-_znorm(truth,domain)))


def _i1_metrics_from_i2a_samples(
    samples:dict[tuple[str,float],np.ndarray],
    public_surface:pd.DataFrame,
)->dict[str,float]:
    public=public_surface[public_surface["horizon"].astype(float)>0.0].copy()
    errors=[]
    for rec in public.itertuples(index=False):
        key=(str(rec.region_id),float(rec.horizon))
        vals=samples[key]
        sigma=float(np.mean(vals + 1e-12 >= float(rec.rho)))
        errors.append(sigma-float(rec.sigma_hat))
    e=np.asarray(errors,dtype=float)
    return {
        "i1_rmse_n100":float(np.sqrt(np.mean(e*e))),
        "i1_mae_n100":float(np.mean(np.abs(e))),
        "i1_bias_n100":float(np.mean(e)),
        "i1_max_abs_error_n100":float(np.max(np.abs(e))),
    }


def _evaluate(payload:dict)->dict:
    metadata=payload["metadata"]
    target=payload["target"]
    public_surface=payload["public_surface"]
    seeds=payload["seeds"]
    theta=payload["theta"]
    samples=_simulate_i2a_samples(
        metadata=metadata,
        mean_service_time=float(theta["mean_service_time"]),
        cost_rate=float(theta["cost_rate"]),
        service_cv=float(theta["service_cv"]),
        seeds=seeds,
    )
    mean_w1,median_w1,max_w1=_score_i2a(target,samples)
    i1=_i1_metrics_from_i2a_samples(samples,public_surface)
    return {
        "row_id":payload["row_id"],
        "n100_i2a_mean_w1":mean_w1,
        "n100_i2a_median_w1":median_w1,
        "n100_i2a_max_w1":max_w1,
        **i1,
    }


def run(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    OUT.mkdir(parents=True,exist_ok=True)

    if not TRIALS.is_file():
        raise FileNotFoundError(TRIALS)
    trials=pd.read_csv(TRIALS)
    if len(trials)!=25:
        raise RuntimeError(f"expected 25 fit-4 trials, found {len(trials)}")
    required={
        "trial_number","search_mean_w1",
        "mean_service_time","cost_rate","service_cv",
    }
    if not required.issubset(trials.columns):
        raise RuntimeError(f"fit-4 trials missing {sorted(required.difference(trials.columns))}")

    metadata,public_surface,_=_load_public_card(WORLD,PROVIDER)
    _,_,target=_load_i2a_target(PROVIDER)
    seed_cfg=read_json(SEEDS)
    seeds=_seed_tuple(seed_cfg["provider_reconstruction"]["common_rescore"])
    if len(seeds)!=100:
        raise RuntimeError("common rescore bank is not N=100")
    domain=_domain_row(WORLD,PROVIDER)
    truth=_truth()

    trial_rows=trials.copy()
    trial_rows["row_id"]=trial_rows["trial_number"].map(lambda x:f"trial_{int(x):02d}")
    trial_rows["source"]="FIT4_TRIAL"
    trial_rows["parameter_distance"]=trial_rows.apply(
        lambda r:_distance({
            "mean_service_time":float(r["mean_service_time"]),
            "cost_rate":float(r["cost_rate"]),
            "service_cv":float(r["service_cv"]),
        },truth,domain),axis=1
    )
    trial_rows["n15_rank"]=trial_rows["search_mean_w1"].rank(method="first").astype(int)

    truth_row=pd.DataFrame([{
        "trial_number":-1,
        "search_mean_w1":np.nan,
        "mean_service_time":truth["mean_service_time"],
        "cost_rate":truth["cost_rate"],
        "service_cv":truth["service_cv"],
        "row_id":"TRUE",
        "source":"TRUE",
        "parameter_distance":0.0,
        "n15_rank":np.nan,
    }])
    all_input=pd.concat([trial_rows,truth_row],ignore_index=True)

    payloads=[]
    for rec in all_input.itertuples(index=False):
        theta={
            "mean_service_time":float(rec.mean_service_time),
            "cost_rate":float(rec.cost_rate),
            "service_cv":float(rec.service_cv),
        }
        payloads.append({
            "row_id":str(rec.row_id),
            "theta":theta,
            "metadata":metadata,
            "target":target,
            "public_surface":public_surface,
            "seeds":seeds,
        })

    results=[]
    if workers==1:
        for i,p in enumerate(payloads,1):
            results.append(_evaluate(p))
            print(f"N100 RESCORE {i}/{len(payloads)} {p['row_id']}",flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(_evaluate,p):p["row_id"] for p in payloads}
            done=0
            for fut in concurrent.futures.as_completed(futures):
                rid=futures[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"N100 rescore failed for {rid}") from exc
                done+=1
                print(f"N100 RESCORE {done}/{len(payloads)} {rid}",flush=True)

    result=pd.DataFrame(results)
    table=all_input.merge(result,on="row_id",how="left",validate="one_to_one")
    if table["n100_i2a_mean_w1"].isna().any():
        raise RuntimeError("missing N100 rescore result")

    trial_mask=table["source"].eq("FIT4_TRIAL")
    table.loc[trial_mask,"n100_rank"]=(
        table.loc[trial_mask,"n100_i2a_mean_w1"].rank(method="first").astype(int)
    )
    table.loc[~trial_mask,"n100_rank"]=np.nan

    trial_table=table[trial_mask].copy()
    n15_best=trial_table.sort_values(["search_mean_w1","trial_number"],kind="mergesort").iloc[0]
    n100_best=trial_table.sort_values(["n100_i2a_mean_w1","trial_number"],kind="mergesort").iloc[0]
    closest=trial_table.sort_values(["parameter_distance","trial_number"],kind="mergesort").iloc[0]
    true_rec=table[table["source"]=="TRUE"].iloc[0]

    spearman=float(
        trial_table["search_mean_w1"].rank(method="average").corr(
            trial_table["n100_i2a_mean_w1"].rank(method="average")
        )
    )

    summary=pd.DataFrame([{
        "provider_id":PROVIDER,
        "fit_index":FIT_INDEX,
        "n_trials":25,
        "n100_bank_n":100,
        "n15_vs_n100_spearman":spearman,
        "n15_best_trial":int(n15_best["trial_number"]),
        "n15_best_search_w1":float(n15_best["search_mean_w1"]),
        "n15_best_n100_w1":float(n15_best["n100_i2a_mean_w1"]),
        "n15_best_parameter_distance":float(n15_best["parameter_distance"]),
        "n100_best_trial":int(n100_best["trial_number"]),
        "n100_best_n100_w1":float(n100_best["n100_i2a_mean_w1"]),
        "n100_best_n15_rank":int(n100_best["n15_rank"]),
        "n100_best_parameter_distance":float(n100_best["parameter_distance"]),
        "closest_trial":int(closest["trial_number"]),
        "closest_parameter_distance":float(closest["parameter_distance"]),
        "closest_n15_rank":int(closest["n15_rank"]),
        "closest_n100_rank":int(closest["n100_rank"]),
        "closest_n15_w1":float(closest["search_mean_w1"]),
        "closest_n100_w1":float(closest["n100_i2a_mean_w1"]),
        "closest_i1_rmse_n100":float(closest["i1_rmse_n100"]),
        "true_n100_i2a_w1":float(true_rec["n100_i2a_mean_w1"]),
        "true_i1_rmse_n100":float(true_rec["i1_rmse_n100"]),
    }])

    table_path=OUT/"providerc_fit4_all25_n100_rescore.csv"
    summary_path=OUT/"providerc_fit4_n100_rescore_summary.csv"
    table.sort_values(["source","n100_i2a_mean_w1"],kind="mergesort").to_csv(table_path,index=False)
    summary.to_csv(summary_path,index=False)

    manifest=OUT/"providerc_fit4_n100_rescore_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_P4_PROVIDERC_FIT4_N100_RESCORE_COMPLETE",
        "posthoc_development_diagnostic":True,
        "new_parameter_points_generated":False,
        "graph_simulation_run":False,
        "hidden_truth_used_for_selection":False,
        "provider_id":PROVIDER,
        "fit_index":FIT_INDEX,
        "candidate_count":25,
        "truth_reference_count":1,
        "common_rescore_n":100,
        "outputs":{
            "table":str(table_path),
            "summary":str(summary_path),
        },
        "output_hashes_sha256":{
            "table":sha256_file(table_path),
            "summary":sha256_file(summary_path),
        },
        "completed_utc":utc_now_iso(),
    })

    print("\nPHASE6_P4_PROVIDERC_FIT4_N100_RESCORE_PASS")
    print(summary.to_string(index=False))
    print("\nTOP 10 BY N100 I2A W1")
    print(
        trial_table.sort_values(["n100_i2a_mean_w1","trial_number"],kind="mergesort")
        [["trial_number","n15_rank","n100_rank","search_mean_w1","n100_i2a_mean_w1",
          "i1_rmse_n100","parameter_distance","mean_service_time","cost_rate","service_cv"]]
        .head(10).to_string(index=False)
    )
    print("\nTRUE")
    print(table[table["source"]=="TRUE"][
        ["n100_i2a_mean_w1","i1_rmse_n100","mean_service_time","cost_rate","service_cv"]
    ].to_string(index=False))
    print("\noutput",OUT)
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    run(args.workers)


if __name__=="__main__":
    main()
