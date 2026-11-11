#!/usr/bin/env python3
"""Read-only B0001 V3/V3b provider reconstruction input preflight.

Checks staged public evidence, source compatibility and source-defined method
domains. Does not fit a model, copy hidden world parameters, or access WB.
The historical M1 V2 domain registry is intentionally NOT repurposed: the
fresh B0001 domain must be independently established before fitting.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
P5=REPO/"first_science"/"phase5"
P2=REPO/"first_science"/"phase2"
ROLES=("P1","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
CANONICAL_QUERY_COLS=("query_id","provider_world_id","graph_id","rho_label",
 "rho","regime","scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status")
SOURCE_FILES=(
 "first_science/phase5/run_phase5_provider_reconstruction_v3.py",
 "first_science/phase5/run_phase5_m2_reconstruction_v2.py",
 "first_science/phase5/run_phase5_m1_reconstruction_v2.py",
 "first_science/phase5/config_phase5_provider_reconstruction_v3.json",
 "first_science/phase5/config_phase5_provider_reconstruction_v3b.json",
 "first_science/phase5/config_phase5_seed_registry_v3.json",
 "first_science/phase5/phase5_reconstruction_v3_selection.py",
)


def require(predicate,message):
    if not predicate:
        raise RuntimeError(message)


def digest(path):
    hasher=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            hasher.update(block)
    return hasher.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def analyze(staging):
    staging=staging.expanduser().resolve()
    manifest_file=staging/"b0001_public_inputs_manifest.json"
    m=read(manifest_file)
    require(m["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE",
            "B0001 public staging status invalid")
    require(m["selected_worlds"]=={
        "P1":"B0001_P1_A02","P3":"B0001_P3_A01","P4":"B0001_P4_A01"},
        "Unexpected selected worlds")
    require(m["prediction_execution_authorized"] is False and
            m["hidden_world_parameters_copied"] is False and
            m["calibration_or_confirmation_values_copied"] is False,
            "Staging privacy or execution gate invalid")
    require(m["cells"]==12 and m["queries_per_cell"]==15,
            "Stage evidence incomplete")
    entries=m["staged_files"]
    bypath={x["path"]:x for x in entries}
    require(len(bypath)==len(entries)==30,
            "Expected 18 provider files and 12 frozen query definitions")
    for entry in entries:
        name=entry["path"]
        require(".." not in Path(name).parts and not Path(name).is_absolute(),
                "Unsafe staging manifest relative path")
        path=staging/name
        require(path.is_file() and digest(path)==entry["staged_sha256"],
                "Staged input drift or missing file: "+name)

    sys.path.insert(0,str(P2))
    from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
    provider_rows=[]
    for role in ROLES:
        for provider in PROVIDERS:
            directory=staging/"public_I1"/role/provider
            metadata,surface=load_rho_conditioned_i1_provider_card(directory)
            require(metadata["provider_id"]==provider,
                    "Provider-card identity mismatch: "+str(directory))
            require(len(surface)>0 and surface["sigma_hat"].notna().all(),
                    "Provider-card missing sigma values: "+str(directory))
            require(surface["sigma_hat"].between(0,1).all(),
                    "Provider-card sigma out of probability bounds")
            require(set(surface["provider_id"])=={provider},
                    "Surface provider-id mismatch")
            provider_rows.append({
                "world_role":role,"provider":provider,
                "card_sha256":digest(directory/"card.json"),
                "surface_sha256":digest(directory/"sigma_surface.csv"),
                "surface_rows":int(len(surface)),
                "n_region_rho":int(surface["region_rho"].nunique()),
                "n_query_rho":int(surface["rho"].nunique()),
                "n_horizons":int(surface["horizon"].nunique()),
            })
    for role in ROLES:
        for graph in GRAPHS:
            p=staging/"frozen_queries"/f"{role}__{graph}"/"step0_frozen_queries.csv"
            q=pd.read_csv(p)
            require(len(q.columns)==len(CANONICAL_QUERY_COLS) and
                    set(q.columns)==set(CANONICAL_QUERY_COLS),
                    "Query input columns differ from original predictor")
            require(len(q)==15 and q.query_id.is_unique,
                    "Query cardinality/uniqueness invalid")
            require(set(q.provider_world_id)=={role} and set(q.graph_id)=={graph},
                    "Query cell identity mismatch")
            require(set(q.step0_cell_status)=={"FROZEN_PHASE5_STEP0_PASS_V2"},
                    "Step-0-failed query in public prediction stage")
    origins={}
    for rel in SOURCE_FILES:
        p=REPO/rel
        require(p.is_file(),"Missing original scientific source: "+rel)
        origins[rel]=digest(p)
    v3=read(P5/"config_phase5_provider_reconstruction_v3.json")
    v3b=read(P5/"config_phase5_provider_reconstruction_v3b.json")
    require(v3["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3",
            "V3 contract drift")
    require(v3b["status"]=="FROZEN_PHASE5_PROVIDER_RECONSTRUCTION_V3B",
            "V3b contract drift")
    require(v3["candidate_reconstruction"]["candidate_count_per_provider"]==7,
            "V3 no longer constructs seven per provider")
    require(v3b["selection_basis"]["candidate_bank_per_provider"]==7
            and v3b["selection_basis"]["ranking_metric"]=="rescore_rmse",
            "V3b RMSE ranking changed")
    # Check that our candidate-domain dependencies are still the exact
    # historical ones. No physical parameters or historical registry rows
    # are imported as B0001 fits.
    v3source=(P5/"run_phase5_provider_reconstruction_v3.py").read_text()
    m2source=(P5/"run_phase5_m2_reconstruction_v2.py").read_text()
    require("domain_row=_domain_row(world,provider)" in v3source and
            "bounds=_bounds(domain_row)" in v3source,
            "V3 domain registry dependence changed: manually re-audit")
    require('DOMAIN_REGISTRY=DEFAULT_ROOT/"phase5_m1_domain_registry.csv"' in m2source,
            "V2 domain registry path changed: manually re-audit")
    return {
        "status":"B0001_V3_RECONSTRUCTION_PUBLIC_COMPATIBILITY_PASS_DOMAIN_PENDING",
        "staged_manifest_sha256":digest(manifest_file),
        "source_sha256":origins,
        "provider_card_checks":provider_rows,
        "provider_cards_verified":len(provider_rows),
        "query_cells_verified":12,
        "v3_candidate_count_per_provider":7,
        "v3b_ranking_metric":"rescore_rmse",
        "domain_registry_status":"NOT_ESTABLISHED_FOR_NEW_WORLDS",
        "blocker":"Original V3 depends on a V2 M1-derived domain registry. A new-world domain registry must be generated under the original M1 V2 domain audit rules, without copying historical provider rows.",
        "simulations_generated":0,
        "prediction_execution_authorized":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--staging",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    out=a.out.expanduser().resolve()
    require(not out.exists(),"Refusing to overwrite reconstruction preflight result")
    require(out != REPO and REPO not in out.parents,
            "Output must be outside source repository")
    require(out != a.staging.expanduser().resolve() and
            a.staging.expanduser().resolve() not in out.parents,
            "Output may not modify immutable public staging")
    result=analyze(a.staging)
    out.mkdir(parents=True)
    target=out/"b0001_v3_reconstruction_preflight.json"
    target.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("B0001_V3_PUBLIC_COMPATIBILITY_PASS",len(result["provider_card_checks"]),"cards 12 cells")
    print("B0001_RECONSTRUCTION_DOMAIN_PENDING no simulations run")
    print("OUTPUT",target)


if __name__=="__main__":
    main()
