"""Official Phase-5 V2 M2 provider reconstruction.

For each provider-world/provider pair:
  * recover the complete M1 TPE search landscape that lies in the final
    declared M1 domain (round0 plus the one expanded round when present);
  * draw the frozen 48-point nonadaptive LHS in normalized
    (log-mu, log-kappa, CV);
  * score the LHS on the frozen N=25 local CRN bank;
  * warm-start the frozen A4 GP/straddle level-set search with all TPE+LHS
    observations and add exactly 48 new evaluated points;
  * precompute a five-member quality/diversity portfolio;
  * confirm all five on the frozen N=100 confirmation bank against
    1.25 * the already-frozen M1 best confirmation MSE;
  * retain the first three passing members in precomputed order;
  * replay those three on the frozen N=100 replay bank, diagnostically only.

No Step-0 WB value, graph prediction, graph WB, hidden provider parameter, or
PPG mechanism is read.  The exact 48-point LHS design is retained for M3.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE2=FIRST_SCIENCE/"phase2"
PHASE3=FIRST_SCIENCE/"phase3"
PHASE4=FIRST_SCIENCE/"phase4"
for p in (PHASE2,PHASE3,PHASE4):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa:E402
from m1_joint_lift_v2 import M1V2SearchBounds  # noqa:E402
from run_m1_provider_lift_v2 import _simulate_and_score  # noqa:E402
from m2_a2_nonadaptive_coverage import _latin_hypercube, _map_unit_to_parameters  # noqa:E402
from m2_a4_gp_levelset_search import (  # noqa:E402
    _build_gp,
    _load_gp_dependencies,
    _make_sobol_pool,
    _unit_to_parameters,
)

from phase5_runtime_v2 import (
    base_manifest,
    canonical_provider_world_ids,
    inclusive_seed_range,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

PROVIDERS=("ProviderA","ProviderB","ProviderC")
DEFAULT_ROOT=HERE/"results"/"03_reconstruction"
DOMAIN_REGISTRY=DEFAULT_ROOT/"phase5_m1_domain_registry.csv"
M1_AUDIT=DEFAULT_ROOT/"phase5_m1_reconstruction_audit_manifest.json"
CLARIFICATION=HERE/"PHASE5_M2_CONFIRMATION_REFERENCE_CLARIFICATION_2026-10-05.md"
A4_SOURCE=PHASE4/"config_phase4_m2_a4_gp_levelset_v1.json"
TOL=1e-12


def _provider_index(provider:str)->int:
    return PROVIDERS.index(provider)


def _load_public_card(world_id:str,provider:str):
    contracts=load_phase5_contracts(HERE)
    root=HERE/"results"/"01_i1"/world_id
    freeze=read_json(root/"i1_freeze_manifest.json")
    if freeze.get("status")!="FROZEN_PHASE5_I1_COMPLETE_V2":
        raise RuntimeError(f"{world_id}: I1 not frozen")
    if freeze.get("method_contract_sha256")!=contracts.hashes["methods"]:
        raise RuntimeError(f"{world_id}: I1 method-contract hash mismatch")
    manifest=read_json(root/"public"/"i1_rho_conditioned_manifest_v2.json")
    rec=dict(manifest["cards"][provider])
    card_dir=root/"public"/provider
    if sha256_file(card_dir/"card.json")!=rec["card_json_sha256"]:
        raise RuntimeError(f"{world_id}/{provider}: card hash mismatch")
    if sha256_file(card_dir/"sigma_surface.csv")!=rec["sigma_surface_sha256"]:
        raise RuntimeError(f"{world_id}/{provider}: surface hash mismatch")
    metadata,surface=load_rho_conditioned_i1_provider_card(card_dir)
    return metadata,surface,rec


def _domain_row(world_id:str,provider:str)->pd.Series:
    if not DOMAIN_REGISTRY.is_file():
        raise FileNotFoundError(DOMAIN_REGISTRY)
    if not M1_AUDIT.is_file():
        raise FileNotFoundError(M1_AUDIT)
    audit=read_json(M1_AUDIT)
    if audit.get("status")!="FROZEN_PHASE5_M1_RECONSTRUCTION_AUDIT_V2":
        raise RuntimeError("M1 reconstruction audit is not frozen")
    table=pd.read_csv(DOMAIN_REGISTRY)
    rows=table[
        (table["provider_world_id"].astype(str)==world_id)
        & (table["provider_id"].astype(str)==provider)
    ]
    if len(rows)!=1:
        raise RuntimeError(f"{world_id}/{provider}: domain registry row count {len(rows)}")
    return rows.iloc[0]


def _bounds(row:pd.Series)->M1V2SearchBounds:
    return M1V2SearchBounds(
        mean_service_time_lower=float(row["mean_service_time_lower"]),
        mean_service_time_upper=float(row["mean_service_time_upper"]),
        cost_rate_lower=float(row["cost_rate_lower"]),
        cost_rate_upper=float(row["cost_rate_upper"]),
        service_cv_lower=float(row["service_cv_lower"]),
        service_cv_upper=float(row["service_cv_upper"]),
        cost_rate_public_reference=float(row["cost_rate_public_reference"]),
    )


def _normalize(mu:float,kappa:float,cv:float,b:M1V2SearchBounds)->tuple[float,float,float]:
    z_mu=(math.log(mu)-math.log(b.mean_service_time_lower))/(
        math.log(b.mean_service_time_upper)-math.log(b.mean_service_time_lower)
    )
    z_k=(math.log(kappa)-math.log(b.cost_rate_lower))/(
        math.log(b.cost_rate_upper)-math.log(b.cost_rate_lower)
    )
    z_cv=(cv-b.service_cv_lower)/(b.service_cv_upper-b.service_cv_lower)
    return float(z_mu),float(z_k),float(z_cv)


def _m1_landscape(world_id:str,provider:str,b:M1V2SearchBounds)->pd.DataFrame:
    pdir=DEFAULT_ROOT/world_id/"m1"/provider
    summary=read_json(pdir/"m1_final_parameters.json")
    final_round=int(summary["final_round"])
    rounds=[("round0",0)]
    if final_round==1:
        rounds.append(("round1_expanded",1))
    frames=[]
    for dirname,round_id in rounds:
        path=pdir/dirname/"m1_v2_search_trials.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        frame=pd.read_csv(path)
        if len(frame)!=100:
            raise RuntimeError(
                f"{world_id}/{provider}/{dirname}: expected 100 M1 trials, found {len(frame)}"
            )
        rows=[]
        for rec in frame.itertuples(index=False):
            mu=float(rec.mean_service_time); k=float(rec.cost_rate); cv=float(rec.service_cv)
            z=_normalize(mu,k,cv,b)
            if min(z)<-1e-10 or max(z)>1.0+1e-10:
                raise RuntimeError(
                    f"{world_id}/{provider}: M1 historical point outside final domain"
                )
            rows.append({
                "provider":provider,
                "candidate_id":f"{world_id}_{provider}_TPE_R{round_id}_{int(rec.trial_number):03d}",
                "source_stage":f"TPE_R{round_id}",
                "z_log_mu":z[0],"z_log_kappa":z[1],"z_cv":z[2],
                "mean_service_time":mu,"cost_rate":k,"service_cv":cv,
                "local_mse":float(rec.search_mse),
                "trial_number":int(rec.trial_number),
                "m1_round":round_id,
            })
        frames.append(pd.DataFrame(rows))
    out=pd.concat(frames,ignore_index=True)
    return out.sort_values(["m1_round","trial_number"],kind="mergesort").reset_index(drop=True)


def _evaluate_candidate(
    *,
    metadata,
    surface,
    row,
    seeds,
)->dict[str,float]:
    metrics,_,_=_simulate_and_score(
        metadata=metadata,
        public_surface=surface,
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
        trajectory_seeds=seeds,
        canonical_ipt=1_000_000.0,
        execution_fraction=0.5,
        quiet=True,
    )
    return {k:float(v) for k,v in metrics.items() if k!="n_points"} | {
        "n_points":int(metrics["n_points"])
    }


def _lhs_stage(
    *,
    world_id:str,
    provider:str,
    b:M1V2SearchBounds,
    metadata,
    surface,
    root:Path,
    seeds:tuple[int,...],
    n_points:int,
    seed:int,
    search_ceiling:float,
)->pd.DataFrame:
    design_path=root/"m2_lhs_design.csv"
    results_path=root/"m2_lhs_search_results.csv"
    if design_path.is_file():
        design=pd.read_csv(design_path)
    else:
        unit=_latin_hypercube(n_points,3,seed+_provider_index(provider)*100003)
        design=_map_unit_to_parameters(unit,b)
        design.insert(0,"lhs_index",np.arange(n_points,dtype=int))
        design.insert(
            0,"candidate_id",
            [f"{world_id}_{provider}_LHS_{i:03d}" for i in range(n_points)],
        )
        design.insert(0,"provider",provider)
        design.to_csv(design_path,index=False)
    if len(design)!=n_points:
        raise RuntimeError(f"{world_id}/{provider}: LHS design size changed")

    if results_path.is_file():
        results=pd.read_csv(results_path)
        completed=set(results["candidate_id"].astype(str))
    else:
        results=pd.DataFrame(); completed=set()
    started=time.perf_counter(); newly=0
    for ordinal,rec in enumerate(design.to_dict("records"),start=1):
        cid=str(rec["candidate_id"])
        if cid in completed:
            continue
        metrics=_evaluate_candidate(
            metadata=metadata,surface=surface,row=rec,seeds=seeds
        )
        row=dict(rec)
        row.update({
            "local_mse":metrics["mse"],
            "local_rmse":metrics["rmse"],
            "local_mae":metrics["mae"],
            "local_bias":metrics["bias"],
            "local_max_abs_error":metrics["max_abs_error"],
            "compatibility_mse_ceiling":search_ceiling,
            "local_compatible":bool(metrics["mse"]<=search_ceiling+TOL),
            "n_local_trajectories":len(seeds),
        })
        results=pd.concat([results,pd.DataFrame([row])],ignore_index=True)
        results=results.drop_duplicates("candidate_id",keep="last").sort_values(
            "lhs_index",kind="mergesort"
        )
        results.to_csv(results_path,index=False)
        completed.add(cid); newly+=1
        done=len(completed)
        if newly==1 or done%8==0 or done==n_points:
            elapsed=time.perf_counter()-started
            avg=elapsed/max(1,newly)
            eta=avg*(n_points-done)
            print(
                f"M2 LHS {world_id}/{provider} {done}/{n_points} | "
                f"elapsed={elapsed/60:.1f} min | avg={avg:.1f} s/candidate | "
                f"ETA={eta/60:.1f} min",
                flush=True,
            )
    if len(results)!=n_points:
        raise RuntimeError(f"{world_id}/{provider}: incomplete LHS stage")
    return results.reset_index(drop=True)


def _dedup_warm(tpe:pd.DataFrame,lhs:pd.DataFrame)->pd.DataFrame:
    cols=[
        "provider","candidate_id","source_stage",
        "z_log_mu","z_log_kappa","z_cv",
        "mean_service_time","cost_rate","service_cv","local_mse",
    ]
    t=tpe.copy()
    l=lhs.copy(); l["source_stage"]="LHS"
    warm=pd.concat([t[cols],l[cols]],ignore_index=True)
    warm["_theta_key"]=warm.apply(
        lambda r:"|".join(
            format(float(r[c]),".14g") for c in ("z_log_mu","z_log_kappa","z_cv")
        ),axis=1,
    )
    warm=warm.sort_values(
        ["_theta_key","local_mse","source_stage","candidate_id"],kind="mergesort"
    ).drop_duplicates("_theta_key",keep="first")
    return warm.drop(columns="_theta_key").reset_index(drop=True)


def _gp_stage(
    *,
    world_id:str,
    provider:str,
    b:M1V2SearchBounds,
    metadata,
    surface,
    root:Path,
    seeds:tuple[int,...],
    warm:pd.DataFrame,
    search_ceiling:float,
    a4_cfg:dict[str,Any],
    n_new:int,
)->pd.DataFrame:
    deps=_load_gp_dependencies()
    cKDTree,qmc_module,convergence_warning=deps[0],deps[1],deps[2]
    cfg=a4_cfg
    pool_cfg=dict(cfg["acquisition"]["candidate_pool"])
    power=int(pool_cfg["sobol_power"])
    if 2**power!=int(pool_cfg["points_per_provider"]):
        raise RuntimeError("A4 Sobol pool contract mismatch")
    unit=_make_sobol_pool(
        provider_index=_provider_index(provider),
        power=power,
        seed=int(pool_cfg["seed"]),
        qmc_module=qmc_module,
    )
    params=[_unit_to_parameters(x,b) for x in unit]
    pool=pd.DataFrame({
        "pool_index":np.arange(len(unit),dtype=int),
        "z_log_mu":unit[:,0],"z_log_kappa":unit[:,1],"z_cv":unit[:,2],
        "mean_service_time":[x[0] for x in params],
        "cost_rate":[x[1] for x in params],
        "service_cv":[x[2] for x in params],
    })
    pool_path=root/"m2_gp_sobol_pool.csv"
    if not pool_path.is_file():
        pool.to_csv(pool_path,index=False)

    results_path=root/"m2_gp_acquisitions.csv"
    if results_path.is_file():
        acquisitions=pd.read_csv(results_path)
        iterations=sorted(acquisitions["gp_iteration"].astype(int).tolist())
        if iterations!=list(range(len(iterations))):
            raise RuntimeError(f"{world_id}/{provider}: GP checkpoint not contiguous")
    else:
        acquisitions=pd.DataFrame()
    beta=float(cfg["acquisition"]["beta_sigma"])
    duplicate_tol=float(pool_cfg["exclude_nearest_observed_distance_leq"])
    base_seed=int(cfg["gp_model"]["random_seed"])
    started=time.perf_counter()
    initial=len(acquisitions)
    for it in range(initial,n_new):
        observed=warm.copy()
        if not acquisitions.empty:
            observed=pd.concat([
                observed,
                acquisitions[[
                    "provider","candidate_id","source_stage",
                    "z_log_mu","z_log_kappa","z_cv",
                    "mean_service_time","cost_rate","service_cv","local_mse",
                ]],
            ],ignore_index=True)
        x_train=observed[["z_log_mu","z_log_kappa","z_cv"]].to_numpy(float)
        y_train=observed["local_mse"].to_numpy(float)
        gp_seed=base_seed+_provider_index(provider)*100003+it
        gp,_=_build_gp(cfg,gp_seed,deps)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",convergence_warning)
            gp.fit(x_train,y_train)

        pool_x=pool[["z_log_mu","z_log_kappa","z_cv"]].to_numpy(float)
        nearest,_=cKDTree(x_train).query(pool_x,k=1)
        eligible=nearest>duplicate_tol
        if not acquisitions.empty:
            used=acquisitions["pool_index"].astype(int).to_numpy()
            eligible[used]=False
        idx=np.flatnonzero(eligible)
        if not len(idx):
            raise RuntimeError(f"{world_id}/{provider}: Sobol pool exhausted")
        mean,std=gp.predict(pool_x[idx],return_std=True)
        acq=beta*std-np.abs(mean-search_ceiling)
        local_choice=int(np.argmax(acq))
        pool_index=int(idx[local_choice])
        rec=pool.iloc[pool_index].to_dict()
        cid=f"{world_id}_{provider}_GP_{it:03d}"
        rec.update({
            "provider":provider,"candidate_id":cid,"source_stage":"GP_LSE",
        })
        metrics=_evaluate_candidate(
            metadata=metadata,surface=surface,row=rec,seeds=seeds
        )
        out=dict(rec)
        out.update({
            "gp_iteration":it,
            "posterior_mean_before_eval":float(mean[local_choice]),
            "posterior_std_before_eval":float(std[local_choice]),
            "straddle_acquisition":float(acq[local_choice]),
            "compatibility_mse_ceiling":search_ceiling,
            "local_mse":metrics["mse"],
            "local_rmse":metrics["rmse"],
            "local_mae":metrics["mae"],
            "local_bias":metrics["bias"],
            "local_max_abs_error":metrics["max_abs_error"],
            "local_compatible":bool(metrics["mse"]<=search_ceiling+TOL),
            "gp_kernel_after_fit":str(gp.kernel_),
            "n_local_trajectories":len(seeds),
        })
        acquisitions=pd.concat([acquisitions,pd.DataFrame([out])],ignore_index=True)
        acquisitions=acquisitions.drop_duplicates("gp_iteration",keep="last").sort_values(
            "gp_iteration",kind="mergesort"
        )
        acquisitions.to_csv(results_path,index=False)

        done=len(acquisitions); newly=done-initial
        if newly==1 or done%8==0 or done==n_new:
            elapsed=time.perf_counter()-started
            avg=elapsed/max(1,newly); eta=avg*(n_new-done)
            print(
                f"M2 GP {world_id}/{provider} {done}/{n_new} | "
                f"elapsed={elapsed/60:.1f} min | avg={avg:.1f} s/eval | "
                f"ETA={eta/60:.1f} min",
                flush=True,
            )
    if len(acquisitions)!=n_new:
        raise RuntimeError(f"{world_id}/{provider}: incomplete GP stage")
    return acquisitions.reset_index(drop=True)


def _provisional(
    warm:pd.DataFrame,
    gp:pd.DataFrame,
    *,
    ceiling:float,
    k:int,
)->pd.DataFrame:
    gp_cols=[
        "provider","candidate_id","source_stage",
        "z_log_mu","z_log_kappa","z_cv",
        "mean_service_time","cost_rate","service_cv","local_mse",
    ]
    observed=pd.concat([warm,gp[gp_cols]],ignore_index=True)
    compatible=observed[
        observed["local_mse"].astype(float)<=ceiling+TOL
    ].sort_values(["local_mse","candidate_id"],kind="mergesort").reset_index(drop=True)
    if len(compatible)<k:
        return pd.DataFrame()
    coords=compatible[["z_log_mu","z_log_kappa","z_cv"]].to_numpy(float)
    chosen=[0]; min_dist=[np.nan]
    while len(chosen)<k:
        options=[]
        for idx in range(len(compatible)):
            if idx in chosen:
                continue
            d=min(float(np.linalg.norm(coords[idx]-coords[j])) for j in chosen)
            options.append(
                (-d,float(compatible.iloc[idx]["local_mse"]),
                 str(compatible.iloc[idx]["candidate_id"]),idx)
            )
        options.sort()
        chosen.append(options[0][-1]); min_dist.append(-options[0][0])
    selected=compatible.iloc[chosen].copy().reset_index(drop=True)
    selected.insert(0,"selection_order",np.arange(1,k+1,dtype=int))
    selected["portfolio_role"]=[
        "BEST_LOCAL_LOSS" if i==0 else f"DIVERSE_{i}" for i in range(k)
    ]
    selected["min_distance_to_previous_portfolio"]=min_dist
    selected["compatibility_mse_ceiling"]=ceiling
    return selected


def _checkpoint_eval(
    *,
    candidates:pd.DataFrame,
    stage:str,
    metadata,
    surface,
    seeds:tuple[int,...],
    root:Path,
)->pd.DataFrame:
    path=root/f"m2_{stage}_results.csv"
    if path.is_file():
        results=pd.read_csv(path); completed=set(results["candidate_id"].astype(str))
    else:
        results=pd.DataFrame(); completed=set()
    started=time.perf_counter(); newly=0
    ordered=candidates.sort_values("selection_order",kind="mergesort")
    for rec in ordered.to_dict("records"):
        cid=str(rec["candidate_id"])
        if cid in completed:
            continue
        metrics=_evaluate_candidate(metadata=metadata,surface=surface,row=rec,seeds=seeds)
        row=dict(rec)
        row.update({
            f"{stage}_mse":metrics["mse"],
            f"{stage}_rmse":metrics["rmse"],
            f"{stage}_mae":metrics["mae"],
            f"{stage}_bias":metrics["bias"],
            f"{stage}_max_abs_error":metrics["max_abs_error"],
            f"{stage}_n_trajectories":len(seeds),
        })
        results=pd.concat([results,pd.DataFrame([row])],ignore_index=True)
        results=results.drop_duplicates("candidate_id",keep="last").sort_values(
            "selection_order",kind="mergesort"
        )
        results.to_csv(path,index=False)
        completed.add(cid); newly+=1
        elapsed=time.perf_counter()-started
        avg=elapsed/max(1,newly); eta=avg*(len(ordered)-len(completed))
        print(
            f"M2 {stage} {cid} {len(completed)}/{len(ordered)} | "
            f"elapsed={elapsed/60:.1f} min | ETA={max(0.0,eta)/60:.1f} min",
            flush=True,
        )
    return results.reset_index(drop=True)


def _run_one(world_id:str,provider:str,result_root:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    m2cfg=contracts.methods["M2"]
    root=Path(result_root).resolve()/world_id/"m2"/provider
    freeze_path=root/"m2_provider_freeze.json"
    if freeze_path.is_file():
        m=read_json(freeze_path)
        if m.get("status") in (
            "FROZEN_PHASE5_M2_PROVIDER_V2",
            "FROZEN_PHASE5_M2_PROVIDER_NOT_INSTANTIABLE_V2",
        ):
            return {"world":world_id,"provider":provider,"status":m["status"],"wall_seconds":0.0}
        raise RuntimeError(f"{world_id}/{provider}: unknown M2 freeze status")

    started_utc=utc_now_iso(); wall=time.perf_counter()
    root.mkdir(parents=True,exist_ok=True)
    row=_domain_row(world_id,provider); b=_bounds(row)
    metadata,surface,card_rec=_load_public_card(world_id,provider)
    tpe=_m1_landscape(world_id,provider,b)
    tpe_path=root/"m2_m1_tpe_warm_start.csv"
    tpe.to_csv(tpe_path,index=False)

    ratio=float(m2cfg["nonadaptive_LHS"]["compatibility_ratio"])
    best_search=float(tpe["local_mse"].min())
    search_ceiling=ratio*best_search
    search_seeds=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_search_CRN"]
    )
    lhs=_lhs_stage(
        world_id=world_id,provider=provider,b=b,metadata=metadata,surface=surface,
        root=root,seeds=search_seeds,
        n_points=int(m2cfg["nonadaptive_LHS"]["n_points_per_provider"]),
        seed=int(m2cfg["nonadaptive_LHS"]["seed"]),
        search_ceiling=search_ceiling,
    )
    warm=_dedup_warm(tpe,lhs)
    warm_path=root/"m2_gp_warm_start.csv"; warm.to_csv(warm_path,index=False)

    a4=read_json(A4_SOURCE)
    n_new=int(m2cfg["GP_levelset"]["new_evaluations_per_provider"])
    gp=_gp_stage(
        world_id=world_id,provider=provider,b=b,metadata=metadata,surface=surface,
        root=root,seeds=search_seeds,warm=warm,search_ceiling=search_ceiling,
        a4_cfg=a4,n_new=n_new,
    )
    provisional=_provisional(
        warm,gp,ceiling=search_ceiling,
        k=int(m2cfg["GP_levelset"]["provisional_portfolio_size"]),
    )
    provisional_path=root/"m2_provisional_portfolio.csv"
    provisional.to_csv(provisional_path,index=False)

    status="FROZEN_PHASE5_M2_PROVIDER_NOT_INSTANTIABLE_V2"
    final=pd.DataFrame(); replay=pd.DataFrame()
    reasons=[]
    confirm_path=root/"m2_confirmation_results.csv"
    replay_path=root/"m2_replay_results.csv"
    final_path=root/"m2_final_portfolio.csv"

    if len(provisional)!=int(m2cfg["GP_levelset"]["provisional_portfolio_size"]):
        reasons.append(
            f"only {len(provisional)} search-compatible members available; "
            f"need {m2cfg['GP_levelset']['provisional_portfolio_size']}"
        )
        pd.DataFrame().to_csv(confirm_path,index=False)
        pd.DataFrame().to_csv(replay_path,index=False)
        pd.DataFrame().to_csv(final_path,index=False)
    else:
        confirm_seeds=inclusive_seed_range(
            contracts.seeds["provider_reconstruction"]["M1_M2_local_confirmation_CRN"]
        )
        confirmation=_checkpoint_eval(
            candidates=provisional,stage="confirmation",metadata=metadata,surface=surface,
            seeds=confirm_seeds,root=root,
        )
        m1_summary=read_json(DEFAULT_ROOT/world_id/"m1"/provider/"m1_final_parameters.json")
        reference=float(m1_summary["confirmation_metrics"]["mse"])
        confirm_ratio=float(m2cfg["GP_levelset"]["compatibility_ratio"])
        confirm_ceiling=confirm_ratio*reference
        confirmation["m1_frozen_confirmation_mse_reference"]=reference
        confirmation["confirmation_mse_ceiling"]=confirm_ceiling
        confirmation["confirmation_compatible"]=(
            confirmation["confirmation_mse"].astype(float)<=confirm_ceiling+TOL
        )
        confirmation=confirmation.sort_values("selection_order",kind="mergesort")
        confirmation.to_csv(confirm_path,index=False)

        final=confirmation[
            confirmation["confirmation_compatible"].astype(bool)
        ].head(int(m2cfg["GP_levelset"]["final_portfolio_size_per_provider"])).copy()
        if len(final)<int(m2cfg["GP_levelset"]["final_portfolio_size_per_provider"]):
            reasons.append(
                f"only {len(final)} of 5 provisional members passed frozen confirmation; need 3"
            )
            final.to_csv(final_path,index=False)
            pd.DataFrame().to_csv(replay_path,index=False)
        else:
            final["final_portfolio_order"]=np.arange(1,len(final)+1,dtype=int)
            final.to_csv(final_path,index=False)
            replay_seeds=inclusive_seed_range(
                contracts.seeds["provider_reconstruction"]["M1_M2_local_replay_CRN"]
            )
            replay=_checkpoint_eval(
                candidates=final,stage="replay",metadata=metadata,surface=surface,
                seeds=replay_seeds,root=root,
            )
            status="FROZEN_PHASE5_M2_PROVIDER_V2"

    search_seed_rec=contracts.seeds["provider_reconstruction"]["M1_M2_local_search_CRN"]
    confirm_seed_rec=contracts.seeds["provider_reconstruction"]["M1_M2_local_confirmation_CRN"]
    replay_seed_rec=contracts.seeds["provider_reconstruction"]["M1_M2_local_replay_CRN"]
    outputs={
        "m1_tpe_warm_start":str(tpe_path),
        "lhs_design":str(root/"m2_lhs_design.csv"),
        "lhs_search_results":str(root/"m2_lhs_search_results.csv"),
        "gp_warm_start":str(warm_path),
        "gp_acquisitions":str(root/"m2_gp_acquisitions.csv"),
        "provisional_portfolio":str(provisional_path),
        "confirmation_results":str(confirm_path),
        "final_portfolio":str(final_path),
        "replay_results":str(replay_path),
    }
    manifest=base_manifest(
        contracts,stage_id="RECONSTRUCTION",status=status,
        inputs={
            "provider_world_id":world_id,"provider_id":provider,
            "m1_domain_registry_sha256":sha256_file(DOMAIN_REGISTRY),
            "m1_audit_manifest_sha256":sha256_file(M1_AUDIT),
            "public_card_json_sha256":card_rec["card_json_sha256"],
            "public_sigma_surface_sha256":card_rec["sigma_surface_sha256"],
            "a4_source_contract_sha256":sha256_file(A4_SOURCE),
            "confirmation_reference_clarification_sha256":sha256_file(CLARIFICATION),
            "search_compatibility_reference":"best observed M1 TPE search MSE over all rounds inside final domain",
            "confirmation_compatibility_reference":"already-frozen M1 selected 100-trajectory confirmation MSE",
            "graph_whitebox_used":False,
            "step0_WB_values_used":False,
            "hidden_provider_parameters_used":False,
            "ppg_mechanism_used":False,
        },
        seed_banks={
            "local_search":dict(search_seed_rec),
            "local_confirmation":dict(confirm_seed_rec),
            "local_replay":dict(replay_seed_rec),
        },
        outputs=outputs,
        started_utc=started_utc,
    )
    manifest["best_m1_search_mse"]=best_search
    manifest["search_compatibility_mse_ceiling"]=search_ceiling
    manifest["n_m1_tpe_warm_points"]=len(tpe)
    manifest["n_lhs_points"]=len(lhs)
    manifest["n_gp_evaluations"]=len(gp)
    manifest["n_provisional_members"]=len(provisional)
    manifest["n_final_members"]=len(final)
    manifest["failure_reasons"]=reasons
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall)
    write_json(freeze_path,manifest)
    print(
        f"M2 {'PASS' if status=='FROZEN_PHASE5_M2_PROVIDER_V2' else 'NOT_INSTANTIABLE'} "
        f"{world_id}/{provider} | wall={manifest['python_wall_seconds']/60:.1f} min",
        flush=True,
    )
    return {"world":world_id,"provider":provider,"status":status,
            "wall_seconds":manifest["python_wall_seconds"]}


def _freeze_worlds(result_root:Path)->None:
    contracts=load_phase5_contracts(HERE)
    for world in canonical_provider_world_ids(contracts):
        rows=[]
        root=result_root/world/"m2"
        for provider in PROVIDERS:
            path=root/provider/"m2_provider_freeze.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            m=read_json(path)
            rows.append({
                "provider":provider,"status":m["status"],
                "manifest_sha256":sha256_file(path),
                "n_final_members":int(m.get("n_final_members",0)),
            })
        table=pd.DataFrame(rows)
        table_path=root/"m2_provider_status.csv"; table.to_csv(table_path,index=False)
        ok=table["status"].eq("FROZEN_PHASE5_M2_PROVIDER_V2").all()
        status=(
            "FROZEN_PHASE5_M2_WORLD_V2"
            if ok else
            "FROZEN_PHASE5_M2_WORLD_WITH_NOT_INSTANTIABLE_PROVIDER_V2"
        )
        manifest=base_manifest(
            contracts,stage_id="RECONSTRUCTION",status=status,
            inputs={"provider_world_id":world,"provider_level_only":True},
            seed_banks={},outputs={"m2_provider_status":str(table_path)},
            started_utc=utc_now_iso(),
        )
        manifest["provider_manifest_sha256"]={
            r["provider"]:r["manifest_sha256"] for r in rows
        }
        write_json(root/"m2_world_freeze_manifest.json",manifest)


def main()->None:
    p=argparse.ArgumentParser(description="Official Phase-5 V2 M2 reconstruction")
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--world",choices=("P1","P2","P3","P4"))
    group.add_argument("--all-worlds",action="store_true")
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--result-root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    contracts=load_phase5_contracts(HERE)
    worlds=canonical_provider_world_ids(contracts) if args.all_worlds else (str(args.world),)
    tasks=[(w,pid) for w in worlds for pid in PROVIDERS]
    started=time.perf_counter(); rows=[]
    if args.workers==1:
        for w,pid in tasks:
            rows.append(_run_one(w,pid,str(args.result_root)))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={
                pool.submit(_run_one,w,pid,str(args.result_root)):(w,pid)
                for w,pid in tasks
            }
            for f in concurrent.futures.as_completed(futures):
                w,pid=futures[f]
                try:
                    rows.append(f.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(f"M2 worker failed for {w}/{pid}") from exc
    _freeze_worlds(args.result_root.resolve())
    table=pd.DataFrame(rows).sort_values(["world","provider"]).reset_index(drop=True)
    print("\nPHASE5_M2_RECONSTRUCTION_SUMMARY")
    print(table.to_string(index=False))
    print(f"stage_wall={(time.perf_counter()-started)/60:.1f} min workers={args.workers}")


if __name__=="__main__":
    main()
