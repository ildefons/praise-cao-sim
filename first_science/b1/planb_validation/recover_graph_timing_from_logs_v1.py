#!/usr/bin/env python3
"""Read-only recovery of B1 original-style and fixed-CV runtime evidence.

Looks only inside declared project directories and optional explicit log files.
Does not run a simulator, alter archived evidence, or infer elapsed time from
file modification/birth timestamps.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]
CELLS=tuple(f"{w}__{g}" for w in ("P1","P3","P4")
             for g in ("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR"))
FAMILIES={
    "original_style":"b1_pilot_m3_retrospective_v1",
    "fixed_cv":"b1_fixed_cv_top1_top14_b1400_v1",
}
EXTS={".log",".out",".time",".txt"}
SKIP_DIRS={".git","checkpoints","ledgers","surfaces","__pycache__",".venv","node_modules"}
GAP_COLUMNS=("family","previous_cell","current_cell",
             "previous_completed_utc","current_completed_utc",
             "seconds_between_completions","interpretation")
LOG_COLUMNS=("family","file","sha256","line_number","kind",
             "seconds","cell","text")
# Recognize measured shell time output (not estimates printed by a simulator).
BASH_REAL=re.compile(r"^\s*real\s+(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?P<s>\d+(?:\.\d+)?)s\s*$",re.I)
POSIX_REAL=re.compile(r"^\s*real\s+(?P<seconds>\d+(?:\.\d+)?)\s*$",re.I)
GNU_TIME=re.compile(r"Elapsed \(wall clock\) time \([^)]*\):\s*(?P<time>(?:\d+:)?\d+:\d+(?:\.\d+)?)\s*$",re.I)
CELL_RE=re.compile(r"\bP[134]__G_(?:PARSEQ|SEQPAR|PAR|SEQ)\b")
PROGRESS_RE=re.compile(r"\belapsed=(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>min|s|h)\b",re.I)
MARKERS=(
    ("fixed_cv_cell_begin","=== FIXED CV"),
    ("fixed_cv_cell_done","PREDICTED AND FROZEN"),
    ("original_cell_done","PREDICTED "),
    ("fixed_cv_finished","B1_FIXED_CV_TOP1_TOP14_STAGE_ALL_PASS"),
    ("original_all_frozen","B1_RETROSPECTIVE_ALL_12_PREDICTIONS_FROZEN"),
    ("graph_benchmark_observation","GRAPH BENCHMARK COMPLETE"),
    ("graph_benchmark_projection","GRAPH BENCHMARK PROJECTION"),
    ("candidate_progress","PREPARE "),
    ("top1_progress","TOP1"),
)
# Only a fully observed command-level 'real' is a candidate measured wall time.
# A runner's progress elapsed is not a separate command-duration measurement.

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def write_csv(path,rows,columns):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

def family_for(path,text=""):
    p=str(path).lower()
    if "fixed_cv_top1_top14" in p or "b1_fixed_cv_top1_top14" in p:
        return "fixed_cv"
    if "pilot_m3_retrospective" in p or "run_pilot_m3_generalization" in text.lower():
        return "original_style"
    if "b1_fixed_cv_top1_top14" in text.lower():
        return "fixed_cv"
    return "unclassified"

def get_time(line):
    m=BASH_REAL.match(line)
    if m:
        return 3600*int(m.group("h") or 0)+60*int(m.group("m") or 0)+float(m.group("s"))
    m=POSIX_REAL.match(line)
    if m:return float(m.group("seconds"))
    m=GNU_TIME.search(line)
    if m:
        parts=[float(x) for x in m.group("time").split(":")]
        if len(parts)==2:return parts[0]*60+parts[1]
        if len(parts)==3:return parts[0]*3600+parts[1]*60+parts[2]
    return None

def inspect_log(path,repo):
    rows=[]
    if path.stat().st_size>20*1024*1024:
        return rows,{"path":str(path),"status":"SKIPPED_OVER_20MB"}
    digest=sha(path)
    try:
        with path.open("r",encoding="utf-8",errors="replace") as f:
            for i,line in enumerate(f,1):
                s=line.strip()
                if not s:continue
                family=family_for(path,s)
                measurement=get_time(s)
                kind="shell_measured_wall" if measurement is not None else None
                if kind is None:
                    for tag,token in MARKERS:
                        if token in s:
                            kind=tag
                            break
                if kind is None and "elapsed=" in s and ("estimated" not in s.lower() or "PROGRESS" in s):
                    kind="progress_elapsed_not_whole_run"
                if kind is None:continue
                c=CELL_RE.search(s)
                rows.append({
                    "family":family,"file":str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path),
                    "sha256":digest,"line_number":i,"kind":kind,
                    "seconds":round(measurement,6) if measurement is not None else "",
                    "cell":c.group(0) if c else "","text":s[:300],
                })
    except OSError as exc:
        return rows,{"path":str(path),"status":"READ_ERROR","error":str(exc)}
    return rows,{"path":str(path),"status":"READ","sha256":digest,"matched_rows":len(rows)}

def discover_logs(repo,extras):
    roots=(
        repo/"first_science/b1/local_audit",
        repo/"first_science/b1/retrospective_m3",
        repo/"first_science/phase5/results/b1_pilot_m3_retrospective_v1",
        repo/"first_science/phase5/results/b1_fixed_cv_top1_top14_b1400_v1",
    )
    found=set()
    for root in roots:
        if not root.is_dir():continue
        for base, dirs, names in os.walk(root):
            dirs[:]=[d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                p=Path(base)/name
                if p.suffix.lower() in EXTS and p.is_file():
                    found.add(p.resolve())
    for extra in extras:
        p=extra.expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Explicit log not found: {p}")
        found.add(p)
    return sorted(found)

def manifest_events(repo):
    rows=[]; gaps=[]; counts={}
    for family,folder in FAMILIES.items():
        has_datetime=[]
        found=0
        for cell in CELLS:
            p=(repo/"first_science/phase5/results"/folder/
               "predictions"/cell/"prediction_manifest.json")
            if not p.is_file():continue
            obj=json.loads(p.read_text())
            found+=1
            dt=obj.get("completed_utc")
            if dt:
                stamp=datetime.fromisoformat(dt)
                if stamp.tzinfo is None:raise ValueError(f"Naive UTC timestamp: {p}")
                has_datetime.append((stamp,cell,dt))
        has_datetime.sort()
        counts[family]={"frozen_manifests":found,"expected":12,
                        "with_completed_utc":len(has_datetime)}
        for ts,cell,t in has_datetime:
            rows.append({"family":family,"cell":cell,"completed_utc":t})
        for earlier,later in zip(has_datetime,has_datetime[1:]):
            gap=(later[0]-earlier[0]).total_seconds()
            gaps.append({
                "family":family,"previous_cell":earlier[1],"current_cell":later[1],
                "previous_completed_utc":earlier[2],"current_completed_utc":later[2],
                "seconds_between_completions":round(gap,6),
                "interpretation":"Completion-to-completion gap ONLY; not a measured cell runtime, may include other work/idle.",
            })
    return rows,gaps,counts

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo",type=Path,default=ROOT)
    ap.add_argument("--out",type=Path,default=Path.home()/"praise/planb_b1_archival_graph_timing_v1")
    ap.add_argument("--log",action="append",type=Path,default=[],help="Additional explicitly named historical log file (repeatable)")
    args=ap.parse_args()
    repo=args.repo.expanduser().resolve()
    out=args.out.expanduser().resolve()
    if out==repo or repo in out.parents:
        ap.error("Output directory must be outside the repository to preserve frozen evidence")
    out.mkdir(parents=True,exist_ok=True)
    logs=discover_logs(repo,args.log)
    logrows=[]; logstatus=[]
    for p in logs:
        rows,meta=inspect_log(p,repo)
        logrows.extend(rows);logstatus.append(meta)
    events,gaps,counts=manifest_events(repo)
    write_csv(out/"log_timing_evidence.csv",logrows,LOG_COLUMNS)
    write_csv(out/"manifest_completion_gaps_NOT_RUNTIME.csv",gaps,GAP_COLUMNS)
    write_csv(out/"manifest_completion_events.csv",events,("family","cell","completed_utc"))
    (out/"log_inventory.json").write_text(json.dumps(logstatus,indent=2)+"\n")
    measured=[r for r in logrows if r["kind"]=="shell_measured_wall"]
    report=[
        "# B1 archival original-style and fixed-CV timing recovery","",
        "**Read-only historical evidence search. No new graph, WB or provider simulations.**","",
        f"- Eligible candidate logs inspected: **{len(logs)}**.",
        f"- Explicit shell-measured wall-time markers found: **{len(measured)}**.",
        f"- Frozen original-style per-cell manifests: **{counts['original_style']['frozen_manifests']}/12**; with completed_utc: **{counts['original_style']['with_completed_utc']}**.",
        f"- Frozen fixed-CV per-cell manifests: **{counts['fixed_cv']['frozen_manifests']}/12**; with completed_utc: **{counts['fixed_cv']['with_completed_utc']}**.",
        "",
        "## Timing evidence interpretation","",
        "A shell \`real\` or GNU time marker is only a **candidate measured duration**: associate it with the exact invocation and check for cached/reused cells before aggregating. Log lines reporting a graph benchmark projection are estimates, not measurements. A progress elapsed time is a partial interval, not the whole batch.",
        "Manifest completion gaps are stored separately as **NOT_RUNTIME**. Their timestamps do not identify cell start times and cannot safely reconstruct per-cell execution times, especially after resumption, parallel execution or pauses.",
        "If the fixed-CV run.log has no embedded timestamp or command-level \`real\`, that log proves completion, not measured wall-clock duration. File creation and modification timestamps are intentionally **not** used as measurements.",
        "",
        "## Log evidence","",
    ]
    if measured:
        report+=["| Family | File | Line | Shell real (h) |","|---|---|---:|---:|"]
        for r in measured:
            report.append(f"| {r['family']} | \`{r['file']}\` | {r['line_number']} | {float(r['seconds'])/3600:.6f} |")
    else:
        report.append("**No explicit measured shell-time marker found in inspected log files.** This is not evidence of zero runtime.")
    report+=["","## Next step","",
        "Inspect \`log_timing_evidence.csv\` for exact source lines and any log timestamp prefixes. If the fixed-CV run has no explicit start/end timestamps, search for contemporaneous scheduler or shell-time output; otherwise leave fixed-CV hours unmeasured. Do not rerun simulations simply to obtain timing.",
    ]
    (out/"ARCHIVAL_TIMING_RECOVERY.md").write_text("\n".join(report)+"\n")
    hashes={p.name:sha(p) for p in out.glob("*") if p.is_file()}
    (out/"recovery_manifest.json").write_text(json.dumps({
        "status":"B1_ARCHIVAL_TIMING_RECOVERY_V1",
        "read_only":True,"simulations_performed":0,
        "logs_inspected":len(logs),"measured_time_markers":len(measured),
        "per_family_manifest_coverage":counts,
        "output_sha256":hashes,
    },indent=2)+"\n")
    print("B1_ARCHIVAL_TIMING_RECOVERY_PASS")
    print("LOGS_INSPECTED",len(logs),"SHELL_TIME_MARKERS",len(measured))
    for family,data in counts.items():
        print("MANIFESTS",family,data)
    print("REPORT",out/"ARCHIVAL_TIMING_RECOVERY.md")
    print("EVIDENCE",out/"log_timing_evidence.csv")

if __name__=="__main__":
    main()
