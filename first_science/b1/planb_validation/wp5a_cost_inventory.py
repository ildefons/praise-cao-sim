#!/usr/bin/env python3
"""WP5a: read-only inventory of completed graph group timers; no simulation."""
import argparse, csv, hashlib, json, os, re
from pathlib import Path

PATTERN=re.compile(r"\b(P[134]__G_(?:PARSEQ|SEQPAR|PAR|SEQ))\s+(M1|M2|M3_FULL343|ORIGINAL_TOP14|ORIGINAL_TOP1|FIXED_CV_TOP14|FIXED_CV_TOP1):\s+models\s+(\d+)/(\d+)\s*\|\s*trajectories\s+(\d+)/(\d+)\s*\|\s*elapsed=(\d+(?:\.\d+)?)\s+min\b")
COUNTS={"M1":100,"M2":2700,"M3_FULL343":1400,"ORIGINAL_TOP14":1400,"ORIGINAL_TOP1":1400,"FIXED_CV_TOP14":1400,"FIXED_CV_TOP1":1400}
CELLS=[f"{w}__{g}" for w in ("P1","P3","P4") for g in ("G_PAR","G_PARSEQ","G_SEQ","G_SEQPAR")]
SKIP={".git","ledgers","checkpoints","__pycache__","surfaces","plots","individual"}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,default=Path.cwd())
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--log",type=Path,action="append",default=[])
    a=p.parse_args(); repo=a.repo.resolve(); out=a.out.expanduser().resolve()
    if out==repo or repo in out.parents: p.error("Output must be outside repository")
    if out.exists(): p.error("Output already exists")
    roots=[repo/"first_science/b1/local_audit",repo/"first_science/phase5",repo/"first_science/b1/retrospective_m3"]
    logs={x.expanduser().resolve() for x in a.log}
    for root in roots:
        for base,dirs,files in os.walk(root):
            dirs[:]=[d for d in dirs if d not in SKIP]
            logs.update(Path(base,f).resolve() for f in files if Path(f).suffix.lower() in {".log",".out",".txt",".time"})
    records=[]; inventory=[]
    for f in sorted(logs):
        if not f.is_file(): raise FileNotFoundError(f)
        if f.stat().st_size>100*1024**2:
            inventory.append({"path":str(f),"status":"skipped_over_100MB"}); continue
        data=f.read_bytes(); sha=hashlib.sha256(data).hexdigest(); count=0
        for line_no,line in enumerate(data.decode("utf-8",errors="replace").splitlines(),1):
            m=PATTERN.search(line)
            if not m: continue
            cell,method,done,total,n,nt,mins=m.groups()
            if done!=total or n!=nt or int(nt)!=COUNTS[method]: continue
            records.append(dict(cell=cell,method=method,minutes=float(mins),trajectories=int(nt),file=str(f),sha256=sha,line=line_no,text=line.strip()[:500]))
            count+=1
        inventory.append({"path":str(f),"sha256":sha,"completed_markers":count})
    out.mkdir(parents=True)
    def write(name,rows,fields):
        with (out/name).open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    write("timing_candidates.csv",records,["cell","method","minutes","trajectories","file","sha256","line","text"])
    coverage=[]
    for cell in CELLS:
        for method in COUNTS:
            hits=[r for r in records if r["cell"]==cell and r["method"]==method]
            times=sorted({r["minutes"] for r in hits})
            coverage.append(dict(cell=cell,method=method,markers=len(hits),distinct_times=len(times),candidate_minutes=";".join(map(str,times)),status="missing" if not hits else "review_cache_and_run_provenance"))
    write("coverage.csv",coverage,["cell","method","markers","distinct_times","candidate_minutes","status"])
    (out/"inventory.json").write_text(json.dumps({"logs":inventory,"scope":"candidate completed graph-group wall timers only; no automatic attribution to uncached frozen execution"},indent=2))
    for method in COUNTS:
        print(method,sum(r["method"]==method and r["markers"]>0 for r in coverage),"/12 cells with candidate timing")
    print("WP5A_READ_ONLY_INVENTORY_COMPLETE",out)
if __name__=="__main__": main()
