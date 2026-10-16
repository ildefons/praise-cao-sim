#!/usr/bin/env python3
"""PRAISE B1 read-only audit of the historical Phase-4 M3 pilot and Stage-B ablation.

Only recomputes metrics from saved comparison tables and verifies manifest
hashes for those tables. No YAFS imports, simulations, method modifications,
or rewriting of original experiment artifacts.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

FIRST = Path(__file__).resolve().parent.parent
R = FIRST / "phase4" / "results"
O = FIRST / "b1" / "local_audit" / "verification_phase4_v0_1"

PILOT = R / "m3_v4_final_evaluation_v1"
POSTHOC = R / "m3_posthoc_stage_b_ablation_v1"
EXPECTED_PILOT = {"M1": 0.1852, "M2": 0.0682, "M3_B1400": 0.03037, "M3_B2000": 0.02755}
EXPECTED_POSTHOC = {
    "TOP1_1400": 0.02878, "UNIFORM14_EQ_1400": 0.05490,
    "WEIGHTED14_EQ_1400": 0.04222, "WEIGHTED14_MINIMAX_1400": 0.03037
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def score(frame, col):
    values = frame[["sigma_whitebox", col]].dropna()
    err = values[col].astype(float).to_numpy() - values["sigma_whitebox"].astype(float).to_numpy()
    if not len(err) or not np.isfinite(err).all():
        raise ValueError(f"No usable data for {col}")
    return {"n_points": len(err), "mae": float(np.abs(err).mean()),
            "rmse": float(np.sqrt((err ** 2).mean())),
            "bias": float(err.mean())}


def main():
    O.mkdir(parents=True, exist_ok=True)
    checks, results = [], []

    def check(section, key, good, detail):
        checks.append({"section": section, "check": key, "result": "PASS" if good else "FAIL", "detail": str(detail)})
        if not good:
            print(f"FAIL [{section}] {key}: {detail}", flush=True)

    def audit(root, label, table, metrics, manifest, cols, expected, stat):
        cmp_path = root / table
        met_path = root / metrics
        man_path = root / manifest
        for path in (cmp_path, met_path, man_path):
            check(label, "file:" + path.name, path.is_file(), path)
        if not all(p.is_file() for p in (cmp_path, met_path, man_path)):
            return
        cmp = pd.read_csv(cmp_path)
        tab = pd.read_csv(met_path)
        man = json.loads(man_path.read_text())
        check(label, "manifest_status", man.get("status") == stat, man.get("status"))
        for key, path in (("comparison_sha256", cmp_path), ("error_metrics_sha256", met_path)):
            if key in man:
                check(label, "hash:" + key, sha(path) == man[key], path)
            elif label == "POSTHOC" and key == "comparison_sha256":
                check(label, "hash:predictions_sha256", sha(path) == man.get("predictions_sha256"), path)
            else:
                check(label, "manifest_field:" + key, False, "missing hash declaration")
        for method, col in cols.items():
            if col not in cmp.columns or "sigma_whitebox" not in cmp.columns:
                check(label, method + ":columns", False, list(cmp.columns))
                continue
            subset = cmp[cmp.horizon.between(60, 240)] if label == "PILOT" else cmp
            row = score(subset, col)
            results.append({"experiment": label, "method": method, **row})
            check(label, method + ":mae_historical", abs(row["mae"] - expected[method]) <= 0.00011,
                  f"computed={row['mae']:.8f}, reported={expected[method]:.5f}")
            if label == "PILOT":
                reported = tab[
                    (tab["window"].astype(str) == "H60_H240") &
                    (tab["summary_level"].astype(str) == "whole_battery") &
                    (tab["summary_key"].astype(str) == "ALL") &
                    (tab["method"].astype(str) == method)
                ]
            else:
                reported = tab[
                    (tab["scope"].astype(str) == "ALL") &
                    (tab["method"].astype(str) == method)
                ]
            check(label, method + ":summary_row", len(reported) == 1, len(reported))
            if len(reported) == 1:
                item = reported.iloc[0]
                for key in ("n_points", "mae", "rmse", "bias"):
                    check(label, method + ":" + key, np.isclose(
                        float(row[key]), float(item[key]), atol=1e-10, rtol=0),
                        f"computed={row[key]} table={item[key]}")

    try:
        audit(PILOT, "PILOT", "m3_v4_final_comparison.csv",
              "m3_v4_final_error_metrics.csv", "m3_v4_final_evaluation_manifest.json",
              {"M1": "sigma_m1", "M2": "sigma_m2_mean",
               "M3_B1400": "sigma_m3_B1400", "M3_B2000": "sigma_m3_B2000"},
              EXPECTED_PILOT, "PHASE4_M3_V4_FINAL_EVALUATION_COMPLETE_V1")
    except Exception as exc:
        check("PILOT", "audit_execution", False, repr(exc))

    try:
        audit(POSTHOC, "POSTHOC", "stage_b_predictions.csv",
              "stage_b_error_metrics.csv", "stage_b_manifest.json",
              {"TOP1_1400": "sigma_top1_1400",
               "UNIFORM14_EQ_1400": "sigma_uniform14_eq1400",
               "WEIGHTED14_EQ_1400": "sigma_weighted14_eq1400",
               "WEIGHTED14_MINIMAX_1400": "sigma_weighted14_minimax1400"},
              EXPECTED_POSTHOC,
              "PHASE4_M3_POSTHOC_STAGE_B_COST_MATCHED_ABLATION_COMPLETE_V1")
    except Exception as exc:
        check("POSTHOC", "audit_execution", False, repr(exc))

    with (O / "verification_checks.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "check", "result", "detail"])
        writer.writeheader()
        writer.writerows(checks)
    pd.DataFrame(results, columns=["experiment", "method", "n_points", "mae", "rmse", "bias"]).to_csv(
        O / "recomputed_metrics.csv", index=False)
    summary = {"status": "B1_PHASE4_PILOT_VERIFICATION_V0_1",
               "simulation_executed": False, "original_evidence_modified": False,
               "passes": sum(x["result"] == "PASS" for x in checks),
               "failures": sum(x["result"] == "FAIL" for x in checks),
               "note": "Limited to saved comparison tables; does not reproduce from raw YAFS ledgers."}
    (O / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("B1_PHASE4_PILOT_VERIFICATION_COMPLETE", summary)
    if results:
        print(pd.DataFrame(results).to_string(index=False))


if __name__ == "__main__":
    main()
