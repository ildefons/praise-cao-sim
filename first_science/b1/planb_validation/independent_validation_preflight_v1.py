#!/usr/bin/env python3
"""Independent PRAISE B1 validation: local pipeline discovery and runtime preflight.

Discovery parses Python files without importing them, searches for relevant
entry points and CLI flags, and writes a structured inventory. Optional timed
commands must be explicitly supplied by the researcher in a JSON plan.
Never executes commands discovered automatically; never changes frozen data.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

STAGES = {
 "provider_generation": ("provider", "world", "generate", "generator", "sample", "seed"),
 "public_evidence": ("i1", "public", "card", "disclosure", "interface"),
 "reconstruction": ("reconstruct", "candidate", "support", "m1", "m2", "m3"),
 "composition_prediction": ("prediction", "predict", "graph", "composition"),
 "white_box": ("white_box", "whitebox", "wb_", "reference", "truth"),
 "evaluation": ("evaluate", "evaluation", "metrics", "mae", "score"),
}
EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
                "site-packages", "dist", "build", ".mypy_cache"}
SIGNALS = ("phase5", "first_science", "b1", "sim", "provider", "graph",
           "prediction", "evaluation", "whitebox", "white_box", "i1")
FLAGS = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+", re.IGNORECASE)


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda:f.read(1024*1024),b""):
            h.update(buf)
    return h.hexdigest()


def find_candidates(repo, max_files):
    out=[]
    scanned=0
    for root, dirs, files in os.walk(repo):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path=Path(root)/name
            rel=path.relative_to(repo).as_posix()
            if not any(key in rel.lower() for key in SIGNALS):
                continue
            scanned+=1
            if scanned>max_files:
                raise RuntimeError(f"More than {max_files} candidate Python files; increase --max-files")
            try:
                source=path.read_text(encoding="utf-8")
                tree=ast.parse(source)
            except (UnicodeError, OSError, SyntaxError) as exc:
                out.append(dict(path=rel, parse_error=str(exc), stage="", rank=0))
                continue
            funcs=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            imports=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):
                    imports.extend(alias.name for alias in n.names)
                elif isinstance(n,ast.ImportFrom) and n.module:
                    imports.append(n.module)
            literals=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Constant) and isinstance(n.value,str):
                    if any(k in n.value.lower() for k in ("output","metric","manifest","provider","evaluation","graph","world")):
                        literals.append(n.value[:130])
            haystack=(rel+" "+" ".join(funcs)+" "+" ".join(literals[:60])).lower()
            ratings={k:sum(tok in haystack for tok in tokens) for k,tokens in STAGES.items()}
            stage=max(ratings,key=ratings.get)
            rank=ratings[stage]
            if not rank:
                continue
            flags=sorted(set(FLAGS.findall(source)))
            main_guard=("__main__" in source and "main(" in source)
            out.append(dict(path=rel,stage=stage,rank=rank,
                            stages=";".join(k for k,v in ratings.items() if v>=2),
                            main_guard=int(main_guard),
                            flags=" ".join(flags[:80]),
                            functions=" ".join(funcs[:45]),
                            imports=" ".join(imports[:30]),
                            candidate_strings=" | ".join(literals[:8]),
                            sha256=digest(path),bytes=path.stat().st_size,
                            parse_error=""))
    return sorted(out,key=lambda r:(-r["rank"],-r["main_guard"],r["path"]))


def write_csv(path,records):
    if not records:
        raise RuntimeError("No candidate Python scripts found")
    fields=sorted({k for r in records for k in r})
    with path.open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def plan_and_run(repo, out, plan_file, timeout):
    plan=json.loads(plan_file.read_text())
    if not isinstance(plan,dict) or not isinstance(plan.get("commands"),list):
        raise ValueError("Plan must be object with list of commands")
    commands=plan["commands"]
    if not commands:
        raise ValueError("No benchmark commands")
    records=[]
    for index,item in enumerate(commands):
        if not isinstance(item,dict) or not isinstance(item.get("argv"),list):
            raise ValueError("Every command needs an argv array")
        argv=item["argv"]
        if not argv or not all(isinstance(v,str) and v for v in argv):
            raise ValueError("argv must be a nonempty array of nonempty strings")
        if any("\n" in v or "\0" in v for v in argv):
            raise ValueError("No newline or NUL in arguments")
        name=item.get("name",f"step_{index:02d}")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",name):
            raise ValueError("Command name must be a safe slug")
        cwd=(repo/item.get("cwd",".")).resolve()
        if not cwd.is_dir() or not cwd.is_relative_to(repo):
            raise ValueError("Working directory must exist inside repository")
        run_timeout=item.get("timeout_seconds",timeout)
        if not isinstance(run_timeout,(int,float)) or not 1<=run_timeout<=86400:
            raise ValueError("Command timeout must be in [1,86400]")
        start=time.perf_counter()
        try:
            p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,
                             errors="replace",timeout=run_timeout,check=False)
            code=p.returncode
            stdout=p.stdout
            stderr=p.stderr
            timed_out=False
        except subprocess.TimeoutExpired as e:
            code=None
            stdout=(e.stdout or b"").decode(errors="replace") if isinstance(e.stdout,bytes) else (e.stdout or "")
            stderr=(e.stderr or b"").decode(errors="replace") if isinstance(e.stderr,bytes) else (e.stderr or "")
            timed_out=True
        elapsed=time.perf_counter()-start
        (out/f"{index:02d}_{name}.stdout.txt").write_text(stdout,encoding="utf-8")
        (out/f"{index:02d}_{name}.stderr.txt").write_text(stderr,encoding="utf-8")
        records.append(dict(index=index,name=name,argv=argv,cwd=str(cwd),
                            exit_code=code,timed_out=timed_out,
                            wall_seconds=elapsed,requested_timeout=run_timeout))
        print("BENCHMARK",name,"wall_s",round(elapsed,3),"exit",code,"timeout",timed_out,flush=True)
        if code!=0:
            print("BENCHMARK_STOPPED_AFTER_FAILED_STEP",name,flush=True)
            break
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,default=Path.cwd())
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-files",type=int,default=20000)
    p.add_argument("--benchmark-plan",type=Path,
                   help="Explicit researcher-approved argv commands, optional")
    p.add_argument("--timeout-seconds",type=float,default=1800)
    args=p.parse_args()
    repo=args.repo.expanduser().resolve()
    out=args.out.expanduser().resolve()
    if not (repo/".git").exists():
        p.error("--repo must be a Git checkout")
    if out.exists():
        raise FileExistsError("Refusing to overwrite output directory: "+str(out))
    out.mkdir(parents=True)
    inventory=find_candidates(repo,args.max_files)
    write_csv(out/"pipeline_inventory.csv",inventory)
    stage_summary=[]
    for stage in STAGES:
        entries=[r for r in inventory if r.get("stage")==stage and not r.get("parse_error")]
        stage_summary.append(dict(
            stage=stage,total=len(entries),
            strongest_candidates=[r["path"] for r in entries[:10]]
        ))
    (out/"stage_summary.json").write_text(json.dumps(stage_summary,indent=2)+"\n")
    benchmarks=[]
    if args.benchmark_plan:
        plan=args.benchmark_plan.expanduser().resolve()
        benchmarks=plan_and_run(repo,out,plan,args.timeout_seconds)
    status=("PIPELINE_DISCOVERY_AND_APPROVED_BENCHMARK" if benchmarks else "PIPELINE_DISCOVERY_ONLY")
    manifest=dict(status=status,repo=str(repo),script_sha256=digest(Path(__file__)),
                  n_candidates=len(inventory),benchmarks=benchmarks,
                  warning=("Discovery does not establish that candidate scripts can generate independent worlds. "
                           "An explicit reviewed benchmark plan is required before execution."),
                  output_sha256={p.name:digest(p) for p in out.iterdir() if p.is_file()})
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("VALIDATION_PREFLIGHT_PASS",status)
    for row in stage_summary:
        print("STAGE",row["stage"],"CANDIDATES",row["total"],
              "TOP",row["strongest_candidates"][:3])
    print("OUTPUT",out)


if __name__=="__main__":
    main()
