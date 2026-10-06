"""Scientific Phase-5 V3 provider reconstruction.

V3 is a pre-graph-WB method-development restart.  It creates seven independent
provider fits using fresh search banks, re-scores all seven on one fresh common
N=100 bank, ranks them by behavioral centrality, instantiates M1 from rank 1,
M2 from ranks 1..3, and M3 from all seven using the frozen KL-Gibbs rule.
A second fresh N=100 replay is diagnostic only.

This runner never reads Step-0 WB values, graph predictions, graph WB, final WB,
or hidden provider parameters.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE3=FIRST_SCIENCE/"phase3"
if str(PHASE3) not in sys.path:
    sys.path.insert(0,str(PHASE3))

from run_m1_provider_lift_v2 import _load_optuna, _simulate_and_score
from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row, _load_public_card
from phase5_reconstruction_v3_selection import (
    gibbs_weights,
    joint_product_support,
    rank_by_behavioral_centroid,
)
from phase5_runtime_v2 import (
    canonical_provider_world_ids,
    git_head,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

PROVIDERS=("ProviderA","ProviderB","ProviderC")
CFG=HERE/"config_phase5_provider_reconstruction_v3.json"
SEEDS=HERE/"config_phase5_seed_registry_v3.json"
DOMAIN_REGISTRY=HERE/"results"/"03_reconstruction"/"phase5_m1_domain_registry.csv"
STEP0_ELIGIBILITY=HERE/"results"/"02_step0"/"phase5_step0_eligibility_manifest.json"
DEFAULT_ROOT=HERE/"results"/"03_reconstruction_v3"
EXPECTED_CFG="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3"
EXPECTED_SEEDS="FROZEN_PHASE5_SEED_REGISTRY_V3"


def _seed_tuple(block:dict[str,Any])->tuple[int,...]:
    start=int(block["start"]); end=int(block["end_inclusive"]); n=int(block["n"])
    out=tuple(range(start,end+1))
    if len(out)!=n:
        raise RuntimeError(f"invalid V3 seed block {start}..{end}; expected n={n}")
    return out


def _v3_objects()->tuple[dict[str,Any],dict[str,Any]]:
    cfg=read_json(CFG); seeds=read_json(SEEDS)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected V3 reconstruction contract status")
    if seeds.get("status")!=EXPECTED_SEEDS:
        raise RuntimeError("unexpected V3 seed-registry status")
    return cfg,seeds


def _require_prerequisites()->None:
    contracts=load_phase5_contracts(HERE)
    if not STEP0_ELIGIBILITY.is_file():
        raise FileNotFoundError(STEP0_ELIGIBILITY)
    step0=read_json(STEP0_ELIGIBILITY)
    if step0.get("status")!="FROZEN_PHASE5_STEP0_ELIGIBILITY_MAP_V2":
        raise RuntimeError("Step-0 eligibility map is not frozen")
    if int(step0.get("n_eligible_cells",-1))+int(step0.get("n_gate_failed_cells",-1))!=16:
        raise RuntimeError("Step-0 eligibility map does not cover all 16 physical cells")
    if not DOMAIN_REGISTRY.is_file():
        raise FileNotFoundError(DOMAIN_REGISTRY)
    table=pd.read_csv(DOMAIN_REGISTRY)
    expected={(w,p) for w in canonical_provider_world_ids(contracts) for p in PROVIDERS}
    actual=set(zip(table["provider_world_id"].astype(str),table["provider_id"].astype(str)))
    if actual!=expected:
        raise RuntimeError("V2 frozen domain registry does not cover the 12 V3 providers")


def _manifest(
    *,
    status:str,
    inputs:dict[str,Any],
    seed_banks:dict[str,Any],
    outputs:dict[str,str],
    started_utc:str,
)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    return {
        "status":status,
        "stage_id":"RECONSTRUCTION_V3",
        "protocol_version":"PHASE5_PROVIDER_RECONSTRUCTION_V3_2026-10-06",
        "scientific_evidence":True,
        "battery_config_sha256":contracts.hashes["battery"],
        "v2_execution_contract_sha256":contracts.hashes["execution"],
        "v2_analysis_contract_sha256":contracts.hashes["analysis"],
        "v3_reconstruction_contract_sha256":sha256_file(CFG),
        "v3_seed_registry_sha256":sha256_file(SEEDS),
        "v2_domain_registry_sha256":sha256_file(DOMAIN_REGISTRY),
        "code_commit":git_head(),
        "inputs":inputs,
        "seed_banks":seed_banks,
        "outputs":outputs,
        "output_hashes_sha256":{
            k:sha256_file(Path(v)) for k,v in outputs.items() if Path(v).is_file()
        },
        "started_utc":started_utc,
        "completed_utc":utc_now_iso(),
    }


def _fit_one(
    *,
    world:str,
    provider:str,
    fit_index:int,
    metadata,
    public_surface,
    bounds,
    sampler_seed:int,
    trajectory_seeds:tuple[int,...],
    out_dir:Path,
    n_trials:int,
    n_startup:int,
)->dict[str,Any]:
    winner_path=out_dir/"winner.json"
    trials_path=out_dir/"trials.csv"
    if winner_path.is_file() and trials_path.is_file():
        winner=read_json(winner_path)
        if (
            winner.get("status")=="FROZEN_PHASE5_V3_FIT_WINNER"
            and int(winner.get("fit_index",-1))==fit_index
            and int(winner.get("sampler_seed",-1))==sampler_seed
            and int(winner.get("search_seed_start",-1))==trajectory_seeds[0]
            and int(winner.get("search_seed_end_inclusive",-1))==trajectory_seeds[-1]
            and int(winner.get("search_n",-1))==len(trajectory_seeds)
            and int(winner.get("n_trials",-1))==n_trials
            and int(winner.get("n_startup_trials",-1))==n_startup
        ):
            return winner
        raise RuntimeError(f"{world}/{provider}/fit{fit_index}: incompatible checkpoint")

    out_dir.mkdir(parents=True,exist_ok=True)
    optuna=_load_optuna()
    sampler=optuna.samplers.TPESampler(seed=sampler_seed,n_startup_trials=n_startup)
    study=optuna.create_study(direction="minimize",sampler=sampler)
    started=time.perf_counter()
    best_seen=float("inf")

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
        metrics,_,_=_simulate_and_score(
            metadata=metadata,
            public_surface=public_surface,
            mean_service_time=mu,
            cost_rate=kappa,
            service_cv=cv,
            trajectory_seeds=trajectory_seeds,
            canonical_ipt=1_000_000.0,
            execution_fraction=0.5,
            quiet=True,
        )
        trial.set_user_attr("rmse",float(metrics["rmse"]))
        trial.set_user_attr("mae",float(metrics["mae"]))
        trial.set_user_attr("bias",float(metrics["bias"]))
        trial.set_user_attr("max_abs_error",float(metrics["max_abs_error"]))
        return float(metrics["mse"])

    def progress(_,trial):
        nonlocal best_seen
        if trial.value is None:
            return
        done=int(trial.number)+1
        value=float(trial.value)
        improved=value<best_seen-1e-15
        if improved:
            best_seen=value
        if improved or done==1 or done%5==0 or done==n_trials:
            elapsed=time.perf_counter()-started
            eta=(elapsed/done)*(n_trials-done)
            print(
                f"V3 FIT {world}/{provider} {fit_index}/7 "
                f"trial {done}/{n_trials} best_mse={best_seen:.6g} "
                f"elapsed={elapsed/60:.1f}m ETA={eta/60:.1f}m",
                flush=True,
            )

    study.optimize(
        objective,n_trials=n_trials,callbacks=[progress],show_progress_bar=False
    )

    trial_rows=[]
    for t in study.trials:
        if t.value is None or not t.params:
            continue
        trial_rows.append({
            "trial_number":int(t.number),
            "search_mse":float(t.value),
            "search_rmse":float(t.user_attrs.get("rmse",math.sqrt(float(t.value)))),
            "search_mae":float(t.user_attrs.get("mae",np.nan)),
            "search_bias":float(t.user_attrs.get("bias",np.nan)),
            "search_max_abs_error":float(t.user_attrs.get("max_abs_error",np.nan)),
            "mean_service_time":float(t.params["mean_service_time"]),
            "cost_rate":float(t.params["cost_rate"]),
            "service_cv":float(t.params["service_cv"]),
        })
    trials=pd.DataFrame(trial_rows).sort_values(
        ["search_mse","trial_number"],kind="mergesort"
    ).reset_index(drop=True)
    trials.to_csv(trials_path,index=False)
    if len(trials)!=n_trials:
        raise RuntimeError(
            f"{world}/{provider}/fit{fit_index}: expected {n_trials} completed trials"
        )
    best=trials.iloc[0]
    winner={
        "status":"FROZEN_PHASE5_V3_FIT_WINNER",
        "provider_world_id":world,
        "provider_id":provider,
        "fit_index":fit_index,
        "candidate_id":f"{world}_{provider}_V3_FIT{fit_index}",
        "sampler_seed":sampler_seed,
        "search_seed_start":trajectory_seeds[0],
        "search_seed_end_inclusive":trajectory_seeds[-1],
        "search_n":len(trajectory_seeds),
        "n_trials":n_trials,
        "n_startup_trials":n_startup,
        "selected_trial_number":int(best["trial_number"]),
        "search_mse":float(best["search_mse"]),
        "search_rmse":float(best["search_rmse"]),
        "mean_service_time":float(best["mean_service_time"]),
        "cost_rate":float(best["cost_rate"]),
        "service_cv":float(best["service_cv"]),
        "trials_sha256":sha256_file(trials_path),
    }
    write_json(winner_path,winner)
    return winner


def _evaluate_candidate(
    *,
    candidate:dict[str,Any],
    metadata,
    public_surface,
    seeds:tuple[int,...],
)->tuple[dict[str,float],pd.DataFrame,pd.DataFrame]:
    metrics,simulated,comparison=_simulate_and_score(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=float(candidate["mean_service_time"]),
        cost_rate=float(candidate["cost_rate"]),
        service_cv=float(candidate["service_cv"]),
        trajectory_seeds=seeds,
        canonical_ipt=1_000_000.0,
        execution_fraction=0.5,
        quiet=True,
    )
    return (
        {k:(int(v) if k=="n_points" else float(v)) for k,v in metrics.items()},
        simulated,
        comparison.sort_values(
            ["region_rho","rho","horizon"],kind="mergesort"
        ).reset_index(drop=True),
    )


def _run_provider(world:str,provider:str,result_root:str)->dict[str,Any]:
    cfg,seeds_cfg=_v3_objects()
    root=Path(result_root).resolve()/world/provider
    freeze_path=root/"provider_freeze_manifest.json"
    if freeze_path.is_file():
        m=read_json(freeze_path)
        if m.get("status")=="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION":
            return {
                "world":world,"provider":provider,"status":m["status"],
                "wall_seconds":0.0,"reused_freeze":True,
            }
        raise RuntimeError(f"{world}/{provider}: unexpected V3 provider freeze")

    started_utc=utc_now_iso()
    wall=time.perf_counter()
    root.mkdir(parents=True,exist_ok=True)
    metadata,public_surface,card_rec=_load_public_card(world,provider)
    domain_row=_domain_row(world,provider)
    bounds=_bounds(domain_row)

    rec_cfg=cfg["candidate_reconstruction"]
    nfits=int(rec_cfg["independent_fit_count"])
    if nfits!=7 or int(rec_cfg["candidate_count_per_provider"])!=7:
        raise RuntimeError("V3 requires seven candidates per provider")
    n_trials=int(rec_cfg["trials_per_fit"])
    n_startup=int(rec_cfg["startup_trials_per_fit"])
    sampler_seeds=[int(x) for x in rec_cfg["fit_sampler_seeds"]]
    if len(sampler_seeds)!=nfits:
        raise RuntimeError("V3 fit sampler-seed count mismatch")

    winners=[]
    seed_manifest={}
    for fit_index in range(1,nfits+1):
        key=f"fit_{fit_index}_search"
        bank=_seed_tuple(seeds_cfg["provider_reconstruction"][key])
        seed_manifest[key]={
            "start":bank[0],"end_inclusive":bank[-1],"n":len(bank)
        }
        winner=_fit_one(
            world=world,provider=provider,fit_index=fit_index,
            metadata=metadata,public_surface=public_surface,bounds=bounds,
            sampler_seed=sampler_seeds[fit_index-1],
            trajectory_seeds=bank,
            out_dir=root/"fits"/f"fit_{fit_index}",
            n_trials=n_trials,n_startup=n_startup,
        )
        winners.append(winner)

    rescore_seeds=_seed_tuple(seeds_cfg["provider_reconstruction"]["common_rescore"])
    replay_seeds=_seed_tuple(seeds_cfg["provider_reconstruction"]["common_replay"])
    seed_manifest["common_rescore"]={
        "start":rescore_seeds[0],"end_inclusive":rescore_seeds[-1],"n":len(rescore_seeds)
    }
    seed_manifest["common_replay"]={
        "start":replay_seeds[0],"end_inclusive":replay_seeds[-1],"n":len(replay_seeds)
    }

    rescore_rows=[]
    replay_rows=[]
    surface_rows=[]
    vectors=[]
    public_vector=None
    for idx,winner in enumerate(winners,start=1):
        cid=str(winner["candidate_id"])
        rescore_metrics,_,comparison=_evaluate_candidate(
            candidate=winner,metadata=metadata,public_surface=public_surface,
            seeds=rescore_seeds,
        )
        replay_metrics,_,_=_evaluate_candidate(
            candidate=winner,metadata=metadata,public_surface=public_surface,
            seeds=replay_seeds,
        )
        if public_vector is None:
            public_vector=comparison["sigma_i1"].to_numpy(float)
        candidate_vector=comparison["sigma_m1_local"].to_numpy(float)
        vectors.append(candidate_vector)
        rescore_rows.append({
            "candidate_id":cid,
            "fit_index":int(winner["fit_index"]),
            "search_mse":float(winner["search_mse"]),
            "search_rmse":float(winner["search_rmse"]),
            "mean_service_time":float(winner["mean_service_time"]),
            "cost_rate":float(winner["cost_rate"]),
            "service_cv":float(winner["service_cv"]),
            "rescore_mse":float(rescore_metrics["mse"]),
            "rescore_rmse":float(rescore_metrics["rmse"]),
            "rescore_mae":float(rescore_metrics["mae"]),
            "rescore_bias":float(rescore_metrics["bias"]),
            "rescore_max_abs_error":float(rescore_metrics["max_abs_error"]),
        })
        replay_rows.append({
            "candidate_id":cid,
            "fit_index":int(winner["fit_index"]),
            "replay_mse":float(replay_metrics["mse"]),
            "replay_rmse":float(replay_metrics["rmse"]),
            "replay_mae":float(replay_metrics["mae"]),
            "replay_bias":float(replay_metrics["bias"]),
            "replay_max_abs_error":float(replay_metrics["max_abs_error"]),
        })
        surf=comparison[
            ["provider_id","region_id","region_rho","rho","horizon","sigma_i1","sigma_m1_local"]
        ].copy()
        surf.insert(0,"candidate_id",cid)
        surface_rows.append(surf)
        print(
            f"V3 RESCORE {world}/{provider} {idx}/7 {cid} "
            f"rmse={rescore_metrics['rmse']:.6g} replay_rmse={replay_metrics['rmse']:.6g}",
            flush=True,
        )

    if public_vector is None:
        raise RuntimeError(f"{world}/{provider}: empty public-I1 comparison")
    vectors_arr=np.asarray(vectors,dtype=float)
    ids=[str(w["candidate_id"]) for w in winners]
    ranking=rank_by_behavioral_centroid(ids,vectors_arr,public_vector)
    weights=gibbs_weights(
        ids,vectors_arr,public_vector,
        n_public=100,n_candidate=len(rescore_seeds),
        lam=float(cfg["methods"]["M3"]["gibbs_lambda"]),
    )

    rescore=pd.DataFrame(rescore_rows).merge(
        ranking[["candidate_id","behavioral_rank","centroid_mse"]],
        on="candidate_id",how="left",validate="one_to_one",
    ).merge(
        weights[["candidate_id","weight_rank","kl_energy","weight"]],
        on="candidate_id",how="left",validate="one_to_one",
    ).sort_values("behavioral_rank",kind="mergesort").reset_index(drop=True)
    replay=pd.DataFrame(replay_rows).merge(
        ranking[["candidate_id","behavioral_rank"]],
        on="candidate_id",how="left",validate="one_to_one",
    ).sort_values("behavioral_rank",kind="mergesort").reset_index(drop=True)
    surfaces=pd.concat(surface_rows,ignore_index=True)

    candidates_path=root/"v3_candidates_rescore.csv"
    replay_path=root/"v3_candidates_replay.csv"
    surfaces_path=root/"v3_common_rescore_surfaces.csv"
    rescore.to_csv(candidates_path,index=False)
    replay.to_csv(replay_path,index=False)
    surfaces.to_csv(surfaces_path,index=False)

    m1=rescore.head(1).copy()
    m1.insert(0,"method_id","M1")
    m1_path=root/"m1_provider_model.csv"
    m1.to_csv(m1_path,index=False)

    m2=rescore.head(3).copy()
    m2.insert(0,"method_id","M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=root/"m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    m3=rescore.sort_values("weight_rank",kind="mergesort").copy()
    m3.insert(0,"method_id","M3")
    m3_path=root/"m3_provider_models.csv"
    m3.to_csv(m3_path,index=False)

    outputs={
        "candidates_rescore":str(candidates_path),
        "candidates_replay":str(replay_path),
        "common_rescore_surfaces":str(surfaces_path),
        "m1_provider_model":str(m1_path),
        "m2_provider_models":str(m2_path),
        "m3_provider_models":str(m3_path),
    }
    manifest=_manifest(
        status="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION",
        inputs={
            "provider_world_id":world,
            "provider_id":provider,
            "public_card_json_sha256":card_rec["card_json_sha256"],
            "public_sigma_surface_sha256":card_rec["sigma_surface_sha256"],
            "frozen_domain":{
                "mean_service_time_lower":float(domain_row["mean_service_time_lower"]),
                "mean_service_time_upper":float(domain_row["mean_service_time_upper"]),
                "cost_rate_lower":float(domain_row["cost_rate_lower"]),
                "cost_rate_upper":float(domain_row["cost_rate_upper"]),
                "service_cv_lower":float(domain_row["service_cv_lower"]),
                "service_cv_upper":float(domain_row["service_cv_upper"]),
            },
            "hidden_provider_parameters_used":False,
            "step0_WB_values_used":False,
            "graph_prediction_used":False,
            "graph_WB_used":False,
            "final_WB_used":False,
            "v2_reconstruction_evidence_used":False,
            "hard_rmse_compatibility_gate":False,
        },
        seed_banks=seed_manifest,
        outputs=outputs,
        started_utc=started_utc,
    )
    manifest["n_candidates"]=7
    manifest["m1_candidate_id"]=str(m1.iloc[0]["candidate_id"])
    manifest["m2_candidate_ids"]=m2["candidate_id"].astype(str).tolist()
    manifest["m3_weight_sum"]=float(m3["weight"].sum())
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall)
    write_json(freeze_path,manifest)

    print(
        f"V3 PROVIDER PASS {world}/{provider} "
        f"M1={manifest['m1_candidate_id']} "
        f"M2={','.join(manifest['m2_candidate_ids'])} "
        f"wall={manifest['python_wall_seconds']/60:.1f}m",
        flush=True,
    )
    return {
        "world":world,"provider":provider,
        "status":manifest["status"],
        "m1_candidate_id":manifest["m1_candidate_id"],
        "m2_candidates":";".join(manifest["m2_candidate_ids"]),
        "wall_seconds":manifest["python_wall_seconds"],
        "reused_freeze":False,
    }


def _freeze_world(world:str,result_root:Path)->dict[str,Any]:
    started=utc_now_iso()
    world_root=result_root/world
    rows=[]
    m2_tables={}
    m3_tables={}
    for provider in PROVIDERS:
        pdir=world_root/provider
        manifest_path=pdir/"provider_freeze_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        m=read_json(manifest_path)
        if m.get("status")!="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION":
            raise RuntimeError(f"{world}/{provider}: provider reconstruction not frozen")
        m1=pd.read_csv(pdir/"m1_provider_model.csv")
        m2=pd.read_csv(pdir/"m2_provider_models.csv")
        m3=pd.read_csv(pdir/"m3_provider_models.csv")
        if len(m1)!=1 or len(m2)!=3 or len(m3)!=7:
            raise RuntimeError(f"{world}/{provider}: M1/M2/M3 provider cardinality mismatch")
        rows.append({
            "provider_id":provider,
            "provider_manifest_sha256":sha256_file(manifest_path),
            "m1_candidate_id":str(m1.iloc[0]["candidate_id"]),
            "m2_candidate_ids":";".join(m2["candidate_id"].astype(str)),
            "m3_weight_sum":float(m3["weight"].sum()),
        })
        m2_tables[provider]=m2
        m3_tables[provider]=m3[["candidate_id","weight"]].copy()

    provider_status=pd.DataFrame(rows)
    provider_status_path=world_root/"v3_provider_status.csv"
    provider_status.to_csv(provider_status_path,index=False)

    # Materialize the exact 27 equal-weight M2 joint models.
    joint_rows=[]
    for a in m2_tables["ProviderA"].itertuples(index=False):
        for b in m2_tables["ProviderB"].itertuples(index=False):
            for c in m2_tables["ProviderC"].itertuples(index=False):
                joint_rows.append({
                    "ProviderA_candidate_id":str(a.candidate_id),
                    "ProviderB_candidate_id":str(b.candidate_id),
                    "ProviderC_candidate_id":str(c.candidate_id),
                    "joint_weight":1.0/27.0,
                })
    m2_joint=pd.DataFrame(joint_rows)
    if len(m2_joint)!=27:
        raise RuntimeError(f"{world}: M2 joint support is not 27")
    m2_joint.insert(0,"joint_rank",np.arange(1,28,dtype=int))
    m2_joint_path=world_root/"m2_joint_support_27.csv"
    m2_joint.to_csv(m2_joint_path,index=False)

    m3_joint=joint_product_support(m3_tables)
    if len(m3_joint)!=343:
        raise RuntimeError(f"{world}: M3 joint support is not 343")
    m3_joint_path=world_root/"m3_joint_support_343.csv"
    m3_top14_path=world_root/"m3_joint_support_top14.csv"
    m3_joint.to_csv(m3_joint_path,index=False)
    m3_joint.head(14).to_csv(m3_top14_path,index=False)

    outputs={
        "provider_status":str(provider_status_path),
        "m2_joint_support_27":str(m2_joint_path),
        "m3_joint_support_343":str(m3_joint_path),
        "m3_joint_support_top14":str(m3_top14_path),
    }
    manifest=_manifest(
        status="FROZEN_PHASE5_V3_WORLD_RECONSTRUCTION",
        inputs={
            "provider_world_id":world,
            "provider_level_only":True,
            "graph_prediction_used":False,
            "final_WB_used":False,
        },
        seed_banks={},
        outputs=outputs,
        started_utc=started,
    )
    manifest["provider_manifest_sha256"]={
        r["provider_id"]:r["provider_manifest_sha256"] for r in rows
    }
    manifest["m1_joint_models"]=1
    manifest["m2_joint_models"]=27
    manifest["m3_joint_models"]=343
    manifest["m3_top14_models"]=14
    write_json(world_root/"world_reconstruction_freeze_manifest.json",manifest)
    return {
        "world":world,"status":manifest["status"],
        "M1_joint":1,"M2_joint":27,"M3_joint":343,"M3_top14":14,
    }


def _freeze_battery(result_root:Path)->Path:
    contracts=load_phase5_contracts(HERE)
    rows=[]
    for world in canonical_provider_world_ids(contracts):
        path=result_root/world/"world_reconstruction_freeze_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        m=read_json(path)
        if m.get("status")!="FROZEN_PHASE5_V3_WORLD_RECONSTRUCTION":
            raise RuntimeError(f"{world}: V3 world reconstruction not frozen")
        rows.append({
            "provider_world_id":world,
            "world_manifest_sha256":sha256_file(path),
        })
    table=pd.DataFrame(rows)
    table_path=result_root/"v3_world_status.csv"
    table.to_csv(table_path,index=False)
    manifest=_manifest(
        status="FROZEN_PHASE5_V3_RECONSTRUCTION_BATTERY",
        inputs={
            "all_12_provider_reconstructions_frozen":True,
            "graph_prediction_used":False,
            "graph_WB_used":False,
            "final_WB_used":False,
        },
        seed_banks={},
        outputs={"world_status":str(table_path)},
        started_utc=utc_now_iso(),
    )
    manifest["world_manifest_sha256"]={
        r["provider_world_id"]:r["world_manifest_sha256"] for r in rows
    }
    path=result_root/"phase5_v3_reconstruction_freeze_manifest.json"
    write_json(path,manifest)
    return path


def main()->None:
    p=argparse.ArgumentParser(description="Scientific Phase-5 V3 provider reconstruction")
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--world",choices=("P1","P2","P3","P4"))
    g.add_argument("--all-worlds",action="store_true")
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--result-root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    _require_prerequisites()
    cfg,seeds_cfg=_v3_objects()
    # Defensive scientific-bank disjointness inside V3.
    banks=[]
    for name,block in seeds_cfg["provider_reconstruction"].items():
        s=set(_seed_tuple(block))
        for prev_name,prev in banks:
            if s.intersection(prev):
                raise RuntimeError(f"V3 reconstruction seed overlap: {name} vs {prev_name}")
        banks.append((name,s))
    if int(cfg["candidate_reconstruction"]["candidate_count_per_provider"])!=7:
        raise RuntimeError("V3 candidate count changed")

    contracts=load_phase5_contracts(HERE)
    worlds=canonical_provider_world_ids(contracts) if args.all_worlds else (str(args.world),)
    root=args.result_root.resolve()
    tasks=[(w,pid) for w in worlds for pid in PROVIDERS]
    started=time.perf_counter()
    rows=[]

    if args.workers==1:
        for w,pid in tasks:
            rows.append(_run_provider(w,pid,str(root)))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(_run_provider,w,pid,str(root)):(w,pid) for w,pid in tasks}
            for fut in concurrent.futures.as_completed(futures):
                w,pid=futures[fut]
                try:
                    rows.append(fut.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"V3 reconstruction worker failed for {w}/{pid}") from exc

    world_rows=[_freeze_world(w,root) for w in worlds]
    battery_manifest=None
    if set(worlds)==set(canonical_provider_world_ids(contracts)):
        battery_manifest=_freeze_battery(root)

    print("\nPHASE5_V3_PROVIDER_RECONSTRUCTION_SUMMARY")
    print(pd.DataFrame(rows).sort_values(["world","provider"]).to_string(index=False))
    print("\nPHASE5_V3_WORLD_RECONSTRUCTION_SUMMARY")
    print(pd.DataFrame(world_rows).sort_values("world").to_string(index=False))
    if battery_manifest is not None:
        print("battery_freeze",battery_manifest)
    print(f"stage_wall={(time.perf_counter()-started)/60:.1f} min workers={args.workers}")


if __name__=="__main__":
    main()
