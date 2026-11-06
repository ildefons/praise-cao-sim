#!/usr/bin/env python3
"""Plot controlled two-stage ablation (7 policies), plus 9-policy reference figure.

Reads existing 95% stratified-bootstrap intervals; runs no new experiments.
Original one-stage KG and Top2 appear only in the 9-policy reference panel.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HASHES={"original":"12a163b488266119f68391e96c8c63cebb4576516a312d3e48b5d4e77c657c80",
        "kg":"38deebbc19fc371817b5e7a5f9d9e2457a773de217010fb1da7ffb4e83cb792f"}
MATCHED=("random","balanced","informed","kg_two_stage_adaptive","kg_two_stage_uniform",
         "top2_two_stage_adaptive","top2_two_stage_uniform")
REFERENCE=MATCHED+("kg_one_step","budgeted_top2")
LABELS={"random":"Random","balanced":"Balanced","informed":"Informed",
        "kg_two_stage_adaptive":"KG two-stage adaptive",
        "kg_two_stage_uniform":"KG two-stage uniform",
        "top2_two_stage_adaptive":"Top2 two-stage adaptive",
        "top2_two_stage_uniform":"Top2 two-stage uniform",
        "kg_one_step":"KG original joint","budgeted_top2":"Top2 original joint"}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def render(df,policies,path,title):
    fig,ax=plt.subplots(figsize=(11.7,7),layout="constrained")
    colors=plt.rcParams["axes.prop_cycle"].by_key()["color"]
    marks=("o","s","^","D","v","P","X","h","*")
    for i,p in enumerate(policies):
        z=df[df.policy==p].sort_values("budget")
        y=z.mean_regret.to_numpy(float)
        err=np.vstack((y-z.regret_low.to_numpy(float),z.regret_high.to_numpy(float)-y))
        color=colors[0] if p.startswith("kg_") else colors[1] if p.startswith("top2_") or p=="budgeted_top2" else colors[2+i%5]
        style="--" if p.endswith("_uniform") else ":" if p in ("kg_one_step","budgeted_top2") else "-"
        ax.errorbar(z.budget,y,yerr=err,linestyle=style,marker=marks[i],color=color,
                    markersize=5,capsize=3,linewidth=1.8,label=LABELS[p])
    ax.set(title=title,xlim=(8,42),ylim=(0,.024),xticks=(10,15,20,30,40),
           xlabel="Evaluation budget (distinct predictor–condition measurements)",
           ylabel="Mean terminal simple regret (MAE units; lower is better)")
    ax.grid(axis="y",alpha=.25)
    ax.legend(fontsize=8.2,loc="upper right")
    fig.text(.5,-.013,"95% stratified percentile bootstrap (2,000 draws), conditional on one historical archive. "
                     "Dotted original joint policies are reference-only, not matched ablation arms.",
                     ha="center",va="top",fontsize=8)
    fig.savefig(path,dpi=220,bbox_inches="tight",pad_inches=.16)
    plt.close(fig)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original-summary",type=Path,required=True)
    ap.add_argument("--kg-summary",type=Path,required=True)
    ap.add_argument("--controlled-summary",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    inputs={"original":a.original_summary.expanduser().resolve(),
            "kg":a.kg_summary.expanduser().resolve(),
            "controlled":a.controlled_summary.expanduser().resolve()}
    out=a.out.expanduser().resolve()
    if out.exists():raise FileExistsError("Refusing overwrite: "+str(out))
    for name,h in HASHES.items():
        if digest(inputs[name])!=h:raise ValueError("Original summary SHA mismatch "+name)
    df=pd.concat([pd.read_csv(p) for p in inputs.values()],ignore_index=True)
    if len(df)!=45 or df.duplicated(["policy","budget"]).any() or set(df.policy)!=set(REFERENCE):
        raise ValueError("Expected 45 unique rows (9 policies x 5 budgets)")
    for p in REFERENCE:
        x=df[df.policy==p]
        if sorted(x.budget.tolist())!=[10,15,20,30,40] or (x.episodes!=240).any():
            raise ValueError("Missing budget/episodes: "+p)
    vals=df[["mean_regret","regret_low","regret_high"]].to_numpy(float)
    if not np.isfinite(vals).all() or (vals[:,1]>vals[:,0]).any() or (vals[:,0]>vals[:,2]).any():
        raise ValueError("Invalid 95% interval")
    out.mkdir(parents=True)
    for stem,policies,title in (
        ("b1_controlled_seven_policy_regret_vs_budget_ci_v1",MATCHED,"Controlled condition-selection comparison"),
        ("b1_nine_policy_with_historical_refs_ci_v1",REFERENCE,"Matched comparison and original historical policies")):
        df[df.policy.isin(policies)].to_csv(out/(stem+".csv"),index=False)
        for ext in ("png","svg"):
            render(df,policies,out/(stem+"."+ext),title)
    manifest={"status":"B1_CONTROLLED_TWO_STAGE_FIGURES_V1",
              "inputs_sha256":{n:digest(p) for n,p in inputs.items()},
              "controlled_policies":MATCHED,"historical_refs":("kg_one_step","budgeted_top2"),
              "bootstrap_replicates":2000,"new_bootstraps":0,"new_simulations":0,
              "outputs_sha256":{p.name:digest(p) for p in out.iterdir() if p.is_file()}}
    (out/"plot_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("B1_CONTROLLED_TWO_STAGE_CONDITION_FIGURES_PASS",out)
if __name__=="__main__":main()
