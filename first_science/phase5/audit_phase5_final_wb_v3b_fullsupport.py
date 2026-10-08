"""Mechanical audit of the frozen Phase-5 V3b FULL343 final white-box bank.

This audit checks provenance, completeness, seed identity, point counts,
query identity, sigma/count consistency, Wilson intervals, and hashes.  It
does NOT load any M0/M1/M2/M3 prediction curves and computes no method
performance metric.  Its purpose is to close the reference-evidence layer
before the frozen analysis contract is applied.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE/"results"/"05_final_wb_v3b_fullsupport"
STEP0=HERE/"results"/"02_step0"
PRED=HERE/"results"/"04_prediction_v3b_fullsupport"
BATTERY_MANIFEST=ROOT/"phase5_v3b_fullsupport_final_wb_freeze_manifest.json"
GLOBAL_PRED=PRED/"phase5_v3b_fullsupport_global_prediction_freeze_manifest.json"
CFG=HERE/"config_phase5_final_wb_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json
from i1_provider_card import wilson_binomial_interval

EXPECTED_BATTERY="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY"
EXPECTED_CELL="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_CELL"
EXPECTED_GLOBAL="FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"
AUDIT_STATUS="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_MECHANICAL_AUDIT_PASS"
TOL=1e-12


def _eligible_and_failed():
    e=pd.read_csv(STEP0/"phase5_step0_eligibility.csv")
    if len(e)!=16:
        raise RuntimeError("Step-0 eligibility must contain 16 physical cells")
    eligible=e[e["eligibility"].astype(str)=="ELIGIBLE"].copy()
    failed=e[e["eligibility"].astype(str)=="GATE_FAILED_STEP0"].copy()
    if len(eligible)!=12 or len(failed)!=4:
        raise RuntimeError("expected exactly 12 eligible and 4 Step-0-failed cells")
    if set(failed["provider_world_id"].astype(str))!={"P2"}:
        raise RuntimeError("all four gate-failed cells must be P2")
    return eligible,failed


def _check_curve_file(cell:str, path:Path, qpath:Path)->dict:
    curves=pd.read_csv(path)
    queries=pd.read_csv(qpath)
    if len(curves)!=15*49:
        raise RuntimeError(f"{cell}: final-WB curve rows !=735")
    if curves["query_id"].astype(str).nunique()!=15:
        raise RuntimeError(f"{cell}: final-WB query count !=15")
    expected_h=[float(x) for x in range(0,241,5)]
    for qid,g in curves.groupby("query_id",sort=False):
        hs=sorted(g["H"].astype(float).tolist())
        if hs!=expected_h:
            raise RuntimeError(f"{cell}/{qid}: horizon support changed")
        if set(g["wb_n"].astype(int))!={1000}:
            raise RuntimeError(f"{cell}/{qid}: WB N changed")

    if not np.allclose(
        curves["sigma_wb"].astype(float).to_numpy(),
        curves["wb_successes"].astype(float).to_numpy()/1000.0,
        atol=TOL,rtol=0.0,
    ):
        raise RuntimeError(f"{cell}: sigma_wb != successes/1000")
    succ=curves["wb_successes"].astype(int)
    if ((succ<0)|(succ>1000)).any():
        raise RuntimeError(f"{cell}: invalid WB success count")
    if ((curves["wb_ci_lower"].astype(float)<-TOL)|
        (curves["wb_ci_upper"].astype(float)>1.0+TOL)|
        (curves["wb_ci_lower"].astype(float)>curves["sigma_wb"].astype(float)+TOL)|
        (curves["wb_ci_upper"].astype(float)<curves["sigma_wb"].astype(float)-TOL)).any():
        raise RuntimeError(f"{cell}: invalid Wilson interval")

    # Spot-check every point against the same frozen Wilson implementation.
    for r in curves.itertuples(index=False):
        lo,hi=wilson_binomial_interval(int(r.wb_successes),1000)
        if abs(float(r.wb_ci_lower)-lo)>1e-12 or abs(float(r.wb_ci_upper)-hi)>1e-12:
            raise RuntimeError(f"{cell}/{r.query_id}/H={r.H}: Wilson mismatch")

    # Query geometry/labels must exactly match the already frozen Step-0 file.
    qcols=["query_id","provider_world_id","graph_id","rho_label","rho","regime",
           "A_G_l_max","A_G_c_max","A_G_q_min"]
    frozen=queries[qcols].copy().sort_values("query_id",kind="mergesort").reset_index(drop=True)
    observed=(
        curves[qcols].drop_duplicates()
        .sort_values("query_id",kind="mergesort").reset_index(drop=True)
    )
    if len(observed)!=15:
        raise RuntimeError(f"{cell}: curve query metadata does not reduce to 15 rows")
    for col in ("query_id","provider_world_id","graph_id","rho_label","regime"):
        if observed[col].astype(str).tolist()!=frozen[col].astype(str).tolist():
            raise RuntimeError(f"{cell}: frozen query metadata mismatch in {col}")
    for col in ("rho","A_G_l_max","A_G_c_max","A_G_q_min"):
        if not np.allclose(
            observed[col].astype(float),frozen[col].astype(float),
            atol=1e-12,rtol=0.0,equal_nan=True
        ):
            raise RuntimeError(f"{cell}: frozen query numeric mismatch in {col}")

    return {
        "curve_rows":int(len(curves)),
        "query_count":int(curves["query_id"].nunique()),
        "horizon_count":49,
        "wb_n":1000,
        "sigma_min":float(curves["sigma_wb"].min()),
        "sigma_max":float(curves["sigma_wb"].max()),
    }


def run()->Path:
    battery=read_json(BATTERY_MANIFEST)
    global_pred=read_json(GLOBAL_PRED)
    if battery.get("status")!=EXPECTED_BATTERY or battery.get("complete") is not True:
        raise RuntimeError("final-WB battery is not completely frozen")
    if battery.get("evaluation_unlocked") is not True:
        raise RuntimeError("final-WB battery has not unlocked evaluation")
    if global_pred.get("status")!=EXPECTED_GLOBAL or global_pred.get("complete") is not True:
        raise RuntimeError("blind-prediction global freeze is not complete")
    if global_pred.get("final_WB_read") is not False:
        raise RuntimeError("blind-prediction freeze does not certify pre-WB blindness")

    eligible,failed=_eligible_and_failed()
    frozen_cells=sorted(battery.get("eligible_final_wb_cells",[]))
    failed_cells=sorted(battery.get("gate_failed_step0_cells",[]))
    if frozen_cells!=sorted(eligible["physical_cell_id"].astype(str).tolist()):
        raise RuntimeError("battery final-WB eligible-cell set mismatches Step-0")
    if failed_cells!=sorted(failed["physical_cell_id"].astype(str).tolist()):
        raise RuntimeError("battery final-WB failed-cell set mismatches Step-0")

    battery_hashes=dict(battery.get("final_wb_manifest_sha256",{}))
    if set(battery_hashes)!=set(frozen_cells):
        raise RuntimeError("battery final-WB manifest-hash set incomplete")

    pred_hashes=dict(global_pred.get("prediction_manifest_sha256",{}))
    rows=[]
    for rec in eligible.sort_values(["provider_world_id","graph_id"],kind="mergesort").itertuples(index=False):
        cell=str(rec.physical_cell_id)
        root=ROOT/cell
        manifest_path=root/"final_wb_manifest.json"
        ledger_path=root/"final_wb_ledger.csv"
        curve_path=root/"final_wb_curves.csv"
        qpath=STEP0/cell/"step0_frozen_queries.csv"
        pred_manifest=PRED/cell/"prediction_manifest.json"

        for p in (manifest_path,ledger_path,curve_path,qpath,pred_manifest):
            if not p.is_file():
                raise FileNotFoundError(p)

        if sha256_file(manifest_path)!=str(battery_hashes[cell]):
            raise RuntimeError(f"{cell}: final-WB manifest changed after battery freeze")
        m=read_json(manifest_path)
        if m.get("status")!=EXPECTED_CELL:
            raise RuntimeError(f"{cell}: final-WB cell manifest not frozen")
        if m.get("output_hashes_sha256",{}).get("final_wb_ledger")!=sha256_file(ledger_path):
            raise RuntimeError(f"{cell}: final-WB ledger hash mismatch")
        if m.get("output_hashes_sha256",{}).get("final_wb_curves")!=sha256_file(curve_path):
            raise RuntimeError(f"{cell}: final-WB curves hash mismatch")
        if m.get("step0_frozen_queries_sha256")!=sha256_file(qpath):
            raise RuntimeError(f"{cell}: Step-0 query hash mismatch")
        if m.get("frozen_prediction_manifest_sha256")!=sha256_file(pred_manifest):
            raise RuntimeError(f"{cell}: prediction-manifest hash mismatch inside WB manifest")
        if sha256_file(pred_manifest)!=str(pred_hashes[cell]):
            raise RuntimeError(f"{cell}: prediction manifest changed after global prediction freeze")
        if int(m.get("inputs",{}).get("whitebox_n",-1))!=1000:
            raise RuntimeError(f"{cell}: WB manifest N !=1000")

        ledger=pd.read_csv(ledger_path,usecols=["trajectory","trajectory_seed"])
        if int(ledger["trajectory"].nunique())!=1000:
            raise RuntimeError(f"{cell}: WB ledger trajectory count !=1000")
        seeds=sorted(ledger["trajectory_seed"].astype(int).unique().tolist())
        if seeds!=list(range(54000,55000)):
            raise RuntimeError(f"{cell}: WB ledger seed identity mismatch")
        seed_per_traj=ledger.groupby("trajectory")["trajectory_seed"].nunique()
        if set(seed_per_traj.astype(int))!={1}:
            raise RuntimeError(f"{cell}: trajectory maps to multiple WB seeds")

        info=_check_curve_file(cell,curve_path,qpath)
        rows.append({
            "physical_cell_id":cell,
            "provider_world_id":str(rec.provider_world_id),
            "graph_id":str(rec.graph_id),
            "manifest_sha256":sha256_file(manifest_path),
            "ledger_sha256":sha256_file(ledger_path),
            "curves_sha256":sha256_file(curve_path),
            **info,
            "status":"PASS",
        })

    # No final-WB manifest may exist for a Step-0-excluded P2 cell.
    for cell in failed["physical_cell_id"].astype(str):
        if (ROOT/cell/"final_wb_manifest.json").exists():
            raise RuntimeError(f"{cell}: excluded cell unexpectedly has a final-WB manifest")

    table=pd.DataFrame(rows).sort_values(
        ["provider_world_id","graph_id"],kind="mergesort"
    ).reset_index(drop=True)
    table_path=ROOT/"phase5_v3b_fullsupport_final_wb_mechanical_audit.csv"
    table.to_csv(table_path,index=False)

    checks={
        "battery_freeze_complete":True,
        "evaluation_unlocked":True,
        "eligible_cells_exactly_12":True,
        "gate_failed_cells_exactly_4":True,
        "all_gate_failed_cells_are_P2":True,
        "all_12_cell_manifest_hashes_match_battery_freeze":True,
        "all_12_prediction_manifest_hashes_still_match_global_prediction_freeze":True,
        "all_12_ledgers_have_exactly_1000_trajectories":True,
        "all_12_ledgers_use_exact_seeds_54000_54999":True,
        "all_12_curve_tables_have_15_queries_x_49_horizons":True,
        "all_curve_points_have_wb_n_1000":True,
        "all_sigma_values_equal_successes_divided_by_1000":True,
        "all_wilson_intervals_recompute_exactly":True,
        "all_query_metadata_match_frozen_step0":True,
        "no_gate_failed_P2_cell_has_final_WB_manifest":True,
        "prediction_curves_read":False,
        "method_performance_computed":False,
    }
    manifest={
        "status":AUDIT_STATUS,
        "stage_id":"FINAL_WB_MECHANICAL_AUDIT_V3B_FULLSUPPORT",
        "scientific_evidence":False,
        "final_wb_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "global_prediction_freeze_sha256":sha256_file(GLOBAL_PRED),
        "final_wb_battery_freeze_sha256":sha256_file(BATTERY_MANIFEST),
        "checks":checks,
        "audited_cells":12,
        "gate_failed_cells":4,
        "output_table":str(table_path),
        "output_table_sha256":sha256_file(table_path),
        "completed_utc":utc_now_iso(),
    }
    path=ROOT/"phase5_v3b_fullsupport_final_wb_mechanical_audit_manifest.json"
    write_json(path,manifest)

    print("PHASE5_V3B_FULLSUPPORT_FINAL_WB_MECHANICAL_AUDIT_PASS")
    print(table[["physical_cell_id","curve_rows","query_count","horizon_count","wb_n","status"]].to_string(index=False))
    for k,v in checks.items():
        print(k,v)
    print("manifest",path)
    return path


if __name__=="__main__":
    run()
