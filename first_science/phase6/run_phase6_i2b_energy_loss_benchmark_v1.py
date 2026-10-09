"""Benchmark the candidate Phase-6 I2b empirical energy loss.

Consumes only the already frozen public I2b-v1 paired distributions.
No provider simulation, inverse reconstruction, graph result, white-box result,
or hidden provider parameter is used.

The scientific diagnostic destroys within-window pairing by deterministic
endpoint shuffling while preserving the two marginals exactly.  A separate
reduced-N control benchmarks search-stage scoring cost.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import (  # noqa:E402
    git_head,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from i2b_energy_loss_v1 import (  # noqa:E402
    max_sorted_marginal_error,
    prepare_public_target,
    score_candidate_windows,
    shuffled_endpoint_candidate,
    target_as_candidate,
)

CFG=HERE/"config_phase6_i2b_energy_loss_benchmark_v1.json"
REP_CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
PROTOCOL=HERE/"PHASE6_I2B_ENERGY_LOSS_BENCHMARK_PROTOCOL_2026-10-09.md"
PUBLIC_ROOT=HERE/"results"/"22_i2b_public_representation"
ROOT=HERE/"results"/"23_i2b_energy_loss_benchmark"

EXPECTED="FROZEN_PHASE6_I2B_ENERGY_LOSS_BENCHMARK_V1"
EXPECTED_REP="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
SHUFFLE_REPS=(0,1,2)
BASE_SEED=620001
TOL=1e-12


def _assert_contracts()->dict[str,Any]:
    cfg=read_json(CFG)
    rep=read_json(REP_CFG)
    sampling=read_json(SAMPLING_CFG)
    if cfg.get("status")!=EXPECTED:
        raise RuntimeError("unexpected I2b energy-benchmark status")
    if rep.get("status")!=EXPECTED_REP:
        raise RuntimeError("unexpected I2b public-representation status")
    if sampling.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected I2b temporal-sampling status")
    if tuple(int(x) for x in sampling["temporal_sampling"]["lags_s"]) != (
        20,30,40,50,75,100,150,200
    ):
        raise RuntimeError("frozen I2b lag support changed")
    if int(sampling["temporal_sampling"]["stride_s"])!=10:
        raise RuntimeError("frozen I2b stride changed")
    return cfg


def _public_pair_path(world:str,provider:str)->Path:
    return PUBLIC_ROOT/world/provider/"i2b_public_temporal_pairs.csv"


def _provider_manifest_path(world:str,provider:str)->Path:
    return PUBLIC_ROOT/world/provider/"i2b_public_representation_manifest.json"


def _validate_public_input(world:str,provider:str,path:Path)->None:
    if not path.is_file():
        raise FileNotFoundError(path)
    mp=_provider_manifest_path(world,provider)
    if not mp.is_file():
        raise FileNotFoundError(mp)
    m=read_json(mp)
    if m.get("status")!="PHASE6_I2B_PUBLIC_PROVIDER_COMPLETE":
        raise RuntimeError(f"{world}/{provider}: public provider manifest not complete")
    expected=str(m["output_hashes_sha256"]["temporal_pairs"])
    if sha256_file(path)!=expected:
        raise RuntimeError(f"{world}/{provider}: public temporal-pair hash mismatch")


def _reusable_benchmark()->Path|None:
    manifest=ROOT/"i2b_energy_loss_benchmark_manifest.json"
    if not manifest.is_file():
        return None
    m=read_json(manifest)
    if m.get("status")!="PHASE6_I2B_ENERGY_LOSS_BENCHMARK_COMPLETE":
        raise RuntimeError("existing I2b benchmark manifest has unexpected status")
    for key,p in m["outputs"].items():
        if key=="upload_bundle":
            continue
        path=Path(p)
        if not path.is_file():
            raise RuntimeError(f"frozen benchmark output missing: {path}")
        expected=m["output_hashes_sha256"].get(key)
        if expected and sha256_file(path)!=expected:
            raise RuntimeError(f"frozen benchmark output hash mismatch: {path}")
    bundle=Path(m["outputs"]["upload_bundle"])
    if not bundle.is_file():
        raise RuntimeError(f"benchmark upload bundle missing: {bundle}")
    summary=pd.read_csv(Path(m["outputs"]["provider_summary"]))
    print("PHASE6_I2B_ENERGY_LOSS_BENCHMARK_PASS [cached]")
    print(summary.to_string(index=False))
    print("\nUPLOAD BUNDLE",bundle)
    return manifest


def _zip_outputs(bundle:Path,paths:list[Path])->None:
    bundle.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p,arcname=p.name)


def run()->Path:
    cfg=_assert_contracts()
    ROOT.mkdir(parents=True,exist_ok=True)
    cached=_reusable_benchmark()
    if cached is not None:
        return cached

    started=time.perf_counter()
    provider_rows=[]
    lag_frames=[]
    input_hashes={}

    for ordinal,(world,provider) in enumerate(
        [(w,p) for w in WORLDS for p in PROVIDERS],
        start=1,
    ):
        pair_path=_public_pair_path(world,provider)
        _validate_public_input(world,provider,pair_path)
        input_hashes[f"{world}/{provider}/temporal_pairs"]=sha256_file(pair_path)

        pairs=pd.read_csv(pair_path)

        t0=time.perf_counter()
        target=prepare_public_target(pairs)
        prepare_seconds=float(time.perf_counter()-t0)

        # Algebraic self-distance invariant.
        self_candidate=target_as_candidate(target)
        t0=time.perf_counter()
        self_overall,_,self_detail=score_candidate_windows(target,self_candidate)
        self_score_seconds=float(time.perf_counter()-t0)
        self_max=float(self_detail["energy_vstat"].astype(float).max())
        if self_max>1e-10 or self_overall>1e-10:
            raise RuntimeError(
                f"{world}/{provider}: self-distance invariant failed "
                f"overall={self_overall} max={self_max}"
            )

        shuffle_scores=[]
        shuffle_seconds=[]
        marginal_errors=[]
        provider_lag_rep=[]
        for rep in SHUFFLE_REPS:
            shuffled=shuffled_endpoint_candidate(
                target,
                provider_world_id=world,
                provider_id=provider,
                base_seed=BASE_SEED,
                repetition=rep,
                candidate_n=100,
            )
            marginal_error=max_sorted_marginal_error(target,shuffled)
            marginal_errors.append(float(marginal_error))
            if marginal_error>TOL:
                raise RuntimeError(
                    f"{world}/{provider}: endpoint shuffle changed a marginal "
                    f"(max error={marginal_error})"
                )

            t0=time.perf_counter()
            overall,by_lag,_=score_candidate_windows(target,shuffled)
            elapsed=float(time.perf_counter()-t0)
            shuffle_scores.append(float(overall))
            shuffle_seconds.append(elapsed)
            if not math.isfinite(overall) or overall<=1e-12:
                raise RuntimeError(
                    f"{world}/{provider}: energy loss did not detect shuffled pairing "
                    f"(rep={rep}, score={overall})"
                )
            one=by_lag.copy()
            one.insert(0,"shuffle_repetition",int(rep))
            one.insert(0,"provider_id",provider)
            one.insert(0,"provider_world_id",world)
            provider_lag_rep.append(one)

        # Search-stage N=25 scoring benchmark.  This is computational only:
        # reduced-N marginals are not expected to match the public N=100 ones.
        n25=shuffled_endpoint_candidate(
            target,
            provider_world_id=world,
            provider_id=provider,
            base_seed=BASE_SEED,
            repetition=100,
            candidate_n=25,
        )
        t0=time.perf_counter()
        n25_score,_,_=score_candidate_windows(target,n25)
        n25_seconds=float(time.perf_counter()-t0)
        if not math.isfinite(n25_score):
            raise RuntimeError(f"{world}/{provider}: nonfinite N=25 benchmark score")

        n100_median_seconds=float(np.median(shuffle_seconds))
        projected_scoring_seconds=(
            int(cfg["runtime_benchmark"]["planned_search_trials"])*n25_seconds
            + int(cfg["runtime_benchmark"]["planned_rescore_candidates"])*n100_median_seconds
        )

        lag_rep=pd.concat(provider_lag_rep,ignore_index=True)
        lag_agg=(
            lag_rep.groupby(
                ["provider_world_id","provider_id","lag_s"],as_index=False,sort=True
            )
            .agg(
                shuffle_mean_energy_vstat=("mean_energy_vstat","mean"),
                shuffle_min_energy_vstat=("mean_energy_vstat","min"),
                shuffle_max_energy_vstat=("mean_energy_vstat","max"),
                window_count=("window_count","first"),
            )
        )
        lag_frames.append(lag_agg)

        provider_rows.append({
            "provider_world_id":world,
            "provider_id":provider,
            "target_windows":len(target.windows),
            "target_prepare_seconds":prepare_seconds,
            "self_overall_energy_vstat":float(self_overall),
            "self_max_window_energy_vstat":self_max,
            "self_score_seconds_n100":self_score_seconds,
            "shuffle_repetitions":len(SHUFFLE_REPS),
            "shuffle_mean_overall_energy_vstat":float(np.mean(shuffle_scores)),
            "shuffle_min_overall_energy_vstat":float(np.min(shuffle_scores)),
            "shuffle_max_overall_energy_vstat":float(np.max(shuffle_scores)),
            "shuffle_max_sorted_marginal_error":float(np.max(marginal_errors)),
            "score_seconds_n25":n25_seconds,
            "score_seconds_n100_median":n100_median_seconds,
            "projected_scoring_seconds_256xN25_plus_24xN100":projected_scoring_seconds,
        })
        print(
            f"I2B ENERGY {ordinal}/12 {world}/{provider} "
            f"shuffle={np.mean(shuffle_scores):.8f} "
            f"t25={n25_seconds:.3f}s t100={n100_median_seconds:.3f}s "
            f"projected={projected_scoring_seconds:.1f}s",
            flush=True,
        )

    summary=pd.DataFrame(provider_rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    lag_detail=pd.concat(lag_frames,ignore_index=True).sort_values(
        ["provider_world_id","provider_id","lag_s"],kind="mergesort"
    ).reset_index(drop=True)

    if len(summary)!=12:
        raise RuntimeError("expected 12 provider benchmark rows")
    if len(lag_detail)!=12*8:
        raise RuntimeError("expected 96 provider-lag diagnostic rows")
    if (summary["shuffle_mean_overall_energy_vstat"].astype(float)<=1e-12).any():
        raise RuntimeError("at least one provider failed temporal-pair sensitivity")
    if summary["shuffle_max_sorted_marginal_error"].astype(float).max()>TOL:
        raise RuntimeError("marginal preservation invariant failed")

    summary_path=ROOT/"i2b_energy_loss_provider_summary.csv"
    lag_path=ROOT/"i2b_energy_loss_shuffle_by_lag.csv"
    summary.to_csv(summary_path,index=False)
    lag_detail.to_csv(lag_path,index=False)

    aggregate={
        "providers":12,
        "all_self_distance_pass":bool(
            summary["self_max_window_energy_vstat"].astype(float).max()<=1e-10
        ),
        "all_shuffle_marginal_preservation_pass":bool(
            summary["shuffle_max_sorted_marginal_error"].astype(float).max()<=TOL
        ),
        "all_shuffle_pair_sensitivity_pass":bool(
            (summary["shuffle_min_overall_energy_vstat"].astype(float)>1e-12).all()
        ),
        "mean_shuffle_overall_energy_vstat":float(
            summary["shuffle_mean_overall_energy_vstat"].astype(float).mean()
        ),
        "min_provider_shuffle_overall_energy_vstat":float(
            summary["shuffle_mean_overall_energy_vstat"].astype(float).min()
        ),
        "max_provider_shuffle_overall_energy_vstat":float(
            summary["shuffle_mean_overall_energy_vstat"].astype(float).max()
        ),
        "median_score_seconds_n25":float(
            summary["score_seconds_n25"].astype(float).median()
        ),
        "median_score_seconds_n100":float(
            summary["score_seconds_n100_median"].astype(float).median()
        ),
        "median_projected_scoring_seconds_per_provider":float(
            summary[
                "projected_scoring_seconds_256xN25_plus_24xN100"
            ].astype(float).median()
        ),
        "max_projected_scoring_seconds_per_provider":float(
            summary[
                "projected_scoring_seconds_256xN25_plus_24xN100"
            ].astype(float).max()
        ),
    }

    manifest_path=ROOT/"i2b_energy_loss_benchmark_manifest.json"
    bundle_path=ROOT/"i2b_energy_loss_benchmark_bundle.zip"
    outputs={
        "provider_summary":str(summary_path),
        "shuffle_by_lag":str(lag_path),
        "upload_bundle":str(bundle_path),
    }
    manifest={
        "status":"PHASE6_I2B_ENERGY_LOSS_BENCHMARK_COMPLETE",
        "scientific_role":"public_interface_loss_sensitivity_and_cost_benchmark",
        "development_evidence":True,
        "code_commit":git_head(),
        "contracts_sha256":{
            "benchmark_config":sha256_file(CFG),
            "public_representation_config":sha256_file(REP_CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "benchmark_protocol":sha256_file(PROTOCOL),
        },
        "inputs_sha256":input_hashes,
        "loss":{
            "name":"empirical_energy_vstat_2d",
            "point_metric":"euclidean",
            "aggregation":"equal lag mean of equal window means",
            "target_self_precomputed":True,
        },
        "shuffle_diagnostic":{
            "repetitions":list(SHUFFLE_REPS),
            "base_seed":BASE_SEED,
            "marginals_preserved_exactly":True,
            "within_window_pairing_destroyed":True,
        },
        "runtime_benchmark":{
            "candidate_n_search":25,
            "candidate_n_rescore":100,
            "planned_search_trials":256,
            "planned_rescore_candidates":24,
            "timing_scope":"loss arithmetic only after public-target preparation",
        },
        "aggregate":aggregate,
        "new_provider_simulation":False,
        "provider_reconstruction_run":False,
        "graph_prediction_read":False,
        "graph_wb_read":False,
        "final_wb_read":False,
        "hidden_provider_parameters_read":False,
        "outputs":outputs,
        "output_hashes_sha256":{
            "provider_summary":sha256_file(summary_path),
            "shuffle_by_lag":sha256_file(lag_path),
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
    }
    write_json(manifest_path,manifest)
    _zip_outputs(bundle_path,[summary_path,lag_path,manifest_path])

    print("\nPHASE6_I2B_ENERGY_LOSS_BENCHMARK_PASS")
    print("\nPROVIDER SUMMARY")
    print(summary.to_string(index=False))
    print("\nAGGREGATE")
    for k,v in aggregate.items():
        print(f"{k}: {v}")
    print("\nUPLOAD BUNDLE",bundle_path)
    print("output",ROOT)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(
        description="Benchmark frozen public I2b-v1 empirical energy loss"
    )
    _=p.parse_args()
    run()


if __name__=="__main__":
    main()
