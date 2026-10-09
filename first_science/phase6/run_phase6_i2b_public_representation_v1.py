"""Materialize the frozen Phase-6 I2b-v1 public representation.

I2b-v1 is self-contained:
  1) I2a empirical marginal compliance distributions at every frozen region/H;
  2) anonymous same-trajectory compliance pairs for the frozen temporal windows.

The private Phase-5 provider ledgers are read only to construct these public
objects.  No trajectory identifier, seed, request identifier, or stable
cross-window sample identifier is persisted.

No new provider simulation, provider reconstruction, graph prediction, graph
white-box, final white-box, or hidden provider parameter is read.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
import sys
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import (  # noqa:E402
    git_head,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from run_phase6_i2a_marginal_audit_v1 import (  # noqa:E402
    _compliance_samples_from_ledger,
    _publicize_i2a,
)

CFG=HERE/"config_phase6_i2b_public_representation_v1.json"
SAMPLING_CFG=HERE/"config_phase6_i2b_temporal_sampling_v1.json"
PROTOCOL=HERE/"PHASE6_I2B_PUBLIC_REPRESENTATION_PROTOCOL_2026-10-09.md"
P5_I1=PHASE5/"results"/"01_i1"
ROOT=HERE/"results"/"22_i2b_public_representation"

WORLDS=("P1","P2","P3","P4")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
EXPECTED_CFG="FROZEN_PHASE6_I2B_PUBLIC_REPRESENTATION_V1"
EXPECTED_SAMPLING="FROZEN_PHASE6_I2B_TEMPORAL_SAMPLING_V1"
TOL=1e-12


def _frozen_sampling()->tuple[int,int,tuple[int,...],int]:
    cfg=read_json(SAMPLING_CFG)
    if cfg.get("status")!=EXPECTED_SAMPLING:
        raise RuntimeError("unexpected frozen I2b temporal-sampling status")
    t=dict(cfg["temporal_sampling"])
    stride=int(t["stride_s"])
    phase=int(t["canonical_start_phase_s"])
    lags=tuple(int(x) for x in t["lags_s"])
    horizon_end=int(cfg["horizon_grid_s"]["end_inclusive"])
    if stride!=10 or phase!=5:
        raise RuntimeError("frozen I2b stride/start phase changed")
    if lags!=(20,30,40,50,75,100,150,200):
        raise RuntimeError("frozen I2b lag set changed")
    if horizon_end!=240:
        raise RuntimeError("frozen I2b horizon end changed")
    return stride,phase,lags,horizon_end


def _valid_starts(*,lag:int,stride:int,phase:int,horizon_end:int)->tuple[int,...]:
    vals=[]
    h=int(phase)
    while h+lag<=horizon_end:
        vals.append(h)
        h+=stride
    return tuple(vals)


def _expected_window_counts(lags:tuple[int,...],stride:int,phase:int,horizon_end:int)->dict[int,int]:
    return {
        int(lag):len(
            _valid_starts(
                lag=int(lag),
                stride=stride,
                phase=phase,
                horizon_end=horizon_end,
            )
        )
        for lag in lags
    }


def _publicize_temporal_pairs(
    samples:pd.DataFrame,
    *,
    world:str,
    provider:str,
    stride:int,
    phase:int,
    lags:tuple[int,...],
    horizon_end:int,
)->pd.DataFrame:
    required={"region_id","region_rho","H","trajectory_private","compliance_fraction"}
    missing=required.difference(samples.columns)
    if missing:
        raise RuntimeError(f"private compliance samples missing {sorted(missing)}")

    rows:list[dict[str,Any]]=[]
    for (region_id,region_rho),g in samples.groupby(
        ["region_id","region_rho"],sort=True
    ):
        pivot=g.pivot(
            index="trajectory_private",
            columns="H",
            values="compliance_fraction",
        ).sort_index().sort_index(axis=1)
        if pivot.shape!=(100,48):
            raise RuntimeError(
                f"{world}/{provider}/{region_id}: expected private compliance matrix (100,48), "
                f"found {pivot.shape}"
            )
        available={int(round(float(x))) for x in pivot.columns}
        if available!=set(range(5,241,5)):
            raise RuntimeError(
                f"{world}/{provider}/{region_id}: positive horizon support changed"
            )

        for lag in lags:
            for start_H in _valid_starts(
                lag=lag,
                stride=stride,
                phase=phase,
                horizon_end=horizon_end,
            ):
                end_H=start_H+lag
                a=pivot[float(start_H)].to_numpy(dtype=float)
                b=pivot[float(end_H)].to_numpy(dtype=float)
                if len(a)!=100 or len(b)!=100:
                    raise RuntimeError("temporal window does not contain N=100 paired samples")

                # The pair itself is preserved, but the private trajectory ID is
                # discarded before serialization.  Lexicographic sorting gives
                # deterministic bytes without introducing a stable identity
                # across different windows.
                pair=pd.DataFrame({
                    "compliance_start":a,
                    "compliance_end":b,
                }).sort_values(
                    ["compliance_start","compliance_end"],
                    kind="mergesort",
                ).reset_index(drop=True)

                for idx,rec in enumerate(pair.itertuples(index=False),start=1):
                    rows.append({
                        "provider_world_id":world,
                        "provider_id":provider,
                        "region_id":str(region_id),
                        "region_rho":float(region_rho),
                        "start_H":float(start_H),
                        "end_H":float(end_H),
                        "lag_s":float(lag),
                        "anonymous_pair_index":int(idx),
                        "sample_mass":0.01,
                        "compliance_start":float(rec.compliance_start),
                        "compliance_end":float(rec.compliance_end),
                    })

    out=pd.DataFrame(rows).sort_values(
        ["region_rho","lag_s","start_H","anonymous_pair_index"],
        kind="mergesort",
    ).reset_index(drop=True)

    banned={"trajectory","trajectory_private","trajectory_seed","seed","request_id"}
    if banned.intersection(out.columns):
        raise RuntimeError("private identifier leaked into public I2b pair columns")
    if ((out["compliance_start"]<-TOL)|(out["compliance_start"]>1.0+TOL)).any():
        raise RuntimeError("public I2b compliance_start outside [0,1]")
    if ((out["compliance_end"]<-TOL)|(out["compliance_end"]>1.0+TOL)).any():
        raise RuntimeError("public I2b compliance_end outside [0,1]")
    if not np.allclose(
        out["sample_mass"].astype(float).to_numpy(),
        0.01,
        rtol=0.0,
        atol=TOL,
    ):
        raise RuntimeError("public I2b sample mass changed")

    group_sizes=out.groupby(
        ["region_id","lag_s","start_H","end_H"],sort=True
    ).size()
    if len(group_sizes)==0 or set(group_sizes.astype(int).tolist())!={100}:
        raise RuntimeError("public I2b temporal windows are not all N=100")
    return out


def _validate_cardinality(
    pairs:pd.DataFrame,
    *,
    expected_by_lag:dict[int,int],
)->None:
    expected_windows_per_region=sum(expected_by_lag.values())
    if expected_windows_per_region!=126:
        raise RuntimeError(
            f"frozen temporal design expected 126 windows/region, found {expected_windows_per_region}"
        )
    n_regions=pairs["region_id"].astype(str).nunique()
    if n_regions!=5:
        raise RuntimeError(f"expected five regions, found {n_regions}")

    window_table=pairs[
        ["region_id","lag_s","start_H","end_H"]
    ].drop_duplicates()
    if len(window_table)!=5*126:
        raise RuntimeError(
            f"expected 630 temporal windows/provider, found {len(window_table)}"
        )
    if len(pairs)!=63000:
        raise RuntimeError(
            f"expected 63000 public temporal pair rows/provider, found {len(pairs)}"
        )

    observed=(
        window_table.assign(lag_int=window_table["lag_s"].astype(int))
        .groupby(["region_id","lag_int"],sort=True)
        .size()
    )
    for region in sorted(window_table["region_id"].astype(str).unique()):
        for lag,count in expected_by_lag.items():
            got=int(observed.loc[(region,int(lag))])
            if got!=int(count):
                raise RuntimeError(
                    f"{region}/lag={lag}: expected {count} windows, found {got}"
                )


def _reuse_provider_manifest(path:Path)->dict[str,Any]|None:
    if not path.is_file():
        return None
    m=read_json(path)
    if m.get("status")!="PHASE6_I2B_PUBLIC_PROVIDER_COMPLETE":
        raise RuntimeError(f"{path}: unexpected existing manifest status")
    outputs=dict(m["outputs"])
    hashes=dict(m["output_hashes_sha256"])
    for key,value in outputs.items():
        p=Path(value)
        if not p.is_file():
            raise RuntimeError(f"{path}: frozen output missing: {p}")
        if sha256_file(p)!=str(hashes[key]):
            raise RuntimeError(f"{path}: frozen output hash mismatch: {p}")
    return m


def run_provider(world:str,provider:str)->dict[str,Any]:
    out=ROOT/world/provider
    out.mkdir(parents=True,exist_ok=True)
    manifest_path=out/"i2b_public_representation_manifest.json"
    reused=_reuse_provider_manifest(manifest_path)
    if reused is not None:
        print(f"I2B PUBLIC {world}/{provider} [cached]",flush=True)
        return {
            "provider_world_id":world,
            "provider_id":provider,
            "marginal_rows":int(reused["counts"]["marginal_rows"]),
            "temporal_windows":int(reused["counts"]["temporal_windows"]),
            "temporal_pair_rows":int(reused["counts"]["temporal_pair_rows"]),
            "provider_manifest_sha256":sha256_file(manifest_path),
            "reused":True,
        }

    stride,phase,lags,horizon_end=_frozen_sampling()
    expected_by_lag=_expected_window_counts(
        lags=lags,
        stride=stride,
        phase=phase,
        horizon_end=horizon_end,
    )

    card_path=P5_I1/world/"public"/provider/"card.json"
    ledger_path=P5_I1/world/"private"/"sigma"/provider/"provider_request_ledgers.csv"
    if not card_path.is_file():
        raise FileNotFoundError(card_path)
    if not ledger_path.is_file():
        raise FileNotFoundError(ledger_path)

    metadata=read_json(card_path)
    if str(metadata["provider_id"])!=provider:
        raise RuntimeError(f"{world}/{provider}: card provider mismatch")

    ledger=pd.read_csv(ledger_path)
    samples=_compliance_samples_from_ledger(ledger,metadata=metadata)

    marginals=_publicize_i2a(samples,provider)
    marginals.insert(0,"provider_world_id",world)
    if len(marginals)!=24000:
        raise RuntimeError(
            f"{world}/{provider}: expected 24000 marginal rows, found {len(marginals)}"
        )
    if "trajectory_private" in marginals.columns:
        raise RuntimeError("private trajectory identity leaked into I2b marginal component")

    pairs=_publicize_temporal_pairs(
        samples,
        world=world,
        provider=provider,
        stride=stride,
        phase=phase,
        lags=lags,
        horizon_end=horizon_end,
    )
    _validate_cardinality(pairs,expected_by_lag=expected_by_lag)

    marginal_path=out/"i2b_public_marginals.csv"
    pair_path=out/"i2b_public_temporal_pairs.csv"
    marginals.to_csv(marginal_path,index=False)
    pairs.to_csv(pair_path,index=False)

    temporal_windows=int(
        pairs[["region_id","lag_s","start_H","end_H"]].drop_duplicates().shape[0]
    )
    manifest={
        "status":"PHASE6_I2B_PUBLIC_PROVIDER_COMPLETE",
        "scientific_role":"public_information_interface_materialization",
        "provider_world_id":world,
        "provider_id":provider,
        "code_commit":git_head(),
        "contracts_sha256":{
            "representation_config":sha256_file(CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "representation_protocol":sha256_file(PROTOCOL),
        },
        "inputs":{
            "phase5_i1_card_sha256":sha256_file(card_path),
            "phase5_private_sigma_ledger_sha256":sha256_file(ledger_path),
            "new_provider_world_simulation":False,
            "provider_reconstruction_run":False,
            "graph_prediction_read":False,
            "graph_wb_read":False,
            "final_wb_read":False,
            "hidden_provider_parameters_read":False,
        },
        "public_semantics":{
            "includes_i2a_marginals":True,
            "within_window_pairing_exposed":True,
            "trajectory_identity_used_privately":True,
            "trajectory_identity_exposed_public":False,
            "stable_cross_window_sample_identifier":False,
            "anonymous_pair_index_scope":"one temporal window only",
            "anonymous_pair_serialization":"lexicographic by compliance_start then compliance_end",
            "formal_privacy_claim":False,
            "sample_mass_per_temporal_pair":0.01,
            "stride_s":stride,
            "canonical_start_phase_s":phase,
            "lags_s":list(lags),
            "window_counts_per_region_by_lag_s":{
                str(k):int(v) for k,v in expected_by_lag.items()
            },
        },
        "counts":{
            "regions":5,
            "positive_horizons":48,
            "trajectories_in_source":100,
            "marginal_rows":int(len(marginals)),
            "temporal_windows":temporal_windows,
            "temporal_pair_rows":int(len(pairs)),
        },
        "outputs":{
            "marginals":str(marginal_path),
            "temporal_pairs":str(pair_path),
        },
        "output_hashes_sha256":{
            "marginals":sha256_file(marginal_path),
            "temporal_pairs":sha256_file(pair_path),
        },
        "completed_utc":utc_now_iso(),
    }
    write_json(manifest_path,manifest)
    print(
        f"I2B PUBLIC {world}/{provider} "
        f"marginals={len(marginals)} windows={temporal_windows} pairs={len(pairs)}",
        flush=True,
    )
    return {
        "provider_world_id":world,
        "provider_id":provider,
        "marginal_rows":int(len(marginals)),
        "temporal_windows":temporal_windows,
        "temporal_pair_rows":int(len(pairs)),
        "provider_manifest_sha256":sha256_file(manifest_path),
        "reused":False,
    }


def run_all(workers:int)->Path:
    if workers<1:
        raise ValueError("--workers must be >=1")
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("unexpected I2b public-representation config status")
    _frozen_sampling()

    ROOT.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    tasks=[(w,p) for w in WORLDS for p in PROVIDERS]
    rows=[]

    if workers==1:
        for world,provider in tasks:
            rows.append(run_provider(world,provider))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures={
                pool.submit(run_provider,world,provider):(world,provider)
                for world,provider in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                world,provider=futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    for other in futures:
                        other.cancel()
                    raise RuntimeError(
                        f"I2b public representation failed for {world}/{provider}"
                    ) from exc

    summary=pd.DataFrame(rows).sort_values(
        ["provider_world_id","provider_id"],kind="mergesort"
    ).reset_index(drop=True)
    if len(summary)!=12:
        raise RuntimeError("expected 12 provider summaries")
    if set(summary["marginal_rows"].astype(int))!={24000}:
        raise RuntimeError("unexpected I2b marginal row count")
    if set(summary["temporal_windows"].astype(int))!={630}:
        raise RuntimeError("unexpected I2b temporal window count")
    if set(summary["temporal_pair_rows"].astype(int))!={63000}:
        raise RuntimeError("unexpected I2b pair row count")
    if int(summary["temporal_pair_rows"].sum())!=756000:
        raise RuntimeError("unexpected total I2b pair rows")

    summary_path=ROOT/"i2b_public_representation_summary.csv"
    summary.to_csv(summary_path,index=False)

    manifest_path=ROOT/"i2b_public_representation_battery_manifest.json"
    write_json(manifest_path,{
        "status":"PHASE6_I2B_PUBLIC_REPRESENTATION_BATTERY_COMPLETE",
        "stage_id":"I2B_PUBLIC_REPRESENTATION_V1",
        "development_evidence":True,
        "code_commit":git_head(),
        "contracts_sha256":{
            "representation_config":sha256_file(CFG),
            "temporal_sampling_config":sha256_file(SAMPLING_CFG),
            "representation_protocol":sha256_file(PROTOCOL),
        },
        "provider_world_count":4,
        "provider_count":12,
        "marginal_rows_total":int(summary["marginal_rows"].sum()),
        "temporal_windows_total":int(summary["temporal_windows"].sum()),
        "temporal_pair_rows_total":int(summary["temporal_pair_rows"].sum()),
        "new_provider_world_simulation":False,
        "provider_reconstruction_run":False,
        "graph_prediction_read":False,
        "graph_wb_read":False,
        "final_wb_read":False,
        "hidden_provider_parameters_read":False,
        "outputs":{"summary":str(summary_path)},
        "output_hashes_sha256":{"summary":sha256_file(summary_path)},
        "provider_manifest_sha256":{
            f"{r['provider_world_id']}/{r['provider_id']}":r["provider_manifest_sha256"]
            for r in rows
        },
        "completed_utc":utc_now_iso(),
        "wall_seconds":float(time.perf_counter()-started),
        "workers":int(workers),
    })

    print("\nPHASE6_I2B_PUBLIC_REPRESENTATION_PASS")
    print(summary.to_string(index=False))
    print("\nTOTAL temporal pairs",int(summary["temporal_pair_rows"].sum()))
    print("output",ROOT)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(
        description="Materialize frozen Phase-6 I2b-v1 public paired distributions"
    )
    p.add_argument("--workers",type=int,default=3)
    args=p.parse_args()
    run_all(args.workers)


if __name__=="__main__":
    main()
