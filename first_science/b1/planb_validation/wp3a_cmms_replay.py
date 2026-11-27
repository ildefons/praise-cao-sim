#!/usr/bin/env python3
"""WP3a frozen CMMS replay, input gate, resumable execution and provenance.

No hardware experiment, simulator, training or prior fitting. Real acquisitions
are executed only in an explicit --stage command. Output directories are immutable.
"""
import argparse
import hashlib
import io
import json
import platform
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from wp3a_policy_core import Catalogue, Gaussian, POLICIES, NESTED, TOL, trajectory, score

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
PROTOCOL="WP3A_CMMS_EXPERIMENTAL_PROTOCOL_2026_11_27_V1.md"
ZIP_SHA="f146fff83bba95cc970faf96cc65ea3943f6508f48351d4a9389120e4aaaa4c2"
CSV_SHA="e6c2a7bb5231c267f1974cefde6bb745bf5bf7f98ba1df7eb612707d92c57038"
CSV_NAME="paper_data/all_clusters_merged.csv"
METHODS=("NoOp","LL","Heuristic","Myopic","DQN","AIF-Hier")
TOKENS=("noop","least_loaded","heuristic","myopic","dqn","aif_hier_v2")
H=("2-node-homo-light","2-node-het-light","5-node-light","8-node-light","8-node-heavy")
S=("ramp_up","burst","steady_overload","oscillating")
CAT=Catalogue(METHODS,H,S)
BUDGETS=(14,21,29,36,43,50,57,64,79,93,100,107,114)
REPEATS=20
SEED=20261127
BASE=(.20,.12,.08,.09,.50)
SCENARIOS={
    "base":BASE,
    "intercept_half":(.10,.12,.08,.09,.50),
    "intercept_double":(.40,.12,.08,.09,.50),
    "configuration_half":(.20,.06,.08,.09,.50),
    "configuration_double":(.20,.24,.08,.09,.50),
    "pattern_half":(.20,.12,.04,.09,.50),
    "pattern_double":(.20,.12,.16,.09,.50),
    "noise_half":(.20,.12,.08,.045,.50),
    "noise_double":(.20,.12,.08,.18,.50),
    "factor_swap":(.20,.08,.12,.09,.50),
    "all_prior_half":(.10,.06,.04,.09,.50),
    "all_prior_double":(.40,.24,.16,.09,.50),
    "mean_low":(.20,.12,.08,.09,.30),
    "mean_high":(.20,.12,.08,.09,.70),
}
STRUCTURES=("independent","exchangeable","interaction25")
STRUCT_POLICIES=("kg_one_step","kg_two_stage_adaptive")
CODE_FILES=("wp3a_policy_core.py","wp3a_cmms_replay.py","wp3a_cmms_analysis.py",
            "test_wp3a_cmms.py",PROTOCOL)
LEGACY_FILES=("b1_budget_comparison_v1.py","b1_kg_one_step_v1.py",
              "b1_condition_selection_controlled_v1.py","b1_nested_budget_replay_v1.py",
              "extend_b1_original_nine_policy_budgets_v1.py","b1_prior_sensitivity_replay_v1.py")


def require(ok,msg):
    if not ok:
        raise ValueError(msg)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(2**20),b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+"\n")


def provenance():
    return {"code_and_protocol_sha256":{n:sha(HERE/n) for n in CODE_FILES+LEGACY_FILES},
            "source_commit":subprocess.check_output(["git","-C",str(REPO),"rev-parse","HEAD"],text=True).strip(),
            "versions":{"python":platform.python_version(),"numpy":np.__version__,
                        "pandas":pd.__version__,"scipy":scipy.__version__},
            "thread_environment":{k:os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS")}}


def load_source(path):
    path=Path(path).expanduser().resolve()
    require(sha(path)==ZIP_SHA,"Unexpected source ZIP SHA-256")
    with zipfile.ZipFile(path) as z:
        require(z.namelist().count(CSV_NAME)==1,"Ambiguous canonical CSV")
        raw=z.read(CSV_NAME)
    require(hashlib.sha256(raw).hexdigest()==CSV_SHA,"Unexpected canonical CSV SHA-256")
    d=pd.read_csv(io.BytesIO(raw))
    require(d.shape==(424,31) and not d.isna().any().any(),"CSV schema/NA")
    require(np.isfinite(d.select_dtypes("number")).all().all(),"Nonfinite CSV")
    require(not d.duplicated().any() and not d.duplicated(["cluster","controller","scenario","run_id"]).any(),"Duplicate episodes")
    require(set(d.controller)==set(TOKENS)|{"round_robin"} and set(d.cluster)==set(H),"Unexpected catalogue labels")
    expected_scenarios={"scenario_"+s+("_heavy" if h.endswith("-heavy") else "") for h in H for s in S}
    require(set(d.scenario)==expected_scenarios,"Unexpected scenario labels")
    require((d.workload==np.where(d.cluster.str.endswith("-heavy"),"HEAVY","LIGHT")).all(),"Load/cluster mismatch")
    require((d.scenario.str.endswith("_heavy")==d.cluster.str.endswith("-heavy")).all(),"Scenario/cluster mismatch")
    require(d.slo_satisfaction_rate.between(0,1).all() and (d.total_windows>0).all(),"Invalid Raw SLO")
    require((d.slo_satisfaction_rate-(1-d.slo_violations/d.total_windows)).abs().max()<=.0000500001,"Raw SLO count mismatch")
    require((d.skip_budget_violated==0).all() and d.skip_ratio.between(0,.30).all(),"Skip constraint")
    require((d.controller=="round_robin").sum()==48,"Round-Robin scope mismatch")
    d=d[d.controller!="round_robin"].copy()
    require(len(d)==376,"Paper portfolio count")
    d["pattern"]=d.scenario.str.removeprefix("scenario_").str.removesuffix("_heavy")
    d["method"]=d.controller.map(dict(zip(TOKENS,METHODS)))
    require(d.method.notna().all(),"Unmapped method")
    g=d.groupby(["method","cluster","pattern"],sort=False)
    require(g.ngroups==120,"Incomplete catalogue")
    for a in METHODS:
        for h,s in CAT.cells:
            actual=sorted(g.get_group((a,h,s)).run_id.tolist())
            expected=list(range(1,6 if a=="AIF-Hier" and h.startswith("2-node") else 4))
            require(actual==expected,"Replication contract failed at "+str((a,h,s)))
    require(len(d[d.run_id<=3])==360,"Balanced replication scope")
    return d


def reference(d,balanced=False):
    if balanced:
        d=d[d.run_id<=3]
    rows=[]; y=np.empty((CAT.A,CAT.C))
    g=d.groupby(["method","cluster","pattern"],sort=False)
    for a,method in enumerate(METHODS):
        for c,(h,s) in enumerate(CAT.cells):
            values=g.get_group((method,h,s)).sort_values("run_id").slo_satisfaction_rate.to_numpy()
            y[a,c]=1-float(values.mean())
            rows.append(dict(method_index=a,condition_index=c,method=method,cluster=h,pattern=s,
                             loss=y[a,c],raw_slo=float(values.mean()),n_runs=len(values),
                             raw_slo_sd=float(values.std(ddof=1))))
    require(np.isfinite(y).all() and ((0<=y)&(y<=1)).all(),"Reference bounds")
    return y,pd.DataFrame(rows)


def expected_counts(policies,budgets=BUDGETS,repeats=REPEATS,cat=CAT):
    nested=sum(p in NESTED for p in policies)
    top=len(policies)-nested
    n=cat.C*repeats
    return (len(policies)*len(budgets)*n,
            n*(nested*max(budgets)+top*sum(budgets)),
            n*(nested+top*len(budgets)))


def design(name):
    if name in SCENARIOS:
        return "primary",SCENARIOS[name],"additive",POLICIES
    if name=="balanced_runs":
        return "balanced",BASE,"additive",POLICIES
    if name in STRUCTURES:
        return "primary",BASE,name,STRUCT_POLICIES
    raise ValueError(name)


def write_reference(root,d,prov):
    dest=root/"reference"
    matrices={}; tables={}
    for name in ("primary","balanced"):
        matrices[name],tables[name]=reference(d,name=="balanced")
    if dest.exists():
        m=json.loads((dest/"manifest.json").read_text())
        require(m["zip_sha256"]==ZIP_SHA and m["csv_sha256"]==CSV_SHA,"Reference provenance mismatch")
        for name in matrices:
            p=dest/(name+".csv")
            require(sha(p)==m["outputs_sha256"][p.name],"Reference SHA mismatch")
            old=pd.read_csv(p,float_precision="round_trip")
            require(old.equals(tables[name]),"Reference does not reproduce")
        return matrices,m["outputs_sha256"]
    tmp=Path(tempfile.mkdtemp(prefix=".reference_incomplete_",dir=root))
    for name,table in tables.items():
        table.to_csv(tmp/(name+".csv"),index=False)
    hashes={p.name:sha(p) for p in tmp.glob("*.csv")}
    dump(tmp/"manifest.json",{"status":"REFERENCE_VERIFIED","zip_sha256":ZIP_SHA,"csv_sha256":CSV_SHA,
         "source_mapping":dict(zip(TOKENS,METHODS)),"configurations":H,"patterns":S,
         "scope":"376 primary episodes, 360 balanced; arithmetic mean Raw SLO per cell; equal cell weight",
         "outputs_sha256":hashes,"provenance":prov})
    tmp.rename(dest)
    return matrices,hashes


def verify_case(root,name,reference_hash,prov):
    dest=root/name
    m=json.loads((dest/"manifest.json").read_text())
    matrix,params,structure,policies=design(name)
    expected=expected_counts(policies)
    require(m["status"]=="WP3A_CASE_COMPLETE" and m["case"]==name and m["matrix"]==matrix
            and m["reference_sha256"]==reference_hash and tuple(m["params"])==tuple(params)
            and m["structure"]==structure and tuple(m["policies"])==tuple(policies)
            and tuple(m["budgets"])==BUDGETS and m["repeats"]==REPEATS and m["seed"]==SEED
            and tuple(m["counts"])==expected,"Case manifest conflicts with frozen design")
    require(m["provenance"]["code_and_protocol_sha256"]==prov["code_and_protocol_sha256"]
            and m["provenance"]["versions"]==prov["versions"]
            and m["provenance"]["thread_environment"]==prov["thread_environment"],"Code/environment changed; use a new versioned output root")
    require(set(m["outputs_sha256"])=={"terminals.csv","paths.npz"},"Missing case outputs")
    for f,d in m["outputs_sha256"].items():
        require(sha(dest/f)==d,"Case output hash mismatch: "+f)
    return m


def verify_paths(y,model,policies,paths,meta,terminals,check_covariance=False):
    """Independent post-run scorer: reconstruct masks from lossless action IDs.

    At checkpoints compute posterior means from selected observations only;
    independently recompute regret/PCS and verify the finite-target rankings.
    Primary base also checks coefficient vs covariance-space moments.
    """
    cat=model.cat
    truth=y.mean(axis=1)
    cov=Gaussian(cat,model.params,"additive_cov") if check_covariance else None
    t_expected,a_expected,p_expected=expected_counts(policies,cat=cat)
    require(len(terminals)==t_expected and len(paths)==len(meta)==p_expected,"Wrong episode/path count")
    require(not terminals.duplicated(["policy","budget","start_index","replicate"]).any(),"Duplicate terminal keys")
    require(len(set(map(tuple,meta)))==len(meta),"Duplicate history keys")
    require(int((paths>=0).sum())==a_expected,"Wrong action count")
    require(terminals.trajectory_id.between(0,len(paths)-1).all(),"Invalid trajectory ID")
    grouped={int(i):g.sort_values("budget") for i,g in terminals.groupby("trajectory_id")}
    near_ties=0; max_mean_error=0.; max_cov_error=0.
    for i,(p,start,rep,B) in enumerate(meta):
        policy=POLICIES[int(p)]
        require(policy in policies and 0<=start<cat.C and 0<=rep<REPEATS,"Invalid path metadata")
        require(B==max(BUDGETS) if policy in NESTED else B in BUDGETS,"Invalid path budget")
        ids=paths[i,:B].astype(int)
        require(((0<=ids)&(ids<cat.A*cat.C)).all() and (paths[i,B:]==-1).all(),"Invalid action IDs/padding")
        require(len(set(ids))==B and np.array_equal(ids[:cat.A],np.arange(cat.A)*cat.C+start),"Repeated action or wrong initialization")
        g=grouped[i]
        checkpoints=BUDGETS if policy in NESTED else (int(B),)
        require(tuple(g.budget)==checkpoints and (g.policy==policy).all() and
                (g.start_index==start).all() and (g.replicate==rep).all(),"History/terminal mismatch")
        masks=[0]*cat.A
        values=np.zeros_like(y)
        previous=0
        for row in g.itertuples(index=False):
            for action in ids[previous:row.budget]:
                a,c=divmod(int(action),cat.C)
                masks[a]|=1<<c; values[a,c]=y[a,c]
            previous=row.budget
            moments=[model.moments(masks[a],values[a]) for a in range(cat.A)]
            mu=np.array([v[0] for v in moments]); finite=np.array([v[1] for v in moments])
            err=float(np.max(abs(finite-(model.m0+model.scale*(mu-model.m0)))))
            max_mean_error=max(max_mean_error,err)
            require(err<1e-10,"WP2 affine relation failed")
            chosen=int(row.recommended_index)
            require(0<=chosen<cat.A and row.recommended==cat.methods[chosen],"Invalid recommendation")
            require(chosen==int(np.argmin(mu)),"Terminal recommendation does not reproduce")
            if chosen!=int(np.argmin(finite)):
                require(finite[chosen]-finite.min()<=TOL,"Finite estimator changes substantive recommendation")
                near_ties+=1
            r=max(0.,float(truth[chosen]-truth.min()))
            require(abs(r-row.simple_regret)<1e-12 and int(r<=TOL)==row.correct,"Regret/PCS does not reproduce")
            if cov is not None:
                for a,v in enumerate(moments):
                    ref=cov.moments(masks[a],values[a])
                    err=max(abs(v[0]-ref[0]),abs(v[1]-ref[1]),abs(v[2]-ref[2]),float(np.max(abs(v[3]-ref[3]))))
                    max_cov_error=max(max_cov_error,err)
                    require(err<1e-10,"Coefficient/covariance posterior mismatch")
    if cov is not None:
        cov.cached.cache_clear()
    return {"finite_mean_max_error":max_mean_error,"finite_argmin_near_ties":near_ties,
            "coefficient_covariance_max_error":max_cov_error if check_covariance else None,
            "terminal_rows_verified":len(terminals),"action_rows_verified":a_expected}


def run_case(root,name,matrices,hashes,prov):
    matrix,params,structure,policies=design(name)
    refhash=hashes[matrix+".csv"]
    dest=root/name
    if dest.exists():
        verify_case(root,name,refhash,prov)
        print("WP3A_CASE_ALREADY_VERIFIED",name,flush=True)
        return
    y=matrices[matrix]
    model=Gaussian(CAT,params,structure)
    t_count,a_count,p_count=expected_counts(policies)
    paths=np.full((p_count,max(BUDGETS)),-1,dtype=np.int16)
    meta=np.empty((p_count,4),dtype=np.int16)
    rows=[]; i=0
    for p in policies:
        for checkpoints in ([BUDGETS] if p in NESTED else [(b,) for b in BUDGETS]):
            for start in range(CAT.C):
                for rep in range(REPEATS):
                    path,term=trajectory(y,model,p,start,rep,checkpoints,SEED)
                    paths[i,:len(path)]=path
                    meta[i]=(POLICIES.index(p),start,rep,max(checkpoints))
                    for B,a,r,correct in term:
                        rows.append(dict(trajectory_id=i,policy=p,budget=B,start_index=start,
                                         replicate=rep,recommended_index=a,recommended=METHODS[a],
                                         simple_regret=r,correct=correct))
                    i+=1
        print("WP3A_POLICY_COMPLETE",name,p,flush=True)
    require(i==p_count and len(rows)==t_count,"Incomplete run")
    terminals=pd.DataFrame(rows)
    checks=verify_paths(y,model,policies,paths,meta,terminals,name=="base")
    model.cached.cache_clear()
    tmp=Path(tempfile.mkdtemp(prefix="."+name+"_incomplete_",dir=root))
    terminals.to_csv(tmp/"terminals.csv",index=False)
    np.savez_compressed(tmp/"paths.npz",actions=paths,meta=meta)
    dump(tmp/"manifest.json",{"status":"WP3A_CASE_COMPLETE","case":name,"matrix":matrix,
         "reference_sha256":refhash,"params":params,"structure":structure,"policies":policies,
         "budgets":BUDGETS,"repeats":REPEATS,"seed":SEED,"counts":[t_count,a_count,p_count],
         "path_encoding":{"actions":"method_index*20+condition_index; -1 padding",
                          "meta_columns":["canonical_policy_index","start_index","replicate","terminal_budget"],
                          "canonical_policies":POLICIES},
         "checks":checks,"provenance":prov,
         "outputs_sha256":{p.name:sha(p) for p in tmp.iterdir() if p.is_file()}})
    tmp.rename(dest)
    print("WP3A_CASE_COMPLETE",name,checks,flush=True)


def verify_additive_paths(root,y,refhash,prov):
    """Before covariance controls reuse primary additive paths, reproduce both
    KG policies under the mathematically equivalent covariance implementation."""
    dest=root/"additive_covariance_check.json"
    base=verify_case(root,"base",refhash,prov)
    if dest.exists():
        marker=json.loads(dest.read_text())
        require(marker["base_paths_sha256"]==base["outputs_sha256"]["paths.npz"] and
                marker["base_terminals_sha256"]==base["outputs_sha256"]["terminals.csv"] and
                marker["status"]=="PASS","Covariance check mismatch")
        return
    model=Gaussian(CAT,BASE,"additive_cov")
    with np.load(root/"base/paths.npz",allow_pickle=False) as z:
        paths,meta=z["actions"],z["meta"]
    terminals=pd.read_csv(root/"base/terminals.csv",float_precision="round_trip")
    grouped={int(i):g.sort_values("budget") for i,g in terminals[terminals.policy.isin(STRUCT_POLICIES)].groupby("trajectory_id")}
    n=0
    for i,(p,start,rep,B) in enumerate(meta):
        policy=POLICIES[int(p)]
        if policy not in STRUCT_POLICIES:
            continue
        path,rows=trajectory(y,model,policy,int(start),int(rep),BUDGETS,SEED)
        require(np.array_equal(path,paths[i,:B]),"Coefficient/covariance acquisition paths differ; STOP for tie diagnosis")
        g=grouped[i]
        require(np.array_equal(np.array(rows)[:,1].astype(int),g.recommended_index),"Covariance recommendation differs; STOP")
        n+=1
    require(n==len(STRUCT_POLICIES)*CAT.C*REPEATS,"Incomplete covariance reproduction")
    model.cached.cache_clear()
    dump(dest,{"status":"PASS","trajectories":n,"base_paths_sha256":base["outputs_sha256"]["paths.npz"],
               "base_terminals_sha256":base["outputs_sha256"]["terminals.csv"],"provenance":prov})
    print("WP3A_ADDITIVE_COVARIANCE_PATHS_REPRODUCED",n,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path)
    p.add_argument("--preflight-only",action="store_true")
    p.add_argument("--stage",choices=("base","review-base","priors","balanced","structure","all","analyse"))
    p.add_argument("--prior",choices=tuple(SCENARIOS)[1:],help="One frozen nonbase prior; requires --stage priors")
    a=p.parse_args()
    require(a.preflight_only != bool(a.stage),"Choose either preflight-only or stage")
    require(a.prior is None or a.stage=="priors","--prior requires --stage priors")
    d=load_source(a.source)
    prov=provenance()
    require(len(SCENARIOS)==14 and expected_counts(POLICIES)==(46800,1242000,18000),"Design count mismatch")
    require(tuple(round(120*b/84) for b in (10,15,20,25,30,35,40,45,55,65,70,75,80))==BUDGETS,"Budget mismatch")
    require(abs(Gaussian(CAT,BASE).kappa-.8896)<1e-12,"Prior covariance mismatch")
    if a.preflight_only:
        print("CMMS_SOURCE_OK 424 rows; 376 eligible; 120 cells; 360 balanced; SHA-256 verified")
        print("WP3A_DESIGN_OK 9 policies; 13 budgets; 20 starts x 20 repeats; 46800 terminals per primary case")
        print("WP3A_PREFLIGHT_PASS no acquisitions or outputs written")
        return
    require(a.out is not None,"--out required for execution")
    root=a.out.expanduser().resolve()
    require(root!=REPO and REPO not in root.parents,"Output must be outside repository")
    root.mkdir(parents=True,exist_ok=True)
    matrices,hashes=write_reference(root,d,prov)
    if a.stage in ("base","all"):
        run_case(root,"base",matrices,hashes,prov)
    else:
        verify_case(root,"base",hashes["primary.csv"],prov)
    if a.stage=="review-base":
        from wp3a_cmms_analysis import review_base
        review_base(root,hashes,prov)
    if a.stage in ("priors","all"):
        for name in ([a.prior] if a.prior else tuple(SCENARIOS)[1:]):
            run_case(root,name,matrices,hashes,prov)
    if a.stage in ("balanced","all"):
        run_case(root,"balanced_runs",matrices,hashes,prov)
    if a.stage in ("structure","all"):
        verify_additive_paths(root,matrices["primary"],hashes["primary.csv"],prov)
        for name in STRUCTURES:
            run_case(root,name,matrices,hashes,prov)
    if a.stage in ("analyse","all"):
        from wp3a_cmms_analysis import analyse
        analyse(root,hashes,prov)
    print("WP3A_STAGE_PASS",a.stage,root,flush=True)


if __name__=="__main__":
    main()
