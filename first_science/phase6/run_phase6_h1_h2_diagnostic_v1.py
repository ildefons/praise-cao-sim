"""Phase-6 H1/H2 diagnostic. True providers used ONLY for evaluation."""
from __future__ import annotations
import argparse,sys,zipfile
from pathlib import Path
import concurrent.futures
import numpy as np
import pandas as pd
H=Path(__file__).resolve().parent
for p in (H.parent/"phase5",H.parent/"phase3"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from phase5_runtime_v2 import load_phase5_contracts,read_json,write_json
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase6_i2a_genuine_reconstruction_p4_v1 import _simulate_samples,_load_target,_score
from run_phase6_i2b_energy_reconstruction_p4_v1 import _load_i2b_target,_candidate_windows_from_sample_groups
from i2b_energy_loss_v1 import score_candidate_windows
R=H/"results"/"43_h1_h2_diagnostic"
COMMON=H/"results"/"40_combined_provider_composition_diagnostic"/"candidate_common_public_fit.csv"
ISO=H/"results"/"41_provider_isolation_p4_g_seqpar"/"provider_isolation_metrics.csv"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
def one(task):
    provider,block=task
    path=R/"checkpoints"/f"{provider}_{block:02}.json"
    if path.exists():
        row=read_json(path)
        if row.get("status")=="COMPLETE":return row
        raise RuntimeError("Incompatible checkpoint")
    model=_hidden_surrogates(load_phase5_contracts(H.parent/"phase5"),"P4")[provider]
    metadata,_,target_a=_load_target(provider)
    _,target_b,_=_load_i2b_target(provider)
    start=81000+block*100
    samples=_simulate_samples(metadata=metadata,mean_service_time=model.mean_service_time,
        cost_rate=model.cost_rate,service_cv=model.service_cv,
        seeds=tuple(range(start,start+100)))
    w1,_,_=_score(target_a,samples)
    energy,_,detail=score_candidate_windows(target_b,_candidate_windows_from_sample_groups(samples))
    if len(detail)!=630:raise RuntimeError("Wrong temporal support")
    row=dict(status="COMPLETE",provider=provider,block=block,seed_start=start,
        i2a_w1=float(w1),i2b_energy=float(energy))
    write_json(path,row)
    return row
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=3)
    args=parser.parse_args()
    if not 1<=args.workers<=6:raise ValueError("workers must be 1..6")
    R.mkdir(parents=True,exist_ok=True);(R/"checkpoints").mkdir(exist_ok=True)
    common=pd.read_csv(COMMON);iso=pd.read_csv(ISO)
    if len(common)!=54:raise RuntimeError("Expected 54 candidate observations")
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        fs=[pool.submit(one,(p,k)) for p in PROVIDERS for k in range(10)]
        for f in concurrent.futures.as_completed(fs):
            row=f.result();rows.append(row)
            print(f"TRUE CONTROL {len(rows)}/30 {row['provider']} block={row['block']}",flush=True)
    true=pd.DataFrame(rows).sort_values(["provider","block"])
    true.to_csv(R/"true_provider_reference_blocks.csv",index=False)
    out=[]
    for rec in common.itertuples(index=False):
        group=true[true.provider==rec.provider]
        for metric,candidate_col,true_col in (
            ("I2a_W1","common_public_i2a_w1","i2a_w1"),
            ("I2b_energy","common_public_i2b_energy","i2b_energy")):
            samples=group[true_col].to_numpy(float)
            score=float(getattr(rec,candidate_col))
            out.append(dict(provider=rec.provider,method=rec.method,rank=int(rec.rank),
                metric=metric,candidate_score=score,true_mean=float(samples.mean()),
                true_q95=float(np.quantile(samples,.95)),true_max=float(samples.max()),
                within_true_empirical_range=bool(samples.min()<=score<=samples.max()),
                passes_exploratory_q95=bool(score<=np.quantile(samples,.95))))
    comp=pd.DataFrame(out)
    comp.to_csv(R/"candidate_true_compatibility.csv",index=False)
    stress=iso[(iso.regime=="Stress")&iso.method.isin(["I2B_V3","I2B_V4"])]
    if len(stress)!=6:raise RuntimeError("Missing six isolation cases")
    wide=comp[comp["rank"]==1].pivot(index=["provider","method"],columns="metric",
        values=["candidate_score","true_mean","passes_exploratory_q95"])
    wide.columns=["_".join(x) for x in wide.columns]
    comparison=stress.merge(wide.reset_index(),on=["provider","method"],validate="one_to_one")
    comparison.to_csv(R/"graph_vs_observation.csv",index=False)
    summary=comp.groupby(["method","provider","metric"],as_index=False).agg(
        candidates=("rank","size"),compatible_screen=("passes_exploratory_q95","sum"),
        candidate_mean=("candidate_score","mean"),true_mean=("true_mean","first"),
        true_q95=("true_q95","first"))
    summary.to_csv(R/"h1_h2_screen.csv",index=False)
    write_json(R/"manifest.json",dict(status="PHASE6_H1_H2_DIAGNOSTIC_PASS",
        true_provider_trajectories=3000,reference_blocks=10,
        no_reconstruction_or_graph_simulations=True,truth_evaluation_only=True,
        q95_is_exploratory_not_calibrated=True,
        limitation="Top-3 supports and observational scores cannot establish global identifiability"))
    with zipfile.ZipFile(R/"h1_h2_bundle.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("true_provider_reference_blocks.csv","candidate_true_compatibility.csv",
                     "graph_vs_observation.csv","h1_h2_screen.csv","manifest.json"):
            z.write(R/name,name)
    print("PHASE6_H1_H2_DIAGNOSTIC_PASS",flush=True)
    print(summary.to_string(index=False),flush=True)
    print("UPLOAD BUNDLE",R/"h1_h2_bundle.zip")
if __name__=="__main__":main()
