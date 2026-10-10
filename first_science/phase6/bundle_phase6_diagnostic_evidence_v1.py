"""Discover and bundle existing Phase-6 reconstruction evidence for diagnostic review.

Run from anywhere. Default scan is local first_science/phase6/results.
Does not write into source folders, does not run simulations, and excludes
private request ledgers, hidden parameter files and raw trajectory rows.
"""
from __future__ import annotations
import argparse, csv, json, re, zipfile, hashlib
from pathlib import Path
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
METHODS={
 "I1STRONG":("18_i1strong_reconstruction_p4",),
 "I2AFS":("14_i2a_fullspectrum_reconstruction_p4",),
 "I2B_V1":("24_i2b_energy_reconstruction_p4",),
 "I2B_V2":("28_i2b_varweight_reconstruction_p4",),
 "I2B_V3":("32_i2b_hierarchical_reconstruction_p4",),
 "I2B_V4":("36_i2b_v4_mean_range_reconstruction_p4",),
}
KEYS=("provider_models","rescore_top24","search_trials","by_lag",
      "joint_support","reconstruction_manifest","provider_reconstruction_manifest",
      "provider_summary")
GRAPHS=("member_curves","predictions","evaluation","pointwise","comparison",
        "decision","metrics","manifest")
REDACT=re.compile(r"(private|request_ledgers|trajectory_ledgers|hidden|ground_truth|oracle|\.git)",re.I)
EXT={".csv",".json",".md",".txt"}
MAX_FILE=30*1024*1024

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def eligible(p,base,category):
    if p.suffix.lower() not in EXT or p.stat().st_size>MAX_FILE:return False
    relative=p.relative_to(base)
    if any(REDACT.search(part) for part in relative.parts):return False
    name=p.name.lower()
    if category=="reconstruction":
        return any(k in name for k in KEYS) or name.endswith("manifest.json")
    return any(k in name for k in GRAPHS)

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument("--results",type=Path,default=HERE/"results")
    pa.add_argument("--output",type=Path,default=HERE/"diagnostics"/"phase6_evidence_bundle.zip")
    pa.add_argument("--include-graph",action="store_true",help="Include compact graph diagnostics and per-member curves")
    args=pa.parse_args();base=args.results.resolve();out=args.output.resolve()
    if not base.is_dir():raise SystemExit(f"Missing results root: {base}")
    out.parent.mkdir(parents=True,exist_ok=True)
    selected=[];missing=[];seen=set()
    for method,folders in METHODS.items():
        located=False
        for folder in folders:
            root=base/folder
            if not root.exists():continue
            located=True
            for p in sorted(root.rglob("*")):
                if p.is_file() and eligible(p,root,"reconstruction"):
                    arc=f"reconstructions/{method}/{p.relative_to(root).as_posix()}"
                    if arc not in seen: selected.append((p,arc,method));seen.add(arc)
        if not located:missing.append(f"{method}: expected one of {folders}")
    if args.include_graph:
        for root in sorted(p for p in base.iterdir() if p.is_dir() and re.search(r"evaluation|prediction|seqpar|five_way|six_way",p.name,re.I)):
            for p in sorted(root.rglob("*")):
                if p.is_file() and eligible(p,root,"graph"):
                    arc=f"graph/{root.name}/{p.relative_to(root).as_posix()}"
                    if arc not in seen:selected.append((p,arc,"GRAPH"));seen.add(arc)
    records=[]
    for p,arc,method in selected:
        records.append(dict(method=method,archive_path=arc,bytes=p.stat().st_size,sha256=digest(p)))
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),results_root=str(base),
                files=len(records),total_uncompressed_bytes=sum(r["bytes"] for r in records),
                missing_directories=missing,
                notes=[
                    "Development-only evidence. No new simulation or reconstruction.",
                    "Private ledgers and hidden/ground-truth paths intentionally excluded.",
                    "May include search-trial CSVs with public candidate parameters and fit scores.",
                    "Manifest SHA256 values allow source verification.",
                ],inventory=records)
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,arc,_ in selected:z.write(p,arc)
        z.writestr("INVENTORY.json",json.dumps(report,indent=2))
        z.writestr("MISSING.txt","\n".join(missing)+"\n")
    print("PHASE6_DIAGNOSTIC_EVIDENCE_BUNDLE_PASS")
    print(f"FILES {len(records)}  SOURCE SIZE {report['total_uncompressed_bytes']/1048576:.2f} MiB")
    print("METHOD COUNTS")
    for k in METHODS:
        print(f"  {k}: {sum(x['method']==k for x in records)}")
    if missing:print("MISSING DIRECTORIES:",*missing,sep="\n  ")
    print("UPLOAD ZIP",out)
if __name__=="__main__":main()
