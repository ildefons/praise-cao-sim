"""Shared deterministic selection helpers for Phase-5 V3 reconstruction."""
from __future__ import annotations

import itertools
import math
from typing import Iterable

import numpy as np
import pandas as pd


def rank_by_behavioral_centroid(
    candidate_ids: Iterable[str],
    surfaces: np.ndarray,
    public_surface: np.ndarray,
) -> pd.DataFrame:
    ids=[str(x) for x in candidate_ids]
    s=np.asarray(surfaces,dtype=float)
    target=np.asarray(public_surface,dtype=float)
    if s.ndim!=2:
        raise ValueError("surfaces must be 2-D [candidate, point]")
    if len(ids)!=s.shape[0]:
        raise ValueError("candidate_ids length mismatch")
    if s.shape[0]<1 or s.shape[1]<1:
        raise ValueError("empty surface bank")
    if target.shape!=(s.shape[1],):
        raise ValueError("public_surface shape mismatch")
    if not np.isfinite(s).all() or not np.isfinite(target).all():
        raise ValueError("non-finite surface value")
    centroid=s.mean(axis=0)
    rows=[]
    for i,cid in enumerate(ids):
        centroid_mse=float(np.mean((s[i]-centroid)**2))
        target_mse=float(np.mean((s[i]-target)**2))
        rows.append({
            "candidate_id":cid,
            "centroid_mse":centroid_mse,
            "rescore_mse":target_mse,
            "rescore_rmse":math.sqrt(target_mse),
        })
    out=pd.DataFrame(rows).sort_values(
        ["centroid_mse","rescore_rmse","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    out.insert(0,"behavioral_rank",np.arange(1,len(out)+1,dtype=int))
    return out


def _smooth_probability(p:np.ndarray,n:int)->np.ndarray:
    if n<1:
        raise ValueError("n must be >=1")
    p=np.asarray(p,dtype=float)
    if np.any((p<0)|(p>1)):
        raise ValueError("probabilities must lie in [0,1]")
    return (n*p+0.5)/(n+1.0)


def bernoulli_kl_energy(
    public_surface: np.ndarray,
    candidate_surface: np.ndarray,
    *,
    n_public:int,
    n_candidate:int,
)->float:
    p=_smooth_probability(np.asarray(public_surface,dtype=float),n_public)
    q=_smooth_probability(np.asarray(candidate_surface,dtype=float),n_candidate)
    if p.shape!=q.shape:
        raise ValueError("surface shape mismatch")
    term=p*np.log(p/q)+(1.0-p)*np.log((1.0-p)/(1.0-q))
    return float(np.mean(term))


def gibbs_weights(
    candidate_ids: Iterable[str],
    surfaces: np.ndarray,
    public_surface: np.ndarray,
    *,
    n_public:int=100,
    n_candidate:int=100,
    lam:float=30.0,
)->pd.DataFrame:
    ids=[str(x) for x in candidate_ids]
    s=np.asarray(surfaces,dtype=float)
    if len(ids)!=len(s):
        raise ValueError("candidate_ids length mismatch")
    energies=np.array([
        bernoulli_kl_energy(
            public_surface,s[i],n_public=n_public,n_candidate=n_candidate
        )
        for i in range(len(ids))
    ],dtype=float)
    logits=-float(lam)*energies
    logits-=float(np.max(logits))
    raw=np.exp(logits)
    weights=raw/raw.sum()
    out=pd.DataFrame({
        "candidate_id":ids,
        "kl_energy":energies,
        "weight":weights,
    }).sort_values(["weight","candidate_id"],ascending=[False,True],kind="mergesort")
    out=out.reset_index(drop=True)
    out.insert(0,"weight_rank",np.arange(1,len(out)+1,dtype=int))
    return out


def joint_product_support(provider_weight_tables:dict[str,pd.DataFrame])->pd.DataFrame:
    providers=tuple(sorted(provider_weight_tables))
    if len(providers)!=3:
        raise ValueError("exactly three providers are required")
    records=[]
    rows_by_provider=[]
    for provider in providers:
        t=provider_weight_tables[provider]
        if not {"candidate_id","weight"}.issubset(t.columns):
            raise ValueError(f"{provider}: missing candidate_id/weight")
        rows_by_provider.append([
            (str(r.candidate_id),float(r.weight))
            for r in t.itertuples(index=False)
        ])
    for combo in itertools.product(*rows_by_provider):
        ids=[x[0] for x in combo]
        weights=[x[1] for x in combo]
        rec={"joint_weight":float(np.prod(weights))}
        for provider,cid in zip(providers,ids):
            rec[f"{provider}_candidate_id"]=cid
        records.append(rec)
    out=pd.DataFrame(records)
    id_cols=[f"{p}_candidate_id" for p in providers]
    out=out.sort_values(
        ["joint_weight",*id_cols],
        ascending=[False,*([True]*len(id_cols))],
        kind="mergesort",
    ).reset_index(drop=True)
    out.insert(0,"joint_rank",np.arange(1,len(out)+1,dtype=int))
    return out
