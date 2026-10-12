"""Retrospective true-parameter fidelity audit for frozen P2 provider I1.

Privileged truth enters ONLY this diagnostic. No fitting, ranking changes or
graph predictions. Uses the exact V3 local simulator/scorer and common seeds.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

from phase5_runtime_v2 import load_phase5_contracts, sha256_file
from run_phase5_provider_reconstruction_v3 import (
    _load_public_card, _domain_row, _bounds, _evaluate_candidate,
    _seed_tuple, SEEDS, PROVIDERS
)
from phase5_runtime_v2 import read_json

HERE=Path(__file__).resolve().parent
OUT=HERE/"results"/"p2_true_parameter_i1_fidelity_audit"
V3B=HERE/"results"/"03_reconstruction_v3b"/"P2"


def main():
    contracts=load_phase5_contracts(HERE)
    battery=contracts.battery
    family=battery["provider_family"]
    world=next(w for w in battery["provider_worlds"] if w["id"]=="P2")
    registry=read_json(SEEDS)
    banks={
        "rescore":_seed_tuple(registry["provider_reconstruction"]["common_rescore"]),
        "replay":_seed_tuple(registry["provider_reconstruction"]["common_replay"]),
    }
    rows=[]
    surfaces=[]
    inputs={}
    for provider in PROVIDERS:
        metadata,public,card=_load_public_card("P2",provider)
        params={
            "candidate_id":"RETROSPECTIVE_TRUE_PARAMETERS",
            "mean_service_time":float(family["execution_fraction_x"])*float(world["provider_means"][provider])/float(family["effective_IPT"]),
            "cost_rate":float(family["cost_rate"]),
            "service_cv":float(family["instruction_cv"]),
        }
        bounds=_bounds(_domain_row("P2",provider))
        domain_ok=all(
            float(getattr(bounds,key+"_lower"))<=params[key]<=float(getattr(bounds,key+"_upper"))
            for key in ("mean_service_time","cost_rate","service_cv")
        )
        quality=pd.read_csv(V3B/provider/"v3b_candidate_quality_ranking.csv")
        replay=pd.read_csv(HERE/"results"/"03_reconstruction_v3"/"P2"/provider/"v3_candidates_replay.csv")
        quality=quality.merge(replay[["candidate_id","replay_rmse"]],on="candidate_id",validate="one_to_one")
        inputs[provider]={
            "public_card_sha256":sha256_file(HERE/"results"/"01_i1"/"P2"/"public"/provider/"public_i1_surface.csv") if (HERE/"results"/"01_i1"/"P2"/"public"/provider/"public_i1_surface.csv").exists() else None,
            "domain_contains_truth":bool(domain_ok),
            "parameter_truth":params,
            "domain_bounds":{key:[float(getattr(bounds,key+"_lower")),float(getattr(bounds,key+"_upper"))] for key in ("mean_service_time","cost_rate","service_cv")},
        }
        for bank_name,seeds in banks.items():
            metrics,_,comparison=_evaluate_candidate(
                candidate=params,metadata=metadata,public_surface=public,seeds=seeds
            )
            best=float(quality["rescore_rmse"].min() if bank_name=="rescore" else quality["replay_rmse"].min())
            selected=quality.sort_values(["rescore_rmse","candidate_id"],kind="mergesort").iloc[0]
            selected_rmse=float(selected["rescore_rmse"] if bank_name=="rescore" else selected["replay_rmse"])
            rows.append({
                "provider":provider,"bank":bank_name,"n_trajectories":len(seeds),
                "true_rmse":metrics["rmse"],"true_mae":metrics["mae"],
                "true_bias":metrics["bias"],"true_n_points":metrics["n_points"],
                "best_candidate_rmse":best,
                "m1_selected_candidate_id":str(selected["candidate_id"]),
                "m1_selected_rmse":selected_rmse,
                "true_minus_best_rmse":metrics["rmse"]-best,
                "truth_inside_frozen_search_bounds":domain_ok,
            })
            cmp=comparison.copy()
            cmp["provider"]=provider
            cmp["bank"]=bank_name
            surfaces.append(cmp)
            print(f"{provider} {bank_name}: truth RMSE={metrics['rmse']:.6f}; best candidate RMSE={best:.6f}; M1 RMSE={selected_rmse:.6f}; truth in bounds={domain_ok}",flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    df=pd.DataFrame(rows)
    df.to_csv(OUT/"true_parameter_i1_fidelity_summary.csv",index=False)
    pd.concat(surfaces,ignore_index=True).to_csv(OUT/"true_parameter_i1_surface_comparison.csv",index=False)
    manifest={
        "status":"P2_TRUE_PARAMETER_I1_FIDELITY_RETROSPECTIVE_COMPLETE",
        "privileged_truth_used_only_for_diagnostic":True,
        "candidate_selection_unchanged":True,"graph_prediction_unchanged":True,
        "simulator":"phase3.run_m1_provider_lift_v2._simulate_and_score",
        "seed_bank_ranges":{name:[s[0],s[-1],len(s)] for name,s in banks.items()},
        "battery_sha256":contracts.hashes["battery"],
        "v3_seed_config_sha256":sha256_file(SEEDS),
        "provider_inputs":inputs,
        "outputs_sha256":{p.name:sha256_file(p) for p in OUT.glob("*.csv")},
        "interpretation_limitations":[
            "Same-seed provider simulations are a retrospective comparison, not new model selection.",
            "If true parameters fit poorly, verify equivalence of the I1 generator and reconstruction simulator.",
            "Lower RMSE at the true parameters does not alone establish statistical identifiability.",
            "The candidate bank is a finite result of an optimization procedure."
        ]
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("P2_TRUE_PARAMETER_I1_FIDELITY_AUDIT_COMPLETE")
    print(df.to_string(index=False))


if __name__=="__main__":
    main()
