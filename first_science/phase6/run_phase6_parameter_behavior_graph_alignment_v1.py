"""Diagnostic: parameter proximity, public behavioral fit, and composed survival error.

No simulation, no fitting, no tuning. 54 candidates evaluated in their frozen
27-member joint supports (conditional association), plus six true-background
single-provider substitutions (controlled finite-difference effect).
"""
from __future__ import annotations
import sys,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
H=Path(__file__).resolve().parent
P5=H.parent/"phase5"
if str(P5) not in sys.path:sys.path.insert(0,str(P5))
from phase5_runtime_v2 import load_phase5_contracts,write_json
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase6_i2bv4_six_way_matched_evaluation import _reference
R=H/"results"/"45_parameter_behavior_graph_alignment"
C=H/"results"/"40_combined_provider_composition_diagnostic"/"candidate_common_public_fit.csv"
ISO=H/"results"/"41_provider_isolation_p4_g_seqpar"/"provider_isolation_metrics.csv"
MEMBER_FILES={
"I1STRONG":("19_i1strong_m2_p4_g_seqpar","i1strong_m2_member_curves.csv"),
"I2AFS":("15_i2afs_m2_p4_g_seqpar","i2afs_m2_member_curves.csv"),
"I2B_V1":("25_i2b_m2_p4_g_seqpar","i2b_m2_member_curves.csv"),
"I2B_V2":("29_i2bvar_m2_p4_g_seqpar","i2bvar_m2_member_curves.csv"),
"I2B_V3":("33_i2b_hierarchical_matched_evaluation","i2bhier_m2_member_curves.csv"),
"I2B_V4":("37_i2b_v4_m2_p4_g_seqpar","i2bv4_m2_member_curves.csv")}
PS=("ProviderA","ProviderB","ProviderC")
PARAMS=("mean_service_time","cost_rate","service_cv")
RECON_ROOTS={
"I1STRONG":"18_i1strong_reconstruction_p4",
"I2AFS":"14_i2a_fullspectrum_reconstruction_p4",
"I2B_V1":"24_i2b_energy_reconstruction_p4",
"I2B_V2":"28_i2b_varweight_reconstruction_p4",
"I2B_V3":"32_i2b_hierarchical_reconstruction_p4",
"I2B_V4":"36_i2b_v4_mean_range_reconstruction_p4"}
def parameters_for(method,provider,candidate_id):
    folder=H/"results"/RECON_ROOTS[method]/provider
    files=list(folder.glob("*m2_provider_models.csv"))
    if len(files)!=1:
        raise RuntimeError(f"{method}/{provider}: expected one frozen support CSV, got {len(files)}")
    support=pd.read_csv(files[0])
    hits=support[support.candidate_id.astype(str)==str(candidate_id)]
    if len(hits)!=1:
        raise RuntimeError(f"{method}/{provider}/{candidate_id}: no unique frozen parameter record")
    return [float(hits.iloc[0][k]) for k in PARAMS]

def main():
    R.mkdir(parents=True,exist_ok=True)
    common=pd.read_csv(C)
    if len(common)!=54 or common.duplicated(["method","provider","rank"]).any():
        raise RuntimeError("Frozen common candidate table is not 54 unique candidates")
    truth=_hidden_surrogates(load_phase5_contracts(P5),"P4")
    ref=_reference()[["query_id","H","sigma_wb"]]
    ref=ref[(ref.H>=60)&(ref.H<=240)]
    rows=[]
    for method,(directory,name) in MEMBER_FILES.items():
        path=H/"results"/directory/name
        m=pd.read_csv(path)
        if m.joint_rank.nunique()!=27:raise RuntimeError(f"{method}: wrong joint support")
        m=m.merge(ref,on=["query_id","H"],validate="many_to_one")
        if len(m)!=27*555:raise RuntimeError(f"{method}: expected 27*555 rows, got {len(m)}")
        m["abs_graph_error"]=(m.sigma_member-m.sigma_wb).abs()
        m["signed_graph_error"]=m.sigma_member-m.sigma_wb
        for provider in PS:
            subset=common[(common.method==method)&(common.provider==provider)]
            for c in subset.itertuples(index=False):
                cand=m[m[provider+"_candidate_id"].astype(str)==str(c.candidate_id)]
                if len(cand)!=9*555:raise RuntimeError(f"{method}/{provider}/rank{c.rank} ID mismatch")
                true=truth[provider]
                vals=parameters_for(method,provider,c.candidate_id)
                target=[float(getattr(true,k)) for k in PARAMS]
                # Relative Euclidean distance, positive-valued dimensions; physical units made comparable.
                rel=float(np.linalg.norm([(x-y)/y for x,y in zip(vals,target)]))
                log_mu_cost=float(np.linalg.norm([np.log(vals[j]/target[j]) for j in (0,1)]))
                rows.append(dict(method=method,provider=provider,rank=int(c.rank),
                    candidate_id=str(c.candidate_id),parameter_relative_l2=rel,
                    parameter_log_mu_cost_l2=log_mu_cost,
                    abs_mu_error=abs(vals[0]-target[0]),
                    abs_cost_error=abs(vals[1]-target[1]),
                    abs_cv_error=abs(vals[2]-target[2]),
                    i2a_w1=float(c.common_public_i2a_w1),
                    i2b_energy=float(c.common_public_i2b_energy),
                    conditional_graph_mae=float(cand.abs_graph_error.mean()),
                    conditional_graph_bias=float(cand.signed_graph_error.mean()),
                    conditional_graph_stress_mae=float(cand[cand.regime=="Stress"].abs_graph_error.mean()),
                    n_graph_contexts=9,n_graph_points=int(len(cand))))
        print(f"JOINED {method} 9/9",flush=True)
    frame=pd.DataFrame(rows)
    if len(frame)!=54:raise RuntimeError("Expected 54 rows")
    frame.to_csv(R/"candidate_parameter_behavior_graph.csv",index=False)
    metrics=["parameter_relative_l2","parameter_log_mu_cost_l2","i2a_w1","i2b_energy"]
    targets=["conditional_graph_mae","conditional_graph_stress_mae"]
    stats=[]
    # With 3 candidates per provider correlations are descriptive, not inferential tests.
    for keys,g in [("ALL",frame)]+[(m,sub) for m,sub in frame.groupby("method")]:
        for x in metrics:
            for y in targets:
                stats.append(dict(scope=keys,x=x,y=y,n=len(g),
                    spearman=float(g[x].corr(g[y],method="spearman")),
                    pearson=float(g[x].corr(g[y],method="pearson"))))
    pd.DataFrame(stats).to_csv(R/"exploratory_correlations.csv",index=False)
    iso=pd.read_csv(ISO)
    sub=frame[(frame["rank"]==1)&frame.method.isin(["I2B_V3","I2B_V4"])]
    effects=iso[iso.regime=="Stress"].merge(sub,on=["method","provider"],validate="one_to_one")
    if len(effects)!=6:raise RuntimeError("Missing controlled isolation cases")
    effects.to_csv(R/"rank1_true_background_effects.csv",index=False)
    write_json(R/"manifest.json",dict(status="PHASE6_PARAMETER_BEHAVIOR_GRAPH_AUDIT_PASS",
        candidates=54,conditional_graph_contexts_per_candidate=9,
        controlled_rank1_substitutions=6,simulations=0,
        scope="P4/G_SEQPAR development-only, six methods",
        parameter_metric="Euclidean relative distance to hidden generating theta, diagnostic only",
        caveat="Conditional graph correlations are not causal, nine contexts per candidate are not independent; original selected supports are restricted and metrics not calibrated.",
        objective="Distinguish parameter proximity versus public behavioral fit as predictors of graph survival error"))
    with zipfile.ZipFile(R/"alignment_audit_bundle.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("candidate_parameter_behavior_graph.csv","exploratory_correlations.csv",
                     "rank1_true_background_effects.csv","manifest.json"):
            z.write(R/name,name)
    print("PHASE6_PARAMETER_BEHAVIOR_GRAPH_AUDIT_PASS")
    print(pd.DataFrame(stats).query("scope=='ALL'").to_string(index=False))
    print("UPLOAD BUNDLE",R/"alignment_audit_bundle.zip")
if __name__=="__main__":main()
