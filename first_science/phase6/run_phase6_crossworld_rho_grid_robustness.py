"""Cross-world robustness audit for the candidate I2a survival-probe criterion.

Development-only diagnostic.

The P4 criterion audit suggested that the five-rho grid

    R5 = {0.80, 0.85, 0.90, 0.925, 0.95}

is more physically informative than the original high-tail I1 grid.  This
script asks whether that conclusion remains sensible across all 12 Phase-5
provider instances (P1-P4 x ProviderA-C).

To keep the comparison uniform across worlds, every provider uses the same type
of candidate bank: the seven frozen Phase-5 V3 provider candidates.  P4-only
I2a-generated candidates are intentionally excluded here.

Each candidate and the hidden synthetic truth are simulated on the same frozen
V3 common N=100 rescore bank.  The resulting compliance samples are converted
to sigma(A,H;rho) at the union of the tested rho values.  No graph simulation
or graph result is read.

Hidden truth is opened only for post-hoc development diagnostics:
- normalized parameter distance,
- truth rank,
- loss-vs-distance rank correlation.
It is never used to fit or alter a candidate.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in __import__("sys").path:
    __import__("sys").path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402
from run_phase5_m2_reconstruction_v2 import _domain_row, _load_public_card  # noqa:E402
from run_phase6_i2a_marginal_audit_v1 import (  # noqa:E402
    _seed_tuple,
    _simulate_candidate_samples,
)

WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
V3_ROOT=PHASE5/"results"/"03_reconstruction_v3"
I2A_ROOT=HERE/"results"/"01_i2a_marginal_audit"
OUT=HERE/"results"/"12_crossworld_rho_grid_robustness"
CHECKPOINTS=OUT/"checkpoints"

GRIDS={
    "ROBUST_R5":(0.80,0.85,0.90,0.925,0.95),
    "ROBUST_R7":(0.80,0.85,0.90,0.925,0.95,0.97,0.99),
    "ROBUST_R8":(0.80,0.85,0.90,0.925,0.95,0.97,0.99,0.995),
    "I1_ORIGINAL":(0.95,0.975,0.9833333333333333,0.99,0.995),
}
RHO_UNION=tuple(sorted({float(r) for grid in GRIDS.values() for r in grid}))
TOL=1e-12


def _truths()->dict[tuple[str,str],dict[str,float]]:
    cfg=read_json(BATTERY)
    fam=cfg["provider_family"]
    x=float(fam["execution_fraction_x"])
    ipt=float(fam["effective_IPT"])
    out={}
    for world in cfg["provider_worlds"]:
        wid=str(world["id"])
        for provider in PROVIDERS:
            out[(wid,provider)]={
                "mean_service_time":float(world["provider_means"][provider])*x/ipt,
                "cost_rate":float(fam["cost_rate"]),
                "service_cv":float(fam["instruction_cv"]),
            }
    expected={(w,p) for w in WORLDS for p in PROVIDERS}
    if set(out)!=expected:
        raise RuntimeError("battery truth does not cover all 12 provider instances")
    return out


def _znorm(theta:dict[str,float],domain:pd.Series)->np.ndarray:
    def zl(v,lo,hi):
        return (
            math.log(float(v))-math.log(float(lo))
        )/(
            math.log(float(hi))-math.log(float(lo))
        )
    return np.asarray([
        zl(theta["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"]),
        zl(theta["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"]),
        (float(theta["service_cv"])-float(domain["service_cv_lower"]))/
        (float(domain["service_cv_upper"])-float(domain["service_cv_lower"])),
    ],dtype=float)


def _distance(theta:dict[str,float],truth:dict[str,float],domain:pd.Series)->float:
    return float(np.linalg.norm(_znorm(theta,domain)-_znorm(truth,domain)))


def _load_target(world:str,provider:str)->dict[tuple[str,float],np.ndarray]:
    path=I2A_ROOT/world/provider/"i2a_public_empirical_cdf.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df=pd.read_csv(path)
    need={"provider_id","region_id","H","compliance_fraction"}
    if not need.issubset(df.columns):
        raise RuntimeError(f"{world}/{provider}: I2a target missing columns")
    if set(df["provider_id"].astype(str))!={provider}:
        raise RuntimeError(f"{world}/{provider}: target provider mismatch")
    out={}
    for (rid,H),g in df.groupby(["region_id","H"],sort=True):
        vals=np.sort(g["compliance_fraction"].astype(float).to_numpy())
        if len(vals)!=100:
            raise RuntimeError(f"{world}/{provider}/{rid}/{H}: target N !=100")
        out[(str(rid),float(H))]=vals
    if len(out)!=5*48:
        raise RuntimeError(f"{world}/{provider}: expected 240 target groups")
    return out


def _sigma_rows(
    *,
    world:str,
    provider:str,
    row_id:str,
    source:str,
    samples:pd.DataFrame,
)->pd.DataFrame:
    rows=[]
    groups={
        (str(rid),float(H)):g["compliance_fraction"].astype(float).to_numpy()
        for (rid,H),g in samples.groupby(["region_id","H"],sort=True)
    }
    if len(groups)!=5*48:
        raise RuntimeError(f"{world}/{provider}/{row_id}: candidate group count !=240")
    for (rid,H),vals in sorted(groups.items(),key=lambda kv:(kv[0][0],kv[0][1])):
        for rho in RHO_UNION:
            rows.append({
                "provider_world_id":world,
                "provider_id":provider,
                "row_id":row_id,
                "source":source,
                "region_id":rid,
                "H":float(H),
                "rho":float(rho),
                "sigma":float(np.mean(vals + TOL >= float(rho))),
            })
    return pd.DataFrame(rows)


def _target_sigma_rows(world:str,provider:str,target:dict[tuple[str,float],np.ndarray])->pd.DataFrame:
    rows=[]
    for (rid,H),vals in sorted(target.items(),key=lambda kv:(kv[0][0],kv[0][1])):
        for rho in RHO_UNION:
            rows.append({
                "provider_world_id":world,
                "provider_id":provider,
                "region_id":rid,
                "H":float(H),
                "rho":float(rho),
                "sigma_target":float(np.mean(vals + TOL >= float(rho))),
            })
    return pd.DataFrame(rows)


def _candidate_table(world:str,provider:str,truth:dict[str,float],domain:pd.Series)->pd.DataFrame:
    path=V3_ROOT/world/provider/"v3_candidates_rescore.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    t=pd.read_csv(path)
    need={"candidate_id","mean_service_time","cost_rate","service_cv"}
    if len(t)!=7 or not need.issubset(t.columns):
        raise RuntimeError(f"{world}/{provider}: expected 7 V3 parameterized candidates")
    rows=[{
        "provider_world_id":world,
        "provider_id":provider,
        "row_id":f"{world}::{provider}::TRUE",
        "candidate_id":"HIDDEN_GENERATOR",
        "source":"TRUE",
        **truth,
        "parameter_distance":0.0,
    }]
    for r in t.itertuples(index=False):
        theta={
            "mean_service_time":float(r.mean_service_time),
            "cost_rate":float(r.cost_rate),
            "service_cv":float(r.service_cv),
        }
        rows.append({
            "provider_world_id":world,
            "provider_id":provider,
            "row_id":f"{world}::{provider}::{r.candidate_id}",
            "candidate_id":str(r.candidate_id),
            "source":"V3_CANDIDATE",
            **theta,
            "parameter_distance":_distance(theta,truth,domain),
        })
    return pd.DataFrame(rows)


def _checkpoint_path(row_id:str)->Path:
    safe=row_id.replace("::","__").replace("/","_")
    return CHECKPOINTS/f"{safe}.csv"


def _simulate_one(payload:dict[str,Any])->dict[str,Any]:
    cp=Path(payload["checkpoint"])
    if cp.is_file():
        frame=pd.read_csv(cp)
        expected=5*48*len(RHO_UNION)
        if len(frame)!=expected or set(frame["row_id"].astype(str))!={payload["row_id"]}:
            raise RuntimeError(f"invalid checkpoint {cp}")
        return {"row_id":payload["row_id"],"checkpoint":str(cp),"cached":True}

    samples=_simulate_candidate_samples(
        metadata=payload["metadata"],
        mean_service_time=float(payload["theta"]["mean_service_time"]),
        cost_rate=float(payload["theta"]["cost_rate"]),
        service_cv=float(payload["theta"]["service_cv"]),
        seeds=tuple(payload["seeds"]),
    )
    frame=_sigma_rows(
        world=payload["world"],
        provider=payload["provider"],
        row_id=payload["row_id"],
        source=payload["source"],
        samples=samples,
    )
    cp.parent.mkdir(parents=True,exist_ok=True)
    tmp=cp.with_suffix(".tmp")
    frame.to_csv(tmp,index=False)
    os.replace(tmp,cp)
    return {"row_id":payload["row_id"],"checkpoint":str(cp),"cached":False}


def _spearman(a:pd.Series,b:pd.Series)->float:
    return float(a.rank(method="average").corr(b.rank(method="average")))


def _grid_loss(
    candidate:pd.DataFrame,
    target:pd.DataFrame,
    rhos:tuple[float,...],
)->float:
    c=candidate[candidate["rho"].astype(float).isin(list(rhos))].copy()
    t=target[target["rho"].astype(float).isin(list(rhos))].copy()
    keys=["provider_world_id","provider_id","region_id","H","rho"]
    m=t.merge(c,on=keys,how="inner",validate="one_to_one")
    expected=5*48*len(rhos)
    if len(m)!=expected:
        raise RuntimeError(f"grid merge expected {expected} points, found {len(m)}")
    e=m["sigma"].astype(float).to_numpy()-m["sigma_target"].astype(float).to_numpy()
    return float(np.sqrt(np.mean(e*e)))


def run(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    OUT.mkdir(parents=True,exist_ok=True)
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)

    seed_cfg=read_json(SEEDS)
    seeds=_seed_tuple(seed_cfg["provider_reconstruction"]["common_rescore"])
    if len(seeds)!=100:
        raise RuntimeError("V3 common rescore bank is not N=100")

    truths=_truths()
    tables=[]
    targets={}
    payloads=[]
    for world in WORLDS:
        for provider in PROVIDERS:
            truth=truths[(world,provider)]
            domain=_domain_row(world,provider)
            table=_candidate_table(world,provider,truth,domain)
            tables.append(table)
            targets[(world,provider)]=_target_sigma_rows(
                world,provider,_load_target(world,provider)
            )
            metadata,_,_=_load_public_card(world,provider)
            for rec in table.itertuples(index=False):
                payloads.append({
                    "world":world,
                    "provider":provider,
                    "row_id":str(rec.row_id),
                    "source":str(rec.source),
                    "metadata":metadata,
                    "theta":{
                        "mean_service_time":float(rec.mean_service_time),
                        "cost_rate":float(rec.cost_rate),
                        "service_cv":float(rec.service_cv),
                    },
                    "seeds":seeds,
                    "checkpoint":str(_checkpoint_path(str(rec.row_id))),
                })

    total=len(payloads)
    if total!=12*8:
        raise RuntimeError(f"expected 96 simulation rows, found {total}")
    results=[]
    if workers==1:
        for i,p in enumerate(payloads,1):
            r=_simulate_one(p)
            results.append(r)
            tag="cached" if r["cached"] else "simulated"
            print(f"CROSSWORLD RHO {i}/{total} {r['row_id']} [{tag}]",flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(_simulate_one,p):p["row_id"] for p in payloads}
            done=0
            for fut in concurrent.futures.as_completed(futures):
                rid=futures[fut]
                try:
                    r=fut.result()
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"cross-world rho simulation failed for {rid}") from exc
                results.append(r)
                done+=1
                tag="cached" if r["cached"] else "simulated"
                print(f"CROSSWORLD RHO {done}/{total} {rid} [{tag}]",flush=True)

    sigma_by_row={}
    for r in results:
        sigma_by_row[str(r["row_id"])]=pd.read_csv(r["checkpoint"])
    table_all=pd.concat(tables,ignore_index=True)

    score_rows=[]
    provider_rows=[]
    for (world,provider),meta in table_all.groupby(
        ["provider_world_id","provider_id"],sort=True
    ):
        target=targets[(str(world),str(provider))]
        for grid_name,rhos in GRIDS.items():
            local=meta.copy()
            losses=[]
            for rec in local.itertuples(index=False):
                losses.append(_grid_loss(sigma_by_row[str(rec.row_id)],target,rhos))
            local["grid_name"]=grid_name
            local["rho_grid"]=",".join(f"{x:.6g}" for x in rhos)
            local["grid_rmse"]=losses
            score_rows.append(local)

            truth_row=local[local["source"]=="TRUE"].iloc[0]
            candidates=local[local["source"]=="V3_CANDIDATE"].copy()
            ranked_all=local.sort_values(["grid_rmse","row_id"],kind="mergesort").reset_index(drop=True)
            truth_idx=np.flatnonzero(ranked_all["source"].astype(str).to_numpy()=="TRUE")
            if len(truth_idx)!=1:
                raise RuntimeError("truth rank lookup failed")
            closest=candidates.sort_values(
                ["parameter_distance","row_id"],kind="mergesort"
            ).iloc[0]
            best=candidates.sort_values(
                ["grid_rmse","row_id"],kind="mergesort"
            ).iloc[0]
            ranked_c=candidates.sort_values(
                ["grid_rmse","row_id"],kind="mergesort"
            ).reset_index(drop=True)
            ci=np.flatnonzero(
                ranked_c["row_id"].astype(str).to_numpy()==str(closest["row_id"])
            )
            if len(ci)!=1:
                raise RuntimeError("closest rank lookup failed")
            provider_rows.append({
                "grid_name":grid_name,
                "rho_grid":local["rho_grid"].iloc[0],
                "provider_world_id":str(world),
                "provider_id":str(provider),
                "truth_rmse":float(truth_row["grid_rmse"]),
                "truth_rank_all8":int(truth_idx[0])+1,
                "spearman_loss_vs_parameter_distance":_spearman(
                    candidates["grid_rmse"],candidates["parameter_distance"]
                ),
                "best_candidate_id":str(best["candidate_id"]),
                "best_candidate_rmse":float(best["grid_rmse"]),
                "best_candidate_parameter_distance":float(best["parameter_distance"]),
                "closest_candidate_id":str(closest["candidate_id"]),
                "closest_candidate_distance":float(closest["parameter_distance"]),
                "closest_candidate_rmse":float(closest["grid_rmse"]),
                "closest_candidate_loss_rank":int(ci[0])+1,
            })

    scores=pd.concat(score_rows,ignore_index=True)
    provider_summary=pd.DataFrame(provider_rows)

    aggregate=provider_summary.groupby(["grid_name","rho_grid"],as_index=False).agg(
        mean_spearman=("spearman_loss_vs_parameter_distance","mean"),
        median_spearman=("spearman_loss_vs_parameter_distance","median"),
        min_spearman=("spearman_loss_vs_parameter_distance","min"),
        positive_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x>0).sum())),
        nonnegative_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x>=0).sum())),
        negative_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x<0).sum())),
        mean_truth_rank=("truth_rank_all8","mean"),
        max_truth_rank=("truth_rank_all8","max"),
        mean_best_candidate_parameter_distance=("best_candidate_parameter_distance","mean"),
        mean_closest_candidate_loss_rank=("closest_candidate_loss_rank","mean"),
    )
    aggregate=aggregate.sort_values(
        ["negative_provider_count","min_spearman","mean_spearman",
         "max_truth_rank","mean_best_candidate_parameter_distance"],
        ascending=[True,False,False,True,True],
        kind="mergesort",
    ).reset_index(drop=True)
    aggregate.insert(0,"robustness_rank",np.arange(1,len(aggregate)+1,dtype=int))

    world_summary=provider_summary.groupby(
        ["grid_name","rho_grid","provider_world_id"],as_index=False
    ).agg(
        mean_spearman=("spearman_loss_vs_parameter_distance","mean"),
        min_spearman=("spearman_loss_vs_parameter_distance","min"),
        negative_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x<0).sum())),
        max_truth_rank=("truth_rank_all8","max"),
        mean_best_candidate_parameter_distance=("best_candidate_parameter_distance","mean"),
    )

    scores_path=OUT/"crossworld_candidate_scores.csv"
    provider_path=OUT/"crossworld_provider_summary.csv"
    world_path=OUT/"crossworld_world_summary.csv"
    aggregate_path=OUT/"crossworld_grid_robustness_summary.csv"
    scores.to_csv(scores_path,index=False)
    provider_summary.to_csv(provider_path,index=False)
    world_summary.to_csv(world_path,index=False)
    aggregate.to_csv(aggregate_path,index=False)

    print("\nPHASE6_CROSSWORLD_RHO_GRID_ROBUSTNESS_PASS")
    print("\nGRID ROBUSTNESS ACROSS 12 PROVIDERS")
    print(aggregate.to_string(index=False))
    print("\nR5 PROVIDER DETAILS")
    print(
        provider_summary[provider_summary["grid_name"]=="ROBUST_R5"]
        .sort_values(["provider_world_id","provider_id"])
        .to_string(index=False)
    )
    print("\nR7 PROVIDER DETAILS")
    print(
        provider_summary[provider_summary["grid_name"]=="ROBUST_R7"]
        .sort_values(["provider_world_id","provider_id"])
        .to_string(index=False)
    )

    manifest=OUT/"crossworld_rho_grid_robustness_manifest.json"
    outputs={
        "candidate_scores":str(scores_path),
        "provider_summary":str(provider_path),
        "world_summary":str(world_path),
        "grid_robustness_summary":str(aggregate_path),
    }
    write_json(manifest,{
        "status":"PHASE6_CROSSWORLD_RHO_GRID_ROBUSTNESS_COMPLETE",
        "posthoc_development_diagnostic":True,
        "worlds":list(WORLDS),
        "providers":list(PROVIDERS),
        "uniform_candidate_bank":"seven frozen Phase-5 V3 candidates per provider",
        "p4_i2a_generated_candidates_included":False,
        "hidden_truth_opened":True,
        "hidden_truth_used_only_for_diagnostics":True,
        "graph_results_read":False,
        "common_rescore_n":100,
        "grids":{k:list(v) for k,v in GRIDS.items()},
        "robustness_priority":[
            "fewest negative providers",
            "largest worst-provider Spearman",
            "largest mean Spearman",
            "best truth rank",
            "smallest mean best-candidate parameter distance",
        ],
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
