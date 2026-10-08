"""Dual-loss provider diagnostic for P4.

Compare the hidden synthetic truth, all seven frozen I1-generated V3 candidates,
and all seven genuine I2a-generated candidates under BOTH provider-local losses:

  1) the original I1 sigma-surface RMSE on the common N=100 rescore bank;
  2) the I2a full-marginal mean empirical W1 on the same N=100 rescore bank.

Hidden truth is opened only for post-hoc diagnosis. It is never used to select,
fit, rank, or modify a reconstruction method.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
PHASE3=HERE.parent/"phase3"
for p in (PHASE5,PHASE3):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

from run_phase5_m2_reconstruction_v2 import _bounds, _domain_row, _load_public_card  # noqa:E402
from run_m1_provider_lift_v2 import _simulate_and_score  # noqa:E402
from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402
from run_phase6_i2a_genuine_reconstruction_p4_v1 import (  # noqa:E402
    _load_target as _load_i2a_target,
    _score as _score_i2a,
    _seed_tuple,
    _simulate_samples as _simulate_i2a_samples,
)

WORLD="P4"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
BATTERY=PHASE5/"config_phase5_recoverability_battery_v2.json"
SEEDS=PHASE5/"config_phase5_seed_registry_v3.json"
I1_ROOT=PHASE5/"results"/"03_reconstruction_v3b"/WORLD
I2A_ROOT=HERE/"results"/"04_i2a_genuine_reconstruction_p4"
OUT=HERE/"results"/"08_p4_dual_loss_diagnostic"


def _truth()->dict[str,dict[str,float]]:
    cfg=read_json(BATTERY)
    world=[x for x in cfg["provider_worlds"] if str(x["id"])==WORLD]
    if len(world)!=1:
        raise RuntimeError("P4 world not uniquely defined")
    fam=cfg["provider_family"]
    ipt=float(fam["effective_IPT"])
    x=float(fam["execution_fraction_x"])
    kappa=float(fam["cost_rate"])
    cv=float(fam["instruction_cv"])
    return {
        p:{
            "mean_service_time":float(world[0]["provider_means"][p])*x/ipt,
            "cost_rate":kappa,
            "service_cv":cv,
        }
        for p in PROVIDERS
    }


def _norm_distance(theta:dict[str,float], truth:dict[str,float], domain:pd.Series)->float:
    def zlog(v,lo,hi):
        return (math.log(float(v))-math.log(float(lo)))/(math.log(float(hi))-math.log(float(lo)))
    zmu=zlog(theta["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"])
    zmu_t=zlog(truth["mean_service_time"],domain["mean_service_time_lower"],domain["mean_service_time_upper"])
    zk=zlog(theta["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"])
    zk_t=zlog(truth["cost_rate"],domain["cost_rate_lower"],domain["cost_rate_upper"])
    lo=float(domain["service_cv_lower"]); hi=float(domain["service_cv_upper"])
    zcv=(float(theta["service_cv"])-lo)/(hi-lo)
    zcv_t=(float(truth["service_cv"])-lo)/(hi-lo)
    return float(np.sqrt((zmu-zmu_t)**2+(zk-zk_t)**2+(zcv-zcv_t)**2))


def _candidate_bank(provider:str)->pd.DataFrame:
    i1_path=I1_ROOT/provider/"m3_provider_models.csv"
    i2_path=I2A_ROOT/provider/"i2a_candidate_rescore.csv"
    if not i1_path.is_file():
        raise FileNotFoundError(i1_path)
    if not i2_path.is_file():
        raise FileNotFoundError(i2_path)

    i1=pd.read_csv(i1_path).copy()
    i2=pd.read_csv(i2_path).copy()
    need={"candidate_id","mean_service_time","cost_rate","service_cv"}
    if len(i1)!=7 or not need.issubset(i1.columns):
        raise RuntimeError(f"{provider}: I1 bank is not seven parameterized candidates")
    if len(i2)!=7 or not need.issubset(i2.columns):
        raise RuntimeError(f"{provider}: I2a bank is not seven parameterized candidates")

    i1=i1[list(need)].copy()
    i1["source_family"]="I1_GENERATED"
    i2=i2[list(need)].copy()
    i2["source_family"]="I2A_GENERATED"
    return pd.concat([i1,i2],ignore_index=True)


def _eval_one(
    *,
    provider:str,
    candidate_id:str,
    source_family:str,
    theta:dict[str,float],
    metadata,
    public_surface,
    i2a_target,
    seeds:tuple[int,...],
    truth:dict[str,float],
    domain:pd.Series,
)->dict:
    i1_metrics,_,_=_simulate_and_score(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=float(theta["mean_service_time"]),
        cost_rate=float(theta["cost_rate"]),
        service_cv=float(theta["service_cv"]),
        trajectory_seeds=seeds,
        canonical_ipt=1_000_000.0,
        execution_fraction=0.5,
        quiet=True,
    )
    samples=_simulate_i2a_samples(
        metadata=metadata,
        mean_service_time=float(theta["mean_service_time"]),
        cost_rate=float(theta["cost_rate"]),
        service_cv=float(theta["service_cv"]),
        seeds=seeds,
    )
    mean_w1,median_w1,max_w1=_score_i2a(i2a_target,samples)
    return {
        "provider_id":provider,
        "candidate_id":candidate_id,
        "source_family":source_family,
        "mean_service_time":float(theta["mean_service_time"]),
        "cost_rate":float(theta["cost_rate"]),
        "service_cv":float(theta["service_cv"]),
        "i1_mse":float(i1_metrics["mse"]),
        "i1_rmse":float(i1_metrics["rmse"]),
        "i1_mae":float(i1_metrics["mae"]),
        "i1_bias":float(i1_metrics["bias"]),
        "i1_max_abs_error":float(i1_metrics["max_abs_error"]),
        "i2a_mean_w1":mean_w1,
        "i2a_median_w1":median_w1,
        "i2a_max_w1":max_w1,
        "normalized_parameter_distance":_norm_distance(theta,truth,domain),
    }


def _plot_provider(provider:str,table:pd.DataFrame)->Path:
    fig,ax=plt.subplots(figsize=(7.2,5.6))
    specs={
        "TRUE":{"marker":"*","s":180},
        "I1_GENERATED":{"marker":"o","s":70},
        "I2A_GENERATED":{"marker":"s","s":70},
    }
    for family,spec in specs.items():
        g=table[table["source_family"]==family]
        ax.scatter(
            g["i1_rmse"].astype(float),
            g["i2a_mean_w1"].astype(float),
            label=family.replace("_"," "),
            marker=spec["marker"],s=spec["s"],alpha=0.85,
        )
    truth=table[table["source_family"]=="TRUE"].iloc[0]
    ax.annotate(
        "TRUE",
        (float(truth["i1_rmse"]),float(truth["i2a_mean_w1"])),
        xytext=(6,6),textcoords="offset points",fontsize=9,
    )
    for family in ("I1_GENERATED","I2A_GENERATED"):
        g=table[table["source_family"]==family]
        best_i1=g.sort_values(["i1_rmse","candidate_id"],kind="mergesort").iloc[0]
        best_i2=g.sort_values(["i2a_mean_w1","candidate_id"],kind="mergesort").iloc[0]
        for label,row in (("best I1",best_i1),("best I2a",best_i2)):
            ax.annotate(
                f"{family.split('_')[0]} {label}",
                (float(row["i1_rmse"]),float(row["i2a_mean_w1"])),
                xytext=(5,-10),textcoords="offset points",fontsize=7,
            )
    ax.set_xlabel("I1 sigma-surface RMSE (lower is better)")
    ax.set_ylabel("I2a mean Wasserstein-1 (lower is better)")
    ax.set_title(f"P4 {provider}: provider reconstruction dual-loss map")
    ax.grid(True,alpha=0.2)
    ax.legend(frameon=False)
    path=OUT/f"p4_{provider}_dual_loss_scatter.png"
    fig.tight_layout()
    fig.savefig(path,dpi=220,bbox_inches="tight")
    plt.close(fig)
    return path


def run()->Path:
    OUT.mkdir(parents=True,exist_ok=True)
    seed_cfg=read_json(SEEDS)
    seeds=_seed_tuple(seed_cfg["provider_reconstruction"]["common_rescore"])
    if len(seeds)!=100:
        raise RuntimeError("common rescore bank is not N=100")

    truths=_truth()
    all_rows=[]
    plots=[]
    summary_rows=[]
    for provider in PROVIDERS:
        metadata,public_surface,_=_load_public_card(WORLD,provider)
        _,_,i2a_target=_load_i2a_target(provider)
        domain=_domain_row(WORLD,provider)
        truth=truths[provider]

        rows=[_eval_one(
            provider=provider,
            candidate_id="HIDDEN_GENERATOR",
            source_family="TRUE",
            theta=truth,
            metadata=metadata,
            public_surface=public_surface,
            i2a_target=i2a_target,
            seeds=seeds,
            truth=truth,
            domain=domain,
        )]
        bank=_candidate_bank(provider)
        for rec in bank.itertuples(index=False):
            theta={
                "mean_service_time":float(rec.mean_service_time),
                "cost_rate":float(rec.cost_rate),
                "service_cv":float(rec.service_cv),
            }
            rows.append(_eval_one(
                provider=provider,
                candidate_id=str(rec.candidate_id),
                source_family=str(rec.source_family),
                theta=theta,
                metadata=metadata,
                public_surface=public_surface,
                i2a_target=i2a_target,
                seeds=seeds,
                truth=truth,
                domain=domain,
            ))

        table=pd.DataFrame(rows)
        all_rows.append(table)
        plots.append(_plot_provider(provider,table))

        t=table[table["source_family"]=="TRUE"].iloc[0]
        for family in ("I1_GENERATED","I2A_GENERATED"):
            g=table[table["source_family"]==family].copy()
            best_i1=g.sort_values(["i1_rmse","candidate_id"],kind="mergesort").iloc[0]
            best_i2=g.sort_values(["i2a_mean_w1","candidate_id"],kind="mergesort").iloc[0]
            closest=g.sort_values(["normalized_parameter_distance","candidate_id"],kind="mergesort").iloc[0]
            summary_rows.append({
                "provider_id":provider,
                "source_family":family,
                "truth_i1_rmse":float(t["i1_rmse"]),
                "truth_i2a_mean_w1":float(t["i2a_mean_w1"]),
                "best_i1_candidate_id":str(best_i1["candidate_id"]),
                "best_i1_rmse":float(best_i1["i1_rmse"]),
                "best_i1_candidate_i2a_w1":float(best_i1["i2a_mean_w1"]),
                "best_i1_parameter_distance":float(best_i1["normalized_parameter_distance"]),
                "best_i2a_candidate_id":str(best_i2["candidate_id"]),
                "best_i2a_mean_w1":float(best_i2["i2a_mean_w1"]),
                "best_i2a_candidate_i1_rmse":float(best_i2["i1_rmse"]),
                "best_i2a_parameter_distance":float(best_i2["normalized_parameter_distance"]),
                "closest_parameter_candidate_id":str(closest["candidate_id"]),
                "closest_parameter_distance":float(closest["normalized_parameter_distance"]),
                "closest_parameter_i1_rmse":float(closest["i1_rmse"]),
                "closest_parameter_i2a_w1":float(closest["i2a_mean_w1"]),
            })

    all_table=pd.concat(all_rows,ignore_index=True).sort_values(
        ["provider_id","source_family","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    all_path=OUT/"p4_dual_loss_all_candidates.csv"
    all_table.to_csv(all_path,index=False)

    summary=pd.DataFrame(summary_rows).sort_values(
        ["provider_id","source_family"],kind="mergesort"
    ).reset_index(drop=True)
    summary_path=OUT/"p4_dual_loss_summary.csv"
    summary.to_csv(summary_path,index=False)

    # Also expose a compact truth-vs-best table for terminal inspection.
    print("PHASE6_P4_DUAL_LOSS_DIAGNOSTIC_PASS")
    print("\\nTRUTH VS BEST CANDIDATES UNDER EACH LOSS")
    print(summary.to_string(index=False))
    print("\\nALL CANDIDATES",all_path)
    for p in plots:
        print("plot",p)

    manifest=OUT/"dual_loss_manifest.json"
    outputs={
        "all_candidates":str(all_path),
        "summary":str(summary_path),
    }
    for p in plots:
        outputs[p.stem]=str(p)
    write_json(manifest,{
        "status":"PHASE6_P4_DUAL_LOSS_PROVIDER_DIAGNOSTIC_COMPLETE",
        "posthoc_diagnostic":True,
        "hidden_truth_opened":True,
        "hidden_truth_used_for_method_selection":False,
        "common_rescore_seed_start":int(seeds[0]),
        "common_rescore_seed_end_inclusive":int(seeds[-1]),
        "common_rescore_n":len(seeds),
        "candidate_families":["I1_GENERATED","I2A_GENERATED"],
        "losses":["I1 sigma-surface RMSE","I2a full-marginal mean empirical W1"],
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    })
    print("manifest",manifest)
    return manifest


if __name__=="__main__":
    run()
