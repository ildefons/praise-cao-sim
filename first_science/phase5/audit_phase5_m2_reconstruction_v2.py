"""Read-only audit of Phase-5 V2 M2 reconstruction status.

The audit verifies all 12 provider-level M2 freeze manifests, preserves
NOT_INSTANTIABLE outcomes, and derives where the complete 3x3x3 M2 portfolio
can be propagated.  It never reruns M2 and never repairs or relaxes a gate.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase5_runtime_v2 import (
    base_manifest,
    canonical_graph_ids,
    canonical_provider_world_ids,
    load_phase5_contracts,
    physical_cell_id,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

HERE=Path(__file__).resolve().parent
DEFAULT_ROOT=HERE/"results"/"03_reconstruction"
STEP0_MANIFEST=HERE/"results"/"02_step0"/"phase5_step0_eligibility_manifest.json"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
PASS="FROZEN_PHASE5_M2_PROVIDER_V2"
FAIL="FROZEN_PHASE5_M2_PROVIDER_NOT_INSTANTIABLE_V2"


def audit(root:Path)->tuple[pd.DataFrame,pd.DataFrame]:
    contracts=load_phase5_contracts(HERE)
    rows=[]
    for world in canonical_provider_world_ids(contracts):
        for provider in PROVIDERS:
            path=root/world/"m2"/provider/"m2_provider_freeze.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            m=read_json(path)
            status=str(m.get("status"))
            if status not in (PASS,FAIL):
                raise RuntimeError(f"{world}/{provider}: unexpected M2 status {status!r}")
            for key,expected in (
                ("battery_config_sha256",contracts.hashes["battery"]),
                ("seed_registry_sha256",contracts.hashes["seeds"]),
                ("method_contract_sha256",contracts.hashes["methods"]),
                ("analysis_contract_sha256",contracts.hashes["analysis"]),
                ("execution_contract_sha256",contracts.hashes["execution"]),
            ):
                if m.get(key)!=expected:
                    raise RuntimeError(f"{world}/{provider}: {key} mismatch")
            inputs=dict(m.get("inputs",{}))
            for forbidden in (
                "graph_whitebox_used",
                "step0_WB_values_used",
                "hidden_provider_parameters_used",
                "ppg_mechanism_used",
            ):
                if bool(inputs.get(forbidden)):
                    raise RuntimeError(f"{world}/{provider}: firewall violation {forbidden}")

            final_path=root/world/"m2"/provider/"m2_final_portfolio.csv"
            n_final=int(m.get("n_final_members",0))
            if status==PASS:
                if n_final!=3:
                    raise RuntimeError(f"{world}/{provider}: PASS but n_final={n_final}")
                if not final_path.is_file() or len(pd.read_csv(final_path))!=3:
                    raise RuntimeError(f"{world}/{provider}: frozen final portfolio is not 3 rows")
            else:
                if n_final>=3:
                    raise RuntimeError(f"{world}/{provider}: NOT_INSTANTIABLE but n_final={n_final}")

            rows.append({
                "provider_world_id":world,
                "provider_id":provider,
                "status":status,
                "instantiable":status==PASS,
                "n_m1_tpe_warm_points":int(m.get("n_m1_tpe_warm_points",0)),
                "n_lhs_points":int(m.get("n_lhs_points",0)),
                "n_gp_evaluations":int(m.get("n_gp_evaluations",0)),
                "n_provisional_members":int(m.get("n_provisional_members",0)),
                "n_final_members":n_final,
                "failure_reasons":" | ".join(str(x) for x in m.get("failure_reasons",[])),
                "manifest_sha256":sha256_file(path),
            })
    providers=pd.DataFrame(rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    if len(providers)!=12:
        raise RuntimeError("M2 audit expected 12 provider rows")

    if not STEP0_MANIFEST.is_file():
        raise FileNotFoundError(STEP0_MANIFEST)
    step0=read_json(STEP0_MANIFEST)
    eligible=set(str(x) for x in step0["eligible_cells"])
    failed=set(str(x) for x in step0["gate_failed_step0_cells"])

    world_rows=[]
    for world in canonical_provider_world_ids(contracts):
        w=providers[providers["provider_world_id"]==world]
        provider_ok=bool(w["instantiable"].all())
        failed_providers=w.loc[~w["instantiable"],"provider_id"].astype(str).tolist()
        for graph in canonical_graph_ids(contracts):
            cell=physical_cell_id(world,graph)
            if cell in failed:
                cell_status="GATE_FAILED_STEP0"
                m2_graph_allowed=False
            elif cell in eligible and provider_ok:
                cell_status="M2_GRAPH_PREDICTION_ELIGIBLE"
                m2_graph_allowed=True
            elif cell in eligible:
                cell_status="M2_NOT_INSTANTIABLE_WORLD"
                m2_graph_allowed=False
            else:
                raise RuntimeError(f"{cell}: absent from frozen Step-0 eligibility map")
            world_rows.append({
                "physical_cell_id":cell,
                "provider_world_id":world,
                "graph_id":graph,
                "m2_provider_world_instantiable":provider_ok,
                "failed_m2_providers":",".join(failed_providers),
                "status":cell_status,
                "m2_graph_prediction_allowed":m2_graph_allowed,
            })
    cells=pd.DataFrame(world_rows).sort_values(
        ["provider_world_id","graph_id"],kind="mergesort"
    ).reset_index(drop=True)
    return providers,cells


def main()->None:
    p=argparse.ArgumentParser(description="Audit frozen Phase-5 M2 reconstruction")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    root=args.root.resolve()
    providers,cells=audit(root)

    providers_path=root/"phase5_m2_provider_audit.csv"
    cells_path=root/"phase5_m2_graph_eligibility.csv"
    providers.to_csv(providers_path,index=False)
    cells.to_csv(cells_path,index=False)

    contracts=load_phase5_contracts(HERE)
    manifest_path=root/"phase5_m2_reconstruction_audit_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status="FROZEN_PHASE5_M2_RECONSTRUCTION_AUDIT_V2",
        inputs={
            "rule":"M2 world is graph-instantiable iff all three provider portfolios are frozen with three members each",
            "repair_or_gate_relaxation":False,
            "step0_eligibility_sha256":sha256_file(STEP0_MANIFEST),
        },
        seed_banks={},
        outputs={
            "provider_audit":str(providers_path),
            "graph_eligibility":str(cells_path),
        },
        started_utc=utc_now_iso(),
    )
    manifest["n_provider_pass"]=int(providers["instantiable"].sum())
    manifest["n_provider_not_instantiable"]=int((~providers["instantiable"]).sum())
    manifest["m2_instantiable_worlds"]=sorted(
        cells.loc[
            cells["m2_provider_world_instantiable"],
            "provider_world_id",
        ].unique().tolist()
    )
    manifest["n_m2_graph_prediction_eligible_cells"]=int(
        cells["m2_graph_prediction_allowed"].sum()
    )
    write_json(manifest_path,manifest)

    print("PHASE5_M2_RECONSTRUCTION_AUDIT_PASS")
    print("\nM2_PROVIDER_STATUS")
    print(providers[[
        "provider_world_id","provider_id","instantiable",
        "n_provisional_members","n_final_members","failure_reasons"
    ]].to_string(index=False))
    print("\nM2_GRAPH_ELIGIBILITY")
    print(cells[[
        "physical_cell_id","status","failed_m2_providers"
    ]].to_string(index=False))
    print(
        f"provider_pass={int(providers['instantiable'].sum())} "
        f"provider_not_instantiable={int((~providers['instantiable']).sum())} "
        f"graph_prediction_cells={int(cells['m2_graph_prediction_allowed'].sum())}"
    )
    print(f"manifest={manifest_path}")


if __name__=="__main__":
    main()
