"""Read-only matched-query M1/M2/M3 comparison for P2 G_PAR.

Requires frozen M1/M2 and M3 predictions and independent white-box
reference from evaluate_i1_m3_p2_pilot.py. Same five rho-diagonal queries,
same 49 horizons, primary 60..240 seconds. Native costs NOT matched.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from phase5_runtime_v2 import sha256_file
from run_i1_m123_p2_native_comparison import OUT, ROOT, QUERIES, M3FREEZE
from evaluate_i1_m3_p2_pilot import REF

def main():
    freeze=OUT/"prediction_manifest.json"
    if not freeze.is_file():raise FileNotFoundError("M1/M2 prediction freeze missing")
    fm=json.loads(freeze.read_text())
    if fm.get("whitebox_read") is not False or fm.get("status")!="FROZEN_P2_G_PAR_MATCHED_QUERY_M1_M2_NATIVE_PREDICTIONS":
        raise RuntimeError("invalid M1/M2 freeze")
    if fm["common_query_sha256"]!=sha256_file(QUERIES):
        raise RuntimeError("M1/M2 query hash mismatch")
    for name,hash_ in fm["output_sha256"].items():
        if sha256_file(OUT/name)!=hash_:raise RuntimeError(f"prediction altered: {name}")
    m3=json.loads(M3FREEZE.read_text())
    m3path=ROOT/"m3_predictions_full343_and_nested.csv"
    if sha256_file(m3path)!=m3["files"]["predictions"]:
        raise RuntimeError("M3 prediction hash mismatch")
    refmanifest=json.loads((REF/"evaluation_manifest.json").read_text())
    wb_path=REF/"wb_survival_on_public_region.csv"
    wb_ledger=REF/"wb_request_ledger.csv"
    if sha256_file(wb_ledger)!=refmanifest["wb_ledger_sha256"]:
        raise RuntimeError("WB ledger altered")
    if sha256_file(wb_path)!=refmanifest["output_sha256"]["wb_survival_on_public_region.csv"]:
        raise RuntimeError("WB curve altered")
    wb=pd.read_csv(wb_path)[["query_id","H","sigma_wb"]]
    if len(wb)!=245 or wb[["query_id","H"]].duplicated().any():
        raise RuntimeError("invalid reference grid")
    frames=[]
    for method,file,root,code in [
        ("M1","m1_predictions.csv",OUT,"M1"),
        ("M2","m2_predictions.csv",OUT,"M2"),
        ("M3_FULL343","m3_predictions_full343_and_nested.csv",ROOT,"M3_FULL343"),
    ]:
        x=pd.read_csv(root/file)
        x=x.loc[x.method_id==code,["query_id","H","sigma_hat"]].copy()
        if len(x)!=245 or x[["query_id","H"]].duplicated().any():
            raise RuntimeError(f"{method}: incorrect prediction grid")
        x["method"]=method
        frames.append(x)
    predicted=pd.concat(frames,ignore_index=True)
    combined=predicted.merge(wb,on=["query_id","H"],validate="many_to_one")
    if len(combined)!=735:raise RuntimeError("prediction/reference grid mismatch")
    combined["error"]=combined.sigma_hat-combined.sigma_wb
    relevant=combined[combined.H>=60].copy()
    result=relevant.groupby("method",as_index=False).agg(
        mae=("error",lambda e:float(np.abs(e).mean())),
        rmse=("error",lambda e:float(np.sqrt(np.square(e).mean()))),
        bias=("error","mean"),
        n_points=("error","size"),
    )
    by_rho=relevant.groupby(["method","query_id"],as_index=False).agg(
        mae=("error",lambda e:float(np.abs(e).mean())),
        rmse=("error",lambda e:float(np.sqrt(np.square(e).mean()))),
        bias=("error","mean"),
    )
    result["graph_trajectories"]=result.method.map({"M1":100,"M2":2700,"M3_FULL343":1400})
    out=OUT/"evaluation"
    out.mkdir(parents=True,exist_ok=True)
    for name,data in [("matched_survival_curves.csv",combined),("matched_rmse_summary.csv",result),("matched_error_by_rho.csv",by_rho)]:
        data.to_csv(out/name,index=False)
    report={
        "status":"RETROSPECTIVE_P2_G_PAR_M1_M2_M3_NATIVE_BUDGET_COMPARISON_COMPLETE",
        "matched_query_sha256":sha256_file(QUERIES),
        "m1_m2_prediction_freeze_sha256":sha256_file(freeze),
        "m3_prediction_freeze_sha256":sha256_file(M3FREEZE),
        "whitebox_evaluation_manifest_sha256":sha256_file(REF/"evaluation_manifest.json"),
        "not_cost_matched":True,
        "A_G_identical_by_construction":True,
        "reference_A_G_comparison":"see whitebox_evaluation/graph_region_comparison.csv; same for every method",
        "outputs_sha256":{p.name:sha256_file(p) for p in out.glob("*.csv")},
    }
    (out/"comparison_manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print("P2_G_PAR_M1_M2_M3_MATCHED_COMPARISON_COMPLETE")
    print(result.to_string(index=False))
    print("A_G same for M1/M2/M3; native graph costs are not matched.")

if __name__=="__main__":
    main()
