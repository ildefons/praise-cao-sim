"""Generate Phase-5 Figure-1-like sigma approximation sheets.

Four figures are generated, one per frozen topology. Each figure is a 3x3
world-by-regime grid. A panel uses one representative frozen query selected
without outcome information: sort the five frozen queries in that
(world, graph, regime) by rho and query_id, then take the median item
(lower median if an even count is ever encountered).

Curves:
    WB, M0, M1, M2, M3_FULL343

The script reads only frozen Step-0 metadata and the already frozen deterministic
pointwise evaluation table. It performs no simulation and recomputes no
prediction.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from phase5_runtime_v2 import git_head, read_json, sha256_file, utc_now_iso, write_json

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_sigma_plots_v3b_fullsupport.json"
STEP0_ROOT=HERE/"results"/"02_step0"
EVAL_ROOT=HERE/"results"/"06_evaluation_v3b_fullsupport"
EVAL_MANIFEST=EVAL_ROOT/"phase5_v3b_fullsupport_deterministic_evaluation_manifest.json"
POINTWISE=EVAL_ROOT/"pointwise_primary_joined.csv"
ROOT=EVAL_ROOT/"sigma_plots"

EXPECTED_CFG="FROZEN_PHASE5_V3B_FULLSUPPORT_SIGMA_PLOT_CONTRACT"
EXPECTED_EVAL="FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION"
WORLDS=("P1","P3","P4")
GRAPHS=("G_PAR","G_SEQ","G_SEQPAR","G_PARSEQ")
REGIMES=("Easy","Mid","Stress")
METHODS=("WB","M0","M1","M2","M3_FULL343")
PRED_METHODS=("M0","M1","M2","M3_FULL343")
H_MIN=60.0
H_MAX=240.0
TOL=1e-12


def _preflight()->dict:
    cfg=read_json(CFG)
    if cfg.get("status")!=EXPECTED_CFG:
        raise RuntimeError("sigma-plot contract is not frozen")
    ev=read_json(EVAL_MANIFEST)
    if ev.get("status")!=EXPECTED_EVAL:
        raise RuntimeError("deterministic evaluation is not frozen")
    if tuple(cfg["provider_worlds"])!=WORLDS:
        raise RuntimeError("sigma-plot provider-world set changed")
    if tuple(cfg["graph_ids"])!=GRAPHS:
        raise RuntimeError("sigma-plot graph set changed")
    if tuple(cfg["regimes"])!=REGIMES:
        raise RuntimeError("sigma-plot regime set changed")
    if tuple(cfg["methods"])!=METHODS:
        raise RuntimeError("sigma-plot method set changed")
    if not POINTWISE.is_file():
        raise FileNotFoundError(POINTWISE)
    recorded=ev.get("output_hashes_sha256",{}).get("pointwise_primary")
    if recorded and sha256_file(POINTWISE)!=str(recorded):
        raise RuntimeError("frozen pointwise evaluation table hash changed")
    return cfg


def load_query_metadata()->pd.DataFrame:
    """Load only frozen Step-0 query definitions for the 12 eligible cells."""
    eligibility=pd.read_csv(STEP0_ROOT/"phase5_step0_eligibility.csv")
    eligible=eligibility[
        eligibility["eligibility"].astype(str)=="ELIGIBLE"
    ].copy()
    eligible=eligible[
        eligible["provider_world_id"].astype(str).isin(WORLDS)
        & eligible["graph_id"].astype(str).isin(GRAPHS)
    ].copy()
    if len(eligible)!=12:
        raise RuntimeError(f"expected 12 eligible plotting cells, found {len(eligible)}")

    frames=[]
    cols=[
        "query_id","provider_world_id","graph_id","rho_label","rho","regime",
        "scale","A_G_l_max","A_G_c_max","A_G_q_min","step0_cell_status",
    ]
    for rec in eligible.sort_values(
        ["provider_world_id","graph_id"],kind="mergesort"
    ).itertuples(index=False):
        cell=str(rec.physical_cell_id)
        path=STEP0_ROOT/cell/"step0_frozen_queries.csv"
        q=pd.read_csv(path,usecols=cols)
        if len(q)!=15 or q["query_id"].astype(str).nunique()!=15:
            raise RuntimeError(f"{cell}: expected 15 unique frozen Step-0 queries")
        if set(q["step0_cell_status"].astype(str))!={"FROZEN_PHASE5_STEP0_PASS_V2"}:
            raise RuntimeError(f"{cell}: plotting query source is not frozen Step-0 PASS")
        q.insert(0,"physical_cell_id",cell)
        frames.append(q)

    out=pd.concat(frames,ignore_index=True)
    if len(out)!=180:
        raise RuntimeError(f"expected 180 eligible frozen queries, found {len(out)}")
    return out


def select_representative_queries(queries:pd.DataFrame)->pd.DataFrame:
    """Select median-rho query in every world x graph x regime panel.

    Stable deterministic rule:
      1. sort by rho ascending, then query_id ascending;
      2. choose index (n-1)//2, which is the lower median for even n.
    """
    required={
        "physical_cell_id","query_id","provider_world_id","graph_id",
        "rho_label","rho","regime",
    }
    missing=required.difference(queries.columns)
    if missing:
        raise ValueError(f"query table missing {sorted(missing)}")

    rows=[]
    for (world,graph,regime),g in queries.groupby(
        ["provider_world_id","graph_id","regime"],sort=True
    ):
        ordered=g.sort_values(["rho","query_id"],kind="mergesort").reset_index(drop=True)
        if len(ordered)!=5:
            raise RuntimeError(
                f"{world}/{graph}/{regime}: expected 5 frozen rho queries, found {len(ordered)}"
            )
        choice=ordered.iloc[(len(ordered)-1)//2].copy()
        rows.append(choice)

    selected=pd.DataFrame(rows).reset_index(drop=True)
    if len(selected)!=36:
        raise RuntimeError(f"expected 36 representative panel queries, found {len(selected)}")
    if selected["query_id"].astype(str).nunique()!=36:
        raise RuntimeError("representative query IDs are not unique")
    expected={
        (w,g,r) for w in WORLDS for g in GRAPHS for r in REGIMES
    }
    actual=set(zip(
        selected["provider_world_id"].astype(str),
        selected["graph_id"].astype(str),
        selected["regime"].astype(str),
    ))
    if actual!=expected:
        raise RuntimeError("representative-query panel coverage is not complete")
    return selected.sort_values(
        ["graph_id","provider_world_id","regime"],kind="mergesort"
    ).reset_index(drop=True)


def load_plot_data(selected:pd.DataFrame)->pd.DataFrame:
    """Extract selected curves from frozen deterministic pointwise evaluation."""
    p=pd.read_csv(POINTWISE)
    required={
        "physical_cell_id","query_id","provider_world_id","graph_id","rho_label",
        "rho","regime","H","method_id","status","sigma_hat","sigma_wb",
        "wb_ci_lower","wb_ci_upper",
    }
    missing=required.difference(p.columns)
    if missing:
        raise RuntimeError(f"pointwise evaluation table missing {sorted(missing)}")
    p=p[
        (p["H"].astype(float)>=H_MIN-TOL)
        & (p["H"].astype(float)<=H_MAX+TOL)
    ].copy()

    chosen=set(selected["query_id"].astype(str))
    p=p[p["query_id"].astype(str).isin(chosen)].copy()
    if set(p["method_id"].astype(str).unique())!=set(PRED_METHODS):
        raise RuntimeError("selected pointwise table does not contain exactly M0/M1/M2/M3_FULL343")

    # Freeze one WB row per query/H from the repeated method-level join.
    wb_cols=[
        "physical_cell_id","query_id","provider_world_id","graph_id","rho_label",
        "rho","regime","H","sigma_wb","wb_ci_lower","wb_ci_upper",
    ]
    wb=p[wb_cols].drop_duplicates().copy()
    if wb.duplicated(["physical_cell_id","query_id","H"]).any():
        raise RuntimeError("WB plotting rows are not unique by cell/query/H")
    wb["method_id"]="WB"
    wb["status"]="REFERENCE"
    wb["sigma"]=wb["sigma_wb"].astype(float)

    pred=p[[
        "physical_cell_id","query_id","provider_world_id","graph_id","rho_label",
        "rho","regime","H","method_id","status","sigma_hat",
    ]].copy()
    pred["sigma"]=pd.to_numeric(pred["sigma_hat"],errors="coerce")
    pred["wb_ci_lower"]=np.nan
    pred["wb_ci_upper"]=np.nan

    cols=[
        "physical_cell_id","query_id","provider_world_id","graph_id","rho_label",
        "rho","regime","H","method_id","status","sigma","wb_ci_lower","wb_ci_upper",
    ]
    out=pd.concat([wb[cols],pred[cols]],ignore_index=True)
    out=out.sort_values(
        ["graph_id","provider_world_id","regime","query_id","method_id","H"],
        kind="mergesort",
    ).reset_index(drop=True)

    # Every WB/M1/M2/M3 selected query has all 37 primary horizons.
    for qid,g in out.groupby("query_id",sort=False):
        for method in ("WB","M1","M2","M3_FULL343"):
            mm=g[g["method_id"].astype(str)==method]
            if len(mm)!=37:
                raise RuntimeError(f"{qid}/{method}: expected 37 primary-horizon rows")
        m0=g[g["method_id"].astype(str)=="M0"]
        if len(m0)!=37:
            raise RuntimeError(f"{qid}/M0: expected 37 status rows")
        states=set(m0["status"].astype(str))
        if states not in ({"PREDICTED"},{"NOT_APPLICABLE"}):
            raise RuntimeError(f"{qid}/M0: mixed or unexpected applicability status {states}")
    return out


def _line_spec(method:str)->dict:
    # Fixed visual semantics shared across all four topology sheets.
    return {
        "WB":{"label":"WB","linewidth":2.6,"linestyle":"-","color":"black","zorder":6},
        "M0":{"label":"M0","linewidth":1.5,"linestyle":"--","color":"0.45","zorder":2},
        "M1":{"label":"M1","linewidth":1.7,"linestyle":":","color":"tab:orange","zorder":3},
        "M2":{"label":"M2","linewidth":1.8,"linestyle":"-.","color":"tab:blue","zorder":4},
        "M3_FULL343":{"label":"M3 FULL343","linewidth":2.1,"linestyle":"-","color":"tab:green","zorder":5},
    }[method]


def make_sigma_figure(
    graph_id:str,
    plot_data:pd.DataFrame,
    selected:pd.DataFrame,
    outdir:Path,
    *,
    png_dpi:int=220,
)->list[Path]:
    if graph_id not in GRAPHS:
        raise ValueError(graph_id)
    outdir.mkdir(parents=True,exist_ok=True)

    fig,axes=plt.subplots(
        nrows=3,ncols=3,figsize=(12.6,9.0),
        sharex=True,sharey=True,
    )
    legend_handles={}
    for i,world in enumerate(WORLDS):
        for j,regime in enumerate(REGIMES):
            ax=axes[i,j]
            sel=selected[
                (selected["provider_world_id"].astype(str)==world)
                & (selected["graph_id"].astype(str)==graph_id)
                & (selected["regime"].astype(str)==regime)
            ]
            if len(sel)!=1:
                raise RuntimeError(f"{graph_id}/{world}/{regime}: representative query count !=1")
            qid=str(sel.iloc[0]["query_id"])
            rho=float(sel.iloc[0]["rho"])
            panel=plot_data[
                (plot_data["query_id"].astype(str)==qid)
                & (plot_data["graph_id"].astype(str)==graph_id)
            ].copy()
            if panel.empty:
                raise RuntimeError(f"{graph_id}/{world}/{regime}: no plot data")

            wb=panel[panel["method_id"].astype(str)=="WB"].sort_values("H")
            ax.fill_between(
                wb["H"].astype(float).to_numpy(),
                wb["wb_ci_lower"].astype(float).to_numpy(),
                wb["wb_ci_upper"].astype(float).to_numpy(),
                color="0.75",alpha=0.28,linewidth=0.0,zorder=1,
            )
            for method in METHODS:
                mm=panel[panel["method_id"].astype(str)==method].sort_values("H")
                if method=="M0" and set(mm["status"].astype(str))=={"NOT_APPLICABLE"}:
                    ax.text(
                        0.97,0.05,"M0 N/A",
                        transform=ax.transAxes,ha="right",va="bottom",
                        fontsize=8,color="0.40",
                    )
                    continue
                mm=mm[mm["sigma"].notna()]
                if mm.empty:
                    continue
                spec=_line_spec(method)
                line,=ax.plot(
                    mm["H"].astype(float),
                    mm["sigma"].astype(float),
                    **{k:v for k,v in spec.items() if k!="label"},
                    label=spec["label"],
                )
                legend_handles.setdefault(method,line)

            ax.set_xlim(H_MIN,H_MAX)
            ax.set_ylim(0.0,1.02)
            ax.set_xticks([60,120,180,240])
            ax.set_yticks(np.linspace(0.0,1.0,6))
            ax.grid(True,alpha=0.18,linewidth=0.7)
            ax.set_title(f"{world} | {regime} | rho={rho:.4g}",fontsize=10)

    for ax in axes[-1,:]:
        ax.set_xlabel("Horizon H (s)")
    for ax in axes[:,0]:
        ax.set_ylabel(r"$\sigma_G(H)$")

    order=[m for m in METHODS if m in legend_handles]
    fig.legend(
        [legend_handles[m] for m in order],
        [_line_spec(m)["label"] for m in order],
        loc="upper center",ncol=len(order),frameon=False,
        bbox_to_anchor=(0.5,0.985),
    )
    fig.suptitle(f"Sigma approximation | {graph_id}",fontsize=14,y=1.015)
    fig.tight_layout(rect=(0.02,0.02,1.0,0.945))

    outputs=[]
    png=outdir/f"phase5_sigma_{graph_id}.png"
    pdf=outdir/f"phase5_sigma_{graph_id}.pdf"
    fig.savefig(png,dpi=int(png_dpi),bbox_inches="tight")
    fig.savefig(pdf,bbox_inches="tight")
    plt.close(fig)
    outputs.extend([png,pdf])
    return outputs


def run()->Path:
    cfg=_preflight()
    ROOT.mkdir(parents=True,exist_ok=True)

    queries=load_query_metadata()
    selected=select_representative_queries(queries)
    selected_path=ROOT/"selected_representative_queries.csv"
    selected.to_csv(selected_path,index=False)

    data=load_plot_data(selected)
    data_path=ROOT/"sigma_plot_data_long.csv"
    data.to_csv(data_path,index=False)

    figure_paths=[]
    for graph_id in GRAPHS:
        figure_paths.extend(
            make_sigma_figure(
                graph_id,data,selected,ROOT,
                png_dpi=int(cfg["plot"]["png_dpi"]),
            )
        )

    if len(figure_paths)!=8:
        raise RuntimeError("expected exactly 4 PNG + 4 PDF figure files")
    for path in figure_paths:
        if not path.is_file() or path.stat().st_size==0:
            raise RuntimeError(f"missing/empty figure output {path}")

    outputs={
        "representative_queries":str(selected_path),
        "plot_data":str(data_path),
    }
    for path in figure_paths:
        outputs[path.name]=str(path)

    manifest={
        "status":"FROZEN_PHASE5_V3B_FULLSUPPORT_SIGMA_PLOTS_COMPLETE",
        "stage_id":"SIGMA_PLOTS_V3B_FULLSUPPORT",
        "scientific_evidence":False,
        "visualization_only":True,
        "code_commit":git_head(),
        "plot_contract_sha256":sha256_file(CFG),
        "deterministic_evaluation_manifest_sha256":sha256_file(EVAL_MANIFEST),
        "pointwise_primary_sha256":sha256_file(POINTWISE),
        "representative_query_rule":"median_rho_stable_lower_median_if_even",
        "representative_query_count":int(len(selected)),
        "figure_count":4,
        "panels_total":36,
        "methods":list(METHODS),
        "simulation_run":False,
        "prediction_recomputed":False,
        "outputs":outputs,
        "output_hashes_sha256":{
            name:sha256_file(Path(path)) for name,path in outputs.items()
        },
        "completed_utc":utc_now_iso(),
    }
    manifest_path=ROOT/"phase5_sigma_plots_manifest.json"
    write_json(manifest_path,manifest)

    print("PHASE5_V3B_FULLSUPPORT_SIGMA_PLOTS_PASS")
    print("figures_generated 4")
    print("panels_total 36")
    print("representative_queries 36")
    print("methods WB M0 M1 M2 M3_FULL343")
    print("output",ROOT)
    print("manifest",manifest_path)
    return manifest_path


def main()->None:
    p=argparse.ArgumentParser(description="Generate frozen Phase-5 sigma approximation figures")
    p.parse_args()
    run()


if __name__=="__main__":
    main()
