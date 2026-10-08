"""Static audit of the P4 I1 vs genuine-I2a inverse-search algorithms.

No simulation is run. This post-hoc development diagnostic opens hidden truth
only to understand why the richer I2a search failed to recover parameters.

Checks:
- whether hidden truth lies inside the frozen reconstruction domain;
- whether I1 and I2a used identical startup proposals as intended;
- whether either 7x25 search ever visited the true-parameter neighborhood;
- whether search loss is aligned with parameter distance to truth;
- how much the keep-one-winner-per-fit reduction discards good points.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
DOMAINS=PHASE5/"results"/"03_reconstruction"/"phase5_m1_domain_registry.csv"
I1_ROOT=PHASE5/"results"/"03_reconstruction_v3"/"P4"
I2_ROOT=HERE/"results"/"04_i2a_genuine_reconstruction_p4"
OUT=HERE/"results"/"09_p4_reconstruction_algorithm_audit"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
FIT_COUNT=7
STARTUP=5
TRIALS_PER_FIT=25


def _read_json(path:Path):
    import json
    return json.loads(path.read_text())


def _truth():
    cfg=_read_json(BATTERY)
    world=[w for w in cfg["provider_worlds"] if str(w["id"])=="P4"][0]
    fam=cfg["provider_family"]
    x=float(fam["execution_fraction_x"])
    ipt=float(fam["effective_IPT"])
    return {
        p:{
            "mean_service_time":float(world["provider_means"][p])*x/ipt,
            "cost_rate":float(fam["cost_rate"]),
            "service_cv":float(fam["instruction_cv"]),
        } for p in PROVIDERS
    }


def _znorm(theta,domain):
    def zl(v,lo,hi):
        return (math.log(float(v))-math.log(float(lo)))/(math.log(float(hi))-math.log(float(lo)))
    return np.array([
        zl(theta["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"]),
        zl(theta["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"]),
        (float(theta["service_cv"])-float(domain["service_cv_lower"]))/
        (float(domain["service_cv_upper"])-float(domain["service_cv_lower"])),
    ],dtype=float)


def _distance(row,truth,domain):
    a=_znorm({
        "mean_service_time":row["mean_service_time"],
        "cost_rate":row["cost_rate"],
        "service_cv":row["service_cv"],
    },domain)
    b=_znorm(truth,domain)
    return float(np.linalg.norm(a-b))


def _load_family(provider,family):
    rows=[]
    root=I1_ROOT if family=="I1" else I2_ROOT
    loss_col="search_mse" if family=="I1" else "search_mean_w1"
    for fit in range(1,FIT_COUNT+1):
        path=root/provider/"fits"/f"fit_{fit}"/"trials.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        t=pd.read_csv(path)
        if len(t)!=TRIALS_PER_FIT:
            raise RuntimeError(f"{family}/{provider}/fit{fit}: expected 25 trials")
        required={"trial_number","mean_service_time","cost_rate","service_cv",loss_col}
        if not required.issubset(t.columns):
            raise RuntimeError(f"{family}/{provider}/fit{fit}: missing columns")
        t=t[list(required)].copy()
        t["fit_index"]=fit
        t["family"]=family
        t=t.rename(columns={loss_col:"search_loss"})
        rows.append(t)
    return pd.concat(rows,ignore_index=True)


def _loss_rank_within_fit(frame):
    out=[]
    for fit,g in frame.groupby("fit_index",sort=True):
        gg=g.sort_values(["search_loss","trial_number"],kind="mergesort").copy()
        gg["loss_rank_within_fit"]=np.arange(1,len(gg)+1)
        out.append(gg)
    return pd.concat(out,ignore_index=True)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    domains=pd.read_csv(DOMAINS)
    truths=_truth()
    domain_rows=[]
    summary_rows=[]
    startup_rows=[]
    all_frames=[]

    for provider in PROVIDERS:
        d=domains[
            (domains["provider_world_id"].astype(str)=="P4")
            & (domains["provider_id"].astype(str)==provider)
        ]
        if len(d)!=1:
            raise RuntimeError(f"{provider}: domain row count !=1")
        domain=d.iloc[0]
        truth=truths[provider]
        z=_znorm(truth,domain)
        inside=bool(np.all((z>=0.0)&(z<=1.0)))
        domain_rows.append({
            "provider_id":provider,
            "truth_mean_service_time":truth["mean_service_time"],
            "truth_cost_rate":truth["cost_rate"],
            "truth_service_cv":truth["service_cv"],
            "mean_service_time_lower":float(domain["mean_service_time_lower"]),
            "mean_service_time_upper":float(domain["mean_service_time_upper"]),
            "cost_rate_lower":float(domain["cost_rate_lower"]),
            "cost_rate_upper":float(domain["cost_rate_upper"]),
            "service_cv_lower":float(domain["service_cv_lower"]),
            "service_cv_upper":float(domain["service_cv_upper"]),
            "truth_z_log_mu":float(z[0]),
            "truth_z_log_kappa":float(z[1]),
            "truth_z_cv":float(z[2]),
            "truth_inside_domain":inside,
        })

        fam={}
        for family in ("I1","I2A"):
            frame=_load_family(provider,family)
            frame["parameter_distance"]=frame.apply(
                lambda r:_distance(r,truth,domain),axis=1
            )
            frame=_loss_rank_within_fit(frame)
            fam[family]=frame
            all_frames.append(frame.assign(provider_id=provider))

            best_loss=frame.sort_values(
                ["search_loss","fit_index","trial_number"],kind="mergesort"
            ).iloc[0]
            closest=frame.sort_values(
                ["parameter_distance","fit_index","trial_number"],kind="mergesort"
            ).iloc[0]
            winners=frame[frame["loss_rank_within_fit"].astype(int)==1]
            corr=float(
                frame["search_loss"].rank(method="average").corr(
                    frame["parameter_distance"].rank(method="average")
                )
            )
            summary_rows.append({
                "provider_id":provider,
                "family":family,
                "n_trials":len(frame),
                "best_search_loss":float(best_loss["search_loss"]),
                "best_loss_parameter_distance":float(best_loss["parameter_distance"]),
                "closest_parameter_distance":float(closest["parameter_distance"]),
                "closest_fit_index":int(closest["fit_index"]),
                "closest_trial_number":int(closest["trial_number"]),
                "closest_search_loss":float(closest["search_loss"]),
                "closest_loss_rank_within_fit":int(closest["loss_rank_within_fit"]),
                "best_winner_parameter_distance":float(winners["parameter_distance"].min()),
                "mean_winner_parameter_distance":float(winners["parameter_distance"].mean()),
                "points_distance_le_0p10":int((frame["parameter_distance"]<=0.10).sum()),
                "points_distance_le_0p20":int((frame["parameter_distance"]<=0.20).sum()),
                "points_distance_le_0p30":int((frame["parameter_distance"]<=0.30).sum()),
                "spearman_search_loss_vs_parameter_distance":corr,
            })

        # The first five Optuna proposals should be identical because both
        # searches reuse the same sampler seed, domain and startup count.
        for fit in range(1,FIT_COUNT+1):
            a=fam["I1"][
                (fam["I1"]["fit_index"]==fit)
                & (fam["I1"]["trial_number"]<STARTUP)
            ].sort_values("trial_number")
            b=fam["I2A"][
                (fam["I2A"]["fit_index"]==fit)
                & (fam["I2A"]["trial_number"]<STARTUP)
            ].sort_values("trial_number")
            cols=["mean_service_time","cost_rate","service_cv"]
            equal=bool(np.allclose(
                a[cols].to_numpy(float),b[cols].to_numpy(float),
                rtol=0.0,atol=1e-14,
            ))
            startup_rows.append({
                "provider_id":provider,
                "fit_index":fit,
                "startup_points":len(a),
                "startup_parameters_identical":equal,
                "max_abs_parameter_difference":float(
                    np.max(np.abs(a[cols].to_numpy(float)-b[cols].to_numpy(float)))
                ),
            })

    domain_table=pd.DataFrame(domain_rows)
    summary=pd.DataFrame(summary_rows)
    startup=pd.DataFrame(startup_rows)
    all_trials=pd.concat(all_frames,ignore_index=True)

    domain_path=OUT/"p4_truth_domain_check.csv"
    summary_path=OUT/"p4_search_efficiency_summary.csv"
    startup_path=OUT/"p4_startup_proposal_identity.csv"
    trials_path=OUT/"p4_all_search_trials_with_truth_distance.csv"
    domain_table.to_csv(domain_path,index=False)
    summary.to_csv(summary_path,index=False)
    startup.to_csv(startup_path,index=False)
    all_trials.to_csv(trials_path,index=False)

    print("PHASE6_P4_RECONSTRUCTION_ALGORITHM_AUDIT_PASS")
    print("\nTRUTH INSIDE FROZEN SEARCH DOMAIN")
    print(domain_table.to_string(index=False))
    print("\nSEARCH EFFICIENCY / VISIT TO TRUE NEIGHBORHOOD")
    print(summary.to_string(index=False))
    print("\nSTARTUP PROPOSAL IDENTITY")
    print(startup.to_string(index=False))
    print("\noutput",OUT)


if __name__=="__main__":
    run()
