#!/usr/bin/env python3
"""PRAISE B1 read-only local simulator/dependency/provenance snapshot.

Runs NO YAFS simulation, does NOT import yafs application/core or run pytest.
Fingerprints installed source files and checks the frozen Phase5 manifest
prediction-to-WB boundary using archived JSON only. All outputs live under B1.
"""
from __future__ import annotations
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path

FIRST = Path(__file__).resolve().parent.parent
HERE = FIRST / "phase5"
OUT = FIRST / "b1" / "local_audit" / "runtime_provenance_v0_1"
PRED = HERE / "results" / "04_prediction_v3b_fullsupport"
WB = HERE / "results" / "05_final_wb_v3b_fullsupport"
EVAL = HERE / "results" / "06_evaluation_v3b_fullsupport"
PRED_GLOBAL = PRED / "phase5_v3b_fullsupport_global_prediction_freeze_manifest.json"
WB_GLOBAL = WB / "phase5_v3b_fullsupport_final_wb_freeze_manifest.json"
EVAL_GLOBAL = EVAL / "phase5_v3b_fullsupport_deterministic_evaluation_manifest.json"
SMOKES = [
    HERE / "smoke" / "phase5_v2" / "phase5_v2_smoke_manifest.json",
    HERE / "smoke" / "phase5_v2_completion" / "phase5_v2_mandatory_smoke_completion_manifest.json",
    HERE / "smoke" / "v3b_graph_adapter" / "phase5_v3b_graph_adapter_smoke_manifest.json",
    HERE / "smoke" / "v3b_fullsupport_graph_adapter" /
    "phase5_v3b_fullsupport_graph_adapter_smoke_manifest.json",
]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def git_head(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=4
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def parse_dt(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    def check(category, key, result, detail=""):
        checks.append({"category": category, "check": key, "result": result, "detail": str(detail)})
        if result == "FAIL":
            print("FAIL", category, key, detail, flush=True)

    versions = {}
    for dist in ("numpy", "pandas", "simpy", "networkx", "optuna", "scipy", "pytest"):
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            versions[dist] = None

    installed = {"python": platform.python_version(), "packages": versions}
    spec = importlib.util.find_spec("yafs")
    if spec is None or not spec.submodule_search_locations:
        check("runtime", "yafs_package_located", "WARN", "Installed yafs package not import-resolvable; no execution attempted")
    else:
        yafs_dir = Path(next(iter(spec.submodule_search_locations))).resolve()
        installed["yafs_package_root"] = str(yafs_dir)
        installed["yafs_ancestor_git_head"] = git_head(yafs_dir)
        signatures = {
            "application.py": ["add_service_module_praise", "set_composition_output_praise", "depends_on"],
            "core.py": ["composition_controllers", "composition_path", "__add_composition_controller"],
            "stats.py": [],
            "distribution.py": ["gamma_distribution"],
        }
        installed["yafs_source"] = {}
        for file, keywords in signatures.items():
            path = yafs_dir / file
            if not path.is_file():
                check("runtime", "exists:" + file, "FAIL", str(path))
                continue
            body = path.read_text(encoding="utf8")
            found = [k for k in keywords if k in body]
            installed["yafs_source"][file] = {
                "path": str(path), "sha256": sha(path),
                "bytes": path.stat().st_size, "markers_present": found,
            }
            check("runtime", "exists:" + file, "PASS", path)
            check("runtime", "features:" + file,
                  "PASS" if len(found) == len(keywords) else "FAIL",
                  f"found {len(found)}/{len(keywords)} expected static markers")
        check("runtime", "simulator_revision_explicitly_pinned",
              "INFO" if installed.get("yafs_ancestor_git_head") else "WARN",
              "Current installed yafs git HEAD is recorded when available; historical execution revision must still be checked against archived run environment")

    installed["praise_repo_git_head_now"] = git_head(FIRST.parent)
    def load(path, cat):
        if not path.is_file():
            check(cat, "exists:" + path.name, "FAIL", path)
            return None
        try:
            data = json.loads(path.read_text())
        except Exception as exc:
            check(cat, "parse:" + path.name, "FAIL", repr(exc))
            return None
        check(cat, "exists:" + path.name, "PASS", path)
        return data

    global_pred = load(PRED_GLOBAL, "prediction_freeze")
    pred_cells, excluded = [], []
    pred_finish, wb_begin = [], []
    if global_pred is not None:
        check("prediction_freeze", "correct_status",
              "PASS" if global_pred.get("status") == "FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE" else "FAIL",
              global_pred.get("status"))
        check("prediction_freeze", "completed_before_wb_flag",
              "PASS" if global_pred.get("complete") is True and global_pred.get("final_WB_read") is False else "FAIL")
        pred_cells = sorted(map(str, global_pred.get("prediction_frozen_cells", [])))
        excluded = sorted(map(str, global_pred.get("gate_failed_step0_cells", [])))
        check("prediction_freeze", "12_plus_4_cells",
              "PASS" if len(pred_cells) == 12 and len(excluded) == 4
              and not set(pred_cells).intersection(excluded) else "FAIL",
              f"pred={len(pred_cells)} excluded={len(excluded)}")
        hashes = global_pred.get("prediction_manifest_sha256", {})
        check("prediction_freeze", "12_hash_coverage",
              "PASS" if set(hashes) == set(pred_cells) else "FAIL",
              f"hash_keys={len(hashes)}")
        for cell in pred_cells:
            path = PRED / cell / "prediction_manifest.json"
            p = load(path, "prediction_cell")
            if p is None:
                continue
            check("prediction_cell", f"{cell}:status",
                  "PASS" if p.get("status") == "FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION" else "FAIL")
            check("prediction_cell", f"{cell}:hash",
                  "PASS" if sha(path) == hashes.get(cell) else "FAIL")
            if p.get("started_utc"):
                pred_finish.append(parse_dt(p.get("completed_utc")))

    wb_global = load(WB_GLOBAL, "wb_freeze")
    if wb_global:
        wb_cells = sorted(map(str, wb_global.get("eligible_final_wb_cells", [])))
        check("wb_freeze", "wb_same_12_cells",
              "PASS" if wb_cells == pred_cells else "FAIL",
              f"wb={len(wb_cells)}, prediction={len(pred_cells)}")
        for cell in wb_cells:
            f = WB / cell / "final_wb_manifest.json"
            p = load(f, "wb_cell")
            if p is None:
                continue
            check("wb_cell", f"{cell}:status",
                  "PASS" if p.get("status") == "FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_CELL" else "FAIL")
            check("wb_cell", f"{cell}:prediction_global_hash",
                  "PASS" if p.get("global_prediction_freeze_sha256") == sha(PRED_GLOBAL) else "FAIL")
            if parse_dt(p.get("started_utc")):
                wb_begin.append(parse_dt(p.get("started_utc")))

    if global_pred:
        pass_time = parse_dt(global_pred.get("completed_utc"))
        if pass_time and wb_begin:
            check("chronology", "global_pred_freeze_precedes_wb",
                  "PASS" if pass_time <= min(wb_begin) else "FAIL",
                  f"pred_global={pass_time}, earliest_wb={min(wb_begin)}")
        else:
            check("chronology", "global_pred_freeze_precedes_wb",
                  "WARN", "Timestamp field unavailable: hash-chain checks still apply")

    eval_global = load(EVAL_GLOBAL, "evaluation")
    if eval_global:
        check("evaluation", "status",
              "PASS" if eval_global.get("status") ==
              "FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION" else "FAIL",
              eval_global.get("status"))

    smoke_records = []
    for path in SMOKES:
        data = None
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                check("smoke", "parse:" + path.name, "FAIL", repr(exc))
        smoke_records.append({
            "path": str(path),
            "present": data is not None,
            "status": data.get("status") if data else None,
            "scientific_evidence": data.get("scientific_evidence") if data else None,
            "completed_utc": data.get("completed_utc") if data else None,
            "sha256": sha(path) if data else None,
        })
        check("smoke", "archive:" + path.name, "INFO" if data else "WARN",
              "present and recorded" if data else "local manifest not found; reported engineering completion remains unverified here")
        if data and data.get("scientific_evidence") is not False:
            check("smoke", "non_scientific:" + path.name, "FAIL",
                  "Scientific-evidence flag is not False")
        elif data:
            check("smoke", "non_scientific:" + path.name, "PASS")

    installed["smoke_archives"] = smoke_records
    installed["stage_manifest_paths"] = {
        "global_pred": str(PRED_GLOBAL),
        "global_WB": str(WB_GLOBAL),
        "evaluation": str(EVAL_GLOBAL),
    }
    installed["limitations"] = [
        "Installed runtime NOW may differ from the runtime used in October 6-8 frozen scientific runs",
        "Only content of current installed package source is fingerprinted; no local simulations/tests run",
        "Historical YAFS dependency git SHA is not recovered unless recorded externally",
        "Selected manifest hash chain and stage ordering are checked, not full transitive hashes or raw ledger semantics",
    ]
    (OUT / "runtime_fingerprint.json").write_text(json.dumps(installed, indent=2) + "\n")
    (OUT / "provenance_checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    totals = {k: sum(c["result"] == k for c in checks) for k in ("PASS", "FAIL", "WARN", "INFO")}
    summary = {"status": "B1_RUNTIME_PROVENANCE_V0_1_COMPLETE",
               "no_simulations": True, "scientific_source_files_modified": False,
               "check_counts": totals, "n_predicted": len(pred_cells),
               "n_excluded": len(excluded),
               "no_historical_aicon_pin_claimed": True}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("B1_RUNTIME_PROVENANCE_AUDIT_COMPLETE", summary)
    print("Audit directory:", OUT)


if __name__ == "__main__":
    main()
