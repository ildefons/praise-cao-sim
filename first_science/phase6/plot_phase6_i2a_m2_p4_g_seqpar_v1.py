"""Plot WB vs frozen I1-M2 vs Phase-6 I2a-M2 for P4 / G_SEQPAR."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE=Path(__file__).resolve().parent
PHASE5=HERE.parent/"phase5"
if str(PHASE5) not in sys.path:
    sys.path.insert(0,str(PHASE5))

from phase5_runtime_v2 import read_json, sha256_file, utc_now_iso, write_json  # noqa:E402

CELL="P4__G_SEQPAR"
WORLD="P4"
GRAPH="G_SEQPAR"
REGIMES=("Easy","Mid","Stress")
P5_POINTWISE=PHASE5/"results"/"06_evaluation_v3b_fullsupport"/"pointwise_primary_joined.csv"
P5_QUERIES=PHASE5/"results"/"02_step0"/CELL/"step0_frozen_queries.csv"
I2A_PRED=HERE/"results"/"02_i2a_m2_p4_g_seqpar"/"i2a_m2_predictions.csv"
PRED_MANIFEST=HERE/"results"/"02_i2a_m2_p4_g_seqpar"/"i2a_m2_prediction_manifest.json"
ROOT=HERE/"results"/"03_i2a_m2_p4_g_seqpar_plot"


def _selected_queries():
    q=pd.read_csv(P5_QUERIES)
    rows=[]
    for regime in REGIMES:
        g=q[q["regime"].astype(str)==regime].sort_values(["rho","query_id"],kind="mergesort").reset_index(drop=True)
        if len(g)!=5:
            raise RuntimeError(f"{regime}: expected five frozen rho queries")
        rows.append(g.iloc[2])
    return pd.DataFrame(rows)


def run():
    if not I2A_PRED.is_file():
        raise FileNotFoundError("run the Phase-6 I2a-M2 graph prediction first")
    manifest=read_json(PRED_MANIFEST)
    if manifest.get("status")!="PHASE6_I2A_M2_P4_G_SEQPAR_PREDICTION_COMPLETE":
        raise RuntimeError("I2a-M2 graph prediction is not frozen complete")

    selected=_selected_queries()
    p=pd.read_csv(P5_POINTWISE)
    p=p[
        (p["physical_cell_id"].astype(str)==CELL)
        & (p["method_id"].astype(str)=="M2")
        & (p["H"].astype(float)>=60.0)
        & (p["H"].astype(float)<=240.0)
    ].copy()
    i2=pd.read_csv(I2A_PRED)
    i2=i2[(i2["H"].astype(float)>=60.0)&(i2["H"].astype(float)<=240.0)].copy()

    ROOT.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(12.6,3.8),sharex=True,sharey=True)
    long_rows=[]
    for ax,regime in zip(axes,REGIMES):
        row=selected[selected["regime"].astype(str)==regime].iloc[0]
        qid=str(row["query_id"])
        rho=float(row["rho"])
        old=p[p["query_id"].astype(str)==qid].sort_values("H")
        new=i2[i2["query_id"].astype(str)==qid].sort_values("H")
        if len(old)!=37 or len(new)!=37:
            raise RuntimeError(f"{regime}: expected 37 primary-horizon rows per method")

        wb=old[["H","sigma_wb","wb_ci_lower","wb_ci_upper"]].drop_duplicates().sort_values("H")
        if len(wb)!=37:
            raise RuntimeError(f"{regime}: WB row count mismatch")

        ax.fill_between(
            wb["H"].astype(float).to_numpy(),
            wb["wb_ci_lower"].astype(float).to_numpy(),
            wb["wb_ci_upper"].astype(float).to_numpy(),
            alpha=0.20,
        )
        ax.plot(wb["H"],wb["sigma_wb"],label="WB",linewidth=2.4)
        ax.plot(old["H"],old["sigma_hat"],label="I1-M2",linewidth=2.0,linestyle="--")
        ax.plot(new["H"],new["sigma_hat"],label="I2a-M2",linewidth=2.0,linestyle="-.")
        ax.set_title(f"{regime} | rho={rho:.4g}")
        ax.set_xlim(60,240)
        ax.set_ylim(0,1.02)
        ax.set_xticks([60,120,180,240])
        ax.grid(True,alpha=0.18)
        ax.set_xlabel("Horizon H (s)")

        for rec in wb.itertuples(index=False):
            long_rows.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rec.H),"method":"WB","sigma":float(rec.sigma_wb)})
        for rec in old.itertuples(index=False):
            long_rows.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rec.H),"method":"I1-M2","sigma":float(rec.sigma_hat)})
        for rec in new.itertuples(index=False):
            long_rows.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rec.H),"method":"I2a-M2","sigma":float(rec.sigma_hat)})

    axes[0].set_ylabel(r"$\sigma_G(H)$")
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="upper center",ncol=3,frameon=False,bbox_to_anchor=(0.5,1.02))
    fig.suptitle("P4 / G_SEQPAR: WB vs I1-M2 vs I2a-M2",y=1.10)
    fig.tight_layout()

    png=ROOT/"phase6_P4_G_SEQPAR_WB_I1M2_I2aM2.png"
    pdf=ROOT/"phase6_P4_G_SEQPAR_WB_I1M2_I2aM2.pdf"
    fig.savefig(png,dpi=220,bbox_inches="tight")
    fig.savefig(pdf,bbox_inches="tight")
    plt.close(fig)

    selected_path=ROOT/"selected_queries.csv"
    data_path=ROOT/"plot_data_long.csv"
    selected.to_csv(selected_path,index=False)
    pd.DataFrame(long_rows).to_csv(data_path,index=False)

    out_manifest=ROOT/"plot_manifest.json"
    write_json(out_manifest,{
        "status":"PHASE6_I2A_M2_P4_G_SEQPAR_PLOT_COMPLETE",
        "visualization_only":True,
        "representative_query_rule":"median rho per regime, same as Phase-5 sigma figures",
        "methods":["WB","I1-M2","I2a-M2"],
        "outputs":{
            "png":str(png),"pdf":str(pdf),
            "selected_queries":str(selected_path),"plot_data":str(data_path)
        },
        "output_hashes_sha256":{
            "png":sha256_file(png),"pdf":sha256_file(pdf),
            "selected_queries":sha256_file(selected_path),"plot_data":sha256_file(data_path)
        },
        "completed_utc":utc_now_iso()
    })
    print("PHASE6_I2A_M2_P4_G_SEQPAR_PLOT_PASS")
    print("png",png)
    print("pdf",pdf)


if __name__=="__main__":
    run()
