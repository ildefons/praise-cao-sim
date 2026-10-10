"""P4/G_SEQPAR rank-1 2^3 provider factorial diagnostic for I2b-v3/v4.

Reuse frozen true, six single replacements, and rank-1 all-reconstructed curves.
Simulate only six double replacements, each with matched 100 graph seeds.
Diagnostic intervention, never optimization. Checkpoint graph ledgers.
"""
from __future__ import annotations
import argparse,sys,time,zipfile
from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
P5=HERE.parent/"phase5";P3=HERE.parent/"phase3"
for p in (P5,P3):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from phase5_runtime_v2 import load_phase5_contracts,graph_record,read_json,write_json,sha256_file,utc_now_iso,git_head
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase5_graph_prediction_v3b_fullsupport import _simulation_payload,_execute_payloads,_validate_complete_ledger,_member_curves,_horizons,_query_definitions
from run_phase6_provider_isolation_p4_g_seqpar_v1 import candidate
from run_phase6_i2bv4_six_way_matched_evaluation import _reference,_qmeta,_metrics,_decision
ROOT=HERE/"results"/"42_provider_factorial_p4_g_seqpar"
ISOLATION=HERE/"results"/"41_provider_isolation_p4_g_seqpar"/"provider_isolation_pointwise.csv"
KNOWN=HERE/"results"/"39_known_provider_p4_g_seqpar_control"/"known_provider_predictions.csv"
GRAPH_CFG=P5/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEED_CFG=P5/"config_phase5_seed_registry_v3b_fullsupport.json"
MEMBERS={"I2B_V3":HERE/"results"/"33_i2b_hierarchical_matched_evaluation"/"i2bhier_m2_member_curves.csv",
         "I2B_V4":HERE/"results"/"37_i2b_v4_m2_p4_g_seqpar"/"i2bv4_m2_member_curves.csv"}
P=("ProviderA","ProviderB","ProviderC");METHODS=("I2B_V3","I2B_V4")
BITS=("000","100","010","001","110","101","011","111")
EXPECTED_KEYS=["query_id","H"]
def read_curve(df,column):
    x=df[EXPECTED_KEYS+[column]].copy()
    if x.duplicated(EXPECTED_KEYS).any() or len(x)!=15*49:
        raise RuntimeError(f"expected unique 15x49 curve for {column}; got {len(x)}")
    return x.rename(columns={column:"sigma_hat"})
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    if args.workers<1:raise ValueError("workers must be >=1")
    ROOT.mkdir(parents=True,exist_ok=True)
    iso=pd.read_csv(ISOLATION)
    known=read_curve(pd.read_csv(KNOWN),"sigma_hat")
    contracts=load_phase5_contracts(P5)
    graph=graph_record(contracts,"G_SEQPAR")
    truth=_hidden_surrogates(contracts,"P4")
    bank=read_json(SEED_CFG)["graph_prediction"]["M1_M2_common_bank"]
    seeds=list(range(int(bank["start"]),int(bank["end_inclusive"])+1))
    if len(seeds)!=100:raise RuntimeError("expected 100 common graph seeds")
    queries=_query_definitions("P4__G_SEQPAR");horizons=_horizons(read_json(GRAPH_CFG))
    curves={};tasks=[];provenance=[]
    for method in METHODS:
        models={};ids={}
        for p in P:
            ids[p],models[p],_=candidate(method,p)
        curves[(method,"000")]=known
        for idx,p in enumerate(P):
            bits="".join("1" if k==idx else "0" for k in range(3))
            g=iso[(iso.method==method)&(iso.replaced_provider==p)]
            if len(g)!=555:raise RuntimeError(f"single intervention missing {method}/{p}")
            # isolate script includes only H 60..240; retain this as its valid evaluation domain.
            curves[(method,bits)]=g[EXPECTED_KEYS+["sigma_hat"]].copy()
        # Reuse existing rank-1 all-reconstructed joint model, verify candidate IDs.
        m=pd.read_csv(MEMBERS[method])
        g=m[m.joint_rank.astype(int)==1].copy()
        if len(g)!=735:raise RuntimeError(f"rank-1 curve size changed for {method}")
        for p in P:
            if set(g[p+"_candidate_id"].astype(str))!={ids[p]}:
                raise RuntimeError(f"rank-1 candidate ID mismatch for {method}/{p}")
        curves[(method,"111")]=read_curve(g,"sigma_member")
        provenance.append(dict(method=method,bits="111",source=str(MEMBERS[method]),source_sha256=sha256_file(MEMBERS[method])))
        for i,j in combinations(range(3),2):
            bits="".join("1" if k in (i,j) else "0" for k in range(3))
            label=f"{method}_{bits}"
            s={p:(models[p] if bits[k]=="1" else truth[p]) for k,p in enumerate(P)}
            ledger=ROOT/"ledgers"/f"{label}.csv"
            tasks.append(_simulation_payload(cell_root=ROOT,graph_id="G_SEQPAR",graph_ast=graph["ast"],
                variant_id=label,surrogates=s,seeds=seeds,ledger_path=ledger,contracts=contracts))
            provenance.append(dict(method=method,bits=bits,source=str(ledger),source_sha256="validated_after_run"))
    start=time.perf_counter()
    _execute_payloads(tasks,workers=args.workers,label="PHASE6 RANK1 PROVIDER FACTORIAL")
    for method in METHODS:
        for bits in ("110","101","011"):
            ledger=ROOT/"ledgers"/f"{method}_{bits}.csv"
            l=_validate_complete_ledger(ledger,seeds)
            member=_member_curves(ledger=l,queries=queries,horizons=horizons,
                method_id=f"{method}_{bits}",rank=1,graph_n=100,joint_weight=1.0,
                candidate_ids={p:"INTERVENED" if bits[k]=="1" else "GENERATING_PROVIDER" for k,p in enumerate(P)})
            curves[(method,bits)]=read_curve(member,"sigma_member")
    reference=_reference()[["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]]
    qmeta=_qmeta()
    records=[];contrasts=[];summary=[]
    for method in METHODS:
        indexed={}
        for bits in BITS:
            df=reference.merge(curves[(method,bits)],on=EXPECTED_KEYS,validate="one_to_one").merge(qmeta,on="query_id",validate="many_to_one")
            if len(df)!=555:raise RuntimeError(f"{method}/{bits} incomplete")
            df["method"]=method;df["bits"]=bits
            records.append(df)
            indexed[bits]=df.set_index(EXPECTED_KEYS)["sigma_hat"].sort_index()
            for regime,g in [("ALL",df)]+list(df.groupby("regime")):
                summary.append(dict(method=method,bits=bits,regime=regime,**_metrics(g),**_decision(g)))
        zero=indexed["000"]
        a=indexed["100"]-zero;b=indexed["010"]-zero;c=indexed["001"]-zero
        ab=indexed["110"]-indexed["100"]-indexed["010"]+zero
        ac=indexed["101"]-indexed["100"]-indexed["001"]+zero
        bc=indexed["011"]-indexed["010"]-indexed["001"]+zero
        abc=indexed["111"]-indexed["110"]-indexed["101"]-indexed["011"]+indexed["100"]+indexed["010"]+indexed["001"]-zero
        for name,v in [("A",a),("B",b),("C",c),("AB",ab),("AC",ac),("BC",bc),("ABC",abc)]:
            row=v.rename("contrast").reset_index().merge(qmeta,on="query_id",validate="many_to_one")
            row["method"]=method;row["term"]=name
            contrasts.append(row)
    points=pd.concat(records,ignore_index=True)
    factorial=pd.concat(contrasts,ignore_index=True)
    metrics=pd.DataFrame(summary)
    contrast_summary=factorial.groupby(["method","term","regime"],as_index=False).agg(
        mean_signed=("contrast","mean"),mean_absolute=("contrast",lambda x:float(np.abs(x).mean())),
        max_absolute=("contrast",lambda x:float(np.abs(x).max())))
    for filename,df in [("factorial_pointwise.csv",points),("factorial_interaction_pointwise.csv",factorial),
                        ("factorial_metrics.csv",metrics),("factorial_interaction_summary.csv",contrast_summary)]:
        df.to_csv(ROOT/filename,index=False)
    manifest=ROOT/"provider_factorial_manifest.json"
    write_json(manifest,dict(status="PHASE6_PROVIDER_FACTORIAL_PASS",methods=list(METHODS),
        graph="P4/G_SEQPAR",factorial_cells_per_method=8,new_double_substitutions=6,
        reuses_true_baseline=True,reuses_six_single_interventions=True,reuses_rank1_all_reconstructed=True,
        hidden_parameters_diagnostic_only=True,no_reconstruction=True,graph_seeds=100,
        interpretation="Finite differences in simulator output; interaction effects conditional on true/model endpoint choices.",
        source_manifest_sha256=sha256_file(ISOLATION),elapsed_seconds=time.perf_counter()-start,
        code_commit=git_head(),completed_utc=utc_now_iso()))
    bundle=ROOT/"provider_factorial_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("factorial_pointwise.csv","factorial_interaction_pointwise.csv","factorial_metrics.csv",
                     "factorial_interaction_summary.csv","provider_factorial_manifest.json"):
            z.write(ROOT/name,name)
    print("PHASE6_PROVIDER_FACTORIAL_PASS")
    print(metrics[metrics.regime=="Stress"].to_string(index=False))
    print("UPLOAD BUNDLE",bundle)
if __name__=="__main__":main()
