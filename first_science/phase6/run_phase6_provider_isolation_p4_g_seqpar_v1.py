"""Six controlled single-provider substitutions around frozen generating P4 providers.

Diagnostic-only intervention. Never uses hidden parameters for reconstruction.
All six cases use the exact same graph CRN bank as the known-provider control.
"""
from __future__ import annotations
import argparse,sys,time,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
P5=HERE.parent/"phase5"
P3=HERE.parent/"phase3"
for p in (P5,P3):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from m1_graph_simulator_v2 import GraphProviderSurrogate
from phase5_runtime_v2 import (load_phase5_contracts,graph_record,read_json,sha256_file,write_json,utc_now_iso,git_head)
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase5_graph_prediction_v3b_fullsupport import (
    _simulation_payload,_execute_payloads,_validate_complete_ledger,_member_curves,
    _horizons,_query_definitions)
from run_phase6_i2bv4_six_way_matched_evaluation import _reference,_qmeta,_metrics,_decision

ROOT=HERE/"results"/"41_provider_isolation_p4_g_seqpar"
KNOWN=HERE/"results"/"39_known_provider_p4_g_seqpar_control"/"known_provider_predictions.csv"
GRAPH_CFG=P5/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEED_CFG=P5/"config_phase5_seed_registry_v3b_fullsupport.json"
WORLD="P4";GRAPH="G_SEQPAR";CELL="P4__G_SEQPAR"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
METHOD_ROOTS={"I2B_V3":"32_i2b_hierarchical_reconstruction_p4",
              "I2B_V4":"36_i2b_v4_mean_range_reconstruction_p4"}

def candidate(method,provider):
    folder=HERE/"results"/METHOD_ROOTS[method]/provider
    paths=list(folder.glob("*m2_provider_models.csv"))
    if len(paths)!=1:raise RuntimeError(f"{method}/{provider}: expected one provider support CSV")
    g=pd.read_csv(paths[0])
    if len(g)!=3:raise RuntimeError(f"{method}/{provider}: expected exactly 3 candidates")
    r=g.iloc[0]
    return str(r.candidate_id),GraphProviderSurrogate(
        mean_service_time=float(r.mean_service_time),
        cost_rate=float(r.cost_rate),service_cv=float(r.service_cv)),sha256_file(paths[0])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=4)
    args=ap.parse_args()
    if args.workers<1:raise ValueError("workers must be positive")
    if not KNOWN.is_file():raise FileNotFoundError("Known-provider control must be completed first")
    ROOT.mkdir(parents=True,exist_ok=True)
    contracts=load_phase5_contracts(P5)
    graph=graph_record(contracts,GRAPH)
    true_models=_hidden_surrogates(contracts,WORLD)
    bank=read_json(SEED_CFG)["graph_prediction"]["M1_M2_common_bank"]
    seeds=list(range(int(bank["start"]),int(bank["end_inclusive"])+1))
    if len(seeds)!=100:raise RuntimeError("M2 seed bank changed")
    base=pd.read_csv(KNOWN)[["query_id","H","sigma_hat"]].rename(columns={"sigma_hat":"known_sigma"})
    ref=_reference()[["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]]
    qm=_qmeta()
    tasks=[];meta=[]
    for method in METHOD_ROOTS:
        for provider in PROVIDERS:
            cid,model,support_hash=candidate(method,provider)
            label=f"{method}_{provider}"
            variants=dict(true_models)
            variants[provider]=model
            ledger=ROOT/"ledgers"/f"{label}.csv"
            tasks.append(_simulation_payload(cell_root=ROOT,graph_id=GRAPH,
                graph_ast=graph["ast"],variant_id=label,surrogates=variants,
                seeds=seeds,ledger_path=ledger,contracts=contracts))
            meta.append(dict(method=method,replaced_provider=provider,candidate_id=cid,
                support_sha256=support_hash,ledger=ledger,label=label))
    start=time.perf_counter()
    _execute_payloads(tasks,workers=args.workers,label="PHASE6 SINGLE PROVIDER ISOLATION P4 G_SEQPAR")
    all_curves=[];metrics=[];effects=[]
    for item in meta:
        ledger=_validate_complete_ledger(item["ledger"],seeds)
        members=_member_curves(ledger=ledger,queries=_query_definitions(CELL),
            horizons=_horizons(read_json(GRAPH_CFG)),method_id=item["label"],rank=1,
            graph_n=100,joint_weight=1.0,
            candidate_ids={p:item["candidate_id"] if p==item["replaced_provider"] else "GENERATING_PROVIDER" for p in PROVIDERS})
        pred=members[["query_id","H","sigma_member"]].rename(columns={"sigma_member":"sigma_hat"})
        joined=ref.merge(pred,on=["query_id","H"],validate="one_to_one").merge(base,on=["query_id","H"],validate="one_to_one").merge(qm,on="query_id",validate="many_to_one")
        joined=joined[(joined.H>=60)&(joined.H<=240)].copy()
        if len(joined)!=555:raise RuntimeError("Expected 555 points")
        joined["method"]=item["method"];joined["replaced_provider"]=item["replaced_provider"]
        joined["candidate_id"]=item["candidate_id"]
        joined["delta_from_known"]=joined.sigma_hat-joined.known_sigma
        joined["abs_delta_from_known"]=joined.delta_from_known.abs()
        all_curves.append(joined)
        for regime,g in [("ALL",joined)]+list(joined.groupby("regime")):
            rec=dict(method=item["method"],provider=item["replaced_provider"],regime=regime,
                **_metrics(g),**_decision(g),
                mean_abs_effect_vs_known=float(g.abs_delta_from_known.mean()),
                mean_signed_effect_vs_known=float(g.delta_from_known.mean()),
                max_abs_effect_vs_known=float(g.abs_delta_from_known.max()))
            metrics.append(rec)
        print(f"ISOLATION {item['label']} COMPLETE",flush=True)
    pointwise=pd.concat(all_curves,ignore_index=True)
    summary=pd.DataFrame(metrics)
    pointwise.to_csv(ROOT/"provider_isolation_pointwise.csv",index=False)
    summary.to_csv(ROOT/"provider_isolation_metrics.csv",index=False)
    manifest=ROOT/"provider_isolation_manifest.json"
    write_json(manifest,dict(status="PHASE6_PROVIDER_ISOLATION_PASS",
        development_evidence=True,intervention="one rank-1 reconstructed provider; remaining two generating models",
        diagnostic_only=True,hidden_provider_parameters_read=True,
        hidden_parameters_used_for_reconstruction=False,
        matched_graph_seeds=True,trajectories_per_case=100,
        cases=6,code_commit=git_head(),elapsed_s=time.perf_counter()-start,
        known_control_sha256=sha256_file(KNOWN),
        outputs_sha256={"pointwise":sha256_file(ROOT/"provider_isolation_pointwise.csv"),
                        "metrics":sha256_file(ROOT/"provider_isolation_metrics.csv")},
        completed_utc=utc_now_iso()))
    bundle=ROOT/"provider_isolation_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("provider_isolation_pointwise.csv","provider_isolation_metrics.csv","provider_isolation_manifest.json"):
            z.write(ROOT/name,name)
    print("PHASE6_PROVIDER_ISOLATION_PASS")
    print(summary.to_string(index=False))
    print("UPLOAD BUNDLE",bundle)
if __name__=="__main__":main()
