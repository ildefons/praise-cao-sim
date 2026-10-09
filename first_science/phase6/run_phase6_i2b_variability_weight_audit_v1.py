"""Audit provider-specific variability weighting over frozen I2b windows.

Uses only the already-public I2b-v1 temporal-pair files. No simulation,
reconstruction, graph prediction/WB, final WB, or hidden provider parameter.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import (  # noqa:E402
    git_head, read_json, sha256_file, utc_now_iso, write_json,
)
from i2b_energy_loss_v1 import (  # noqa:E402
    prepare_public_target,
    score_candidate_windows,
    shuffled_endpoint_candidate,
)

CFG=HERE/"config_phase6_i2b_variability_weight_audit_v1.json"
REP_CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
PROTOCOL=HERE/"PHASE6_I2B_VARIABILITY_WEIGHT_AUDIT_PROTOCOL_2026-10-09.md"
PUBLIC_ROOT=HERE/"results"/"22_i2b_public_representation"
ROOT=HERE/"results"/"27_i2b_variability_weight_audit"

EXPECTED="FROZEN_PHASE6_I2B_VARIABILITY_WEIGHT_AUDIT_V1"
EXPECTED_REP="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SHUFFLE_REPS=(0,1,2)
BASE_SEED=620001
TOL=1e-15


def _assert_contracts()->dict[str,Any]:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected variability-weight audit status")
    rep=read_json(REP_CFG)
    sampling=read_json(SAMPLING_CFG)
    if rep.get("status")!=EXPECTED_REP:
        raise RuntimeError("unexpected public I2b representation status")
    if sampling.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected temporal-sampling status")
    if int(sampling["temporal_sampling"]["stride_s"])!=10:
        raise RuntimeError("frozen I2b stride changed")
    if tuple(int(x) for x in sampling["temporal_sampling"]["lags_s"]) != (
        20,30,40,50,75,100,150,200
    ):
        raise RuntimeError("frozen I2b lag set changed")
    return cfg


def _pair_path(world:str,provider:str)->Path:
    return PUBLIC_ROOT/world/provider/"i2b_public_temporal_pairs.csv"


def _validate_public(world:str,provider:str,path:Path)->None:
    manifest=PUBLIC_ROOT/world/provider/"i2b_public_representation_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    m=read_json(manifest)
    if m.get("status")!="PHASE6_I2B_PUBLIC_PROVIDER_COMPLETE":
        raise RuntimeError(f"{world}/{provider}: public I2b manifest incomplete")
    if sha256_file(path)!=str(m["output_hashes_sha256"]["temporal_pairs"]):
        raise RuntimeError(f"{world}/{provider}: public pair hash mismatch")


def _window_table(pairs:pd.DataFrame)->pd.DataFrame:
    required={
        "region_id","region_rho","start_H","end_H","lag_s",
        "compliance_start","compliance_end",
    }
    missing=required.difference(pairs.columns)
    if missing:
        raise RuntimeError(f"public pair file missing {sorted(missing)}")

    rows=[]
    for key,g in pairs.groupby(
        ["region_id","region_rho","start_H","end_H","lag_s"],sort=True
    ):
        rid,rho,start,end,lag=key
        if len(g)!=100:
            raise RuntimeError(f"window {key} does not contain N=100")
        a=g["compliance_start"].astype(float).to_numpy()
        b=g["compliance_end"].astype(float).to_numpy()
        d=b-a
        v=float(np.mean(d*d))
        det=np.maximum(-d,0.0)
        imp=np.maximum(d,0.0)
        rows.append({
            "region_id":str(rid),
            "region_rho":float(rho),
            "start_H":float(start),
            "end_H":float(end),
            "lag_s":float(lag),
            "window_n":100,
            "variation_energy":v,
            "deterioration_energy":float(np.mean(det*det)),
            "improvement_energy":float(np.mean(imp*imp)),
            "mean_abs_change":float(np.mean(np.abs(d))),
            "max_abs_change":float(np.max(np.abs(d))),
            "changed_fraction":float(np.mean(np.abs(d)>1e-12)),
        })
    out=pd.DataFrame(rows)
    if len(out)!=630:
        raise RuntimeError(f"expected 630 windows/provider, found {len(out)}")
    total=float(out["variation_energy"].sum())
    if not math.isfinite(total) or total<=0.0:
        raise RuntimeError("provider has zero/nonfinite total temporal variation energy")
    out["variability_weight"]=out["variation_energy"].astype(float)/total
    if abs(float(out["variability_weight"].sum())-1.0)>1e-12:
        raise RuntimeError("variability weights do not normalize")
    return out


def _mass_n(weights:np.ndarray,target:float)->int:
    w=np.sort(np.asarray(weights,dtype=float))[::-1]
    cs=np.cumsum(w)
    idx=int(np.searchsorted(cs,float(target),side="left"))
    return min(len(w),idx+1)


def _provider_summary(
    world:str,
    provider:str,
    w:pd.DataFrame,
    shuffle_equal:list[float],
    shuffle_weighted:list[float],
)->dict[str,Any]:
    weights=w["variability_weight"].astype(float).to_numpy()
    ordered=np.sort(weights)[::-1]
    total_v=float(w["variation_energy"].astype(float).sum())
    total_det=float(w["deterioration_energy"].astype(float).sum())
    total_imp=float(w["improvement_energy"].astype(float).sum())
    effective=1.0/float(np.sum(weights*weights))
    return {
        "provider_world_id":world,
        "provider_id":provider,
        "window_count":int(len(w)),
        "total_variation_energy":total_v,
        "max_window_weight":float(ordered[0]),
        "top10_mass":float(ordered[:10].sum()),
        "top25_mass":float(ordered[:25].sum()),
        "top50_mass":float(ordered[:50].sum()),
        "effective_window_count":effective,
        "effective_window_fraction":float(effective/len(w)),
        "windows_for_50pct_mass":_mass_n(weights,0.50),
        "windows_for_80pct_mass":_mass_n(weights,0.80),
        "windows_for_90pct_mass":_mass_n(weights,0.90),
        "deterioration_energy_share":float(total_det/total_v),
        "improvement_energy_share":float(total_imp/total_v),
        "shuffle_equal_lag_energy_mean":float(np.mean(shuffle_equal)),
        "shuffle_variability_weighted_energy_mean":float(np.mean(shuffle_weighted)),
        "shuffle_variability_weighted_energy_min":float(np.min(shuffle_weighted)),
        "shuffle_variability_weighted_energy_max":float(np.max(shuffle_weighted)),
    }


def _weighted_shuffle_score(
    target,
    detail:pd.DataFrame,
    weights:pd.DataFrame,
)->float:
    keys=["region_id","lag_s","start_H","end_H"]
    m=detail.merge(
        weights[keys+["variability_weight"]],
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    if len(m)!=len(target.windows):
        raise RuntimeError("shuffle-detail/weight join incomplete")
    return float(
        np.sum(
            m["energy_vstat"].astype(float).to_numpy()
            *m["variability_weight"].astype(float).to_numpy()
        )
    )


def _zip(bundle:Path,paths:list[Path])->None:
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p,arcname=p.name)


def run()->Path:
    _assert_contracts()
    ROOT.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()

    provider_rows=[]
    window_frames=[]
    lag_frames=[]
    region_frames=[]
    input_hashes={}

    for ordinal,(world,provider) in enumerate(
        [(w,p) for w in WORLDS for p in PROVIDERS],
        start=1,
    ):
        path=_pair_path(world,provider)
        _validate_public(world,provider,path)
        input_hashes[f"{world}/{provider}"]=sha256_file(path)
        pairs=pd.read_csv(path)

        windows=_window_table(pairs)
        windows.insert(0,"provider_id",provider)
        windows.insert(0,"provider_world_id",world)
        window_frames.append(windows)

        lag=(
            windows.groupby("lag_s",as_index=False,sort=True)
            .agg(
                window_count=("variability_weight","size"),
                weight_mass=("variability_weight","sum"),
                mean_variation_energy=("variation_energy","mean"),
                median_variation_energy=("variation_energy","median"),
                mean_abs_change=("mean_abs_change","mean"),
                mean_changed_fraction=("changed_fraction","mean"),
                deterioration_energy=("deterioration_energy","sum"),
                improvement_energy=("improvement_energy","sum"),
            )
        )
        lag.insert(0,"provider_id",provider)
        lag.insert(0,"provider_world_id",world)
        lag_frames.append(lag)

        region=(
            windows.groupby(["region_id","region_rho"],as_index=False,sort=True)
            .agg(
                window_count=("variability_weight","size"),
                weight_mass=("variability_weight","sum"),
                mean_variation_energy=("variation_energy","mean"),
                deterioration_energy=("deterioration_energy","sum"),
                improvement_energy=("improvement_energy","sum"),
            )
        )
        region.insert(0,"provider_id",provider)
        region.insert(0,"provider_world_id",world)
        region_frames.append(region)

        target=prepare_public_target(pairs)
        equal_scores=[]
        weighted_scores=[]
        for rep in SHUFFLE_REPS:
            shuffled=shuffled_endpoint_candidate(
                target,
                provider_world_id=world,
                provider_id=provider,
                base_seed=BASE_SEED,
                repetition=rep,
                candidate_n=100,
            )
            equal,_,detail=score_candidate_windows(target,shuffled)
            weighted=_weighted_shuffle_score(target,detail,windows)
            if not math.isfinite(weighted) or weighted<=0.0:
                raise RuntimeError(
                    f"{world}/{provider}: nonpositive weighted shuffle sensitivity"
                )
            equal_scores.append(float(equal))
            weighted_scores.append(float(weighted))

        provider_rows.append(
            _provider_summary(
                world,provider,windows,equal_scores,weighted_scores
            )
        )
        print(
            f"I2B VAR-WEIGHT {ordinal}/12 {world}/{provider} "
            f"max_w={provider_rows[-1]['max_window_weight']:.5f} "
            f"Neff={provider_rows[-1]['effective_window_count']:.1f}/630 "
            f"top50={provider_rows[-1]['top50_mass']:.3f}",
            flush=True,
        )

    summary=pd.DataFrame(provider_rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    windows=pd.concat(window_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","region_rho","lag_s","start_H"],
        kind="mergesort",
    ).reset_index(drop=True)
    lag_detail=pd.concat(lag_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","lag_s"],kind="mergesort"
    ).reset_index(drop=True)
    region_detail=pd.concat(region_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","region_rho"],kind="mergesort"
    ).reset_index(drop=True)

    # Cross-provider lag view for quick interpretation; provider weights each
    # normalize independently, so this is a mean provider mass, not a pooled weight.
    lag_aggregate=(
        lag_detail.groupby("lag_s",as_index=False,sort=True)
        .agg(
            mean_provider_weight_mass=("weight_mass","mean"),
            min_provider_weight_mass=("weight_mass","min"),
            max_provider_weight_mass=("weight_mass","max"),
            mean_variation_energy=("mean_variation_energy","mean"),
            mean_abs_change=("mean_abs_change","mean"),
        )
    )

    summary_path=ROOT/"provider_weight_concentration_summary.csv"
    windows_path=ROOT/"window_variability_weights.csv"
    lag_path=ROOT/"lag_weight_mass_by_provider.csv"
    region_path=ROOT/"region_weight_mass_by_provider.csv"
    lag_agg_path=ROOT/"lag_weight_mass_aggregate.csv"
    summary.to_csv(summary_path,index=False)
    windows.to_csv(windows_path,index=False)
    lag_detail.to_csv(lag_path,index=False)
    region_detail.to_csv(region_path,index=False)
    lag_aggregate.to_csv(lag_agg_path,index=False)

    aggregate={
        "providers":12,
        "mean_max_window_weight":float(summary["max_window_weight"].mean()),
        "max_max_window_weight":float(summary["max_window_weight"].max()),
        "mean_top10_mass":float(summary["top10_mass"].mean()),
        "max_top10_mass":float(summary["top10_mass"].max()),
        "mean_top50_mass":float(summary["top50_mass"].mean()),
        "max_top50_mass":float(summary["top50_mass"].max()),
        "mean_effective_window_count":float(summary["effective_window_count"].mean()),
        "min_effective_window_count":float(summary["effective_window_count"].min()),
        "mean_effective_window_fraction":float(summary["effective_window_fraction"].mean()),
        "min_effective_window_fraction":float(summary["effective_window_fraction"].min()),
        "mean_windows_for_50pct_mass":float(summary["windows_for_50pct_mass"].mean()),
        "min_windows_for_50pct_mass":int(summary["windows_for_50pct_mass"].min()),
        "mean_deterioration_energy_share":float(summary["deterioration_energy_share"].mean()),
        "mean_improvement_energy_share":float(summary["improvement_energy_share"].mean()),
        "mean_shuffle_equal_lag_energy":float(
            summary["shuffle_equal_lag_energy_mean"].mean()
        ),
        "mean_shuffle_variability_weighted_energy":float(
            summary["shuffle_variability_weighted_energy_mean"].mean()
        ),
        "all_weighted_shuffle_positive":bool(
            (summary["shuffle_variability_weighted_energy_min"]>0.0).all()
        ),
    }

    manifest_path=ROOT/"i2b_variability_weight_audit_manifest.json"
    bundle_path=ROOT/"i2b_variability_weight_audit_bundle.zip"
    outputs={
        "provider_summary":str(summary_path),
        "window_weights":str(windows_path),
        "lag_detail":str(lag_path),
        "region_detail":str(region_path),
        "lag_aggregate":str(lag_agg_path),
        "upload_bundle":str(bundle_path),
    }
    write_json(manifest_path,{
        "status":"PHASE6_I2B_VARIABILITY_WEIGHT_AUDIT_COMPLETE",
        "development_evidence":True,
        "code_commit":git_head(),
        "contracts_sha256":{
            "audit_config":sha256_file(CFG),
            "public_representation_config":sha256_file(REP_CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "protocol":sha256_file(PROTOCOL),
        },
        "inputs_sha256":input_hashes,
        "weight_definition":"omega_w = mean((c_end-c_start)^2) / sum_w mean((c_end-c_start)^2), normalized within provider",
        "aggregate":aggregate,
        "new_provider_simulation":False,
        "provider_reconstruction_run":False,
        "graph_prediction_read":False,
        "graph_wb_read":False,
        "final_wb_read":False,
        "hidden_provider_parameters_read":False,
        "outputs":outputs,
        "output_hashes_sha256":{
            "provider_summary":sha256_file(summary_path),
            "window_weights":sha256_file(windows_path),
            "lag_detail":sha256_file(lag_path),
            "region_detail":sha256_file(region_path),
            "lag_aggregate":sha256_file(lag_agg_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    })
    _zip(
        bundle_path,
        [summary_path,windows_path,lag_path,region_path,lag_agg_path,manifest_path],
    )

    print("\nPHASE6_I2B_VARIABILITY_WEIGHT_AUDIT_PASS")
    print("\nPROVIDER CONCENTRATION")
    print(summary.to_string(index=False))
    print("\nLAG WEIGHT MASS AGGREGATE")
    print(lag_aggregate.to_string(index=False))
    print("\nAGGREGATE")
    for k,v in aggregate.items():
        print(f"{k}: {v}")
    print("\nUPLOAD BUNDLE",bundle_path)
    print("output",ROOT)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(
        description="Audit public I2b variability-derived temporal-window weights"
    )
    _=p.parse_args()
    run()


if __name__=="__main__":
    main()
