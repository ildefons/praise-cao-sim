"""Read-only detailed diagnosis of Phase-5 V2 M2 local gates.

Clarifies two distinct failure modes without changing any frozen scientific
outcome:
  1) fewer than five search-compatible observed candidates, so no provisional
     portfolio can be formed;
  2) five provisional candidates exist but fewer than three pass confirmation.

The official runner writes n_provisional_members=0 when mode (1) occurs because
it returns an empty provisional table whenever the compatible observed set has
size <5.  This audit therefore reports the *actual* compatible-observation
count separately.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase5_runtime_v2 import (
    base_manifest,
    canonical_provider_world_ids,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

HERE=Path(__file__).resolve().parent
DEFAULT_ROOT=HERE/"results"/"03_reconstruction"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
PASS="FROZEN_PHASE5_M2_PROVIDER_V2"
FAIL="FROZEN_PHASE5_M2_PROVIDER_NOT_INSTANTIABLE_V2"
TOL=1e-12


def _observed_table(root:Path)->pd.DataFrame:
    warm=pd.read_csv(root/"m2_gp_warm_start.csv")
    gp=pd.read_csv(root/"m2_gp_acquisitions.csv")
    gp_cols=[
        "provider","candidate_id","source_stage",
        "z_log_mu","z_log_kappa","z_cv",
        "mean_service_time","cost_rate","service_cv","local_mse",
    ]
    missing=[c for c in gp_cols if c not in gp.columns]
    if missing:
        raise RuntimeError(f"{root}: GP acquisitions missing {missing}")
    observed=pd.concat([warm[gp_cols],gp[gp_cols]],ignore_index=True)
    return observed.drop_duplicates("candidate_id",keep="last").reset_index(drop=True)


def audit(root:Path)->tuple[pd.DataFrame,pd.DataFrame]:
    contracts=load_phase5_contracts(HERE)
    summaries=[]
    details=[]
    for world in canonical_provider_world_ids(contracts):
        for provider in PROVIDERS:
            pdir=root/world/"m2"/provider
            manifest_path=pdir/"m2_provider_freeze.json"
            if not manifest_path.is_file():
                raise FileNotFoundError(manifest_path)
            m=read_json(manifest_path)
            status=str(m.get("status"))
            if status not in (PASS,FAIL):
                raise RuntimeError(f"{world}/{provider}: unexpected status {status}")
            ceiling=float(m["search_compatibility_mse_ceiling"])
            observed=_observed_table(pdir)
            compatible=observed[
                observed["local_mse"].astype(float)<=ceiling+TOL
            ].copy().sort_values(["local_mse","candidate_id"],kind="mergesort")
            source_counts=compatible.groupby("source_stage").size().to_dict()

            prov_path=pdir/"m2_provisional_portfolio.csv"
            provisional=(
                pd.read_csv(prov_path)
                if prov_path.is_file() and prov_path.stat().st_size>1
                else pd.DataFrame()
            )
            conf_path=pdir/"m2_confirmation_results.csv"
            confirmation=(
                pd.read_csv(conf_path)
                if conf_path.is_file() and conf_path.stat().st_size>1
                else pd.DataFrame()
            )

            confirmation_pass=None
            confirmation_total=None
            confirmation_reference=None
            confirmation_ceiling=None
            if not confirmation.empty:
                confirmation_total=len(confirmation)
                if "confirmation_compatible" in confirmation.columns:
                    confirmation_pass=int(
                        confirmation["confirmation_compatible"].astype(bool).sum()
                    )
                if "m1_frozen_confirmation_mse_reference" in confirmation.columns:
                    confirmation_reference=float(
                        confirmation["m1_frozen_confirmation_mse_reference"].iloc[0]
                    )
                if "confirmation_mse_ceiling" in confirmation.columns:
                    confirmation_ceiling=float(
                        confirmation["confirmation_mse_ceiling"].iloc[0]
                    )
                for r in confirmation.itertuples(index=False):
                    details.append({
                        "provider_world_id":world,
                        "provider_id":provider,
                        "stage":"confirmation",
                        "candidate_id":str(r.candidate_id),
                        "source_stage":str(r.source_stage),
                        "selection_order":int(r.selection_order),
                        "mse":float(r.confirmation_mse),
                        "ceiling":float(r.confirmation_mse_ceiling),
                        "ratio_to_ceiling":float(r.confirmation_mse)/float(r.confirmation_mse_ceiling),
                        "compatible":bool(r.confirmation_compatible),
                    })

            for r in compatible.itertuples(index=False):
                details.append({
                    "provider_world_id":world,
                    "provider_id":provider,
                    "stage":"search_compatible",
                    "candidate_id":str(r.candidate_id),
                    "source_stage":str(r.source_stage),
                    "selection_order":None,
                    "mse":float(r.local_mse),
                    "ceiling":ceiling,
                    "ratio_to_ceiling":float(r.local_mse)/ceiling,
                    "compatible":True,
                })

            summaries.append({
                "provider_world_id":world,
                "provider_id":provider,
                "status":status,
                "n_observed_total":int(len(observed)),
                "search_compatibility_mse_ceiling":ceiling,
                "n_search_compatible_actual":int(len(compatible)),
                "compatible_TPE_R0":int(source_counts.get("TPE_R0",0)),
                "compatible_TPE_R1":int(source_counts.get("TPE_R1",0)),
                "compatible_LHS":int(source_counts.get("LHS",0)),
                "compatible_GP_LSE":int(source_counts.get("GP_LSE",0)),
                "n_provisional_members":int(len(provisional)),
                "confirmation_pass":confirmation_pass,
                "confirmation_total":confirmation_total,
                "confirmation_reference_mse":confirmation_reference,
                "confirmation_ceiling":confirmation_ceiling,
                "failure_reasons":" | ".join(str(x) for x in m.get("failure_reasons",[])),
            })
    return (
        pd.DataFrame(summaries).sort_values(
            ["provider_world_id","provider_id"],kind="mergesort"
        ).reset_index(drop=True),
        pd.DataFrame(details),
    )


def main()->None:
    p=argparse.ArgumentParser(description="Detailed read-only Phase-5 M2 gate audit")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    root=args.root.resolve()
    summary,details=audit(root)

    summary_path=root/"phase5_m2_gate_diagnostics.csv"
    details_path=root/"phase5_m2_gate_diagnostic_candidates.csv"
    summary.to_csv(summary_path,index=False)
    details.to_csv(details_path,index=False)

    contracts=load_phase5_contracts(HERE)
    manifest_path=root/"phase5_m2_gate_diagnostics_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status="FROZEN_PHASE5_M2_GATE_DIAGNOSTICS_V2",
        inputs={
            "read_only":True,
            "changes_scientific_outcome":False,
            "clarification":"n_provisional_members=0 means the compatible observed set had fewer than five members, not necessarily zero",
        },
        seed_banks={},
        outputs={
            "gate_summary":str(summary_path),
            "candidate_details":str(details_path),
        },
        started_utc=utc_now_iso(),
    )
    write_json(manifest_path,manifest)

    print("PHASE5_M2_GATE_DIAGNOSTICS_PASS")
    print(summary[[
        "provider_world_id","provider_id","status",
        "n_observed_total","n_search_compatible_actual",
        "compatible_TPE_R0","compatible_TPE_R1",
        "compatible_LHS","compatible_GP_LSE",
        "n_provisional_members","confirmation_pass","confirmation_total"
    ]].to_string(index=False))

    failed_search=summary[
        summary["n_search_compatible_actual"].astype(int)<5
    ]
    if not failed_search.empty:
        print("\nSEARCH_GATE_FAILURES_ACTUAL_COUNTS")
        print(failed_search[[
            "provider_world_id","provider_id",
            "n_search_compatible_actual",
            "search_compatibility_mse_ceiling",
            "failure_reasons"
        ]].to_string(index=False))

    conf=summary[
        summary["confirmation_total"].notna()
        & (summary["confirmation_pass"].fillna(99).astype(int)<3)
    ]
    if not conf.empty:
        print("\nCONFIRMATION_GATE_FAILURES")
        print(conf[[
            "provider_world_id","provider_id",
            "confirmation_pass","confirmation_total",
            "confirmation_reference_mse","confirmation_ceiling",
            "failure_reasons"
        ]].to_string(index=False))
        for r in conf.itertuples(index=False):
            d=details[
                (details["provider_world_id"]==r.provider_world_id)
                & (details["provider_id"]==r.provider_id)
                & (details["stage"]=="confirmation")
            ].sort_values("selection_order")
            print(f"\n{r.provider_world_id}/{r.provider_id} confirmation candidates")
            print(d[[
                "selection_order","candidate_id","source_stage",
                "mse","ceiling","ratio_to_ceiling","compatible"
            ]].to_string(index=False))

    print(f"summary={summary_path}")
    print(f"details={details_path}")
    print(f"manifest={manifest_path}")


if __name__=="__main__":
    main()
