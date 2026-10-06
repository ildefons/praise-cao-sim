"""Read-only Phase-5 secondary M2-RMSE15 compatibility audit.

Reclassifies the already generated primary-M2 candidate observations under the
frozen secondary rule RMSE_candidate <= 1.15 * RMSE_reference, equivalently
MSE_candidate <= 1.3225 * MSE_reference.

No TPE/LHS/GP candidate is generated. No local simulation is run. No graph
prediction or white-box artifact is read. The audit freezes the five-member
provisional portfolio implied by the new search criterion when possible and
reports exactly which selected candidates already have N=100 confirmation
evidence versus which would require confirmation in the next stage.
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
from run_phase5_m2_reconstruction_v2 import _provisional

HERE=Path(__file__).resolve().parent
PRIMARY_ROOT=HERE/"results"/"03_reconstruction"
CONTRACT=HERE/"config_phase5_m2_rmse15_secondary_v1.json"
DEFAULT_OUTPUT=PRIMARY_ROOT/"m2_rmse15_secondary_audit"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED="FROZEN_PHASE5_M2_RMSE15_SECONDARY_V1"
TOL=1e-12


def _read_optional_csv(path:Path)->pd.DataFrame:
    if not path.is_file() or path.stat().st_size<=1:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def audit(output:Path)->tuple[pd.DataFrame,pd.DataFrame]:
    contracts=load_phase5_contracts(HERE)
    cfg=read_json(CONTRACT)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected M2-RMSE15 contract status")
    ratio=float(cfg["closeness_definition"]["equivalent_mse_ratio_max"])
    if abs(ratio-1.3225)>1e-12:
        raise RuntimeError("M2-RMSE15 MSE ratio is not frozen at 1.3225")

    summaries=[]
    selected_rows=[]

    for world in canonical_provider_world_ids(contracts):
        for provider in PROVIDERS:
            pdir=PRIMARY_ROOT/world/"m2"/provider
            primary_manifest_path=pdir/"m2_provider_freeze.json"
            if not primary_manifest_path.is_file():
                raise FileNotFoundError(primary_manifest_path)
            primary=read_json(primary_manifest_path)

            warm_path=pdir/"m2_gp_warm_start.csv"
            gp_path=pdir/"m2_gp_acquisitions.csv"
            if not warm_path.is_file() or not gp_path.is_file():
                raise FileNotFoundError(f"{world}/{provider}: missing frozen M2 search observations")
            warm=pd.read_csv(warm_path)
            gp=pd.read_csv(gp_path)

            best_m1_search=float(primary["best_m1_search_mse"])
            search_ceiling=ratio*best_m1_search

            gp_cols=[
                "provider","candidate_id","source_stage",
                "z_log_mu","z_log_kappa","z_cv",
                "mean_service_time","cost_rate","service_cv","local_mse",
            ]
            observed=pd.concat([warm[gp_cols],gp[gp_cols]],ignore_index=True)
            observed=observed.drop_duplicates("candidate_id",keep="last").reset_index(drop=True)
            compatible=observed[
                observed["local_mse"].astype(float)<=search_ceiling+TOL
            ].copy().sort_values(["local_mse","candidate_id"],kind="mergesort")

            provisional=_provisional(
                warm,gp,ceiling=search_ceiling,k=5
            )
            provisional_possible=len(provisional)==5

            m1_summary_path=PRIMARY_ROOT/world/"m1"/provider/"m1_final_parameters.json"
            m1_summary=read_json(m1_summary_path)
            confirm_reference=float(m1_summary["confirmation_metrics"]["mse"])
            confirm_ceiling=ratio*confirm_reference

            existing_conf=_read_optional_csv(pdir/"m2_confirmation_results.csv")
            conf_by_id={}
            if not existing_conf.empty and "candidate_id" in existing_conf.columns:
                conf_by_id={
                    str(r.candidate_id):float(r.confirmation_mse)
                    for r in existing_conf.itertuples(index=False)
                }

            known_pass=0
            known_fail=0
            missing=0
            selected_ids=[]
            if provisional_possible:
                for rec in provisional.sort_values("selection_order").to_dict("records"):
                    cid=str(rec["candidate_id"])
                    selected_ids.append(cid)
                    if cid in conf_by_id:
                        cmse=float(conf_by_id[cid])
                        cstatus=bool(cmse<=confirm_ceiling+TOL)
                        if cstatus:
                            known_pass+=1
                        else:
                            known_fail+=1
                    else:
                        cmse=None
                        cstatus=None
                        missing+=1

                    selected_rows.append({
                        "provider_world_id":world,
                        "provider_id":provider,
                        "selection_order":int(rec["selection_order"]),
                        "candidate_id":cid,
                        "source_stage":str(rec["source_stage"]),
                        "local_mse":float(rec["local_mse"]),
                        "search_reference_mse":best_m1_search,
                        "search_mse_ceiling_rmse15":search_ceiling,
                        "search_mse_ratio":float(rec["local_mse"])/best_m1_search,
                        "existing_confirmation_available":cid in conf_by_id,
                        "confirmation_mse":cmse,
                        "confirmation_reference_mse":confirm_reference,
                        "confirmation_mse_ceiling_rmse15":confirm_ceiling,
                        "confirmation_mse_ratio":None if cmse is None else cmse/confirm_reference,
                        "confirmation_pass_rmse15":cstatus,
                    })

            summaries.append({
                "provider_world_id":world,
                "provider_id":provider,
                "primary_m2_status":str(primary.get("status")),
                "n_observed_candidates":int(len(observed)),
                "primary_search_mse_ratio":1.25,
                "rmse15_search_mse_ratio":ratio,
                "best_m1_search_mse_reference":best_m1_search,
                "rmse15_search_mse_ceiling":search_ceiling,
                "n_search_compatible_primary_recorded":int(
                    (
                        observed["local_mse"].astype(float)
                        <=float(primary["search_compatibility_mse_ceiling"])+TOL
                    ).sum()
                ),
                "n_search_compatible_rmse15":int(len(compatible)),
                "provisional5_possible_rmse15":bool(provisional_possible),
                "selected_candidate_ids":";".join(selected_ids),
                "confirmation_reference_mse":confirm_reference,
                "rmse15_confirmation_mse_ceiling":confirm_ceiling,
                "selected_with_existing_confirmation":int(known_pass+known_fail),
                "selected_confirmation_pass_known":int(known_pass),
                "selected_confirmation_fail_known":int(known_fail),
                "selected_confirmation_missing":int(missing),
                "can_already_freeze_3_from_existing_confirmation":bool(
                    provisional_possible and known_pass>=3
                ),
            })

    summary=pd.DataFrame(summaries).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    selected=pd.DataFrame(selected_rows)
    if not selected.empty:
        selected=selected.sort_values(
            ["provider_world_id","provider_id","selection_order"],kind="mergesort"
        ).reset_index(drop=True)

    output.mkdir(parents=True,exist_ok=True)
    summary_path=output/"m2_rmse15_search_and_confirmation_audit.csv"
    selected_path=output/"m2_rmse15_provisional5_candidates.csv"
    summary.to_csv(summary_path,index=False)
    selected.to_csv(selected_path,index=False)

    manifest_path=output/"m2_rmse15_secondary_audit_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status="FROZEN_PHASE5_M2_RMSE15_SECONDARY_AUDIT_V1",
        inputs={
            "secondary_contract_sha256":sha256_file(CONTRACT),
            "read_only_reclassification":True,
            "new_candidate_generation":False,
            "new_simulation":False,
            "graph_prediction_read":False,
            "graph_whitebox_read":False,
            "final_whitebox_read":False,
            "rmse_ratio_max":1.15,
            "equivalent_mse_ratio_max":ratio,
        },
        seed_banks={},
        outputs={
            "provider_summary":str(summary_path),
            "provisional5_candidates":str(selected_path),
        },
        started_utc=utc_now_iso(),
    )
    write_json(manifest_path,manifest)
    return summary,selected


def main()->None:
    p=argparse.ArgumentParser(description="Audit secondary Phase-5 M2-RMSE15 compatibility")
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    args=p.parse_args()
    summary,selected=audit(args.output.resolve())

    print("PHASE5_M2_RMSE15_SECONDARY_AUDIT_PASS")
    print("\nRMSE15_PROVIDER_SUMMARY")
    print(summary[[
        "provider_world_id","provider_id",
        "n_search_compatible_primary_recorded",
        "n_search_compatible_rmse15",
        "provisional5_possible_rmse15",
        "selected_with_existing_confirmation",
        "selected_confirmation_pass_known",
        "selected_confirmation_fail_known",
        "selected_confirmation_missing",
        "can_already_freeze_3_from_existing_confirmation",
    ]].to_string(index=False))

    unresolved=summary[
        summary["provisional5_possible_rmse15"].astype(bool)
        & (
            summary["selected_confirmation_missing"].astype(int)>0
        )
    ]
    if not unresolved.empty:
        print("\nRMSE15_CONFIRMATION_WORK_REQUIRED")
        print(unresolved[[
            "provider_world_id","provider_id",
            "n_search_compatible_rmse15",
            "selected_with_existing_confirmation",
            "selected_confirmation_missing",
        ]].to_string(index=False))

    still_search_failed=summary[
        ~summary["provisional5_possible_rmse15"].astype(bool)
    ]
    if not still_search_failed.empty:
        print("\nRMSE15_STILL_SEARCH_NOT_INSTANTIABLE")
        print(still_search_failed[[
            "provider_world_id","provider_id",
            "n_search_compatible_rmse15"
        ]].to_string(index=False))

    print(f"\noutput={args.output.resolve()}")


if __name__=="__main__":
    main()
