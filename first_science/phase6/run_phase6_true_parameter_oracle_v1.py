"""Diagnostic-only true-parameter oracle for frozen I2b-v1 and I2b-v3 inverse objectives.

No true parameters are supplied to reconstruction. Evaluates frozen original
search/rescore objectives and identifies domain vs optimization vs ranking issues.
"""
from __future__ import annotations
import argparse,sys,zipfile
from pathlib import Path
import pandas as pd
H=Path(__file__).resolve().parent
for p in (H.parent/"phase3",H.parent/"phase5"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from phase5_runtime_v2 import load_phase5_contracts,read_json,write_json
from run_phase5_step0_v2 import _hidden_surrogates
from run_phase5_m2_reconstruction_v2 import _domain_row,_bounds
import run_phase6_i2b_energy_reconstruction_p4_v1 as v1
import run_phase6_i2b_hierarchical_reconstruction_p4_v1 as v3
R=H/"results"/"44_true_parameter_oracle"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
def run_one(method,provider,bank):
    folder=R/"checkpoints";folder.mkdir(exist_ok=True,parents=True)
    path=folder/f"{method}_{provider}_{bank}.json"
    if path.exists():
        rec=read_json(path)
        if rec.get("status")=="COMPLETE":return rec
        raise RuntimeError("Incompatible checkpoint")
    module=v1 if method=="I2B_V1" else v3
    cfg=module._assert_contracts()
    metadata,target,_=module._load_i2b_target(provider)
    truth=_hidden_surrogates(load_phase5_contracts(H.parent/"phase5"),"P4")[provider]
    t={"mean_service_time":float(truth.mean_service_time),"cost_rate":float(truth.cost_rate),"service_cv":float(truth.service_cv)}
    d=_domain_row("P4",provider)
    limits={}
    inside=True
    for k,val in t.items():
        lo=float(d[k+"_lower"]);hi=float(d[k+"_upper"])
        limits[k]={"lower":lo,"true":val,"upper":hi,"inside":bool(lo<=val<=hi)}
        inside=inside and lo<=val<=hi
    spec=cfg["search"] if bank=="search" else cfg["common_rescore"]
    if bank=="search":
        start=int(spec["search_seed_start"]);end=int(spec["search_seed_end_inclusive"])
    else:
        start=int(spec["seed_start"]);end=int(spec["seed_end_inclusive"])
    seeds=tuple(range(start,end+1))
    if len(seeds)!=(25 if bank=="search" else 100):raise RuntimeError("Seed protocol changed")
    if method=="I2B_V1":
        score,_=v1._score_i2b(metadata=metadata,target=target,
            mean_service_time=t["mean_service_time"],cost_rate=t["cost_rate"],
            service_cv=t["service_cv"],seeds=seeds)
    else:
        w=v3._target_weights(target)
        result=v3._score_params(metadata=metadata,target=target,weights=w,
            mu=t["mean_service_time"],cost=t["cost_rate"],cv=t["service_cv"],seeds=seeds)
        score=float(result[0]) if isinstance(result,tuple) else float(result)
    rec=dict(status="COMPLETE",method=method,provider=provider,bank=bank,
             true_parameters=t,domain=limits,true_within_domain=bool(inside),
             oracle_objective=float(score),seed_start=start,seed_end=end)
    write_json(path,rec)
    return rec
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--methods",nargs="+",choices=["I2B_V1","I2B_V3"],default=["I2B_V1","I2B_V3"])
    args=ap.parse_args()
    R.mkdir(parents=True,exist_ok=True)
    rows=[]
    for method in args.methods:
        for provider in PROVIDERS:
            for bank in ("search","rescore"):
                r=run_one(method,provider,bank)
                print(f"ORACLE {method} {provider} {bank} score={r['oracle_objective']:.8f} inside={r['true_within_domain']}",flush=True)
                rows.append(dict(method=method,provider=provider,bank=bank,
                     score=r["oracle_objective"],inside=r["true_within_domain"],
                     **{f"{k}_true":v for k,v in r["true_parameters"].items()},
                     **{f"{k}_lower":v["lower"] for k,v in r["domain"].items()},
                     **{f"{k}_upper":v["upper"] for k,v in r["domain"].items()}))
    frame=pd.DataFrame(rows)
    frame.to_csv(R/"oracle_scores_and_domains.csv",index=False)
    write_json(R/"manifest.json",dict(status="PHASE6_TRUE_PARAMETER_ORACLE_PASS",
        scope="Exact original search and rescore objectives for I2b-v1 and I2b-v3",
        true_parameters_diagnostic_only=True,graph_simulations=0,
        candidate_selection_unchanged=True,
        note="Comparison with winner scores requires auditing frozen score-column schema; do not compare objectives across distinct seed banks."))
    with zipfile.ZipFile(R/"true_parameter_oracle_bundle.zip","w",compression=zipfile.ZIP_DEFLATED) as z:
        for n in ("oracle_scores_and_domains.csv","manifest.json"):
            z.write(R/n,n)
    print("PHASE6_TRUE_PARAMETER_ORACLE_PASS",flush=True)
    print(frame.to_string(index=False),flush=True)
    print("UPLOAD BUNDLE",R/"true_parameter_oracle_bundle.zip",flush=True)
if __name__=="__main__":main()
