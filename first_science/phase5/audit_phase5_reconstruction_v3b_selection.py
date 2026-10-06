"""Read-only mechanical audit of the frozen Phase-5 V3b reconstruction selection.

Checks only already-materialized V3/V3b artifacts.  It runs no simulation and
does not read graph prediction or final-WB evidence.
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

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_provider_reconstruction_v3b.json"
V3_ROOT=HERE/"results"/"03_reconstruction_v3"
V3B_ROOT=HERE/"results"/"03_reconstruction_v3b"
OUT=V3B_ROOT/"phase5_v3b_selection_audit_manifest.json"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3B"
TOL=1e-12


def _assert_same_csv(a:Path,b:Path,label:str)->None:
    if not a.is_file() or not b.is_file():
        raise FileNotFoundError(f"{label}: missing file")
    da=pd.read_csv(a)
    db=pd.read_csv(b)
    if list(da.columns)!=list(db.columns):
        raise RuntimeError(f"{label}: columns differ")
    if da.shape!=db.shape:
        raise RuntimeError(f"{label}: shape differs {da.shape} vs {db.shape}")
    # CSV re-materialization can alter formatting, so compare parsed values.
    for col in da.columns:
        xa=da[col]
        xb=db[col]
        if pd.api.types.is_numeric_dtype(xa) and pd.api.types.is_numeric_dtype(xb):
            if not np.allclose(
                xa.to_numpy(float),xb.to_numpy(float),
                rtol=0.0,atol=1e-15,equal_nan=True,
            ):
                raise RuntimeError(f"{label}: numeric column {col} differs")
        else:
            if xa.fillna("<NA>").astype(str).tolist()!=xb.fillna("<NA>").astype(str).tolist():
                raise RuntimeError(f"{label}: column {col} differs")


def _audit_provider(world:str,provider:str)->dict:
    v3=V3_ROOT/world/provider
    v3b=V3B_ROOT/world/provider

    src_candidates=v3/"v3_candidates_rescore.csv"
    src_replay=v3/"v3_candidates_replay.csv"
    src_m3=v3/"m3_provider_models.csv"
    b_rank=v3b/"v3b_candidate_quality_ranking.csv"
    b_m1=v3b/"m1_provider_model.csv"
    b_m2=v3b/"m2_provider_models.csv"
    b_m3=v3b/"m3_provider_models.csv"
    b_diag=v3b/"v3b_selection_diagnostics.csv"
    b_manifest=v3b/"provider_selection_freeze_manifest.json"

    for p in (src_candidates,src_replay,src_m3,b_rank,b_m1,b_m2,b_m3,b_diag,b_manifest):
        if not p.is_file():
            raise FileNotFoundError(p)

    candidates=pd.read_csv(src_candidates)
    replay=pd.read_csv(src_replay)
    ranked=pd.read_csv(b_rank)
    m1=pd.read_csv(b_m1)
    m2=pd.read_csv(b_m2)
    m3=pd.read_csv(b_m3)
    diag=pd.read_csv(b_diag)
    mf=read_json(b_manifest)

    if mf.get("status")!="FROZEN_PHASE5_V3B_PROVIDER_SELECTION":
        raise RuntimeError(f"{world}/{provider}: provider V3b freeze status mismatch")
    if len(candidates)!=7 or candidates["candidate_id"].nunique()!=7:
        raise RuntimeError(f"{world}/{provider}: source candidate cardinality != 7")
    expected=candidates.sort_values(
        ["rescore_rmse","candidate_id"],kind="mergesort"
    ).reset_index(drop=True)
    expected_ids=expected["candidate_id"].astype(str).tolist()

    if ranked["candidate_id"].astype(str).tolist()!=expected_ids:
        raise RuntimeError(f"{world}/{provider}: V3b quality ranking is not ascending rescore RMSE")
    if ranked["v3b_quality_rank"].astype(int).tolist()!=list(range(1,8)):
        raise RuntimeError(f"{world}/{provider}: V3b quality ranks are not 1..7")
    if not np.all(np.diff(ranked["rescore_rmse"].to_numpy(float))>=-TOL):
        raise RuntimeError(f"{world}/{provider}: V3b RMSE ranking not monotone")

    if len(m1)!=1 or str(m1.iloc[0]["candidate_id"])!=expected_ids[0]:
        raise RuntimeError(f"{world}/{provider}: M1 is not RMSE rank 1")
    if len(m2)!=3 or m2["candidate_id"].astype(str).tolist()!=expected_ids[:3]:
        raise RuntimeError(f"{world}/{provider}: M2 is not RMSE ranks 1..3")
    if str(m1.iloc[0]["candidate_id"]) not in set(m2["candidate_id"].astype(str)):
        raise RuntimeError(f"{world}/{provider}: M1 is not contained in M2")
    if not np.allclose(m2["provider_weight"].to_numpy(float),1.0/3.0,rtol=0.0,atol=TOL):
        raise RuntimeError(f"{world}/{provider}: M2 provider weights are not 1/3")

    _assert_same_csv(src_m3,b_m3,f"{world}/{provider}: V3 M3 carry-forward")
    if len(m3)!=7 or abs(float(m3["weight"].sum())-1.0)>TOL:
        raise RuntimeError(f"{world}/{provider}: M3 provider weights do not normalize")

    # Replay and centroid information must not alter the frozen quality ordering.
    expected_diag=ranked[[
        "candidate_id","v3b_quality_rank","rescore_rmse","rescore_mse",
        "behavioral_rank","centroid_mse","weight_rank","kl_energy","weight"
    ]].merge(
        replay[["candidate_id","replay_rmse","replay_mse"]],
        on="candidate_id",how="left",validate="one_to_one",
    )
    if diag["candidate_id"].astype(str).tolist()!=expected_diag["candidate_id"].astype(str).tolist():
        raise RuntimeError(f"{world}/{provider}: diagnostics changed selection ordering")

    if bool(mf["inputs"].get("replay_used_for_selection")):
        raise RuntimeError(f"{world}/{provider}: replay marked as selection input")
    if bool(mf["inputs"].get("behavioral_centroid_used_for_selection")):
        raise RuntimeError(f"{world}/{provider}: centroid marked as selection input")
    for key in ("graph_prediction_used","graph_WB_used","final_WB_used"):
        if bool(mf["inputs"].get(key)):
            raise RuntimeError(f"{world}/{provider}: firewall violation {key}")

    return {
        "provider_world_id":world,
        "provider_id":provider,
        "m1_candidate_id":expected_ids[0],
        "m1_rescore_rmse":float(expected.iloc[0]["rescore_rmse"]),
        "m2_candidate_ids":";".join(expected_ids[:3]),
        "m2_rmse_max":float(expected.iloc[2]["rescore_rmse"]),
        "m3_weight_sum":float(m3["weight"].sum()),
        "provider_selection_manifest_sha256":sha256_file(b_manifest),
    }


def _audit_world(world:str)->dict:
    wroot=V3B_ROOT/world
    world_manifest=wroot/"world_selection_freeze_manifest.json"
    m2_joint=wroot/"m2_joint_support_27.csv"
    m3_joint=wroot/"m3_joint_support_343.csv"
    m3_top14=wroot/"m3_joint_support_top14.csv"
    for p in (world_manifest,m2_joint,m3_joint,m3_top14):
        if not p.is_file():
            raise FileNotFoundError(p)

    wm=read_json(world_manifest)
    if wm.get("status")!="FROZEN_PHASE5_V3B_WORLD_SELECTION":
        raise RuntimeError(f"{world}: world V3b freeze status mismatch")

    m2=pd.read_csv(m2_joint)
    if len(m2)!=27:
        raise RuntimeError(f"{world}: M2 joint support != 27")
    if not np.allclose(m2["joint_weight"].to_numpy(float),1.0/27.0,rtol=0.0,atol=TOL):
        raise RuntimeError(f"{world}: M2 joint weights are not 1/27")
    if abs(float(m2["joint_weight"].sum())-1.0)>TOL:
        raise RuntimeError(f"{world}: M2 joint weights do not sum to 1")

    m3=pd.read_csv(m3_joint)
    top14=pd.read_csv(m3_top14)
    if len(m3)!=343:
        raise RuntimeError(f"{world}: M3 joint support != 343")
    if len(top14)!=14:
        raise RuntimeError(f"{world}: M3 Top14 support != 14")
    if abs(float(m3["joint_weight"].sum())-1.0)>1e-10:
        raise RuntimeError(f"{world}: M3 joint weights do not sum to 1")
    if m3["joint_rank"].astype(int).tolist()!=list(range(1,344)):
        raise RuntimeError(f"{world}: M3 joint ranks are not 1..343")
    if top14["joint_rank"].astype(int).tolist()!=list(range(1,15)):
        raise RuntimeError(f"{world}: M3 Top14 is not joint ranks 1..14")
    if not np.all(np.diff(m3["joint_weight"].to_numpy(float))<=TOL):
        raise RuntimeError(f"{world}: M3 joint weights are not descending")

    # Top14 must be exactly the prefix of the full frozen 343 support.
    cols=list(m3.columns)
    prefix=m3.head(14).reset_index(drop=True)
    t=top14[cols].reset_index(drop=True)
    for col in cols:
        if pd.api.types.is_numeric_dtype(prefix[col]) and pd.api.types.is_numeric_dtype(t[col]):
            if not np.allclose(prefix[col].to_numpy(float),t[col].to_numpy(float),rtol=0.0,atol=1e-15):
                raise RuntimeError(f"{world}: M3 Top14 numeric column {col} differs from full-support prefix")
        else:
            if prefix[col].astype(str).tolist()!=t[col].astype(str).tolist():
                raise RuntimeError(f"{world}: M3 Top14 column {col} differs from full-support prefix")

    return {
        "provider_world_id":world,
        "M1_joint_models":1,
        "M2_joint_models":27,
        "M3_joint_models":343,
        "M3_top14_models":14,
        "M2_joint_weight_sum":float(m2["joint_weight"].sum()),
        "M3_joint_weight_sum":float(m3["joint_weight"].sum()),
        "world_selection_manifest_sha256":sha256_file(world_manifest),
    }


def main()->None:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected V3b selection contract status")

    contracts=load_phase5_contracts(HERE)
    provider_rows=[]
    for world in canonical_provider_world_ids(contracts):
        for provider in PROVIDERS:
            provider_rows.append(_audit_provider(world,provider))
    world_rows=[_audit_world(w) for w in canonical_provider_world_ids(contracts)]

    provider_table=pd.DataFrame(provider_rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    world_table=pd.DataFrame(world_rows).sort_values(
        "provider_world_id",kind="mergesort"
    ).reset_index(drop=True)

    provider_path=V3B_ROOT/"phase5_v3b_selection_audit_providers.csv"
    world_path=V3B_ROOT/"phase5_v3b_selection_audit_worlds.csv"
    provider_table.to_csv(provider_path,index=False)
    world_table.to_csv(world_path,index=False)

    battery_freeze=V3B_ROOT/"phase5_v3b_selection_freeze_manifest.json"
    if not battery_freeze.is_file():
        raise FileNotFoundError(battery_freeze)
    bf=read_json(battery_freeze)
    if bf.get("status")!="FROZEN_PHASE5_V3B_RECONSTRUCTION_SELECTION_BATTERY":
        raise RuntimeError("V3b battery selection freeze status mismatch")
    if bool(bf["inputs"].get("graph_prediction_used")):
        raise RuntimeError("V3b battery freeze says graph prediction was used")
    if bool(bf["inputs"].get("graph_WB_used")) or bool(bf["inputs"].get("final_WB_used")):
        raise RuntimeError("V3b battery freeze says WB evidence was used")

    manifest={
        "status":"FROZEN_PHASE5_V3B_SELECTION_MECHANICAL_AUDIT_PASS",
        "stage_id":"RECONSTRUCTION_V3B_SELECTION_AUDIT",
        "protocol_version":"PHASE5_PROVIDER_RECONSTRUCTION_V3B_2026-10-06",
        "scientific_evidence":False,
        "audit_role":"mechanical consistency/provenance audit only",
        "v3b_selection_contract_sha256":sha256_file(CFG),
        "v3b_battery_freeze_sha256":sha256_file(battery_freeze),
        "code_commit":git_head(),
        "checks":{
            "all_12_provider_candidate_banks_have_7_unique_candidates":True,
            "m1_is_common_N100_RMSE_rank1":True,
            "m2_is_common_N100_RMSE_ranks1_to_3":True,
            "m1_is_member_of_m2":True,
            "m2_provider_weights_are_equal_thirds":True,
            "m2_joint_support_is_27":True,
            "m2_joint_weights_are_1_over_27":True,
            "m3_provider_tables_unchanged_from_v3":True,
            "m3_provider_weights_normalize":True,
            "m3_joint_support_is_343":True,
            "m3_joint_weights_normalize":True,
            "m3_top14_is_exact_prefix_of_343_support":True,
            "replay_not_used_for_selection":True,
            "behavioral_centroid_not_used_for_selection":True,
            "graph_prediction_not_used":True,
            "graph_WB_not_used":True,
            "final_WB_not_used":True
        },
        "outputs":{
            "provider_audit":str(provider_path),
            "world_audit":str(world_path),
        },
        "output_hashes_sha256":{
            "provider_audit":sha256_file(provider_path),
            "world_audit":sha256_file(world_path),
        },
        "completed_utc":utc_now_iso(),
    }
    write_json(OUT,manifest)

    print("PHASE5_V3B_SELECTION_MECHANICAL_AUDIT_PASS")
    for key,value in manifest["checks"].items():
        print(key,value)
    print("\\nPROVIDER AUDIT")
    print(provider_table[[
        "provider_world_id","provider_id","m1_candidate_id",
        "m1_rescore_rmse","m2_candidate_ids","m2_rmse_max","m3_weight_sum"
    ]].to_string(index=False))
    print("\\nWORLD AUDIT")
    print(world_table.to_string(index=False))
    print("manifest",OUT)


if __name__=="__main__":
    main()
