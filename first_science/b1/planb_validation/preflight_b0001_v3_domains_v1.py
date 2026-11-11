#!/usr/bin/env python3
"""Simulation-free B0001 V3 provider reconstruction domain and seed preflight.

Revalidates immutable nine-domain M1 evidence and the staged public-I1 cards.
Produces a new B0001-specific, disjoint V3 *provider-local* seed plan, without
copying historical domains, accessing hidden physical parameters, running any
simulations, or authorizing reconstruction. The historical V3 runner itself is
not rewired by this audit. Its preexisting output/input paths remain unsafe for
B0001 unless a separately tested adapter redirects them.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
P5=REPO/"first_science"/"phase5"
ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
WORLDS={"P1":"B0001_P1_A02","P3":"B0001_P3_A01","P4":"B0001_P4_A01"}
BANK_NAMES=tuple([f"fit_{k}_search" for k in range(1,8)]+["common_rescore","common_replay"])
REQUIRED_BOUNDS=("mean_service_time","cost_rate","service_cv")
SOURCE_FILES=(
    "first_science/phase5/run_phase5_provider_reconstruction_v3.py",
    "first_science/phase5/phase5_reconstruction_v3_selection.py",
    "first_science/phase5/config_phase5_provider_reconstruction_v3.json",
    "first_science/phase5/config_phase5_provider_reconstruction_v3b.json",
    "first_science/phase5/config_phase5_seed_registry_v3.json",
    "first_science/phase5/audit_phase5_m1_reconstruction_v2.py",
    "first_science/b1/planb_validation/establish_b0001_m1_domains_v1.py",
)


def require(ok,message):
    if not ok:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def seed_ranges(world, role):
    # The B0001 Step-0 candidate banks occupy +0..+599 and its M1-domain
    # bank occupies +650..+874. Reserve +1000..+1304 for V3.
    base=int(world["seed_blocks"]["region"]["start"])+1000
    out={}
    for i,k in enumerate(BANK_NAMES):
        start=base+i*25 if i<7 else base+200+(i-7)*100
        n=15 if i<7 else 100
        out[k]={"start":start,"end_inclusive":start+n-1,"n":n}
    return out


def check(staging,domains,preflight,eligibility):
    stage_file=staging/"b0001_public_inputs_manifest.json"
    domain_file=domains/"b0001_m1_domain_freeze.json"
    registry=domains/"phase5_m1_domain_registry.csv"
    setup_file=domains.parent/"domain_setup.json"
    pf_file=preflight
    eligibility_file=eligibility
    for p in (stage_file,domain_file,registry,setup_file,pf_file,eligibility_file):
        require(p.is_file(),"Prerequisite not found: "+str(p))
    stage=read(stage_file)
    frozen=read(domain_file)
    setup=read(setup_file)
    pf=read(pf_file)
    eligible=read(eligibility_file)
    require(stage["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE",
            "Public input staging status mismatch")
    require(stage["selected_worlds"]==WORLDS and stage["prediction_execution_authorized"] is False,
            "Unexpected B0001 selected worlds or prediction authorization")
    require(pf["status"]=="B0001_V3_RECONSTRUCTION_PUBLIC_COMPATIBILITY_PASS_DOMAIN_PENDING"
            and pf["staged_manifest_sha256"]==digest(stage_file),
            "Public preflight did not pass on these inputs")
    require(frozen["status"]=="B0001_NINE_M1_FINAL_DOMAINS_FROZEN",
            "Nine-domain freeze status invalid")
    require(frozen["registry_sha256"]==digest(registry),
            "Nine-domain registry hash changed")
    require(frozen["source_public_inputs_sha256"]==digest(stage_file),
            "Domain registry not derived from currently frozen public inputs")
    require(frozen["n_providers"]==9 and frozen["v3_predictions_authorized"] is False,
            "Incorrect provider count or premature V3 authorization")
    require(all(frozen[k] is False for k in
            ("method_outcomes_used","graph_whitebox_used","final_whitebox_used")),
            "Domain freeze firewall violated")
    require(set(frozen["provider_evidence_sha256"])==
            {f"{r}/{p}" for r in ROLES for p in PROVIDERS},
            "Nine provider evidence provenance keys incomplete")
    require(setup["status"]=="B0001_M1_DOMAIN_SETUP_NO_FITS"
            and setup["stage_manifest_sha256"]==digest(stage_file),
            "M1-domain setup provenance invalid")
    require(eligible["status"]=="B0001_STEP0_ELIGIBILITY_EVIDENCE_FROZEN"
            and eligible["selected_by_role"]==WORLDS,
            "Eligibility freeze disagrees with domain inputs")
    require(stage["eligibility_freeze_sha256"]==digest(eligibility_file),
            "Stage 0 evidence hash changed")
    require(frozen["source_original_domain_audit_sha256"]==
            digest(P5/"audit_phase5_m1_reconstruction_v2.py"),
            "Original M1 domain-audit source changed")

    with registry.open(newline="",encoding="utf-8") as f:
        t=list(csv.DictReader(f))
    require(len(t)==9,"Expected nine M1 domain rows")
    observed=set()
    expansions=0
    for row in t:
        role=row["provider_world_id"]
        provider=row["provider_id"]
        require(role in ROLES and provider in PROVIDERS,"Unexpected provider identity")
        pair=(role,provider)
        require(pair not in observed,"Duplicate provider domain: "+str(pair))
        observed.add(pair)
        expected=frozen["provider_evidence_sha256"][f"{role}/{provider}"]
        require(row["provider_freeze_sha256"]==expected["freeze_sha256"] and
                row["m1_best_sha256"]==expected["m1_best_sha256"],
                "Provider evidence row hash differs: "+str(pair))
        k=int(row["final_round"])
        require(k in (0,1),"Invalid number of M1 boundary expansions")
        is_expanded=row["expanded"].lower()=="true"
        require(is_expanded==(k==1),"M1 final-round / expanded disagreement")
        expansions+=k
        for field in REQUIRED_BOUNDS:
            lo=float(row[field+"_lower"])
            hi=float(row[field+"_upper"])
            val=float(row["selected_"+field])
            require(all(math.isfinite(x) for x in (lo,hi,val)),
                    "Nonfinite provider domain: "+str(pair))
            require((lo>=0 if field=="service_cv" else lo>0)
                    and lo<hi and lo<=val<=hi,
                    f"Invalid {field} bounds or selected value for {role}/{provider}: "
                    f"{lo} <= {val} <= {hi}")
        require(float(row["cost_rate_public_reference"])>0,
                "Cost-rate public reference must be positive")
    require(observed=={(r,p) for r in ROLES for p in PROVIDERS},
            "Some provider reconstruction domains missing")
    require(expansions==frozen["n_expanded"],
            "Expansion count disagrees with frozen evidence")

    # Source contracts retain their historical scientific hyperparameters.
    sources={}
    for name in SOURCE_FILES:
        p=REPO/name
        require(p.is_file(),"Source contract not found: "+name)
        sources[name]=digest(p)
    v3=read(P5/"config_phase5_provider_reconstruction_v3.json")
    v3b=read(P5/"config_phase5_provider_reconstruction_v3b.json")
    historical_seeds=read(P5/"config_phase5_seed_registry_v3.json")
    require(v3["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3",
            "Historical V3 status changed")
    require(v3b["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3B",
            "Historical V3b status changed")
    fit=v3["candidate_reconstruction"]
    require(fit["candidate_count_per_provider"]==7 and
            fit["independent_fit_count"]==7 and
            fit["trials_per_fit"]==25 and
            fit["startup_trials_per_fit"]==5 and
            len(fit["fit_sampler_seeds"])==7 and
            len(set(fit["fit_sampler_seeds"]))==7,
            "V3 scientific fit configuration changed")
    require(v3b["selection_basis"]["ranking_metric"]=="rescore_rmse" and
            v3b["selection_basis"]["candidate_bank_per_provider"]==7,
            "V3b selection contract changed")
    require(historical_seeds["status"]=="FROZEN_PHASE5_SEED_REGISTRY_V3",
            "Original V3 seed registry changed")
    historical=historical_seeds["provider_reconstruction"]
    require(set(historical)==set(BANK_NAMES),
            "Original V3 provider reconstruction bank names changed")
    for key in BANK_NAMES:
        require(int(historical[key]["n"])==(15 if key.startswith("fit_") else 100),
                "Original V3 local seed-bank sample size changed")

    attempts={a["candidate_id"]:a for a in eligible["attempts"]}
    require(len(attempts)==4,"Original recruitment ledger incomplete")
    # Original rejected and selected I1/Step0 + all new M1 banks must be disjoint
    # from this V3 namespace. Historical Phase-5 V2/V3 original local banks
    # are also checked for conflicts.
    occupied=[]
    for att in attempts.values():
        for label,b in att["seed_blocks"].items():
            occupied.append((att["candidate_id"]+"/"+label,
                             int(b["start"]),int(b["end_inclusive"])))
    for role in ROLES:
        selected=attempts[WORLDS[role]]
        m1=setup["phases"][role]["M1_seed_banks"]
        for label,b in m1.items():
            occupied.append((role+"/M1/"+label,int(b["start"]),int(b["end_inclusive"])))
    for label,b in historical.items():
        occupied.append(("historical_V3/"+label,int(b["start"]),int(b["end_inclusive"])))
    for label,b in read(P5/"config_phase5_seed_registry_v2.json")["provider_reconstruction"].items():
        occupied.append(("historical_V2/"+label,int(b["start"]),int(b["end_inclusive"])))

    planned={}
    new_spans=[]
    for role in ROLES:
        banks=seed_ranges(attempts[WORLDS[role]],role)
        planned[role]=banks
        for label,b in banks.items():
            lo,hi=b["start"],b["end_inclusive"]
            require(hi-lo+1==b["n"],"V3 seed count incorrect")
            require(lo>=0 and hi*100+3<=2**32-1,
                    "V3 seed would overflow native 32-bit provider RNG")
            for previous,p_lo,p_hi in occupied+new_spans:
                require(hi<p_lo or lo>p_hi,
                        f"V3 {role}/{label} overlaps {previous}")
            new_spans.append((role+"/"+label,lo,hi))

    # The next stage must redirect historical runner HERE, DOMAIN_REGISTRY,
    # the public-I1 loader and every result path before executing V3.
    v3_source=(P5/"run_phase5_provider_reconstruction_v3.py").read_text()
    require("DOMAIN_REGISTRY" in v3_source and
            "load_phase5_contracts(HERE)" in v3_source and
            "_load_public_card" in v3_source,
            "Original runner path/input assumptions changed; re-audit required")
    return {
        "status":"B0001_NINE_DOMAIN_V3_PREFLIGHT_PASS_EXECUTION_BLOCKED",
        "eligible_worlds":WORLDS,
        "provider_domains_verified":9,
        "domain_expansions_verified":expansions,
        "registry_sha256":digest(registry),
        "domain_freeze_sha256":digest(domain_file),
        "staged_public_manifest_sha256":digest(stage_file),
        "reconstruction_preflight_sha256":digest(pf_file),
        "eligibility_freeze_sha256":digest(eligibility_file),
        "original_source_sha256":sources,
        "v3_fit_count_per_provider":7,
        "v3_total_fit_count":63,
        "v3_trials_per_fit":25,
        "v3_common_rescore_n":100,
        "v3_common_replay_n":100,
        "v3b_selection_metric":"rescore_rmse",
        "planned_local_seed_banks_by_world":planned,
        "seed_bank_collisions":0,
        "hidden_provider_parameters_used":False,
        "confirmation_outcomes_used":False,
        "simulations_executed":0,
        "reconstruction_execution_authorized":False,
        "prediction_execution_authorized":False,
        "next_required_gate":"separate isolated B0001 V3 reconstruction adapter, frozen manifests and no-historical-path smoke",
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging",type=Path,required=True)
    parser.add_argument("--domains",type=Path,required=True)
    parser.add_argument("--preflight",type=Path,required=True)
    parser.add_argument("--eligibility",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    staging=args.staging.expanduser().resolve()
    domains=args.domains.expanduser().resolve()
    pf=args.preflight.expanduser().resolve()
    eligibility=args.eligibility.expanduser().resolve()
    output=args.out.expanduser().resolve()
    require(not output.exists(),"Refusing to overwrite existing V3 preflight output")
    for private in (REPO,staging,domains,domains.parent,pf.parent,eligibility.parent):
        require(output!=private and private not in output.parents,
                "Audit output cannot be placed inside input or repo directory")
    result=check(staging,domains,pf,eligibility)
    output.mkdir(parents=True)
    path=output/"b0001_v3_domain_preflight.json"
    path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("B0001_NINE_DOMAIN_V3_PREFLIGHT_PASS",flush=True)
    print("PROVIDERS 9 EXPANSIONS",result["domain_expansions_verified"],flush=True)
    print("FRESH_V3_SEED_BANKS_PASS 3 worlds 9 banks per world",flush=True)
    print("V3_RECONSTRUCTION_NOT_AUTHORIZED no simulations launched",flush=True)
    print("MANIFEST",path,flush=True)


if __name__=="__main__":
    main()
