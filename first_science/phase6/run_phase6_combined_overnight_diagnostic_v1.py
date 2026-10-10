"""Single resumable Phase-6 overnight audit: known-provider residual + common provider benchmarks.

Diagnostic only, frozen candidates, no fitting or selection using WB.
Outputs separately distinguish same-reference PUBLIC FIT from held-out truth.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,time,zipfile,sys
from pathlib import Path
_IMPORT_HERE=Path(__file__).resolve().parent
for _import_dir in (_IMPORT_HERE.parent/'phase5',_IMPORT_HERE.parent/'phase3'):
    if str(_import_dir) not in sys.path:
        sys.path.insert(0,str(_import_dir))
import numpy as np
import pandas as pd
from phase5_runtime_v2 import read_json,sha256_file,write_json,utc_now_iso,git_head
from run_phase6_i2b_energy_reconstruction_p4_v1 import _load_i2b_target,_candidate_windows_from_sample_groups
from run_phase6_i2a_genuine_reconstruction_p4_v1 import _simulate_samples,empirical_w1
from i2b_energy_loss_v1 import score_candidate_windows
HERE=Path(__file__).resolve().parent
ROOT=HERE/"results"/"40_combined_provider_composition_diagnostic"
KNOWN=HERE/"results"/"39_known_provider_p4_g_seqpar_control"
METHOD_ROOTS={
"I1STRONG":"18_i1strong_reconstruction_p4",
"I2AFS":"14_i2a_fullspectrum_reconstruction_p4",
"I2B_V1":"24_i2b_energy_reconstruction_p4",
"I2B_V2":"28_i2b_varweight_reconstruction_p4",
"I2B_V3":"32_i2b_hierarchical_reconstruction_p4",
"I2B_V4":"36_i2b_v4_mean_range_reconstruction_p4"}
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SEEDS=tuple(range(70000,70100)) # new diagnostic CRN, disjoint from reconstruction search/rescore 60xxx

def residual():
    source=KNOWN/"pointwise_known_provider_vs_whitebox.csv"
    if not source.is_file():raise FileNotFoundError(source)
    d=pd.read_csv(source)
    if len(d)!=555:raise RuntimeError("expected 555 known-provider evaluation points")
    d["error"]=d.sigma_hat-d.sigma_wb
    d["abs_error"]=d.error.abs()
    d["horizon_bin"]=pd.cut(d.H,[59,100,160,240],labels=["60-100","105-160","165-240"])
    groups=[]
    for fields in (["regime"],["regime","horizon_bin"],["rho"]):
        for keys,g in d.groupby(fields,observed=True):
            row=dict(zip(fields,keys if isinstance(keys,tuple) else (keys,)))
            row.update(n=len(g),mae=float(g.abs_error.mean()),bias=float(g.error.mean()),
                       rmse=float(np.sqrt(np.mean(g.error**2))),
                       max_abs=float(g.abs_error.max()))
            groups.append(row)
    pd.DataFrame(groups).to_csv(ROOT/"known_control_residual_slices.csv",index=False)
    d.nlargest(25,"abs_error").to_csv(ROOT/"known_control_worst25.csv",index=False)
    stats=dict(n=555,mae=float(d.abs_error.mean()),bias=float(d.error.mean()),
        worst=float(d.abs_error.max()),
        note="Same true generating provider family/graph implementation as WB; independent simulation seeds cause sampling error. This audit does not identify a variance decomposition or certify MC-only residual.")
    write_json(ROOT/"known_control_residual_summary.json",stats)
    return stats

def _one(task):
    method,provider,rank,rec=task
    folder=ROOT/"checkpoints";folder.mkdir(parents=True,exist_ok=True)
    path=folder/f"{method}_{provider}_rank{rank}.json"
    fingerprint={k:float(rec[k]) for k in ("mean_service_time","cost_rate","service_cv")}
    if path.is_file():
        saved=read_json(path)
        if saved.get("parameters")==fingerprint and saved.get("seeds")==[SEEDS[0],SEEDS[-1]] and saved.get("status")=="COMPLETE":
            return saved
        raise RuntimeError(f"checkpoint conflict {path}")
    metadata,target,_=_load_i2b_target(provider)
    samples=_simulate_samples(metadata=metadata,mean_service_time=fingerprint["mean_service_time"],
        cost_rate=fingerprint["cost_rate"],service_cv=fingerprint["service_cv"],seeds=SEEDS)
    candidates=_candidate_windows_from_sample_groups(samples)
    e,_,detail=score_candidate_windows(target,candidates)
    public_marg=HERE/"results"/"22_i2b_public_representation"/"P4"/provider/"i2b_public_marginals.csv"
    marg=pd.read_csv(public_marg)
    # W1 of empirical marginals on the same 5x48 grid.
    means=[]
    for (rid,h),g in marg.groupby(["region_id","H"]):
        a=np.sort(g.compliance_fraction.to_numpy(dtype=float))
        b=np.sort(samples[(str(rid),float(h))])
        if len(a)!=100 or len(b)!=100:raise RuntimeError("marginal sample mismatch")
        means.append(float(np.mean(np.abs(a-b))))
    if len(means)!=240:raise RuntimeError("expected 240 marginal windows")
    result=dict(status="COMPLETE",method=method,provider=provider,rank=rank,
        candidate_id=str(rec["candidate_id"]),parameters=fingerprint,seeds=[SEEDS[0],SEEDS[-1]],
        common_public_i2a_w1=float(np.mean(means)),
        common_public_i2b_energy=float(e),
        candidate_n=len(SEEDS),pair_windows=len(detail),marginal_cells=len(means),
        provenance="Public-interface diagnostic; not independent provider truth nor held-out reference")
    write_json(path,result)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=3)
    args=ap.parse_args()
    if not 1<=args.workers<=6:raise ValueError("workers must be in 1..6")
    ROOT.mkdir(parents=True,exist_ok=True)
    stats=residual()
    print("KNOWN_PROVIDER_RESIDUAL_AUDIT_PASS",stats,flush=True)
    tasks=[]
    for method,directory in METHOD_ROOTS.items():
        for provider in PROVIDERS:
            files=list((HERE/"results"/directory/provider).glob("*m2_provider_models.csv"))
            if len(files)!=1:raise RuntimeError(f"Missing support {method}/{provider}")
            g=pd.read_csv(files[0])
            if len(g)!=3:raise RuntimeError("expected top-three per provider")
            for rank,rec in enumerate(g.to_dict("records"),start=1):
                tasks.append((method,provider,rank,rec))
    done=[]
    started=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        future_map={pool.submit(_one,t):t for t in tasks}
        for fut in concurrent.futures.as_completed(future_map):
            val=fut.result();done.append(val)
            print(f"COMMON PROVIDER {len(done)}/54 {val['method']} {val['provider']} rank={val['rank']} I2aW1={val['common_public_i2a_w1']:.5f} I2bE={val['common_public_i2b_energy']:.5f}",flush=True)
    if len(done)!=54:raise RuntimeError("incomplete common reference evaluation")
    raw=pd.DataFrame(done).drop(columns=["parameters","seeds","status","provenance"])
    raw.to_csv(ROOT/"candidate_common_public_fit.csv",index=False)
    summary=raw.groupby(["method","provider"],as_index=False).agg(
        mean_i2a_w1=("common_public_i2a_w1","mean"),
        best_i2a_w1=("common_public_i2a_w1","min"),
        mean_i2b_energy=("common_public_i2b_energy","mean"),
        best_i2b_energy=("common_public_i2b_energy","min"))
    summary.to_csv(ROOT/"method_provider_common_public_fit.csv",index=False)
    manifest=ROOT/"combined_diagnostic_manifest.json"
    write_json(manifest,dict(status="PHASE6_COMBINED_DIAGNOSTIC_PASS",development_evidence=True,
        code_commit=git_head(),total_candidates=54,workers=args.workers,
        simulation_seed_start=SEEDS[0],simulation_seed_end=SEEDS[-1],
        common_public_interface_fit_not_heldout_truth=True,
        known_provider_residual_audit_only=True,
        hidden_provider_parameters_read=False,graph_wb_used_for_candidate_selection=False,
        new_graph_simulation=False,wall_seconds=time.perf_counter()-started,
        completed_utc=utc_now_iso()))
    bundle=ROOT/"combined_diagnostic_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("known_control_residual_slices.csv","known_control_worst25.csv",
            "known_control_residual_summary.json","candidate_common_public_fit.csv",
            "method_provider_common_public_fit.csv","combined_diagnostic_manifest.json"):
            z.write(ROOT/name,name)
    print("PHASE6_COMBINED_DIAGNOSTIC_PASS")
    print(summary.to_string(index=False))
    print("UPLOAD BUNDLE",bundle)
if __name__=="__main__":main()
