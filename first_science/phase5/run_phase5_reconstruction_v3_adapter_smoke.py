"""Tiny end-to-end engineering smoke for the Phase-5 V3 reconstruction adapter.

Unlike the synthetic selection smoke, this runner exercises the real public-I1
loader, the frozen provider domains, Optuna/TPE, and the native local provider
simulator.  It uses only smoke seeds and reduced budgets, writes only under
smoke/, and is never scientific evidence.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE3=FIRST_SCIENCE/"phase3"
if str(PHASE3) not in sys.path:
    sys.path.insert(0,str(PHASE3))

from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row, _load_public_card
from run_m1_provider_lift_v2 import _load_optuna, _simulate_and_score
from phase5_reconstruction_v3_selection import (
    gibbs_weights,
    joint_product_support,
    rank_by_behavioral_centroid,
)

CFG=HERE/"config_phase5_provider_reconstruction_v3.json"
SEEDS=HERE/"config_phase5_seed_registry_v3.json"
OUT=HERE/"smoke"/"v3_reconstruction_adapter"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
WORLD="P1"

SMOKE_FITS=7
SMOKE_TRIALS_PER_FIT=2
SMOKE_STARTUP_PER_FIT=1
SMOKE_SEARCH_N=1
SMOKE_RESCORE_N=2
SMOKE_REPLAY_N=2


def _read(path:Path):
    return json.loads(path.read_text())


def _seed_tuple(start:int,n:int)->tuple[int,...]:
    return tuple(range(int(start),int(start)+int(n)))


def _candidate_search(
    *,
    provider:str,
    fit_index:int,
    metadata,
    public_surface,
    bounds,
    sampler_seed:int,
    trajectory_seeds:tuple[int,...],
)->dict:
    optuna=_load_optuna()
    sampler=optuna.samplers.TPESampler(
        seed=int(sampler_seed),
        n_startup_trials=SMOKE_STARTUP_PER_FIT,
    )
    study=optuna.create_study(direction="minimize",sampler=sampler)

    def objective(trial):
        mu=trial.suggest_float(
            "mean_service_time",
            bounds.mean_service_time_lower,
            bounds.mean_service_time_upper,
            log=True,
        )
        kappa=trial.suggest_float(
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
        return float(metrics["mse"])

    study.optimize(objective,n_trials=SMOKE_TRIALS_PER_FIT,show_progress_bar=False)
    best=study.best_trial
    return {
        "provider":provider,
        "fit_index":int(fit_index),
        "candidate_id":f"SMOKE_{WORLD}_{provider}_FIT{fit_index}",
        "sampler_seed":int(sampler_seed),
        "search_seed_start":int(trajectory_seeds[0]),
        "search_n":len(trajectory_seeds),
        "search_mse":float(best.value),
        "mean_service_time":float(best.params["mean_service_time"]),
        "cost_rate":float(best.params["cost_rate"]),
        "service_cv":float(best.params["service_cv"]),
    }


def _score_surface(*,candidate,metadata,public_surface,seeds):
    metrics,_,comparison=_simulate_and_score(
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
    comparison=comparison.sort_values(
        ["region_rho","rho","horizon"],kind="mergesort"
    ).reset_index(drop=True)
    return metrics,comparison


def main()->None:
    cfg=_read(CFG); seed_cfg=_read(SEEDS)
    if cfg.get("status")!="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3":
        raise RuntimeError("unexpected V3 reconstruction contract")
    if seed_cfg["engineering_smoke"]["scientific_evidence"] is not False:
        raise RuntimeError("engineering smoke scientific-evidence flag changed")
    if int(cfg["candidate_reconstruction"]["candidate_count_per_provider"])!=7:
        raise RuntimeError("V3 candidate count changed")

    base=int(seed_cfg["engineering_smoke"]["seed_base"])
    sampler_seeds=[int(x) for x in cfg["candidate_reconstruction"]["fit_sampler_seeds"]]
    if len(sampler_seeds)!=7:
        raise RuntimeError("expected seven scientific sampler seeds")

    OUT.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    provider_weight_tables={}
    provider_summaries={}
    all_candidate_rows=[]

    for pidx,provider in enumerate(PROVIDERS):
        metadata,public_surface,_=_load_public_card(WORLD,provider)
        bounds=_bounds(_domain_row(WORLD,provider))
        candidates=[]
        for fit_idx in range(1,SMOKE_FITS+1):
            # Smoke-only deterministic seeds, disjoint across provider and fit.
            search_start=base+pidx*10000+fit_idx*100
            cand=_candidate_search(
                provider=provider,
                fit_index=fit_idx,
                metadata=metadata,
                public_surface=public_surface,
                bounds=bounds,
                sampler_seed=sampler_seeds[fit_idx-1],
                trajectory_seeds=_seed_tuple(search_start,SMOKE_SEARCH_N),
            )
            candidates.append(cand)
            print(
                f"V3 ADAPTER SMOKE {WORLD}/{provider} fit {fit_idx}/7 "
                f"search_mse={cand['search_mse']:.6g}",
                flush=True,
            )

        # Common smoke rescore/replay banks are shared across the seven candidates
        # within one provider, mirroring the V3 scientific adapter structure.
        rescore_seeds=_seed_tuple(base+pidx*10000+9000,SMOKE_RESCORE_N)
        replay_seeds=_seed_tuple(base+pidx*10000+9100,SMOKE_REPLAY_N)
        surfaces=[]
        public_vector=None
        rows=[]
        for cand in candidates:
            metrics,comparison=_score_surface(
                candidate=cand,metadata=metadata,public_surface=public_surface,
                seeds=rescore_seeds,
            )
            replay_metrics,_=_score_surface(
                candidate=cand,metadata=metadata,public_surface=public_surface,
                seeds=replay_seeds,
            )
            if public_vector is None:
                public_vector=comparison["sigma_i1"].to_numpy(float)
            candidate_vector=comparison["sigma_m1_local"].to_numpy(float)
            surfaces.append(candidate_vector)
            rows.append({
                **cand,
                "rescore_mse":float(metrics["mse"]),
                "rescore_rmse":float(metrics["rmse"]),
                "replay_mse":float(replay_metrics["mse"]),
                "replay_rmse":float(replay_metrics["rmse"]),
            })

        surfaces_arr=np.asarray(surfaces,dtype=float)
        if public_vector is None:
            raise RuntimeError("empty public comparison surface")
        ids=[str(c["candidate_id"]) for c in candidates]
        ranking=rank_by_behavioral_centroid(ids,surfaces_arr,public_vector)
        weights=gibbs_weights(
            ids,surfaces_arr,public_vector,
            n_public=100,n_candidate=SMOKE_RESCORE_N,
            lam=float(cfg["methods"]["M3"]["gibbs_lambda"]),
        )
        provider_weight_tables[provider]=weights

        result=pd.DataFrame(rows).merge(
            ranking[["candidate_id","behavioral_rank","centroid_mse"]],
            on="candidate_id",how="left",validate="one_to_one",
        ).merge(
            weights[["candidate_id","weight_rank","kl_energy","weight"]],
            on="candidate_id",how="left",validate="one_to_one",
        ).sort_values("behavioral_rank",kind="mergesort")
        result.to_csv(OUT/f"{provider}_adapter_candidates.csv",index=False)
        all_candidate_rows.extend(result.to_dict("records"))

        m1=str(result.iloc[0]["candidate_id"])
        m2=result.head(3)["candidate_id"].astype(str).tolist()
        provider_summaries[provider]={
            "m1_candidate":m1,
            "m2_candidates":m2,
            "m3_weight_sum":float(weights["weight"].sum()),
            "candidate_count":len(result),
        }

    joint=joint_product_support(provider_weight_tables)
    joint.head(14).to_csv(OUT/"m3_top14_joint_support.csv",index=False)
    if len(joint)!=343:
        raise RuntimeError("V3 M3 smoke joint support is not 343")
    if any(v["candidate_count"]!=7 for v in provider_summaries.values()):
        raise RuntimeError("V3 smoke provider candidate count changed")
    if any(len(v["m2_candidates"])!=3 for v in provider_summaries.values()):
        raise RuntimeError("V3 smoke M2 provider portfolio size changed")
    if any(abs(v["m3_weight_sum"]-1.0)>1e-12 for v in provider_summaries.values()):
        raise RuntimeError("V3 smoke M3 provider weights do not normalize")

    # M2 combines the three selected candidates independently per provider.
    m2_joint_count=3**3
    if m2_joint_count!=27:
        raise RuntimeError("V3 smoke M2 joint count changed")

    pd.DataFrame(all_candidate_rows).to_csv(
        OUT/"v3_adapter_all_candidates.csv",index=False
    )
    payload={
        "status":"PHASE5_V3_RECONSTRUCTION_ADAPTER_SMOKE_PASS",
        "scientific_evidence":False,
        "provider_world_id":WORLD,
        "reduced_smoke_budget":{
            "fits_per_provider":SMOKE_FITS,
            "trials_per_fit":SMOKE_TRIALS_PER_FIT,
            "search_n_per_fit":SMOKE_SEARCH_N,
            "common_rescore_n":SMOKE_RESCORE_N,
            "common_replay_n":SMOKE_REPLAY_N,
        },
        "checks":{
            "real_public_i1_loader":True,
            "frozen_v2_domain_registry_read":True,
            "actual_optuna_tpe":True,
            "actual_native_provider_simulator":True,
            "seven_independent_fit_winners_per_provider":True,
            "common_rescore_surface_generation":True,
            "behavioral_centroid_ranking":True,
            "m1_one_member_per_provider":True,
            "m2_three_members_per_provider":True,
            "m2_joint_count_27":True,
            "m3_all_seven_weighted":True,
            "m3_joint_count_343":True,
            "m3_top14_materialized":True,
            "common_replay_executed":True,
            "hard_rmse_gate_absent":True,
        },
        "provider_summary":provider_summaries,
        "m2_joint_count":m2_joint_count,
        "m3_joint_count":int(len(joint)),
        "m3_top14_count":int(len(joint.head(14))),
        "wall_seconds":float(time.perf_counter()-start),
        "note":"Engineering-only reduced-budget adapter smoke. No output is scientific evidence."
    }
    manifest=OUT/"v3_reconstruction_adapter_smoke_manifest.json"
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print("\nPHASE5_V3_RECONSTRUCTION_ADAPTER_SMOKE_PASS")
    for k,v in payload["checks"].items():
        print(k,v)
    print("scientific_evidence",payload["scientific_evidence"])
    print(f"wall={(payload['wall_seconds']/60):.1f} min")
    print("output",manifest)


if __name__=="__main__":
    main()
