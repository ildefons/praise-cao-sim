#!/usr/bin/env python3
"""B0001 V3b FULL343 graph-prediction preflight (NO SIMULATIONS).

Checks the 12 frozen public graph-query sets and the 9 V3b provider banks,
verifies M1/M2/M3 support semantics and frozen hashes, derives the original
B=1400 full-support integer minimax allocations for each of three worlds,
and reserves fresh stage-disjoint graph prediction seed blocks.

This DOES NOT authorize graph predictions: the B0001 graph-runner isolation
adapter and smoke must separately pass before scientific execution. No hidden
provider worlds, Step-0 outcome values, or final-WB evidence is opened.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PHASE5=REPO/"first_science"/"phase5"
PHASE4=REPO/"first_science"/"phase4"
ROLES=("P1","P3","P4")
GRAPHS=("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")
PROVIDERS=("ProviderA","ProviderB","ProviderC")
COLUMNS=("query_id","provider_world_id","graph_id","rho_label","rho","regime",
         "scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status")
BUDGET=1400
N_M1M2=100
N_M3=343
SEED_M1M2=35_000_000
SEED_M3=36_000_000
SEED_STRIDE=1000
MAX_NATIVE=(2**32-1-3)//100
TOL=1e-10
CONTRACT_FILES=(
    "config_phase5_graph_prediction_v3b_fullsupport.json",
    "config_phase5_seed_registry_v3b_fullsupport.json",
    "run_phase5_graph_prediction_v3b_fullsupport.py",
    "freeze_phase5_graph_prediction_v3b_fullsupport_preexecution.py",
)


def require(ok,msg):
    if not ok:
        raise RuntimeError(msg)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def save(p,obj):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def same_csv(source,target,label):
    a=pd.read_csv(source);b=pd.read_csv(target)
    require(list(a.columns)==list(b.columns) and a.shape==b.shape,
            label+": CSV schema/shape mismatch")
    for name in a.columns:
        if pd.api.types.is_numeric_dtype(a[name]) and pd.api.types.is_numeric_dtype(b[name]):
            require(np.allclose(a[name].to_numpy(float),b[name].to_numpy(float),
                                rtol=0,atol=1e-15,equal_nan=True),
                    label+": numeric discrepancy in "+name)
        else:
            require(a[name].fillna("<NA>").astype(str).tolist()==
                    b[name].fillna("<NA>").astype(str).tolist(),
                    label+": identity discrepancy in "+name)


def source_contract():
    source={name:sha(PHASE5/name) for name in CONTRACT_FILES}
    cfg=load(PHASE5/CONTRACT_FILES[0])
    seeds=load(PHASE5/CONTRACT_FILES[1])
    require(cfg["status"]=="FROZEN_PHASE5_GRAPH_PREDICTION_V3B_FULLSUPPORT",
            "Frozen original fullsupport graph contract changed")
    require(seeds["status"]=="FROZEN_PHASE5_SEED_REGISTRY_V3B_FULLSUPPORT",
            "Frozen original fullsupport seed registry changed")
    require(cfg["eligibility"]["eligible_provider_worlds"]==list(ROLES)
            and cfg["eligibility"]["expected_eligible_cells"]==12,
            "Original eligible-world graph contract changed")
    require(cfg["queries"]["queries_per_eligible_cell"]==15
            and cfg["queries"]["rho_count"]==5,
            "Original frozen-query contract changed")
    require(cfg["methods"]["M2"]["joint_models"]==27
            and cfg["methods"]["M3"]["full_joint_support"]==N_M3
            and cfg["methods"]["M3"]["graph_budget_per_physical_cell"]==BUDGET
            and cfg["methods"]["M1"]["graph_trajectories_per_joint_model"]==N_M1M2
            and cfg["methods"]["M2"]["graph_trajectories_per_joint_model"]==N_M1M2,
            "Original full-support scientific budgets changed")
    require(cfg["methods"]["M3"]["allocation"]["integer_rule"].startswith("initialize N_j=1"),
            "Original M3 minimax allocation rule changed")
    require(seeds["graph_prediction"]["M3"]["support_size"]==N_M3,
            "Original M3 support size changed")
    require(cfg["horizons"]["prediction_grid_seconds"]==
            {"start":0,"end_inclusive":240,"step":5},
            "Original graph prediction grid changed")
    return cfg,seeds,source


def validate_inputs(a):
    stagefile=a.staging/"b0001_public_inputs_manifest.json"
    v3bfile=a.v3b/"b0001_v3b_selection_audit_freeze.json"
    require(stagefile.is_file() and v3bfile.is_file(),
            "Frozen B0001 staging or V3b selection manifest missing")
    stage=load(stagefile)
    freeze=load(v3bfile)
    require(stage["status"]=="B0001_PUBLIC_PREDICTION_INPUTS_STAGED_NOT_EXECUTABLE"
            and stage["cells"]==12 and stage["queries_per_cell"]==15
            and stage["prediction_execution_authorized"] is False
            and stage["hidden_world_parameters_copied"] is False
            and stage["calibration_or_confirmation_values_copied"] is False,
            "Staged predictor input firewall invalid")
    require(freeze["status"]=="B0001_V3B_SELECTION_AND_AUDIT_FROZEN_GRAPH_BLOCKED"
            and freeze["n_provider_selections"]==9 and freeze["n_worlds"]==3
            and freeze["new_provider_simulations"] is False
            and freeze["graph_prediction_authorized"] is False
            and freeze["replay_used_for_selection"] is False
            and freeze["centroid_used_for_selection"] is False
            and freeze["graph_prediction_used"] is False
            and freeze["graph_whitebox_used"] is False
            and freeze["final_whitebox_used"] is False,
            "Frozen V3b selection firewall invalid")
    require(freeze["scope"]=="B0001_P1_P3_P4",
            "Unexpected selected B0001 role set")
    cfg,seeds,source=source_contract()
    require(freeze["v3b_selection_contract_sha256"]==
            sha(PHASE5/"config_phase5_provider_reconstruction_v3b.json"),
            "V3b selection was frozen with another scientific contract")
    for name,digest in freeze["summary_sha256"].items():
        require((a.v3b/name).is_file() and sha(a.v3b/name)==digest,
                "V3b freeze summary has changed: "+name)
    paths={}
    for record in stage["staged_files"]:
        rel=record["path"]
        require(rel not in paths,"Duplicate public staging file in manifest")
        p=a.staging/rel
        require(p.is_file() and sha(p)==record["staged_sha256"],
                "B0001 staged public evidence modified: "+rel)
        paths[rel]=record["staged_sha256"]
    require(len(paths)==30,"Expected 18 provider public files and 12 query files")
    return stage,freeze,paths,cfg,seeds,source


def audit_queries(a,paths,cfg):
    details=[]
    query_hashes={}
    expected={(r,g) for r in ROLES for g in GRAPHS}
    observed=set()
    for role,graph in sorted(expected):
        relative=f"frozen_queries/{role}__{graph}/step0_frozen_queries.csv"
        require(relative in paths,"Missing public frozen query file: "+relative)
        path=a.staging/relative
        q=pd.read_csv(path)
        require(list(q.columns)==list(COLUMNS) or
                (len(q.columns)==len(COLUMNS) and set(q.columns)==set(COLUMNS)),
                "Query includes unapproved columns or is missing definitions: "+relative)
        require(len(q)==15 and q["query_id"].astype(str).is_unique,
                "Expected exactly 15 unique frozen queries: "+relative)
        require(set(q["provider_world_id"].astype(str))=={role}
                and set(q["graph_id"].astype(str))=={graph}
                and set(q["step0_cell_status"].astype(str))=={"FROZEN_PHASE5_STEP0_PASS_V2"},
                "Query world/graph/eligibility mismatch: "+relative)
        require(set(q["regime"].astype(str))=={"Easy","Mid","Stress"},
                "Unexpected Step-0 regime names: "+relative)
        rhos=q["rho"].to_numpy(float)
        require(np.isfinite(rhos).all() and np.all((rhos>0)&(rhos<=1)),
                "Nonfinite or inadmissible rho: "+relative)
        require(q["rho_label"].astype(str).nunique()==5
                and len(np.unique(rhos))==5
                and q.groupby("regime")["rho"].nunique().to_dict()==
                {"Easy":5,"Mid":5,"Stress":5},
                "Expected 5 rho values crossed with 3 regimes: "+relative)
        # Query-specific numeric admissibility belongs to the public interface;
        # make no inference from final WB success/failure.
        for col in ("scale","A_G_l_max","A_G_c_max","A_G_q_min"):
            vals=q[col].to_numpy(float)
            require(np.isfinite(vals).all() and (vals>=0).all(),
                    "Nonfinite or negative public query value: "+relative+"/"+col)
        require(np.all(q["A_G_q_min"].to_numpy(float)<=1),
                "Public query quality threshold exceeds 1: "+relative)
        observed.add((role,graph))
        query_hashes[f"{role}/{graph}"]=sha(path)
        details.append({"role":role,"graph":graph,"n_queries":15,
                        "n_rho":5,"n_regimes":3,"query_sha256":sha(path)})
    require(observed==expected,"Frozen graph-query cell matrix is incomplete")
    return query_hashes,details


def audit_support(a,freeze,paths):
    # Use original support-construction mathematics and original allocation
    # routine, not a new approximation.
    sys.path.insert(0,str(PHASE5))
    sys.path.insert(0,str(PHASE4))
    from phase5_reconstruction_v3_selection import joint_product_support
    from m3_v4_dominant_mass_graph import _integer_minimax_allocations

    provider_meta={}
    world_meta={}
    allocations={}
    for role in ROLES:
        model_sets={}
        m3_weights={}
        for provider in PROVIDERS:
            label=f"{role}/{provider}"
            root=a.v3b/role/provider
            manifest=root/"provider_selection_freeze_manifest.json"
            require(manifest.is_file()
                    and sha(manifest)==freeze["provider_manifest_sha256"][label],
                    "V3b frozen provider selection manifest hash mismatch: "+label)
            pm=load(manifest)
            require(pm["status"]=="FROZEN_PHASE5_V3B_PROVIDER_SELECTION"
                    and pm["inputs"]["provider_world_id"]==role
                    and pm["inputs"]["provider_id"]==provider
                    and pm["inputs"]["selection_metric"]=="rescore_rmse"
                    and pm["inputs"]["replay_used_for_selection"] is False
                    and pm["inputs"]["behavioral_centroid_used_for_selection"] is False,
                    "V3b provider selection semantics changed: "+label)
            for flag in ("graph_prediction_used","graph_WB_used","final_WB_used"):
                require(pm["inputs"][flag] is False,
                        "V3b provider selection crossed evidence firewall: "+label)
            tables={}
            for method,name,count in (
                ("M1","m1_provider_model.csv",1),
                ("M2","m2_provider_models.csv",3),
                ("M3","m3_provider_models.csv",7),
            ):
                file=root/name
                require(file.is_file() and
                        pm["output_hashes_sha256"][
                            {"M1":"m1_provider_model","M2":"m2_provider_models",
                             "M3":"m3_provider_models"}[method]]==sha(file),
                        "V3b model table hash mismatch: "+label+"/"+method)
                table=pd.read_csv(file)
                ids=table["candidate_id"].astype(str).tolist()
                require(len(table)==count and len(set(ids))==count
                        and all(cid.startswith(f"{role}_{provider}_V3_FIT") for cid in ids),
                        "V3b candidate set/cardinality invalid: "+label+"/"+method)
                for col in ("mean_service_time","cost_rate","service_cv"):
                    require(np.isfinite(table[col].to_numpy(float)).all(),
                            "Nonfinite surrogate parameter: "+label+"/"+col)
                require((table["mean_service_time"].to_numpy(float)>0).all()
                        and (table["cost_rate"].to_numpy(float)>0).all()
                        and (table["service_cv"].to_numpy(float)>=0).all(),
                        "Invalid graph-surrogate parameter: "+label)
                tables[method]=table
            m1,m2,m3=tables["M1"],tables["M2"],tables["M3"]
            require(m1["candidate_id"].astype(str).iloc[0]==
                    m2["candidate_id"].astype(str).iloc[0]
                    and set(m2["candidate_id"].astype(str)).issubset(
                        set(m3["candidate_id"].astype(str))),
                    "M1/M2/M3 candidate nesting invalid: "+label)
            rank_file=root/"v3b_candidate_quality_ranking.csv"
            require(sha(rank_file)==pm["output_hashes_sha256"]["quality_ranking"],
                    "V3b quality ranking hash mismatch: "+label)
            rank=pd.read_csv(rank_file)
            require(len(rank)==7
                    and rank["v3b_quality_rank"].astype(int).tolist()==list(range(1,8))
                    and rank["candidate_id"].astype(str).iloc[:3].tolist()==
                    m2["candidate_id"].astype(str).tolist()
                    and rank["candidate_id"].astype(str).iloc[0]==
                    m1["candidate_id"].astype(str).iloc[0],
                    "M1/M2 not first ranks of V3b quality ordering: "+label)
            require(np.isfinite(rank["rescore_rmse"].to_numpy(float)).all()
                    and np.all(np.diff(rank["rescore_rmse"].to_numpy(float))>=-1e-12),
                    "V3b quality RMSE ranking invalid: "+label)
            require(np.allclose(m2["provider_weight"].to_numpy(float),1/3,
                                rtol=0,atol=1e-12),
                    "M2 provider weights not equal thirds: "+label)
            require(np.isfinite(m3["weight"].to_numpy(float)).all()
                    and (m3["weight"].to_numpy(float)>=0).all()
                    and abs(float(m3["weight"].sum())-1)<1e-12,
                    "M3 Gibbs provider weights invalid: "+label)
            # Check original public I1 surface is available for each provider.
            pub=f"public_I1/{role}/{provider}/sigma_surface.csv"
            card=f"public_I1/{role}/{provider}/card.json"
            require(pub in paths and card in paths,
                    "Frozen public-I1 provider input missing: "+label)
            surface=pd.read_csv(a.staging/pub,usecols=[
                "provider_id","region_id","region_rho","rho","horizon","sigma_hat"
            ])
            require(not surface.empty and
                    set(surface["provider_id"].astype(str))=={provider},
                    "Public-I1 provider surface incompatible with selected model: "+label)
            require(np.isfinite(surface["sigma_hat"].to_numpy(float)).all()
                    and surface["sigma_hat"].between(0,1).all(),
                    "Public-I1 sigma values outside [0,1]: "+label)
            model_sets[provider]=tables
            m3_weights[provider]=m3[["candidate_id","weight"]]
            provider_meta[label]={
                "m1_id":m1["candidate_id"].iloc[0],
                "m2_ids":m2["candidate_id"].astype(str).tolist(),
                "m3_ids":m3["candidate_id"].astype(str).tolist(),
                "m3_weight_sum":float(m3["weight"].sum()),
                "m1_model_sha256":sha(root/"m1_provider_model.csv"),
                "m2_model_sha256":sha(root/"m2_provider_models.csv"),
                "m3_model_sha256":sha(root/"m3_provider_models.csv"),
            }
        world=a.v3b/role
        wm_path=world/"world_selection_freeze_manifest.json"
        require(wm_path.is_file()
                and sha(wm_path)==freeze["world_manifest_sha256"][role],
                "V3b world selection freeze hash mismatch: "+role)
        wm=load(wm_path)
        require(wm["status"]=="FROZEN_PHASE5_V3B_WORLD_SELECTION"
                and wm["M1_joint_models"]==1
                and wm["M2_joint_models"]==27
                and wm["M3_joint_models"]==343
                and wm["M3_top14_models"]==14,
                "V3b world support method cardinalities invalid: "+role)
        expected_m2=[
            (x.candidate_id,y.candidate_id,z.candidate_id)
            for x in model_sets["ProviderA"]["M2"].itertuples(index=False)
            for y in model_sets["ProviderB"]["M2"].itertuples(index=False)
            for z in model_sets["ProviderC"]["M2"].itertuples(index=False)
        ]
        m2=pd.read_csv(world/"m2_joint_support_27.csv")
        require(len(m2)==27 and
                np.allclose(m2["joint_weight"].to_numpy(float),1/27,
                            atol=1e-12,rtol=0),
                "M2 full joint weights/cardinality incorrect: "+role)
        ids=[tuple(x) for x in m2[[f"{p}_candidate_id" for p in PROVIDERS]]
             .astype(str).itertuples(index=False,name=None)]
        require(ids==expected_m2 and
                m2["joint_rank"].astype(int).tolist()==list(range(1,28)),
                "M2 joint candidate ordering incorrect: "+role)
        expected_m3=joint_product_support(m3_weights)
        m3=pd.read_csv(world/"m3_joint_support_343.csv")
        top14=pd.read_csv(world/"m3_joint_support_top14.csv")
        require(len(m3)==N_M3 and len(top14)==14
                and m3["joint_rank"].astype(int).tolist()==list(range(1,N_M3+1))
                and top14["joint_rank"].astype(int).tolist()==list(range(1,15)),
                "M3 full/Top14 support cardinality invalid: "+role)
        for name,seen,expected in (
            ("full",m3,expected_m3),("Top14",top14,expected_m3.head(14))):
            require(seen[[f"{p}_candidate_id" for p in PROVIDERS]]
                    .astype(str).to_numpy().tolist()==
                    expected[[f"{p}_candidate_id" for p in PROVIDERS]]
                    .astype(str).to_numpy().tolist()
                    and np.allclose(seen["joint_weight"].to_numpy(float),
                                    expected["joint_weight"].to_numpy(float),
                                    rtol=0,atol=1e-15),
                    "M3 joint model/weight ordering changed: "+role+"/"+name)
        for key,path in wm["outputs"].items():
            fp=Path(path).resolve()
            require(fp.is_file() and fp.parent==world.resolve() and
                    sha(fp)==wm["output_hashes_sha256"][key],
                    "Frozen V3b world output hash mismatch: "+role+"/"+key)

        # Exact original Phase-5 integer-minimax allocation, no simulation.
        weights=m3["joint_weight"].to_numpy(float)
        alloc=_integer_minimax_allocations(weights,[BUDGET]).copy()
        require(len(alloc)==N_M3
                and "n_trajectories" in alloc.columns
                and "rank" in alloc.columns,
                "Original allocation helper returned unexpected schema")
        alloc=alloc.sort_values("rank",kind="mergesort").reset_index(drop=True)
        nn=alloc["n_trajectories"].to_numpy(int)
        require(alloc["rank"].astype(int).tolist()==list(range(1,N_M3+1))
                and nn.min()>=1 and int(nn.sum())==BUDGET
                and nn.max()<SEED_STRIDE,
                "M3 fullsupport allocation invalid: "+role)
        alloc["joint_weight"]=weights
        alloc["seed_start"]=[SEED_M3+(r-1)*SEED_STRIDE
                             for r in range(1,N_M3+1)]
        alloc["seed_end_inclusive"]=[
            int(start)+int(n)-1
            for start,n in zip(alloc["seed_start"],nn)
        ]
        require(int(alloc["seed_end_inclusive"].max())<=MAX_NATIVE,
                "M3 native provider RNG seed would overflow")
        require(np.all(alloc["seed_end_inclusive"].to_numpy(int)[:-1]<
                       alloc["seed_start"].to_numpy(int)[1:]),
                "M3 rank seed streams collide")
        allocations[role]=alloc
        world_meta[role]={
            "m1_joint_models":1,
            "m2_joint_models":27,
            "m3_joint_models":N_M3,
            "m3_total_budget":BUDGET,
            "m3_min_trajectories_per_rank":int(nn.min()),
            "m3_max_trajectories_per_rank":int(nn.max()),
            "m3_top14_mass":float(weights[:14].sum()),
            "m2_support_sha256":sha(world/"m2_joint_support_27.csv"),
            "m3_support_sha256":sha(world/"m3_joint_support_343.csv"),
            "m3_top14_sha256":sha(world/"m3_joint_support_top14.csv"),
        }
    return provider_meta,world_meta,allocations


def reserved_seeds(a,allocations):
    # All ranks use the same seed suffix namespace across eligible worlds and
    # graphs, as common random numbers; only world-specific prefix sizes differ.
    # Cross-world/cell reuse is intentional, not an accidental collision.
    common=(SEED_M1M2,SEED_M1M2+N_M1M2-1)
    m3=(SEED_M3,SEED_M3+(N_M3-1)*SEED_STRIDE+BUDGET-1)
    require(m3[1]<=MAX_NATIVE and common[1]<=MAX_NATIVE,
            "Fresh B0001 graph seed exceeds native provider RandomState range")
    require(common[1]<m3[0],"M1/M2 and M3 graph banks overlap")
    # Prior B0001 I1/Step-0/M1/V3 reconstruction banks all remain embargoed
    # for graph prediction. Explicitly compare only known immutable manifests.
    evidence=load(a.eligibility)
    require(evidence["status"]=="B0001_STEP0_ELIGIBILITY_EVIDENCE_FROZEN",
            "Missing immutable B0001 Step-0 seed provenance")
    occupied=[]
    for att in evidence["attempts"]:
        for key,bank in att["seed_blocks"].items():
            occupied.append((att["candidate_id"]+"/"+key,
                             int(bank["start"]),int(bank["end_inclusive"])))
    setup=load(a.domains.parent/"domain_setup.json")
    for role in ROLES:
        for key,bank in setup["phases"][role]["M1_seed_banks"].items():
            occupied.append((role+"/M1/"+key,int(bank["start"]),int(bank["end_inclusive"])))
        config=load(a.v3_workspace/"frozen_contracts"/
                    f"config_b0001_v3_seed_registry_{role}.json")
        for key,bank in config["provider_reconstruction"].items():
            occupied.append((role+"/V3/"+key,int(bank["start"]),int(bank["end_inclusive"])))
    historical=load(PHASE5/"config_phase5_seed_registry_v3b_fullsupport.json")
    old=historical["graph_prediction"]
    occupied.append(("original_Phase5_M1_M2",
                     int(old["M1_M2_common_bank"]["start"]),
                     int(old["M1_M2_common_bank"]["end_inclusive"])))
    orig_m3=old["M3"]
    occupied.append(("original_Phase5_M3",
                     int(orig_m3["seed_base"]),
                     int(orig_m3["seed_base"])+342*int(orig_m3["seed_block_stride"])+BUDGET-1))
    for label,lo,hi in occupied:
        require(common[1]<lo or common[0]>hi,
                "Fresh M1/M2 graph seed bank overlaps "+label)
        require(m3[1]<lo or m3[0]>hi,
                "Fresh M3 graph seed bank overlaps "+label)
    for role,alloc in allocations.items():
        require(int(alloc["seed_start"].min())==SEED_M3
                and int(alloc["seed_end_inclusive"].max())<=m3[1],
                "M3 allocated seeds disagree with reserved graph namespace: "+role)
    return {
        "reuse_semantics":"Within each world all four graphs reuse rank streams as CRN; same seed labels may be reused across worlds, following original Phase-5 semantics",
        "m1_m2_common_100":{"start":common[0],"end_inclusive":common[1],
                            "n":N_M1M2},
        "m3":{"support_size":N_M3,"seed_base":SEED_M3,
              "seed_block_stride":SEED_STRIDE,
              "budget_per_cell":BUDGET,
              "maximum_reserved_seed":m3[1]},
        "native_rng_max_trajectory_seed":MAX_NATIVE,
        "cross_stage_collisions":0,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging",type=Path,required=True)
    parser.add_argument("--v3b",type=Path,required=True)
    parser.add_argument("--v3-workspace",type=Path,required=True)
    parser.add_argument("--domains",type=Path,required=True)
    parser.add_argument("--eligibility",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    for name in ("staging","v3b","v3_workspace","domains","eligibility","out"):
        setattr(a,name,getattr(a,name).expanduser().resolve())
    require(not a.out.exists(),"Refusing to overwrite graph-preflight workspace")
    require(a.out!=REPO and REPO not in a.out.parents,
            "No outputs permitted inside source repository")
    for inputpath in (a.staging,a.v3b,a.v3_workspace,a.domains,a.domains.parent,
                      a.eligibility.parent):
        require(a.out!=inputpath and inputpath not in a.out.parents
                and a.out not in inputpath.parents,
                "Graph preflight must be separate from private and public source inputs")
    stage,freeze,files,cfg,seeds,source=validate_inputs(a)
    query_hashes,queries=audit_queries(a,files,cfg)
    provider_info,world_info,allocations=audit_support(a,freeze,files)
    bank=reserved_seeds(a,allocations)
    a.out.mkdir(parents=True)
    allocation_hashes={}
    for role,frame in allocations.items():
        path=a.out/f"m3_fullsupport_allocation_{role}.csv"
        frame.to_csv(path,index=False)
        allocation_hashes[role]=sha(path)
    cell_rows=[]
    for role in ROLES:
        for graph in GRAPHS:
            cell_rows.append({"provider_world_id":role,"graph_id":graph,
                              "physical_cell_id":f"{role}__{graph}",
                              "queries_sha256":query_hashes[f"{role}/{graph}"],
                              "m1_m2_n":N_M1M2,
                              "m2_joint_models":27,
                              "m3_joint_models":N_M3,
                              "m3_total_budget":BUDGET,
                              "m3_allocation_sha256":allocation_hashes[role]})
    status=a.out/"b0001_graph_cell_preflight.csv"
    pd.DataFrame(cell_rows).to_csv(status,index=False)
    manifest={
        "status":"B0001_GRAPH_PREDICTION_PREFLIGHT_PASS_EXECUTION_BLOCKED",
        "scientific_simulations_executed":0,
        "v3b_selection_freeze_sha256":sha(a.v3b/"b0001_v3b_selection_audit_freeze.json"),
        "public_staging_manifest_sha256":sha(a.staging/"b0001_public_inputs_manifest.json"),
        "original_graph_source_sha256":source,
        "n_worlds":3,
        "n_provider_models_sets":9,
        "n_graph_cells":12,
        "queries_per_cell":15,
        "graph_prediction_horizons":49,
        "query_sha256_by_cell":query_hashes,
        "provider_selection_sha256_and_ids":provider_info,
        "world_support_sha256_and_allocation":world_info,
        "allocation_sha256":allocation_hashes,
        "cell_preflight_sha256":sha(status),
        "graph_seed_plan":bank,
        "m0_unchanged":True,
        "m1_m2_seed_common_random_numbers":True,
        "m3_343_fullsupport_allocation_frozen":True,
        "hidden_generating_parameters_read":False,
        "step0_WB_outcomes_read":False,
        "graph_whitebox_read":False,
        "final_whitebox_read":False,
        "graph_prediction_execution_authorized":False,
        "next_gate":"B0001 isolated graph runner and adapter smoke before scientific predictions",
    }
    frozen=a.out/"b0001_graph_prediction_preflight.json"
    save(frozen,manifest)
    print("B0001_GRAPH_PREDICTION_PREFLIGHT_PASS 12 cells 9 providers",flush=True)
    print("B0001_FULL343_ALLOCATIONS_PASS 3 worlds B=1400",flush=True)
    print("B0001_GRAPH_SEED_PLAN_PASS native-uint32 and disjoint from reconstruction",flush=True)
    print("NO_SIMULATIONS / GRAPH_EXECUTION_BLOCKED pending isolated runner smoke",flush=True)
    print("MANIFEST",frozen,flush=True)


if __name__=="__main__":
    main()
