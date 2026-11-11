#!/usr/bin/env python3
"""B0001 M1-derived final domain establishment for nine providers.

The original Phase-5 M1 V2 _run_one performs the actual science. This adapter
isolates its contract, reads only staged public I1 cards, and uses separate
new-world reconstruction seed banks. After the nine original M1 V2 fits have
frozen, a strict domain audit extracts their exact final declared search bounds.
No historical M1 provider fits/domains are copied and no graph WB is read.
--verify performs only source/input/seed checks; --run executes M1 simulations.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import isolated_step0_pilot_v1 as base

ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SELECTED={"P1":"B0001_P1_A02","P3":"B0001_P3_A01","P4":"B0001_P4_A01"}
LOCAL_SIZES=(25,100,100)
BANK_NAMES=("M1_M2_local_search_CRN","M1_M2_local_confirmation_CRN","M1_M2_local_replay_CRN")
SOURCE=("run_phase5_m1_reconstruction_v2.py","audit_phase5_m1_reconstruction_v2.py")
FIELDS=("mean_service_time","cost_rate","service_cv")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def require(ok,message):
    if not ok:
        raise RuntimeError(message)


def block(start,n):
    return {"start":start,"end_inclusive":start+n-1,"n":n}


def new_banks(candidate):
    # Candidate-specific namespace: 0..599 already occupied by I1/Step0.
    # 650..874 is reserved for M1, leaving room for later V3 banks.
    start=base.seed_blocks(candidate)["region"]["start"]+650
    return {BANK_NAMES[0]:block(start,25),
            BANK_NAMES[1]:block(start+25,100),
            BANK_NAMES[2]:block(start+125,100)}


def source_check():
    sources={name:base.sha(base.PHASE5/name) for name in SOURCE}
    m1=(base.PHASE5/SOURCE[0]).read_text(encoding="utf-8")
    audit=(base.PHASE5/SOURCE[1]).read_text(encoding="utf-8")
    require("_run_one(world_id:str,provider:str,result_root:str)" in m1,
            "Original M1 V2 API changed")
    require("run_joint_lift_for_provider(" in m1 and
            "_expanded_contract(base,hits0)" in m1,
            "Original boundary expansion method changed")
    require('best["optimizer"]["search_bounds"]' in audit,
            "Original final-domain source changed")
    return sources


def inputs(staging,preflight):
    staging=staging.expanduser().resolve()
    f=load(staging/"b0001_public_inputs_manifest.json")
    require(f["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE",
            "Public stage not frozen")
    require(f["selected_worlds"]==SELECTED and f["prediction_execution_authorized"] is False,
            "Staged selection/authorization differs")
    for entry in f["staged_files"]:
        p=staging/entry["path"]
        require(p.is_file() and base.sha(p)==entry["staged_sha256"],
                "Public evidence missing or changed: "+str(p))
    pf=load(preflight.expanduser().resolve())
    require(pf["status"]=="B0001_V3_RECONSTRUCTION_PUBLIC_COMPATIBILITY_PASS_DOMAIN_PENDING",
            "Prerequisite preflight did not pass")
    require(pf["staged_manifest_sha256"]==base.sha(staging/"b0001_public_inputs_manifest.json"),
            "Staged I1 changed since preflight")
    return f


def assert_safe(out,staging):
    out=out.expanduser().resolve()
    require(out!=base.REPO and base.REPO not in out.parents,
            "Domain workspace inside source repository")
    require(out!=staging and staging not in out.parents,
            "Domain workspace inside staged public evidence")


def validate_seed_plan():
    used=set()
    all_rows=[]
    for role in ROLES:
        c=SELECTED[role]
        banks=new_banks(c)
        for name,spec in banks.items():
            require(spec["end_inclusive"]<=base.MAX_TRAJECTORY_SEED and
                    spec["end_inclusive"]*100+3<=base.MAX_NATIVE_SEED,
                    "Native NumPy seed overflow")
            region=set(range(spec["start"],spec["end_inclusive"]+1))
            require(not (region&used),"Cross-role or cross-stage reconstruction seed collision")
            used|=region
            all_rows.append({"role":role,"bank":name,**spec})
        step=base.seed_blocks(c)
        for name in ("region","sigma","calibration","confirmation"):
            spec=step[name]
            require(not (used & set(range(spec["start"],spec["end_inclusive"]+1))),
                    "M1 seeds overlap existing Step-0/I1")
    for other in ("B0001_P1_A01",):
        old=base.seed_blocks(other)
        for b in old.values():
            require(not (used&set(range(b["start"],b["end_inclusive"]+1))),
                    "M1 seeds overlap rejected candidate")
    return all_rows


def setup(out,staging,preflight):
    require(not out.exists(),"Refusing to overwrite existing domain workspace")
    out.mkdir(parents=True)
    sources=source_check()
    rows=validate_seed_plan()
    stagefile=staging/"b0001_public_inputs_manifest.json"
    pf=preflight.expanduser().resolve()
    phases={}
    for role in ROLES:
        phase=out/"contracts"/role
        phase.mkdir(parents=True)
        # Copy the original *scientific* contracts. Provider world entries are
        # not consulted by M1; no hidden new-world world parameters are copied.
        for name in base.COPY_NAMES:
            shutil.copy2(base.PHASE5/name,phase/name)
        path=phase/"config_phase5_seed_registry_v2.json"
        registry=load(path)
        for name,b in new_banks(SELECTED[role]).items():
            registry["provider_reconstruction"][name]=b
        save(path,registry)
        phases[role]={
            "contract_sha256":{name:base.sha(phase/name) for name in base.COPY_NAMES},
            "M1_seed_banks":new_banks(SELECTED[role]),
        }
    status={
        "status":"B0001_M1_DOMAIN_SETUP_NO_FITS",
        "stage_manifest_sha256":base.sha(stagefile),
        "preflight_sha256":base.sha(pf),
        "source_sha256":sources,
        "selected":SELECTED,
        "phases":phases,
        "seed_plan":rows,
        "hidden_new_world_parameters_copied":False,
        "original_m1_v2_scientific_implementation":True,
        "simulations_generated":0,
    }
    save(out/"domain_setup.json",status)


def verify(out,staging,preflight):
    inputs(staging,preflight)
    source_check()
    validate_seed_plan()
    if not out.exists():
        print("B0001_M1_DOMAIN_VERIFY_PASS (setup not yet created)",flush=True)
        return
    meta=load(out/"domain_setup.json")
    require(meta["status"]=="B0001_M1_DOMAIN_SETUP_NO_FITS",
            "Domain setup status changed")
    require(meta["stage_manifest_sha256"]==
            base.sha(staging/"b0001_public_inputs_manifest.json"),
            "Public stage mismatch")
    require(meta["preflight_sha256"]==base.sha(preflight),
            "Reconstruction preflight mismatch")
    require(meta["source_sha256"]==source_check(),
            "Original M1 scientific source changed")
    for role in ROLES:
        phase=out/"contracts"/role
        for name,digest in meta["phases"][role]["contract_sha256"].items():
            require(base.sha(phase/name)==digest,"Contract changed: "+str(phase/name))
    print("B0001_M1_DOMAIN_VERIFY_PASS",flush=True)


def run(out,staging,preflight):
    verify(out,staging,preflight)
    sys.path.insert(0,str(base.PHASE5))
    import run_phase5_m1_reconstruction_v2 as m1
    from phase5_runtime_v2 import load_phase5_contracts
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    original_loader=m1.load_phase5_contracts
    original_card=m1._load_public_card
    try:
        for role in ROLES:
            phase=out/"contracts"/role
            def loader(_path=None,phase=phase):
                return load_phase5_contracts(phase)
            def card(world_id,provider):
                require(world_id==role and provider in PROVIDERS,
                        "M1 requested unexpected provider")
                folder=staging/"public_I1"/role/provider
                metadata,surface=load_rho_conditioned_i1_provider_card(folder)
                rec={"card_json_sha256":base.sha(folder/"card.json"),
                     "sigma_surface_sha256":base.sha(folder/"sigma_surface.csv")}
                return metadata,surface,rec
            m1.load_phase5_contracts=loader
            m1._load_public_card=card
            for provider in PROVIDERS:
                print("B0001_M1_FIT",role,provider,flush=True)
                base.run_stage(out,"m1_"+role+"_"+provider,
                    lambda role=role,provider=provider:m1._run_one(
                        role,provider,str(out/"m1")))
    finally:
        m1.load_phase5_contracts=original_loader
        m1._load_public_card=original_card
    audit_domains(out,staging,preflight)


def audit_domains(out,staging,preflight):
    verify(out,staging,preflight)
    rows=[]
    evidence={}
    for role in ROLES:
        for provider in PROVIDERS:
            root=out/"m1"/role/"m1"/provider
            fp=root/"m1_provider_freeze.json"
            sp=root/"m1_final_parameters.json"
            require(fp.is_file() and sp.is_file(),
                    "M1 fit not finished: "+role+"/"+provider)
            f=load(fp); s=load(sp)
            require(f["status"]=="FROZEN_PHASE5_M1_PROVIDER_V2" and
                    s["status"]=="FROZEN_PHASE5_M1_PROVIDER_V2" and
                    s["instantiable"] is True and not s["unresolved_boundary_reasons"],
                    "M1 provider not instantiable: "+role+"/"+provider)
            require(f["inputs"]["hidden_provider_parameters_used"] is False and
                    f["inputs"]["step0_WB_values_used"] is False and
                    f["inputs"]["graph_WB_used"] is False,
                    "M1 evidence firewall violated")
            expected=load(out/"domain_setup.json")["phases"][role]["contract_sha256"]
            for key,filename in (
                ("battery_config_sha256","config_phase5_recoverability_battery_v2.json"),
                ("seed_registry_sha256","config_phase5_seed_registry_v2.json"),
                ("method_contract_sha256","config_phase5_method_instantiation_v2.json"),
                ("analysis_contract_sha256","config_phase5_analysis_addendum_v2.json"),
                ("execution_contract_sha256","config_phase5_execution_contract_v2.json"),
            ):
                require(f[key]==expected[filename],"M1 freeze/contract mismatch")
            for name,spec in new_banks(SELECTED[role]).items():
                short={"M1_M2_local_search_CRN":"local_search",
                       "M1_M2_local_confirmation_CRN":"local_confirmation",
                       "M1_M2_local_replay_CRN":"local_replay"}[name]
                require(f["seed_banks"][short]==spec,
                        "M1 fit seeds not from reserved reconstruction namespace")
            round_no=int(s["final_round"])
            require(round_no in (0,1),"More than one domain expansion")
            best_path=root/("round0" if round_no==0 else "round1_expanded")/"m1_v2_best.json"
            best=load(best_path)
            bounds=best["optimizer"]["search_bounds"]
            values=s["parameters"]
            row={"provider_world_id":role,"provider_id":provider,
                 "final_round":round_no,"expanded":bool(round_no),
                 "initial_boundary_hits":str(s["initial_boundary_hits"]),
                 "one_round_expansion":str(s["one_round_expansion"])}
            for field in FIELDS:
                lo=float(bounds[field+"_lower"])
                hi=float(bounds[field+"_upper"])
                x=float(values[field])
                valid_domain=(0.0<=lo<hi if field=="service_cv" else 0.0<lo<hi)
                require(valid_domain and lo<=x<=hi,
                        f"Final M1 domain invalid for {role}/{provider}/{field}: "
                        f"value={x!r}, bounds=[{lo!r},{hi!r}]")
                row[field+"_lower"]=lo
                row[field+"_upper"]=hi
                row["selected_"+field]=x
            row["cost_rate_public_reference"]=float(bounds["cost_rate_public_reference"])
            row["provider_freeze_sha256"]=base.sha(fp)
            row["m1_best_sha256"]=base.sha(best_path)
            evidence[role+"/"+provider]={"freeze_sha256":base.sha(fp),
                                       "summary_sha256":base.sha(sp),
                                       "m1_best_sha256":base.sha(best_path)}
            rows.append(row)
    require(len(rows)==9,"Missing B0001 provider-domain coverage")
    root=out/"domains"
    require(not root.exists(),"Refusing to overwrite frozen B0001 domain registry")
    root.mkdir(parents=True)
    table=root/"phase5_m1_domain_registry.csv"
    with table.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest={
        "status":"B0001_NINE_M1_FINAL_DOMAINS_FROZEN",
        "registry_sha256":base.sha(table),
        "source_original_domain_audit_sha256":base.sha(base.PHASE5/SOURCE[1]),
        "provider_evidence_sha256":evidence,
        "n_providers":9,
        "n_expanded":sum(int(x["expanded"]) for x in rows),
        "source_public_inputs_sha256":base.sha(staging/"b0001_public_inputs_manifest.json"),
        "method_outcomes_used":False,
        "graph_whitebox_used":False,
        "final_whitebox_used":False,
        "v3_predictions_authorized":False,
    }
    save(root/"b0001_m1_domain_freeze.json",manifest)
    print("B0001_NINE_M1_FINAL_DOMAINS_FROZEN",flush=True)
    print("REGISTRY",table,flush=True)
    print("FREEZE",root/"b0001_m1_domain_freeze.json",flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging",required=True,type=Path)
    p.add_argument("--preflight",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--verify",action="store_true")
    modes.add_argument("--run",action="store_true")
    modes.add_argument("--audit",action="store_true")
    a=p.parse_args()
    out=a.out.expanduser().resolve()
    staging=a.staging.expanduser().resolve()
    preflight=a.preflight.expanduser().resolve()
    assert_safe(out,staging)
    inputs(staging,preflight)
    if a.verify:
        verify(out,staging,preflight)
        return
    if a.run:
        if not out.exists():
            setup(out,staging,preflight)
        run(out,staging,preflight)
    else:
        audit_domains(out,staging,preflight)


if __name__=="__main__":
    main()
