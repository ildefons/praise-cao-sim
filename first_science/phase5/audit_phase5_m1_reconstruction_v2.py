"""Audit and freeze the Phase-5 V2 M1 reconstruction domains.

M2 is defined on each provider's *final declared M1 domain after any permitted
public-I1-only one-round expansion*.  This script derives that domain registry
mechanically from the already-frozen M1 provider artifacts.  It does not rerun
M1, read Step-0 WB values, or inspect graph/final-WB evidence.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase5_runtime_v2 import (
    base_manifest,
    canonical_provider_world_ids,
    inclusive_seed_range,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

HERE=Path(__file__).resolve().parent
DEFAULT_ROOT=HERE/"results"/"03_reconstruction"
PROVIDERS=("ProviderA","ProviderB","ProviderC")


def _expected_seed_record(contracts):
    r=contracts.seeds["provider_reconstruction"]
    out={}
    for key in (
        "M1_M2_local_search_CRN",
        "M1_M2_local_confirmation_CRN",
        "M1_M2_local_replay_CRN",
    ):
        s=inclusive_seed_range(r[key])
        out[key]=(s[0],s[-1],len(s))
    return out


def audit(root:Path)->pd.DataFrame:
    contracts=load_phase5_contracts(HERE)
    expected_seeds=_expected_seed_record(contracts)
    rows=[]
    for world in canonical_provider_world_ids(contracts):
        world_manifest_path=root/world/"m1"/"m1_world_freeze_manifest.json"
        if not world_manifest_path.is_file():
            raise FileNotFoundError(world_manifest_path)
        wm=read_json(world_manifest_path)
        if wm.get("status")!="FROZEN_PHASE5_M1_WORLD_V2":
            raise RuntimeError(f"{world}: M1 world not fully instantiable/frozen")

        for provider in PROVIDERS:
            pdir=root/world/"m1"/provider
            freeze_path=pdir/"m1_provider_freeze.json"
            summary_path=pdir/"m1_final_parameters.json"
            if not freeze_path.is_file() or not summary_path.is_file():
                raise FileNotFoundError(f"{world}/{provider}: missing M1 freeze artifacts")
            freeze=read_json(freeze_path)
            summary=read_json(summary_path)
            if freeze.get("status")!="FROZEN_PHASE5_M1_PROVIDER_V2":
                raise RuntimeError(f"{world}/{provider}: M1 is not instantiable")
            if summary.get("status")!="FROZEN_PHASE5_M1_PROVIDER_V2":
                raise RuntimeError(f"{world}/{provider}: M1 summary/freeze disagreement")
            if not bool(summary.get("instantiable")):
                raise RuntimeError(f"{world}/{provider}: instantiable flag false")
            if summary.get("unresolved_boundary_reasons"):
                raise RuntimeError(f"{world}/{provider}: unresolved boundary remains")
            if bool(summary.get("graph_whitebox_used")) or bool(summary.get("step0_whitebox_outcomes_used")):
                raise RuntimeError(f"{world}/{provider}: firewall violation in summary")

            for key,expected in (
                ("battery_config_sha256",contracts.hashes["battery"]),
                ("seed_registry_sha256",contracts.hashes["seeds"]),
                ("method_contract_sha256",contracts.hashes["methods"]),
                ("analysis_contract_sha256",contracts.hashes["analysis"]),
                ("execution_contract_sha256",contracts.hashes["execution"]),
            ):
                if freeze.get(key)!=expected:
                    raise RuntimeError(f"{world}/{provider}: {key} mismatch")
            if bool(freeze["inputs"].get("hidden_provider_parameters_used")):
                raise RuntimeError(f"{world}/{provider}: hidden parameters used")
            if bool(freeze["inputs"].get("step0_WB_values_used")):
                raise RuntimeError(f"{world}/{provider}: Step-0 WB used in M1")
            if bool(freeze["inputs"].get("graph_WB_used")):
                raise RuntimeError(f"{world}/{provider}: graph WB used in M1")

            observed={
                "M1_M2_local_search_CRN":(
                    int(freeze["seed_banks"]["local_search"]["start"]),
                    int(freeze["seed_banks"]["local_search"]["end_inclusive"]),
                    int(freeze["seed_banks"]["local_search"]["n"]),
                ),
                "M1_M2_local_confirmation_CRN":(
                    int(freeze["seed_banks"]["local_confirmation"]["start"]),
                    int(freeze["seed_banks"]["local_confirmation"]["end_inclusive"]),
                    int(freeze["seed_banks"]["local_confirmation"]["n"]),
                ),
                "M1_M2_local_replay_CRN":(
                    int(freeze["seed_banks"]["local_replay"]["start"]),
                    int(freeze["seed_banks"]["local_replay"]["end_inclusive"]),
                    int(freeze["seed_banks"]["local_replay"]["n"]),
                ),
            }
            if observed!=expected_seeds:
                raise RuntimeError(f"{world}/{provider}: M1 seed-bank mismatch")

            final_round=int(summary["final_round"])
            if final_round not in (0,1):
                raise RuntimeError(f"{world}/{provider}: invalid final round {final_round}")
            result_dir=pdir/("round0" if final_round==0 else "round1_expanded")
            best_path=result_dir/"m1_v2_best.json"
            if not best_path.is_file():
                raise FileNotFoundError(best_path)
            best=read_json(best_path)
            bounds=dict(best["optimizer"]["search_bounds"])
            params=dict(summary["parameters"])

            # Final parameters must lie inside the exact final domain.
            values={
                "mean_service_time":float(params["mean_service_time"]),
                "cost_rate":float(params["cost_rate"]),
                "service_cv":float(params["service_cv"]),
            }
            checks=(
                ("mean_service_time","mean_service_time_lower","mean_service_time_upper"),
                ("cost_rate","cost_rate_lower","cost_rate_upper"),
                ("service_cv","service_cv_lower","service_cv_upper"),
            )
            for field,lo_key,hi_key in checks:
                x=values[field]; lo=float(bounds[lo_key]); hi=float(bounds[hi_key])
                if not (lo<=x<=hi):
                    raise RuntimeError(
                        f"{world}/{provider}: final {field}={x} outside [{lo},{hi}]"
                    )

            rows.append({
                "provider_world_id":world,
                "provider_id":provider,
                "final_round":final_round,
                "expanded":bool(final_round==1),
                "initial_boundary_hits":str(summary.get("initial_boundary_hits",{})),
                "one_round_expansion":str(summary.get("one_round_expansion")),
                "mean_service_time_lower":float(bounds["mean_service_time_lower"]),
                "mean_service_time_upper":float(bounds["mean_service_time_upper"]),
                "cost_rate_lower":float(bounds["cost_rate_lower"]),
                "cost_rate_upper":float(bounds["cost_rate_upper"]),
                "service_cv_lower":float(bounds["service_cv_lower"]),
                "service_cv_upper":float(bounds["service_cv_upper"]),
                "cost_rate_public_reference":float(bounds["cost_rate_public_reference"]),
                "selected_mean_service_time":values["mean_service_time"],
                "selected_cost_rate":values["cost_rate"],
                "selected_service_cv":values["service_cv"],
                "provider_freeze_sha256":sha256_file(freeze_path),
                "m1_best_sha256":sha256_file(best_path),
            })
    frame=pd.DataFrame(rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    if len(frame)!=12:
        raise RuntimeError(f"M1 domain registry expected 12 providers, found {len(frame)}")
    return frame


def main()->None:
    p=argparse.ArgumentParser(description="Audit/freeze Phase-5 M1 domain registry")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    root=args.root.resolve()
    frame=audit(root)
    registry_path=root/"phase5_m1_domain_registry.csv"
    frame.to_csv(registry_path,index=False)

    contracts=load_phase5_contracts(HERE)
    manifest_path=root/"phase5_m1_reconstruction_audit_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status="FROZEN_PHASE5_M1_RECONSTRUCTION_AUDIT_V2",
        inputs={
            "domain_semantics":"final declared M1 domain after at most one permitted public-I1-only expansion",
            "graph_whitebox_used":False,
            "step0_WB_values_used":False,
        },
        seed_banks={},
        outputs={"m1_domain_registry":str(registry_path)},
        started_utc=utc_now_iso(),
    )
    manifest["n_provider_reconstructions"]=int(len(frame))
    manifest["n_expanded"]=int(frame["expanded"].sum())
    manifest["expanded_provider_worlds"]=[
        f"{r.provider_world_id}/{r.provider_id}"
        for r in frame[frame["expanded"]].itertuples(index=False)
    ]
    write_json(manifest_path,manifest)

    print("PHASE5_M1_RECONSTRUCTION_AUDIT_PASS")
    print(frame[[
        "provider_world_id","provider_id","final_round","expanded",
        "selected_mean_service_time","selected_cost_rate","selected_service_cv"
    ]].to_string(index=False))
    print(f"providers={len(frame)} expanded={int(frame['expanded'].sum())}")
    print(f"registry={registry_path}")
    print(f"manifest={manifest_path}")


if __name__=="__main__":
    main()
