"""Parameter-recovery diagnostic: true P4 providers vs I1-M2 vs genuine I2a-M2.

This is a post-hoc diagnostic for the synthetic benchmark. It deliberately opens
the known hidden P4 generator parameters only after the I1/I2a reconstructions
and graph predictions have been frozen. It does not alter any scientific method.

Truth mapping:
    mean_service_time = D_instructions * execution_fraction_x / effective_IPT
because the surrogate adapter maps
    nominal_instruction_mean = mean_service_time * IPT / x.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402

BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
I1_ROOT=PHASE5/"results"/"03_reconstruction_v3b"/"P4"
I2A_ROOT=HERE/"results"/"04_i2a_genuine_reconstruction_p4"
OUT=HERE/"results"/"07_p4_parameter_recovery"
PROVIDERS=("ProviderA","ProviderB","ProviderC")


def _truth() -> dict[str,dict[str,float]]:
    cfg=read_json(BATTERY)
    world=[x for x in cfg["provider_worlds"] if str(x["id"])=="P4"]
    if len(world)!=1:
        raise RuntimeError("P4 world not uniquely defined")
    world=world[0]
    fam=cfg["provider_family"]
    ipt=float(fam["effective_IPT"])
    x=float(fam["execution_fraction_x"])
    kappa=float(fam["cost_rate"])
    cv=float(fam["instruction_cv"])
    out={}
    for p in PROVIDERS:
        D=float(world["provider_means"][p])
        out[p]={
            "mean_service_time":D*x/ipt,
            "cost_rate":kappa,
            "service_cv":cv,
            "instruction_mean":D,
        }
    return out


def _norm_error(row:pd.Series, truth:dict[str,float], domain:pd.Series)->float:
    # Normalize mu and kappa in the same log coordinates used by reconstruction,
    # and CV linearly over its frozen search range.
    def zn(v,lo,hi):
        return (math.log(float(v))-math.log(float(lo)))/(math.log(float(hi))-math.log(float(lo)))
    z_mu_hat=zn(row["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"])
    z_mu_true=zn(truth["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"])
    z_k_hat=zn(row["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"])
    z_k_true=zn(truth["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"])
    cv_lo=float(domain["service_cv_lower"]); cv_hi=float(domain["service_cv_upper"])
    z_cv_hat=(float(row["service_cv"])-cv_lo)/(cv_hi-cv_lo)
    z_cv_true=(float(truth["service_cv"])-cv_lo)/(cv_hi-cv_lo)
    return float(np.sqrt(
        (z_mu_hat-z_mu_true)**2+
        (z_k_hat-z_k_true)**2+
        (z_cv_hat-z_cv_true)**2
    ))


def run()->Path:
    truth=_truth()
    domains=pd.read_csv(PHASE5/"results"/"03_reconstruction"/"phase5_m1_domain_registry.csv")
    rows=[]
    for provider in PROVIDERS:
        d=domains[
            (domains["provider_world_id"].astype(str)=="P4")
            & (domains["provider_id"].astype(str)==provider)
        ]
        if len(d)!=1:
            raise RuntimeError(f"{provider}: domain row count !=1")
        domain=d.iloc[0]
        t=truth[provider]

        rows.append({
            "provider_id":provider,
            "method":"TRUE",
            "rank":0,
            "candidate_id":"HIDDEN_GENERATOR",
            "mean_service_time":t["mean_service_time"],
            "cost_rate":t["cost_rate"],
            "service_cv":t["service_cv"],
            "instruction_mean":t["instruction_mean"],
            "mu_abs_error":0.0,
            "mu_rel_error_pct":0.0,
            "cost_rate_abs_error":0.0,
            "cost_rate_rel_error_pct":0.0,
            "service_cv_abs_error":0.0,
            "service_cv_rel_error_pct":0.0,
            "normalized_parameter_distance":0.0,
        })

        sources={
            "I1_M2":I1_ROOT/provider/"m2_provider_models.csv",
            "I2A_M2_GENUINE":I2A_ROOT/provider/"i2a_m2_provider_models.csv",
        }
        for method,path in sources.items():
            if not path.is_file():
                raise FileNotFoundError(path)
            tab=pd.read_csv(path).reset_index(drop=True)
            if len(tab)!=3:
                raise RuntimeError(f"{provider}/{method}: expected three M2 provider models")
            for i,r in tab.iterrows():
                mu=float(r["mean_service_time"])
                k=float(r["cost_rate"])
                cv=float(r["service_cv"])
                rows.append({
                    "provider_id":provider,
                    "method":method,
                    "rank":i+1,
                    "candidate_id":str(r["candidate_id"]),
                    "mean_service_time":mu,
                    "cost_rate":k,
                    "service_cv":cv,
                    "instruction_mean":mu*float(read_json(BATTERY)["provider_family"]["effective_IPT"])/float(read_json(BATTERY)["provider_family"]["execution_fraction_x"]),
                    "mu_abs_error":abs(mu-t["mean_service_time"]),
                    "mu_rel_error_pct":100.0*abs(mu-t["mean_service_time"])/t["mean_service_time"],
                    "cost_rate_abs_error":abs(k-t["cost_rate"]),
                    "cost_rate_rel_error_pct":100.0*abs(k-t["cost_rate"])/t["cost_rate"],
                    "service_cv_abs_error":abs(cv-t["service_cv"]),
                    "service_cv_rel_error_pct":100.0*abs(cv-t["service_cv"])/t["service_cv"],
                    "normalized_parameter_distance":_norm_error(r,t,domain),
                })

    full=pd.DataFrame(rows).sort_values(
        ["provider_id","method","rank"],kind="mergesort"
    ).reset_index(drop=True)
    OUT.mkdir(parents=True,exist_ok=True)
    full_path=OUT/"p4_true_vs_i1_vs_i2a_all_m2_members.csv"
    full.to_csv(full_path,index=False)

    rank1=full[(full["rank"].astype(int).isin([0,1]))].copy()
    rank1_path=OUT/"p4_true_vs_i1_vs_i2a_rank1.csv"
    rank1.to_csv(rank1_path,index=False)

    summary=[]
    for provider in PROVIDERS:
        for method in ("I1_M2","I2A_M2_GENUINE"):
            g=full[
                (full["provider_id"]==provider)
                & (full["method"]==method)
            ]
            summary.append({
                "provider_id":provider,
                "method":method,
                "rank1_normalized_parameter_distance":float(g[g["rank"]==1]["normalized_parameter_distance"].iloc[0]),
                "best_of_top3_normalized_parameter_distance":float(g["normalized_parameter_distance"].min()),
                "mean_top3_normalized_parameter_distance":float(g["normalized_parameter_distance"].mean()),
                "rank1_mu_rel_error_pct":float(g[g["rank"]==1]["mu_rel_error_pct"].iloc[0]),
                "rank1_cost_rate_rel_error_pct":float(g[g["rank"]==1]["cost_rate_rel_error_pct"].iloc[0]),
                "rank1_service_cv_rel_error_pct":float(g[g["rank"]==1]["service_cv_rel_error_pct"].iloc[0]),
            })
    summary=pd.DataFrame(summary)
    summary_path=OUT/"p4_parameter_recovery_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest=OUT/"parameter_recovery_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_P4_PARAMETER_RECOVERY_DIAGNOSTIC_COMPLETE",
        "posthoc_diagnostic":True,
        "hidden_truth_opened":True,
        "hidden_truth_used_for_method_selection":False,
        "truth_mapping":"mean_service_time = D_instructions * execution_fraction_x / effective_IPT; cost_rate and service_cv from frozen provider family",
        "outputs":{
            "all_m2_members":str(full_path),
            "rank1":str(rank1_path),
            "summary":str(summary_path),
        },
        "output_hashes_sha256":{
            "all_m2_members":sha256_file(full_path),
            "rank1":sha256_file(rank1_path),
            "summary":sha256_file(summary_path),
        },
        "completed_utc":utc_now_iso(),
    })

    print("PHASE6_P4_PARAMETER_RECOVERY_DIAGNOSTIC_PASS")
    print("\\nTRUE AND RANK-1 RECONSTRUCTIONS")
    print(rank1[[
        "provider_id","method","rank","candidate_id",
        "mean_service_time","cost_rate","service_cv",
        "mu_rel_error_pct","cost_rate_rel_error_pct","service_cv_rel_error_pct",
        "normalized_parameter_distance",
    ]].to_string(index=False))
    print("\\nM2 TOP-3 PARAMETER RECOVERY SUMMARY")
    print(summary.to_string(index=False))
    print("\\noutput",OUT)
    return manifest


if __name__=="__main__":
    run()
