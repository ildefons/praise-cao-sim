"""Retrospective P2 G_PAR provider-parameter and graph-trajectory diagnostics.

READ-ONLY over frozen ledgers and model selections. No simulator runs, no
provider refitting, no reweighting, no changes to frozen predictions.
Results are explanatory and cannot tune the already evaluated P2 model.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from phase5_runtime_v2 import load_phase5_contracts, sha256_file
from run_i1_m123_p2_native_comparison import ROOT, OUT, QUERIES, M3FREEZE
from evaluate_i1_m3_p2_pilot import REF

V3B=Path(__file__).resolve().parent/"results"/"03_reconstruction_v3b"
DEST=OUT/"attribution_diagnostic"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
METHODS=("WB","M1","M2","M3")
HORIZONS=(60.,120.,180.,240.)


def provider_models():
    contracts=load_phase5_contracts(Path(__file__).resolve().parent)
    world=next(w for w in contracts.battery["provider_worlds"] if w["id"]=="P2")
    fam=contracts.battery["provider_family"]
    true={
        "mean_service_time":float(fam["execution_fraction_x"])*float(world["provider_means"]["ProviderA"])/float(fam["effective_IPT"]),
        "cost_rate":float(fam["cost_rate"]),
        "service_cv":float(fam["instruction_cv"]),
    }
    rows=[]
    for provider in PROVIDERS:
        true["mean_service_time"]=float(fam["execution_fraction_x"])*float(world["provider_means"][provider])/float(fam["effective_IPT"])
        src=V3B/"P2"/provider/"v3b_candidate_quality_ranking.csv"
        ranked=pd.read_csv(src)
        models=pd.read_csv(V3B/"P2"/provider/"m3_provider_models.csv")
        cols=["candidate_id","mean_service_time","cost_rate","service_cv","weight"]
        t=ranked.merge(models[cols],on="candidate_id",how="inner",validate="one_to_one",
                       suffixes=("_ranked",""))
        if len(t)!=7:raise RuntimeError(f"{provider}: expected seven candidates")
        for r in t.itertuples(index=False):
            rec={"provider":provider,"candidate_id":r.candidate_id,
                 "quality_rank":int(r.v3b_quality_rank),
                 "rescore_rmse":float(r.rescore_rmse),
                 "gibbs_weight":float(r.weight)}
            for parameter in ("mean_service_time","cost_rate","service_cv"):
                estimate=float(getattr(r,parameter))
                truth=float(true[parameter])
                rec[parameter]=estimate
                rec["true_"+parameter]=truth
                rec["relative_error_"+parameter]=(estimate-truth)/truth
            rows.append(rec)
    return pd.DataFrame(rows)


def _validate_frozen():
    m3=json.loads(M3FREEZE.read_text())
    if m3["status"]!="FROZEN_P2_I1_M3_INDUCED_GRAPH_PREDICTION":raise RuntimeError("M3 not frozen")
    if sha256_file(QUERIES)!=m3["files"]["queries"]:raise RuntimeError("query changed")
    if sha256_file(ROOT/"m3_predictions_full343_and_nested.csv")!=m3["files"]["predictions"]:
        raise RuntimeError("M3 predictions changed")
    mm=OUT/"prediction_manifest.json"
    a=json.loads(mm.read_text())
    if a["status"]!="FROZEN_P2_G_PAR_MATCHED_QUERY_M1_M2_NATIVE_PREDICTIONS":
        raise RuntimeError("M1/M2 not frozen")
    if sha256_file(QUERIES)!=a["common_query_sha256"]:raise RuntimeError("M1/M2 queries changed")
    for name,h in a["output_sha256"].items():
        if sha256_file(OUT/name)!=h:raise RuntimeError(f"M1/M2 {name} changed")
    ref=json.loads((REF/"evaluation_manifest.json").read_text())
    if sha256_file(REF/"wb_request_ledger.csv")!=ref["wb_ledger_sha256"]:
        raise RuntimeError("WB ledger changed")


def _ledger_summary(ledger,method,member,query):
    necessary={"trajectory","request_id","completion","L","C","Q"}
    if not necessary.issubset(ledger.columns):
        raise RuntimeError(f"{method}/{member}: ledger columns missing: {necessary-set(ledger.columns)}")
    rho=float(query.rho)
    rows=[]
    for horizon in HORIZONS:
        # Match the existing decided-request and SLA convention. Completion
        # before/equal H contributes, unresolved is excluded.
        decided=ledger[ledger.completion.notna() & (ledger.completion.astype(float)<=horizon)].copy()
        ok=(decided.L<=float(query.A_G_l_max)+1e-12)&(decided.C<=float(query.A_G_c_max)+1e-12)&(decided.Q>=float(query.A_G_q_min)-1e-12)
        decided["ok"]=ok.astype(int)
        all_trajectories=pd.Index(sorted(ledger.trajectory.unique()),name="trajectory")
        counts=decided.groupby("trajectory").agg(decided=("ok","size"),satisfied=("ok","sum")).reindex(all_trajectories,fill_value=0)
        counts["fraction"]=np.where(counts.decided>0,counts.satisfied/np.maximum(counts.decided,1),1.)
        rows.append({
            "method":method,"member":member,"rho":rho,"H":horizon,
            "n_trajectories":len(all_trajectories),
            "requests_decided_mean":float(counts.decided.mean()),
            "zero_decision_fraction":float((counts.decided==0).mean()),
            "compliance_mean":float(counts.fraction.mean()),
            "compliance_std":float(counts.fraction.std(ddof=0)),
            "compliance_q10":float(counts.fraction.quantile(.1)),
            "compliance_q50":float(counts.fraction.quantile(.5)),
            "compliance_q90":float(counts.fraction.quantile(.9)),
            "sigma_empirical":float((counts.fraction>=rho-1e-12).mean()),
            "completed_latency_mean":float(decided.L.mean()) if len(decided) else np.nan,
            "completed_cost_mean":float(decided.C.mean()) if len(decided) else np.nan,
            "completed_request_pass_fraction":float(ok.mean()) if len(ok) else np.nan,
        })
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",action="store_true")
    args=ap.parse_args()
    _validate_frozen()
    parameters=provider_models()
    if not args.run:
        print("P2_PROVIDER_GRAPH_ATTRIBUTION_PREFLIGHT_PASS")
        print("3 providers x 7 models; WB/M1/27 M2/343 M3 graph ledgers")
        return
    q=pd.read_csv(QUERIES)
    if len(q)!=5:raise RuntimeError("expected 5 graph regions")
    paths=[("WB",0,REF/"wb_request_ledger.csv"),
           ("M1",1,OUT/"ledgers"/"M1.csv")]
    paths += [("M2",j,OUT/"ledgers"/f"M2_R{j:02d}.csv") for j in range(1,28)]
    paths += [("M3",j,ROOT/"ledgers"/f"M3_R{j:03d}.csv") for j in range(1,344)]
    frames=[]
    for k,(method,j,path) in enumerate(paths,1):
        if not path.is_file():raise FileNotFoundError(path)
        ledger=pd.read_csv(path)
        for query in q.itertuples(index=False):
            frames.extend(_ledger_summary(ledger,method,j,query))
        if k%50==0:print(f"Attribution ledgers {k}/{len(paths)}",flush=True)
    details=pd.DataFrame(frames)
    if details.groupby(["method","member","rho"]).H.nunique().min()!=4:
        raise RuntimeError("incomplete time grid")
    # Validation: reproduce frozen diagonal point estimates at 4 horizons.
    m1=pd.read_csv(OUT/"m1_predictions.csv")
    m2=pd.read_csv(OUT/"m2_predictions.csv")
    m3=pd.read_csv(ROOT/"m3_predictions_full343_and_nested.csv")
    weight_support=pd.read_csv(V3B/"P2"/"m3_joint_support_343.csv")
    w=dict(zip(weight_support.joint_rank.astype(int),weight_support.joint_weight.astype(float)))
    m3_details=details[details.method=="M3"].copy()
    m3_details["weighted"]=m3_details.apply(lambda r:r.sigma_empirical*w[int(r.member)],axis=1)
    m3aggregate=m3_details.groupby(["rho","H"],as_index=False).weighted.sum()
    for label,pred,measured in [
        ("M1",m1,details[details.method=="M1"].rename(columns={"sigma_empirical":"reproduced"})),
        ("M2",m2,details[details.method=="M2"].groupby(["rho","H"],as_index=False).sigma_empirical.mean().rename(columns={"sigma_empirical":"reproduced"})),
        ("M3",m3[m3.method_id=="M3_FULL343"],m3aggregate.rename(columns={"weighted":"reproduced"})),
    ]:
        merged=pred.merge(measured[["rho","H","reproduced"]],on=["rho","H"],validate="one_to_one")
        if len(merged)!=20 or not np.allclose(merged.sigma_hat,merged.reproduced,atol=1e-12,rtol=0):
            raise RuntimeError(f"{label} diagnostic does not reproduce frozen sigma")
    DEST.mkdir(parents=True,exist_ok=True)
    parameters.to_csv(DEST/"provider_candidate_parameter_errors.csv",index=False)
    details.to_csv(DEST/"graph_member_trajectory_statistics.csv",index=False)
    wb=details[details.method=="WB"][["rho","H","sigma_empirical","compliance_mean","requests_decided_mean"]]
    full=m3aggregate.merge(wb,on=["rho","H"])
    full["m3_error"]=full.weighted-full.sigma_empirical
    full.to_csv(DEST/"m3_vs_wb_mechanism_summary.csv",index=False)
    manifest={
        "status":"P2_G_PAR_POSTHOC_PROVIDER_GRAPH_ATTRIBUTION_COMPLETE",
        "read_only_input":True,"wb_used_only_for_analysis":True,
        "cannot_identify_causal_error_contributions_without_interventions":True,
        "limitations":[
            "provider parameter error is privileged diagnostic, not reconstruction target",
            "member-level graph N often too small for trustworthy individual statistics",
            "mean request-level compliance is not graph survival probability",
            "completion-conditioned latency/cost statistics may have selection bias",
        ],
        "files_sha256":{p.name:sha256_file(p) for p in DEST.glob("*.csv")},
    }
    (DEST/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("P2_G_PAR_PROVIDER_GRAPH_ATTRIBUTION_COMPLETE")
    print("PARAMETER RMSE RANK1 BY PROVIDER:")
    print(parameters[parameters.quality_rank==1][["provider","rescore_rmse","relative_error_mean_service_time","relative_error_cost_rate","relative_error_service_cv"]].to_string(index=False))
    print("GRAPH MECHANISM SUMMARY:")
    print(full.to_string(index=False))


if __name__=="__main__":
    main()
