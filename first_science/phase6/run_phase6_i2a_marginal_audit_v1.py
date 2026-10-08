"""Phase-6 I2a-full provider-only ambiguity audit.

I2a-full augments I1 with the empirical marginal distribution of cumulative
provider-local compliance c_i(A_i,H) at each frozen I1 region and horizon.

The target distributions are deterministically post-processed from the exact
Phase-5 I1 sigma-estimation corpus.  No new provider-world evidence is acquired.

The same seven frozen V3b candidate surrogate parameters are re-simulated on
the already frozen V3 common N=100 rescore bank only because trajectory-level
compliance samples were not persisted by the I1 sigma-surface artifacts.

This stage never reads graph prediction, Step-0 WB outcomes, graph WB, or final
WB, and performs no graph simulation.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE1=FIRST_SCIENCE/"phase1"
PHASE2=FIRST_SCIENCE/"phase2"
PHASE3=FIRST_SCIENCE/"phase3"
PHASE5=FIRST_SCIENCE/"phase5"
for p in (PHASE1,PHASE2,PHASE3,PHASE5):
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
from phase5_runtime_v2 import (  # noqa:E402
    git_head,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

CFG=HERE/"config_phase6_i2a_marginal_audit_v1.json"
P5_I1=PHASE5/"results"/"01_i1"
P5_V3B=PHASE5/"results"/"03_reconstruction_v3b"
P5_V3_SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
ROOT=HERE/"results"/"01_i2a_marginal_audit"

WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I2A_MARGINAL_AUDIT_V1"
EXPECTED_V3_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3"
TOL=1e-12


def _seed_tuple(block:dict[str,Any])->tuple[int,...]:
    start=int(block["start"])
    end=int(block["end_inclusive"])
    n=int(block["n"])
    seeds=tuple(range(start,end+1))
    if len(seeds)!=n:
        raise RuntimeError("invalid frozen candidate seed bank")
    return seeds


def _regions(metadata:dict[str,Any])->list[dict[str,Any]]:
    rows=[dict(x) for x in metadata["rho_conditioned_regions"]]
    if len(rows)!=5:
        raise RuntimeError(f"expected five frozen I1 regions, found {len(rows)}")
    need={"region_id","region_rho","l_max","c_max","q_min"}
    for r in rows:
        missing=need.difference(r)
        if missing:
            raise RuntimeError(f"I1 region missing {sorted(missing)}")
    return sorted(rows,key=lambda x:(float(x["region_rho"]),str(x["region_id"])))


def _positive_horizons(metadata:dict[str,Any])->list[float]:
    hs=sorted(float(x) for x in metadata["supported_horizons"] if float(x)>0.0)
    if len(hs)!=48 or hs[0]!=5.0 or hs[-1]!=240.0:
        raise RuntimeError("frozen positive I1 horizon grid changed")
    return hs


def _compliance_samples_from_ledger(
    ledger:pd.DataFrame,
    *,
    metadata:dict[str,Any],
)->pd.DataFrame:
    """Return one c_i(A,H) value per trajectory, region and H>0."""
    required={"trajectory","request_id","emission","completion","L","C","Q"}
    missing=required.difference(ledger.columns)
    if missing:
        raise RuntimeError(f"provider ledger missing columns {sorted(missing)}")
    tids=sorted(ledger["trajectory"].astype(int).unique())
    if len(tids)!=100:
        raise RuntimeError(f"expected N=100 provider trajectories, found {len(tids)}")
    workload=dict(metadata["workload_contract"])
    horizons=_positive_horizons(metadata)
    rows=[]
    for region in _regions(metadata):
        for tid in tids:
            one=ledger[ledger["trajectory"].astype(int)==int(tid)].copy()
            decisions=build_request_sla_decision_table(
                one,
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
            for rec in curve.itertuples(index=False):
                rows.append({
                    "region_id":str(region["region_id"]),
                    "region_rho":float(region["region_rho"]),
                    "H":float(rec.horizon),
                    "trajectory_private":int(tid),
                    "compliance_fraction":float(rec.compliance_fraction),
                })
    out=pd.DataFrame(rows)
    expected=5*48*100
    if len(out)!=expected:
        raise RuntimeError(f"expected {expected} compliance samples, found {len(out)}")
    if ((out["compliance_fraction"]<-TOL)|(out["compliance_fraction"]>1.0+TOL)).any():
        raise RuntimeError("compliance fraction outside [0,1]")
    return out


def _publicize_i2a(samples:pd.DataFrame,provider:str)->pd.DataFrame:
    """Sort independently per (region,H), removing all trajectory identity."""
    rows=[]
    for (region_id,region_rho,H),g in samples.groupby(
        ["region_id","region_rho","H"],sort=True
    ):
        vals=np.sort(g["compliance_fraction"].astype(float).to_numpy())
        if len(vals)!=100:
            raise RuntimeError("I2a public group does not contain N=100")
        for rank,value in enumerate(vals,start=1):
            rows.append({
                "provider_id":provider,
                "region_id":str(region_id),
                "region_rho":float(region_rho),
                "H":float(H),
                "sample_rank":int(rank),
                "empirical_cdf_probability":float(rank/len(vals)),
                "compliance_fraction":float(value),
            })
    out=pd.DataFrame(rows).sort_values(
        ["region_rho","H","sample_rank"],kind="mergesort"
    ).reset_index(drop=True)
    if "trajectory_private" in out.columns:
        raise RuntimeError("trajectory identity leaked into public I2a")
    return out


def empirical_w1_equal_n(a:Iterable[float],b:Iterable[float])->float:
    aa=np.sort(np.asarray(tuple(a),dtype=float))
    bb=np.sort(np.asarray(tuple(b),dtype=float))
    if len(aa)==0 or len(aa)!=len(bb):
        raise ValueError("W1 equal-N implementation requires equal nonzero sample counts")
    return float(np.mean(np.abs(aa-bb)))


def _simulate_candidate_samples(
    *,
    metadata:dict[str,Any],
    mean_service_time:float,
    cost_rate:float,
    service_cv:float,
    seeds:tuple[int,...],
)->pd.DataFrame:
    if len(seeds)!=100:
        raise RuntimeError("Phase-6 candidate rescore requires N=100")
    parameters=SingleProviderSurrogateParameters(
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
    )
    provider=str(metadata["provider_id"])
    workload=dict(metadata["workload_contract"])
    pieces=[]
    with open(os.devnull,"w",encoding="utf-8") as devnull:
        with contextlib.redirect_stdout(devnull),contextlib.redirect_stderr(devnull):
            for ordinal,seed in enumerate(seeds):
                ledger=execute_one_single_provider_trajectory(
                    provider_id=provider,
                    parameters=parameters,
                    workload_contract=workload,
                    trajectory_seed=int(seed),
                    canonical_ipt=1_000_000.0,
                    execution_fraction=0.5,
                )
                ledger=ledger.copy()
                ledger["trajectory"]=int(ordinal)
                pieces.append(ledger)
    merged=pd.concat(pieces,ignore_index=True)
    return _compliance_samples_from_ledger(merged,metadata=metadata)


def _score_candidate(
    public_i2a:pd.DataFrame,
    candidate_samples:pd.DataFrame,
)->tuple[float,pd.DataFrame]:
    target_groups={
        (str(rid),float(H)):g["compliance_fraction"].astype(float).to_numpy()
        for (rid,H),g in public_i2a.groupby(["region_id","H"],sort=True)
    }
    candidate_groups={
        (str(rid),float(H)):g["compliance_fraction"].astype(float).to_numpy()
        for (rid,H),g in candidate_samples.groupby(["region_id","H"],sort=True)
    }
    if set(target_groups)!=set(candidate_groups):
        raise RuntimeError("candidate I2a group support differs from provider I2a")
    rows=[]
    for key in sorted(target_groups,key=lambda x:(x[0],x[1])):
        rid,H=key
        pub=public_i2a[
            (public_i2a["region_id"].astype(str)==rid)
            & np.isclose(public_i2a["H"].astype(float),H,atol=TOL,rtol=0.0)
        ]
        rows.append({
            "region_id":rid,
            "region_rho":float(pub["region_rho"].iloc[0]),
            "H":float(H),
            "w1":empirical_w1_equal_n(target_groups[key],candidate_groups[key]),
        })
    groups=pd.DataFrame(rows)
    return float(groups["w1"].mean()),groups


def _spearman_rank(a:pd.Series,b:pd.Series)->float:
    ar=a.rank(method="average")
    br=b.rank(method="average")
    return float(ar.corr(br))


def run_provider(world:str,provider:str,seeds:tuple[int,...])->dict[str,Any]:
    out=ROOT/world/provider
    out.mkdir(parents=True,exist_ok=True)

    manifest_path=out/"i2a_provider_audit_manifest.json"
    if manifest_path.is_file():
        manifest=read_json(manifest_path)
        if manifest.get("status")!="PHASE6_I2A_PROVIDER_AUDIT_COMPLETE":
            raise RuntimeError(f"{world}/{provider}: unexpected existing Phase-6 manifest status")
        d=manifest["diagnostics"]
        print(f"PHASE6 I2A {world}/{provider} reuse completed provider audit",flush=True)
        return {
            "provider_world_id":world,
            "provider_id":provider,
            "best_candidate_id":str(d["i2a_best_candidate_id"]),
            "best_mean_w1":float(d["i2a_best_mean_w1"]),
            "best_second_gap":float(d["i2a_best_second_gap"]),
            "best_worst_range":float(d["i2a_best_worst_range"]),
            "rank_spearman":float(d["i1_i2a_rank_spearman"]),
            "top3_overlap":int(d["i1_i2a_top3_overlap_count"]),
            "wall_seconds":0.0,
            "provider_manifest_sha256":sha256_file(manifest_path),
        }

    card_path=P5_I1/world/"public"/provider/"card.json"
    target_ledger_path=P5_I1/world/"private"/"sigma"/provider/"provider_request_ledgers.csv"
    candidates_path=P5_V3B/world/provider/"m3_provider_models.csv"
    i1_rank_path=P5_V3B/world/provider/"v3b_candidate_quality_ranking.csv"
    for p in (card_path,target_ledger_path,candidates_path,i1_rank_path):
        if not p.is_file():
            raise FileNotFoundError(p)

    metadata=read_json(card_path)
    if str(metadata["provider_id"])!=provider:
        raise RuntimeError(f"{world}/{provider}: card provider mismatch")

    target_ledger=pd.read_csv(target_ledger_path)
    target_private=_compliance_samples_from_ledger(target_ledger,metadata=metadata)
    public_i2a=_publicize_i2a(target_private,provider)
    public_path=out/"i2a_public_empirical_cdf.csv"
    public_i2a.to_csv(public_path,index=False)

    candidates=pd.read_csv(candidates_path)
    if len(candidates)!=7 or candidates["candidate_id"].astype(str).nunique()!=7:
        raise RuntimeError(f"{world}/{provider}: expected seven frozen V3b candidates")
    need={"candidate_id","mean_service_time","cost_rate","service_cv"}
    missing=need.difference(candidates.columns)
    if missing:
        raise RuntimeError(f"V3b candidate table missing {sorted(missing)}")

    i1_rank=pd.read_csv(i1_rank_path)
    if set(i1_rank["candidate_id"].astype(str))!=set(candidates["candidate_id"].astype(str)):
        raise RuntimeError("I1 ranking and candidate family differ")

    score_rows=[]
    group_frames=[]
    wall=time.perf_counter()
    ordered=candidates.sort_values("candidate_id",kind="mergesort").reset_index(drop=True)
    checkpoint_root=out/"checkpoints"
    checkpoint_root.mkdir(parents=True,exist_ok=True)
    for index,rec in enumerate(ordered.itertuples(index=False),start=1):
        cid=str(rec.candidate_id)
        safe_cid=cid.replace("/","_")
        score_cp=checkpoint_root/f"{safe_cid}_score.csv"
        groups_cp=checkpoint_root/f"{safe_cid}_groups.csv"
        if score_cp.is_file() and groups_cp.is_file():
            one=pd.read_csv(score_cp)
            groups=pd.read_csv(groups_cp)
            if len(one)!=1 or str(one.iloc[0]["candidate_id"])!=cid:
                raise RuntimeError(f"{world}/{provider}/{cid}: invalid candidate checkpoint")
            expected_groups=5*48
            if len(groups)!=expected_groups or set(groups["candidate_id"].astype(str))!={cid}:
                raise RuntimeError(f"{world}/{provider}/{cid}: invalid group checkpoint")
            row=one.iloc[0].to_dict()
            score_rows.append(row)
            group_frames.append(groups)
            print(
                f"PHASE6 I2A {world}/{provider} candidate {index}/7 "
                f"{cid} mean_W1={float(row['mean_w1']):.6f} [cached]",
                flush=True,
            )
            continue

        cand_samples=_simulate_candidate_samples(
            metadata=metadata,
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            seeds=seeds,
        )
        mean_w1,groups=_score_candidate(public_i2a,cand_samples)
        groups.insert(0,"candidate_id",cid)
        row={
            "candidate_id":cid,
            "mean_w1":mean_w1,
            "median_group_w1":float(groups["w1"].median()),
            "max_group_w1":float(groups["w1"].max()),
            "mean_service_time":float(rec.mean_service_time),
            "cost_rate":float(rec.cost_rate),
            "service_cv":float(rec.service_cv),
        }
        pd.DataFrame([row]).to_csv(score_cp,index=False)
        groups.to_csv(groups_cp,index=False)
        score_rows.append(row)
        group_frames.append(groups)
        print(
            f"PHASE6 I2A {world}/{provider} candidate {index}/7 "
            f"{cid} mean_W1={mean_w1:.6f}",
            flush=True,
        )

    scores=pd.DataFrame(score_rows).sort_values(
        ["mean_w1","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    scores.insert(0,"i2a_rank",np.arange(1,8,dtype=int))
    scores=scores.merge(
        i1_rank[["candidate_id","v3b_quality_rank","rescore_rmse"]],
        on="candidate_id",how="left",validate="one_to_one",
    )
    # Carry the old M3 rank if available, but do not use old weights in I2a scoring.
    if "weight_rank" in i1_rank.columns:
        scores=scores.merge(
            i1_rank[["candidate_id","weight_rank","weight"]],
            on="candidate_id",how="left",validate="one_to_one",
        )

    old_top3=set(
        i1_rank.sort_values(["v3b_quality_rank","candidate_id"],kind="mergesort")
        .head(3)["candidate_id"].astype(str)
    )
    new_top3=set(scores.head(3)["candidate_id"].astype(str))
    rank_spearman=_spearman_rank(
        scores["i2a_rank"].astype(float),
        scores["v3b_quality_rank"].astype(float),
    )
    best_second_gap=float(scores.iloc[1]["mean_w1"]-scores.iloc[0]["mean_w1"])
    best_worst_range=float(scores.iloc[-1]["mean_w1"]-scores.iloc[0]["mean_w1"])

    scores_path=out/"i2a_candidate_scores.csv"
    groups_path=out/"i2a_candidate_group_scores.csv"
    top3_path=out/"i2a_top3_preview.csv"
    scores.to_csv(scores_path,index=False)
    pd.concat(group_frames,ignore_index=True).to_csv(groups_path,index=False)
    top3=scores.head(3).copy()
    top3["preview_provider_weight"]=1.0/3.0
    top3.to_csv(top3_path,index=False)

    manifest={
        "status":"PHASE6_I2A_PROVIDER_AUDIT_COMPLETE",
        "scientific_role":"provider_only_information_axis_development",
        "provider_world_id":world,
        "provider_id":provider,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "inputs":{
            "phase5_i1_card_sha256":sha256_file(card_path),
            "phase5_i1_sigma_ledger_sha256":sha256_file(target_ledger_path),
            "phase5_v3b_candidate_table_sha256":sha256_file(candidates_path),
            "phase5_v3b_i1_ranking_sha256":sha256_file(i1_rank_path),
            "candidate_seed_start":int(seeds[0]),
            "candidate_seed_end_inclusive":int(seeds[-1]),
            "candidate_n":len(seeds),
            "new_provider_world_simulation":False,
            "candidate_family_refit":False,
            "graph_prediction_read":False,
            "graph_wb_read":False,
            "final_wb_read":False,
            "hidden_provider_parameters_read":False,
        },
        "i2a":{
            "public_sample_count_per_region_horizon":100,
            "region_count":5,
            "positive_horizon_count":48,
            "temporal_identity_exposed":False,
            "metric":"empirical_1d_wasserstein_1",
            "aggregate":"mean over region x H>0",
        },
        "diagnostics":{
            "i2a_best_candidate_id":str(scores.iloc[0]["candidate_id"]),
            "i2a_best_mean_w1":float(scores.iloc[0]["mean_w1"]),
            "i2a_second_mean_w1":float(scores.iloc[1]["mean_w1"]),
            "i2a_best_second_gap":best_second_gap,
            "i2a_best_worst_range":best_worst_range,
            "i1_i2a_rank_spearman":rank_spearman,
            "i1_i2a_top3_overlap_count":int(len(old_top3.intersection(new_top3))),
            "i1_top3_candidate_ids":sorted(old_top3),
            "i2a_top3_candidate_ids":scores.head(3)["candidate_id"].astype(str).tolist(),
        },
        "outputs":{
            "public_i2a":str(public_path),
            "candidate_scores":str(scores_path),
            "group_scores":str(groups_path),
            "top3_preview":str(top3_path),
        },
        "output_hashes_sha256":{
            "public_i2a":sha256_file(public_path),
            "candidate_scores":sha256_file(scores_path),
            "group_scores":sha256_file(groups_path),
            "top3_preview":sha256_file(top3_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-wall),
    }
    manifest_path=out/"i2a_provider_audit_manifest.json"
    write_json(manifest_path,manifest)
    # Candidate checkpoints are deterministic resumability artifacts only.
    # Remove them after the provider audit is frozen.
    if checkpoint_root.exists():
        import shutil
        shutil.rmtree(checkpoint_root)
    return {
        "provider_world_id":world,
        "provider_id":provider,
        "best_candidate_id":manifest["diagnostics"]["i2a_best_candidate_id"],
        "best_mean_w1":manifest["diagnostics"]["i2a_best_mean_w1"],
        "best_second_gap":best_second_gap,
        "best_worst_range":best_worst_range,
        "rank_spearman":rank_spearman,
        "top3_overlap":int(len(old_top3.intersection(new_top3))),
        "wall_seconds":manifest["wall_seconds"],
        "provider_manifest_sha256":sha256_file(manifest_path),
    }


def run_all(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected Phase-6 I2a contract status")
    seeds_cfg=read_json(P5_V3_SEEDS)
    if seeds_cfg.get("status")!=EXPECTED_V3_SEEDS:
        raise RuntimeError("unexpected frozen V3 seed registry")
    seeds=_seed_tuple(seeds_cfg["provider_reconstruction"]["common_rescore"])
    if len(seeds)!=100:
        raise RuntimeError("frozen V3 common rescore bank is not N=100")

    ROOT.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    tasks=[(world,provider) for world in WORLDS for provider in PROVIDERS]
    rows=[]
    if workers==1:
        for world,provider in tasks:
            rows.append(run_provider(world,provider,seeds))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={
                pool.submit(run_provider,world,provider,seeds):(world,provider)
                for world,provider in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                world,provider=futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(
                        f"Phase-6 I2a worker failed for {world}/{provider}"
                    ) from exc

    summary=pd.DataFrame(rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    summary_path=ROOT/"phase6_i2a_provider_audit_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest={
        "status":"PHASE6_I2A_PROVIDER_AUDIT_BATTERY_COMPLETE",
        "stage_id":"I2A_PROVIDER_ONLY_AMBIGUITY_AUDIT",
        "development_evidence":True,
        "code_commit":git_head(),
        "phase6_contract_sha256":sha256_file(CFG),
        "phase5_v3_seed_registry_sha256":sha256_file(P5_V3_SEEDS),
        "provider_world_count":4,
        "provider_count":12,
        "candidate_count_per_provider":7,
        "graph_prediction_run":False,
        "graph_wb_read":False,
        "final_wb_read":False,
        "hidden_provider_parameters_read":False,
        "outputs":{"summary":str(summary_path)},
        "output_hashes_sha256":{"summary":sha256_file(summary_path)},
        "provider_manifest_sha256":{
            f"{r['provider_world_id']}/{r['provider_id']}":r["provider_manifest_sha256"]
            for r in rows
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
        "workers":int(workers),
    }
    path=ROOT/"phase6_i2a_provider_audit_manifest.json"
    write_json(path,manifest)

    print("\\nPHASE6_I2A_PROVIDER_AUDIT_PASS")
    print(summary.to_string(index=False))
    print("graph_prediction_run False")
    print("graph_wb_read False")
    print("manifest",path)
    return path


def main()->None:
    p=argparse.ArgumentParser(description="Phase-6 I2a provider-only ambiguity audit")
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    run_all(args.workers)


if __name__=="__main__":
    main()