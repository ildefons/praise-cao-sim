#!/usr/bin/env python3
"""Read-only local evidence inventory for PRAISE B1 registry v0.1.

No YAFS imports, no simulation, no method evaluation, no change to frozen
experiments. Hashes manifest JSONs, not large request/trajectory ledgers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIRST = HERE.parent
REGISTRY = HERE / "evidence_registry_v0_1.json"
OUT = HERE / "local_audit"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_root(path: Path, max_files: int) -> dict:
    if not path.exists():
        return {"exists": False, "file_count": 0, "total_bytes": 0, "truncated": False}
    if path.is_file():
        return {
            "exists": True,
            "kind": "file",
            "file_count": 1,
            "total_bytes": path.stat().st_size,
            "truncated": False,
        }
    count = 0
    nbytes = 0
    truncated = False
    for parent, _dirs, files in os.walk(path):
        for name in files:
            file = Path(parent) / name
            if not file.is_file():
                continue
            count += 1
            nbytes += file.stat().st_size
            if count >= max_files:
                truncated = True
                break
        if truncated:
            break
    return {
        "exists": True, "kind": "directory",
        "file_count": count, "total_bytes": nbytes,
        "truncated": truncated,
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-files-per-root", type=int, default=100000)
    ap.add_argument("--max-manifest-mb", type=float, default=8.0)
    args = ap.parse_args()
    if args.max_files_per_root < 1 or args.max_manifest_mb <= 0:
        ap.error("limits must be positive")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("schema_id") != "PRAISE_B1_EVIDENCE_REGISTRY_V0_1":
        raise ValueError("registry schema mismatch")
    source_paths = sorted({p for e in registry["entries"] for p in e["source_paths"]})
    data_paths = sorted({p for e in registry["entries"] for p in e["local_artifact_paths"]})
    missing = []

    sources = {}
    for rel in source_paths:
        path = FIRST / rel
        sources[rel] = {"exists": path.is_file()}
        if path.is_file():
            sources[rel]["size_bytes"] = path.stat().st_size
        else:
            missing.append({"kind": "source", "path": rel})

    data = {}
    manifest_rows = []
    manifest_seen = set()
    for rel in data_paths:
        path = FIRST / rel
        stats = scan_root(path, args.max_files_per_root)
        data[rel] = stats
        if not stats["exists"]:
            missing.append({"kind": "local_data", "path": rel})
            continue
        if path.is_file():
            files = [path]
        else:
            files = (p for p in path.rglob("*.json") if "manifest" in p.name.lower())
        for file in files:
            if file.name.lower().find("manifest") < 0:
                continue
            identity = str(file.resolve())
            if identity in manifest_seen:
                continue
            manifest_seen.add(identity)
            size = file.stat().st_size
            too_big = size > args.max_manifest_mb * 1024 * 1024
            manifest_rows.append({
                "path": str(file.relative_to(FIRST)),
                "size_bytes": size,
                "sha256": "" if too_big else sha256_file(file),
                "status": "SKIPPED_SIZE_LIMIT" if too_big else "HASHED",
            })

    entry_status = []
    for entry in registry["entries"]:
        src_ok = sum(sources[p]["exists"] for p in entry["source_paths"])
        data_ok = sum(data[p]["exists"] for p in entry["local_artifact_paths"])
        entry_status.append({
            "id": entry["id"],
            "name": entry["name"],
            "source_files_present": src_ok,
            "source_files_total": len(entry["source_paths"]),
            "data_roots_present": data_ok,
            "data_roots_total": len(entry["local_artifact_paths"]),
            "locally_complete_sources": src_ok == len(entry["source_paths"]),
            "locally_complete_data_roots": data_ok == len(entry["local_artifact_paths"]),
        })

    payload = {
        "status": "B1_LOCAL_EVIDENCE_INVENTORY_ONLY",
        "not_an_experiment_integrity_certificate": True,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "registry_schema": registry["schema_id"],
        "scope": "Existing filesystem paths named by registry v0.1",
        "methodology": "File/directory existence, per-root file counts and bytes, SHA256 of JSON manifest files",
        "exclusions": [
            "No simulation execution",
            "No validation of CSV schema or row counts",
            "No comparison of embedded manifest SHA256 values against files referenced by manifests",
            "No full hash of potentially very large trajectory ledgers",
        ],
        "source_files": sources,
        "data_roots": data,
        "entries": entry_status,
        "manifest_file_count": len(manifest_rows),
        "missing_path_count": len(missing),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "local_inventory_v0_1.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        OUT / "local_manifest_hashes.csv",
        sorted(manifest_rows, key=lambda row: row["path"]),
        ["path", "size_bytes", "sha256", "status"],
    )
    write_csv(
        OUT / "missing_evidence_paths.csv",
        sorted(missing, key=lambda row: (row["kind"], row["path"])),
        ["kind", "path"],
    )
    print("B1_LOCAL_EVIDENCE_INVENTORY_COMPLETE")
    print(f"Registry entries: {len(registry['entries'])}; source files present: {sum(x['exists'] for x in sources.values())}/{len(sources)}")
    print(f"Local data roots present: {sum(x['exists'] for x in data.values())}/{len(data)}; manifest JSON hashed: {sum(x['status']=='HASHED' for x in manifest_rows)}")
    print(f"Missing paths: {len(missing)}; outputs: {OUT}")
    print("NOTE: This is inventory only; frozen prediction and WB hashes are NOT yet independently cross-checked.")


if __name__ == "__main__":
    main()
