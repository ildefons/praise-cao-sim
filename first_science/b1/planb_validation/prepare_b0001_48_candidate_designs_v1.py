#!/usr/bin/env python3
"""Freeze BOTH original 48-LHS candidate designs for B0001 using PUBLIC inputs.

No simulations, no white-box/reference access. Original style uses the frozen
new-world M1 domain registry (original historical 48-LHS procedure). Fixed-CV
uses the original Phase-4 pilot domain builder and expanded ProviderC contract
on the same B0001 public I1 metadata. Candidate-design algorithms unchanged.

Run --check for read-only validation, --freeze to create immutable by
convention candidate-design CSVs in a fresh isolated output directory.
Graph runs and local provider scoring are NOT authorized by this file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
P5=REPO/"first_science"/"phase5"
B1=REPO/"first_science"/"b1"/"retrospective_m3"
ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
COLUMNS=("candidate_id","mean_service_time","cost_rate","service_cv")
SOURCES=(
    "first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py",
    "first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py",
    "first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py",
    "first_science/phase4/m2_a2_nonadaptive_coverage.py",
    "first_science/phase3/m1_joint_lift_v2.py",
    "first_science/phase5/run_phase5_m2_reconstruction_v2.py",
)
STATUS="B0001_TWO_48_LHS_PUBLIC_DESIGN_BANKS_FROZEN_NO_SIMULATION"


def require(cond,msg):
    if not cond:raise RuntimeError("B0001 48-LHS: "+msg)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dependencies():
    # Historical modules require the modified YAFS runtime, available in
    # the user's project checkout; preserve original functions.
    for root in (B1,REPO/"first_science"/"phase2",
                 REPO/"first_science"/"phase3",
                 REPO/"first_science"/"phase4",P5):
        if str(root) not in sys.path:sys.path.insert(0,str(root))
    import run_pilot_m3_generalization_v1 as original
    import run_pilot_m3_policy_transfer_v1 as policy
    import _pilot_m3_policy_transfer_core_v1 as core
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    from run_phase5_m2_reconstruction_v2 import _bounds
    return original,policy,core,load_rho_conditioned_i1_provider_card,_bounds


def prepare(a):
    stage_path=a.staging/"b0001_public_inputs_manifest.json"
    stage=load(stage_path)
    require(stage["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE"
            and stage["cells"]==12
            and stage["hidden_world_parameters_copied"] is False,
            "Frozen public I1 staging invalid")
    registry=a.registry
    require(registry.is_file(),"Missing B0001 nine-provider domain registry")
    cols=pd.read_csv(registry)
    require(len(cols)==9 and
            set(zip(cols.provider_world_id,cols.provider_id))==
            {(w,p) for w in ROLES for p in PROVIDERS},
            "Domain registry must have exactly nine new-world rows")
    require("provider_freeze_sha256" in cols.columns,
            "Not a B0001 M1 frozen domain registry")
    dlookup={(r.provider_world_id,r.provider_id):pd.Series(r._asdict())
             for r in cols.itertuples(index=False)}
    staged={x["path"]:x["staged_sha256"] for x in stage["staged_files"]}
    cards={}
    for world in ROLES:
        for provider in PROVIDERS:
            base=a.staging/"public_I1"/world/provider
            hashes={}
            for filename in ("card.json","sigma_surface.csv"):
                path=base/filename
                key=f"public_I1/{world}/{provider}/{filename}"
                require(key in staged and digest(path)==staged[key],
                        "Staged public card SHA mismatch: "+key)
                hashes[filename]=staged[key]
            cards[world,provider]=hashes
    original,policy,core,load_card,bounds=dependencies()
    o_cfg=load(original.CONFIG)
    p_cfg=load(policy.CONFIG)
    require(o_cfg["status"]=="B1_RETROSPECTIVE_M3_V1_DESIGN_FROZEN"
            and p_cfg["status"]=="B1_PILOT_M3_POLICY_TRANSFER_V1_FROZEN",
            "Original 48-point designs changed")
    require(o_cfg["n_candidates_per_provider"]==
            p_cfg["n_candidates_per_provider"]==48
            and o_cfg["lhs_seed"]==p_cfg["lhs_seed"]==20260917,
            "48-LHS candidate count or original seed changed")
    # Replace ONLY input access. Never open the original historical Phase5
    # I1/world registry, private B0001 physical world, or WB.
    old_legacy_row=original._domain_row
    old_pilot_card=core._load_public_card
    def domain_row(world,provider):
        require((world,provider) in dlookup,
                "Original design requested non-B0001 domain")
        return dlookup[world,provider]
    def public_card(world,provider):
        require((world,provider) in cards,
                "Pilot design requested non-B0001 card")
        base=a.staging/"public_I1"/world/provider
        metadata,surface=load_card(base)
        return metadata,surface,{
            "card_json_sha256":cards[world,provider]["card.json"],
            "sigma_surface_sha256":cards[world,provider]["sigma_surface.csv"],
        }
    original._domain_row=domain_row
    core._load_public_card=public_card
    designs={}
    try:
        for world in ROLES:
            for provider in PROVIDERS:
                for family,fn,cfg in (
                    ("original",original.candidate_design,o_cfg),
                    ("fixed_cv",policy.candidate_design,p_cfg),
                ):
                    df=fn(cfg,world,provider)
                    require(len(df)==48 and
                            set(COLUMNS).issubset(df.columns) and
                            df.candidate_id.nunique()==48,
                            "Invalid candidate model count/identity: "+
                            family+"/"+world+"/"+provider)
                    v=df[list(COLUMNS[1:])].to_numpy(dtype=float)
                    require(np.isfinite(v).all() and (v>0).all(),
                            "Nonpositive/nonfinite candidate parameter")
                    require(df.candidate_id.astype(str).tolist()==[
                        f"{world}_{provider}_LHS_{i:03d}" for i in range(48)],
                        "Original candidate ID/order changed")
                    designs[family,world,provider]=df[list(COLUMNS)]
    finally:
        original._domain_row=old_legacy_row
        core._load_public_card=old_pilot_card
    return designs,stage_path,registry,cards


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging",type=Path,required=True)
    p.add_argument("--registry",type=Path,required=True,
                   help="Frozen B0001 phase5_m1_domain_registry.csv, not historical registry")
    p.add_argument("--out",type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--freeze",action="store_true")
    a=p.parse_args()
    for name in ("staging","registry","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    require(REPO not in a.out.parents and a.out!=REPO,
            "Output must be outside Git checkout")
    require(a.out!=a.staging and a.staging not in a.out.parents
            and a.out not in a.staging.parents,
            "Output/staging overlap")
    designs,stage,registry,cards=prepare(a)
    # Count how often the two historical candidate domains differ;
    # do not interpret discrepancies as failures or tune them.
    distinct=sum(not np.array_equal(
        designs["original",world,provider].iloc[:,1:].to_numpy(),
        designs["fixed_cv",world,provider].iloc[:,1:].to_numpy()
    ) for world in ROLES for provider in PROVIDERS)
    print("B0001_48_LHS_DESIGN_CHECK_PASS",len(designs),"provider-family banks",
          "432 candidates per family? NO, 432 total per family? NO: 9x48x2=864 total",
          flush=True)
    print("B0001_ORIGINAL_VS_PILOT_DESIGN_DIFFERENCES",distinct,"of 9 providers",
          flush=True)
    if a.check:
        print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ",flush=True)
        return
    require(not a.out.exists(),"Refusing overwrite of design freeze")
    a.out.mkdir(parents=True)
    hashes={}
    for (family,world,provider),df in designs.items():
        path=a.out/family/world/(provider+"_lhs_design.csv")
        path.parent.mkdir(parents=True,exist_ok=True)
        df.to_csv(path,index=False)
        hashes[str(path.relative_to(a.out))]=digest(path)
    manifest={
        "status":STATUS,"families":["original","fixed_cv"],
        "provider_banks_per_family":9,"candidate_count_per_provider":48,
        "candidate_models_total":864,
        "different_original_vs_pilot_provider_domains":distinct,
        "historical_source_sha256":{name:digest(REPO/name) for name in SOURCES},
        "original_config_sha256":digest(B1/"config_pilot_m3_generalization_v1.json"),
        "pilot_transfer_config_sha256":digest(B1/"config_pilot_m3_policy_transfer_v1.json"),
        "public_input_stage_sha256":digest(stage),
        "b0001_m1_domain_registry_sha256":digest(registry),
        "staged_public_card_sha256":{
            f"{world}/{provider}":detail for (world,provider),detail in cards.items()
        },
        "design_file_sha256":hashes,
        "whitebox_reference_read":False,
        "provider_simulations":0,
        "graph_simulations":0,
        "evaluation_authorized":False,
        "next":"isolate candidate local rescoring with fresh seeds, check original and CV supports, verify no WB, then run four missing B1400 graph predictors",
    }
    dest=a.out/"b0001_48_lhs_design_freeze.json"
    dest.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",
                    encoding="utf-8")
    print("B0001_TWO_48_LHS_DESIGN_BANKS_FROZEN_NO_SIMULATION")
    print("FREEZE",dest)


if __name__=="__main__":
    main()
