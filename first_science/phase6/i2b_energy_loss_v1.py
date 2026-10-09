"""Reusable Phase-6 I2b-v1 empirical energy-loss utilities.

The public I2b temporal object is an empirical bivariate distribution of
(compliance_start, compliance_end) for each frozen (region, start_H, lag)
window.  This module compares such joint distributions with the empirical
energy statistic

    E(P,Q) = 2 E||X-Y|| - E||X-X'|| - E||Y-Y'||,

using the V-statistic empirical expectations and Euclidean distance in the
two-dimensional compliance plane.

Aggregation is fixed by the temporal-sampling contract:
  - equal weight across selected lags;
  - within each lag, equal weight across all region x start-H windows.

No graph or white-box information is used here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TOL=1e-12
WindowKey=tuple[str,float,float,float]  # region_id, lag_s, start_H, end_H


@dataclass(frozen=True)
class PreparedWindow:
    points: np.ndarray
    self_mean_distance: float


@dataclass(frozen=True)
class PreparedI2bTarget:
    windows: dict[WindowKey,PreparedWindow]
    lags: tuple[float,...]


def _mean_pairwise_distance(a:np.ndarray,b:np.ndarray)->float:
    aa=np.asarray(a,dtype=float)
    bb=np.asarray(b,dtype=float)
    if aa.ndim!=2 or bb.ndim!=2 or aa.shape[1]!=2 or bb.shape[1]!=2:
        raise ValueError("I2b energy distance expects arrays shaped (N,2)")
    if len(aa)<1 or len(bb)<1:
        raise ValueError("I2b energy distance requires nonempty samples")
    d=aa[:,None,:]-bb[None,:,:]
    return float(np.sqrt(np.sum(d*d,axis=2)).mean())


def empirical_energy_vstat(
    target:np.ndarray,
    candidate:np.ndarray,
    *,
    target_self_mean:float|None=None,
)->float:
    """Return the nonnegative empirical energy V-statistic in R^2."""
    x=np.asarray(target,dtype=float)
    y=np.asarray(candidate,dtype=float)
    xx=(
        float(target_self_mean)
        if target_self_mean is not None
        else _mean_pairwise_distance(x,x)
    )
    yy=_mean_pairwise_distance(y,y)
    xy=_mean_pairwise_distance(x,y)
    value=2.0*xy-xx-yy
    if value<0.0 and abs(value)<=1e-12:
        value=0.0
    if value<-1e-10:
        raise RuntimeError(f"empirical energy statistic unexpectedly negative: {value}")
    return float(max(0.0,value))


def prepare_public_target(pairs:pd.DataFrame)->PreparedI2bTarget:
    required={
        "region_id","lag_s","start_H","end_H",
        "compliance_start","compliance_end",
    }
    missing=required.difference(pairs.columns)
    if missing:
        raise RuntimeError(f"I2b public pairs missing columns {sorted(missing)}")

    windows:dict[WindowKey,PreparedWindow]={}
    for key,g in pairs.groupby(
        ["region_id","lag_s","start_H","end_H"],sort=True
    ):
        rid,lag,start,end=key
        points=g[["compliance_start","compliance_end"]].to_numpy(dtype=float)
        if len(points)!=100:
            raise RuntimeError(f"public I2b target window {key} does not contain N=100")
        if ((points<-TOL)|(points>1.0+TOL)).any():
            raise RuntimeError(f"public I2b target window {key} outside [0,1]")
        wkey=(str(rid),float(lag),float(start),float(end))
        windows[wkey]=PreparedWindow(
            points=points,
            self_mean_distance=_mean_pairwise_distance(points,points),
        )

    if len(windows)!=630:
        raise RuntimeError(f"expected 630 I2b target windows/provider, found {len(windows)}")
    lags=tuple(sorted({float(k[1]) for k in windows}))
    expected=(20.0,30.0,40.0,50.0,75.0,100.0,150.0,200.0)
    if lags!=expected:
        raise RuntimeError(f"I2b target lag support changed: {lags}")
    return PreparedI2bTarget(windows=windows,lags=lags)


def score_candidate_windows(
    target:PreparedI2bTarget,
    candidate_windows:dict[WindowKey,np.ndarray],
)->tuple[float,pd.DataFrame,pd.DataFrame]:
    """Score candidate joint distributions with frozen equal-lag aggregation."""
    if set(candidate_windows)!=set(target.windows):
        missing=set(target.windows).difference(candidate_windows)
        extra=set(candidate_windows).difference(target.windows)
        raise RuntimeError(
            f"I2b candidate window support mismatch: missing={len(missing)} extra={len(extra)}"
        )

    rows=[]
    for key in sorted(target.windows,key=lambda z:(z[1],z[0],z[2],z[3])):
        rid,lag,start,end=key
        tw=target.windows[key]
        y=np.asarray(candidate_windows[key],dtype=float)
        if y.ndim!=2 or y.shape[1]!=2 or len(y)<1:
            raise RuntimeError(f"candidate I2b window {key} has invalid shape {y.shape}")
        if ((y<-TOL)|(y>1.0+TOL)).any():
            raise RuntimeError(f"candidate I2b window {key} outside [0,1]")
        rows.append({
            "region_id":rid,
            "lag_s":lag,
            "start_H":start,
            "end_H":end,
            "target_n":len(tw.points),
            "candidate_n":len(y),
            "energy_vstat":empirical_energy_vstat(
                tw.points,y,target_self_mean=tw.self_mean_distance
            ),
        })
    detail=pd.DataFrame(rows)

    lag_rows=[]
    for lag,g in detail.groupby("lag_s",sort=True):
        lag_rows.append({
            "lag_s":float(lag),
            "window_count":int(len(g)),
            "mean_energy_vstat":float(g["energy_vstat"].astype(float).mean()),
            "median_energy_vstat":float(g["energy_vstat"].astype(float).median()),
            "max_energy_vstat":float(g["energy_vstat"].astype(float).max()),
        })
    by_lag=pd.DataFrame(lag_rows)
    if tuple(by_lag["lag_s"].astype(float))!=target.lags:
        raise RuntimeError("I2b lag aggregation support changed")
    overall=float(by_lag["mean_energy_vstat"].astype(float).mean())
    return overall,by_lag,detail


def target_as_candidate(target:PreparedI2bTarget)->dict[WindowKey,np.ndarray]:
    return {k:v.points.copy() for k,v in target.windows.items()}


def _stable_rng(
    *,
    base_seed:int,
    provider_world_id:str,
    provider_id:str,
    key:WindowKey,
    repetition:int,
)->np.random.Generator:
    rid,lag,start,end=key
    token=(
        f"{int(base_seed)}|{provider_world_id}|{provider_id}|"
        f"{rid}|{lag:.12g}|{start:.12g}|{end:.12g}|{int(repetition)}"
    ).encode("utf-8")
    digest=hashlib.sha256(token).digest()
    seed=int.from_bytes(digest[:8],"little",signed=False)
    return np.random.default_rng(seed)


def shuffled_endpoint_candidate(
    target:PreparedI2bTarget,
    *,
    provider_world_id:str,
    provider_id:str,
    base_seed:int,
    repetition:int,
    candidate_n:int|None=None,
)->dict[WindowKey,np.ndarray]:
    """Destroy within-window pairing while preserving empirical marginals at N=100.

    When candidate_n < 100, independently subsample start and end coordinates
    without replacement after deriving the deterministic RNG.  This reduced-N
    form is intended only for computational benchmarking.
    """
    out={}
    for key,tw in target.windows.items():
        x=tw.points
        n=len(x)
        rng=_stable_rng(
            base_seed=base_seed,
            provider_world_id=provider_world_id,
            provider_id=provider_id,
            key=key,
            repetition=repetition,
        )
        perm=rng.permutation(n)
        if candidate_n is None or int(candidate_n)==n:
            y=np.column_stack((x[:,0],x[perm,1]))
        else:
            m=int(candidate_n)
            if m<1 or m>n:
                raise ValueError("candidate_n must be within 1..target N")
            start_idx=rng.choice(n,size=m,replace=False)
            end_idx=rng.choice(n,size=m,replace=False)
            y=np.column_stack((x[start_idx,0],x[end_idx,1]))
        out[key]=np.asarray(y,dtype=float)
    return out


def max_sorted_marginal_error(
    target:PreparedI2bTarget,
    candidate_windows:dict[WindowKey,np.ndarray],
)->float:
    """Max sorted marginal error; defined for equal-N diagnostic candidates."""
    worst=0.0
    for key,tw in target.windows.items():
        x=tw.points
        y=np.asarray(candidate_windows[key],dtype=float)
        if len(x)!=len(y):
            raise ValueError("marginal preservation check requires equal N")
        for col in (0,1):
            d=np.max(np.abs(np.sort(x[:,col])-np.sort(y[:,col])))
            worst=max(worst,float(d))
    return worst


def candidate_windows_from_compliance_samples(
    samples:pd.DataFrame,
    *,
    stride_s:int=10,
    start_phase_s:int=5,
    lags_s:tuple[int,...]=(20,30,40,50,75,100,150,200),
    horizon_end_s:int=240,
)->dict[WindowKey,np.ndarray]:
    """Build private candidate pair arrays from simulated c_j(A,H) samples.

    This function is for reconstruction-time scoring.  Candidate trajectory
    identity is used internally only to form same-trajectory pairs.
    """
    required={"region_id","H","trajectory_private","compliance_fraction"}
    missing=required.difference(samples.columns)
    if missing:
        raise RuntimeError(f"candidate compliance samples missing {sorted(missing)}")

    out:dict[WindowKey,np.ndarray]={}
    for region_id,g in samples.groupby("region_id",sort=True):
        pivot=g.pivot(
            index="trajectory_private",
            columns="H",
            values="compliance_fraction",
        ).sort_index().sort_index(axis=1)
        if pivot.shape[0]<1:
            raise RuntimeError("candidate compliance matrix has no trajectories")
        cols={int(round(float(x))) for x in pivot.columns}
        if cols!=set(range(5,241,5)):
            raise RuntimeError(f"candidate horizon support changed for {region_id}")
        for lag in lags_s:
            start=int(start_phase_s)
            while start+int(lag)<=int(horizon_end_s):
                end=start+int(lag)
                arr=np.column_stack((
                    pivot[float(start)].to_numpy(dtype=float),
                    pivot[float(end)].to_numpy(dtype=float),
                ))
                key=(str(region_id),float(lag),float(start),float(end))
                out[key]=arr
                start+=int(stride_s)
    if len(out)!=630:
        raise RuntimeError(f"expected 630 candidate I2b windows, found {len(out)}")
    return out
