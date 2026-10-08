"""Compare WB, frozen I1-M2, and genuine reconstructed I2a-M2."""
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

CELL="P4__G_SEQPAR"; REGIMES=("Easy","Mid","Stress")
P5_POINTWISE=PHASE5/"results"/"06_evaluation_v3b_fullsupport"/"pointwise_primary_joined.csv"
P5_QUERIES=PHASE5/"results"/"02_step0"/CELL/"step0_frozen_queries.csv"
NEW_ROOT=HERE/"results"/"05_i2a_genuine_m2_p4_g_seqpar"
NEW_PRED=NEW_ROOT/"genuine_i2a_m2_predictions.csv"
NEW_MANIFEST=NEW_ROOT/"prediction_manifest.json"
ROOT=HERE/"results"/"06_i2a_genuine_m2_p4_g_seqpar_plot"


def _selected():
    q=pd.read_csv(P5_QUERIES)
    rows=[]
    for regime in REGIMES:
        g=q[q["regime"].astype(str)==regime].sort_values(["rho","query_id"],kind="mergesort").reset_index(drop=True)
        if len(g)!=5:
            raise RuntimeError(f"{regime}: expected five queries")
        rows.append(g.iloc[2])
    return pd.DataFrame(rows)


def run():
    if not NEW_PRED.is_file():
        raise FileNotFoundError("run genuine I2a-M2 graph prediction first")
    m=read_json(NEW_MANIFEST)
    if m.get("status")!="PHASE6_GENUINE_I2A_M2_P4_G_SEQPAR_PREDICTION_COMPLETE":
        raise RuntimeError("genuine I2a-M2 prediction not complete")

    selected=_selected()
    old=pd.read_csv(P5_POINTWISE)
    old=old[
        (old["physical_cell_id"].astype(str)==CELL)
        & (old["method_id"].astype(str)=="M2")
        & (old["H"].astype(float)>=60)
        & (old["H"].astype(float)<=240)
    ].copy()
    new=pd.read_csv(NEW_PRED)
    new=new[(new["H"].astype(float)>=60)&(new["H"].astype(float)<=240)].copy()

    ROOT.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(12.6,3.8),sharex=True,sharey=True)
    long=[]
    for ax,regime in zip(axes,REGIMES):
        rec=selected[selected["regime"].astype(str)==regime].iloc[0]
        qid=str(rec["query_id"]); rho=float(rec["rho"])
        o=old[old["query_id"].astype(str)==qid].sort_values("H")
        n=new[new["query_id"].astype(str)==qid].sort_values("H")
        wb=o[["H","sigma_wb","wb_ci_lower","wb_ci_upper"]].drop_duplicates().sort_values("H")
        if len(o)!=37 or len(n)!=37 or len(wb)!=37:
            raise RuntimeError(f"{regime}: expected 37 points per curve")
        ax.fill_between(
            wb["H"].astype(float).to_numpy(),
            wb["wb_ci_lower"].astype(float).to_numpy(),
            wb["wb_ci_upper"].astype(float).to_numpy(),
            alpha=0.20,
        )
        ax.plot(wb["H"],wb["sigma_wb"],label="WB",linewidth=2.4)
        ax.plot(o["H"],o["sigma_hat"],label="I1-M2",linewidth=2.0,linestyle="--")
        ax.plot(n["H"],n["sigma_hat"],label="I2a-M2 genuine",linewidth=2.0,linestyle="-.")
        ax.set_title(f"{regime} | rho={rho:.4g}")
        ax.set_xlim(60,240); ax.set_ylim(0,1.02); ax.set_xticks([60,120,180,240])
        ax.grid(True,alpha=0.18); ax.set_xlabel("Horizon H (s)")
        for rr in wb.itertuples(index=False):
            long.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rr.H),"method":"WB","sigma":float(rr.sigma_wb)})
        for rr in o.itertuples(index=False):
            long.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rr.H),"method":"I1-M2","sigma":float(rr.sigma_hat)})
        for rr in n.itertuples(index=False):
            long.append({"query_id":qid,"regime":regime,"rho":rho,"H":float(rr.H),"method":"I2a-M2 genuine","sigma":float(rr.sigma_hat)})

    axes[0].set_ylabel(r"$\sigma_G(H)$")
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="upper center",ncol=3,frameon=False,bbox_to_anchor=(0.5,1.02))
    fig.suptitle("P4 / G_SEQPAR: WB vs I1-M2 vs genuine I2a-M2",y=1.10)
    fig.tight_layout()
    png=ROOT/"phase6_P4_G_SEQPAR_WB_I1M2_GenuineI2aM2.png"
    pdf=ROOT/"phase6_P4_G_SEQPAR_WB_I1M2_GenuineI2aM2.pdf"
    fig.savefig(png,dpi=220,bbox_inches="tight"); fig.savefig(pdf,bbox_inches="tight")
    plt.close(fig)
    data=ROOT/"plot_data_long.csv"; pd.DataFrame(long).to_csv(data,index=False)
    manifest=ROOT/"plot_manifest.json"
    write_json(manifest,{
        "status":"PHASE6_GENUINE_I2A_M2_COMPARISON_PLOT_COMPLETE",
        "methods":["WB","I1-M2","I2a-M2 genuine"],
        "outputs":{"png":str(png),"pdf":str(pdf),"plot_data":str(data)},
        "output_hashes_sha256":{"png":sha256_file(png),"pdf":sha256_file(pdf),"plot_data":sha256_file(data)},
        "completed_utc":utc_now_iso(),
    })
    print("PHASE6_GENUINE_I2A_M2_COMPARISON_PLOT_PASS")
    print("png",png)
    print("pdf",pdf)


if __name__=="__main__":
    run()
