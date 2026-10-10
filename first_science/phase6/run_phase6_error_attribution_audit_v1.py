"""Read-only Phase-6 error attribution audit; no simulation or hidden-data access."""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SOURCES={
"I1STRONG":("18_i1strong_reconstruction_p4","19_i1strong_m2_p4_g_seqpar","i1strong_m2_member_curves.csv"),
"I2AFS":("14_i2a_fullspectrum_reconstruction_p4","15_i2afs_m2_p4_g_seqpar","i2afs_m2_member_curves.csv"),
"I2B_V1":("24_i2b_energy_reconstruction_p4","25_i2b_m2_p4_g_seqpar","i2b_m2_member_curves.csv"),
"I2B_V2":("28_i2b_varweight_reconstruction_p4","29_i2bvar_m2_p4_g_seqpar","i2bvar_m2_member_curves.csv"),
"I2B_V3":("32_i2b_hierarchical_reconstruction_p4","33_i2b_hierarchical_matched_evaluation","i2bhier_m2_member_curves.csv"),
"I2B_V4":("36_i2b_v4_mean_range_reconstruction_p4","37_i2b_v4_m2_p4_g_seqpar","i2bv4_m2_member_curves.csv")}
PARS=("mean_service_time","cost_rate","service_cv")

def run(base,out):
    out.mkdir(parents=True,exist_ok=True)
    providers=[]
    for method,(recon,_,_) in SOURCES.items():
        for p in ("ProviderA","ProviderB","ProviderC"):
            matches=list((base/recon/p).glob("*m2_provider_models.csv"))
            if len(matches)!=1:raise RuntimeError(f"Missing/ambiguous provider support: {method}/{p}")
            df=pd.read_csv(matches[0])
            if len(df)!=3:raise RuntimeError("Expected exactly 3 candidates")
            for r in df.to_dict("records"):
                providers.append(dict(method=method,provider=p,candidate_id=r["candidate_id"],**{k:float(r[k]) for k in PARS}))
    pm=pd.DataFrame(providers)
    pm.to_csv(out/"candidate_parameters.csv",index=False)
    spreads=[]
    for (method,p),g in pm.groupby(["method","provider"]):
        row=dict(method=method,provider=p)
        for name in PARS:
            vals=g[name].to_numpy()
            row[name+"_min"]=float(vals.min())
            row[name+"_max"]=float(vals.max())
            row[name+"_relative_sd"]=float(vals.std()/vals.mean()) if vals.mean()!=0 else None
        spreads.append(row)
    pd.DataFrame(spreads).to_csv(out/"provider_top3_spreads.csv",index=False)
    reference=pd.read_csv(base/"38_i2b_v4_six_way_evaluation"/"pointwise_joined.csv")
    wb=reference[reference.method=="I2BV4_M2"][["query_id","H","sigma_wb"]].copy()
    if len(wb)!=555:raise RuntimeError("Unexpected graph white-box count")
    summary=[]; effects=[]; curves=[]
    for method,(_,folder,file) in SOURCES.items():
        x=pd.read_csv(base/folder/file).merge(wb,on=["query_id","H"],validate="many_to_one")
        x=x[(x.H>=60)&(x.H<=240)].copy()
        if len(x)!=27*555:raise RuntimeError(f"Unexpected joint support: {method}")
        x["method"]=method;x["error"]=x.sigma_member-x.sigma_wb
        for regime,g in x.groupby("regime"):
            m=g.pivot(index=["query_id","H"],columns="joint_rank",values="sigma_member")
            ref=g.groupby(["query_id","H"]).sigma_wb.first().reindex(m.index).to_numpy()
            val=m.to_numpy();pred=val.mean(axis=1)
            member_mae=np.mean(np.abs(val-ref[:,None]),axis=0)
            summary.append(dict(method=method,regime=regime,points=len(ref),
                ensemble_mae=float(np.abs(pred-ref).mean()),ensemble_bias=float((pred-ref).mean()),
                member_spread=float(val.std(axis=1).mean()),
                support_range_coverage=float(((ref>=val.min(axis=1))&(ref<=val.max(axis=1))).mean()),
                oracle_best_fixed_member_mae=float(member_mae.min()),
                average_member_mae=float(member_mae.mean()),
                oracle_best_fixed_rank=int(m.columns[np.argmin(member_mae)])))
            for p in ("ProviderA","ProviderB","ProviderC"):
                means=g.groupby(["query_id","H",p+"_candidate_id"]).sigma_member.mean().reset_index()
                s=means.groupby(["query_id","H"]).sigma_member.std(ddof=0)
                effects.append(dict(method=method,regime=regime,provider=p,
                    mean_between_candidate_sd=float(s.mean()),max_between_candidate_sd=float(s.max())))
        curves.append(x[["method","query_id","H","regime","joint_rank","sigma_member","sigma_wb","error",
                         "ProviderA_candidate_id","ProviderB_candidate_id","ProviderC_candidate_id"]])
    pd.DataFrame(summary).to_csv(out/"member_ensemble_decomposition.csv",index=False)
    pd.DataFrame(effects).to_csv(out/"within_support_provider_effects.csv",index=False)
    pd.concat(curves,ignore_index=True).to_csv(out/"member_vs_whitebox.csv",index=False)
    (out/"known_provider_control_readiness.json").write_text(json.dumps({
       "control_completed":False,
       "reason":"No verified graph predictions with true provider parameters in these artifacts.",
       "interpretation":"Candidate sensitivity is conditional on selected support; not global causal attribution.",
       "needed_next":"Independently verify known-provider graph execution before claiming composition fidelity."},indent=2)+"\n")
    print("PHASE6_ERROR_ATTRIBUTION_AUDIT_PASS")
    print(pd.DataFrame(summary).query("regime == 'Stress'").to_string(index=False))
    print("OUTPUT",out)
if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--results",type=Path,default=HERE/"results")
    a.add_argument("--output",type=Path,default=HERE/"diagnostics"/"error_attribution_v1")
    args=a.parse_args()
    run(args.results,args.output)
