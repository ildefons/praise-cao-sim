#!/usr/bin/env python3
"""B0001 isolated V3b selection-and-freeze, simulation-free.

Modes
-----
--check: read-only deep audit of frozen B0001 V3 inputs and historic V3b
         selection/scientific code.  Does not create output files.
--run: repeat the input audit, apply ORIGINAL V3b _rank_provider/_freeze_world
       to only B0001 P1/P3/P4, mechanically verify all nine selections and
       three supports, and freeze B0001-specific selection + audit manifests.

Absolutely no provider or graph simulation.  V3 source files are read-only.
Outputs are separate from V3 and the Phase-5 historical result directories.
No graph-prediction execution is authorized.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import preflight_b0001_v3_domains_v1 as preflight

REPO=preflight.REPO
PHASE5=preflight.P5
ROLES=preflight.ROLES
PROVIDERS=preflight.PROVIDERS
V3_CONTRACT=PHASE5/"config_phase5_provider_reconstruction_v3.json"
V3B_CONTRACT=PHASE5/"config_phase5_provider_reconstruction_v3b.json"
SCIENTIFIC_SOURCES={
    "freeze_phase5_reconstruction_v3b_selection.py",
    "audit_phase5_reconstruction_v3b_selection.py",
    "phase5_reconstruction_v3_selection.py",
    "config_phase5_provider_reconstruction_v3b.json",
}
PROVIDER_OUTPUT_NAMES=(
    "v3_candidates_rescore.csv","v3_candidates_replay.csv",
    "v3_common_rescore_surfaces.csv",
    "m1_provider_model.csv","m2_provider_models.csv",
    "m3_provider_models.csv",
)
WORLD_OUTPUT_NAMES=(
    "m2_joint_support_27.csv","m3_joint_support_343.csv",
    "m3_joint_support_top14.csv",
)
SOURCE_STATUS="B0001_V3_CANDIDATE_GENERATION_FROZEN_V3B_SELECTION_PENDING"
OUT_STATUS="B0001_V3B_SELECTION_AND_AUDIT_FROZEN_GRAPH_BLOCKED"
TOL=1e-12


def require(condition,detail):
    if not condition:
        raise RuntimeError(detail)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def save(path,payload):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")


def unchanged_csv(a,b,label):
    da=pd.read_csv(a)
    db=pd.read_csv(b)
    require(list(da.columns)==list(db.columns) and da.shape==db.shape,
            f"{label}: CSV schema/size changed")
    for key in da.columns:
        if pd.api.types.is_numeric_dtype(da[key]) and pd.api.types.is_numeric_dtype(db[key]):
            require(np.allclose(da[key].to_numpy(float),db[key].to_numpy(float),
                                rtol=0,atol=1e-15,equal_nan=True),
                    f"{label}: numerical column {key} changed")
        else:
            require(da[key].fillna("<NA>").astype(str).tolist()==
                    db[key].fillna("<NA>").astype(str).tolist(),
                    f"{label}: text column {key} changed")


def source_inputs(a):
    """Deep read-only input audit before ANY V3b output is created."""
    v3=a.v3
    workspace=a.workspace
    guardfile=workspace/"b0001_v3_isolation_check.json"
    frozenfile=workspace/"b0001_v3_candidate_generation_freeze.json"
    require(v3==(workspace/"v3_results").resolve(),
            "V3 root must be the isolated B0001 workspace's v3_results")
    for path in (guardfile,frozenfile):
        require(path.is_file(),"Missing B0001 reconstruction gate: "+str(path))
    gate=load(guardfile)
    frozen=load(frozenfile)
    require(gate["status"]=="B0001_V3_ISOLATION_CHECK_PASS_NO_SIMULATIONS",
            "Source V3 isolation status invalid")
    require(frozen["status"]==SOURCE_STATUS and
            frozen["n_provider_banks"]==9 and
            frozen["n_candidate_fits"]==63 and
            frozen["v3b_m1_m2_selection_complete"] is False and
            frozen["graph_prediction_authorized"] is False,
            "B0001 V3 candidate freeze invalid")
    require(frozen["isolation_gate_sha256"]==sha(guardfile),
            "B0001 V3 candidate freeze isolation hash mismatch")
    require(frozen["domain_registry_sha256"]==gate["frozen_domain_sha256"],
            "Frozen V3 domain provenance disagreement")
    require(frozen["original_v3_config_sha256"]==gate["config_v3_sha256"]==
            sha(V3_CONTRACT),
            "V3 scientific reconstruction contract changed")
    require(gate["config_v3b_sha256"]==sha(V3B_CONTRACT),
            "V3b selection contract differs from isolated B0001 preflight")
    require(gate["total_fits"]==63 and gate["seed_bank_collisions"]==0,
            "V3 seed or candidate count invalid")
    require(gate["world_roles"]==list(ROLES) and gate["providers_per_world"]==3,
            "B0001 source roles/providers changed")
    contract=load(V3B_CONTRACT)
    require(contract["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3B",
            "Original V3b contract status unexpected")
    basis=contract["selection_basis"]
    require(basis["ranking_metric"]=="rescore_rmse" and
            basis["replay_may_select_or_reorder"] is False and
            basis["behavioral_centroid_may_select_or_reorder"] is False,
            "V3b selection must use rescore RMSE alone")
    require(contract["provenance"]["no_new_provider_simulation"] is True and
            contract["provenance"]["v3_outputs_are_not_overwritten"] is True,
            "V3b contract no-simulation/no-overwrite rule changed")
    require(contract["methods"]["M1"]["members_per_provider"]==1 and
            contract["methods"]["M2"]["members_per_provider"]==3 and
            contract["methods"]["M3"]["joint_support_size"]==343,
            "V3b original method cardinalities changed")

    source_sha={}
    for name in SCIENTIFIC_SOURCES:
        path=PHASE5/name
        require(path.is_file(),"Original V3b source missing: "+name)
        source_sha[name]=sha(path)

    sys.path.insert(0,str(PHASE5))
    from phase5_reconstruction_v3_selection import joint_product_support

    input_sha={}
    v3_world_sha={}
    summary=[]
    for role in ROLES:
        world=v3/role
        worldfile=world/"world_reconstruction_freeze_manifest.json"
        require(worldfile.is_file(),"Missing frozen V3 world: "+role)
        wf=load(worldfile)
        require(wf["status"]=="FROZEN_PHASE5_V3_WORLD_RECONSTRUCTION" and
                wf["inputs"]["provider_world_id"]==role and
                wf["inputs"]["graph_prediction_used"] is False and
                wf["inputs"]["final_WB_used"] is False,
                "Source V3 world manifest invalid: "+role)
        require(sha(worldfile)==frozen["world_sha256"][role],
                "B0001 source V3 world manifest hash mismatch: "+role)
        v3_world_sha[role]=sha(worldfile)
        tables={}
        m3_tables={}
        for provider in PROVIDERS:
            label=f"{role}/{provider}"
            root=world/provider
            fp=root/"provider_freeze_manifest.json"
            require(fp.is_file(),"Missing V3 provider manifest: "+label)
            pm=load(fp)
            require(pm["status"]=="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION" and
                    pm["inputs"]["provider_world_id"]==role and
                    pm["inputs"]["provider_id"]==provider and
                    pm["n_candidates"]==7,
                    "Source V3 provider metadata invalid: "+label)
            require(wf["provider_manifest_sha256"][provider]==sha(fp),
                    "Source world/provider manifest hash differs: "+label)
            for flag in ("hidden_provider_parameters_used","step0_WB_values_used",
                         "graph_prediction_used","graph_WB_used","final_WB_used",
                         "v2_reconstruction_evidence_used"):
                require(pm["inputs"].get(flag) is False,
                        "V3 provider source firewall violation "+label+"/"+flag)
            require(pm["v3_reconstruction_contract_sha256"]==sha(V3_CONTRACT),
                    "Provider used different V3 contract: "+label)
            expected_seeds=load(workspace/"frozen_contracts"/
                                f"config_b0001_v3_seed_registry_{role}.json")
            require(pm["v3_seed_registry_sha256"]==
                    sha(workspace/"frozen_contracts"/
                        f"config_b0001_v3_seed_registry_{role}.json"),
                    "Provider used different V3 seed registry: "+label)
            require(pm["v2_domain_registry_sha256"]==
                    frozen["domain_registry_sha256"],
                    "Provider used different frozen M1 domain: "+label)
            require(pm["seed_banks"]==expected_seeds["provider_reconstruction"],
                    "Provider seed banks do not match isolated plan: "+label)
            require(pm["inputs"]["public_card_json_sha256"]==
                    gate["staged_cards_sha256"][label]["card.json"] and
                    pm["inputs"]["public_sigma_surface_sha256"]==
                    gate["staged_cards_sha256"][label]["sigma_surface.csv"],
                    "Provider public card provenance mismatch: "+label)

            provenance={"provider_freeze_manifest.json":sha(fp)}
            for name in PROVIDER_OUTPUT_NAMES:
                path=root/name
                require(path.is_file(),"Missing V3 provider output: "+label+"/"+name)
                provenance[name]=sha(path)
            for k,expected in pm["output_hashes_sha256"].items():
                require(k in pm["outputs"] and
                        sha(root/Path(pm["outputs"][k]).name)==expected,
                        "Provider output hash differs from original freeze: "+label+"/"+k)
                require(Path(pm["outputs"][k]).resolve()==
                        (root/Path(pm["outputs"][k]).name).resolve(),
                        "Provider frozen path points outside B0001 root: "+label+"/"+k)
            candidates=pd.read_csv(root/"v3_candidates_rescore.csv")
            replay=pd.read_csv(root/"v3_candidates_replay.csv")
            m3=pd.read_csv(root/"m3_provider_models.csv")
            surfaces=pd.read_csv(root/"v3_common_rescore_surfaces.csv")
            ids=candidates["candidate_id"].astype(str).tolist()
            require(len(ids)==7 and len(set(ids))==7 and
                    set(ids)=={f"{role}_{provider}_V3_FIT{i}" for i in range(1,8)},
                    "V3 candidate bank identities invalid: "+label)
            require(len(replay)==len(m3)==7 and
                    set(replay["candidate_id"].astype(str))==set(ids) and
                    set(m3["candidate_id"].astype(str))==set(ids),
                    "V3 replay/M3 candidate bank mismatch: "+label)
            require(set(surfaces["candidate_id"].astype(str))==set(ids) and
                    len(surfaces)%7==0,
                    "Rescore surface coverage incomplete: "+label)
            vals=candidates["rescore_rmse"].to_numpy(float)
            require(np.isfinite(vals).all() and (vals>=0).all(),
                    "Nonfinite V3 common-rescore errors: "+label)
            require(np.isfinite(candidates["rescore_mse"].to_numpy(float)).all()
                    and np.allclose(vals**2,candidates["rescore_mse"].to_numpy(float),
                                    rtol=1e-8,atol=1e-10),
                    "V3 rescore MSE/RMSE inconsistency: "+label)
            require(m3["weight"].notna().all() and
                    np.isfinite(m3["weight"].to_numpy(float)).all() and
                    (m3["weight"].to_numpy(float)>=0).all() and
                    abs(float(m3["weight"].sum())-1.0)<=TOL,
                    "Original V3 M3 provider weights invalid: "+label)
            # Original V3 centroid intermediate output is allowed to differ
            # from V3b RMSE selection. Never treat it as the V3b decision.
            quality=candidates.sort_values(
                ["rescore_rmse","candidate_id"],kind="mergesort"
            ).reset_index(drop=True)
            summary.append({"world":role,"provider":provider,
                            "m1_candidate_id":str(quality.iloc[0]["candidate_id"]),
                            "m1_rescore_rmse":float(quality.iloc[0]["rescore_rmse"]),
                            "m2_candidate_ids":";".join(
                                quality.head(3)["candidate_id"].astype(str))})
            tables[provider]=quality
            m3_tables[provider]=m3[["candidate_id","weight"]].copy()
            input_sha[label]=provenance

        # Ensure the original M3 world support matches the provider weights.
        expected_joint=joint_product_support(m3_tables)
        m3_joint=pd.read_csv(world/"m3_joint_support_343.csv")
        m3_top14=pd.read_csv(world/"m3_joint_support_top14.csv")
        require(len(expected_joint)==len(m3_joint)==343 and len(m3_top14)==14,
                "V3 world M3 support cardinality incorrect: "+role)
        for name,observed,expected in (
            ("full",m3_joint,expected_joint),
            ("Top14",m3_top14,expected_joint.head(14))):
            require(observed["joint_rank"].tolist()==expected["joint_rank"].tolist(),
                    "V3 world M3 joint ranks corrupted: "+role+"/"+name)
            require(observed[[f"{x}_candidate_id" for x in PROVIDERS]]
                    .astype(str).to_numpy().tolist()==
                    expected[[f"{x}_candidate_id" for x in PROVIDERS]]
                    .astype(str).to_numpy().tolist(),
                    "V3 M3 candidate combinations corrupted: "+role+"/"+name)
            require(np.allclose(observed["joint_weight"].to_numpy(float),
                                expected["joint_weight"].to_numpy(float),
                                atol=1e-15,rtol=0),
                    "V3 M3 joint weights corrupted: "+role+"/"+name)
        for name in WORLD_OUTPUT_NAMES:
            path=world/name
            require(path.is_file(),"Missing V3 world support "+role+"/"+name)
            input_sha[f"{role}/world/{name}"]=sha(path)
        for key,expected in wf["output_hashes_sha256"].items():
            require(sha(Path(wf["outputs"][key]))==expected,
                    "V3 world output freeze changed: "+role+"/"+key)
            require(Path(wf["outputs"][key]).resolve().is_relative_to(world.resolve()),
                    "V3 world manifest output is outside its world directory")
    return {
        "source_v3_generation_freeze_sha256":sha(frozenfile),
        "source_v3_isolation_gate_sha256":sha(guardfile),
        "source_v3_world_manifest_sha256":v3_world_sha,
        "source_v3_provider_and_support_sha256":input_sha,
        "v3b_contract_sha256":sha(V3B_CONTRACT),
        "original_v3b_source_sha256":source_sha,
        "provider_selection_preview":summary,
        "all_nine_provider_banks_checked":True,
        "all_three_v3_world_supports_checked":True,
        "simulations_executed":0,
        "graph_prediction_authorized":False,
    }


def verify_sources_unchanged(a,checks):
    current=source_inputs(a)
    for name in ("source_v3_generation_freeze_sha256",
                 "source_v3_isolation_gate_sha256",
                 "source_v3_world_manifest_sha256",
                 "source_v3_provider_and_support_sha256",
                 "v3b_contract_sha256",
                 "original_v3b_source_sha256"):
        require(current[name]==checks[name],
                "Frozen V3 evidence changed during V3b selection: "+name)


def run_original_v3b(a,checks):
    sys.path.insert(0,str(PHASE5))
    import freeze_phase5_reconstruction_v3b_selection as original
    import audit_phase5_reconstruction_v3b_selection as auditor
    # B0001-specific SOURCE+OUTPUT paths replace the historical twelve-world
    # defaults. The original scientific selection and audit functions remain
    # unmodified, including tie-breaks and Gibbs M3 support construction.
    originals={
        "freeze":(original.V3_ROOT,original.OUT_ROOT),
        "audit":(auditor.V3_ROOT,auditor.V3B_ROOT),
    }
    original.V3_ROOT=a.v3
    original.OUT_ROOT=a.out
    auditor.V3_ROOT=a.v3
    auditor.V3B_ROOT=a.out
    provider_status=[]
    world_status=[]
    try:
        for world in ROLES:
            for provider in PROVIDERS:
                provider_status.append(original._rank_provider(world,provider))
            world_status.append(original._freeze_world(world))
        # Independently run the original provider + world mechanical audits.
        audit_providers=[
            auditor._audit_provider(role,provider)
            for role in ROLES for provider in PROVIDERS
        ]
        audit_worlds=[auditor._audit_world(role) for role in ROLES]
        # Compare original M3 carried forward byte-independently and ensure
        # selected RMSE rank-1 and rank-1..3 are the same as preview.
        for role in ROLES:
            for provider in PROVIDERS:
                src=a.v3/role/provider
                dst=a.out/role/provider
                unchanged_csv(src/"m3_provider_models.csv",
                              dst/"m3_provider_models.csv",
                              role+"/"+provider+" M3 carry-forward")
            unchanged_csv(a.v3/role/"m3_joint_support_343.csv",
                          a.out/role/"m3_joint_support_343.csv",
                          role+" M3 full support")
            unchanged_csv(a.v3/role/"m3_joint_support_top14.csv",
                          a.out/role/"m3_joint_support_top14.csv",
                          role+" M3 Top14")
    finally:
        original.V3_ROOT,original.OUT_ROOT=originals["freeze"]
        auditor.V3_ROOT,auditor.V3B_ROOT=originals["audit"]

    # Re-read all V3 files and original source hashes before final freeze.
    verify_sources_unchanged(a,checks)
    provider_table=pd.DataFrame(provider_status).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    world_table=pd.DataFrame(world_status).sort_values(
        "world",kind="mergesort"
    ).reset_index(drop=True)
    audit_provider_table=pd.DataFrame(audit_providers).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    audit_world_table=pd.DataFrame(audit_worlds).sort_values(
        "provider_world_id",kind="mergesort"
    ).reset_index(drop=True)
    provider_table.to_csv(a.out/"v3b_provider_selection_summary.csv",index=False)
    world_table.to_csv(a.out/"v3b_world_selection_summary.csv",index=False)
    audit_provider_table.to_csv(a.out/"b0001_v3b_provider_audit.csv",index=False)
    audit_world_table.to_csv(a.out/"b0001_v3b_world_audit.csv",index=False)
    manifest={
        "status":OUT_STATUS,
        "scope":"B0001_P1_P3_P4",
        "source_v3_generation_freeze_sha256":checks["source_v3_generation_freeze_sha256"],
        "source_v3_isolation_gate_sha256":checks["source_v3_isolation_gate_sha256"],
        "source_v3_world_manifest_sha256":checks["source_v3_world_manifest_sha256"],
        "v3b_selection_contract_sha256":checks["v3b_contract_sha256"],
        "original_v3b_source_sha256":checks["original_v3b_source_sha256"],
        "n_provider_selections":9,
        "n_worlds":3,
        "m1_rank_rule":"ascending common-N100 rescore RMSE; candidate ID tie break",
        "m2_provider_rule":"same RMSE ranks 1..3; equal weights",
        "m3_rule":"exact carry-forward V3 Gibbs weights; 343 joint; Top14 prefix",
        "replay_used_for_selection":False,
        "centroid_used_for_selection":False,
        "new_provider_simulations":False,
        "graph_prediction_used":False,
        "graph_whitebox_used":False,
        "final_whitebox_used":False,
        "graph_prediction_authorized":False,
        "provider_manifest_sha256":{
            f"{role}/{provider}":sha(a.out/role/provider/
                                    "provider_selection_freeze_manifest.json")
            for role in ROLES for provider in PROVIDERS
        },
        "world_manifest_sha256":{
            role:sha(a.out/role/"world_selection_freeze_manifest.json")
            for role in ROLES
        },
        "summary_sha256":{
            name:sha(a.out/name)
            for name in (
                "v3b_provider_selection_summary.csv",
                "v3b_world_selection_summary.csv",
                "b0001_v3b_provider_audit.csv",
                "b0001_v3b_world_audit.csv",
            )
        },
    }
    save(a.out/"b0001_v3b_selection_audit_freeze.json",manifest)
    print("B0001_V3B_SELECTION_AND_MECHANICAL_AUDIT_PASS 9 providers 3 worlds",flush=True)
    print(provider_table[["provider_world_id","provider_id",
                          "m1_candidate_id","m1_rmse"]].to_string(index=False),
          flush=True)
    print("M2_27 M3_343 M3_TOP14_14 verified per world",flush=True)
    print("NO_SIMULATIONS / GRAPH_PREDICTIONS_BLOCKED",flush=True)
    print("FREEZE",a.out/"b0001_v3b_selection_audit_freeze.json",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true",
                      help="read-only full source-V3 checks; no output files")
    mode.add_argument("--run",action="store_true",
                      help="materialize B0001-only V3b selections and mechanical audit")
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    args.workspace=args.workspace.expanduser().resolve()
    args.v3=(args.workspace/"v3_results").resolve()
    args.out=args.out.expanduser().resolve()
    require(not args.out.exists(),
            "Refusing to overwrite existing V3b outputs. Select a new --out path.")
    require(args.out!=REPO and REPO not in args.out.parents,
            "V3b output cannot be inside repository")
    require(args.out!=args.workspace and
            args.workspace not in args.out.parents and
            args.out not in args.workspace.parents,
            "V3b output cannot overlap V3 source workspace")
    require(PHASE5 not in args.out.parents,
            "Historical Phase-5 output is off limits")
    checks=source_inputs(args)
    print("B0001_V3B_SOURCE_PREFLIGHT_PASS 9 provider banks 3 V3 supports",flush=True)
    print("V3B_SELECTION_RULE rescore_rmse M3 unchanged",flush=True)
    if args.check:
        print("READ_ONLY_NO_SIMULATIONS_NO_OUTPUTS",flush=True)
        return
    args.out.mkdir(parents=True)
    run_original_v3b(args,checks)


if __name__=="__main__":
    main()
