from __future__ import annotations

import numpy as np

from phase5_reconstruction_v3_selection import (
    gibbs_weights,
    joint_product_support,
    rank_by_behavioral_centroid,
)


def test_centroid_ranking_uses_actual_candidate():
    public=np.array([0.9,0.6,0.3])
    ids=["a","b","c"]
    surfaces=np.array([
        [0.89,0.59,0.31],
        [0.80,0.50,0.20],
        [0.98,0.70,0.40],
    ])
    out=rank_by_behavioral_centroid(ids,surfaces,public)
    assert set(out["candidate_id"])==set(ids)
    assert out.iloc[0]["candidate_id"]=="a"


def test_gibbs_weights_normalize():
    public=np.array([0.9,0.6,0.3])
    ids=["a","b","c"]
    surfaces=np.array([
        [0.89,0.59,0.31],
        [0.80,0.50,0.20],
        [0.98,0.70,0.40],
    ])
    out=gibbs_weights(ids,surfaces,public)
    assert abs(float(out["weight"].sum())-1.0)<1e-12
    assert (out["weight"]>0).all()


def test_seven_per_provider_yields_343_joint_models():
    public=np.array([0.9,0.6,0.3])
    tables={}
    for p in ("ProviderA","ProviderB","ProviderC"):
        ids=[f"{p}_{i}" for i in range(7)]
        surfaces=np.array([
            np.clip(public+(i-3)*0.005,0,1) for i in range(7)
        ])
        tables[p]=gibbs_weights(ids,surfaces,public)
    joint=joint_product_support(tables)
    assert len(joint)==343
    assert joint.head(14)["joint_rank"].tolist()==list(range(1,15))
