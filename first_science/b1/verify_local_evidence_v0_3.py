#!/usr/bin/env python3
"""B1 v0.3 read-only evidence verification (no YAFS, simulations or frozen edits).

Rehashes the prior inventory's manifest snapshots, checks selected manifest
output hashes below a size cap, and independently recomputes saved evaluation
metrics for Phase5, Phase6, the P2 induced pilot, and P2 truth diagnostics.
Only writes to first_science/b1/local_audit/verification_v0_2/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import pandas as pd
import numpy as np

FIRST = Path(__file__).resolve().parent.parent
HERE = FIRST / "b1"
AUDIT = HERE / "local_audit"
OUT = AUDIT / "verification_v0_3"
P5 = FIRST / "phase5" / "results"
P6 = FIRST / "phase6" / "results"
REGISTRY = HERE / "evidence_registry_v0_1.json"
PHASE5 = P5 / "06_evaluation_v3b_fullsupport"
PHASE6 = P6 / "38_i2b_v4_six_way_evaluation"
P2 = P5 / "i1_m3_p2_induced_pilot" / "P2__G_PAR"
TOL = 1e-6


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metrics(frame, method_col, method_val, pred_col="sigma_hat", wb_col="sigma_wb"):
    part = frame.loc[frame[method_col].astype(str).eq(method_val)]
    errors = part[pred_col].to_numpy(dtype=float) - part[wb_col].to_numpy(dtype=float)
    if not len(errors) or not np.isfinite(errors).all():
        raise ValueError(f"Missing or nonfinite scoring values for {method_val}")
    return {"method": method_val, "n_points": len(errors),
            "mae": float(np.abs(errors).mean()),
            "rmse": float(np.sqrt((errors**2).mean())),
            "bias": float(errors.mean())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-output-mb", type=float, default=32.0,
                    help="Maximum per-file size for checking manifest-declared output SHA256")
    args = ap.parse_args()
    if args.max_output_mb <= 0:
        ap.error("--max-output-mb must be positive")

    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    summaries = {}
    registry = json.loads(REGISTRY.read_text())
    entries = {x["id"]: x for x in registry["entries"]}

    def record(scope, check, result, detail):
        checks.append({"scope": scope, "check": check, "result": result, "detail": str(detail)})
        if result == "FAIL":
            print(f"FAIL {scope} {check}: {detail}", flush=True)

    def require(condition, scope, check, detail=""):
        record(scope, check, "PASS" if condition else "FAIL", detail)

    def read_csv(path, cols=()):
        if not path.is_file():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        miss = set(cols) - set(df.columns)
        if miss:
            raise ValueError(f"{path}: missing columns {sorted(miss)}")
        return df

    # Verify that the snapshot of 233 manifest hashes still matches current files.
    invfile = AUDIT / "local_manifest_hashes.csv"
    if invfile.is_file():
        old = read_csv(invfile, ("path", "sha256", "status"))
        for row in old.itertuples(index=False):
            path = FIRST / str(row.path)
            if str(row.status) != "HASHED":
                record("INVENTORY", str(row.path), "SKIP", "Previous inventory did not hash this file")
            elif not path.is_file():
                record("INVENTORY", str(row.path), "FAIL", "Manifest missing since inventory")
            else:
                require(digest(path) == str(row.sha256), "INVENTORY",
                        str(row.path), "SHA256 versus original snapshot")
    else:
        record("INVENTORY", "snapshot", "FAIL", "Missing local_manifest_hashes.csv")

    # Verify the output files referenced by high-priority frozen manifests.
    # This intentionally avoids scanning potentially massive request ledgers.
    selected_manifests = [
        P5 / "02_step0/phase5_step0_eligibility_manifest.json",
        P5 / "04_prediction_v3b_fullsupport/phase5_v3b_fullsupport_global_prediction_freeze_manifest.json",
        P5 / "05_final_wb_v3b_fullsupport/phase5_v3b_fullsupport_final_wb_freeze_manifest.json",
        PHASE5 / "phase5_v3b_fullsupport_deterministic_evaluation_manifest.json",
        PHASE5 / "bootstrap_reference/phase5_v3b_fullsupport_wb_reference_bootstrap_manifest.json",
        PHASE6 / "evaluation_manifest.json",
        P2 / "m1_m2_native_comparison/evaluation/comparison_manifest.json",
        P5 / "p2_true_parameter_i1_fidelity_audit/manifest.json",
        P5 / "p2_bounded_reconstruction_diagnostic/manifest.json",
    ]
    for manifest in selected_manifests:
        key = manifest.relative_to(FIRST).as_posix()
        if not manifest.is_file():
            record("MANIFEST", key, "FAIL", "Missing")
            continue
        data = json.loads(manifest.read_text())
        status = data.get("status", "UNSPECIFIED")
        record("MANIFEST_STATUS", key, "INFO", status)
        expected_status = {
            "phase5_v3b_fullsupport_global_prediction_freeze_manifest.json":
                "FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE",
            "phase5_v3b_fullsupport_final_wb_freeze_manifest.json":
                "FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY",
            "phase5_v3b_fullsupport_deterministic_evaluation_manifest.json":
                "FROZEN_PHASE5_V3B_FULLSUPPORT_DETERMINISTIC_EVALUATION",
            "phase5_v3b_fullsupport_wb_reference_bootstrap_manifest.json":
                "FROZEN_PHASE5_V3B_FULLSUPPORT_WB_REFERENCE_BOOTSTRAP_COMPLETE",
            "evaluation_manifest.json":
                "PHASE6_I2BV4_SIX_WAY_MATCHED_EVALUATION_COMPLETE",
            "comparison_manifest.json":
                "RETROSPECTIVE_P2_G_PAR_M1_M2_M3_NATIVE_BUDGET_COMPARISON_COMPLETE"
        }.get(manifest.name)
        if expected_status is not None:
            require(status == expected_status, "MANIFEST_STATUS", key + ":expected", status)
        outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
        mappings = [
            ("output_hashes_sha256", data.get("output_hashes_sha256")),
            ("output_sha256", data.get("output_sha256")),
            ("outputs_sha256", data.get("outputs_sha256")),
            ("files_sha256", data.get("files_sha256"))
        ]
        for section, hashes in mappings:
            if not isinstance(hashes, dict):
                continue
            for name, expected in hashes.items():
                if not isinstance(expected, str) or len(expected) != 64:
                    record("OUTPUT_HASH", f"{key}:{section}:{name}", "SKIP", "Non-SHA256 value")
                    continue
                # When the manifest has named output paths, use those paths.
                locations = []
                if name in outputs and isinstance(outputs[name], str):
                    locations.append(Path(outputs[name]))
                locations.extend([manifest.parent / name, FIRST / name, FIRST.parent / name, FIRST / "phase5" / name, FIRST / "phase6" / name])
                chosen = None
                for loc in locations:
                    candidates = [loc] if loc.is_absolute() else [FIRST.parent / loc, FIRST / loc, manifest.parent / loc]
                    for p in candidates:
                        if p.is_file() and p.resolve().is_relative_to(FIRST.resolve()):
                            chosen = p
                            break
                    if chosen is not None:
                        break
                label = f"{key}:{section}:{name}"
                if chosen is None:
                    record("OUTPUT_HASH", label, "SKIP", "Cannot resolve declared output path (may be historical absolute path)")
                elif chosen.stat().st_size > args.max_output_mb * (1024**2):
                    record("OUTPUT_HASH", label, "SKIP", f"Size cap {args.max_output_mb:g} MB")
                else:
                    require(digest(chosen) == expected, "OUTPUT_HASH", label, chosen.relative_to(FIRST))

    # Reconstruction evidence is essential but omitted from the initial 17
    # registered result roots. Record presence explicitly rather than
    # incorrectly treating initial directory coverage as exhaustive.
    for rel in ("phase3/results", "phase5/results/03_reconstruction_v3/P2",
                "phase5/results/03_reconstruction_v3b/P2"):
        path = FIRST / rel
        require(path.is_dir(), "REGISTRY_COVERAGE", rel, "Additional source root required for full B1 provenance")

    # Phase 5. Recompute each metric from the actual frozen pointwise join,
    # without using methods or outcomes during calculation.
    try:
        joined = read_csv(PHASE5 / "pointwise_primary_joined.csv",
                          ("method_id", "status", "sigma_hat", "sigma_wb", "H",
                           "physical_cell_id", "query_id", "regime"))
        reported = read_csv(PHASE5 / "primary_metrics.csv",
                            ("method_id", "scope", "scope_value", "MAE",
                             "RMSE", "signed_bias", "n_points"))
        wb_cells = set(joined["physical_cell_id"].astype(str).unique())
        expect_cells = {f"{world}__{graph}" for world in ("P1", "P3", "P4")
                        for graph in ("G_PAR", "G_SEQ", "G_SEQPAR", "G_PARSEQ")}
        require(wb_cells == expect_cells, "PHASE5", "eligible_cells", f"{len(wb_cells)} observed")
        require(not any(x.startswith("P2__") for x in wb_cells),
                "PHASE5", "P2_undisturbed_exclusion")
        require(joined["H"].between(60., 240.).all(), "PHASE5", "primary_horizons")
        metrics_out = []
        for method in ("M0", "M1", "M2", "M3_FULL343"):
            df = joined.loc[(joined["method_id"] == method) &
                            (joined["status"] == "PREDICTED") &
                            joined["sigma_hat"].notna()]
            row = metrics(df, "method_id", method)
            metrics_out.append(row)
            expected = entries["E06"]["primary_results"][method]
            result = reported.loc[(reported.method_id == method) &
                                  (reported.scope == "ALL") &
                                  (reported.scope_value == "ALL")]
            require(len(result) == 1, "PHASE5", method + "_summary_present")
            for field, key in (("mae", "MAE"), ("rmse", "RMSE"), ("bias", "signed_bias")):
                require(abs(row[field] - expected[field]) <= TOL, "PHASE5",
                        method + "_" + field + "_registry", f"computed={row[field]:.9f} registered={expected[field]:.9f}")
                if len(result) == 1:
                    require(abs(row[field] - float(result.iloc[0][key])) <= 1e-10,
                            "PHASE5", method + "_" + field + "_frozen_csv")
            require(row["n_points"] == expected["points"], "PHASE5", method + "_points", row["n_points"])
            if method != "M0":
                cell_count = df.groupby("physical_cell_id").size()
                require(len(cell_count) == 12 and cell_count.eq(555).all(),
                        "PHASE5", method + "_cell_grid", cell_count.to_dict())
        summaries["phase5_metrics"] = metrics_out
        agg = pd.DataFrame(metrics_out)
        agg.to_csv(OUT / "recomputed_phase5_metrics.csv", index=False)
    except Exception as exc:
        record("PHASE5", "recomputation", "FAIL", repr(exc))

    # Phase 6. Compare six-way saved joined evidence with separately archived table.
    try:
        joined = read_csv(PHASE6 / "pointwise_joined.csv",
                          ("method", "sigma_hat", "sigma_wb", "H", "query_id"))
        reported = read_csv(PHASE6 / "metrics.csv",
                            ("method", "scope", "mae", "rmse", "bias", "n_points"))
        result = []
        for method, expected_metrics in entries["E07"]["primary_results"].items():
            row = metrics(joined, "method", method)
            result.append(row)
            summary = reported.loc[(reported.method == method) & (reported.scope == "ALL")]
            require(row["n_points"] == 555 and len(summary) == 1,
                    "PHASE6", method + "_grid_and_summary", row["n_points"])
            for field in ("mae", "rmse", "bias"):
                if field in expected_metrics:
                    require(abs(row[field] - expected_metrics[field]) <= TOL,
                            "PHASE6", method + "_" + field + "_registry",
                            f"computed={row[field]:.9f} registered={expected_metrics[field]:.9f}")
                if len(summary) == 1:
                    require(abs(row[field] - float(summary.iloc[0][field])) <= 1e-10,
                            "PHASE6", method + "_" + field + "_frozen_csv")
            sub = joined.loc[joined.method.eq(method)]
            require(sub[["query_id", "H"]].drop_duplicates().shape[0] == 555,
                    "PHASE6", method + "_unique_query_h")
        summaries["phase6_metrics"] = result
        pd.DataFrame(result).to_csv(OUT / "recomputed_phase6_metrics.csv", index=False)
    except Exception as exc:
        record("PHASE6", "recomputation", "FAIL", repr(exc))

    # P2 induced-region comparison, not a repaired Phase5 P2 cell.
    try:
        root = P2 / "m1_m2_native_comparison/evaluation"
        joined = read_csv(root / "matched_survival_curves.csv",
                          ("method", "sigma_hat", "sigma_wb", "H", "query_id"))
        reported = read_csv(root / "matched_rmse_summary.csv",
                            ("method", "mae", "rmse", "bias", "n_points"))
        subset = joined.loc[joined.H >= 60.]
        result = []
        for method, expected in entries["E09"]["primary_results"].items():
            # Registry names encode the reconstruction version, while saved
            # evaluation uses stable M1/M2/M3_FULL343 method labels.
            evaluation_method = {"M1_V3B": "M1", "M2_V3B": "M2",
                                 "M3_FULL343_V3B": "M3_FULL343"}[method]
            row = metrics(subset, "method", evaluation_method)
            row["registry_method"] = method
            result.append(row)
            s = reported[reported.method.eq(evaluation_method)]
            require(subset.loc[subset.method.eq(evaluation_method), ["query_id", "H"]].drop_duplicates().shape[0] == 185,
                    "P2_INDUCED", method + "_unique_query_h")
            require(len(s) == 1 and row["n_points"] == 185,
                    "P2_INDUCED", method + "_grid_and_summary", row["n_points"])
            for field in ("mae", "rmse", "bias"):
                require(abs(row[field] - expected[field]) <= TOL,
                        "P2_INDUCED", method + "_" + field + "_registry",
                        f"computed={row[field]:.9f} registered={expected[field]:.9f}")
                if len(s) == 1:
                    require(abs(row[field] - float(s.iloc[0][field])) <= 1e-10,
                            "P2_INDUCED", method + "_" + field + "_frozen_csv")
        summaries["p2_induced_metrics"] = result
        pd.DataFrame(result).to_csv(OUT / "recomputed_p2_induced_metrics.csv", index=False)
    except Exception as exc:
        record("P2_INDUCED", "recomputation", "FAIL", repr(exc))

    # P2 true-parameter audit: compare six data rows with numerical registry.
    try:
        truth = read_csv(P5 / "p2_true_parameter_i1_fidelity_audit/true_parameter_i1_fidelity_summary.csv",
                         ("provider", "bank", "true_rmse", "m1_selected_rmse",
                          "truth_inside_frozen_search_bounds"))
        require(len(truth) == 6, "P2_TRUTH", "six_provider_bank_rows", len(truth))
        for provider in ("ProviderA", "ProviderB", "ProviderC"):
            meta = entries["E11"]["primary_results"][provider]
            for bank in ("rescore", "replay"):
                row = truth.loc[truth.provider.eq(provider) & truth.bank.eq(bank)]
                require(len(row) == 1, "P2_TRUTH", provider + "_" + bank + "_present")
                if len(row) != 1:
                    continue
                for key, col in (("truth_rmse_" + bank, "true_rmse"),
                                 ("best_selected_rmse_" + bank, "m1_selected_rmse")):
                    require(abs(float(row.iloc[0][col]) - meta[key]) <= TOL,
                            "P2_TRUTH", provider + "_" + bank + "_" + col)
                require(bool(row.iloc[0]["truth_inside_frozen_search_bounds"]),
                        "P2_TRUTH", provider + "_" + bank + "_inside_bounds")
        sensitivity = read_csv(P5 / "p2_bounded_reconstruction_diagnostic/truth_neighborhood_sensitivity.csv",
                               ("provider", "variant", "bank", "rmse"))
        require(len(sensitivity) == 42 and sensitivity[["provider", "variant", "bank"]].duplicated().sum() == 0,
                "P2_SENSITIVITY", "42_unique_configurations", len(sensitivity))
        summaries["p2_sensitivity_range"] = sensitivity.groupby("variant")["rmse"].agg(["min", "max"]).round(6).to_dict("index")
    except Exception as exc:
        record("P2_TRUTH", "recomputation", "FAIL", repr(exc))

    summary = {
        "status": "B1_VERIFICATION_V0_3_COMPLETE",
        "read_only": True,
        "not_a_full_frozen_evidence_certificate": True,
        "phases_checked": ["phase5", "phase6", "P2_induced", "P2_truth_sensitivity"],
        "checks_by_result": {name: sum(x["result"] == name for x in checks)
                             for name in ("PASS", "FAIL", "INFO", "SKIP")},
        "results": summaries,
        "limitations": [
            "Selected output hashes capped by file size; full ledgers not rehashed.",
            "Does not independently reconstruct sigma curves from raw request/trajectory ledgers.",
            "Phase4 pilot and simulation-code equivalence not yet independently checked.",
            "Phase6 checkpoint is stale; verified evaluation CSVs, not checkpoint status, are prioritized.",
        ],
    }
    with (OUT / "verification_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    with (OUT / "verification_checks.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, ["scope", "check", "result", "detail"])
        writer.writeheader()
        writer.writerows(checks)
    print("B1_EVIDENCE_VERIFICATION_V0_3_COMPLETE")
    print("Counts:", summary["checks_by_result"])
    for name in ("phase5_metrics", "phase6_metrics", "p2_induced_metrics"):
        if name in summaries:
            print(name + "\n" + pd.DataFrame(summaries[name]).to_string(index=False))
    print("Output:", OUT)
    if summary["checks_by_result"]["FAIL"]:
        print("ACTION: review FAIL rows before upgrading registry to v1.0")


if __name__ == "__main__":
    main()
