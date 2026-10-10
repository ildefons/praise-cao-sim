"""Development-only P4/G_SEQPAR known-provider graph-composition control.

Uses the hidden generating provider parameters for *diagnostic evaluation only*.
Never feeds them to reconstruction, weighting, or candidate selection.
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
from phase5_runtime_v2 import (load_phase5_contracts,graph_record,physical_cell_id,
    read_json,sha256_file,utc_now_iso,write_json,git_head)
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase5_graph_prediction_v3b_fullsupport import (
    _simulation_payload,_execute_payloads,_validate_complete_ledger,_member_curves,
    _horizons,_query_definitions)
from run_phase6_i2bv4_six_way_matched_evaluation import _reference,_qmeta,_metrics,_decision
ROOT=HERE/"results"/"39_known_provider_p4_g_seqpar_control"
CFG=P5/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=P5/"config_phase5_seed_registry_v3b_fullsupport.json"
WORLD="P4";GRAPH="G_SEQPAR";CELL="P4__G_SEQPAR"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    if args.workers<1:raise ValueError("workers must be positive")
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/"known_provider_control_manifest.json"
    if manifest.exists() and read_json(manifest).get("status")=="PHASE6_KNOWN_PROVIDER_CONTROL_PASS":
        print("PHASE6_KNOWN_PROVIDER_CONTROL_CACHED")
        return
    contracts=load_phase5_contracts(P5)
    graph=graph_record(contracts,GRAPH)
    surrogates=_hidden_surrogates(contracts,WORLD)
    bank=read_json(SEEDS)["graph_prediction"]["M1_M2_common_bank"]
    seeds=list(range(int(bank["start"]),int(bank["end_inclusive"])+1))
    if len(seeds)!=100:raise RuntimeError("expected 100 common graph seeds")
    ledger=ROOT/"known_provider_graph_ledger.csv"
    payload=_simulation_payload(cell_root=ROOT,graph_id=GRAPH,graph_ast=graph["ast"],
        variant_id="KNOWN_PROVIDER",surrogates=surrogates,seeds=seeds,
        ledger_path=ledger,contracts=contracts)
    start=time.perf_counter()
    _execute_payloads([payload],workers=args.workers,label="P4 G_SEQPAR KNOWN PROVIDER CONTROL")
    complete=_validate_complete_ledger(ledger,seeds)
    member=_member_curves(ledger=complete,queries=_query_definitions(CELL),
        horizons=_horizons(read_json(CFG)),method_id="KNOWN_PROVIDER_MEMBER",
        rank=1,graph_n=100,joint_weight=1.0,
        candidate_ids={p:"GENERATING_PROVIDER" for p in ("ProviderA","ProviderB","ProviderC")})
    # One-member control: do not call the 27-member M2 aggregator.
    required={"query_id","H","sigma_member"}
    if not required.issubset(member.columns):
        raise RuntimeError(f"known-provider curves missing {required-set(member.columns)}")
    pred=member[["query_id","H","sigma_member"]].rename(columns={"sigma_member":"sigma_hat"}).copy()
    if pred.duplicated(["query_id","H"]).any():
        raise RuntimeError("duplicate known-provider query/horizon prediction")
    pred["method_id"]="KNOWN_PROVIDER"
    pred.to_csv(ROOT/"known_provider_predictions.csv",index=False)
    ref=_reference()
    qmeta=_qmeta()
    joined=(ref[["query_id","H","sigma_wb","wb_ci_lower","wb_ci_upper"]]
      .merge(pred[["query_id","H","sigma_hat"]],on=["query_id","H"],validate="one_to_one")
      .merge(qmeta,on="query_id",validate="many_to_one"))
    joined=joined[(joined.H>=60)&(joined.H<=240)]
    if len(joined)!=555:raise RuntimeError(f"expected 555 points, got {len(joined)}")
    joined.to_csv(ROOT/"pointwise_known_provider_vs_whitebox.csv",index=False)
    rows=[]
    for regime,g in [("ALL",joined)]+list(joined.groupby("regime")):
        rows.append({"regime":regime,**_metrics(g),**_decision(g)})
    summary=pd.DataFrame(rows)
    summary.to_csv(ROOT/"known_provider_control_metrics.csv",index=False)
    write_json(manifest,{
        "status":"PHASE6_KNOWN_PROVIDER_CONTROL_PASS",
        "development_evidence":True,"world":WORLD,"graph":GRAPH,
        "diagnostic_only":True,"hidden_provider_parameters_read":True,
        "hidden_parameters_used_in_reconstruction":False,
        "graph_simulator_same_as_methods":True,
        "graph_seed_bank_same_as_m2":True,
        "graph_trajectories":100,
        "whitebox_reference_source":str(P5/"results"/"06_evaluation_v3b_fullsupport"/"pointwise_primary_joined.csv"),
        "reference_evaluation_only":True,
        "code_commit":git_head(),"elapsed_s":time.perf_counter()-start,
        "output_sha256":{p.name:sha256_file(p) for p in
          (ROOT/"known_provider_predictions.csv",ROOT/"pointwise_known_provider_vs_whitebox.csv",
           ROOT/"known_provider_control_metrics.csv")},
        "completed_utc":utc_now_iso()})
    bundle=ROOT/"known_provider_control_bundle.zip"
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("known_provider_predictions.csv","pointwise_known_provider_vs_whitebox.csv",
                     "known_provider_control_metrics.csv","known_provider_control_manifest.json"):
            z.write(ROOT/name,name)
    print("PHASE6_KNOWN_PROVIDER_CONTROL_PASS")
    print(summary.to_string(index=False))
    print("UPLOAD BUNDLE",bundle)
if __name__=="__main__":main()
