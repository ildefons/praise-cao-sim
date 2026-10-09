"""Matched four-way evaluation: I1-strong, I2AFS, I2b-v1, I2b-v2."""
from __future__ import annotations

import zipfile
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

METHODS={
    "I1STRONG_M2":{
        "pred":HERE/"results"/"19_i1strong_m2_p4_g_seqpar"/"i1strong_m2_predictions.csv",
        "manifest":HERE/"results"/"19_i1strong_m2_p4_g_seqpar"/"prediction_manifest.json",
        "status":"PHASE6_I1STRONG_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
    },
    "I2AFS_M2":{
        "pred":HERE/"results"/"15_i2afs_m2_p4_g_seqpar"/"i2afs_m2_predictions.csv",
        "manifest":HERE/"results"/"15_i2afs_m2_p4_g_seqpar"/"prediction_manifest.json",
        "status":"PHASE6_I2AFS_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
    },
    "I2B_M2":{
        "pred":HERE/"results"/"25_i2b_m2_p4_g_seqpar"/"i2b_m2_predictions.csv",
        "manifest":HERE/"results"/"25_i2b_m2_p4_g_seqpar"/"prediction_manifest.json",
        "status":"PHASE6_I2B_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
    },
    "I2BVAR_M2":{
        "pred":HERE/"results"/"29_i2bvar_m2_p4_g_seqpar"/"i2bvar_m2_predictions.csv",
        "manifest":HERE/"results"/"29_i2bvar_m2_p4_g_seqpar"/"prediction_manifest.json",
        "status":"PHASE6_I2BVAR_M2_P4_G_SEQPAR_PREDICTION_COMPLETE",
    },
}
OUT=HERE/"results"/"30_i1strong_i2afs_i2b_i2bvar_matched_evaluation"


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
    if len(p)!=15*37:
        raise RuntimeError("reference support invalid")
    return p


def _qmeta():
    q=pd.read_csv(P5_QUERIES)[["query_id","regime","rho"]].drop_duplicates()
    if len(q)!=15:
        raise RuntimeError("expected 15 frozen queries")
    return q


def _load_method(name,spec,ref,qmeta):
    p=pd.read_csv(spec["pred"])
    p=p[(p["H"].astype(float)>=60.0)&(p["H"].astype(float)<=240.0)].copy()
    if len(p)!=555:
        raise RuntimeError(f"{name}: expected 555 points")
    base=ref[["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]].drop_duplicates()
    out=base.merge(
        p[["query_id","H","sigma_hat"]],
        on=["query_id","H"],how="inner",validate="one_to_one"
    ).merge(qmeta,on="query_id",how="left",validate="many_to_one")
    out["method"]=name
    return out


def _paired(joined,baseline,challenger):
    a=joined[joined["method"]==baseline][
        ["query_id","H","sigma_hat","sigma_wb","regime"]
    ].rename(columns={"sigma_hat":"sigma_baseline"})
    b=joined[joined["method"]==challenger][
        ["query_id","H","sigma_hat"]
    ].rename(columns={"sigma_hat":"sigma_challenger"})
    pair=a.merge(b,on=["query_id","H"],validate="one_to_one")
    pair["adv"]=(
        (pair["sigma_baseline"]-pair["sigma_wb"]).abs()
        -(pair["sigma_challenger"]-pair["sigma_wb"]).abs()
    )
    rows=[]
    for scope,regime,g in [("ALL","ALL",pair)]+[
        ("REGIME",str(r),gg) for r,gg in pair.groupby("regime",sort=False)
    ]:
        adv=g["adv"].astype(float)
        rows.append({
            "baseline":baseline,
            "challenger":challenger,
            "scope":scope,
            "regime":regime,
            "n_points":int(len(g)),
            "challenger_better_points":int((adv>0).sum()),
            "ties":int(np.isclose(adv,0.0,atol=1e-15,rtol=0.0).sum()),
            "baseline_better_points":int((adv<0).sum()),
            "mean_challenger_abs_error_advantage":float(adv.mean()),
            "median_challenger_abs_error_advantage":float(adv.median()),
        })
    return rows


def run():
    for name,spec in METHODS.items():
        if not spec["manifest"].is_file():
            raise FileNotFoundError(spec["manifest"])
        if read_json(spec["manifest"]).get("status")!=spec["status"]:
            raise RuntimeError(f"{name}: prediction manifest not complete")

    ref=_reference()
    qmeta=_qmeta()
    joined=pd.concat(
        [_load_method(name,spec,ref,qmeta) for name,spec in METHODS.items()],
        ignore_index=True,
    )

    metrics=[]
    decisions=[]
    for method,g in joined.groupby("method",sort=False):
        metrics.append({"scope":"ALL","regime":"ALL","method":method,**_metrics(g)})
        decisions.append({"scope":"ALL","regime":"ALL","method":method,**_decision(g)})
        for regime,gg in g.groupby("regime",sort=False):
            metrics.append({"scope":"REGIME","regime":str(regime),"method":method,**_metrics(gg)})
            decisions.append({"scope":"REGIME","regime":str(regime),"method":method,**_decision(gg)})
    metrics=pd.DataFrame(metrics)
    decisions=pd.DataFrame(decisions)

    pairs=[]
    for baseline,challenger in (
        ("I1STRONG_M2","I2BVAR_M2"),
        ("I2B_M2","I2BVAR_M2"),
        ("I2AFS_M2","I2BVAR_M2"),
        ("I1STRONG_M2","I2B_M2"),
        ("I1STRONG_M2","I2AFS_M2"),
    ):
        pairs.extend(_paired(joined,baseline,challenger))
    paired=pd.DataFrame(pairs)

    per_query=[]
    for (method,qid),g in joined.groupby(["method","query_id"],sort=True):
        rec=g.iloc[0]
        per_query.append({
            "method":method,
            "query_id":str(qid),
            "regime":str(rec["regime"]),
            "rho":float(rec["rho"]),
            **_metrics(g),
        })
    per_query=pd.DataFrame(per_query)

    OUT.mkdir(parents=True,exist_ok=True)
    outputs={
        "pointwise_joined":OUT/"pointwise_joined.csv",
        "metrics":OUT/"metrics.csv",
        "decisions":OUT/"decision_beta090.csv",
        "paired_summary":OUT/"paired_summary.csv",
        "per_query":OUT/"per_query_metrics.csv",
    }
    joined.to_csv(outputs["pointwise_joined"],index=False)
    metrics.to_csv(outputs["metrics"],index=False)
    decisions.to_csv(outputs["decisions"],index=False)
    paired.to_csv(outputs["paired_summary"],index=False)
    per_query.to_csv(outputs["per_query"],index=False)

    manifest=OUT/"evaluation_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_I1STRONG_I2AFS_I2B_I2BVAR_MATCHED_EVALUATION_COMPLETE",
        "matched_reconstruction_and_graph_control":True,
        "provider_world_id":"P4",
        "graph_id":"G_SEQPAR",
        "primary_window":"H60..H240",
        "query_count":15,
        "point_count_per_method":555,
        "beta":BETA,
        "prediction_manifest_sha256":{k:sha256_file(v["manifest"]) for k,v in METHODS.items()},
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    })

    bundle=OUT/"i2bvar_matched_evaluation_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in list(outputs.values())+[manifest]:
            z.write(p,arcname=p.name)

    print("PHASE6_I1STRONG_I2AFS_I2B_I2BVAR_MATCHED_EVALUATION_PASS")
    print("\nALL-POINT METRICS")
    print(metrics[metrics["scope"]=="ALL"].to_string(index=False))
    print("\nBY-REGIME METRICS")
    print(metrics[metrics["scope"]=="REGIME"].to_string(index=False))
    print("\nBETA=0.9 DECISION METRICS")
    print(decisions[decisions["scope"]=="ALL"].to_string(index=False))
    print("\nPAIRED COMPARISONS")
    print(paired.to_string(index=False))
    print("\nUPLOAD BUNDLE",bundle)
    print("output",OUT)
    return manifest


if __name__=="__main__":
    run()
