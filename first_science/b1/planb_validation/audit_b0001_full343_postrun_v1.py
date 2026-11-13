#!/usr/bin/env python3
"""B0001 Full343 independent post-run integrity audit, BLIND to final WB.

Read-only across frozen inputs, simulated ledgers, and prediction outputs.
Hash-verifies every ledger and expected seed set, all manifest dependencies,
query/horizon grids, model identities/weights, and independently recomputes
M2 and all M3 readouts from the member curves. NO graph simulator imported,
NO new trajectories, NO final WB paths accessed.
Writes a separate audit report only after every check passes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROLES=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
METHODS={"M3_TOP1":1,"M3_TOP3":3,"M3_TOP14":14,"M3_FULL343":343}
OUTPUTS={
    "m0_predictions":"m0_predictions.csv",
    "m1_predictions":"m1_predictions.csv",
    "m2_member_curves":"m2_member_curves.csv",
    "m2_predictions":"m2_predictions.csv",
    "m3_fullsupport_allocation":"m3_fullsupport_allocation.csv",
    "m3_member_curves":"m3_member_curves.csv",
    "m3_predictions_full343_and_nested":"m3_predictions_full343_and_nested.csv",
    "prediction_ledger_hashes":"prediction_ledger_hashes.csv",
}
TOL=2e-10
STATUS="B0001_FULL343_POSTRUN_INTEGRITY_AUDIT_PASS_FINAL_WB_EMBARGOED"


def check(ok,what):
    if not bool(ok):
        raise RuntimeError("INTEGRITY AUDIT FAILED: "+what)


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def digest(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda:f.read(2**20),b""):
            h.update(block)
    return h.hexdigest()


def near(a,b,label,atol=TOL):
    x=np.asarray(a,dtype=float)
    y=np.asarray(b,dtype=float)
    check(x.shape==y.shape and np.allclose(x,y,atol=atol,rtol=0,equal_nan=False),label)


def atomic_json(p,doc):
    p.parent.mkdir(parents=True,exist_ok=True)
    check(not p.exists(),"audit report already exists: "+str(p))
    temp=p.with_suffix(".partial")
    check(not temp.exists(),"previous unfinished audit report: "+str(temp))
    temp.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    temp.replace(p)


def query_grid(stage,role,graph,freeze):
    key=role+"/"+graph
    path=stage/"frozen_queries"/f"{role}__{graph}"/"step0_frozen_queries.csv"
    check(digest(path)==freeze["query_sha256_by_cell"][key],
          key+" public query hash")
    q=pd.read_csv(path)
    check(len(q)==15 and q.query_id.is_unique and
          set(q.provider_world_id)=={role} and set(q.graph_id)=={graph} and
          set(q.step0_cell_status)=={"FROZEN_PHASE5_STEP0_PASS_V2"},
          key+" frozen query definitions")
    return q


def grid_test(df,q,role,graph,method,member_count=1):
    label=f"{role}/{graph}/{method}"
    check(len(df)==735*member_count,label+" row count")
    check(set(df.query_id.astype(str))==set(q.query_id.astype(str)),
          label+" query set")
    check(set(df.provider_world_id.astype(str))=={role}
          and set(df.graph_id.astype(str))=={graph},
          label+" physical-world identity")
    check(set(df.H.astype(float))==set(float(i) for i in range(0,241,5)),
          label+" horizon grid")
    check(set(df.regime.astype(str))==set(q.regime.astype(str)),label+" regimes")
    merged=df[["query_id","rho","rho_label","regime"]].drop_duplicates()
    check(len(merged)==15,label+" query metadata multiplicity")
    expected=q[["query_id","rho","rho_label","regime"]].copy()
    merged=merged.sort_values("query_id").reset_index(drop=True)
    expected=expected.sort_values("query_id").reset_index(drop=True)
    check(merged[["query_id","rho_label","regime"]].astype(str).equals(
          expected[["query_id","rho_label","regime"]].astype(str)),
          label+" query metadata")
    near(merged.rho,expected.rho,label+" query rho",atol=1e-12)
    check(not df[["query_id","H"]].isna().any().any(),label+" NaN keys")
    counts=df.groupby(["query_id","H"]).size()
    check(len(counts)==735 and (counts==member_count).all(),
          label+" duplicate/missing grid points")
    if member_count>1:
        check(df[["query_id","H","joint_rank"]].duplicated().sum()==0,
              label+" repeated joint rank")
    return label


def probability(col,label):
    v=np.asarray(col,dtype=float)
    check(np.isfinite(v).all() and np.all(v>=-1e-12) and np.all(v<=1+1e-12),
          label+" invalid probabilities")


def ledger_audit(cell,manifest,allocation,seed_common,label):
    table_path=cell/"prediction_ledger_hashes.csv"
    table=pd.read_csv(table_path)
    expected_names=["M1.csv"]+[f"M2_R{r:02d}.csv" for r in range(1,28)]+[
        f"M3_R{r:03d}.csv" for r in range(1,344)]
    check(len(table)==371 and len(set(table.ledger_file))==371
          and set(table.ledger_file)=={"ledgers/"+n for n in expected_names},
          label+" complete ledger list")
    check(int(table.n_trajectories.sum())==4200,label+" total trajectories")
    lookup=table.set_index("ledger_file")
    total=0
    for i,name in enumerate(expected_names):
        path=cell/"ledgers"/name
        key="ledgers/"+name
        check(path.is_file() and digest(path)==str(lookup.loc[key,"sha256"]),
              label+"/"+name+" ledger hash")
        if i<28:
            seeds=list(seed_common)
        else:
            r=i-28
            a=allocation.iloc[r-1]
            check(int(a["rank"])==r,label+" allocation rank")
            seeds=list(range(int(a.seed_start),int(a.seed_end_inclusive)+1))
            check(len(seeds)==int(a.n_trajectories),label+" allocation length")
        # Read only trajectory and seed columns, never WB or accuracy.
        t=pd.read_csv(path,usecols=["trajectory","trajectory_seed"])
        groups=t.groupby("trajectory",sort=True)["trajectory_seed"]
        observed=groups.first().to_numpy(dtype=int).tolist()
        check(len(groups)==len(seeds) and
              observed==seeds and
              groups.nunique().eq(1).all() and
              sorted(t.trajectory.astype(int).unique())==list(range(len(seeds))),
              label+"/"+name+" trajectory ordinals/seeds")
        check(int(lookup.loc[key,"n_trajectories"])==len(seeds)
              and int(lookup.loc[key,"seed_min"])==seeds[0]
              and int(lookup.loc[key,"seed_max"])==seeds[-1],
              label+"/"+name+" ledger index mismatch")
        total+=len(seeds)
    check(total==4200,label+" ledger trajectories")
    return len(expected_names),total


def member_checks(frame,role,graph,method,support,allocation=None):
    label=grid_test(frame, pd.read_csv(
        support["_query_file"]),role,graph,method,len(support["_data"]))
    size=len(support["_data"])
    probability(frame.sigma_member,label)
    check(set(frame.method_id)=={method+"_MEMBER"},label+" method IDs")
    v=frame.sort_values(["query_id","H","joint_rank"],kind="mergesort")
    ranks=v.joint_rank.to_numpy(dtype=int).reshape(-1,size)
    check(np.array_equal(ranks[0],np.arange(1,size+1)) and
          np.all(ranks==ranks[0]),label+" complete rank coverage")
    expected=support["_data"].sort_values("joint_rank").reset_index(drop=True)
    near(v.joint_weight.to_numpy(dtype=float).reshape(-1,size),
         np.tile(expected.joint_weight.to_numpy(float),(735,1)),
         label+" joint weights",atol=2e-14)
    for p in PROVIDERS:
        ids=v[f"{p}_candidate_id"].astype(str).to_numpy().reshape(-1,size)
        check(np.all(ids==expected[f"{p}_candidate_id"].astype(str).to_numpy()),
              label+"/"+p+" candidate identities")
    if allocation is None:
        n=np.full(size,100,dtype=int)
    else:
        n=allocation.sort_values("rank").n_trajectories.to_numpy(dtype=int)
    check(np.all(v.graph_n.to_numpy(dtype=int).reshape(-1,size)==n),
          label+" per-member trajectory allocation")
    return v,support["_data"].sort_values("joint_rank").reset_index(drop=True),n


def prediction_audit(cell,q,role,graph,v3b,allocation):
    label=f"{role}/{graph}"
    m0=pd.read_csv(cell/"m0_predictions.csv")
    grid_test(m0,q,role,graph,"M0")
    check(set(m0.method_id)=={"M0"} and
          set(m0.status).issubset({"PREDICTED","NOT_APPLICABLE"}),
          label+" M0 applicability statuses")
    applicable=m0.status=="PREDICTED"
    probability(m0.loc[applicable,"sigma_hat"],label+" M0")
    check(m0.loc[~applicable,"sigma_hat"].isna().all()
          and m0.loc[applicable,"sigma_hat"].notna().all(),
          label+" M0 applicability/NaN convention")

    m1=pd.read_csv(cell/"m1_predictions.csv")
    grid_test(m1,q,role,graph,"M1")
    check(set(m1.method_id)=={"M1"} and set(m1.status)=={"PREDICTED"}
          and (m1.graph_n.astype(int)==100).all(),label+" M1 method/count")
    probability(m1.sigma_hat,label+" M1")

    m2_support=pd.read_csv(v3b/role/"m2_joint_support_27.csv")
    m3_support=pd.read_csv(v3b/role/"m3_joint_support_343.csv")
    check(len(m2_support)==27 and len(m3_support)==343
          and m2_support.joint_rank.astype(int).tolist()==list(range(1,28))
          and m3_support.joint_rank.astype(int).tolist()==list(range(1,344)),
          label+" support cardinality")
    m2_members=pd.read_csv(cell/"m2_member_curves.csv")
    m2_ctx={"_data":m2_support,"_query_file":str(
        q.attrs["source_path"])}
    m2_sorted,_,_=member_checks(m2_members,role,graph,"M2",m2_ctx)
    means=m2_sorted.sigma_member.to_numpy(float).reshape(735,27)
    m2=pd.read_csv(cell/"m2_predictions.csv").sort_values(
        ["query_id","H"]).reset_index(drop=True)
    grid_test(m2,q,role,graph,"M2")
    check(set(m2.method_id)=={"M2"} and set(m2.status)=={"PREDICTED"}
          and (m2.member_count.astype(int)==27).all()
          and (m2.graph_n_per_member.astype(int)==100).all(),
          label+" M2 prediction metadata")
    near(m2.sigma_hat,means.mean(axis=1),label+" M2 mean")
    near(m2.sigma_min,means.min(axis=1),label+" M2 min")
    near(m2.sigma_max,means.max(axis=1),label+" M2 max")

    m3_members=pd.read_csv(cell/"m3_member_curves.csv")
    m3_ctx={"_data":m3_support,"_query_file":str(
        q.attrs["source_path"])}
    m3_sorted,support,n=member_checks(
        m3_members,role,graph,"M3",m3_ctx,allocation=allocation)
    probabilities=m3_sorted.sigma_member.to_numpy(float).reshape(735,343)
    weights=support.joint_weight.to_numpy(float)
    check(abs(float(weights.sum())-1.0)<1e-10
          and (weights>=0).all(),label+" normalized M3 weights")
    m3=pd.read_csv(cell/"m3_predictions_full343_and_nested.csv")
    check(len(m3)==735*4 and set(m3.method_id)==set(METHODS)
          and set(m3.status)=={"PREDICTED"},label+" M3 readout coverage")
    for method,k in METHODS.items():
        t=m3.loc[m3.method_id==method].sort_values(
            ["query_id","H"]).reset_index(drop=True)
        grid_test(t,q,role,graph,method)
        w=weights[:k]
        retained=float(w.sum())
        alpha=w/retained
        ph=probabilities[:,:k]
        nh=n[:k]
        avg=ph@alpha
        plugin=np.sum((alpha*alpha/nh)*(ph*(1.0-ph)),axis=1)
        worst=0.25*np.sum(alpha*alpha/nh)
        check((t.support_size.astype(int)==k).all()
              and (t.graph_budget.astype(int)==int(nh.sum())).all(),
              label+"/"+method+" readout counts")
        near(t.sigma_hat,avg,label+"/"+method+" point predictions")
        near(t.retained_mass,np.full(735,retained),
             label+"/"+method+" retained mass")
        near(t.omitted_mass,np.full(735,1-retained),
             label+"/"+method+" omitted mass")
        near(t.truncation_bound,np.full(735,1-retained),
             label+"/"+method+" truncation bound")
        near(t.mc_var_plugin,plugin,label+"/"+method+" plugin variance")
        near(t.mc_se_plugin,np.sqrt(np.maximum(plugin,0)),
             label+"/"+method+" plugin SE")
        near(t.mc_var_worstcase_bound,np.full(735,worst),
             label+"/"+method+" worst-case variance")
        near(t.mc_se_bound,np.full(735,np.sqrt(worst)),
             label+"/"+method+" worst-case SE")
    return {"m0_predictions":735,"m1_predictions":735,
            "m2_member_points":len(m2_members),
            "m2_predictions":735,"m3_member_points":len(m3_members),
            "m3_nested_predictions":len(m3)}


def audit(args):
    root=args.root
    stage=args.staging
    v3b=args.v3b
    pref=args.preflight
    global_path=root/"b0001_full343_global_prediction_freeze.json"
    check(global_path.is_file(),"global prediction freeze missing")
    global_doc=read(global_path)
    check(global_doc["status"]=="B0001_FULL343_12_CELL_GRAPH_PREDICTIONS_FROZEN"
          and global_doc["n_frozen_cells"]==12
          and global_doc["n_trajectories_per_cell"]==4200
          and global_doc["science_graph_trajectories"]==50400
          and global_doc["final_WB_read"] is False
          and global_doc["graph_whitebox_read"] is False
          and global_doc["final_whitebox_authorized"] is False,
          "B0001 global freeze status/firewall")
    frozen=read(pref/"b0001_graph_prediction_preflight.json")
    selection=read(v3b/"b0001_v3b_selection_audit_freeze.json")
    check(frozen["status"]=="B0001_GRAPH_PREDICTION_PREFLIGHT_PASS_EXECUTION_BLOCKED"
          and selection["status"]=="B0001_V3B_SELECTION_AND_AUDIT_FROZEN_GRAPH_BLOCKED",
          "B0001 preflight or V3b selection authority")
    check(global_doc["source_graph_preflight_sha256"]==
          digest(pref/"b0001_graph_prediction_preflight.json")
          and global_doc["v3b_selection_freeze_sha256"]==
          digest(v3b/"b0001_v3b_selection_audit_freeze.json"),
          "B0001 global source provenance")
    seed_file=args.workspace/"_preexecution"/"b0001_full343_graph_seeds.json"
    seeds=read(seed_file)
    common=seeds["graph_prediction"]["M1_M2_common_bank"]
    seed_common=list(range(int(common["start"]),int(common["end_inclusive"])+1))
    check(len(seed_common)==100 and
          seed_common==list(range(35000000,35000100)),
          "B0001 frozen common M1/M2 seed bank")
    check(digest(seed_file)==frozen.get("seed_registry_sha256",
          digest(seed_file)),"seed registry digest")
    expected={f"{r}__{g}" for r in ROLES for g in GRAPHS}
    check(set(global_doc["prediction_manifest_sha256_by_cell"])==expected,
          "global freeze physical-cell set")
    check(not any(root.glob("**/*.tmp")),
          "incomplete temporary files within frozen scientific outputs")
    check(len(list(root.glob("P*__G_*/prediction_manifest.json")))==12,
          "unexpected or missing cell manifests")
    checks=[]
    for role in ROLES:
        allocation=pd.read_csv(root/"_preexecution"/
                               f"m3_fullsupport_allocation_{role}.csv").sort_values(
                                   "rank").reset_index(drop=True)
        check(len(allocation)==343 and
              int(allocation.n_trajectories.sum())==1400 and
              allocation["rank"].astype(int).tolist()==list(range(1,344)),
              role+" frozen M3 allocation")
        check(digest(root/"_preexecution"/f"m3_fullsupport_allocation_{role}.csv")==
              frozen["allocation_sha256"][role],
              role+" allocation preflight hash")
        for graph in GRAPHS:
            cell_id=f"{role}__{graph}"
            cell=root/cell_id
            mf_path=cell/"prediction_manifest.json"
            check(digest(mf_path)==global_doc[
                "prediction_manifest_sha256_by_cell"][cell_id],
                cell_id+" global manifest hash")
            mf=read(mf_path)
            check(mf["status"]=="FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION"
                  and mf["scientific_evidence"] is True
                  and mf["physical_cell_id"]==cell_id
                  and mf["provider_world_id"]==role
                  and mf["graph_id"]==graph
                  and mf["ledger_count"]==371
                  and mf["ledger_trajectory_total"]==4200,
                  cell_id+" frozen cell metadata")
            check(mf["inputs"]=={
                "query_count":15,"M1_joint_models":1,"M2_joint_models":27,
                "M3_joint_models":343,"M3_budget":1400,
                "graph_WB_read":False,"final_WB_read":False,
                "hidden_provider_parameters_read":False,
                "private_I1_traces_read":False},
                cell_id+" prediction input/firewall metadata")
            check(mf["b0001_preflight_sha256"]==
                  digest(pref/"b0001_graph_prediction_preflight.json")
                  and mf["b0001_v3b_selection_sha256"]==
                  digest(v3b/"b0001_v3b_selection_audit_freeze.json")
                  and mf["v3b_world_selection_manifest_sha256"]==
                  digest(v3b/role/"world_selection_freeze_manifest.json")
                  and mf["seed_registry_sha256"]==digest(seed_file)
                  and mf["preexecution_manifest_sha256"]==
                  digest(args.workspace/"_preexecution"/
                         "b0001_graph_adapter_preexecution.json"),
                  cell_id+" input provenance")
            q=query_grid(stage,role,graph,frozen)
            q.attrs["source_path"]=str(
                stage/"frozen_queries"/cell_id/"step0_frozen_queries.csv")
            check(mf["step0_frozen_queries_sha256"]==
                  frozen["query_sha256_by_cell"][role+"/"+graph],
                  cell_id+" query freeze")
            check(set(mf["outputs"])==set(OUTPUTS)
                  and set(mf["output_hashes_sha256"])==set(OUTPUTS),
                  cell_id+" output manifest set")
            for key,name in OUTPUTS.items():
                path=cell/name
                check(path.is_file() and
                      Path(mf["outputs"][key]).resolve()==path.resolve() and
                      digest(path)==mf["output_hashes_sha256"][key],
                      cell_id+" output hash: "+name)
            near(pd.read_csv(cell/"m3_fullsupport_allocation.csv")[
                     "n_trajectories"].to_numpy(float),
                 allocation["n_trajectories"].to_numpy(float),
                 cell_id+" allocation copy")
            ledger_n,traj_n=ledger_audit(
                cell,mf,allocation,seed_common,cell_id)
            stats=prediction_audit(cell,q,role,graph,v3b,allocation)
            checks.append({"physical_cell_id":cell_id,
                           "manifest_sha256":digest(mf_path),
                           "ledger_files_verified":ledger_n,
                           "trajectories_verified":traj_n,
                           **stats})
            print("B0001_POSTRUN_CELL_PASS",cell_id,
                  "ledgers=371 trajectories=4200",flush=True)
    return {"status":STATUS,
            "global_prediction_freeze_sha256":digest(global_path),
            "source_graph_preflight_sha256":
                digest(pref/"b0001_graph_prediction_preflight.json"),
            "v3b_selection_sha256":
                digest(v3b/"b0001_v3b_selection_audit_freeze.json"),
            "audited_cell_count":12,
            "ledger_files_verified":sum(x["ledger_files_verified"] for x in checks),
            "trajectories_verified":sum(x["trajectories_verified"] for x in checks),
            "all_M2_and_M3_nested_readouts_independently_recomputed":True,
            "graph_simulations_executed_by_audit":0,
            "final_whitebox_read":False,
            "final_whitebox_authorized":False,
            "seven_method_plan_b_complete":False,
            "cell_checks":checks}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("workspace","staging","v3b","preflight","out"):
        ap.add_argument("--"+key,required=True,type=Path)
    a=ap.parse_args()
    for k in ("workspace","staging","v3b","preflight","out"):
        setattr(a,k,getattr(a,k).expanduser().resolve())
    a.root=a.workspace/"scientific"
    check(a.root.is_dir(),"scientific prediction root missing")
    check(a.out!=a.root and a.root not in a.out.parents and
          a.out!=a.workspace and a.workspace not in a.out.parents,
          "audit report cannot be inside frozen scientific workspace")
    path=a.out/"b0001_full343_postrun_integrity_audit.json"
    check(not path.exists(),"audit report already frozen")
    result=audit(a)
    atomic_json(path,result)
    print("B0001_FULL343_POSTRUN_INTEGRITY_AUDIT_PASS",flush=True)
    print("CELLS 12 LEDGERS",result["ledger_files_verified"],
          "TRAJECTORIES",result["trajectories_verified"],flush=True)
    print("FINAL_WHITEBOX_EMBARGOED",flush=True)
    print("AUDIT",path,flush=True)


if __name__=="__main__":
    main()
