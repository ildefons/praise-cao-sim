"""Phase-6 cross-world full-spectrum I2a survival-loss audit.

Development-only diagnostic.

I2a exposes, for every provider region A and horizon H, the empirical
distribution of cumulative compliance c(A,H).  Therefore it also exposes the
entire marginal survival curve

    sigma(A,H;rho) = P(c(A,H) >= rho),   rho in [0,1].

This audit evaluates the direct continuum generalization of the I1 fitting
criterion:

    L_full(theta)^2 =
        mean_{A,H} integral_0^1
        [sigma_theta(A,H;rho)-sigma_I2a(A,H;rho)]^2 d rho.

The integral is computed exactly for the two empirical step functions, using
their pooled breakpoints.  No rho grid is introduced.

Scope:
- P1-P4 x ProviderA-C (12 provider instances),
- hidden synthetic truth + seven frozen Phase-5 V3 candidates per provider,
- frozen V3 common N=100 rescore bank,
- provider-only diagnostic; no graph simulation or graph result is read.

Hidden truth is opened only for development diagnostics such as parameter
distance and truth rank.  It is never used to fit, alter, or select a
candidate during simulation.
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
GRID_ROOT=HERE/"results"/"12_crossworld_rho_grid_robustness"
OUT=HERE/"results"/"13_crossworld_full_spectrum_sigma_loss"
CHECKPOINTS=OUT/"checkpoints"

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
    def zlog(v,lo,hi):
        return (
            math.log(float(v))-math.log(float(lo))
        )/(
            math.log(float(hi))-math.log(float(lo))
        )
    return np.asarray([
        zlog(theta["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"]),
        zlog(theta["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"]),
        (float(theta["service_cv"])-float(domain["service_cv_lower"]))/
        (float(domain["service_cv_upper"])-float(domain["service_cv_lower"])),
    ],dtype=float)


def _distance(theta:dict[str,float],truth:dict[str,float],domain:pd.Series)->float:
    return float(np.linalg.norm(_znorm(theta,domain)-_znorm(truth,domain)))


def _candidate_table(world:str,provider:str,truth:dict[str,float],domain:pd.Series)->pd.DataFrame:
    path=V3_ROOT/world/provider/"v3_candidates_rescore.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    t=pd.read_csv(path)
    need={"candidate_id","mean_service_time","cost_rate","service_cv"}
    if len(t)!=7 or not need.issubset(t.columns):
        raise RuntimeError(f"{world}/{provider}: expected seven parameterized V3 candidates")

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


def _load_target(world:str,provider:str)->dict[tuple[str,float],np.ndarray]:
    path=I2A_ROOT/world/provider/"i2a_public_empirical_cdf.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df=pd.read_csv(path)
    need={"provider_id","region_id","H","compliance_fraction"}
    if not need.issubset(df.columns):
        raise RuntimeError(f"{world}/{provider}: public I2a target missing columns")
    if set(df["provider_id"].astype(str))!={provider}:
        raise RuntimeError(f"{world}/{provider}: target provider mismatch")

    out={}
    for (rid,H),g in df.groupby(["region_id","H"],sort=True):
        vals=np.sort(g["compliance_fraction"].astype(float).to_numpy())
        if len(vals)!=100:
            raise RuntimeError(f"{world}/{provider}/{rid}/{H}: target N !=100")
        if np.any(vals < -TOL) or np.any(vals > 1.0+TOL):
            raise RuntimeError("target compliance outside [0,1]")
        out[(str(rid),float(H))]=vals
    if len(out)!=5*48:
        raise RuntimeError(f"{world}/{provider}: expected 240 target groups")
    return out


def _candidate_groups(samples:pd.DataFrame)->dict[tuple[str,float],np.ndarray]:
    out={}
    for (rid,H),g in samples.groupby(["region_id","H"],sort=True):
        vals=np.sort(g["compliance_fraction"].astype(float).to_numpy())
        if len(vals)!=100:
            raise RuntimeError(f"candidate {rid}/{H}: N !=100")
        if np.any(vals < -TOL) or np.any(vals > 1.0+TOL):
            raise RuntimeError("candidate compliance outside [0,1]")
        out[(str(rid),float(H))]=vals
    if len(out)!=5*48:
        raise RuntimeError("candidate does not contain 240 region-horizon groups")
    return out


def integrated_survival_sq(a:np.ndarray,b:np.ndarray)->float:
    """Exact integral_0^1 [S_a(rho)-S_b(rho)]^2 d rho for empirical samples."""
    aa=np.sort(np.asarray(a,dtype=float))
    bb=np.sort(np.asarray(b,dtype=float))
    if len(aa)==0 or len(bb)==0:
        raise ValueError("empty empirical distribution")
    breaks=np.unique(np.concatenate((np.asarray([0.0,1.0]),aa,bb)))
    breaks=breaks[(breaks>=0.0)&(breaks<=1.0)]
    if len(breaks)<2:
        return 0.0
    left=breaks[:-1]
    right=breaks[1:]
    width=right-left
    positive=width>0.0
    if not np.any(positive):
        return 0.0
    mid=(left[positive]+right[positive])/2.0

    # The empirical survival is constant between pooled breakpoints.
    sa=(len(aa)-np.searchsorted(aa,mid,side="left"))/float(len(aa))
    sb=(len(bb)-np.searchsorted(bb,mid,side="left"))/float(len(bb))
    return float(np.sum(width[positive]*(sa-sb)**2))


def _score_groups(
    target:dict[tuple[str,float],np.ndarray],
    candidate:dict[tuple[str,float],np.ndarray],
)->pd.DataFrame:
    if set(target)!=set(candidate):
        raise RuntimeError("target/candidate group supports differ")
    rows=[]
    for rid,H in sorted(target,key=lambda x:(x[0],x[1])):
        integ=integrated_survival_sq(target[(rid,H)],candidate[(rid,H)])
        rows.append({
            "region_id":rid,
            "H":float(H),
            "integrated_squared_survival_error":float(integ),
        })
    return pd.DataFrame(rows)


def _checkpoint_path(row_id:str)->Path:
    safe=row_id.replace("::","__").replace("/","_")
    return CHECKPOINTS/f"{safe}.csv"


def _simulate_and_score(payload:dict[str,Any])->dict[str,Any]:
    cp=Path(payload["checkpoint"])
    if cp.is_file():
        frame=pd.read_csv(cp)
        if len(frame)!=5*48:
            raise RuntimeError(f"invalid checkpoint row count: {cp}")
        if set(frame["row_id"].astype(str))!={payload["row_id"]}:
            raise RuntimeError(f"invalid checkpoint row id: {cp}")
        return {"row_id":payload["row_id"],"checkpoint":str(cp),"cached":True}

    samples=_simulate_candidate_samples(
        metadata=payload["metadata"],
        mean_service_time=float(payload["theta"]["mean_service_time"]),
        cost_rate=float(payload["theta"]["cost_rate"]),
        service_cv=float(payload["theta"]["service_cv"]),
        seeds=tuple(payload["seeds"]),
    )
    groups=_score_groups(payload["target"],_candidate_groups(samples))
    groups.insert(0,"row_id",payload["row_id"])
    groups.insert(1,"source",payload["source"])
    groups["full_spectrum_mse"]=float(groups["integrated_squared_survival_error"].mean())
    groups["full_spectrum_rmse"]=float(
        math.sqrt(groups["integrated_squared_survival_error"].mean())
    )

    cp.parent.mkdir(parents=True,exist_ok=True)
    tmp=cp.with_suffix(".tmp")
    groups.to_csv(tmp,index=False)
    os.replace(tmp,cp)
    return {"row_id":payload["row_id"],"checkpoint":str(cp),"cached":False}


def _spearman(a:pd.Series,b:pd.Series)->float:
    return float(a.rank(method="average").corr(b.rank(method="average")))


def _w1_provider_summary(
    *,
    world:str,
    provider:str,
    meta:pd.DataFrame,
)->dict[str,Any]:
    path=I2A_ROOT/world/provider/"i2a_candidate_scores.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    w=pd.read_csv(path)
    if "mean_w1" not in w.columns or "candidate_id" not in w.columns:
        raise RuntimeError(f"{world}/{provider}: malformed W1 score file")
    cand=meta[meta["source"]=="V3_CANDIDATE"][
        ["candidate_id","parameter_distance"]
    ].merge(
        w[["candidate_id","mean_w1"]],
        on="candidate_id",how="inner",validate="one_to_one",
    )
    if len(cand)!=7:
        raise RuntimeError(f"{world}/{provider}: W1 merge did not recover seven candidates")
    best=cand.sort_values(["mean_w1","candidate_id"],kind="mergesort").iloc[0]
    return {
        "criterion":"W1",
        "provider_world_id":world,
        "provider_id":provider,
        "spearman_loss_vs_parameter_distance":_spearman(
            cand["mean_w1"],cand["parameter_distance"]
        ),
        "best_candidate_id":str(best["candidate_id"]),
        "best_candidate_parameter_distance":float(best["parameter_distance"]),
    }


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
            target=_load_target(world,provider)
            targets[(world,provider)]=target
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
                    "target":target,
                    "checkpoint":str(_checkpoint_path(str(rec.row_id))),
                })

    if len(payloads)!=12*8:
        raise RuntimeError(f"expected 96 truth/candidate rows, found {len(payloads)}")

    results=[]
    if workers==1:
        for i,p in enumerate(payloads,1):
            r=_simulate_and_score(p)
            results.append(r)
            status="cached" if r["cached"] else "simulated"
            print(f"FULL SPECTRUM {i}/96 {r['row_id']} [{status}]",flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(_simulate_and_score,p):p["row_id"] for p in payloads}
            done=0
            for fut in concurrent.futures.as_completed(futures):
                rid=futures[fut]
                try:
                    r=fut.result()
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"full-spectrum scoring failed for {rid}") from exc
                results.append(r)
                done+=1
                status="cached" if r["cached"] else "simulated"
                print(f"FULL SPECTRUM {done}/96 {rid} [{status}]",flush=True)

    row_score={}
    group_frames=[]
    for r in results:
        g=pd.read_csv(r["checkpoint"])
        group_frames.append(g)
        vals=g["full_spectrum_rmse"].astype(float).unique()
        if len(vals)!=1:
            raise RuntimeError(f"{r['row_id']}: checkpoint contains inconsistent RMSE")
        row_score[str(r["row_id"])]=float(vals[0])

    meta_all=pd.concat(tables,ignore_index=True)
    score_rows=[]
    provider_rows=[]
    criterion_rows=[]

    for (world,provider),meta in meta_all.groupby(
        ["provider_world_id","provider_id"],sort=True
    ):
        local=meta.copy()
        local["full_spectrum_rmse"]=[
            row_score[str(x)] for x in local["row_id"].astype(str)
        ]
        score_rows.append(local)

        truth=local[local["source"]=="TRUE"].iloc[0]
        cand=local[local["source"]=="V3_CANDIDATE"].copy()
        ranked=local.sort_values(
            ["full_spectrum_rmse","row_id"],kind="mergesort"
        ).reset_index(drop=True)
        ti=np.flatnonzero(ranked["source"].astype(str).to_numpy()=="TRUE")
        if len(ti)!=1:
            raise RuntimeError("truth rank lookup failed")

        best=cand.sort_values(
            ["full_spectrum_rmse","candidate_id"],kind="mergesort"
        ).iloc[0]
        closest=cand.sort_values(
            ["parameter_distance","candidate_id"],kind="mergesort"
        ).iloc[0]
        ranked_c=cand.sort_values(
            ["full_spectrum_rmse","candidate_id"],kind="mergesort"
        ).reset_index(drop=True)
        ci=np.flatnonzero(
            ranked_c["candidate_id"].astype(str).to_numpy()
            == str(closest["candidate_id"])
        )
        if len(ci)!=1:
            raise RuntimeError("closest candidate rank lookup failed")

        full_row={
            "criterion":"FULL_SPECTRUM",
            "provider_world_id":str(world),
            "provider_id":str(provider),
            "truth_rmse":float(truth["full_spectrum_rmse"]),
            "truth_rank_all8":int(ti[0])+1,
            "spearman_loss_vs_parameter_distance":_spearman(
                cand["full_spectrum_rmse"],cand["parameter_distance"]
            ),
            "best_candidate_id":str(best["candidate_id"]),
            "best_candidate_rmse":float(best["full_spectrum_rmse"]),
            "best_candidate_parameter_distance":float(best["parameter_distance"]),
            "closest_candidate_id":str(closest["candidate_id"]),
            "closest_candidate_distance":float(closest["parameter_distance"]),
            "closest_candidate_rmse":float(closest["full_spectrum_rmse"]),
            "closest_candidate_loss_rank":int(ci[0])+1,
        }
        provider_rows.append(full_row)
        criterion_rows.append({
            k:full_row[k] for k in (
                "criterion","provider_world_id","provider_id",
                "spearman_loss_vs_parameter_distance",
                "best_candidate_id","best_candidate_parameter_distance",
            )
        })
        criterion_rows.append(_w1_provider_summary(
            world=str(world),provider=str(provider),meta=meta
        ))

    scores=pd.concat(score_rows,ignore_index=True)
    provider_summary=pd.DataFrame(provider_rows)
    criterion_compare=pd.DataFrame(criterion_rows)

    # Add the already-computed fixed-grid criteria when available.
    old_provider_path=GRID_ROOT/"crossworld_provider_summary.csv"
    if old_provider_path.is_file():
        old=pd.read_csv(old_provider_path)
        needed={
            "grid_name","provider_world_id","provider_id",
            "spearman_loss_vs_parameter_distance",
            "best_candidate_id","best_candidate_parameter_distance",
        }
        if needed.issubset(old.columns):
            old=old[list(needed)].copy()
            old=old.rename(columns={"grid_name":"criterion"})
            criterion_compare=pd.concat([criterion_compare,old],ignore_index=True)

    criterion_aggregate=criterion_compare.groupby("criterion",as_index=False).agg(
        mean_spearman=("spearman_loss_vs_parameter_distance","mean"),
        median_spearman=("spearman_loss_vs_parameter_distance","median"),
        min_spearman=("spearman_loss_vs_parameter_distance","min"),
        positive_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x>0).sum())),
        nonnegative_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x>=0).sum())),
        negative_provider_count=("spearman_loss_vs_parameter_distance",lambda x:int((x<0).sum())),
        mean_best_candidate_parameter_distance=("best_candidate_parameter_distance","mean"),
    ).sort_values(
        ["negative_provider_count","min_spearman","mean_spearman"],
        ascending=[True,False,False],kind="mergesort",
    ).reset_index(drop=True)
    criterion_aggregate.insert(
        0,"robustness_rank",np.arange(1,len(criterion_aggregate)+1,dtype=int)
    )

    scores_path=OUT/"full_spectrum_candidate_scores.csv"
    groups_path=OUT/"full_spectrum_group_scores.csv"
    provider_path=OUT/"full_spectrum_provider_summary.csv"
    compare_path=OUT/"criterion_provider_comparison.csv"
    aggregate_path=OUT/"criterion_robustness_comparison.csv"

    scores.to_csv(scores_path,index=False)
    pd.concat(group_frames,ignore_index=True).to_csv(groups_path,index=False)
    provider_summary.to_csv(provider_path,index=False)
    criterion_compare.to_csv(compare_path,index=False)
    criterion_aggregate.to_csv(aggregate_path,index=False)

    print("\nPHASE6_CROSSWORLD_FULL_SPECTRUM_SIGMA_LOSS_PASS")
    print("\nCRITERION ROBUSTNESS ACROSS 12 PROVIDERS")
    print(criterion_aggregate.to_string(index=False))
    print("\nFULL-SPECTRUM PROVIDER DETAILS")
    print(
        provider_summary.sort_values(
            ["provider_world_id","provider_id"],kind="mergesort"
        ).to_string(index=False)
    )

    manifest=OUT/"full_spectrum_sigma_loss_manifest.json"
    outputs={
        "candidate_scores":str(scores_path),
        "group_scores":str(groups_path),
        "provider_summary":str(provider_path),
        "criterion_provider_comparison":str(compare_path),
        "criterion_robustness_comparison":str(aggregate_path),
    }
    write_json(manifest,{
        "status":"PHASE6_CROSSWORLD_FULL_SPECTRUM_SIGMA_LOSS_COMPLETE",
        "posthoc_development_diagnostic":True,
        "criterion":"sqrt(mean_{A,H} integral_0^1 (sigma_candidate-sigma_I2a)^2 d rho)",
        "integral":"exact over pooled empirical step-function breakpoints",
        "rho_grid_used":False,
        "worlds":list(WORLDS),
        "providers":list(PROVIDERS),
        "uniform_candidate_bank":"seven frozen Phase-5 V3 candidates per provider",
        "hidden_truth_opened":True,
        "hidden_truth_used_only_for_diagnostics":True,
        "graph_results_read":False,
        "common_rescore_n":100,
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
