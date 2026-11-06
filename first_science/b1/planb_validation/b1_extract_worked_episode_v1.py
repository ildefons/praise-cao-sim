#!/usr/bin/env python3
"""Extract one REAL archived B1 episode; never simulate or change frozen evidence."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
import numpy as np

def read(p):
    with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,rows):
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=tuple(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--terminal",type=Path,required=True)
    p.add_argument("--actions",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--policy",choices=("random","balanced","informed","budgeted_top2"),default="budgeted_top2")
    p.add_argument("--budget",type=int,choices=(10,15,20,30,40),default=15)
    p.add_argument("--start-index",type=int,choices=range(12),default=1)
    p.add_argument("--replicate",type=int,choices=range(20),default=0)
    a=p.parse_args()
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import b1_budget_comparison_v1 as f
    paths={k:getattr(a,k).expanduser().resolve() for k in ("matrix","terminal","actions")}
    dest=a.out.expanduser().resolve()
    if dest.exists():raise FileExistsError("Refusing overwrite: "+str(dest))
    m=read(paths["matrix"])
    entries={(r["method"],r["world"],r["graph"]):float(r["mae"]) for r in m}
    if len(m)!=84 or len(entries)!=84:raise ValueError("Invalid matrix length or duplicated key")
    if set(entries)!={(method,w,g) for method in f.METHODS for w,g in f.CELLS}:
        raise ValueError("Unexpected matrix methods or cells")
    Y=np.array([[entries[(method,w,g)] for w,g in f.CELLS] for method in f.METHODS])
    target=(str(a.budget),str(a.start_index),str(a.replicate),a.policy)
    filt=lambda r:(r["budget"],r["start_index"],r["replicate"],r["policy"])==target
    terminal=[r for r in read(paths["terminal"]) if filt(r)]
    history=[r for r in read(paths["actions"]) if filt(r)]
    if len(terminal)!=1 or len(history)!=a.budget:
        raise ValueError("Archive does not contain exactly one requested episode")
    history.sort(key=lambda x:int(x["step"]))
    if [int(r["step"]) for r in history]!=list(range(1,a.budget+1)):
        raise ValueError("Unexpected trace step numbering")
    seen=[];uniq=set()
    for i,r in enumerate(history):
        key=(r["method"],r["world"],r["graph"])
        if key in uniq:raise ValueError("Repeated action")
        uniq.add(key)
        if abs(float(r["mae"])-entries[key])>1e-12:
            raise ValueError("Trace loss differs from validated matrix: "+str(key))
        method=f.METHODS.index(r["method"]);cell=f.CELLS.index((r["world"],r["graph"]))
        if i<7 and (method!=i or cell!=a.start_index):
            raise ValueError("Incorrect common-start initialization")
        seen.append((method,cell,float(r["mae"])))
    posterior,_,_=f.posterior(seen,7)
    selected=f.METHODS[int(np.argmin(posterior))]
    truth=Y.mean(axis=1)
    best=f.METHODS[int(np.argmin(truth))]
    regret=max(0.,float(truth[f.METHODS.index(selected)]-min(truth)))
    t=terminal[0]
    if selected!=t["recommended"] or abs(regret-float(t["simple_regret"]))>1e-12:
        raise ValueError("Terminal decision/regret does not reproduce from trace")
    if int(t["correct"])!=int(selected==best):raise ValueError("Incorrect correct flag")
    if t["start_cell"]!=f.CELLS[a.start_index][0]+"__"+f.CELLS[a.start_index][1]:
        raise ValueError("Incorrect terminal start cell")
    dest.mkdir(parents=True)
    write(dest/"worked_episode_actions.csv",history)
    posterior_rows=[{"method":method,"observed_count":sum(x[0]==i for x in seen),
                     "posterior_mean_mae":float(posterior[i]),
                     "true_12_cell_mean_mae_OFFLINE_ONLY":float(truth[i])}
                    for i,method in enumerate(f.METHODS)]
    write(dest/"worked_episode_terminal_estimates.csv",posterior_rows)
    lines=[
      "# Real archived B1 sequential validation episode","",
      "**Provenance:** extracted directly from archived original B1 episode CSVs; not a synthetic story. "
      "The full-domain errors below are retrospective evaluator-only quantities, "
      "never exposed to acquisition policy.","",
      f"**Policy:** \`{a.policy}\` · **Budget:** {a.budget} unique evaluations · "
      f"**Starting condition:** {f.CELLS[a.start_index][0]} / {f.CELLS[a.start_index][1]} "
      f"· **Repetition:** {a.replicate}.","",
      "| Step | Predictor | Provider world | Graph | Revealed cell MAE |",
      "|---:|---|---|---|---:|"]
    for r in history:
        lines.append(f'| {r["step"]} | {r["method"]} | {r["world"]} | {r["graph"]} | {float(r["mae"]):.6f} |')
    lines+=["","## Terminal choice (policy-available posterior only)","",
        "| Predictor | Observations | Posterior mean domain MAE |",
        "|---|---:|---:|"]
    for x in posterior_rows:
        lines.append(f'| {x["method"]} | {x["observed_count"]} | {x["posterior_mean_mae"]:.6f} |')
    lines+=["",f"**Selected predictor:** \`{selected}\`.",
            "","## Retrospective audit, inaccessible to selector","",
            f"**Reference best across 12 cells:** \`{best}\`.",
            f"**Terminal simple regret:** {regret:.9f}.",
            f"**Correct best-method decision:** {selected==best}.","",
            "The example demonstrates an **overall predictor choice for the entire 12-cell domain**, "
            "not a per-graph routing decision. No computation-time savings or live deployment are established."]
    (dest/"worked_episode.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    manifest={"status":"B1_ORIGINAL_EPISODE_TRACE_VERIFIED","source_hash_sha256":
        {k:sha(p) for k,p in paths.items()},"policy":a.policy,"budget":a.budget,
        "start_index":a.start_index,"replicate":a.replicate,
        "selected":selected,"best_reference_OFFLINE_ONLY":best,
        "regret":regret,
        "script_sha256":sha(Path(__file__).resolve()),
        "outputs_sha256":{f.name:sha(f) for f in dest.iterdir() if f.is_file()}}
    (dest/"episode_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("B1_WORKED_EPISODE_VERIFIED",dest)
    print("SELECTED",selected,"REFERENCE_BEST",best,"REGRET",regret)
if __name__=="__main__":main()
