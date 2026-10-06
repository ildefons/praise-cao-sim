"""Registered engineering smoke for Phase-5 V3 reconstruction selection.

This smoke exercises the new common seven-candidate representation and the
M1/M2/M3 aggregation rules.  It does not generate scientific evidence and
must never be consumed by scientific stages.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from phase5_graph_ast_v2 import assert_frozen_graph_compilation
from phase5_reconstruction_v3_selection import (
    gibbs_weights,
    joint_product_support,
    rank_by_behavioral_centroid,
)

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_provider_reconstruction_v3.json"
SEEDS=HERE/"config_phase5_seed_registry_v3.json"
BATTERY=HERE/"config_phase5_recoverability_battery_v2.json"
OUT=HERE/"smoke"/"v3_reconstruction"
MANIFEST=OUT/"v3_reconstruction_smoke_manifest.json"


def _load(path:Path):
    return json.loads(path.read_text())


def _check_seed_disjointness(seed_cfg:dict)->None:
    banks=[]
    for name,rec in seed_cfg["provider_reconstruction"].items():
        lo=int(rec["start"]); hi=int(rec["end_inclusive"])
        assert int(rec["n"])==hi-lo+1
        banks.append((name,set(range(lo,hi+1))))
    for i,(a,sa) in enumerate(banks):
        for b,sb in banks[i+1:]:
            assert sa.isdisjoint(sb),(a,b)


def main()->None:
    cfg=_load(CFG); seeds=_load(SEEDS); battery=_load(BATTERY)
    assert cfg["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3"
    assert seeds["status"]=="FROZEN_PHASE5_SEED_REGISTRY_V3"
    assert cfg["candidate_reconstruction"]["candidate_count_per_provider"]==7
    assert cfg["methods"]["M1"]["members_per_provider"]==1
    assert cfg["methods"]["M2"]["members_per_provider"]==3
    assert cfg["methods"]["M3"]["members_per_provider"]==7
    assert cfg["behavioral_centrality"]["hard_rmse_compatibility_gate"] is False
    assert seeds["engineering_smoke"]["scientific_evidence"] is False
    _check_seed_disjointness(seeds)

    graph_checks={}
    for rec in battery["graphs"]:
        gid=str(rec["id"])
        plan=assert_frozen_graph_compilation(gid,rec["ast"])
        graph_checks[gid]={
            "dependencies":{k:list(v) for k,v in plan.dependencies.items()},
            "pass":True,
        }

    x=np.linspace(0.05,0.95,37)
    public=np.clip(1.0-x**1.35,0.01,0.99)
    provider_tables={}
    central_tables={}
    for pidx,provider in enumerate(("ProviderA","ProviderB","ProviderC")):
        surfaces=[]
        ids=[]
        for j in range(7):
            ids.append(f"{provider}_C{j+1}")
            amp=(j-3)*0.012+(pidx-1)*0.002
            phase=(j+1)*(pidx+1)*0.37
            perturb=amp*np.sin(np.linspace(0.0,3.0*np.pi,37)+phase)
            surfaces.append(np.clip(public+perturb,0.0,1.0))
        surfaces=np.asarray(surfaces)
        ranked=rank_by_behavioral_centroid(ids,surfaces,public)
        assert len(ranked)==7
        assert ranked["behavioral_rank"].tolist()==list(range(1,8))
        central_tables[provider]=ranked
        weights=gibbs_weights(ids,surfaces,public,lam=float(cfg["methods"]["M3"]["gibbs_lambda"]))
        assert len(weights)==7
        assert abs(float(weights["weight"].sum())-1.0)<1e-12
        provider_tables[provider]=weights

    m1={p:str(t.iloc[0]["candidate_id"]) for p,t in central_tables.items()}
    m2={p:t.head(3)["candidate_id"].astype(str).tolist() for p,t in central_tables.items()}
    assert all(m1[p] in m2[p] for p in m1)
    m2_joint_count=1
    for p in m2:
        m2_joint_count*=len(m2[p])
    assert m2_joint_count==27

    joint=joint_product_support(provider_tables)
    assert len(joint)==343
    assert np.all(np.diff(joint["joint_weight"].to_numpy(float))<=1e-15)
    top1=joint.head(1)["joint_rank"].tolist()
    top3=joint.head(3)["joint_rank"].tolist()
    top14=joint.head(14)["joint_rank"].tolist()
    assert top1==[1]
    assert top3==[1,2,3]
    assert top14==list(range(1,15))

    OUT.mkdir(parents=True,exist_ok=True)
    payload={
        "status":"PHASE5_V3_RECONSTRUCTION_SMOKE_PASS",
        "scientific_evidence":False,
        "registered_checks":{
            "fresh_reconstruction_seed_banks_disjoint":True,
            "all_four_graph_asts_compile":True,
            "seven_candidate_behavioral_ranking":True,
            "m1_rank1_selection":True,
            "m2_rank1_to_rank3_selection":True,
            "m2_joint_count_27":True,
            "m3_seven_provider_weights_normalize":True,
            "m3_joint_count_343":True,
            "m3_nested_top1_top3_top14":True,
            "hard_rmse_gate_absent":True
        },
        "graph_checks":graph_checks,
        "m1_smoke_selection":m1,
        "m2_smoke_selection":m2,
        "m3_joint_support_size":int(len(joint)),
        "note":"Engineering-only synthetic surfaces. No scientific provider reconstruction, graph prediction, or WB evidence."
    }
    MANIFEST.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print("PHASE5_V3_RECONSTRUCTION_SMOKE_PASS")
    for k,v in payload["registered_checks"].items():
        print(k,v)
    print("scientific_evidence",payload["scientific_evidence"])
    print("output",MANIFEST)


if __name__=="__main__":
    main()
