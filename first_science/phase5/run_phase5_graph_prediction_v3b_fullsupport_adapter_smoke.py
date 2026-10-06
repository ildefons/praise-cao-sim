"""Engineering-only adapter smoke for the Phase-5 V3b full-support M3 revision.

The scientific V3b provider reconstruction remains frozen.  This smoke validates
that the revised graph adapter can consume all 343 frozen joint members, derive
the provider-world-specific B=1400 full-support minimax allocation, construct
every member surrogate tuple, assign disjoint rank seed streams, and form
FULL343 plus nested Top1/Top3/Top14 readouts.

To keep the engineering check small, native graph simulation is executed only
for sentinel support ranks on G_PAR.  The previously passed V3b graph-adapter
smoke already exercised all four graph ASTs, all 27 M2 members, and the native
M3 path.  No scientific graph seeds or final-WB evidence are read.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FIRST_SCIENCE=HERE.parent
PHASE4=FIRST_SCIENCE/"phase4"
if str(PHASE4) not in sys.path:
    sys.path.insert(0,str(PHASE4))

from m3_v4_dominant_mass_graph import _integer_minimax_allocations  # noqa:E402
from phase5_runtime_v2 import (
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)
from run_phase5_graph_prediction_v3b_adapter_smoke import (  # noqa:E402
    PROVIDERS,
    V3B_ROOT,
    _candidate_lookup,
    _curve,
    _one_graph_ledger,
    _provider_tables,
    _selected_smoke_query,
)

CFG=HERE/"config_phase5_graph_prediction_v3b_fullsupport.json"
SEEDS=HERE/"config_phase5_seed_registry_v3b_fullsupport.json"
OLD_SMOKE=HERE/"smoke"/"v3b_graph_adapter"/"phase5_v3b_graph_adapter_smoke_manifest.json"
DEFAULT_OUTPUT=HERE/"smoke"/"v3b_fullsupport_graph_adapter"
ELIGIBLE_WORLDS=("P1","P3","P4")
SUPPORT_SIZE=343
PRODUCTION_BUDGET=1400
SENTINEL_RANKS=(1,2,3,14,343)
SMOKE_STOP_TIME_NOTE="native sentinel trajectories use the inherited 5-second adapter-smoke horizon"


def _support_and_variants(world:str):
    tables=_provider_tables(world,"M3")
    lookup=_candidate_lookup(tables)
    path=V3B_ROOT/world/"m3_joint_support_343.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    support=pd.read_csv(path).sort_values("joint_rank",kind="mergesort").reset_index(drop=True)
    if len(support)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: expected 343 M3 joint members")
    if support["joint_rank"].astype(int).tolist()!=list(range(1,SUPPORT_SIZE+1)):
        raise RuntimeError(f"{world}: M3 ranks changed")
    if abs(float(support["joint_weight"].astype(float).sum())-1.0)>1e-10:
        raise RuntimeError(f"{world}: M3 joint weights do not normalize")
    if not np.all(np.diff(support["joint_weight"].astype(float).to_numpy())<=1e-12):
        raise RuntimeError(f"{world}: M3 weights are not descending")

    # Construct all 343 real surrogate tuples.  This is the key full-support
    # adapter check; every frozen candidate ID must resolve before science runs.
    variants={}
    for rec in support.itertuples(index=False):
        rank=int(rec.joint_rank)
        variants[rank]={
            p:__import__("run_phase5_graph_prediction_v3b_adapter_smoke")._surrogate(
                lookup[(p,str(getattr(rec,f"{p}_candidate_id")))]
            )
            for p in PROVIDERS
        }
    if set(variants)!=set(range(1,SUPPORT_SIZE+1)):
        raise RuntimeError(f"{world}: did not construct every full-support variant")
    return support,variants


def _allocation(world:str,support:pd.DataFrame,cfg:dict)->pd.DataFrame:
    weights=support["joint_weight"].astype(float).to_numpy()
    out=_integer_minimax_allocations(weights,[PRODUCTION_BUDGET]).copy()
    if len(out)!=SUPPORT_SIZE:
        raise RuntimeError(f"{world}: allocation does not cover all 343 ranks")
    if int(out["n_trajectories"].astype(int).sum())!=PRODUCTION_BUDGET:
        raise RuntimeError(f"{world}: allocation does not sum to 1400")
    if (out["n_trajectories"].astype(int)<1).any():
        raise RuntimeError(f"{world}: full-support allocation has N<1")

    seed_base=int(cfg["seeds"]["M3"]["seed_base"])
    stride=int(cfg["seeds"]["M3"]["seed_block_stride"])
    out["joint_weight"]=weights
    out["seed_start"]=[
        seed_base+(int(r)-1)*stride for r in out["rank"]
    ]
    out["seed_end_inclusive"]=[
        int(s)+int(n)-1
        for s,n in zip(out["seed_start"],out["n_trajectories"])
    ]
    if any(int(n)>=stride for n in out["n_trajectories"]):
        raise RuntimeError(f"{world}: rank allocation reaches seed-block stride")
    # Consecutive blocks must be disjoint even at their allocated prefixes.
    starts=out["seed_start"].astype(int).to_numpy()
    ends=out["seed_end_inclusive"].astype(int).to_numpy()
    if np.any(ends[:-1]>=starts[1:]):
        raise RuntimeError(f"{world}: M3 rank seed prefixes overlap")
    return out


def _nested_mass_table(support:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for k,label in ((1,"M3_TOP1"),(3,"M3_TOP3"),(14,"M3_TOP14"),(343,"M3_FULL343")):
        mass=float(support.head(k)["joint_weight"].astype(float).sum())
        rows.append({
            "method_id":label,
            "support_size":k,
            "retained_mass":mass,
            "omitted_mass":1.0-mass,
            "truncation_bound":1.0-mass,
        })
    out=pd.DataFrame(rows)
    full=out[out["method_id"]=="M3_FULL343"].iloc[0]
    if abs(float(full["retained_mass"])-1.0)>1e-10:
        raise RuntimeError("FULL343 retained mass is not one")
    if abs(float(full["truncation_bound"]))>1e-10:
        raise RuntimeError("FULL343 truncation bound is not zero")
    return out


def run(output:Path,*,reset:bool)->None:
    started=utc_now_iso()
    cfg=read_json(CFG)
    seeds=read_json(SEEDS)
    if cfg.get("status")!="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT":
        raise RuntimeError("unexpected full-support graph contract")
    if seeds.get("status")!="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT":
        raise RuntimeError("unexpected full-support seed registry")
    if seeds["engineering_smoke"]["scientific_evidence"] is not False:
        raise RuntimeError("full-support smoke must be non-scientific")

    old=read_json(OLD_SMOKE)
    if old.get("status")!="FROZEN_PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS":
        raise RuntimeError("base V3b real graph-adapter smoke did not pass")
    if old.get("inputs",{}).get("final_WB_read") is not False:
        raise RuntimeError("base smoke final-WB firewall flag invalid")

    output=output.resolve()
    try:
        output.relative_to(HERE.resolve())
    except ValueError as exc:
        raise RuntimeError("smoke output must remain inside phase5/") from exc
    if "results" in output.parts:
        raise RuntimeError("engineering smoke must not write under scientific results/")
    if reset and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True,exist_ok=True)

    summary_rows=[]
    outputs={}
    supports={}
    variants={}
    allocations={}
    for world in ELIGIBLE_WORLDS:
        support,var=_support_and_variants(world)
        alloc=_allocation(world,support,cfg)
        mass=_nested_mass_table(support)
        supports[world]=support
        variants[world]=var
        allocations[world]=alloc

        ap=output/f"m3_fullsupport_B1400_allocation_{world}.csv"
        mp=output/f"m3_nested_mass_{world}.csv"
        alloc.to_csv(ap,index=False)
        mass.to_csv(mp,index=False)
        outputs[f"allocation_{world}"]=ap
        outputs[f"nested_mass_{world}"]=mp

        summary_rows.append({
            "provider_world_id":world,
            "support_size":len(support),
            "budget":int(alloc["n_trajectories"].sum()),
            "members_with_one_trajectory":int((alloc["n_trajectories"].astype(int)==1).sum()),
            "rank1_n":int(alloc.iloc[0]["n_trajectories"]),
            "max_n":int(alloc["n_trajectories"].max()),
            "min_n":int(alloc["n_trajectories"].min()),
            "worst_case_mc_variance_bound":float(alloc["worst_case_mc_variance_bound_budget"].iloc[0]),
            "worst_case_mc_se_bound":float(alloc["worst_case_mc_se_bound_budget"].iloc[0]),
            "top14_mass":float(support.head(14)["joint_weight"].sum()),
            "full_mass":float(support["joint_weight"].sum()),
        })

    summary=pd.DataFrame(summary_rows)
    summary_path=output/"fullsupport_allocation_summary.csv"
    summary.to_csv(summary_path,index=False)
    outputs["allocation_summary"]=summary_path

    # Native simulator sentinel: use real P1 full-support models for ranks that
    # touch each nested diagnostic boundary plus the final rank.  This checks
    # low-weight-tail model construction without paying for 343 smoke runs.
    smoke_base=int(seeds["engineering_smoke"]["seed_base"])
    query=_selected_smoke_query("G_PAR")
    sentinel_rows=[]
    curve_rows=[]
    for i,rank in enumerate(SENTINEL_RANKS):
        seed=smoke_base+i
        ledger=_one_graph_ledger(
            contracts=__import__("phase5_runtime_v2").load_phase5_contracts(HERE),
            graph_id="G_PAR",
            surrogates=variants["P1"][rank],
            seeds=[seed],
        )
        curve=_curve(ledger,query,"sigma_member_smoke")
        curve.insert(0,"joint_rank",rank)
        curve["joint_weight"]=float(
            supports["P1"].loc[supports["P1"]["joint_rank"].astype(int)==rank,"joint_weight"].iloc[0]
        )
        curve_rows.append(curve)
        sentinel_rows.append({
            "joint_rank":rank,
            "engineering_seed":seed,
            "request_rows":int(len(ledger)),
            "completed_rows":int(ledger["completed_by_stop"].astype(bool).sum()),
        })
    sentinel=pd.DataFrame(sentinel_rows)
    curves=pd.concat(curve_rows,ignore_index=True)
    sentinel_path=output/"native_sentinel_execution.csv"
    curves_path=output/"native_sentinel_curves.csv"
    sentinel.to_csv(sentinel_path,index=False)
    curves.to_csv(curves_path,index=False)
    outputs["native_sentinel_execution"]=sentinel_path
    outputs["native_sentinel_curves"]=curves_path

    checks={
        "base_v3b_graph_adapter_smoke_passed":True,
        "all_three_eligible_worlds_checked":True,
        "all_343_joint_members_resolve_for_each_eligible_world":True,
        "full_support_weights_normalize_for_each_world":True,
        "B1400_allocation_covers_all_343_members":True,
        "every_fullsupport_member_has_at_least_one_trajectory":True,
        "rank_seed_prefixes_are_disjoint":True,
        "top1_top3_top14_mass_diagnostics_materialized":True,
        "full343_retained_mass_is_one":True,
        "full343_truncation_bound_is_zero":True,
        "native_tail_sentinel_rank343_executed":True,
        "scientific_graph_seeds_used":False,
        "final_WB_read":False,
    }
    manifest={
        "status":"FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_ADAPTER_SMOKE_PASS",
        "stage_id":"ENGINEERING_SMOKE_V3B_FULLSUPPORT_GRAPH_ADAPTER",
        "scientific_evidence":False,
        "graph_contract_sha256":sha256_file(CFG),
        "seed_registry_sha256":sha256_file(SEEDS),
        "base_v3b_smoke_sha256":sha256_file(OLD_SMOKE),
        "support_size":SUPPORT_SIZE,
        "production_budget":PRODUCTION_BUDGET,
        "sentinel_ranks":list(SENTINEL_RANKS),
        "smoke_stop_time_note":SMOKE_STOP_TIME_NOTE,
        "checks":checks,
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "started_utc":started,
        "completed_utc":utc_now_iso(),
    }
    manifest_path=output/"phase5_v3b_fullsupport_graph_adapter_smoke_manifest.json"
    write_json(manifest_path,manifest)

    print("PHASE5_V3B_FULLSUPPORT_GRAPH_ADAPTER_SMOKE_PASS")
    print(summary.to_string(index=False))
    print("\\nNATIVE SENTINELS")
    print(sentinel.to_string(index=False))
    for k,v in checks.items():
        print(k,v)
    print("scientific_evidence False")
    print("final_WB_read False")
    print("manifest",manifest_path)


def main()->None:
    p=argparse.ArgumentParser(description="Run the non-scientific V3b full-support graph-adapter smoke")
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--reset",action="store_true")
    args=p.parse_args()
    run(args.output,reset=bool(args.reset))


if __name__=="__main__":
    main()
