"""Evaluate frozen I2AFS-M2 P4/G_SEQPAR prediction against the existing WB and I1-M2.

Post-prediction development evaluation.  The I2AFS provider reconstruction and
graph prediction are already frozen.  This script does not alter either method.

Primary comparison:
- all 15 frozen Step-0 queries,
- H = 60..240 s,
- pointwise MAE, RMSE, signed bias, max absolute error,
- the same metrics by Easy/Mid/Stress regime,
- beta=0.9 admission agreement on WB-resolvable points.

For context, if the earlier genuine I2a-W1 prediction exists, it is evaluated
with the same code but is not used to tune I2AFS.
"""
from __future__ import annotations

import math
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

NEW_ROOT=HERE/"results"/"15_i2afs_m2_p4_g_seqpar"
NEW_PRED=NEW_ROOT/"i2afs_m2_predictions.csv"
NEW_MANIFEST=NEW_ROOT/"prediction_manifest.json"

OLD_I2A_ROOT=HERE/"results"/"05_i2a_genuine_m2_p4_g_seqpar"
OLD_I2A_PRED=OLD_I2A_ROOT/"genuine_i2a_m2_predictions.csv"

OUT=HERE/"results"/"17_i2afs_m2_p4_g_seqpar_evaluation"


def _metrics(g:pd.DataFrame)->dict:
    e=g["sigma_hat"].astype(float).to_numpy()-g["sigma_wb"].astype(float).to_numpy()
    return {
        "n_points":int(len(e)),
        "mae":float(np.mean(np.abs(e))),
        "rmse":float(np.sqrt(np.mean(e*e))),
        "bias":float(np.mean(e)),
        "max_abs_error":float(np.max(np.abs(e))),
    }


def _decision(g:pd.DataFrame)->dict:
    # Same conservative WB-resolvable semantics used in the Phase-5 analysis:
    # resolvable accept if lower CI >= beta; resolvable reject if upper CI < beta.
    lower=g["wb_ci_lower"].astype(float).to_numpy()
    upper=g["wb_ci_upper"].astype(float).to_numpy()
    pred=g["sigma_hat"].astype(float).to_numpy()>=BETA

    wb_accept=lower>=BETA
    wb_reject=upper<BETA
    resolvable=wb_accept|wb_reject
    if not np.any(resolvable):
        return {
            "beta":BETA,
            "wb_resolvable_points":0,
            "false_accept":0,
            "false_reject":0,
            "agreement":float("nan"),
        }

    false_accept=int(np.sum(pred & wb_reject))
    false_reject=int(np.sum((~pred) & wb_accept))
    agreement=float(np.mean(pred[resolvable]==wb_accept[resolvable]))
    return {
        "beta":BETA,
        "wb_resolvable_points":int(np.sum(resolvable)),
        "false_accept":false_accept,
        "false_reject":false_reject,
        "agreement":agreement,
    }


def _load_reference()->pd.DataFrame:
    if not P5_POINTWISE.is_file():
        raise FileNotFoundError(P5_POINTWISE)
    p=pd.read_csv(P5_POINTWISE)
    p=p[
        (p["physical_cell_id"].astype(str)==CELL)
        &(p["method_id"].astype(str)=="M2")
        &(p["H"].astype(float)>=60.0)
        &(p["H"].astype(float)<=240.0)
    ].copy()
    need={"query_id","H","sigma_hat","sigma_wb","wb_ci_lower","wb_ci_upper"}
    if not need.issubset(p.columns):
        raise RuntimeError(f"Phase-5 pointwise reference missing {sorted(need-set(p.columns))}")
    if len(p)!=15*37:
        raise RuntimeError(f"expected 555 I1-M2 reference points, found {len(p)}")
    p=p.rename(columns={"sigma_hat":"sigma_i1_m2"})
    return p


def _query_meta()->pd.DataFrame:
    q=pd.read_csv(P5_QUERIES)
    need={"query_id","regime","rho"}
    if not need.issubset(q.columns):
        raise RuntimeError("Step-0 query file lacks query_id/regime/rho")
    q=q[list(need)].drop_duplicates()
    if len(q)!=15:
        raise RuntimeError(f"expected 15 frozen queries, found {len(q)}")
    return q


def _join_method(name:str,pred_path:Path,ref:pd.DataFrame,qmeta:pd.DataFrame)->pd.DataFrame:
    p=pd.read_csv(pred_path)
    need={"query_id","H","sigma_hat"}
    if not need.issubset(p.columns):
        raise RuntimeError(f"{name}: prediction missing {sorted(need-set(p.columns))}")
    p=p[(p["H"].astype(float)>=60.0)&(p["H"].astype(float)<=240.0)].copy()
    if len(p)!=15*37:
        raise RuntimeError(f"{name}: expected 555 prediction points, found {len(p)}")

    base=ref[
        ["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]
    ].drop_duplicates()
    if len(base)!=15*37:
        raise RuntimeError("WB reference support is not unique")

    out=base.merge(
        p[["query_id","H","sigma_hat"]],
        on=["query_id","H"],how="inner",validate="one_to_one",
    ).merge(qmeta,on="query_id",how="left",validate="many_to_one")
    if len(out)!=15*37 or out["regime"].isna().any():
        raise RuntimeError(f"{name}: joined support incomplete")
    out["method"]=name
    return out


def _i1_frame(ref:pd.DataFrame,qmeta:pd.DataFrame)->pd.DataFrame:
    out=ref[
        ["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper","sigma_i1_m2"]
    ].copy().rename(columns={"sigma_i1_m2":"sigma_hat"})
    out=out.merge(qmeta,on="query_id",how="left",validate="many_to_one")
    out["method"]="I1_M2"
    return out


def run()->Path:
    if not NEW_PRED.is_file():
        raise FileNotFoundError("run frozen I2AFS graph prediction first")
    manifest=read_json(NEW_MANIFEST)
    if manifest.get("status")!="PHASE6_I2AFS_M2_P4_G_SEQPAR_PREDICTION_COMPLETE":
        raise RuntimeError("I2AFS graph prediction is not frozen complete")

    ref=_load_reference()
    qmeta=_query_meta()

    frames=[
        _i1_frame(ref,qmeta),
        _join_method("I2AFS_M2",NEW_PRED,ref,qmeta),
    ]
    if OLD_I2A_PRED.is_file():
        frames.append(_join_method("I2A_W1_M2",OLD_I2A_PRED,ref,qmeta))

    joined=pd.concat(frames,ignore_index=True)
    rows=[]
    decisions=[]
    for method,g in joined.groupby("method",sort=False):
        rows.append({"scope":"ALL","regime":"ALL","method":method,**_metrics(g)})
        decisions.append({"scope":"ALL","regime":"ALL","method":method,**_decision(g)})
        for regime,gg in g.groupby("regime",sort=False):
            rows.append({"scope":"REGIME","regime":str(regime),"method":method,**_metrics(gg)})
            decisions.append({"scope":"REGIME","regime":str(regime),"method":method,**_decision(gg)})

    metrics=pd.DataFrame(rows)
    decision=pd.DataFrame(decisions)

    # Per-query summaries make it obvious whether aggregate gains are broad or
    # driven by a small number of frozen queries.
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

    # Direct paired improvement of I2AFS against I1 on identical WB points.
    i1=joined[joined["method"]=="I1_M2"][
        ["query_id","H","sigma_hat","sigma_wb"]
    ].rename(columns={"sigma_hat":"sigma_i1"})
    fs=joined[joined["method"]=="I2AFS_M2"][
        ["query_id","H","sigma_hat"]
    ].rename(columns={"sigma_hat":"sigma_i2afs"})
    pair=i1.merge(fs,on=["query_id","H"],how="inner",validate="one_to_one")
    pair["abs_error_i1"]=(pair["sigma_i1"]-pair["sigma_wb"]).abs()
    pair["abs_error_i2afs"]=(pair["sigma_i2afs"]-pair["sigma_wb"]).abs()
    pair["abs_error_improvement"]=pair["abs_error_i1"]-pair["abs_error_i2afs"]
    paired_summary={
        "n_points":int(len(pair)),
        "i2afs_better_points":int((pair["abs_error_improvement"]>0).sum()),
        "ties":int(np.isclose(pair["abs_error_improvement"],0.0,atol=1e-15,rtol=0.0).sum()),
        "i1_better_points":int((pair["abs_error_improvement"]<0).sum()),
        "mean_abs_error_improvement":float(pair["abs_error_improvement"].mean()),
        "median_abs_error_improvement":float(pair["abs_error_improvement"].median()),
    }

    OUT.mkdir(parents=True,exist_ok=True)
    joined_path=OUT/"pointwise_joined.csv"
    metrics_path=OUT/"metrics.csv"
    decision_path=OUT/"decision_beta090.csv"
    per_query_path=OUT/"per_query_metrics.csv"
    pair_path=OUT/"paired_i1_vs_i2afs.csv"
    joined.to_csv(joined_path,index=False)
    metrics.to_csv(metrics_path,index=False)
    decision.to_csv(decision_path,index=False)
    per_query.to_csv(per_query_path,index=False)
    pair.to_csv(pair_path,index=False)

    print("PHASE6_I2AFS_M2_P4_G_SEQPAR_EVALUATION_PASS")
    print("\nALL-POINT METRICS")
    print(metrics[metrics["scope"]=="ALL"].to_string(index=False))
    print("\nBY-REGIME METRICS")
    print(metrics[metrics["scope"]=="REGIME"].to_string(index=False))
    print("\nBETA=0.9 DECISION METRICS")
    print(decision[decision["scope"]=="ALL"].to_string(index=False))
    print("\nPAIRED I1 VS I2AFS")
    for k,v in paired_summary.items():
        print(k,v)

    outputs={
        "pointwise_joined":str(joined_path),
        "metrics":str(metrics_path),
        "decision":str(decision_path),
        "per_query_metrics":str(per_query_path),
        "paired_i1_vs_i2afs":str(pair_path),
    }
    out_manifest=OUT/"evaluation_manifest.json"
    write_json(out_manifest,{
        "status":"PHASE6_I2AFS_M2_P4_G_SEQPAR_EVALUATION_COMPLETE",
        "post_prediction_evaluation":True,
        "provider_world_id":"P4",
        "graph_id":"G_SEQPAR",
        "primary_window":"H60..H240",
        "query_count":15,
        "point_count_per_method":15*37,
        "beta":BETA,
        "i2afs_prediction_manifest_sha256":sha256_file(NEW_MANIFEST),
        "outputs":outputs,
        "output_hashes_sha256":{k:sha256_file(Path(v)) for k,v in outputs.items()},
        "paired_i1_vs_i2afs_summary":paired_summary,
        "completed_utc":utc_now_iso(),
    })
    print("\noutput",OUT)
    return out_manifest


if __name__=="__main__":
    run()
