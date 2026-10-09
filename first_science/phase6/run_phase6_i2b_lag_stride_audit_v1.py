"""Initial Phase-6 I2b lag/stride information-cost audit.

Uses the exact Phase-5 provider-local N=100 I1 ledgers, preserving trajectory
identity privately, to measure lag-dependent rank persistence and how much of
that curve is retained when sliding-window starts are subsampled.

No new provider simulation, provider reconstruction, graph prediction, graph WB,
final WB, or hidden provider parameter is used.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402
from run_phase6_i2a_marginal_audit_v1 import _compliance_samples_from_ledger  # noqa:E402

CFG=HERE/"config_phase6_i2b_lag_stride_audit_v1.json"
P5_I1=PHASE5/"results"/"01_i1"
OUT=HERE/"results"/"21_i2b_lag_stride_audit"

WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
STRIDES=(5,10,15,20,25,30,40,50)
HORIZONS=tuple(float(x) for x in range(5,241,5))
LAGS=tuple(float(x) for x in range(5,240,5))
EXPECTED="FROZEN_PHASE6_I2B_LAG_STRIDE_AUDIT_V1"
TOL=1e-12


def _midranks(values:np.ndarray)->np.ndarray:
    s=pd.Series(np.asarray(values,dtype=float))
    r=s.rank(method="average").to_numpy(dtype=float)
    n=float(len(r))
    return (r-0.5)/n


def _corr(a:np.ndarray,b:np.ndarray)->float:
    aa=np.asarray(a,dtype=float)
    bb=np.asarray(b,dtype=float)
    if np.std(aa)<=TOL or np.std(bb)<=TOL:
        return float("nan")
    return float(np.corrcoef(aa,bb)[0,1])


def _provider_window_rows(world:str,provider:str)->list[dict[str,Any]]:
    card=P5_I1/world/"public"/provider/"card.json"
    ledger_path=P5_I1/world/"private"/"sigma"/provider/"provider_request_ledgers.csv"
    if not card.is_file():
        raise FileNotFoundError(card)
    if not ledger_path.is_file():
        raise FileNotFoundError(ledger_path)

    metadata=read_json(card)
    ledger=pd.read_csv(ledger_path)
    samples=_compliance_samples_from_ledger(ledger,metadata=metadata)

    rows=[]
    for region_id,g in samples.groupby("region_id",sort=True):
        pivot=g.pivot(
            index="trajectory_private",
            columns="H",
            values="compliance_fraction",
        ).sort_index().sort_index(axis=1)
        cols=tuple(float(x) for x in pivot.columns)
        if cols!=HORIZONS:
            raise RuntimeError(
                f"{world}/{provider}/{region_id}: horizon grid mismatch"
            )
        if pivot.shape!=(100,48):
            raise RuntimeError(
                f"{world}/{provider}/{region_id}: compliance matrix shape {pivot.shape}"
            )

        c=pivot.to_numpy(dtype=float)
        u=np.empty_like(c,dtype=float)
        endpoint_nondegenerate=np.zeros(c.shape[1],dtype=bool)
        for hidx in range(c.shape[1]):
            u[:,hidx]=_midranks(c[:,hidx])
            endpoint_nondegenerate[hidx]=np.std(c[:,hidx])>TOL

        for i in range(len(HORIZONS)-1):
            for j in range(i+1,len(HORIZONS)):
                h0=HORIZONS[i]
                h1=HORIZONS[j]
                lag=h1-h0
                raw0=c[:,i]
                raw1=c[:,j]
                rank0=u[:,i]
                rank1=u[:,j]
                both_nonconstant=bool(
                    endpoint_nondegenerate[i] and endpoint_nondegenerate[j]
                )
                rows.append({
                    "provider_world_id":world,
                    "provider_id":provider,
                    "region_id":str(region_id),
                    "start_H":float(h0),
                    "end_H":float(h1),
                    "lag_s":float(lag),
                    "start_index":int(i),
                    "window_n":100,
                    "endpoint_nondegenerate":both_nonconstant,
                    "spearman_rank_persistence":(
                        _corr(rank0,rank1) if both_nonconstant else float("nan")
                    ),
                    "mean_abs_rank_displacement":float(
                        np.mean(np.abs(rank1-rank0))
                    ),
                    "mean_abs_compliance_displacement":float(
                        np.mean(np.abs(raw1-raw0))
                    ),
                    "fraction_raw_compliance_changed":float(
                        np.mean(np.abs(raw1-raw0)>TOL)
                    ),
                })
    return rows


def _curve_for_stride(windows:pd.DataFrame,stride:int)->pd.DataFrame:
    if stride%5:
        raise ValueError("stride must align with 5-s horizon grid")
    stride_steps=stride//5
    sub=windows[windows["start_index"].astype(int)%stride_steps==0].copy()

    rows=[]
    for lag,g in sub.groupby("lag_s",sort=True):
        sp=g["spearman_rank_persistence"].astype(float)
        finite=np.isfinite(sp.to_numpy())
        rows.append({
            "stride_s":int(stride),
            "lag_s":float(lag),
            "window_count":int(len(g)),
            "paired_trajectory_observations":int(len(g)*100),
            "informative_window_count":int(finite.sum()),
            "informative_window_fraction":float(finite.mean()),
            "mean_spearman_rank_persistence":(
                float(sp[finite].mean()) if finite.any() else float("nan")
            ),
            "median_spearman_rank_persistence":(
                float(sp[finite].median()) if finite.any() else float("nan")
            ),
            "mean_abs_rank_displacement":float(
                g["mean_abs_rank_displacement"].astype(float).mean()
            ),
            "mean_abs_compliance_displacement":float(
                g["mean_abs_compliance_displacement"].astype(float).mean()
            ),
            "mean_fraction_raw_compliance_changed":float(
                g["fraction_raw_compliance_changed"].astype(float).mean()
            ),
        })
    curve=pd.DataFrame(rows)
    if set(curve["lag_s"].astype(float))!=set(LAGS):
        raise RuntimeError(f"stride {stride}: incomplete lag support")
    return curve


def _finite_mae(a:pd.Series,b:pd.Series)->tuple[float,float,int]:
    aa=a.astype(float).to_numpy()
    bb=b.astype(float).to_numpy()
    mask=np.isfinite(aa)&np.isfinite(bb)
    if not np.any(mask):
        return float("nan"),float("nan"),0
    d=np.abs(aa[mask]-bb[mask])
    return float(d.mean()),float(d.max()),int(mask.sum())


def run()->Path:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected I2b lag/stride audit config")

    OUT.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()

    window_rows=[]
    input_hashes={}
    index=0
    for world in WORLDS:
        for provider in PROVIDERS:
            index+=1
            card=P5_I1/world/"public"/provider/"card.json"
            ledger=P5_I1/world/"private"/"sigma"/provider/"provider_request_ledgers.csv"
            input_hashes[f"{world}/{provider}/card"]=sha256_file(card)
            input_hashes[f"{world}/{provider}/ledger"]=sha256_file(ledger)
            rows=_provider_window_rows(world,provider)
            window_rows.extend(rows)
            print(
                f"I2B WINDOW AUDIT {index}/12 {world}/{provider} "
                f"windows={len(rows)}",
                flush=True,
            )

    windows=pd.DataFrame(window_rows)
    expected=12*5*(48*47//2)
    if len(windows)!=expected:
        raise RuntimeError(
            f"expected {expected} provider-region temporal windows, found {len(windows)}"
        )

    # This artifact is aggregated over trajectories.  No trajectory identifier
    # is persisted beyond the in-memory construction step.
    window_path=OUT/"window_level_aggregated_private_audit.csv"
    windows.to_csv(window_path,index=False)

    curves=[]
    for stride in STRIDES:
        curves.append(_curve_for_stride(windows,stride))
    curves=pd.concat(curves,ignore_index=True)
    curves_path=OUT/"lag_stride_curves.csv"
    curves.to_csv(curves_path,index=False)

    ref=curves[curves["stride_s"]==5].copy()
    stride_rows=[]
    ref_windows=int(ref["window_count"].sum())
    ref_pairs=int(ref["paired_trajectory_observations"].sum())

    for stride in STRIDES:
        c=curves[curves["stride_s"]==stride].copy()
        m=ref.merge(
            c,on="lag_s",suffixes=("_ref","_test"),validate="one_to_one"
        )

        p_mae,p_max,p_n=_finite_mae(
            m["mean_spearman_rank_persistence_ref"],
            m["mean_spearman_rank_persistence_test"],
        )
        r_mae,r_max,r_n=_finite_mae(
            m["mean_abs_rank_displacement_ref"],
            m["mean_abs_rank_displacement_test"],
        )
        c_mae,c_max,c_n=_finite_mae(
            m["mean_abs_compliance_displacement_ref"],
            m["mean_abs_compliance_displacement_test"],
        )
        f_mae,f_max,f_n=_finite_mae(
            m["mean_fraction_raw_compliance_changed_ref"],
            m["mean_fraction_raw_compliance_changed_test"],
        )

        windows_n=int(c["window_count"].sum())
        pairs_n=int(c["paired_trajectory_observations"].sum())
        stride_rows.append({
            "stride_s":int(stride),
            "total_temporal_windows":windows_n,
            "paired_trajectory_observations":pairs_n,
            "cost_ratio_vs_stride5":float(pairs_n/ref_pairs),
            "window_ratio_vs_stride5":float(windows_n/ref_windows),
            "persistence_curve_mae_vs_stride5":p_mae,
            "persistence_curve_max_abs_dev_vs_stride5":p_max,
            "persistence_curve_lags_compared":p_n,
            "rank_displacement_curve_mae_vs_stride5":r_mae,
            "rank_displacement_curve_max_abs_dev_vs_stride5":r_max,
            "rank_displacement_curve_lags_compared":r_n,
            "compliance_displacement_curve_mae_vs_stride5":c_mae,
            "compliance_displacement_curve_max_abs_dev_vs_stride5":c_max,
            "compliance_displacement_curve_lags_compared":c_n,
            "changed_fraction_curve_mae_vs_stride5":f_mae,
            "changed_fraction_curve_max_abs_dev_vs_stride5":f_max,
            "changed_fraction_curve_lags_compared":f_n,
        })

    stride_summary=pd.DataFrame(stride_rows)
    stride_path=OUT/"stride_cost_stability_summary.csv"
    stride_summary.to_csv(stride_path,index=False)

    sample_lags={10.0,20.0,30.0,40.0,50.0,75.0,100.0,150.0,200.0,235.0}
    lag_snapshot=ref[
        ref["lag_s"].astype(float).isin(sample_lags)
    ].copy()
    lag_snapshot_path=OUT/"reference_stride5_selected_lags.csv"
    lag_snapshot.to_csv(lag_snapshot_path,index=False)

    # Provider/world detail at the maximal stride-5 reference.  This helps
    # reveal whether the aggregate curve is masking very different regimes.
    provider_rows=[]
    for (world,provider,lag),g in windows.groupby(
        ["provider_world_id","provider_id","lag_s"],sort=True
    ):
        sp=g["spearman_rank_persistence"].astype(float)
        finite=np.isfinite(sp.to_numpy())
        provider_rows.append({
            "provider_world_id":str(world),
            "provider_id":str(provider),
            "lag_s":float(lag),
            "window_count":int(len(g)),
            "informative_window_fraction":float(finite.mean()),
            "mean_spearman_rank_persistence":(
                float(sp[finite].mean()) if finite.any() else float("nan")
            ),
            "mean_abs_rank_displacement":float(
                g["mean_abs_rank_displacement"].astype(float).mean()
            ),
            "mean_abs_compliance_displacement":float(
                g["mean_abs_compliance_displacement"].astype(float).mean()
            ),
            "mean_fraction_raw_compliance_changed":float(
                g["fraction_raw_compliance_changed"].astype(float).mean()
            ),
        })
    provider_detail=pd.DataFrame(provider_rows)
    provider_detail_path=OUT/"provider_lag_detail_stride5.csv"
    provider_detail.to_csv(provider_detail_path,index=False)

    print("\nPHASE6_I2B_LAG_STRIDE_AUDIT_PASS")
    print("\nSTRIDE COST / STABILITY")
    print(stride_summary.to_string(index=False))
    print("\nREFERENCE STRIDE=5: SELECTED LAGS")
    print(
        lag_snapshot[
            [
                "lag_s",
                "window_count",
                "informative_window_fraction",
                "mean_spearman_rank_persistence",
                "mean_abs_rank_displacement",
                "mean_abs_compliance_displacement",
                "mean_fraction_raw_compliance_changed",
            ]
        ].to_string(index=False)
    )

    outputs={
        "window_level_aggregated_private_audit":str(window_path),
        "lag_stride_curves":str(curves_path),
        "stride_cost_stability_summary":str(stride_path),
        "reference_stride5_selected_lags":str(lag_snapshot_path),
        "provider_lag_detail_stride5":str(provider_detail_path),
    }
    manifest=OUT/"i2b_lag_stride_audit_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_I2B_LAG_STRIDE_AUDIT_COMPLETE",
        "development_evidence":True,
        "new_provider_world_simulation":False,
        "provider_world_count":4,
        "provider_count":12,
        "region_count_per_provider":5,
        "trajectory_count_per_provider":100,
        "positive_horizon_count":48,
        "lag_count":47,
        "strides_s":list(STRIDES),
        "trajectory_identity_used_privately":True,
        "trajectory_identity_persisted":False,
        "rank_transform":"tie-aware empirical midrank u=(rank-0.5)/N",
        "graph_prediction_read":False,
        "graph_wb_read":False,
        "final_wb_read":False,
        "hidden_provider_parameters_read":False,
        "inputs_sha256":input_hashes,
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    })
    print("\noutput",OUT)
    return manifest


if __name__=="__main__":
    run()
