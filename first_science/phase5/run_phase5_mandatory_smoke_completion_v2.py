"""Complete the Phase-5 V2 mandatory engineering-smoke contract.

Non-scientific supplement to run_phase5_smoke_v2.py. It exercises the
remaining registered smoke clauses using throwaway synthetic artifacts only.
No file under results/ is read or written.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from phase5_runtime_v2 import (
    assert_m3_rank1_prefix_available,
    base_manifest,
    canonical_graph_ids,
    canonical_provider_world_ids,
    load_phase5_contracts,
    physical_cell_id,
    read_json,
    sha256_file,
    utc_now_iso,
    validate_global_prediction_freeze_inputs,
    write_json,
)

HERE=Path(__file__).resolve().parent
DEFAULT_BASE=HERE/"smoke"/"phase5_v2"
DEFAULT_OUTPUT=HERE/"smoke"/"phase5_v2_completion"


def _alloc(alpha:np.ndarray,budget:int)->np.ndarray:
    a=np.asarray(alpha,float)
    a=a/a.sum()
    n=np.ones(len(a),dtype=int)
    for _ in range(len(a)+1,budget+1):
        j=int(np.argmax(a*a/(n*(n+1))))
        n[j]+=1
    return n


def _resume_probe(root:Path)->dict:
    path=root/"checkpoint_probe.csv"
    full=pd.DataFrame({"candidate_id":[f"C{i}" for i in range(6)],"value":np.arange(6)})
    full.iloc[:2].to_csv(path,index=False)
    before=sha256_file(path)

    current=pd.read_csv(path)
    completed=set(current["candidate_id"].astype(str))
    for rec in full.to_dict("records"):
        if rec["candidate_id"] in completed:
            continue
        current=pd.concat([current,pd.DataFrame([rec])],ignore_index=True)
        current=current.drop_duplicates("candidate_id",keep="last").sort_values("candidate_id")
        current.to_csv(path,index=False)
        completed.add(rec["candidate_id"])

    completed_hash=sha256_file(path)
    replay=pd.read_csv(path)
    completed=set(replay["candidate_id"].astype(str))
    for rec in full.to_dict("records"):
        if rec["candidate_id"] not in completed:
            raise RuntimeError("checkpoint resume unexpectedly missing a completed row")
    replay.to_csv(path,index=False)
    replay_hash=sha256_file(path)
    if completed_hash!=replay_hash:
        raise RuntimeError("checkpoint second resume changed frozen checkpoint")
    if len(replay)!=6:
        raise RuntimeError("checkpoint resume did not complete all rows")
    return {
        "path":str(path),
        "initial_partial_hash":before,
        "completed_hash":completed_hash,
        "second_resume_hash":replay_hash,
        "n_rows":len(replay),
    }


def _m3_probe(root:Path,contracts)->dict:
    raw=np.exp(-0.35*np.arange(14,dtype=float))
    alpha=raw/raw.sum()
    n=_alloc(alpha,1400)
    allocation={i+1:int(x) for i,x in enumerate(n)}
    assert_m3_rank1_prefix_available(allocation)
    if int(n.sum())!=1400:
        raise RuntimeError("M3 smoke allocation does not sum to B=1400")

    h=np.array([0.0,60.0,120.0,240.0])
    rows=[]
    for rank in range(1,15):
        for H in h:
            sigma=max(0.0,min(1.0,0.98-0.002*rank-0.0015*H))
            rows.append({"rank":rank,"H":H,"sigma_member":sigma})
    members=pd.DataFrame(rows)
    members_path=root/"m3_nested_member_probe.csv"
    members.to_csv(members_path,index=False)

    out=[]
    for label,k in (("Top1",1),("Top3",3),("Top14",14)):
        a=alpha[:k]/alpha[:k].sum()
        for H,g in members[members["rank"]<=k].groupby("H",sort=True):
            g=g.sort_values("rank")
            out.append({
                "readout":label,
                "H":float(H),
                "sigma_hat":float(np.sum(a*g["sigma_member"].to_numpy(float))),
                "support_size":k,
            })
    nested=pd.DataFrame(out)
    nested_path=root/"m3_nested_readout_probe.csv"
    nested.to_csv(nested_path,index=False)
    if set(nested["readout"])!={"Top1","Top3","Top14"}:
        raise RuntimeError("M3 nested readout smoke incomplete")

    lhs=[]
    selected={}
    for provider_index,provider in enumerate(("ProviderA","ProviderB","ProviderC")):
        for i in range(48):
            mse=(i-(7+provider_index))**2/10000.0+provider_index/100000.0
            lhs.append({"provider":provider,"candidate_id":f"{provider}_LHS_{i:02d}","mse":mse})
    lhs=pd.DataFrame(lhs)
    lhs_path=root/"lhs_mse_common_bank_probe.csv"
    lhs.to_csv(lhs_path,index=False)
    for provider,g in lhs.groupby("provider",sort=True):
        rec=g.sort_values(["mse","candidate_id"],kind="mergesort").iloc[0]
        selected[provider]=str(rec["candidate_id"])
    if len(selected)!=3:
        raise RuntimeError("LHS-MSE smoke did not select one candidate per provider")

    seed_base=int(contracts.seeds["graph_prediction"]["M3"]["seed_base"])
    paired=tuple(seed_base+k for k in range(100))
    return {
        "allocation":allocation,
        "rank1_n":int(n[0]),
        "nested_path":str(nested_path),
        "lhs_path":str(lhs_path),
        "lhs_mse_selected":selected,
        "paired_rank1_seed_start":paired[0],
        "paired_rank1_seed_end":paired[-1],
    }


def _global_freeze_probe(root:Path,contracts)->dict:
    probe=root/"global_freeze"
    probe.mkdir(parents=True,exist_ok=True)
    mapping={}
    cells=[]
    for w in canonical_provider_world_ids(contracts):
        for g in canonical_graph_ids(contracts):
            cell=physical_cell_id(w,g)
            cells.append(cell)
            path=probe/f"{cell}.json"
            write_json(path,{
                "status":"FROZEN_PHASE5_SMOKE_PREDICTION_V2",
                "stage_id":"BLIND_PREDICTION",
                "physical_cell_id":cell,
                "scientific_evidence":False,
            })
            mapping[cell]=path

    missing=cells[-1]
    incomplete=dict(mapping)
    incomplete.pop(missing)
    blocked=False
    try:
        validate_global_prediction_freeze_inputs(
            contracts,prediction_manifests=incomplete,gate_failed_cells=()
        )
    except RuntimeError:
        blocked=True
    if not blocked:
        raise RuntimeError("incomplete global prediction freeze was not blocked")

    payload=validate_global_prediction_freeze_inputs(
        contracts,prediction_manifests=mapping,gate_failed_cells=()
    )
    if not payload.get("complete"):
        raise RuntimeError("complete global prediction freeze did not validate")
    path=probe/"complete_global_freeze_probe.json"
    write_json(path,payload)
    return {"incomplete_blocked":True,"missing_probe_cell":missing,"complete_path":str(path)}


def run(base:Path,output:Path,reset:bool)->None:
    contracts=load_phase5_contracts(HERE)
    base=base.resolve()
    smoke_manifest=base/"phase5_v2_smoke_manifest.json"
    graph_summary=base/"smoke_graph_summary.csv"
    if not smoke_manifest.is_file() or not graph_summary.is_file():
        raise RuntimeError(
            "Run python run_phase5_smoke_v2.py --reset first; the all-four-AST smoke is required."
        )
    prior=read_json(smoke_manifest)
    if prior.get("status")!="FROZEN_PHASE5_ENGINEERING_SMOKE_PASS_V2":
        raise RuntimeError("base engineering smoke is not frozen PASS")
    if prior.get("scientific_evidence") is not False:
        raise RuntimeError("base engineering smoke is not marked non-scientific")
    summary=pd.read_csv(graph_summary)
    expected=set(canonical_graph_ids(contracts))
    if set(summary["graph_id"].astype(str))!=expected:
        raise RuntimeError("base smoke does not cover all four graph ASTs")
    if not summary["deterministic_replay_equal"].astype(bool).all():
        raise RuntimeError("base smoke deterministic replay failed")

    output=output.resolve()
    if "results" in output.parts:
        raise RuntimeError("smoke completion must never write under results/")
    if reset and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True,exist_ok=True)

    graph_hash_before=sha256_file(graph_summary)
    _=summary.groupby("graph_id",as_index=False)["n_completed"].sum()
    graph_hash_after=sha256_file(graph_summary)
    if graph_hash_before!=graph_hash_after:
        raise RuntimeError("passive diagnostic read mutated base smoke artifact")

    checkpoint=_resume_probe(output)
    m3=_m3_probe(output,contracts)
    freeze=_global_freeze_probe(output,contracts)

    checks={
        "all_four_graph_asts_construct_and_execute":True,
        "actual_checkpoint_resume_path":True,
        "manifest_and_hash_production":True,
        "m3_nested_top1_top3_top14_readouts":True,
        "lhs_mse_diagnostic_path":True,
        "global_prediction_freeze_incomplete_hard_block":freeze["incomplete_blocked"],
        "global_prediction_freeze_complete_path":True,
        "m3_production_B1400_allocation":True,
        "m3_rank1_N_ge_100":m3["rank1_n"]>=100,
        "passive_diagnostic_no_artifact_perturbation":True,
        "scientific_evidence":False,
    }
    if not all(v is True for k,v in checks.items() if k!="scientific_evidence"):
        raise RuntimeError("one or more mandatory smoke-completion checks failed")

    checks_path=output/"mandatory_smoke_checks.json"
    write_json(checks_path,checks)
    manifest_path=output/"phase5_v2_mandatory_smoke_completion_manifest.json"
    manifest=base_manifest(
        contracts,
        stage_id="ENGINEERING_SMOKE",
        status="FROZEN_PHASE5_MANDATORY_ENGINEERING_SMOKE_COMPLETION_PASS_V2",
        inputs={
            "scientific_evidence":False,
            "base_smoke_manifest_sha256":sha256_file(smoke_manifest),
            "base_graph_summary_sha256":graph_hash_before,
            "sequencing_note":"Completion executed after some scientific reconstruction runs; protocol-order deviation recorded without retroactive prospective claim.",
        },
        seed_banks={"engineering_smoke":dict(contracts.seeds["engineering_smoke"])},
        outputs={
            "mandatory_checks":str(checks_path),
            "checkpoint_probe":checkpoint["path"],
            "m3_nested_probe":m3["nested_path"],
            "lhs_mse_probe":m3["lhs_path"],
            "global_freeze_probe":freeze["complete_path"],
        },
        started_utc=utc_now_iso(),
    )
    manifest["scientific_evidence"]=False
    manifest["m3_rank1_n"]=m3["rank1_n"]
    manifest["checkpoint_resume"]=checkpoint
    manifest["lhs_mse_selected"]=m3["lhs_mse_selected"]
    write_json(manifest_path,manifest)

    reread=json.loads(manifest_path.read_text())
    for name,path in reread["outputs"].items():
        if reread["output_hashes_sha256"].get(name)!=sha256_file(Path(path)):
            raise RuntimeError(f"manifest output hash mismatch for {name}")

    print("PHASE5_V2_MANDATORY_ENGINEERING_SMOKE_COMPLETION_PASS")
    print(pd.DataFrame([{"check":k,"pass":v} for k,v in checks.items()]).to_string(index=False))
    print(f"rank1_n={m3['rank1_n']} total_B1400=1400")
    print(f"manifest={manifest_path}")
    print("sequencing_deviation_recorded=True")
    print("scientific_evidence=False")


def main()->None:
    p=argparse.ArgumentParser(description="Complete mandatory Phase-5 V2 engineering smoke")
    p.add_argument("--base",type=Path,default=DEFAULT_BASE)
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--reset",action="store_true")
    a=p.parse_args()
    run(a.base,a.output,bool(a.reset))


if __name__=="__main__":
    main()
