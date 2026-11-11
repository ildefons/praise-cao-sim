#!/usr/bin/env python3
"""Isolated B0001 V3 seven-candidate provider reconstruction.

--check: simulation-free preparation and scientific-firewall audit.
--run: ONLY after --check succeeds; executes original Phase-5 V3 provider fits
and world-support materialization with fresh B0001 seed banks. Does NOT
perform the historical V3 centroid selection as the final B0001 V3b M1/M2
decision, does NOT execute graph predictions, and does NOT read final WB.

Original scientific functions _run_provider/_freeze_world are reused; their
world-dependent input access is replaced by checked B0001 public card and
frozen-domain readers. The original historical paths are never overwritten.
Use --workers 1: process-local adapter wiring is deliberately not forked.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

import preflight_b0001_v3_domains_v1 as p
from preflight_b0001_v3_domains_v1 import read,digest,require

PHASE5=p.P5
ROLES=p.ROLES
PROVIDERS=p.PROVIDERS
SOURCE_FILES=(
    "run_phase5_provider_reconstruction_v3.py",
    "phase5_reconstruction_v3_selection.py",
    "run_phase5_m2_reconstruction_v2.py",
    "phase5_runtime_v2.py",
)
CONFIG_FILE="config_phase5_provider_reconstruction_v3.json"
SEEDS_FILE="config_phase5_seed_registry_v3.json"
DOMAINS_FILE="phase5_m1_domain_registry.csv"
GUARD_FILE="b0001_v3_isolation_check.json"
RESULTS="v3_results"


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def in_repo(path):
    return path==p.REPO or p.REPO in path.parents


def security_paths(out,staging,domains,preflight,eligibility,domain_preflight):
    require(not in_repo(out),"V3 results may not be written inside repository")
    for target in (staging,domains,domains.parent,preflight.parent,
                   eligibility.parent,domain_preflight.parent):
        require(out!=target and target not in out.parents and
                out not in target.parents,
                "V3 output must be isolated from all scientific input artifacts")


def validate_prerequisites(a):
    # Run the entire original B0001 V3 preflight again; do not trust a
    # status string alone or a manifest copied from another machine.
    result=p.check(a.staging,a.domains,a.preflight,a.eligibility)
    dp=read(a.domain_preflight)
    require(dp["status"]=="B0001_NINE_DOMAIN_V3_PREFLIGHT_PASS_EXECUTION_BLOCKED",
            "B0001 V3 domain preflight status invalid")
    for field in (
        "registry_sha256","domain_freeze_sha256","staged_public_manifest_sha256",
        "reconstruction_preflight_sha256","eligibility_freeze_sha256",
        "original_source_sha256","planned_local_seed_banks_by_world",
    ):
        require(dp[field]==result[field],
                "Original domain preflight no longer matches source evidence: "+field)
    require(dp["simulations_executed"]==0 and
            dp["reconstruction_execution_authorized"] is False,
            "Unexpected earlier execution authorization in domain preflight")
    require(dp["v3_total_fit_count"]==63,
            "Unexpected B0001 V3 sample count")
    return result


def public_card_hashes(staging):
    stage=read(staging/"b0001_public_inputs_manifest.json")
    rows=stage["staged_files"]
    paths={entry["path"]:entry for entry in rows}
    result={}
    for role in ROLES:
        for prov in PROVIDERS:
            folder=staging/"public_I1"/role/prov
            result[f"{role}/{prov}"]={}
            for name in ("card.json","sigma_surface.csv"):
                relative=f"public_I1/{role}/{prov}/{name}"
                require(relative in paths,"Card missing from staged manifest: "+relative)
                path=folder/name
                require(path.is_file(),"Card missing on disk: "+relative)
                actual=digest(path)
                require(actual==paths[relative]["staged_sha256"],
                        "Public card hash mismatch: "+relative)
                result[f"{role}/{prov}"][name]=actual
    return result


def setup(a,preflight_result):
    out=a.out
    frozen=out/"frozen_contracts"
    require(not out.exists(),"Cannot initialize over an existing B0001 V3 workspace")
    out.mkdir(parents=True)
    frozen.mkdir()
    for filename in SOURCE_FILES:
        require((PHASE5/filename).is_file(),"Missing V3 scientific source: "+filename)
    shutil.copy2(PHASE5/CONFIG_FILE,frozen/CONFIG_FILE)
    original=read(PHASE5/SEEDS_FILE)
    require(original["status"]=="FROZEN_PHASE5_SEED_REGISTRY_V3",
            "Original V3 seed config changed")
    # B0001 seed configuration is per-world (not one global historical bank).
    all_seeds={}
    for role in ROLES:
        seed=copy.deepcopy(original)
        seed["provider_reconstruction"]=preflight_result["planned_local_seed_banks_by_world"][role]
        seed["b0001_world_role"]=role
        path=frozen/f"config_b0001_v3_seed_registry_{role}.json"
        save(path,seed)
        all_seeds[role]=digest(path)
    # Original domain table is copied verbatim; all V3 input access points
    # will use this only, and hash checks tie it to the frozen M1 audit.
    shutil.copy2(a.domains/DOMAINS_FILE,frozen/DOMAINS_FILE)
    require(digest(frozen/DOMAINS_FILE)==preflight_result["registry_sha256"],
            "Domain registry copy mismatch")
    cards=public_card_hashes(a.staging)
    meta={
        "status":"B0001_V3_ISOLATION_CHECK_PASS_NO_SIMULATIONS",
        "source_files_sha256":{name:digest(PHASE5/name) for name in SOURCE_FILES},
        "config_v3_sha256":digest(PHASE5/CONFIG_FILE),
        "config_v3b_sha256":digest(PHASE5/"config_phase5_provider_reconstruction_v3b.json"),
        "frozen_domain_sha256":digest(frozen/DOMAINS_FILE),
        "domain_preflight_sha256":digest(a.domain_preflight),
        "preflight_reverified":True,
        "staged_cards_sha256":cards,
        "world_specific_v3_seed_configs_sha256":all_seeds,
        "v3_original_algorithm":True,
        "seed_bank_collisions":0,
        "world_roles":list(ROLES),
        "providers_per_world":3,
        "fits_per_provider":7,
        "total_fits":63,
        "v3_m1_m2_centroid_output_intermediate_only":True,
        "v3b_rescore_rmse_selection_pending":True,
        "graph_prediction_authorized":False,
        "simulations_executed":0,
    }
    save(out/GUARD_FILE,meta)
    print("B0001_V3_ISOLATION_CHECK_PASS 9 providers 63 fits",flush=True)
    print("NO_SIMULATIONS_RUN / V3b_SELECTION_PENDING",flush=True)
    print("WORKSPACE",out,flush=True)


def verify_setup(a,preflight_result):
    out=a.out
    require((out/GUARD_FILE).is_file(),
            "Missing isolation check. Run --check first.")
    meta=read(out/GUARD_FILE)
    require(meta["status"]=="B0001_V3_ISOLATION_CHECK_PASS_NO_SIMULATIONS",
            "Unexpected workspace isolation status")
    frozen=out/"frozen_contracts"
    require(meta["domain_preflight_sha256"]==digest(a.domain_preflight),
            "B0001 V3 preflight changed")
    require(meta["frozen_domain_sha256"]==
            preflight_result["registry_sha256"]==
            digest(frozen/DOMAINS_FILE),
            "Frozen M1 domain registry changed")
    require(meta["config_v3_sha256"]==
            digest(PHASE5/CONFIG_FILE)==digest(frozen/CONFIG_FILE),
            "Original V3 scientific contract changed")
    require(meta["config_v3b_sha256"]==
            digest(PHASE5/"config_phase5_provider_reconstruction_v3b.json"),
            "Original V3b scientific contract changed")
    for name,old_sha in meta["source_files_sha256"].items():
        require(digest(PHASE5/name)==old_sha,
                "V3 scientific code changed since isolation gate: "+name)
    require(meta["staged_cards_sha256"]==public_card_hashes(a.staging),
            "Staged B0001 public cards changed")
    for role in ROLES:
        path=frozen/f"config_b0001_v3_seed_registry_{role}.json"
        require(digest(path)==meta["world_specific_v3_seed_configs_sha256"][role],
                "B0001 V3 per-world seed registry changed")
        require(read(path)["provider_reconstruction"]==
                preflight_result["planned_local_seed_banks_by_world"][role],
                "B0001 V3 fresh seeds differ from audited plan")
    require(meta["graph_prediction_authorized"] is False,
            "Unexpected prediction authorization")
    print("B0001_V3_ISOLATION_RECHECK_PASS",flush=True)


def original_runner():
    sys.path.insert(0,str(PHASE5))
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    import run_phase5_provider_reconstruction_v3 as v3
    from run_phase5_m2_reconstruction_v2 import _bounds
    return v3,load_rho_conditioned_i1_provider_card,_bounds


def read_domain_table(path):
    with path.open(newline="",encoding="utf-8") as fh:
        rows=list(csv.DictReader(fh))
    lookup={(r["provider_world_id"],r["provider_id"]):r for r in rows}
    require(len(lookup)==9,"Domain registry should contain nine unique providers")
    return lookup


def audit_finished_provider(v3,out,role,provider,domain,seed,card_hashes):
    root=out/RESULTS/role/provider
    freeze=root/"provider_freeze_manifest.json"
    if not freeze.exists():
        return False
    f=read(freeze)
    require(f["status"]=="FROZEN_PHASE5_V3_PROVIDER_RECONSTRUCTION",
            "Existing V3 provider checkpoint status invalid")
    require(f["inputs"]["provider_world_id"]==role and
            f["inputs"]["provider_id"]==provider,
            "V3 checkpoint provider identity changed")
    require(f["inputs"]["public_card_json_sha256"]==
            card_hashes[f"{role}/{provider}"]["card.json"] and
            f["inputs"]["public_sigma_surface_sha256"]==
            card_hashes[f"{role}/{provider}"]["sigma_surface.csv"],
            "Existing provider freeze tied to different public I1 card")
    for field in ("mean_service_time_lower","mean_service_time_upper",
                  "cost_rate_lower","cost_rate_upper",
                  "service_cv_lower","service_cv_upper"):
        require(math.isclose(float(f["inputs"]["frozen_domain"][field]),
                             float(domain[field]),rel_tol=0,abs_tol=1e-12),
                "Existing V3 provider freeze used different domain")
    for bank,value in seed["provider_reconstruction"].items():
        require(f["seed_banks"][bank]==value,
                "Existing V3 provider freeze used different seed bank")
    require(f["v3_reconstruction_contract_sha256"]==
            digest(out/"frozen_contracts"/CONFIG_FILE) and
            f["v3_seed_registry_sha256"]==
            digest(out/"frozen_contracts"/f"config_b0001_v3_seed_registry_{role}.json") and
            f["v2_domain_registry_sha256"]==
            digest(out/"frozen_contracts"/DOMAINS_FILE),
            "Existing V3 provider freeze has incompatible source contracts")
    for key,value in f["output_hashes_sha256"].items():
        path=Path(f["outputs"][key]).resolve()
        require(root in path.parents and digest(path)==value,
                "Existing V3 provider output was modified: "+str(path))
    return True


def run(a,preflight_result):
    verify_setup(a,preflight_result)
    v3,load_card,bounds=v3_runner=original_runner()
    output=a.out/RESULTS
    lookup=read_domain_table(a.out/"frozen_contracts"/DOMAINS_FILE)
    cards=read(a.out/GUARD_FILE)["staged_cards_sha256"]
    config_path=a.out/"frozen_contracts"/CONFIG_FILE
    domain_path=a.out/"frozen_contracts"/DOMAINS_FILE
    # Original module-level import bindings: store and restore after scientific
    # functions return. No historical Phase-5 prerequisite or I1 loader used.
    originals={name:getattr(v3,name) for name in
               ("CFG","SEEDS","DOMAIN_REGISTRY","_load_public_card",
                "_domain_row","_v3_objects")}
    try:
        v3.CFG=config_path
        v3.DOMAIN_REGISTRY=domain_path
        for role in ROLES:
            seed_path=a.out/"frozen_contracts"/f"config_b0001_v3_seed_registry_{role}.json"
            config=read(config_path)
            seed=read(seed_path)
            def provider_card(world,provider):
                require(world==role and provider in PROVIDERS,
                        "V3 requested provider outside isolated role")
                folder=a.staging/"public_I1"/role/provider
                require(digest(folder/"card.json")==cards[f"{role}/{provider}"]["card.json"]
                        and digest(folder/"sigma_surface.csv")==
                        cards[f"{role}/{provider}"]["sigma_surface.csv"],
                        "B0001 public-I1 inputs modified during V3 run")
                metadata,surface=load_card(folder)
                return metadata,surface,{
                    "card_json_sha256":digest(folder/"card.json"),
                    "sigma_surface_sha256":digest(folder/"sigma_surface.csv"),
                }
            def domain_row(world,provider):
                require(world==role and provider in PROVIDERS,
                        "V3 requested domain outside isolated role")
                return lookup[(world,provider)]
            v3.SEEDS=seed_path
            v3._v3_objects=lambda config=config,seed=seed:(config,seed)
            v3._load_public_card=provider_card
            v3._domain_row=domain_row
            for provider in PROVIDERS:
                if audit_finished_provider(v3,a.out,role,provider,
                                           lookup[(role,provider)],seed,cards):
                    print("B0001_V3_PROVIDER_CHECKPOINT_REUSED",role,provider,flush=True)
                    continue
                print("B0001_V3_FIT_START",role,provider,flush=True)
                v3._run_provider(role,provider,str(output))
                require(audit_finished_provider(v3,a.out,role,provider,
                                                lookup[(role,provider)],seed,cards),
                        "Provider finished without a valid frozen V3 checkpoint")
            # Source V3 materializes 27 equal-weight M2 combinations and 343
            # Gibbs-weighted M3 combinations; V3b will replace M1/M2 ranking.
            if not (output/role/"world_reconstruction_freeze_manifest.json").exists():
                v3._freeze_world(role,output)
            print("B0001_V3_WORLD_FROZEN",role,flush=True)
    finally:
        for name,value in originals.items():
            setattr(v3,name,value)
    status={
        "status":"B0001_V3_CANDIDATE_GENERATION_FROZEN_V3B_SELECTION_PENDING",
        "isolation_gate_sha256":digest(a.out/GUARD_FILE),
        "original_v3_config_sha256":digest(config_path),
        "domain_registry_sha256":digest(domain_path),
        "world_sha256":{
            role:digest(output/role/"world_reconstruction_freeze_manifest.json")
            for role in ROLES
        },
        "n_provider_banks":9,
        "n_candidate_fits":63,
        "v3b_m1_m2_selection_complete":False,
        "graph_prediction_authorized":False,
    }
    status_path=a.out/"b0001_v3_candidate_generation_freeze.json"
    require(not status_path.exists(),"Refusing to overwrite V3 candidate freeze")
    save(status_path,status)
    print("B0001_V3_CANDIDATE_GENERATION_FROZEN",flush=True)
    print("V3B_SELECTION_PENDING / GRAPH_PREDICTIONS_BLOCKED",flush=True)
    print("FREEZE",status_path,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true",
                      help="read-only scientific checks and initialize isolated workspace")
    mode.add_argument("--run",action="store_true",
                      help="run original V3 provider candidate fitting, after --check")
    ap.add_argument("--staging",type=Path,required=True)
    ap.add_argument("--domains",type=Path,required=True)
    ap.add_argument("--preflight",type=Path,required=True)
    ap.add_argument("--eligibility",type=Path,required=True)
    ap.add_argument("--domain-preflight",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    for name in ("staging","domains","preflight","eligibility","domain_preflight","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    security_paths(a.out,a.staging,a.domains,a.preflight,a.eligibility,a.domain_preflight)
    check=validate_prerequisites(a)
    if a.check:
        if not a.out.exists():
            setup(a,check)
        else:
            verify_setup(a,check)
        return
    require(a.out.exists(),"Run --check before --run")
    run(a,check)


if __name__=="__main__":
    main()
