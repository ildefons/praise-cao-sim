"""Bounded P2 reconstruction diagnosis; privileged, retrospective, no refitting.

Stage 1 (default): read-only audit of 7x25 trial history and frozen N100
candidate rescore/replay. Stage 2 (--probe): N100 rescore + replay for a
small, predeclared one-at-a-time perturbation set around generating theta.
Never edits frozen Phase-5 artifacts or uses graph WB.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from audit_p2_true_parameter_i1_fidelity import HERE, OUT as TRUTH_OUT
from run_phase5_provider_reconstruction_v3 import (
    PROVIDERS, _load_public_card, _domain_row, _bounds,
    _evaluate_candidate, _seed_tuple, SEEDS
)
from phase5_runtime_v2 import load_phase5_contracts, read_json, sha256_file

V3=HERE/"results"/"03_reconstruction_v3"/"P2"
OUT=HERE/"results"/"p2_bounded_reconstruction_diagnostic"
SCALES=(0.8,1.2)
PARAMS=("mean_service_time","cost_rate","service_cv")


def truth_parameters(contracts,provider):
    fam=contracts.battery["provider_family"]
    w=next(w for w in contracts.battery["provider_worlds"] if w["id"]=="P2")
    return {
        "mean_service_time":float(fam["execution_fraction_x"])*float(w["provider_means"][provider])/float(fam["effective_IPT"]),
        "cost_rate":float(fam["cost_rate"]),
        "service_cv":float(fam["instruction_cv"])
    }


def audit(contracts):
    rows=[]
    for provider in PROVIDERS:
        truth=truth_parameters(contracts,provider)
        domain=_bounds(_domain_row("P2",provider))
        cand=pd.read_csv(V3/provider/"v3_candidates_rescore.csv")
        replay=pd.read_csv(V3/provider/"v3_candidates_replay.csv")
        candidates=cand.merge(replay[["candidate_id","replay_rmse"]],
                              on="candidate_id",validate="one_to_one")
        trials=[]
        for fit in range(1,8):
            t=pd.read_csv(V3/provider/"fits"/f"fit_{fit}"/"trials.csv")
            t["fit_index"]=fit
            trials.append(t)
        t=pd.concat(trials,ignore_index=True)
        if len(candidates)!=7 or t.fit_index.nunique()!=7:
            raise RuntimeError(f"{provider}: expected 7 candidate fits and 7 trial histories")
        if len(t)!=175:
            raise RuntimeError(f"{provider}: expected 7x25 trials, found {len(t)}")
        for k in PARAMS:
            lo=float(getattr(domain,k+"_lower"));hi=float(getattr(domain,k+"_upper"))
            if not lo<=truth[k]<=hi:raise RuntimeError(f"{provider}: truth outside {k} search bounds")
        for c in (candidates,t):
            for k in PARAMS:
                c["rel_"+k]=(c[k]-truth[k])/truth[k]
        for row in t.itertuples(index=False):
            rows.append({"provider":provider,"fit_index":int(row.fit_index),
                         "trial_number":int(row.trial_number),
                         "search_rmse":float(row.search_rmse),
                         **{k:float(getattr(row,k)) for k in PARAMS},
                         **{"rel_"+k:float(getattr(row,"rel_"+k)) for k in PARAMS}})
        best=candidates.loc[candidates.rescore_rmse.idxmin()]
        print(f"{provider}: trials={len(t)}, search min={t.search_rmse.min():.5f}, "
              f"best N100={best.rescore_rmse:.5f}, replay={best.replay_rmse:.5f}, "
              f"truth-nearest mu rel={t.rel_mean_service_time.abs().min():.3f}")
    OUT.mkdir(parents=True,exist_ok=True)
    df=pd.DataFrame(rows)
    df.to_csv(OUT/"frozen_trial_history_audit.csv",index=False)
    return df


def probe(contracts):
    registry=read_json(SEEDS)
    banks={name:_seed_tuple(registry["provider_reconstruction"][key]) for name,key in
           [("rescore","common_rescore"),("replay","common_replay")]}
    rows=[]
    for provider in PROVIDERS:
        truth=truth_parameters(contracts,provider)
        metadata,public,_=_load_public_card("P2",provider)
        bounds=_bounds(_domain_row("P2",provider))
        configurations=[("TRUE",truth)]
        for k in PARAMS:
            for scale in SCALES:
                alt=dict(truth);alt[k]*=scale
                if not float(getattr(bounds,k+"_lower"))<=alt[k]<=float(getattr(bounds,k+"_upper")):
                    raise RuntimeError(f"{provider}: perturbation outside frozen {k} bounds")
                configurations.append((f"{k}_x{scale:g}",alt))
        for label,theta in configurations:
            for bank,seeds in banks.items():
                metrics,_,_= _evaluate_candidate(
                    candidate=theta,metadata=metadata,public_surface=public,seeds=seeds)
                rows.append({"provider":provider,"variant":label,"bank":bank,
                             "n":len(seeds),"rmse":metrics["rmse"],
                             "mae":metrics["mae"],"bias":metrics["bias"],
                             **theta})
            print(f"{provider}: {label} completed",flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT/"truth_neighborhood_sensitivity.csv",index=False)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--probe",action="store_true",
                    help="Run 7 parameter configurations x 2 N100 banks x 3 providers")
    args=ap.parse_args()
    contracts=load_phase5_contracts(HERE)
    df=audit(contracts)
    if args.probe:
        probe(contracts)
    files=["frozen_trial_history_audit.csv"]
    if args.probe:files.append("truth_neighborhood_sensitivity.csv")
    (OUT/"manifest.json").write_text(json.dumps({
        "status":"P2_BOUNDED_RECONSTRUCTION_AUDIT_COMPLETE",
        "privileged_truth_retrospective_only":True,
        "frozen_predictions_modified":False,
        "trial_count":len(df),
        "probe_executed":bool(args.probe),
        "probe_configurations_per_provider":7,
        "probe_banks":["rescore","replay"],
        "files_sha256":{name:sha256_file(OUT/name) for name in files}
    },indent=2)+"\n")
    print("P2_BOUNDED_RECONSTRUCTION_DIAGNOSTIC_COMPLETE")


if __name__=="__main__":
    main()
