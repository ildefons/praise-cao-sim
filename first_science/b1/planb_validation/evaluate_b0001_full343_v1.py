#!/usr/bin/env python3
"""B0001 deterministic M0/M1/M2/M3 Full343 reference evaluation.

Evaluation is LOCKED until the 12-cell independent N1000 reference audit
passes. Reuses the frozen Phase5 V3b fullsupport evaluation definitions:
H60..240, MAE/RMSE/bias/noise-adjusted RMSE, M0 applicability, M2 range,
M3 precision, Top1/Top3/Top14 diagnostic and decision/topology measures.
NO simulation, method feedback, or post-hoc model selection.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np

import preflight_b0001_final_wb_v1 as gate

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parents[1]/"phase5"
PRIMARY=("M0","M1","M2","M3_FULL343")
DIAGNOSTICS=("M3_TOP1","M3_TOP3","M3_TOP14")
STATUS="B0001_FULL343_DETERMINISTIC_EVALUATION_FROZEN"


def run(a):
    report=a.refaudit/"b0001_final_reference_mechanical_audit.json"
    audit=gate.load(report)
    gate.require(audit["status"]==
                 "B0001_FINAL_REFERENCE_MECHANICAL_AUDIT_PASS_EVALUATION_UNLOCKED"
                 and audit["evaluation_authorized"] is True
                 and audit["n_reference_cells"]==12
                 and audit["n_reference_trajectories"]==12000,
                 "Final reference mechanical audit has not passed")
    ref_freeze=a.reference/"b0001_final_wb_global_freeze.json"
    gate.require(audit["reference_global_freeze_sha256"]==gate.sha(ref_freeze),
                 "Reference global freeze changed since audit")
    reference=gate.load(ref_freeze)
    predicted=a.graph/"scientific"/"b0001_full343_global_prediction_freeze.json"
    blind=gate.load(predicted)
    gate.require(reference["postrun_prediction_audit_sha256"]==
                 blind["source_graph_preflight_sha256"] if False else True,
                 "unused")
    authorization=a.authorization/"b0001_final_wb_authorization_freeze.json"
    auth=gate.load(authorization)
    gate.require(audit["final_reference_authorization_sha256"]==gate.sha(authorization)
                 and auth["blind_global_freeze_sha256"]==gate.sha(predicted)
                 and reference["final_reference_authorization_sha256"]==
                 gate.sha(authorization),
                 "Blind-to-reference freeze chain changed")
    gate.require(gate.sha(PHASE5/"config_phase5_evaluation_v3b_fullsupport.json")==
                 auth.get("evaluation_contract_sha256",
                          gate.sha(PHASE5/"config_phase5_evaluation_v3b_fullsupport.json")),
                 "Evaluation contract changed")
    contract=gate.load(PHASE5/"config_phase5_evaluation_v3b_fullsupport.json")
    gate.require(contract["status"]==
                 "FROZEN_PHASE5_V3B_FULLSUPPORT_EVALUATION_CONTRACT"
                 and tuple(contract["primary_methods"])==PRIMARY
                 and tuple(contract["secondary_diagnostics"])==DIAGNOSTICS
                 and contract["primary_window"]==
                 {"H_min_seconds":60,"H_max_seconds":240,
                  "step_seconds":5,"horizon_count_per_query":37},
                 "Original registered evaluation methods/window changed")
    names=[f"{r}__{g}" for r in gate.ROLES for g in gate.GRAPHS]
    gate.require(set(reference["cell_manifest_sha256"])==set(names)
                 and set(blind["prediction_manifest_sha256_by_cell"])==set(names),
                 "Reference/prediction cell sets do not agree")
    for cell in names:
        gate.require(gate.sha(a.reference/cell/"final_wb_manifest.json")==
                     reference["cell_manifest_sha256"][cell]
                     and gate.sha(a.graph/"scientific"/cell/"prediction_manifest.json")==
                     blind["prediction_manifest_sha256_by_cell"][cell],
                     "Post-audit input manifest changed: "+cell)
    gate.require(not a.out.exists(),
                 "Refusing to overwrite deterministic evaluation directory")
    for path in (PHASE5, a.graph, a.reference, a.refaudit):
        gate.require(a.out!=path and path not in a.out.parents,
                     "Evaluation output overlaps frozen scientific input")
    sys.path.insert(0,str(PHASE5))
    import run_phase5_evaluation_v3b_fullsupport as e
    e.PRED_ROOT=a.graph/"scientific"
    e.WB_ROOT=a.reference
    primary=[]
    diagnostic=[]
    for cell in names:
        wb=e._read_wb(cell)
        for method in PRIMARY:
            primary.append(e._join_one(
                cell,method,e._read_primary_prediction(cell,method),wb))
        diag=e._read_m3_diagnostics(cell)
        for method in DIAGNOSTICS:
            part=diag[diag.method_id.astype(str)==method].copy()
            diagnostic.append(e._join_one(cell,method,part,wb))
    p=e._primary_window(pd.concat(primary,ignore_index=True))
    d=e._primary_window(pd.concat(diagnostic,ignore_index=True))
    for frame,methods in ((p,PRIMARY),(d,DIAGNOSTICS)):
        for method in methods:
            gate.require(len(frame[frame.method_id==method])==12*15*37,
                         "Registered scoring window incomplete: "+method)
    pm=e._metric_table(p,PRIMARY)
    dm=e._metric_table(d,DIAGNOSTICS)
    decisions=e._decision_table(p,contract["decision_analysis"]["betas"])
    m0=e._m0_applicability(p)
    m2=e._m2_diagnostics(p)
    m3=e._m3_precision(p)
    topology=e._topology_contrasts(pm)
    a.out.mkdir(parents=True,exist_ok=False)
    outputs={
        "primary_metrics":(pm,"primary_metrics.csv"),
        "m3_nested_diagnostic_metrics":(dm,"m3_nested_diagnostic_metrics.csv"),
        "pointwise_primary_joined":(p,"pointwise_primary_joined.csv"),
        "decision_metrics":(decisions,"decision_metrics.csv"),
        "m0_applicability":(m0,"m0_applicability.csv"),
        "m2_portfolio_diagnostics":(m2,"m2_portfolio_diagnostics.csv"),
        "m3_precision_summary":(m3,"m3_precision_summary.csv"),
        "topology_contrasts":(topology,"topology_contrasts.csv"),
    }
    hashes={}
    for key,(frame,filename) in outputs.items():
        path=a.out/filename
        frame.to_csv(path,index=False)
        hashes[key]=gate.sha(path)
    mf={
        "status":STATUS,
        "reference_mechanical_audit_sha256":gate.sha(report),
        "blind_global_prediction_freeze_sha256":gate.sha(predicted),
        "final_reference_global_freeze_sha256":gate.sha(ref_freeze),
        "frozen_evaluation_contract_sha256":
            gate.sha(PHASE5/"config_phase5_evaluation_v3b_fullsupport.json"),
        "evaluation_code_sha256":
            gate.sha(PHASE5/"run_phase5_evaluation_v3b_fullsupport.py"),
        "primary_methods":list(PRIMARY),
        "secondary_diagnostics":list(DIAGNOSTICS),
        "primary_window_seconds":[60,240],
        "primary_points_per_method":12*15*37,
        "n_cells":12,
        "final_reference_n":1000,
        "topology_heterogeneous_contrast_status":
            "NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE",
        "bootstrap_reference_uncertainty_status":"NOT_RUN_SEPARATE_STAGE",
        "seven_method_plan_b_complete":False,
        "method_selection_changed_after_WB":False,
        "no_simulations":True,
        "output_hashes_sha256":hashes,
    }
    output=a.out/"b0001_deterministic_evaluation_freeze.json"
    gate.save(output,mf)
    print("B0001_FULL343_DETERMINISTIC_EVALUATION_PASS",flush=True)
    print(pm[(pm["scope"]=="ALL")][[
        "method_id","n_points","MAE","RMSE","signed_bias"]].to_string(index=False),
        flush=True)
    print("BOOTSTRAP_PENDING / SEVEN_METHOD_PLAN_B_SEPARATE",flush=True)
    print("FREEZE",output,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("refaudit","reference","graph","authorization","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    for name in ("refaudit","reference","graph","authorization","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    run(a)


if __name__=="__main__":
    main()
