"""Matched-control evaluation: I1-strong M2 vs I2AFS-M2 on P4/G_SEQPAR."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"

from sys import path as _sys_path
if str(PHASE5) not in _sys_path:
    _sys_path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402

CELL="P4__G_SEQPAR"
BETA=0.9

P5_POINTWISE=PHASE5/"results"/"06_evaluation_v3b_fullsupport"/"pointwise_primary_joined.csv"
P5_QUERIES=PHASE5/"results"/"02_step0"/CELL/"step0_frozen_queries.csv"

I1S_ROOT=HERE/"results"/"19_i1strong_m2_p4_g_seqpar"
I1S_PRED=I1S_ROOT/"i1strong_m2_predictions.csv"
I1S_MANIFEST=I1S_ROOT/"prediction_manifest.json"

I2AFS_ROOT=HERE/"results"/"15_i2afs_m2_p4_g_seqpar"
I2AFS_PRED=I2AFS_ROOT/"i2afs_m2_predictions.csv"
I2AFS_MANIFEST=I2AFS_ROOT/"prediction_manifest.json"

OUT=HERE/"results"/"20_i1strong_vs_i2afs_matched_evaluation"


def _metrics(g):
    e=g["sigma_hat"].astype(float).to_numpy()-g["sigma_wb"].astype(float).to_numpy()
    return {
        "n_points":int(len(e)),
        "mae":float(np.mean(np.abs(e))),
        "rmse":float(np.sqrt(np.mean(e*e))),
        "bias":float(np.mean(e)),
        "max_abs_error":float(np.max(np.abs(e))),
    }


def _decision(g):
    lower=g["wb_ci_lower"].astype(float).to_numpy()
    upper=g["wb_ci_upper"].astype(float).to_numpy()
    pred=g["sigma_hat"].astype(float).to_numpy()>=BETA
    wb_accept=lower>=BETA
    wb_reject=upper<BETA
    resolvable=wb_accept|wb_reject
    if not np.any(resolvable):
        return {
            "beta":BETA,"wb_resolvable_points":0,
            "false_accept":0,"false_reject":0,"agreement":float("nan"),
        }
    return {
        "beta":BETA,
        "wb_resolvable_points":int(np.sum(resolvable)),
        "false_accept":int(np.sum(pred & wb_reject)),
        "false_reject":int(np.sum((~pred) & wb_accept)),
        "agreement":float(np.mean(pred[resolvable]==wb_accept[resolvable])),
    }


def _reference():
    p=pd.read_csv(P5_POINTWISE)
    p=p[
        (p["physical_cell_id"].astype(str)==CELL)
        &(p["method_id"].astype(str)=="M2")
        &(p["H"].astype(float)>=60.0)
        &(p["H"].astype(float)<=240.0)
    ].copy()
    need={"query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper","sigma_hat"}
    if not need.issubset(p.columns) or len(p)!=15*37:
        raise RuntimeError("Phase-5 P4/G_SEQPAR reference support invalid")
    return p


def _qmeta():
    q=pd.read_csv(P5_QUERIES)
    q=q[["query_id","regime","rho"]].drop_duplicates()
    if len(q)!=15:
        raise RuntimeError("expected 15 frozen queries")
    return q


def _load_method(name,pred_path,ref,qmeta):
    p=pd.read_csv(pred_path)
    p=p[(p["H"].astype(float)>=60.0)&(p["H"].astype(float)<=240.0)].copy()
    if len(p)!=15*37:
        raise RuntimeError(f"{name}: expected 555 points")
    base=ref[
        ["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]
    ].drop_duplicates()
    out=base.merge(
        p[["query_id","H","sigma_hat"]],
        on=["query_id","H"],how="inner",validate="one_to_one",
    ).merge(qmeta,on="query_id",how="left",validate="many_to_one")
    if len(out)!=15*37:
        raise RuntimeError(f"{name}: incomplete join")
    out["method"]=name
    return out


def run():
    for path,status in (
        (I1S_MANIFEST,"PHASE6_I1STRONG_M2_P4_G_SEQPAR_PREDICTION_COMPLETE"),
        (I2AFS_MANIFEST,"PHASE6_I2AFS_M2_P4_G_SEQPAR_PREDICTION_COMPLETE"),
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
        if read_json(path).get("status")!=status:
            raise RuntimeError(f"prediction manifest not complete: {path}")

    ref=_reference()
    qmeta=_qmeta()
    frames=[
        _load_method("I1STRONG_M2",I1S_PRED,ref,qmeta),
        _load_method("I2AFS_M2",I2AFS_PRED,ref,qmeta),
    ]
    joined=pd.concat(frames,ignore_index=True)

    metric_rows=[]
    decision_rows=[]
    for method,g in joined.groupby("method",sort=False):
        metric_rows.append({"scope":"ALL","regime":"ALL","method":method,**_metrics(g)})
        decision_rows.append({"scope":"ALL","regime":"ALL","method":method,**_decision(g)})
        for regime,gg in g.groupby("regime",sort=False):
            metric_rows.append({"scope":"REGIME","regime":str(regime),"method":method,**_metrics(gg)})
            decision_rows.append({"scope":"REGIME","regime":str(regime),"method":method,**_decision(gg)})

    metrics=pd.DataFrame(metric_rows)
    decisions=pd.DataFrame(decision_rows)

    a=joined[joined["method"]=="I1STRONG_M2"][
        ["query_id","H","sigma_hat","sigma_wb","regime"]
    ].rename(columns={"sigma_hat":"sigma_i1strong"})
    b=joined[joined["method"]=="I2AFS_M2"][
        ["query_id","H","sigma_hat"]
    ].rename(columns={"sigma_hat":"sigma_i2afs"})
    pair=a.merge(b,on=["query_id","H"],how="inner",validate="one_to_one")
    pair["abs_error_i1strong"]=(pair["sigma_i1strong"]-pair["sigma_wb"]).abs()
    pair["abs_error_i2afs"]=(pair["sigma_i2afs"]-pair["sigma_wb"]).abs()
    pair["i2afs_abs_error_advantage"]=pair["abs_error_i1strong"]-pair["abs_error_i2afs"]

    paired_rows=[{
        "scope":"ALL",
        "regime":"ALL",
        "n_points":int(len(pair)),
        "i2afs_better_points":int((pair["i2afs_abs_error_advantage"]>0).sum()),
        "ties":int(np.isclose(pair["i2afs_abs_error_advantage"],0.0,atol=1e-15,rtol=0.0).sum()),
        "i1strong_better_points":int((pair["i2afs_abs_error_advantage"]<0).sum()),
        "mean_i2afs_abs_error_advantage":float(pair["i2afs_abs_error_advantage"].mean()),
        "median_i2afs_abs_error_advantage":float(pair["i2afs_abs_error_advantage"].median()),
    }]
    for regime,g in pair.groupby("regime",sort=False):
        paired_rows.append({
            "scope":"REGIME",
            "regime":str(regime),
            "n_points":int(len(g)),
            "i2afs_better_points":int((g["i2afs_abs_error_advantage"]>0).sum()),
            "ties":int(np.isclose(g["i2afs_abs_error_advantage"],0.0,atol=1e-15,rtol=0.0).sum()),
            "i1strong_better_points":int((g["i2afs_abs_error_advantage"]<0).sum()),
            "mean_i2afs_abs_error_advantage":float(g["i2afs_abs_error_advantage"].mean()),
            "median_i2afs_abs_error_advantage":float(g["i2afs_abs_error_advantage"].median()),
        })
    paired=pd.DataFrame(paired_rows)

    qrows=[]
    for (method,qid),g in joined.groupby(["method","query_id"],sort=True):
        rec=g.iloc[0]
        qrows.append({
            "method":method,
            "query_id":str(qid),
            "regime":str(rec["regime"]),
            "rho":float(rec["rho"]),
            **_metrics(g),
        })
    per_query=pd.DataFrame(qrows)

    OUT.mkdir(parents=True,exist_ok=True)
    outputs={
        "pointwise_joined":OUT/"pointwise_joined.csv",
        "metrics":OUT/"metrics.csv",
        "decisions":OUT/"decision_beta090.csv",
        "paired":OUT/"paired_i1strong_vs_i2afs.csv",
        "per_query":OUT/"per_query_metrics.csv",
    }
    joined.to_csv(outputs["pointwise_joined"],index=False)
    metrics.to_csv(outputs["metrics"],index=False)
    decisions.to_csv(outputs["decisions"],index=False)
    paired.to_csv(outputs["paired"],index=False)
    per_query.to_csv(outputs["per_query"],index=False)

    print("PHASE6_I1STRONG_VS_I2AFS_MATCHED_EVALUATION_PASS")
    print("\nALL-POINT METRICS")
    print(metrics[metrics["scope"]=="ALL"].to_string(index=False))
    print("\nBY-REGIME METRICS")
    print(metrics[metrics["scope"]=="REGIME"].to_string(index=False))
    print("\nBETA=0.9 DECISION METRICS")
    print(decisions[decisions["scope"]=="ALL"].to_string(index=False))
    print("\nPAIRED I1-STRONG VS I2AFS")
    print(paired.to_string(index=False))

    manifest=OUT/"evaluation_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_I1STRONG_VS_I2AFS_MATCHED_EVALUATION_COMPLETE",
        "matched_reconstruction_control":True,
        "provider_world_id":"P4",
        "graph_id":"G_SEQPAR",
        "primary_window":"H60..H240",
        "query_count":15,
        "point_count_per_method":555,
        "beta":BETA,
        "i1strong_prediction_manifest_sha256":sha256_file(I1S_MANIFEST),
        "i2afs_prediction_manifest_sha256":sha256_file(I2AFS_MANIFEST),
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    })
    print("\noutput",OUT)
    return manifest


if __name__=="__main__":
    run()
