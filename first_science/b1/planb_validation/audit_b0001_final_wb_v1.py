#!/usr/bin/env python3
"""Independent B0001 final reference mechanical audit (NO prediction values).

Confirms 12 selected B0001 physical-world reference cells, frozen query keys,
1000 exact seed identities per cell, N=1000 point estimates, Wilson95
intervals, and all output hashes. Reads no M0/M1/M2/M3 predictions and
generates no graph simulations.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import preflight_b0001_final_wb_v1 as gate

STATUS="B0001_FINAL_REFERENCE_MECHANICAL_AUDIT_PASS_EVALUATION_UNLOCKED"
Z=1.959963984540054
TOL=1e-11


def wilson(k,n):
    p=k/n
    z2=Z*Z
    center=(p+z2/(2*n))/(1+z2/n)
    half=Z*math.sqrt(p*(1-p)/n+z2/(4*n*n))/(1+z2/n)
    return max(0.0,center-half),min(1.0,center+half)


def verify(a):
    auth_file=a.authorization/"b0001_final_wb_authorization_freeze.json"
    auth=gate.load(auth_file)
    gate.require(auth["status"]==gate.STATUS
                 and auth["reference_execution_authorized"] is True,
                 "Final WB authorization missing")
    global_file=a.reference/"b0001_final_wb_global_freeze.json"
    global_doc=gate.load(global_file)
    gate.require(global_doc["status"]==
                 "B0001_FINAL_WB_N1000_12_CELL_FROZEN_EVALUATION_NOT_YET_AUDITED"
                 and global_doc["n_cells"]==12
                 and global_doc["reference_trajectories"]==12000
                 and global_doc["final_reference_authorization_sha256"]==
                 gate.sha(auth_file)
                 and global_doc["postrun_prediction_audit_sha256"]==
                 auth["postrun_integrity_audit_sha256"],
                 "Reference freeze not tied to blind postrun audit")
    ids={f"{role}__{g}" for role in gate.ROLES for g in gate.GRAPHS}
    gate.require(set(global_doc["cell_manifest_sha256"])==ids,
                 "Reference global freeze incomplete")
    seed=auth["final_reference_seed_bank"]
    expected_seeds=list(range(seed["start"],seed["end_inclusive"]+1))
    gate.require(len(expected_seeds)==1000,"Final reference seed cardinality")
    rows=[]
    for role in gate.ROLES:
        for graph in gate.GRAPHS:
            cell=f"{role}__{graph}"
            root=a.reference/cell
            meta=root/"final_wb_manifest.json"
            gate.require(gate.sha(meta)==global_doc["cell_manifest_sha256"][cell],
                         "Reference manifest mutated: "+cell)
            record=gate.load(meta)
            gate.require(record["status"]==
                         "B0001_FINAL_WB_N1000_CELL_FROZEN"
                         and record["physical_cell_id"]==cell
                         and record["selected_candidate_id"]==gate.WORLD_IDS[role]
                         and record["selected_physical_contract_sha256"]==
                         auth["selected_worlds"][role]["world_contract_sha256"]
                         and record["authorization_sha256"]==gate.sha(auth_file)
                         and record["query_count"]==15
                         and record["horizon_count"]==49
                         and record["wb_n"]==1000
                         and record["generation_uses_prediction_values"] is False
                         and record["method_selection_changed"] is False,
                         "Reference manifest provenance/roles invalid: "+cell)
            qpath=a.staging/"frozen_queries"/cell/"step0_frozen_queries.csv"
            gate.require(record["frozen_query_sha256"]==gate.sha(qpath),
                         "Reference query definition drift: "+cell)
            q=pd.read_csv(qpath)
            pred_meta=a.graph/"scientific"/cell/"prediction_manifest.json"
            gate.require(gate.sha(pred_meta)==
                         record["prediction_manifest_sha256"],
                         "Blind prediction manifest changed: "+cell)
            ledger_path=root/"final_wb_ledger.csv"
            curves_path=root/"final_wb_curves.csv"
            for key,p in (("final_wb_ledger",ledger_path),
                          ("final_wb_curves",curves_path)):
                gate.require(p.is_file()
                             and record["output_sha256"][key]==gate.sha(p),
                             "Frozen reference file checksum drift: "+cell+"/"+key)
            ledger=pd.read_csv(ledger_path,usecols=[
                "trajectory","trajectory_seed","request_id"])
            check=ledger.groupby("trajectory",sort=True)["trajectory_seed"]
            gate.require(len(check)==1000
                         and check.first().astype(int).tolist()==expected_seeds
                         and check.nunique().eq(1).all()
                         and sorted(ledger.trajectory.astype(int).unique())==
                         list(range(1000))
                         and not ledger[["trajectory","request_id"]].duplicated().any(),
                         "Reference trajectory seeds/ordinals invalid: "+cell)
            curves=pd.read_csv(curves_path)
            gate.require(len(curves)==735
                         and curves.query_id.astype(str).nunique()==15
                         and curves[["query_id","H"]].duplicated().sum()==0
                         and set(curves.provider_world_id)=={role}
                         and set(curves.graph_id)=={graph},
                         "Reference curve grid/cell invalid: "+cell)
            for query,g in curves.groupby("query_id"):
                gate.require(g.H.astype(float).sort_values().tolist()==
                             list(map(float,range(0,241,5))),
                             "Reference horizon set changed: "+cell+"/"+str(query))
            keys=["query_id","provider_world_id","graph_id",
                  "rho_label","rho","regime",
                  "A_G_l_max","A_G_c_max","A_G_q_min"]
            expected=q[keys].sort_values("query_id").reset_index(drop=True)
            observed=curves[keys].drop_duplicates().sort_values(
                "query_id").reset_index(drop=True)
            gate.require(len(observed)==15,
                         "Reference query metadata duplicated: "+cell)
            for key in keys:
                if pd.api.types.is_numeric_dtype(expected[key]):
                    gate.require(np.allclose(expected[key].to_numpy(float),
                                             observed[key].to_numpy(float),
                                             atol=TOL,rtol=0),
                                 "Reference query numeric metadata changed: "+
                                 cell+"/"+key)
                else:
                    gate.require(expected[key].astype(str).tolist()==
                                 observed[key].astype(str).tolist(),
                                 "Reference query labels changed: "+cell+"/"+key)
            successes=curves.wb_successes.astype(int).to_numpy()
            n=curves.wb_n.astype(int).to_numpy()
            gate.require(np.all(n==1000)
                         and np.all((successes>=0)&(successes<=1000))
                         and np.allclose(curves.sigma_wb.to_numpy(float),
                                         successes/1000,atol=TOL,rtol=0),
                         "Reference sigma/count mismatch: "+cell)
            confidence=np.array([wilson(int(k),1000) for k in successes])
            gate.require(np.allclose(curves.wb_ci_lower.to_numpy(float),
                                     confidence[:,0],atol=1e-9,rtol=0)
                         and np.allclose(curves.wb_ci_upper.to_numpy(float),
                                         confidence[:,1],atol=1e-9,rtol=0),
                         "Reference Wilson95 interval mismatch: "+cell)
            rows.append({"cell":cell,"ledger_sha256":gate.sha(ledger_path),
                         "curve_sha256":gate.sha(curves_path),
                         "n_trajectories":1000,"n_queries":15,
                         "n_curve_points":735})
            print("B0001_FINAL_REFERENCE_CELL_AUDIT_PASS",cell,flush=True)
    return {
        "status":STATUS,
        "reference_global_freeze_sha256":gate.sha(global_file),
        "final_reference_authorization_sha256":gate.sha(auth_file),
        "blind_postrun_audit_sha256":auth["postrun_integrity_audit_sha256"],
        "n_reference_cells":12,"n_reference_trajectories":12000,
        "n_reference_curve_points":8820,
        "all_reference_Wilson95_intervals_checked":True,
        "reference_generation_uses_blind_prediction_values":False,
        "evaluation_authorized":True,
        "seven_method_plan_b_complete":False,
        "graph_simulations_run_by_audit":0,
        "cell_checks":rows,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("authorization","reference","graph","staging","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    for name in ("authorization","reference","graph","staging","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    gate.require(a.out!=a.reference and a.reference not in a.out.parents,
                 "Mechanical audit must not overwrite frozen reference")
    output=verify(a)
    path=a.out/"b0001_final_reference_mechanical_audit.json"
    gate.save(path,output)
    print("B0001_FINAL_REFERENCE_MECHANICAL_AUDIT_PASS 12 cells N1000",flush=True)
    print("EVALUATION_UNLOCKED_AFTER_REFERENCE_AUDIT",flush=True)
    print("AUDIT",path,flush=True)


if __name__=="__main__":
    main()
