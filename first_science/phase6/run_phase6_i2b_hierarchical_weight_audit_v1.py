"""Audit hierarchical variability weighting over frozen public I2b windows.

The audit preserves equal outer mass across five SLA regions and eight lags,
and redistributes weight only across start horizons within each (region, lag)
block according to target temporal variation energy.

No simulation, reconstruction, graph prediction/WB, final WB, or hidden
provider parameter is read.
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

CFG=HERE/"config_phase6_i2b_hierarchical_weight_audit_v1.json"
REP_CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
PROTOCOL=HERE/"PHASE6_I2B_HIERARCHICAL_WEIGHT_AUDIT_PROTOCOL_2026-10-09.md"
PUBLIC_ROOT=HERE/"results"/"22_i2b_public_representation"
ROOT=HERE/"results"/"31_i2b_hierarchical_weight_audit"

EXPECTED="FROZEN_PHASE6_I2B_HIERARCHICAL_WEIGHT_AUDIT_V1"
EXPECTED_REP="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
LAGS=(20.0,30.0,40.0,50.0,75.0,100.0,150.0,200.0)
SHUFFLE_REPS=(0,1,2)
BASE_SEED=620001
OUTER_BLOCK_MASS=1.0/(5.0*8.0)
TOL=1e-12


def _assert_contracts()->dict[str,Any]:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected hierarchical-weight audit status")
    rep=read_json(REP_CFG)
    sampling=read_json(SAMPLING_CFG)
    if rep.get("status")!=EXPECTED_REP:
        raise RuntimeError("unexpected public I2b representation status")
    if sampling.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected temporal-sampling status")
    if int(sampling["temporal_sampling"]["stride_s"])!=10:
        raise RuntimeError("frozen I2b stride changed")
    if tuple(float(x) for x in sampling["temporal_sampling"]["lags_s"])!=LAGS:
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
        det=np.maximum(-d,0.0)
        imp=np.maximum(d,0.0)
        rows.append({
            "region_id":str(rid),
            "region_rho":float(rho),
            "start_H":float(start),
            "end_H":float(end),
            "lag_s":float(lag),
            "window_n":100,
            "variation_energy":float(np.mean(d*d)),
            "deterioration_energy":float(np.mean(det*det)),
            "improvement_energy":float(np.mean(imp*imp)),
            "mean_abs_change":float(np.mean(np.abs(d))),
            "max_abs_change":float(np.max(np.abs(d))),
            "changed_fraction":float(np.mean(np.abs(d)>1e-12)),
        })

    out=pd.DataFrame(rows)
    if len(out)!=630:
        raise RuntimeError(f"expected 630 windows/provider, found {len(out)}")
    if out["region_id"].nunique()!=5:
        raise RuntimeError("expected exactly five SLA regions")
    if tuple(sorted(out["lag_s"].unique().astype(float)))!=LAGS:
        raise RuntimeError("lag support mismatch")

    total=float(out["variation_energy"].sum())
    if not math.isfinite(total) or total<=0.0:
        raise RuntimeError("zero/nonfinite total temporal variation")
    out["global_variability_weight"]=out["variation_energy"].astype(float)/total

    hier=np.zeros(len(out),dtype=float)
    zero_blocks=np.zeros(len(out),dtype=bool)
    block_rows=[]
    for (rid,lag),idx in out.groupby(["region_id","lag_s"],sort=True).groups.items():
        ix=np.asarray(list(idx),dtype=int)
        vals=out.loc[ix,"variation_energy"].astype(float).to_numpy()
        block_total=float(vals.sum())
        n=len(ix)
        if n<1:
            raise RuntimeError("empty hierarchical block")
        if block_total<=TOL:
            local=np.full(n,1.0/n,dtype=float)
            zero_blocks[ix]=True
            fallback=True
        else:
            local=vals/block_total
            fallback=False
        hier[ix]=OUTER_BLOCK_MASS*local
        neff=1.0/float(np.sum(local*local))
        block_rows.append({
            "region_id":str(rid),
            "lag_s":float(lag),
            "start_window_count":int(n),
            "block_variation_energy":block_total,
            "zero_variation_fallback":bool(fallback),
            "local_effective_start_count":neff,
            "local_effective_start_fraction":float(neff/n),
            "max_local_start_weight":float(local.max()),
        })

    out["hierarchical_weight"]=hier
    out["zero_variation_block_fallback"]=zero_blocks

    if abs(float(out["hierarchical_weight"].sum())-1.0)>1e-12:
        raise RuntimeError("hierarchical weights do not normalize")

    # Exact outer-mass invariants.
    region_mass=out.groupby("region_id")["hierarchical_weight"].sum()
    lag_mass=out.groupby("lag_s")["hierarchical_weight"].sum()
    if not np.allclose(region_mass.to_numpy(dtype=float),0.2,atol=1e-12,rtol=0.0):
        raise RuntimeError("hierarchical region masses are not exactly 1/5")
    if not np.allclose(lag_mass.to_numpy(dtype=float),0.125,atol=1e-12,rtol=0.0):
        raise RuntimeError("hierarchical lag masses are not exactly 1/8")

    blocks=pd.DataFrame(block_rows)
    if len(blocks)!=40:
        raise RuntimeError(f"expected 40 region-lag blocks, found {len(blocks)}")
    return out,blocks


def _mass_n(weights:np.ndarray,target:float)->int:
    w=np.sort(np.asarray(weights,dtype=float))[::-1]
    cs=np.cumsum(w)
    return min(len(w),int(np.searchsorted(cs,float(target),side="left"))+1)


def _weighted_score(detail:pd.DataFrame,weights:pd.DataFrame,column:str)->float:
    keys=["region_id","lag_s","start_H","end_H"]
    m=detail.merge(
        weights[keys+[column]],
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    if len(m)!=630:
        raise RuntimeError("energy-detail/weight join incomplete")
    return float(
        np.sum(
            m["energy_vstat"].astype(float).to_numpy()
            *m[column].astype(float).to_numpy()
        )
    )


def _provider_summary(
    world:str,
    provider:str,
    windows:pd.DataFrame,
    blocks:pd.DataFrame,
    equal_scores:list[float],
    global_scores:list[float],
    hierarchical_scores:list[float],
)->dict[str,Any]:
    w=windows["hierarchical_weight"].astype(float).to_numpy()
    ordered=np.sort(w)[::-1]
    effective=1.0/float(np.sum(w*w))
    total_v=float(windows["variation_energy"].sum())
    total_det=float(windows["deterioration_energy"].sum())
    total_imp=float(windows["improvement_energy"].sum())
    region_mass=windows.groupby("region_id")["hierarchical_weight"].sum().astype(float)
    lag_mass=windows.groupby("lag_s")["hierarchical_weight"].sum().astype(float)
    return {
        "provider_world_id":world,
        "provider_id":provider,
        "window_count":int(len(windows)),
        "block_count":int(len(blocks)),
        "zero_variation_block_count":int(blocks["zero_variation_fallback"].sum()),
        "max_window_weight":float(ordered[0]),
        "top10_mass":float(ordered[:10].sum()),
        "top25_mass":float(ordered[:25].sum()),
        "top50_mass":float(ordered[:50].sum()),
        "effective_window_count":effective,
        "effective_window_fraction":float(effective/len(windows)),
        "windows_for_50pct_mass":_mass_n(w,0.50),
        "windows_for_80pct_mass":_mass_n(w,0.80),
        "windows_for_90pct_mass":_mass_n(w,0.90),
        "min_block_effective_start_count":float(blocks["local_effective_start_count"].min()),
        "max_block_effective_start_count":float(blocks["local_effective_start_count"].max()),
        "mean_block_effective_start_count":float(blocks["local_effective_start_count"].mean()),
        "max_region_mass_error_from_0p2":float(np.max(np.abs(region_mass.to_numpy()-0.2))),
        "max_lag_mass_error_from_0p125":float(np.max(np.abs(lag_mass.to_numpy()-0.125))),
        "deterioration_energy_share":float(total_det/total_v),
        "improvement_energy_share":float(total_imp/total_v),
        "shuffle_equal_lag_energy_mean":float(np.mean(equal_scores)),
        "shuffle_global_var_energy_mean":float(np.mean(global_scores)),
        "shuffle_hierarchical_var_energy_mean":float(np.mean(hierarchical_scores)),
        "shuffle_hierarchical_var_energy_min":float(np.min(hierarchical_scores)),
        "shuffle_hierarchical_var_energy_max":float(np.max(hierarchical_scores)),
    }


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
    block_frames=[]
    region_frames=[]
    lag_frames=[]
    input_hashes={}

    tasks=[(w,p) for w in WORLDS for p in PROVIDERS]
    for ordinal,(world,provider) in enumerate(tasks,start=1):
        path=_pair_path(world,provider)
        _validate_public(world,provider,path)
        input_hashes[f"{world}/{provider}"]=sha256_file(path)
        pairs=pd.read_csv(path)

        windows,blocks=_window_table(pairs)
        for frame in (windows,blocks):
            frame.insert(0,"provider_id",provider)
            frame.insert(0,"provider_world_id",world)
        window_frames.append(windows)
        block_frames.append(blocks)

        region=(
            windows.groupby(["region_id","region_rho"],as_index=False,sort=True)
            .agg(
                window_count=("hierarchical_weight","size"),
                hierarchical_weight_mass=("hierarchical_weight","sum"),
                global_variability_weight_mass=("global_variability_weight","sum"),
                total_variation_energy=("variation_energy","sum"),
            )
        )
        region.insert(0,"provider_id",provider)
        region.insert(0,"provider_world_id",world)
        region_frames.append(region)

        lag=(
            windows.groupby("lag_s",as_index=False,sort=True)
            .agg(
                window_count=("hierarchical_weight","size"),
                hierarchical_weight_mass=("hierarchical_weight","sum"),
                global_variability_weight_mass=("global_variability_weight","sum"),
                total_variation_energy=("variation_energy","sum"),
            )
        )
        lag.insert(0,"provider_id",provider)
        lag.insert(0,"provider_world_id",world)
        lag_frames.append(lag)

        target=prepare_public_target(pairs)
        equal_scores=[]
        global_scores=[]
        hier_scores=[]
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
            global_score=_weighted_score(
                detail,windows,"global_variability_weight"
            )
            hier_score=_weighted_score(
                detail,windows,"hierarchical_weight"
            )
            if hier_score<=0.0 or not math.isfinite(hier_score):
                raise RuntimeError(
                    f"{world}/{provider}: nonpositive hierarchical shuffle sensitivity"
                )
            equal_scores.append(float(equal))
            global_scores.append(float(global_score))
            hier_scores.append(float(hier_score))

        rec=_provider_summary(
            world,provider,windows,blocks,
            equal_scores,global_scores,hier_scores,
        )
        provider_rows.append(rec)
        print(
            f"I2B HIER-WEIGHT {ordinal}/12 {world}/{provider} "
            f"max_w={rec['max_window_weight']:.5f} "
            f"Neff={rec['effective_window_count']:.1f}/630 "
            f"top50={rec['top50_mass']:.3f} "
            f"zero_blocks={rec['zero_variation_block_count']}",
            flush=True,
        )

    summary=pd.DataFrame(provider_rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    windows=pd.concat(window_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","region_rho","lag_s","start_H"],
        kind="mergesort",
    ).reset_index(drop=True)
    blocks=pd.concat(block_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","region_id","lag_s"],
        kind="mergesort",
    ).reset_index(drop=True)
    regions=pd.concat(region_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","region_rho"],
        kind="mergesort",
    ).reset_index(drop=True)
    lags=pd.concat(lag_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","lag_s"],
        kind="mergesort",
    ).reset_index(drop=True)

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
        "total_zero_variation_blocks":int(summary["zero_variation_block_count"].sum()),
        "max_region_mass_error_from_0p2":float(summary["max_region_mass_error_from_0p2"].max()),
        "max_lag_mass_error_from_0p125":float(summary["max_lag_mass_error_from_0p125"].max()),
        "mean_shuffle_equal_lag_energy":float(summary["shuffle_equal_lag_energy_mean"].mean()),
        "mean_shuffle_global_var_energy":float(summary["shuffle_global_var_energy_mean"].mean()),
        "mean_shuffle_hierarchical_var_energy":float(summary["shuffle_hierarchical_var_energy_mean"].mean()),
        "all_hierarchical_shuffle_positive":bool(
            (summary["shuffle_hierarchical_var_energy_min"]>0.0).all()
        ),
    }

    summary_path=ROOT/"provider_hierarchical_weight_summary.csv"
    windows_path=ROOT/"window_hierarchical_weights.csv"
    blocks_path=ROOT/"block_hierarchical_weight_summary.csv"
    regions_path=ROOT/"region_weight_mass_by_provider.csv"
    lags_path=ROOT/"lag_weight_mass_by_provider.csv"
    summary.to_csv(summary_path,index=False)
    windows.to_csv(windows_path,index=False)
    blocks.to_csv(blocks_path,index=False)
    regions.to_csv(regions_path,index=False)
    lags.to_csv(lags_path,index=False)

    manifest_path=ROOT/"i2b_hierarchical_weight_audit_manifest.json"
    bundle_path=ROOT/"i2b_hierarchical_weight_audit_bundle.zip"
    outputs={
        "provider_summary":str(summary_path),
        "window_weights":str(windows_path),
        "block_summary":str(blocks_path),
        "region_mass":str(regions_path),
        "lag_mass":str(lags_path),
        "upload_bundle":str(bundle_path),
    }
    write_json(manifest_path,{
        "status":"PHASE6_I2B_HIERARCHICAL_WEIGHT_AUDIT_COMPLETE",
        "development_evidence":True,
        "development_note":"Weighting design informed by P4/G_SEQPAR; no graph data read by this audit.",
        "code_commit":git_head(),
        "contracts_sha256":{
            "audit_config":sha256_file(CFG),
            "public_representation_config":sha256_file(REP_CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "protocol":sha256_file(PROTOCOL),
        },
        "inputs_sha256":input_hashes,
        "weight_definition":"equal region 1/5 x equal lag 1/8 x target variation-energy-normalized starts within each region-lag block",
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
            "block_summary":sha256_file(blocks_path),
            "region_mass":sha256_file(regions_path),
            "lag_mass":sha256_file(lags_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    })
    _zip(
        bundle_path,
        [summary_path,windows_path,blocks_path,regions_path,lags_path,manifest_path],
    )

    print("\nPHASE6_I2B_HIERARCHICAL_WEIGHT_AUDIT_PASS")
    print("\nPROVIDER CONCENTRATION")
    print(summary.to_string(index=False))
    print("\nP4 REGION MASSES: HIERARCHICAL VS GLOBAL-V2")
    print(
        regions[regions["provider_world_id"]=="P4"][
            [
                "provider_id","region_id","region_rho",
                "hierarchical_weight_mass","global_variability_weight_mass",
            ]
        ].to_string(index=False)
    )
    print("\nAGGREGATE")
    for k,v in aggregate.items():
        print(f"{k}: {v}")
    print("\nUPLOAD BUNDLE",bundle_path)
    print("output",ROOT)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(
        description="Audit hierarchical public I2b variability-derived weights"
    )
    _=p.parse_args()
    run()


if __name__=="__main__":
    main()
