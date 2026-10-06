"""Materialize the frozen Phase-5 V3b provider selection from V3 evidence.

No simulation occurs here.  The script reads only already-frozen V3 local
reconstruction artifacts, ranks candidates by common-N100 rescore RMSE, derives
M1 rank 1 and M2 ranks 1..3, and carries forward the unchanged V3 M3 support.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase5_runtime_v2 import (
    canonical_provider_world_ids,
    git_head,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from phase5_reconstruction_v3_selection import joint_product_support

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_provider_reconstruction_v3b.json"
V3_ROOT=HERE/"results"/"03_reconstruction_v3"
OUT_ROOT=HERE/"results"/"03_reconstruction_v3b"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3B"
EXPECTED_V3_PROVIDER="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION"
EXPECTED_V3_WORLD="FROZEN_PHASE5_V3_WORLD_RECONSTRUCTION"


def _manifest(status:str,inputs:dict,outputs:dict)->dict:
    contracts=load_phase5_contracts(HERE)
    return {
        "status":status,
        "stage_id":"RECONSTRUCTION_V3B_SELECTION",
        "protocol_version":"PHASE5_PROVIDER_RECONSTRUCTION_V3B_2026-10-06",
        "scientific_evidence":True,
        "battery_config_sha256":contracts.hashes["battery"],
        "v2_execution_contract_sha256":contracts.hashes["execution"],
        "v2_analysis_contract_sha256":contracts.hashes["analysis"],
        "v3b_selection_contract_sha256":sha256_file(CFG),
        "code_commit":git_head(),
        "inputs":inputs,
        "outputs":outputs,
        "output_hashes_sha256":{
            k:sha256_file(Path(v)) for k,v in outputs.items() if Path(v).is_file()
        },
        "started_utc":utc_now_iso(),
        "completed_utc":utc_now_iso(),
    }


def _rank_provider(world:str,provider:str)->dict:
    src=V3_ROOT/world/provider
    out=OUT_ROOT/world/provider
    out.mkdir(parents=True,exist_ok=True)

    freeze_path=src/"provider_freeze_manifest.json"
    if not freeze_path.is_file():
        raise FileNotFoundError(freeze_path)
    freeze=read_json(freeze_path)
    if freeze.get("status")!=EXPECTED_V3_PROVIDER:
        raise RuntimeError(f"{world}/{provider}: V3 provider reconstruction not frozen")

    candidates_path=src/"v3_candidates_rescore.csv"
    replay_path=src/"v3_candidates_replay.csv"
    m3_path=src/"m3_provider_models.csv"
    for p in (candidates_path,replay_path,m3_path):
        if not p.is_file():
            raise FileNotFoundError(p)

    candidates=pd.read_csv(candidates_path)
    replay=pd.read_csv(replay_path)
    m3=pd.read_csv(m3_path)

    if len(candidates)!=7 or candidates["candidate_id"].nunique()!=7:
        raise RuntimeError(f"{world}/{provider}: expected seven unique V3 candidates")
    if len(replay)!=7 or set(replay["candidate_id"].astype(str))!=set(candidates["candidate_id"].astype(str)):
        raise RuntimeError(f"{world}/{provider}: replay candidate set mismatch")
    if len(m3)!=7 or set(m3["candidate_id"].astype(str))!=set(candidates["candidate_id"].astype(str)):
        raise RuntimeError(f"{world}/{provider}: M3 candidate set mismatch")
    if candidates["rescore_rmse"].isna().any():
        raise RuntimeError(f"{world}/{provider}: missing rescore RMSE")

    ranked=candidates.sort_values(
        ["rescore_rmse","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    ranked.insert(0,"v3b_quality_rank",np.arange(1,8,dtype=int))
    ranked_path=out/"v3b_candidate_quality_ranking.csv"
    ranked.to_csv(ranked_path,index=False)

    m1=ranked.head(1).copy()
    m1.insert(0,"method_id","M1")
    m1_path=out/"m1_provider_model.csv"
    m1.to_csv(m1_path,index=False)

    m2=ranked.head(3).copy()
    m2.insert(0,"method_id","M2")
    m2["provider_weight"]=1.0/3.0
    m2_path=out/"m2_provider_models.csv"
    m2.to_csv(m2_path,index=False)

    # M3 is intentionally unchanged, but copy its frozen provider table into
    # the V3b namespace and verify normalization.
    m3copy=m3.copy()
    if abs(float(m3copy["weight"].sum())-1.0)>1e-12:
        raise RuntimeError(f"{world}/{provider}: V3 M3 weights do not normalize")
    m3_out=out/"m3_provider_models.csv"
    m3copy.to_csv(m3_out,index=False)

    diagnostics=ranked[[
        "candidate_id","v3b_quality_rank","rescore_rmse","rescore_mse",
        "behavioral_rank","centroid_mse","weight_rank","kl_energy","weight"
    ]].merge(
        replay[["candidate_id","replay_rmse","replay_mse"]],
        on="candidate_id",how="left",validate="one_to_one",
    )
    diagnostics_path=out/"v3b_selection_diagnostics.csv"
    diagnostics.to_csv(diagnostics_path,index=False)

    outputs={
        "quality_ranking":str(ranked_path),
        "m1_provider_model":str(m1_path),
        "m2_provider_models":str(m2_path),
        "m3_provider_models":str(m3_out),
        "selection_diagnostics":str(diagnostics_path),
    }
    manifest=_manifest(
        "FROZEN_PHASE5_V3B_PROVIDER_SELECTION",
        inputs={
            "provider_world_id":world,
            "provider_id":provider,
            "source_v3_provider_manifest_sha256":sha256_file(freeze_path),
            "source_v3_candidates_rescore_sha256":sha256_file(candidates_path),
            "source_v3_replay_sha256":sha256_file(replay_path),
            "source_v3_m3_provider_models_sha256":sha256_file(m3_path),
            "selection_metric":"rescore_rmse",
            "selection_bank":"V3 common N=100 rescore",
            "replay_used_for_selection":False,
            "behavioral_centroid_used_for_selection":False,
            "graph_prediction_used":False,
            "graph_WB_used":False,
            "final_WB_used":False,
        },
        outputs=outputs,
    )
    manifest["m1_candidate_id"]=str(m1.iloc[0]["candidate_id"])
    manifest["m2_candidate_ids"]=m2["candidate_id"].astype(str).tolist()
    manifest["m3_candidate_ids"]=m3copy["candidate_id"].astype(str).tolist()
    write_json(out/"provider_selection_freeze_manifest.json",manifest)

    return {
        "provider_world_id":world,
        "provider_id":provider,
        "m1_candidate_id":manifest["m1_candidate_id"],
        "m1_rmse":float(m1.iloc[0]["rescore_rmse"]),
        "m2_candidate_ids":";".join(manifest["m2_candidate_ids"]),
        "m2_rmse":";".join(f"{x:.9g}" for x in m2["rescore_rmse"].astype(float)),
    }


def _freeze_world(world:str)->dict:
    src_world_manifest=V3_ROOT/world/"world_reconstruction_freeze_manifest.json"
    if not src_world_manifest.is_file():
        raise FileNotFoundError(src_world_manifest)
    src_world=read_json(src_world_manifest)
    if src_world.get("status")!=EXPECTED_V3_WORLD:
        raise RuntimeError(f"{world}: V3 world reconstruction not frozen")

    out=OUT_ROOT/world
    provider_rows=[]
    m2_tables={}
    m3_tables={}
    for provider in PROVIDERS:
        pdir=out/provider
        manifest_path=pdir/"provider_selection_freeze_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        mf=read_json(manifest_path)
        if mf.get("status")!="FROZEN_PHASE5_V3B_PROVIDER_SELECTION":
            raise RuntimeError(f"{world}/{provider}: V3b provider selection not frozen")
        m1=pd.read_csv(pdir/"m1_provider_model.csv")
        m2=pd.read_csv(pdir/"m2_provider_models.csv")
        m3=pd.read_csv(pdir/"m3_provider_models.csv")
        if len(m1)!=1 or len(m2)!=3 or len(m3)!=7:
            raise RuntimeError(f"{world}/{provider}: provider cardinality mismatch")
        if str(m1.iloc[0]["candidate_id"])!=str(m2.iloc[0]["candidate_id"]):
            raise RuntimeError(f"{world}/{provider}: M1 is not rank-1 member of M2")
        provider_rows.append({
            "provider_id":provider,
            "m1_candidate_id":str(m1.iloc[0]["candidate_id"]),
            "m1_rescore_rmse":float(m1.iloc[0]["rescore_rmse"]),
            "m2_candidate_ids":";".join(m2["candidate_id"].astype(str)),
            "provider_manifest_sha256":sha256_file(manifest_path),
        })
        m2_tables[provider]=m2
        m3_tables[provider]=m3[["candidate_id","weight"]].copy()

    provider_table=pd.DataFrame(provider_rows)
    provider_table_path=out/"v3b_provider_selection_status.csv"
    provider_table.to_csv(provider_table_path,index=False)

    rows=[]
    for a in m2_tables["ProviderA"].itertuples(index=False):
        for b in m2_tables["ProviderB"].itertuples(index=False):
            for c in m2_tables["ProviderC"].itertuples(index=False):
                rows.append({
                    "ProviderA_candidate_id":str(a.candidate_id),
                    "ProviderB_candidate_id":str(b.candidate_id),
                    "ProviderC_candidate_id":str(c.candidate_id),
                    "joint_weight":1.0/27.0,
                })
    m2_joint=pd.DataFrame(rows)
    if len(m2_joint)!=27:
        raise RuntimeError(f"{world}: V3b M2 joint support is not 27")
    m2_joint.insert(0,"joint_rank",np.arange(1,28,dtype=int))
    m2_joint_path=out/"m2_joint_support_27.csv"
    m2_joint.to_csv(m2_joint_path,index=False)

    m3_joint=joint_product_support(m3_tables)
    if len(m3_joint)!=343:
        raise RuntimeError(f"{world}: V3b M3 joint support is not 343")
    m3_joint_path=out/"m3_joint_support_343.csv"
    m3_top14_path=out/"m3_joint_support_top14.csv"
    m3_joint.to_csv(m3_joint_path,index=False)
    m3_joint.head(14).to_csv(m3_top14_path,index=False)

    outputs={
        "provider_selection_status":str(provider_table_path),
        "m2_joint_support_27":str(m2_joint_path),
        "m3_joint_support_343":str(m3_joint_path),
        "m3_joint_support_top14":str(m3_top14_path),
    }
    mf=_manifest(
        "FROZEN_PHASE5_V3B_WORLD_SELECTION",
        inputs={
            "provider_world_id":world,
            "source_v3_world_manifest_sha256":sha256_file(src_world_manifest),
            "graph_prediction_used":False,
            "final_WB_used":False,
        },
        outputs=outputs,
    )
    mf["M1_joint_models"]=1
    mf["M2_joint_models"]=27
    mf["M3_joint_models"]=343
    mf["M3_top14_models"]=14
    write_json(out/"world_selection_freeze_manifest.json",mf)
    return {
        "world":world,"M1_joint":1,"M2_joint":27,"M3_joint":343,"M3_top14":14
    }


def main()->None:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected V3b selection contract status")

    contracts=load_phase5_contracts(HERE)
    rows=[]
    for world in canonical_provider_world_ids(contracts):
        for provider in PROVIDERS:
            rows.append(_rank_provider(world,provider))

    world_rows=[_freeze_world(w) for w in canonical_provider_world_ids(contracts)]

    table=pd.DataFrame(rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    table_path=OUT_ROOT/"v3b_provider_selection_summary.csv"
    table.to_csv(table_path,index=False)

    worlds=pd.DataFrame(world_rows).sort_values("world").reset_index(drop=True)
    worlds_path=OUT_ROOT/"v3b_world_selection_summary.csv"
    worlds.to_csv(worlds_path,index=False)

    mf=_manifest(
        "FROZEN_PHASE5_V3B_RECONSTRUCTION_SELECTION_BATTERY",
        inputs={
            "all_12_provider_selections_frozen":True,
            "new_provider_simulation":False,
            "selection_metric":"common-N100 rescore RMSE",
            "graph_prediction_used":False,
            "graph_WB_used":False,
            "final_WB_used":False,
        },
        outputs={
            "provider_selection_summary":str(table_path),
            "world_selection_summary":str(worlds_path),
        },
    )
    path=OUT_ROOT/"phase5_v3b_selection_freeze_manifest.json"
    write_json(path,mf)

    print("PHASE5_V3B_SELECTION_FREEZE_PASS")
    print(table.to_string(index=False))
    print("\\nPHASE5_V3B_WORLD_SELECTION_SUMMARY")
    print(worlds.to_string(index=False))
    print("battery_freeze",path)


if __name__=="__main__":
    main()
