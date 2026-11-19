#!/usr/bin/env python3
"""B0001 seven-method deterministic prediction-accuracy evaluation.

--check: verify the pre-WB blind freeze, the independently supplied post-WB
         mechanical audit, and every reference/prediction input SHA-256.
         Does not read reference curve values, compute errors or write files.
--run:   repeat the same gates, then score exactly 7 methods x 12 cells.
         Produces deterministic CSVs and a new immutable result manifest.

This stage is NOT a selection-policy replay and NOT a trajectory-level
reference-uncertainty bootstrap. No simulator is imported or run. All methods,
the evaluation window H=60..240 and the primary equal-cell MAE objective were
fixed in the pre-reference B1 and Phase5 protocols. Predictions stay frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
PHASE5 = HERE.parents[1] / "phase5"
METHODS = (
    "M1", "M2", "M3_FULL343", "ORIGINAL_TOP14_B1400",
    "ORIGINAL_TOP1_B1400", "FIXED_CV_TOP14", "FIXED_CV_TOP1",
)
ORIGINAL = {
    "M1": "m1_predictions.csv",
    "M2": "m2_predictions.csv",
    "M3_FULL343": "m3_predictions_full343_and_nested.csv",
}
ROLES = ("P1", "P3", "P4")
GRAPHS = ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")
CELLS = tuple(f"{role}__{graph}" for role in ROLES for graph in GRAPHS)
KEYS = (
    "query_id", "provider_world_id", "graph_id", "rho_label",
    "rho", "regime", "H",
)
HORIZONS = tuple(range(0, 241, 5))
PRIMARY_HORIZONS = tuple(range(60, 241, 5))
REFERENCE_N = 1000
N_QUERIES = 15
N_RAW = N_QUERIES * len(HORIZONS)             # 735
N_PRIMARY = N_QUERIES * len(PRIMARY_HORIZONS)  # 555
STATUS = "B0001_SEVEN_METHOD_12_CELL_ACCURACY_EVALUATION_V1_FROZEN"
AUDIT_STATUS = "B0001_FINAL_WB_SEVEN_ARM_POSTRUN_MECHANICAL_AUDIT_V2_PASS"
REF_STATUS = "B0001_FINAL_WB_N1000_12_CELL_FROZEN_EVALUATION_NOT_YET_AUDITED"
TOL = 1e-12

# Verified against independently uploaded audit JSON, before evaluating the
# seven methods. Pin its exact byte sequence to prevent a substituted audit.
EXTERNAL_AUDIT_SHA256 = (
    "211e5b75cef98bdc4232c4dc74c532705c936269a64513f6e5e9afbeffcca4e4"
)


def require(condition: object, message: str) -> None:
    if not bool(condition):
        raise RuntimeError("B0001 SEVEN ACCURACY GATE: " + message)


def sha(path: Path) -> str:
    require(path.is_file(), "missing file: " + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    require(path.is_file(), "missing JSON: " + str(path))
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def reference_file(a: argparse.Namespace, cell: str) -> Path:
    return a.reference / cell / "final_wb_curves.csv"


def prediction_file(a: argparse.Namespace, method: str, cell: str) -> Path:
    if method in ORIGINAL:
        return a.graph / "scientific" / cell / ORIGINAL[method]
    return a.four_arm / "scientific" / method / cell / "predictions.csv"


def check_output_path(a: argparse.Namespace) -> None:
    require(not a.out.exists(), "refusing existing output directory: " + str(a.out))
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven_arm", "four_arm", "refaudit",
    ):
        source = getattr(a, name)
        require(
            a.out != source and a.out not in source.parents
            and source not in a.out.parents,
            "output directory overlaps frozen input: " + name,
        )


def preflight(a: argparse.Namespace) -> dict:
    """Only metadata and file hashes; no curve contents or model errors."""
    import b0001_seven_arm_blind_reference_guard_v1 as guard
    import preflight_b0001_final_wb_v1 as wb_gate

    check_output_path(a)
    audit_path = a.refaudit / "b0001_final_reference_seven_arm_postrun_audit_v2.json"
    require(sha(audit_path) == EXTERNAL_AUDIT_SHA256,
            "mechanical audit differs from independently uploaded record")
    audit = read_json(audit_path)
    require(
        audit.get("status") == AUDIT_STATUS
        and audit.get("evaluation_authorized") is True
        and audit.get("seven_arm_postrun_equals_pre_WB_authorization") is True
        and audit.get("mechanical_audit_only") is True
        and audit.get("n_reference_cells") == 12
        and audit.get("n_reference_trajectories") == 12000
        and audit.get("n_reference_curve_points") == 8820
        and audit.get("seven_blind_algorithms_unchanged") == 7
        and audit.get("method_condition_predictions_unchanged") == 84,
        "independent seven-arm reference audit not complete",
    )
    auth_path = a.authorization / "b0001_final_wb_authorization_freeze.json"
    auth = read_json(auth_path)
    ref_freeze_path = a.reference / "b0001_final_wb_global_freeze.json"
    reference = read_json(ref_freeze_path)
    require(
        sha(ref_freeze_path) == audit["reference_global_freeze_sha256"]
        and sha(auth_path) == audit["final_reference_authorization_sha256"]
        and reference["status"] == REF_STATUS
        and reference["reference_trajectories"] == 12000
        and reference["evaluation_unlocked"] is False
        and reference["seven_method_plan_b_complete"] is False
        and reference["final_reference_authorization_sha256"] == sha(auth_path)
        and reference["postrun_prediction_audit_sha256"] ==
        audit["blind_postrun_audit_sha256"] == auth["postrun_integrity_audit_sha256"],
        "reference/authorization freeze chain differs from mechanical audit",
    )
    require(auth["status"] == wb_gate.STATUS
            and auth["analysis_authorized"] is False
            and auth["all_seven_algorithms_blind_before_reference"] is True,
            "pre-reference authorization changed")
    require(set(reference["cell_manifest_sha256"]) == set(CELLS),
            "not exactly the twelve authorized reference cells")

    evidence = guard.verify(
        original_audit=a.audit, graph=a.graph, four_arm=a.four_arm,
        seven_arm=a.seven_arm, wb_seed_start=wb_gate.WB_START,
        wb_seed_n=wb_gate.WB_N, deep=False,
    )
    require(evidence == audit["seven_arm_postrun_evidence"]
            and evidence == auth["seven_arm_blind_evidence"],
            "blind predictor files changed since reference audit")

    contract_path = PHASE5 / "config_phase5_evaluation_v3b_fullsupport.json"
    scorer_path = PHASE5 / "run_phase5_evaluation_v3b_fullsupport.py"
    require(sha(contract_path) == auth["evaluation_contract_sha256"]
            and sha(scorer_path) == auth["evaluation_runner_sha256"],
            "previously registered Phase5 evaluation definitions changed")
    contract = read_json(contract_path)
    require(
        contract["status"] == "FROZEN_PHASE5_V3B_FULLSUPPORT_EVALUATION_CONTRACT"
        and contract["primary_window"] == {
            "H_min_seconds": 60, "H_max_seconds": 240,
            "step_seconds": 5, "horizon_count_per_query": 37,
        }
        and contract["primary_metrics"]["N_WB"] == REFERENCE_N,
        "historical primary scoring window/reference N changed",
    )
    # The seven-arm method set and equal-cell objective were frozen separately
    # by the B1 selection policy. Recheck that pre-WB source, without running it.
    policy_path = HERE / "B1_EXECUTABLE_POLICY_FREEZE_V1.md"
    seven_freeze = read_json(
        a.seven_arm / "b0001_seven_arm_pre_wb_blind_freeze.json"
    )
    require(
        sha(policy_path) == seven_freeze["policy_source_sha256"][policy_path.name]
        and tuple(seven_freeze["original_method_ids"]) == METHODS[:3]
        and set(seven_freeze["supplementary_method_ids"]) == set(METHODS[3:])
        and seven_freeze["n_method_condition_pairs"] == 84,
        "seven-arm method/policy freeze differs from original definition",
    )
    cell_audits = {row["cell"]: row for row in audit["cell_checks"]}
    require(set(cell_audits) == set(CELLS), "missing reference cell audit")
    for cell in CELLS:
        root = a.reference / cell
        require(
            sha(root / "final_wb_manifest.json") ==
            reference["cell_manifest_sha256"][cell],
            "reference cell manifest mutated: " + cell,
        )
        for filename, attr in (
            ("final_wb_ledger.csv", "ledger_sha256"),
            ("final_wb_curves.csv", "curve_sha256"),
        ):
            require(sha(root / filename) == cell_audits[cell][attr],
                    "reference file mutated: " + cell + "/" + filename)
    return {
        "reference_audit": audit_path,
        "reference_global_freeze": ref_freeze_path,
        "reference_global_sha256": sha(ref_freeze_path),
        "authorization_sha256": sha(auth_path),
        "seven_blind_freeze_sha256": evidence["seven_arm_blind_freeze_sha256"],
        "historical_scoring_contract_sha256": sha(contract_path),
    }


def validate_curve(frame: pd.DataFrame, cell: str) -> pd.DataFrame:
    required = set(KEYS) | {
        "sigma_wb", "wb_n", "wb_successes", "wb_ci_lower", "wb_ci_upper",
    }
    require(required <= set(frame.columns), cell + ": missing reference columns")
    require(len(frame) == N_RAW and not frame.duplicated(list(KEYS)).any(),
            cell + ": reference row count/key uniqueness")
    require(set(frame["provider_world_id"].astype(str)) == {cell.split("__")[0]}
            and set(frame["graph_id"].astype(str)) == {cell.split("__")[1]},
            cell + ": reference cell identity mismatch")
    require(frame["query_id"].nunique() == N_QUERIES,
            cell + ": reference query coverage")
    for _, group in frame.groupby("query_id"):
        require(group["H"].astype(float).sort_values().tolist() ==
                list(map(float, HORIZONS)), cell + ": reference horizon grid")
    require((frame["wb_n"] == REFERENCE_N).all()
            and frame["sigma_wb"].between(0, 1).all(),
            cell + ": reference N or probabilities")
    return frame


def validate_prediction(frame: pd.DataFrame, method: str, cell: str) -> pd.DataFrame:
    required = set(KEYS) | {"sigma_hat", "method_id"}
    require(required <= set(frame.columns), f"{cell}/{method}: missing columns")
    if method == "M3_FULL343":
        frame = frame[frame["method_id"].astype(str) == method].copy()
    require(len(frame) == N_RAW and not frame.duplicated(list(KEYS)).any(),
            f"{cell}/{method}: incomplete/duplicate predictions")
    require(set(frame["method_id"].astype(str)) == {method},
            f"{cell}/{method}: wrong method label")
    require(frame["query_id"].nunique() == N_QUERIES,
            f"{cell}/{method}: wrong query count")
    values = pd.to_numeric(frame["sigma_hat"], errors="coerce").to_numpy(float)
    require(np.isfinite(values).all()
            and ((values >= -TOL) & (values <= 1 + TOL)).all(),
            f"{cell}/{method}: nonfinite/out-of-range predictions")
    return frame


def join_primary(
    prediction: pd.DataFrame, reference: pd.DataFrame,
    method: str, cell: str,
) -> pd.DataFrame:
    pred = validate_prediction(prediction, method, cell)
    wb = validate_curve(reference, cell)
    reference_cols = list(KEYS) + [
        "sigma_wb", "wb_n", "wb_successes", "wb_ci_lower", "wb_ci_upper",
    ]
    merged = pred.merge(
        wb[reference_cols], on=list(KEYS), how="inner", validate="one_to_one",
    )
    require(len(merged) == N_RAW, f"{cell}/{method}: mismatched prediction/WB keys")
    merged = merged[merged["H"].isin(PRIMARY_HORIZONS)].copy()
    require(len(merged) == N_PRIMARY,
            f"{cell}/{method}: primary 60..240 window incomplete")
    merged.insert(0, "physical_cell_id", cell)
    merged["method_id"] = method
    merged["error"] = merged["sigma_hat"].astype(float) - merged["sigma_wb"].astype(float)
    merged["abs_error"] = merged["error"].abs()
    merged["squared_error"] = merged["error"] ** 2
    keep = [
        "physical_cell_id", "method_id", *KEYS, "sigma_hat", "sigma_wb",
        "wb_n", "wb_successes", "wb_ci_lower", "wb_ci_upper",
        "error", "abs_error", "squared_error",
    ]
    return merged[keep].sort_values(["query_id", "H"], kind="mergesort")


def metrics(frame: pd.DataFrame) -> dict:
    require(len(frame) > 0, "cannot score empty set")
    err = frame["error"].to_numpy(float)
    truth = frame["sigma_wb"].to_numpy(float)
    noise = truth * (1 - truth) / (REFERENCE_N - 1)
    require(np.isfinite(err).all(), "nonfinite prediction errors")
    return {
        "n_points": int(len(frame)),
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(math.sqrt(np.mean(err ** 2))),
        "signed_bias": float(np.mean(err)),
        "max_abs_error": float(np.max(np.abs(err))),
        "reference_noise_adjusted_RMSE": float(math.sqrt(
            max(0.0, np.mean(err ** 2 - noise))
        )),
    }


def summarize(joined: pd.DataFrame) -> dict[str, pd.DataFrame]:
    require(len(joined) == len(METHODS) * len(CELLS) * N_PRIMARY,
            "seven-arm pointwise coverage is not 7 x 12 x 555")
    cell_rows = []
    for method in METHODS:
        for cell in CELLS:
            subset = joined[
                (joined["method_id"] == method) &
                (joined["physical_cell_id"] == cell)
            ]
            require(len(subset) == N_PRIMARY, f"{method}/{cell}: wrong primary size")
            role, graph = cell.split("__")
            cell_rows.append({
                "method_id": method, "physical_cell_id": cell,
                "provider_world_id": role, "graph_id": graph,
                **metrics(subset),
            })
    cell_metrics = pd.DataFrame(cell_rows)
    require(len(cell_metrics) == 84 and
            not cell_metrics[["method_id", "physical_cell_id"]].duplicated().any(),
            "method-cell archive not exactly 84 unique entries")

    overall_rows = []
    for method in METHODS:
        subset = joined[joined["method_id"] == method]
        cell_mean = cell_metrics[cell_metrics["method_id"] == method]["MAE"].mean()
        all_metrics = metrics(subset)
        require(len(subset) == 12 * N_PRIMARY and
                np.isclose(all_metrics["MAE"], cell_mean, atol=TOL, rtol=0),
                "equal-cell MAE objective disagreement: " + method)
        overall_rows.append({
            "method_id": method, "n_cells": 12,
            "equal_cell_mean_MAE": float(cell_mean), **all_metrics,
        })
    overall = pd.DataFrame(overall_rows)

    scope_columns = {
        "provider_world": ["provider_world_id"],
        "graph": ["graph_id"],
        "regime": ["regime"],
        "rho": ["rho"],
        "provider_world_x_graph": ["provider_world_id", "graph_id"],
        "graph_x_regime": ["graph_id", "regime"],
        "provider_world_x_regime": ["provider_world_id", "regime"],
        "rho_x_regime": ["rho", "regime"],
    }
    strata = []
    for method in METHODS:
        subset = joined[joined["method_id"] == method]
        for scope, columns in scope_columns.items():
            grouper = columns[0] if len(columns) == 1 else columns
            for key, group in subset.groupby(grouper, sort=True, dropna=False):
                if len(columns) == 1:
                    key = (key,)
                strata.append({
                    "method_id": method, "scope": scope,
                    "scope_value": "|".join(
                        f"{name}={value}" for name, value in zip(columns, key)
                    ),
                    **metrics(group),
                })
    stratified = pd.DataFrame(strata)

    long_matrix = cell_metrics.rename(columns={
        "method_id": "method", "provider_world_id": "world",
        "graph_id": "graph", "MAE": "mae",
    })[["method", "world", "graph", "mae"]].copy()
    return {
        "method_cell_metrics": cell_metrics,
        "overall_accuracy": overall,
        "stratified_accuracy": stratified,
        "seven_method_matrix": long_matrix,
    }


def run(a: argparse.Namespace) -> None:
    evidence = preflight(a)
    if a.check:
        print("B0001_SEVEN_METHOD_ACCURACY_PREFLIGHT_PASS", flush=True)
        print("ALL_SEVEN_PREDICTIONS_UNCHANGED / AUDITED_REFERENCE_UNCHANGED", flush=True)
        print("NO_REFERENCE_VALUES_READ / NO_ERRORS_COMPUTED / NO_WRITES", flush=True)
        return

    frames = []
    for cell in CELLS:
        wb = validate_curve(pd.read_csv(reference_file(a, cell)), cell)
        for method in METHODS:
            pred = pd.read_csv(prediction_file(a, method, cell))
            frames.append(join_primary(pred, wb, method, cell))
        print("B0001_SEVEN_METHOD_ACCURACY_CELL_PASS", cell, flush=True)
    joined = pd.concat(frames, ignore_index=True)
    outputs = summarize(joined)
    outputs["pointwise_primary_joined"] = joined

    # All assertions and computations finish before creating the result tree.
    a.out.mkdir(parents=True, exist_ok=False)
    hashes = {}
    filenames = {
        "method_cell_metrics": "method_cell_metrics.csv",
        "overall_accuracy": "overall_accuracy.csv",
        "stratified_accuracy": "stratified_accuracy.csv",
        "seven_method_matrix": "seven_method_matrix.csv",
        "pointwise_primary_joined": "pointwise_primary_joined.csv",
    }
    for name, frame in outputs.items():
        path = a.out / filenames[name]
        frame.to_csv(path, index=False, float_format="%.17g")
        hashes[name] = sha(path)
    manifest = {
        "status": STATUS,
        "reference_mechanical_audit_sha256": sha(evidence["reference_audit"]),
        "final_reference_global_freeze_sha256": evidence["reference_global_sha256"],
        "final_reference_authorization_sha256": evidence["authorization_sha256"],
        "seven_arm_blind_freeze_sha256": evidence["seven_blind_freeze_sha256"],
        "registered_scoring_contract_sha256": evidence["historical_scoring_contract_sha256"],
        "evaluation_source_sha256": sha(Path(__file__)),
        "methods": list(METHODS),
        "n_methods": len(METHODS), "n_cells": len(CELLS),
        "n_method_cell_scores": 84, "primary_points_per_cell": N_PRIMARY,
        "total_pointwise_scores": len(joined),
        "primary_horizon_seconds": [60, 240],
        "primary_metric": "equal-cell mean MAE across 12 conditions",
        "pointwise_metric": "absolute(sigma_hat - sigma_wb)",
        "supplementary_metrics": [
            "RMSE", "signed_bias", "max_abs_error",
            "reference_noise_adjusted_RMSE",
        ],
        "m0_excluded_from_seven_arm_selection": True,
        "reference_uncertainty_bootstrap": "NOT_RUN_SEPARATE_STAGE",
        "selection_policy_replay": "NOT_RUN_SEPARATE_STAGE",
        "prediction_or_reference_modified": False,
        "simulations_run": 0,
        "seven_method_plan_b_complete": False,
        "output_files": filenames,
        "output_hashes_sha256": hashes,
    }
    manifest_path = a.out / "b0001_seven_method_accuracy_evaluation_v1.json"
    require(not manifest_path.exists(), "will not overwrite evaluation manifest")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print("B0001_SEVEN_METHOD_ACCURACY_EVALUATION_PASS", flush=True)
    print(outputs["overall_accuracy"][[
        "method_id", "n_points", "MAE", "RMSE", "signed_bias",
    ]].sort_values("MAE").to_string(index=False), flush=True)
    print("FROZEN_MATRIX", a.out / filenames["seven_method_matrix"], flush=True)
    print("MANIFEST", manifest_path, flush=True)
    print("NO_SIMULATIONS / NINE_POLICY_REPLAY_NOT_YET_RUN", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument("--check", action="store_true")
    mx.add_argument("--run", action="store_true")
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven-arm", "four-arm", "refaudit", "out",
    ):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven_arm", "four_arm", "refaudit", "out",
    ):
        setattr(a, name, getattr(a, name).expanduser().resolve())
    run(a)


if __name__ == "__main__":
    main()
