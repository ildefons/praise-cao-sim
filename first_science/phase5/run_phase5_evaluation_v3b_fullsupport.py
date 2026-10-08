"""Frozen deterministic evaluation for Phase-5 V3b FULL343.

This stage is the first code that intentionally joins blind prediction outputs
to the untouched N=1000 final white-box reference.  Its semantics are fixed by
config_phase5_evaluation_v3b_fullsupport.json, which was committed after the
reference mechanical audit and before any method-performance readout.

The registered WB-reference bootstrap is deliberately a later stage.  This
runner freezes deterministic pointwise joins, primary error summaries, decision
metrics, M0 applicability, M2 finite-portfolio spread diagnostics, M3 MC
precision summaries, nested M3 diagnostics, and the registered topology
contrast.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from phase5_runtime_v2 import git_head, read_json, sha256_file, utc_now_iso, write_json

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_evaluation_v3b_fullsupport.json"
PRED_ROOT=HERE/"results"/"04_prediction_v3b_fullsupport"
WB_ROOT=HERE/"results"/"05_final_wb_v3b_fullsupport"
WB_AUDIT=WB_ROOT/"phase5_v3b_fullsupport_final_wb_mechanical_audit_manifest.json"
WB_FREEZE=WB_ROOT/"phase5_v3b_fullsupport_final_wb_freeze_manifest.json"
GLOBAL_PRED=PRED_ROOT/"phase5_v3b_fullsupport_global_prediction_freeze_manifest.json"
ROOT=HERE/"results"/"06_evaluation_v3b_fullsupport"

EXPECTED_CFG="FROZEN_PHASE5_V3B_FULLSUPPORT_EVALUATION_CONTRACT"
EXPECTED_AUDIT="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_MECHANICAL_AUDIT_PASS"
EXPECTED_WB="FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY"
EXPECTED_PRED="FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"
FROZEN_STATUS="FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION"
PRIMARY_METHODS=("M0","M1","M2","M3_FULL343")
M3_DIAGNOSTICS=("M3_TOP1","M3_TOP3","M3_TOP14")
PRIMARY_H_MIN=60.0
PRIMARY_H_MAX=240.0
N_WB=1000
TOL=1e-12

SCOPE_COLUMNS={
    "ALL":(),
    "provider_world":("provider_world_id",),
    "graph":("graph_id",),
    "regime":("regime",),
    "rho":("rho",),
    "provider_world_x_graph":("provider_world_id","graph_id"),
    "graph_x_regime":("graph_id","regime"),
    "provider_world_x_regime":("provider_world_id","regime"),
    "rho_x_regime":("rho","regime"),
}


def _preflight()->dict:
    cfg=read_json(CFG)
    audit=read_json(WB_AUDIT)
    wb=read_json(WB_FREEZE)
    pred=read_json(GLOBAL_PRED)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("evaluation adapter is not frozen")
    if audit.get("status")!=EXPECTED_AUDIT:
        raise RuntimeError("final-WB mechanical audit has not passed")
    if audit.get("checks",{}).get("prediction_curves_read") is not False:
        raise RuntimeError("WB audit provenance unexpectedly read prediction curves")
    if audit.get("checks",{}).get("method_performance_computed") is not False:
        raise RuntimeError("WB audit provenance unexpectedly computed method performance")
    if wb.get("status")!=EXPECTED_WB or wb.get("complete") is not True:
        raise RuntimeError("final-WB battery is not frozen")
    if pred.get("status")!=EXPECTED_PRED or pred.get("complete") is not True:
        raise RuntimeError("blind-prediction battery is not frozen")
    if sorted(cfg["primary_methods"])!=sorted(PRIMARY_METHODS):
        raise RuntimeError("primary method set changed")
    if cfg["M3"]["primary"]!="M3_FULL343":
        raise RuntimeError("primary M3 is not FULL343")
    return cfg


def _cells()->list[str]:
    wb=read_json(WB_FREEZE)
    cells=sorted(map(str,wb["eligible_final_wb_cells"]))
    if len(cells)!=12:
        raise RuntimeError("evaluation expects exactly 12 eligible cells")
    return cells


def _read_primary_prediction(cell:str,method:str)->pd.DataFrame:
    root=PRED_ROOT/cell
    if method=="M0":
        path=root/"m0_predictions.csv"
    elif method=="M1":
        path=root/"m1_predictions.csv"
    elif method=="M2":
        path=root/"m2_predictions.csv"
    elif method=="M3_FULL343":
        path=root/"m3_predictions_full343_and_nested.csv"
    else:
        raise KeyError(method)
    if not path.is_file():
        raise FileNotFoundError(path)
    p=pd.read_csv(path)
    if method=="M3_FULL343":
        p=p[p["method_id"].astype(str)=="M3_FULL343"].copy()
    return p


def _read_m3_diagnostics(cell:str)->pd.DataFrame:
    path=PRED_ROOT/cell/"m3_predictions_full343_and_nested.csv"
    p=pd.read_csv(path)
    return p[p["method_id"].astype(str).isin(M3_DIAGNOSTICS)].copy()


def _read_wb(cell:str)->pd.DataFrame:
    path=WB_ROOT/cell/"final_wb_curves.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _join_one(cell:str,method:str,p:pd.DataFrame,wb:pd.DataFrame)->pd.DataFrame:
    key=["query_id","provider_world_id","graph_id","rho_label","rho","regime","H"]
    required=set(key+["sigma_hat"])
    if method=="M0":
        required.add("status")
    missing=required.difference(p.columns)
    if missing:
        raise RuntimeError(f"{cell}/{method}: prediction missing {sorted(missing)}")
    wcols=key+["sigma_wb","wb_n","wb_successes","wb_ci_lower","wb_ci_upper"]
    missing_w=set(wcols).difference(wb.columns)
    if missing_w:
        raise RuntimeError(f"{cell}: WB missing {sorted(missing_w)}")
    if p.duplicated(key).any() or wb.duplicated(key).any():
        raise RuntimeError(f"{cell}/{method}: duplicate pointwise key")
    merged=p.merge(wb[wcols],on=key,how="inner",validate="one_to_one")
    if len(merged)!=len(p):
        raise RuntimeError(f"{cell}/{method}: prediction/WB join lost rows")
    merged.insert(0,"physical_cell_id",cell)
    if "method_id" not in merged.columns:
        merged["method_id"]=method
    merged["method_id"]=method
    if method!="M0":
        merged["status"]="PREDICTED"
    return merged


def _primary_window(df:pd.DataFrame)->pd.DataFrame:
    return df[
        (df["H"].astype(float)>=PRIMARY_H_MIN-TOL)
        & (df["H"].astype(float)<=PRIMARY_H_MAX+TOL)
    ].copy()


def _scope_value(row:pd.Series|tuple|object,cols:tuple[str,...])->str:
    if not cols:
        return "ALL"
    vals=[]
    if isinstance(row,pd.Series):
        getter=lambda c:row[c]
    elif hasattr(row,"_asdict"):
        d=row._asdict()
        getter=lambda c:d[c]
    else:
        raise TypeError(type(row))
    for c in cols:
        v=getter(c)
        vals.append(f"{c}={v}")
    return "|".join(vals)


def _iter_scope_groups(df:pd.DataFrame,scope:str):
    cols=SCOPE_COLUMNS[scope]
    if not cols:
        yield "ALL",df
        return
    grouper=cols[0] if len(cols)==1 else list(cols)
    for key,g in df.groupby(grouper,sort=True,dropna=False):
        if len(cols)==1:
            key=(key,)
        value="|".join(f"{c}={v}" for c,v in zip(cols,key))
        yield value,g


def _error_metrics(g:pd.DataFrame)->dict:
    scored=g[
        (g["status"].astype(str)=="PREDICTED")
        & g["sigma_hat"].notna()
    ].copy()
    n=int(len(scored))
    if n==0:
        return {
            "n_points":0,"MAE":np.nan,"RMSE":np.nan,"signed_bias":np.nan,
            "max_abs_error":np.nan,"reference_noise_adjusted_RMSE":np.nan,
        }
    pred=scored["sigma_hat"].astype(float).to_numpy()
    truth=scored["sigma_wb"].astype(float).to_numpy()
    err=pred-truth
    noise=truth*(1.0-truth)/(N_WB-1)
    adjusted=float(np.mean(err*err-noise))
    return {
        "n_points":n,
        "MAE":float(np.mean(np.abs(err))),
        "RMSE":float(np.sqrt(np.mean(err*err))),
        "signed_bias":float(np.mean(err)),
        "max_abs_error":float(np.max(np.abs(err))),
        "reference_noise_adjusted_RMSE":float(np.sqrt(max(0.0,adjusted))),
    }


def _metric_table(joined:pd.DataFrame,methods:Iterable[str])->pd.DataFrame:
    rows=[]
    for method in methods:
        m=joined[joined["method_id"].astype(str)==method].copy()
        for scope in SCOPE_COLUMNS:
            for value,g in _iter_scope_groups(m,scope):
                rows.append({
                    "method_id":method,
                    "scope":scope,
                    "scope_value":value,
                    **_error_metrics(g),
                })
    return pd.DataFrame(rows).sort_values(
        ["method_id","scope","scope_value"],kind="mergesort"
    ).reset_index(drop=True)


def _decision_table(joined:pd.DataFrame,betas:list[float])->pd.DataFrame:
    rows=[]
    for method in PRIMARY_METHODS:
        m=joined[
            (joined["method_id"].astype(str)==method)
            & (joined["status"].astype(str)=="PREDICTED")
            & joined["sigma_hat"].notna()
        ].copy()
        for beta in betas:
            certain_accept=m["wb_ci_lower"].astype(float)>=float(beta)-TOL
            certain_reject=m["wb_ci_upper"].astype(float)<float(beta)-TOL
            certain=certain_accept|certain_reject
            mm=m[certain].copy()
            mm["wb_decision_accept"]=certain_accept[certain].to_numpy()
            mm["prediction_accept"]=mm["sigma_hat"].astype(float)>=float(beta)-TOL
            for scope in SCOPE_COLUMNS:
                for value,g in _iter_scope_groups(mm,scope):
                    n=int(len(g))
                    wb_a=g["wb_decision_accept"].astype(bool)
                    pred_a=g["prediction_accept"].astype(bool)
                    fa=int((pred_a & ~wb_a).sum())
                    fr=int((~pred_a & wb_a).sum())
                    n_reject=int((~wb_a).sum())
                    n_accept=int(wb_a.sum())
                    rows.append({
                        "method_id":method,
                        "beta":float(beta),
                        "scope":scope,
                        "scope_value":value,
                        "wb_certain_point_count":n,
                        "wb_certain_accept_count":n_accept,
                        "wb_certain_reject_count":n_reject,
                        "false_accept_count":fa,
                        "false_reject_count":fr,
                        "decision_agreement_rate":float((pred_a==wb_a).mean()) if n else np.nan,
                        "false_accept_rate":float(fa/n_reject) if n_reject else np.nan,
                        "false_reject_rate":float(fr/n_accept) if n_accept else np.nan,
                    })
    return pd.DataFrame(rows).sort_values(
        ["method_id","beta","scope","scope_value"],kind="mergesort"
    ).reset_index(drop=True)


def _m0_applicability(joined:pd.DataFrame)->pd.DataFrame:
    m=joined[joined["method_id"].astype(str)=="M0"].copy()
    q=(
        m[["physical_cell_id","query_id","provider_world_id","graph_id","rho","regime","status"]]
        .drop_duplicates()
    )
    rows=[]
    for scope in SCOPE_COLUMNS:
        for value,g in _iter_scope_groups(q,scope):
            pred=g["status"].astype(str)=="PREDICTED"
            rows.append({
                "scope":scope,
                "scope_value":value,
                "query_count":int(len(g)),
                "applicable_query_count":int(pred.sum()),
                "not_applicable_query_count":int((~pred).sum()),
                "query_applicability_fraction":float(pred.mean()) if len(g) else np.nan,
            })
    return pd.DataFrame(rows).sort_values(["scope","scope_value"],kind="mergesort")


def _m2_diagnostics(joined:pd.DataFrame)->pd.DataFrame:
    m=joined[
        (joined["method_id"].astype(str)=="M2")
        & (joined["status"].astype(str)=="PREDICTED")
    ].copy()
    if not {"sigma_min","sigma_max"}.issubset(m.columns):
        raise RuntimeError("M2 joined table lacks finite-portfolio min/max")
    m["range_width"]=m["sigma_max"].astype(float)-m["sigma_min"].astype(float)
    wb=m["sigma_wb"].astype(float)
    lo=m["sigma_min"].astype(float)
    hi=m["sigma_max"].astype(float)
    m["wb_inside_range"]=(wb>=lo-TOL)&(wb<=hi+TOL)
    m["distance_outside_range"]=np.maximum.reduce([
        (lo-wb).to_numpy(),
        (wb-hi).to_numpy(),
        np.zeros(len(m)),
    ])
    rows=[]
    for scope in SCOPE_COLUMNS:
        for value,g in _iter_scope_groups(m,scope):
            rows.append({
                "scope":scope,
                "scope_value":value,
                "n_points":int(len(g)),
                "mean_range_width":float(g["range_width"].mean()),
                "WB_coverage_fraction":float(g["wb_inside_range"].mean()),
                "mean_distance_outside_range":float(g["distance_outside_range"].mean()),
                "max_distance_outside_range":float(g["distance_outside_range"].max()),
            })
    return pd.DataFrame(rows).sort_values(["scope","scope_value"],kind="mergesort")


def _m3_precision(joined:pd.DataFrame)->pd.DataFrame:
    m=joined[joined["method_id"].astype(str)=="M3_FULL343"].copy()
    required={"mc_se_plugin","mc_se_bound","graph_budget","truncation_bound","retained_mass"}
    if not required.issubset(m.columns):
        raise RuntimeError("M3 FULL343 precision columns missing")
    if not np.allclose(m["retained_mass"].astype(float),1.0,atol=1e-10,rtol=0.0):
        raise RuntimeError("M3 FULL343 retained mass !=1 in evaluation")
    if not np.allclose(m["truncation_bound"].astype(float),0.0,atol=1e-10,rtol=0.0):
        raise RuntimeError("M3 FULL343 truncation bound !=0 in evaluation")
    rows=[]
    for scope in SCOPE_COLUMNS:
        for value,g in _iter_scope_groups(m,scope):
            rows.append({
                "scope":scope,
                "scope_value":value,
                "n_points":int(len(g)),
                "mean_plugin_MC_SE":float(g["mc_se_plugin"].mean()),
                "max_plugin_MC_SE":float(g["mc_se_plugin"].max()),
                "mean_conservative_MC_SE_bound":float(g["mc_se_bound"].mean()),
                "max_conservative_MC_SE_bound":float(g["mc_se_bound"].max()),
                "mean_graph_budget":float(g["graph_budget"].mean()),
                "fullsupport_truncation_bound":0.0,
            })
    return pd.DataFrame(rows).sort_values(["scope","scope_value"],kind="mergesort")


def _topology_contrasts(primary_metrics:pd.DataFrame)->pd.DataFrame:
    base=primary_metrics[
        (primary_metrics["scope"]=="provider_world_x_graph")
        & primary_metrics["MAE"].notna()
    ].copy()
    rows=[]
    for method in PRIMARY_METHODS:
        mm=base[base["method_id"].astype(str)==method]
        for world in ("P1","P3","P4"):
            par=mm[mm["scope_value"]==f"provider_world_id={world}|graph_id=G_PAR"]
            seq=mm[mm["scope_value"]==f"provider_world_id={world}|graph_id=G_SEQ"]
            if len(par)!=1 or len(seq)!=1:
                rows.append({
                    "method_id":method,"contrast":"Delta_P",
                    "provider_world_id":world,"status":"NOT_ESTIMABLE",
                    "MAE_G_PAR":np.nan,"MAE_G_SEQ":np.nan,"Delta_SEQ_minus_PAR":np.nan,
                })
                continue
            rows.append({
                "method_id":method,"contrast":"Delta_P",
                "provider_world_id":world,"status":"ESTIMABLE",
                "MAE_G_PAR":float(par.iloc[0]["MAE"]),
                "MAE_G_SEQ":float(seq.iloc[0]["MAE"]),
                "Delta_SEQ_minus_PAR":float(seq.iloc[0]["MAE"]-par.iloc[0]["MAE"]),
            })
        rows.append({
            "method_id":method,
            "contrast":"Delta_het",
            "provider_world_id":"P2+P4_vs_P1+P3",
            "status":"NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE",
            "MAE_G_PAR":np.nan,
            "MAE_G_SEQ":np.nan,
            "Delta_SEQ_minus_PAR":np.nan,
        })
    return pd.DataFrame(rows)


def _input_hashes(cells:list[str])->pd.DataFrame:
    rows=[]
    for cell in cells:
        files={
            "m0":PRED_ROOT/cell/"m0_predictions.csv",
            "m1":PRED_ROOT/cell/"m1_predictions.csv",
            "m2":PRED_ROOT/cell/"m2_predictions.csv",
            "m3":PRED_ROOT/cell/"m3_predictions_full343_and_nested.csv",
            "wb":WB_ROOT/cell/"final_wb_curves.csv",
        }
        for kind,path in files.items():
            rows.append({
                "physical_cell_id":cell,
                "input_kind":kind,
                "path":str(path),
                "sha256":sha256_file(path),
            })
    return pd.DataFrame(rows)


def run()->Path:
    cfg=_preflight()
    cells=_cells()
    ROOT.mkdir(parents=True,exist_ok=True)

    joined_frames=[]
    diag_frames=[]
    for cell in cells:
        wb=_read_wb(cell)
        for method in PRIMARY_METHODS:
            joined_frames.append(
                _join_one(cell,method,_read_primary_prediction(cell,method),wb)
            )
        diag=_read_m3_diagnostics(cell)
        for method in M3_DIAGNOSTICS:
            part=diag[diag["method_id"].astype(str)==method].copy()
            diag_frames.append(_join_one(cell,method,part,wb))

    joined=pd.concat(joined_frames,ignore_index=True,sort=False)
    diagnostics=pd.concat(diag_frames,ignore_index=True,sort=False)
    joined_primary=_primary_window(joined)
    diagnostics_primary=_primary_window(diagnostics)

    expected_primary_points_per_method=12*15*37
    for method in ("M1","M2","M3_FULL343"):
        n=len(joined_primary[joined_primary["method_id"].astype(str)==method])
        if n!=expected_primary_points_per_method:
            raise RuntimeError(f"{method}: primary-window point count {n} != {expected_primary_points_per_method}")
    for method in M3_DIAGNOSTICS:
        n=len(diagnostics_primary[diagnostics_primary["method_id"].astype(str)==method])
        if n!=expected_primary_points_per_method:
            raise RuntimeError(f"{method}: diagnostic primary-window point count mismatch")

    primary_metrics=_metric_table(joined_primary,PRIMARY_METHODS)
    diagnostic_metrics=_metric_table(diagnostics_primary,M3_DIAGNOSTICS)
    decisions=_decision_table(joined_primary,[float(x) for x in cfg["decision_analysis"]["betas"]])
    m0=_m0_applicability(joined_primary)
    m2=_m2_diagnostics(joined_primary)
    m3=_m3_precision(joined_primary)
    topology=_topology_contrasts(primary_metrics)
    hashes=_input_hashes(cells)

    outputs={
        "pointwise_primary":ROOT/"pointwise_primary_joined.csv",
        "primary_metrics":ROOT/"primary_metrics.csv",
        "m3_nested_diagnostic_metrics":ROOT/"m3_nested_diagnostic_metrics.csv",
        "decision_metrics":ROOT/"decision_metrics.csv",
        "m0_applicability":ROOT/"m0_applicability.csv",
        "m2_portfolio_diagnostics":ROOT/"m2_portfolio_diagnostics.csv",
        "m3_precision_summary":ROOT/"m3_precision_summary.csv",
        "topology_contrasts":ROOT/"topology_contrasts.csv",
        "input_hashes":ROOT/"evaluation_input_hashes.csv",
    }
    joined_primary.to_csv(outputs["pointwise_primary"],index=False)
    primary_metrics.to_csv(outputs["primary_metrics"],index=False)
    diagnostic_metrics.to_csv(outputs["m3_nested_diagnostic_metrics"],index=False)
    decisions.to_csv(outputs["decision_metrics"],index=False)
    m0.to_csv(outputs["m0_applicability"],index=False)
    m2.to_csv(outputs["m2_portfolio_diagnostics"],index=False)
    m3.to_csv(outputs["m3_precision_summary"],index=False)
    topology.to_csv(outputs["topology_contrasts"],index=False)
    hashes.to_csv(outputs["input_hashes"],index=False)

    all_primary=primary_metrics[
        (primary_metrics["scope"]=="ALL")
        & (primary_metrics["scope_value"]=="ALL")
    ].sort_values("method_id",kind="mergesort")
    all_diag=diagnostic_metrics[
        (diagnostic_metrics["scope"]=="ALL")
        & (diagnostic_metrics["scope_value"]=="ALL")
    ].sort_values("method_id",kind="mergesort")
    beta09=decisions[
        (np.isclose(decisions["beta"].astype(float),0.9,atol=1e-12,rtol=0.0))
        & (decisions["scope"]=="ALL")
    ].sort_values("method_id",kind="mergesort")

    manifest={
        "status":FROZEN_STATUS,
        "stage_id":"DETERMINISTIC_EVALUATION_V3B_FULLSUPPORT",
        "scientific_evidence":True,
        "evaluation_contract_sha256":sha256_file(CFG),
        "final_wb_audit_sha256":sha256_file(WB_AUDIT),
        "final_wb_freeze_sha256":sha256_file(WB_FREEZE),
        "global_prediction_freeze_sha256":sha256_file(GLOBAL_PRED),
        "code_commit":git_head(),
        "primary_methods":list(PRIMARY_METHODS),
        "secondary_m3_diagnostics":list(M3_DIAGNOSTICS),
        "primary_window":"H60..H240",
        "eligible_cells":12,
        "gate_failed_cells":4,
        "registered_Delta_het_status":"NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE",
        "bootstrap_reference_uncertainty_status":"PENDING_SEPARATE_FROZEN_STAGE",
        "outputs":{k:str(v) for k,v in outputs.items()},
        "output_hashes_sha256":{k:sha256_file(v) for k,v in outputs.items()},
        "completed_utc":utc_now_iso(),
    }
    manifest_path=ROOT/"phase5_v3b_fullsupport_deterministic_evaluation_manifest.json"
    write_json(manifest_path,manifest)

    print("PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION_PASS")
    print("\nPRIMARY ALL")
    print(all_primary[[
        "method_id","n_points","MAE","RMSE","signed_bias",
        "max_abs_error","reference_noise_adjusted_RMSE"
    ]].to_string(index=False))
    print("\nM3 NESTED DIAGNOSTICS ALL")
    print(all_diag[[
        "method_id","n_points","MAE","RMSE","signed_bias","max_abs_error"
    ]].to_string(index=False))
    print("\nDECISIONS beta=0.9 ALL")
    print(beta09[[
        "method_id","wb_certain_point_count","false_accept_count",
        "false_reject_count","decision_agreement_rate"
    ]].to_string(index=False))
    print("\nTOPOLOGY CONTRASTS")
    print(topology.to_string(index=False))
    print("\nbootstrap_reference_uncertainty_status PENDING_SEPARATE_FROZEN_STAGE")
    print("manifest",manifest_path)
    return manifest_path


if __name__=="__main__":
    run()
