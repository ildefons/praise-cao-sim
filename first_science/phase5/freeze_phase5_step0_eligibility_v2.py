"""Freeze the Phase-5 V2 Step-0 eligibility map after confirmation.

This read-only audit consumes the 16 Step-0 confirmation manifests and emits a
battery-level eligibility table plus manifest.  It never repairs, reselects or
reruns a Step-0 query.  Provider-world reconstruction remains allowed for every
world, including worlds with zero eligible graph cells; graph prediction and
final WB are allowed only for ELIGIBLE physical cells.
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
DEFAULT_ROOT=HERE/"results"/"02_step0"


def audit(root:Path)->pd.DataFrame:
    contracts=load_phase5_contracts(HERE)
    rows=[]
    for world in canonical_provider_world_ids(contracts):
        for graph in canonical_graph_ids(contracts):
            cell=physical_cell_id(world,graph)
            path=root/cell/"step0_confirmation_manifest.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            m=read_json(path)
            for key,expected in (
                ("battery_config_sha256",contracts.hashes["battery"]),
                ("seed_registry_sha256",contracts.hashes["seeds"]),
                ("method_contract_sha256",contracts.hashes["methods"]),
                ("analysis_contract_sha256",contracts.hashes["analysis"]),
                ("execution_contract_sha256",contracts.hashes["execution"]),
            ):
                if m.get(key)!=expected:
                    raise RuntimeError(f"{cell}: {key} mismatch")

            status=str(m.get("status"))
            if status=="FROZEN_PHASE5_STEP0_PASS_V2":
                eligibility="ELIGIBLE"
                qpath=root/cell/"step0_frozen_queries.csv"
                if not qpath.is_file():
                    raise FileNotFoundError(qpath)
                q=pd.read_csv(qpath)
                if len(q)!=15:
                    raise RuntimeError(f"{cell}: eligible cell has {len(q)} queries")
                if not (q["step0_cell_status"].astype(str)==status).all():
                    raise RuntimeError(f"{cell}: frozen-query status mismatch")
                n_queries=15
            elif status=="GATE_FAILED_STEP0":
                eligibility="GATE_FAILED_STEP0"
                n_queries=0
            else:
                raise RuntimeError(f"{cell}: unexpected confirmation status {status!r}")

            rows.append({
                "physical_cell_id":cell,
                "provider_world_id":world,
                "graph_id":graph,
                "step0_status":status,
                "eligibility":eligibility,
                "n_frozen_queries_for_prediction":n_queries,
                "confirmation_manifest_sha256":sha256_file(path),
            })
    frame=pd.DataFrame(rows).sort_values(
        ["provider_world_id","graph_id"],kind="mergesort"
    ).reset_index(drop=True)
    if len(frame)!=16:
        raise RuntimeError("Step-0 eligibility map must contain 16 cells")
    return frame


def main()->None:
    p=argparse.ArgumentParser(description="Freeze Phase-5 Step-0 eligibility map")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    args=p.parse_args()
    root=args.root.resolve()
    frame=audit(root)
    csv_path=root/"phase5_step0_eligibility.csv"
    frame.to_csv(csv_path,index=False)

    contracts=load_phase5_contracts(HERE)
    eligible=frame.loc[frame["eligibility"]=="ELIGIBLE","physical_cell_id"].tolist()
    failed=frame.loc[
        frame["eligibility"]=="GATE_FAILED_STEP0","physical_cell_id"
    ].tolist()
    world_counts=(
        frame.assign(is_eligible=frame["eligibility"].eq("ELIGIBLE").astype(int))
        .groupby("provider_world_id",as_index=False)["is_eligible"].sum()
        .set_index("provider_world_id")["is_eligible"]
        .astype(int)
        .to_dict()
    )
    manifest_path=root/"phase5_step0_eligibility_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="STEP0_CONFIRMATION",
        status="FROZEN_PHASE5_STEP0_ELIGIBILITY_MAP_V2",
        inputs={
            "rule":"cell-level prospective exclusion; no repair or reselection",
            "provider_reconstruction_scope":"all provider worlds regardless of graph-cell eligibility",
            "graph_prediction_scope":"eligible cells only",
        },
        seed_banks={},
        outputs={"eligibility_table":str(csv_path)},
        started_utc=utc_now_iso(),
    )
    manifest["eligible_cells"]=eligible
    manifest["gate_failed_step0_cells"]=failed
    manifest["eligible_graph_count_by_provider_world"]=world_counts
    manifest["n_eligible_cells"]=len(eligible)
    manifest["n_gate_failed_cells"]=len(failed)
    write_json(manifest_path,manifest)

    print("PHASE5_STEP0_ELIGIBILITY_FREEZE_PASS")
    print(frame[[
        "physical_cell_id","eligibility","n_frozen_queries_for_prediction"
    ]].to_string(index=False))
    print(f"eligible={len(eligible)} gate_failed={len(failed)}")
    print(f"eligible_by_world={world_counts}")
    print(f"manifest={manifest_path}")


if __name__=="__main__":
    main()
