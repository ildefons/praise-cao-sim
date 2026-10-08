"""Phase-6 P4 five-rho survival-grid criterion audit.

Development-only provider diagnostic.  It asks how to exploit I2a while keeping
the same semantic fitting object used by I1:

    sigma_i(A,H;rho) = P(c_i(A,H) >= rho).

For P4/ProviderA-C, this script evaluates the hidden truth plus the seven
I1-generated and seven genuine-I2a-generated candidate parameter sets on the
same frozen common N=100 local rescore bank.  From the resulting I2a compliance
samples it can evaluate many five-rho grids without any further simulation.

The hidden truth is opened only to assess whether a candidate loss is aligned
with physical parameter recovery.  It is not used as a scientific validation
result and no graph result is read.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import itertools
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
    _seed_tuple,
    _simulate_samples as _simulate_i2a_samples,
)

WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
I1_ROOT=PHASE5/"results"/"03_reconstruction_v3"/WORLD
I2_ROOT=HERE/"results"/"04_i2a_genuine_reconstruction_p4"
OUT=HERE/"results"/"11_p4_five_rho_grid_audit"

# Deliberately modest candidate pool.  Exhaustive 5-of-10 combinations are
# cheap once N=100 compliance samples have been generated.
RHO_POOL=(
    0.80,0.85,0.90,0.925,0.95,0.97,0.975,0.9833333333333333,0.99,0.995
)
PREDECLARED_GRIDS={
    "I1_ORIGINAL":(0.95,0.975,0.9833333333333333,0.99,0.995),
    "BROAD_5":(0.80,0.90,0.95,0.97,0.99),
    "BROAD_HIGH_5":(0.85,0.90,0.95,0.98,0.995),
    "MIDTAIL_5":(0.90,0.925,0.95,0.975,0.995),
}


def _truth()->dict[str,dict[str,float]]:
    cfg=read_json(BATTERY)
    worlds=[w for w in cfg["provider_worlds"] if str(w["id"])==WORLD]
    if len(worlds)!=1:
        raise RuntimeError("P4 world not uniquely defined")
    world=worlds[0]
    fam=cfg["provider_family"]
    x=float(fam["execution_fraction_x"]); ipt=float(fam["effective_IPT"])
    return {
        p:{
            "mean_service_time":float(world["provider_means"][p])*x/ipt,
            "cost_rate":float(fam["cost_rate"]),
            "service_cv":float(fam["instruction_cv"]),
        } for p in PROVIDERS
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


def _candidate_bank(provider:str)->pd.DataFrame:
    i1_path=I1_ROOT/provider/"v3_candidates_rescore.csv"
    i2_path=I2_ROOT/provider/"i2a_candidate_rescore.csv"
    if not i1_path.is_file():
        raise FileNotFoundError(i1_path)
    if not i2_path.is_file():
        raise FileNotFoundError(i2_path)
    need=["candidate_id","mean_service_time","cost_rate","service_cv"]
    i1=pd.read_csv(i1_path)
    i2=pd.read_csv(i2_path)
    if len(i1)!=7 or len(i2)!=7:
        raise RuntimeError(f"{provider}: expected 7 I1 + 7 I2a candidates")
    for col in need:
        if col not in i1.columns or col not in i2.columns:
            raise RuntimeError(f"{provider}: candidate bank missing {col}")
    i1=i1[need].copy(); i1["source_family"]="I1_GENERATED"
    i2=i2[need].copy(); i2["source_family"]="I2A_GENERATED"
    return pd.concat([i1,i2],ignore_index=True)


def _eval_candidate(payload:dict)->dict:
    samples=_simulate_i2a_samples(
        metadata=payload["metadata"],
        mean_service_time=float(payload["theta"]["mean_service_time"]),
        cost_rate=float(payload["theta"]["cost_rate"]),
        service_cv=float(payload["theta"]["service_cv"]),
        seeds=payload["seeds"],
    )
    # Return compact sorted samples as Python lists; process boundary then closes.
    packed={
        f"{rid}|{H:.12g}":np.asarray(vals,dtype=float).tolist()
        for (rid,H),vals in samples.items()
    }
    return {"row_id":payload["row_id"],"samples":packed}


def _unpack(packed:dict[str,list[float]])->dict[tuple[str,float],np.ndarray]:
    out={}
    for key,vals in packed.items():
        rid,h=key.split("|",1)
        out[(rid,float(h))]=np.asarray(vals,dtype=float)
    return out


def _sigma_surface(samples:dict[tuple[str,float],np.ndarray],rhos:tuple[float,...])->np.ndarray:
    vals=[]
    for key in sorted(samples):
        x=samples[key]
        for rho in rhos:
            vals.append(float(np.mean(x + 1e-12 >= float(rho))))
    return np.asarray(vals,dtype=float)


def _rmse(target:np.ndarray,candidate:np.ndarray)->float:
    d=np.asarray(candidate,dtype=float)-np.asarray(target,dtype=float)
    return float(np.sqrt(np.mean(d*d)))


def _spearman(a:pd.Series,b:pd.Series)->float:
    return float(a.rank(method="average").corr(b.rank(method="average")))


def _grid_id(rhos:tuple[float,...])->str:
    return ",".join(f"{x:.6g}" for x in rhos)


def run(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    OUT.mkdir(parents=True,exist_ok=True)

    truths=_truth()
    seed_cfg=read_json(SEEDS)
    seeds=_seed_tuple(seed_cfg["provider_reconstruction"]["common_rescore"])
    if len(seeds)!=100:
        raise RuntimeError("common rescore bank is not N=100")

    provider_tables={}
    target_samples={}
    payloads=[]
    for provider in PROVIDERS:
        metadata,_,_=_load_public_card(WORLD,provider)
        _,_,target=_load_i2a_target(provider)
        target_samples[provider]=target
        domain=_domain_row(WORLD,provider)
        truth=truths[provider]
        bank=_candidate_bank(provider)
        rows=[{
            "provider_id":provider,
            "row_id":f"{provider}::TRUE",
            "candidate_id":"HIDDEN_GENERATOR",
            "source_family":"TRUE",
            **truth,
            "parameter_distance":0.0,
        }]
        for r in bank.itertuples(index=False):
            theta={
                "mean_service_time":float(r.mean_service_time),
                "cost_rate":float(r.cost_rate),
                "service_cv":float(r.service_cv),
            }
            rows.append({
                "provider_id":provider,
                "row_id":f"{provider}::{r.source_family}::{r.candidate_id}",
                "candidate_id":str(r.candidate_id),
                "source_family":str(r.source_family),
                **theta,
                "parameter_distance":_distance(theta,truth,domain),
            })
        table=pd.DataFrame(rows)
        provider_tables[provider]=table
        for r in table.itertuples(index=False):
            payloads.append({
                "row_id":str(r.row_id),
                "metadata":metadata,
                "theta":{
                    "mean_service_time":float(r.mean_service_time),
                    "cost_rate":float(r.cost_rate),
                    "service_cv":float(r.service_cv),
                },
                "seeds":seeds,
            })

    results=[]
    if workers==1:
        for i,p in enumerate(payloads,1):
            results.append(_eval_candidate(p))
            print(f"RHO GRID SIM {i}/{len(payloads)} {p['row_id']}",flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(_eval_candidate,p):p["row_id"] for p in payloads}
            done=0
            for fut in concurrent.futures.as_completed(futures):
                rid=futures[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"rho-grid simulation failed for {rid}") from exc
                done+=1
                print(f"RHO GRID SIM {done}/{len(payloads)} {rid}",flush=True)

    samples_by_id={r["row_id"]:_unpack(r["samples"]) for r in results}
    if len(samples_by_id)!=len(payloads):
        raise RuntimeError("candidate simulation result count mismatch")

    # Evaluate predeclared grids plus all 5-of-pool combinations.
    all_grids={f"POOL_{i:03d}":tuple(g) for i,g in enumerate(itertools.combinations(RHO_POOL,5),1)}
    for name,g in PREDECLARED_GRIDS.items():
        all_grids[name]=tuple(g)

    score_rows=[]
    summary_rows=[]
    for grid_name,rhos in all_grids.items():
        for provider in PROVIDERS:
            target_vec=_sigma_surface(target_samples[provider],rhos)
            t=provider_tables[provider].copy()
            losses=[]
            for rec in t.itertuples(index=False):
                losses.append(_rmse(target_vec,_sigma_surface(samples_by_id[str(rec.row_id)],rhos)))
            t["grid_rmse"]=losses
            t["grid_name"]=grid_name
            t["rho_grid"]=_grid_id(rhos)
            t["rho_min"]=min(rhos); t["rho_max"]=max(rhos)
            t["rho_count"]=len(rhos)
            score_rows.append(t)

            nontruth=t[t["source_family"]!="TRUE"].copy()
            truth_row=t[t["source_family"]=="TRUE"].iloc[0]
            ranked_all=t.sort_values(["grid_rmse","row_id"],kind="mergesort").reset_index(drop=True)
            truth_rank=int(ranked_all.index[ranked_all["source_family"]=="TRUE"][0])+1
            closest=nontruth.sort_values(["parameter_distance","row_id"],kind="mergesort").iloc[0]
            ranked_nontruth=nontruth.sort_values(
                ["grid_rmse","row_id"],kind="mergesort"
            ).reset_index(drop=True)
            matches=np.flatnonzero(
                ranked_nontruth["row_id"].astype(str).to_numpy()
                == str(closest["row_id"])
            )
            if len(matches)!=1:
                raise RuntimeError("closest-candidate rank lookup failed")
            closest_rank=int(matches[0])+1
            best=nontruth.sort_values(["grid_rmse","row_id"],kind="mergesort").iloc[0]
            summary_rows.append({
                "grid_name":grid_name,
                "rho_grid":_grid_id(rhos),
                "provider_id":provider,
                "truth_rmse":float(truth_row["grid_rmse"]),
                "truth_rank_all15":truth_rank,
                "spearman_loss_vs_parameter_distance_nontruth":_spearman(
                    nontruth["grid_rmse"],nontruth["parameter_distance"]
                ),
                "best_candidate_id":str(best["candidate_id"]),
                "best_candidate_source":str(best["source_family"]),
                "best_candidate_rmse":float(best["grid_rmse"]),
                "best_candidate_parameter_distance":float(best["parameter_distance"]),
                "closest_candidate_id":str(closest["candidate_id"]),
                "closest_candidate_distance":float(closest["parameter_distance"]),
                "closest_candidate_rmse":float(closest["grid_rmse"]),
                "closest_candidate_loss_rank_nontruth":closest_rank,
            })

    scores=pd.concat(score_rows,ignore_index=True)
    summary=pd.DataFrame(summary_rows)

    agg=summary.groupby(["grid_name","rho_grid"],as_index=False).agg(
        mean_spearman=("spearman_loss_vs_parameter_distance_nontruth","mean"),
        min_spearman=("spearman_loss_vs_parameter_distance_nontruth","min"),
        mean_truth_rank=("truth_rank_all15","mean"),
        max_truth_rank=("truth_rank_all15","max"),
        mean_best_candidate_parameter_distance=("best_candidate_parameter_distance","mean"),
        mean_closest_candidate_loss_rank=("closest_candidate_loss_rank_nontruth","mean"),
    )
    # This ranking is explicitly diagnostic and truth-opened. Higher correlation
    # is desirable; then prefer truth closer to rank 1 and physically closer
    # best candidates. It is NOT a frozen method-selection rule.
    agg=agg.sort_values(
        ["mean_spearman","max_truth_rank","mean_best_candidate_parameter_distance","rho_grid"],
        ascending=[False,True,True,True],kind="mergesort"
    ).reset_index(drop=True)
    agg.insert(0,"diagnostic_rank",np.arange(1,len(agg)+1,dtype=int))

    scores_path=OUT/"p4_five_rho_candidate_scores.csv"
    summary_path=OUT/"p4_five_rho_provider_summary.csv"
    agg_path=OUT/"p4_five_rho_grid_ranking.csv"
    scores.to_csv(scores_path,index=False)
    summary.to_csv(summary_path,index=False)
    agg.to_csv(agg_path,index=False)

    pre_names=set(PREDECLARED_GRIDS)
    pre=agg[agg["grid_name"].isin(pre_names)].copy().sort_values("diagnostic_rank")
    top=agg.head(15).copy()

    print("\nPHASE6_P4_FIVE_RHO_GRID_AUDIT_PASS")
    print("\nPREDECLARED FIVE-RHO GRIDS")
    print(pre.to_string(index=False))
    print("\nTOP 15 FIVE-RHO GRIDS FROM 5-OF-10 POOL")
    print(top.to_string(index=False))

    # Per-provider details for the user's proposed broad grid.
    proposed=summary[summary["grid_name"]=="BROAD_5"].copy()
    print("\nBROAD_5 PROVIDER DETAILS")
    print(proposed.to_string(index=False))

    manifest=OUT/"p4_five_rho_grid_audit_manifest.json"
    outputs={
        "candidate_scores":str(scores_path),
        "provider_summary":str(summary_path),
        "grid_ranking":str(agg_path),
    }
    write_json(manifest,{
        "status":"PHASE6_P4_FIVE_RHO_GRID_AUDIT_COMPLETE",
        "posthoc_development_diagnostic":True,
        "hidden_truth_opened":True,
        "hidden_truth_used_only_for_diagnostic_ranking":True,
        "graph_results_read":False,
        "new_provider_parameter_points_generated":False,
        "candidate_bank_per_provider":{
            "truth":1,"I1_generated":7,"I2a_generated":7
        },
        "common_rescore_n":100,
        "rho_pool":list(RHO_POOL),
        "predeclared_grids":{k:list(v) for k,v in PREDECLARED_GRIDS.items()},
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    })
    print("\noutput",OUT)
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    run(args.workers)


if __name__=="__main__":
    main()