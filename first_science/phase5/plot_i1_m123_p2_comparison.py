"""Plot same-region WB/M1/M2/M3 sigma curves for the P2 G_PAR pilot.

Read-only. Requires evaluate_i1_m123_p2_native_comparison.py to have run.
Produces five per-rho overlays, five per-rho error plots, and overview figures.
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
BASE=HERE/"results"/"i1_m3_p2_induced_pilot"/"P2__G_PAR"
SOURCE=BASE/"m1_m2_native_comparison"/"evaluation"/"matched_survival_curves.csv"
OUT=BASE/"m1_m2_native_comparison"/"evaluation"/"plots"
LABELS={"M1":"I1-M1","M2":"I1-M2","M3_FULL343":"I1-M3"}
METHODS=["M1","M2","M3_FULL343"]


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Run evaluate_i1_m123_p2_native_comparison.py first: {SOURCE}")
    df=pd.read_csv(SOURCE)
    required={"query_id","H","method","sigma_hat","sigma_wb"}
    if not required.issubset(df.columns):
        raise ValueError(f"missing columns: {required-set(df.columns)}")
    if set(df.method.unique())!=set(METHODS):
        raise ValueError("expected M1, M2, M3_FULL343")
    rho_query=pd.read_csv(BASE/"public_induced_queries.csv")[["query_id","rho"]]
    if len(rho_query)!=5 or rho_query.query_id.nunique()!=5:
        raise RuntimeError("expected exactly five frozen rho queries")
    if df[["query_id","H","method"]].duplicated().any():
        raise RuntimeError("duplicate method/query/horizon points")
    plotted=df.merge(rho_query,on="query_id",validate="many_to_one")
    OUT.mkdir(parents=True,exist_ok=True)
    fig_all,axs=plt.subplots(2,3,figsize=(15,9),sharex=True,sharey=True)
    fig_err,axs_err=plt.subplots(2,3,figsize=(15,9),sharex=True,sharey=True)
    for i,q in enumerate(rho_query.sort_values("rho").itertuples(index=False)):
        d=plotted[plotted.query_id==q.query_id]
        ax=axs.flat[i]
        ae=axs_err.flat[i]
        ref=d[d.method=="M1"].sort_values("H")
        if len(ref)!=49:raise RuntimeError(f"{q.query_id}: invalid WB horizon grid")
        ax.plot(ref.H,ref.sigma_wb,color="black",lw=2.3,label="White-box")
        fig,one=plt.subplots(figsize=(8,5))
        fig2,one_err=plt.subplots(figsize=(8,4))
        one.plot(ref.H,ref.sigma_wb,color="black",lw=2.3,label="White-box")
        one_err.axhline(0,color="black",lw=1)
        ae.axhline(0,color="black",lw=1)
        for method in METHODS:
            g=d[d.method==method].sort_values("H")
            if len(g)!=49 or not np.array_equal(g.H.to_numpy(),ref.H.to_numpy()):
                raise RuntimeError(f"{q.query_id}/{method}: grid mismatch")
            label=LABELS[method]
            ax.plot(g.H,g.sigma_hat,label=label)
            one.plot(g.H,g.sigma_hat,label=label)
            residual=g.sigma_hat.to_numpy()-g.sigma_wb.to_numpy()
            ae.plot(g.H,residual,label=label)
            one_err.plot(g.H,residual,label=label)
        for a in (ax,one):
            a.set_ylim(-0.025,1.025)
            a.set_xlabel("Horizon H (s)")
            a.set_ylabel("Graph survival sigma")
            a.set_title(f"P2 / G_PAR / rho={q.rho:g}")
            a.grid(alpha=.2)
        for a in (ae,one_err):
            a.set_xlabel("Horizon H (s)")
            a.set_ylabel("Predicted minus WB sigma")
            a.set_title(f"P2 / G_PAR / rho={q.rho:g}")
            a.grid(alpha=.2)
        one.legend(frameon=False)
        one_err.legend(frameon=False)
        token=f"{q.rho:.9f}".rstrip("0").rstrip(".").replace(".","p")
        fig.tight_layout()
        fig2.tight_layout()
        fig.savefig(OUT/f"rho_{token}_sigma.png",dpi=180)
        fig2.savefig(OUT/f"rho_{token}_error.png",dpi=180)
        plt.close(fig)
        plt.close(fig2)
    for empty in (axs.flat[-1],axs_err.flat[-1]):
        empty.axis("off")
    axs.flat[0].legend(frameon=False,fontsize=8)
    axs_err.flat[0].legend(frameon=False,fontsize=8)
    fig_all.suptitle("P2 G_PAR: WB / M1 / M2 / M3, common A_G(rho)")
    fig_err.suptitle("P2 G_PAR: survival prediction errors")
    for fig,name in [(fig_all,"all_rho_sigma.png"),(fig_err,"all_rho_error.png")]:
        fig.tight_layout()
        fig.savefig(OUT/name,dpi=200)
        plt.close(fig)
    print(f"P2_G_PAR_M123_SIGMA_PLOTS_PASS: 12 PNG files in {OUT}")


if __name__=="__main__":
    main()
