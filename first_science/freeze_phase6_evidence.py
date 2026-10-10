"""Create a SHA256 inventory and tar archive of completed first_science results.
Run from repository; archive is written outside Git. No existing results modified.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,tarfile,subprocess

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--destination",type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    dest=(args.destination or root.parent/"praise-evidence-freezes").resolve()
    if dest==root or root in dest.parents:raise ValueError("Archive must be outside repository")
    sources=sorted({p for d in root.glob("first_science/**/results") for p in d.rglob("*") if p.is_file() and not p.is_symlink()})
    print("FILES",len(sources),"BYTES",sum(p.stat().st_size for p in sources))
    print("ARCHIVE_DIRECTORY",dest)
    if not args.execute:
        print("DRY_RUN: add --execute to create archive")
        return
    dest.mkdir(parents=True,exist_ok=True)
    suffix=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive=dest/("praise_results_"+suffix+".tar")
    if archive.exists():raise FileExistsError(archive)
    entries=[]
    with tarfile.open(archive,"w") as tar:
        for i,p in enumerate(sources,1):
            rel=str(p.relative_to(root))
            hashval=sha256(p)
            tar.add(p,arcname=rel,recursive=False)
            entries.append({"path":rel,"size":p.stat().st_size,"sha256":hashval})
            if i%500==0:print("ARCHIVED",i,"OF",len(sources),flush=True)
    with tarfile.open(archive) as tar:
        if len(tar.getmembers())!=len(sources):raise RuntimeError("Incomplete archive")
    result={"created_utc":suffix,"archive":archive.name,"archive_sha256":sha256(archive),"files":entries,
        "note":"Second independent backup required. Git commits do not include this archive."}
    manifest=dest/(archive.stem+".manifest.json")
    manifest.write_text(json.dumps(result,indent=2)+"\n")
    print("FREEZE_ARCHIVE_CREATED",archive)
    print("MANIFEST",manifest)
    print("SHA256",result["archive_sha256"])
if __name__=="__main__":main()
