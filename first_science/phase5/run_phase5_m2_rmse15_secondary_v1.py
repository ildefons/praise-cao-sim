"""Run the frozen secondary Phase-5 M2-RMSE15 variant.

This stage does not generate new search candidates. It consumes the read-only
RMSE15 audit, reuses exact primary-M2 confirmation/replay evidence whenever the
same candidate was already evaluated on the same frozen bank, simulates only
missing exact-candidate confirmation/replay evidence, and freezes the first
three RMSE15-confirmed members in provisional order.

No graph prediction or graph/Step-0/final-WB evidence is read.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase5_runtime_v2 import (
    base_manifest,
    canonical_provider_world_ids,
    inclusive_seed_range,
    load_phase5_contracts,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from run_phase5_m2_reconstruction_v2 import _evaluate_candidate, _load_public_card

HERE=Path(__file__).resolve().parent
PRIMARY_ROOT=HERE/"results"/"03_reconstruction"
AUDIT_ROOT=PRIMARY_ROOT/"m2_rmse15_secondary_audit"
AUDIT_SUMMARY=AUDIT_ROOT/"m2_rmse15_search_and_confirmation_audit.csv"
AUDIT_SELECTED=AUDIT_ROOT/"m2_rmse15_provisional5_candidates.csv"
AUDIT_MANIFEST=AUDIT_ROOT/"m2_rmse15_secondary_audit_manifest.json"
CONTRACT=HERE/"config_phase5_m2_rmse15_secondary_v1.json"
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CONTRACT="FROZEN_PHASE5_M2_RMSE15_SECONDARY_V1"
PASS="FROZEN_PHASE5_M2_RMSE15_PROVIDER_V1"
FAIL="FROZEN_PHASE5_M2_RMSE15_PROVIDER_NOT_INSTANTIABLE_V1"
RATIO=1.3225
TOL=1e-12


def _optional_csv(path:Path)->pd.DataFrame:
    if not path.is_file() or path.stat().st_size<=1:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _candidate_lookup(world:str,provider:str)->dict[str,dict[str,Any]]:
    pdir=PRIMARY_ROOT/world/"m2"/provider
    warm=pd.read_csv(pdir/"m2_gp_warm_start.csv")
    gp=pd.read_csv(pdir/"m2_gp_acquisitions.csv")
    cols=[
        "provider","candidate_id","source_stage",
        "z_log_mu","z_log_kappa","z_cv",
        "mean_service_time","cost_rate","service_cv","local_mse",
    ]
    obs=pd.concat([warm[cols],gp[cols]],ignore_index=True)
    obs=obs.drop_duplicates("candidate_id",keep="last")
    return {str(r["candidate_id"]):r for r in obs.to_dict("records")}


def _eval_one(
    *,
    world:str,
    provider:str,
    candidate:dict[str,Any],
    metadata,
    surface,
    seeds:tuple[int,...],
)->dict[str,float]:
    metrics=_evaluate_candidate(
        metadata=metadata,
        surface=surface,
        row=candidate,
        seeds=seeds,
    )
    return {
        "mse":float(metrics["mse"]),
        "rmse":float(metrics["rmse"]),
        "mae":float(metrics["mae"]),
        "bias":float(metrics["bias"]),
        "max_abs_error":float(metrics["max_abs_error"]),
    }


def _run_provider(world:str,provider:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    cfg=read_json(CONTRACT)
    if cfg.get("status")!=EXPECTED_CONTRACT:
        raise RuntimeError("unexpected secondary M2-RMSE15 contract status")
    if abs(float(cfg["closeness_definition"]["equivalent_mse_ratio_max"])-RATIO)>TOL:
        raise RuntimeError("secondary M2-RMSE15 ratio changed")

    out=PRIMARY_ROOT/world/"m2_rmse15"/provider
    freeze_path=out/"m2_rmse15_provider_freeze.json"
    if freeze_path.is_file():
        m=read_json(freeze_path)
        if m.get("status") in (PASS,FAIL):
            return {
                "world":world,"provider":provider,
                "status":m["status"],"wall_seconds":0.0,
                "reused_freeze":True,
            }
        raise RuntimeError(f"{world}/{provider}: unexpected existing RMSE15 freeze")

    summary=pd.read_csv(AUDIT_SUMMARY)
    sel=pd.read_csv(AUDIT_SELECTED)
    s=summary[
        (summary["provider_world_id"].astype(str)==world)
        & (summary["provider_id"].astype(str)==provider)
    ]
    if len(s)!=1:
        raise RuntimeError(f"{world}/{provider}: missing/duplicate RMSE15 audit row")
    s=s.iloc[0]
    out.mkdir(parents=True,exist_ok=True)
    started_utc=utc_now_iso()
    wall=time.perf_counter()

    provider_sel=sel[
        (sel["provider_world_id"].astype(str)==world)
        & (sel["provider_id"].astype(str)==provider)
    ].copy().sort_values("selection_order",kind="mergesort")

    if not bool(s["provisional5_possible_rmse15"]):
        reason=(
            f"only {int(s['n_search_compatible_rmse15'])} search-compatible "
            "members under frozen RMSE15 criterion; need 5"
        )
        manifest=base_manifest(
            contracts,
            stage_id="RECONSTRUCTION",
            status=FAIL,
            inputs={
                "provider_world_id":world,
                "provider_id":provider,
                "secondary_contract_sha256":sha256_file(CONTRACT),
                "secondary_audit_manifest_sha256":sha256_file(AUDIT_MANIFEST),
                "new_search_candidates_generated":False,
                "graph_prediction_used":False,
                "graph_whitebox_used":False,
                "final_whitebox_used":False,
            },
            seed_banks={},
            outputs={},
            started_utc=started_utc,
        )
        manifest["failure_reasons"]=[reason]
        manifest["n_search_compatible_rmse15"]=int(s["n_search_compatible_rmse15"])
        manifest["n_final_members"]=0
        manifest["python_wall_seconds"]=float(time.perf_counter()-wall)
        write_json(freeze_path,manifest)
        return {
            "world":world,"provider":provider,"status":FAIL,
            "wall_seconds":manifest["python_wall_seconds"],
            "reused_freeze":False,
        }

    if len(provider_sel)!=5:
        raise RuntimeError(f"{world}/{provider}: expected 5 frozen RMSE15 provisional members")

    lookup=_candidate_lookup(world,provider)
    metadata,surface,_card=_load_public_card(world,provider)
    primary_dir=PRIMARY_ROOT/world/"m2"/provider
    primary_conf=_optional_csv(primary_dir/"m2_confirmation_results.csv")
    primary_replay=_optional_csv(primary_dir/"m2_replay_results.csv")
    conf_by_id=(
        {str(r.candidate_id):r for r in primary_conf.itertuples(index=False)}
        if not primary_conf.empty else {}
    )
    replay_by_id=(
        {str(r.candidate_id):r for r in primary_replay.itertuples(index=False)}
        if not primary_replay.empty else {}
    )

    confirm_seeds=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_confirmation_CRN"]
    )
    replay_seeds=inclusive_seed_range(
        contracts.seeds["provider_reconstruction"]["M1_M2_local_replay_CRN"]
    )
    confirm_reference=float(s["confirmation_reference_mse"])
    confirm_ceiling=RATIO*confirm_reference

    conf_rows=[]
    newly_confirmed=0
    for rec in provider_sel.to_dict("records"):
        cid=str(rec["candidate_id"])
        if cid not in lookup:
            raise RuntimeError(f"{world}/{provider}: selected candidate {cid} missing from search bank")
        cand=lookup[cid]
        if cid in conf_by_id:
            old=conf_by_id[cid]
            metrics={
                "mse":float(old.confirmation_mse),
                "rmse":float(old.confirmation_rmse),
                "mae":float(old.confirmation_mae),
                "bias":float(old.confirmation_bias),
                "max_abs_error":float(old.confirmation_max_abs_error),
            }
            evidence_source="PRIMARY_M2_EXACT_CANDIDATE_REUSE"
        else:
            metrics=_eval_one(
                world=world,provider=provider,candidate=cand,
                metadata=metadata,surface=surface,seeds=confirm_seeds,
            )
            evidence_source="M2_RMSE15_NEW_CONFIRMATION"
            newly_confirmed+=1
            print(
                f"M2-RMSE15 CONFIRM {world}/{provider} "
                f"{int(rec['selection_order'])}/5 {cid} "
                f"mse={metrics['mse']:.6g} ceiling={confirm_ceiling:.6g}",
                flush=True,
            )
        conf_rows.append({
            **{k:rec[k] for k in (
                "provider_world_id","provider_id","selection_order",
                "candidate_id","source_stage","local_mse",
                "search_reference_mse","search_mse_ceiling_rmse15",
                "search_mse_ratio",
            )},
            "confirmation_mse":metrics["mse"],
            "confirmation_rmse":metrics["rmse"],
            "confirmation_mae":metrics["mae"],
            "confirmation_bias":metrics["bias"],
            "confirmation_max_abs_error":metrics["max_abs_error"],
            "confirmation_reference_mse":confirm_reference,
            "confirmation_mse_ceiling_rmse15":confirm_ceiling,
            "confirmation_mse_ratio":metrics["mse"]/confirm_reference,
            "confirmation_pass_rmse15":bool(metrics["mse"]<=confirm_ceiling+TOL),
            "evidence_source":evidence_source,
            "confirmation_n":len(confirm_seeds),
        })

    confirmation=pd.DataFrame(conf_rows).sort_values("selection_order",kind="mergesort")
    confirmation_path=out/"m2_rmse15_confirmation_results.csv"
    confirmation.to_csv(confirmation_path,index=False)

    final=confirmation[
        confirmation["confirmation_pass_rmse15"].astype(bool)
    ].head(3).copy()
    final_path=out/"m2_rmse15_final_portfolio.csv"
    replay_path=out/"m2_rmse15_replay_results.csv"
    reasons=[]
    newly_replayed=0

    if len(final)<3:
        final.to_csv(final_path,index=False)
        pd.DataFrame().to_csv(replay_path,index=False)
        status=FAIL
        reasons.append(
            f"only {len(final)} of 5 provisional members passed frozen RMSE15 confirmation; need 3"
        )
    else:
        final["final_portfolio_order"]=np.arange(1,4,dtype=int)
        final.to_csv(final_path,index=False)
        replay_rows=[]
        for rec in final.sort_values("final_portfolio_order").to_dict("records"):
            cid=str(rec["candidate_id"])
            cand=lookup[cid]
            if cid in replay_by_id:
                old=replay_by_id[cid]
                metrics={
                    "mse":float(old.replay_mse),
                    "rmse":float(old.replay_rmse),
                    "mae":float(old.replay_mae),
                    "bias":float(old.replay_bias),
                    "max_abs_error":float(old.replay_max_abs_error),
                }
                evidence_source="PRIMARY_M2_EXACT_CANDIDATE_REUSE"
            else:
                metrics=_eval_one(
                    world=world,provider=provider,candidate=cand,
                    metadata=metadata,surface=surface,seeds=replay_seeds,
                )
                evidence_source="M2_RMSE15_NEW_REPLAY"
                newly_replayed+=1
                print(
                    f"M2-RMSE15 REPLAY {world}/{provider} "
                    f"{int(rec['final_portfolio_order'])}/3 {cid} "
                    f"mse={metrics['mse']:.6g}",
                    flush=True,
                )
            replay_rows.append({
                "provider_world_id":world,
                "provider_id":provider,
                "final_portfolio_order":int(rec["final_portfolio_order"]),
                "candidate_id":cid,
                "source_stage":str(rec["source_stage"]),
                "replay_mse":metrics["mse"],
                "replay_rmse":metrics["rmse"],
                "replay_mae":metrics["mae"],
                "replay_bias":metrics["bias"],
                "replay_max_abs_error":metrics["max_abs_error"],
                "evidence_source":evidence_source,
                "replay_n":len(replay_seeds),
            })
        pd.DataFrame(replay_rows).to_csv(replay_path,index=False)
        status=PASS

    outputs={
        "confirmation_results":str(confirmation_path),
        "final_portfolio":str(final_path),
        "replay_results":str(replay_path),
    }
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status=status,
        inputs={
            "provider_world_id":world,
            "provider_id":provider,
            "secondary_contract_sha256":sha256_file(CONTRACT),
            "secondary_audit_manifest_sha256":sha256_file(AUDIT_MANIFEST),
            "primary_m2_provider_manifest_sha256":sha256_file(
                primary_dir/"m2_provider_freeze.json"
            ),
            "new_search_candidates_generated":False,
            "rmse_ratio_max":1.15,
            "equivalent_mse_ratio_max":RATIO,
            "graph_prediction_used":False,
            "graph_whitebox_used":False,
            "final_whitebox_used":False,
            "step0_whitebox_values_used":False,
            "hidden_provider_parameters_used":False,
        },
        seed_banks={
            "confirmation":dict(
                contracts.seeds["provider_reconstruction"]["M1_M2_local_confirmation_CRN"]
            ),
            "replay":dict(
                contracts.seeds["provider_reconstruction"]["M1_M2_local_replay_CRN"]
            ),
        },
        outputs=outputs,
        started_utc=started_utc,
    )
    manifest["n_search_compatible_rmse15"]=int(s["n_search_compatible_rmse15"])
    manifest["n_new_confirmation_candidates"]=newly_confirmed
    manifest["n_confirmation_pass"]=int(
        confirmation["confirmation_pass_rmse15"].astype(bool).sum()
    )
    manifest["n_final_members"]=int(len(final))
    manifest["n_new_replay_candidates"]=newly_replayed
    manifest["failure_reasons"]=reasons
    manifest["python_wall_seconds"]=float(time.perf_counter()-wall)
    write_json(freeze_path,manifest)

    return {
        "world":world,"provider":provider,"status":status,
        "new_confirmation":newly_confirmed,
        "confirmation_pass":int(
            confirmation["confirmation_pass_rmse15"].astype(bool).sum()
        ),
        "new_replay":newly_replayed,
        "wall_seconds":manifest["python_wall_seconds"],
        "reused_freeze":False,
    }


def _freeze_world(world:str)->dict[str,Any]:
    contracts=load_phase5_contracts(HERE)
    root=PRIMARY_ROOT/world/"m2_rmse15"
    rows=[]
    for provider in PROVIDERS:
        p=root/provider/"m2_rmse15_provider_freeze.json"
        if not p.is_file():
            raise FileNotFoundError(p)
        m=read_json(p)
        rows.append({
            "provider":provider,
            "status":str(m["status"]),
            "n_final_members":int(m.get("n_final_members",0)),
            "manifest_sha256":sha256_file(p),
        })
    table=pd.DataFrame(rows)
    table_path=root/"m2_rmse15_provider_status.csv"
    table.to_csv(table_path,index=False)
    ok=table["status"].eq(PASS).all()
    status=(
        "FROZEN_PHASE5_M2_RMSE15_WORLD_V1"
        if ok else
        "FROZEN_PHASE5_M2_RMSE15_WORLD_WITH_NOT_INSTANTIABLE_PROVIDER_V1"
    )
    manifest=base_manifest(
        contracts,
        stage_id="RECONSTRUCTION",
        status=status,
        inputs={
            "provider_world_id":world,
            "secondary_contract_sha256":sha256_file(CONTRACT),
            "graph_prediction_used":False,
            "graph_whitebox_used":False,
        },
        seed_banks={},
        outputs={"provider_status":str(table_path)},
        started_utc=utc_now_iso(),
    )
    manifest["provider_manifest_sha256"]={
        r["provider"]:r["manifest_sha256"] for r in rows
    }
    write_json(root/"m2_rmse15_world_freeze_manifest.json",manifest)
    return {
        "world":world,
        "instantiable":bool(ok),
        "status":status,
    }


def main()->None:
    p=argparse.ArgumentParser(description="Run frozen secondary Phase-5 M2-RMSE15")
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--world",choices=("P1","P2","P3","P4"))
    group.add_argument("--all-worlds",action="store_true")
    p.add_argument("--workers",type=int,default=4)
    args=p.parse_args()
    if args.workers<1:
        raise ValueError("--workers must be >=1")
    for required in (CONTRACT,AUDIT_SUMMARY,AUDIT_SELECTED,AUDIT_MANIFEST):
        if not required.is_file():
            raise FileNotFoundError(required)

    contracts=load_phase5_contracts(HERE)
    worlds=canonical_provider_world_ids(contracts) if args.all_worlds else (str(args.world),)
    tasks=[(w,pid) for w in worlds for pid in PROVIDERS]
    started=time.perf_counter()
    rows=[]

    if args.workers==1:
        for w,pid in tasks:
            rows.append(_run_provider(w,pid))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(_run_provider,w,pid):(w,pid) for w,pid in tasks}
            for f in concurrent.futures.as_completed(futures):
                w,pid=futures[f]
                try:
                    rows.append(f.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(
                        f"M2-RMSE15 worker failed for {w}/{pid}"
                    ) from exc

    world_rows=[_freeze_world(w) for w in worlds]
    print("\nPHASE5_M2_RMSE15_PROVIDER_SUMMARY")
    print(pd.DataFrame(rows).sort_values(["world","provider"]).to_string(index=False))
    print("\nPHASE5_M2_RMSE15_WORLD_SUMMARY")
    print(pd.DataFrame(world_rows).sort_values("world").to_string(index=False))
    print(f"stage_wall={(time.perf_counter()-started)/60:.1f} min workers={args.workers}")


if __name__=="__main__":
    main()
