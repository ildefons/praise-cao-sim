#!/usr/bin/env python3
"""Collect existing small source tables for PRAISE B1 manuscript display audit.

Read-only for frozen research data; copies specified existing CSVs and source
manifests into a new B1 audit ZIP. Does NOT run any experiments or rewrite
scientific evidence. Missing files are recorded explicitly.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

FIRST = Path(__file__).resolve().parent.parent
OUT = FIRST / "b1" / "local_audit" / "display_sources_v0_1"
PHASE4 = FIRST / "phase4"
NAMES = [
    "m3_v4_final_evaluation_v1/m3_v4_final_comparison.csv",
    "m3_v4_final_evaluation_v1/m3_v4_final_error_metrics.csv",
    "m3_v4_final_evaluation_v1/m3_v4_final_regime_means_H60_H240.csv",
    "m3_v4_final_evaluation_v1/m3_v4_final_evaluation_manifest.json",
    "m3_top3_support_validation_v1/m3_top3_support_predictions.csv",
    "m3_top3_support_validation_v1/m3_top3_error_metrics.csv",
    "m3_top3_support_validation_v1/m3_top3_decision_metrics.csv",
    "m3_top3_support_validation_v1/m3_top3_mc_width_summary.csv",
    "m3_top3_support_validation_v1/m3_top3_support_manifest.json",
    "m3_posthoc_stage_b_ablation_v1/stage_b_predictions.csv",
    "m3_posthoc_stage_b_ablation_v1/stage_b_error_metrics.csv",
    "m3_posthoc_stage_b_ablation_v1/stage_b_decision_metrics.csv",
    "m3_posthoc_stage_b_ablation_v1/stage_b_bootstrap_summary.csv",
    "m3_posthoc_stage_b_ablation_v1/stage_b_manifest.json",
    "m3_v4_wb_reference_bootstrap_v1/wb_reference_bootstrap_summary.csv",
    "m3_v4_wb_reference_bootstrap_v1/wb_reference_bootstrap_manifest.json",
    "m1_vs_top1_public_i1_audit_v1/m1_vs_top1_parameters.csv",
    "m1_vs_top1_public_i1_audit_v1/m1_vs_top1_public_i1_fit.csv",
    "pilot_evidence_strengthening_v1/hidden_theta_comparison.csv",
    "pilot_evidence_strengthening_v1/signed_bias_by_regime.csv",
    "m3_posthoc_mechanism_audit_v1/truth_candidate_audit.csv",
    "m3_posthoc_mechanism_audit_v1/posthoc_mechanism_audit_manifest.json",
]
MAX_BYTES_PER_FILE = 8 * 1024 * 1024

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    path_zip = OUT / "praise_b1_display_source_evidence_v0_1.zip"
    with ZipFile(path_zip, "w", ZIP_DEFLATED, compresslevel=6) as z:
        for rel in NAMES:
            src = PHASE4 / "results" / rel
            rec = {"path": "phase4/results/" + rel,
                   "status": "MISSING", "bytes": "", "sha256": ""}
            if src.is_file():
                n = src.stat().st_size
                rec["bytes"] = n
                if n > MAX_BYTES_PER_FILE:
                    rec["status"] = "SKIPPED_TOO_LARGE"
                else:
                    rec["status"] = "INCLUDED"
                    rec["sha256"] = sha256(src)
                    z.write(src, arcname=rec["path"])
            report.append(rec)
        metadata = {
            "status": "B1_DISPLAY_ARCHIVE_COLLECTION_V0_1",
            "not_full_simulation_replay": True,
            "frozen_data_unchanged": True,
            "included": sum(x["status"]=="INCLUDED" for x in report),
            "missing": sum(x["status"]=="MISSING" for x in report),
            "skipped": sum(x["status"]=="SKIPPED_TOO_LARGE" for x in report),
            "files": report,
        }
        z.writestr("b1_display_archive_manifest.json",
                   json.dumps(metadata, indent=2) + "\n")
    with (OUT / "source_file_status.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path","status","bytes","sha256"])
        w.writeheader()
        w.writerows(report)
    print("B1_DISPLAY_EVIDENCE_COLLECTION_COMPLETE")
    print(f"{metadata['included']} INCLUDED, {metadata['missing']} MISSING, {metadata['skipped']} SKIPPED_TOO_LARGE")
    print("Archive:", path_zip)
    print("No experiments run; no source file modified.")

if __name__ == "__main__":
    main()
