#!/usr/bin/env python3
"""Independent raw-ledger audit and registered B0001 reference uncertainty.

No simulator is imported; no trajectory is generated and no predictor is changed.
--check only hashes/validates frozen metadata, with no reference values read.
--run independently recomputes every SLA outcome from the 12 original request
ledgers, checks all 8,820 frozen reference points, diagnoses P1__G_PAR,
and runs the registered 10,000 paired, trajectory-index bootstrap replicates.

Resampling uses ONE vector of 1,000 complete trajectory indices per replicate,
shared across all 12 physical cells, preserving within-trajectory correlation
across all 15 queries and 37 primary horizons. This is finite reference-MC
uncertainty, *not* uncertainty over physical worlds or algorithm training.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import evaluate_b0001_seven_method_accuracy_v1 as original

HERE = Path(__file__).resolve().parent
STATUS = "B0001_P1_GPAR_RAW_AUDIT_AND_JOINT_REFERENCE_BOOTSTRAP_V1_PASS"
N = original.REFERENCE_N
N_REPS = 10000
SEED = 2026100201
HORIZONS = np.asarray(original.HORIZONS, dtype=np.float64)
PRIMARY_HORIZONS = frozenset(original.PRIMARY_HORIZONS)
EVENT_TOLERANCE = 1e-12
REQUIRED_LEDGER = {"trajectory", "trajectory_seed", "request_id", "emission", "completion", "L", "C", "Q"}
QUERY_COLS = ("query_id", "provider_world_id", "graph_id", "rho_label", "rho", "regime", "A_G_l_max", "A_G_c_max", "A_G_q_min")
KEY = ("physical_cell_id", "query_id", "H")


def require(ok: object, message: str) -> None:
    if not bool(ok):
        raise RuntimeError("B0001 RAW REFERENCE AUDIT: " + message)


def independently_reconstruct_query(
    ledger: pd.DataFrame, *, latency_limit: float, cost_limit: float,
    quality_minimum: float, rho: float, horizons: np.ndarray = HORIZONS,
) -> tuple[np.ndarray, dict[str, int]]:
    """Return [horizon, trajectory] binary SLA states from raw requests.

    Independent vectorized implementation of the *frozen* Phase-1 semantics:
    in-time completion is decided at completion; missed latency deadline is
    decided at emission+limit; requests undecided at t=240 are excluded;
    the decided-request cumulative admissible fraction must meet rho.
    """
    require(latency_limit >= 0 and cost_limit >= 0 and 0 < rho <= 1,
            "invalid frozen query thresholds")
    trajectory = ledger["trajectory"].to_numpy(dtype=np.int32)
    emitted = pd.to_numeric(ledger["emission"], errors="coerce").to_numpy(float)
    completion = pd.to_numeric(ledger["completion"], errors="coerce").to_numpy(float)
    cost = pd.to_numeric(ledger["C"], errors="coerce").to_numpy(float)
    quality = pd.to_numeric(ledger["Q"], errors="coerce").to_numpy(float)
    require(np.isfinite(emitted).all() and np.all((trajectory >= 0) & (trajectory < N)),
            "invalid emission or trajectory value")
    deadline = emitted + float(latency_limit)
    in_time = np.isfinite(completion) & (completion <= deadline + EVENT_TOLERANCE)
    require(np.isfinite(cost[in_time]).all() and np.isfinite(quality[in_time]).all(),
            "on-time request lacks finite C or Q")
    decision_time = np.where(in_time, completion, deadline)
    decided = decision_time <= float(horizons[-1]) + EVENT_TOLERANCE
    compliant = in_time & (cost <= cost_limit) & (quality >= quality_minimum)
    # First grid point where the decision is observable; a request contributes
    # to every later horizon. Histogram increments, then cumulative sum, avoid
    # both 1,000 Python per-trajectory loops and 49x request-size allocations.
    first_h = np.searchsorted(horizons, decision_time - EVENT_TOLERANCE, side="left")
    visible = decided & (first_h < len(horizons))
    n_decided = np.zeros((N, len(horizons)), dtype=np.int32)
    n_passed = np.zeros((N, len(horizons)), dtype=np.int32)
    np.add.at(n_decided, (trajectory[visible], first_h[visible]), 1)
    passed = visible & compliant
    np.add.at(n_passed, (trajectory[passed], first_h[passed]), 1)
    np.cumsum(n_decided, axis=1, out=n_decided)
    np.cumsum(n_passed, axis=1, out=n_passed)
    fraction = np.ones(n_decided.shape, dtype=np.float64)  # zero decisions => 1
    np.divide(n_passed, n_decided, out=fraction, where=n_decided != 0)
    states = (fraction + EVENT_TOLERANCE >= float(rho)).T.copy()
    return states, {
        "decided_requests_by_stop": int(visible.sum()),
        "compliant_requests_by_stop": int(passed.sum()),
        "latency_deadline_failures_by_stop": int((visible & ~in_time).sum()),
        "cost_failures_by_stop": int((visible & in_time & (cost > cost_limit)).sum()),
        "quality_failures_by_stop": int((visible & in_time & (quality < quality_minimum)).sum()),
        "unresolved_requests_at_stop": int((~visible).sum()),
        "zero_decision_states": int((n_decided == 0).sum()),
    }


def _ledger(a: argparse.Namespace, cell: str) -> pd.DataFrame:
    ledger = pd.read_csv(a.reference / cell / "final_wb_ledger.csv")
    require(REQUIRED_LEDGER <= set(ledger.columns), cell + ": missing ledger fields")
    require(not ledger.empty and not ledger[["trajectory", "request_id"]].duplicated().any(),
            cell + ": empty ledger or duplicate logical requests")
    require(not ledger["trajectory"].isna().any()
            and not ledger["trajectory_seed"].isna().any(), cell + ": null trajectory identity")
    traj = ledger["trajectory"].to_numpy()
    require(np.isfinite(traj).all() and np.array_equal(traj, traj.astype(np.int32)),
            cell + ": non-integer trajectory")
    require(sorted(ledger["trajectory"].unique().tolist()) == list(range(N)),
            cell + ": incomplete trajectory ordinals")
    for trajectory, chunk in ledger.groupby("trajectory", sort=True):
        require(chunk["trajectory_seed"].nunique() == 1
                and int(chunk["trajectory_seed"].iloc[0]) == 42_000_000 + int(trajectory),
                cell + f": seed/ordinal mismatch at trajectory {trajectory}")
    return ledger


def reconstruct_cell(a: argparse.Namespace, cell: str) -> tuple[pd.DataFrame, np.ndarray, list[dict]]:
    ledger = _ledger(a, cell)
    frozen = pd.read_csv(a.staging / "frozen_queries" / cell / "step0_frozen_queries.csv")
    wb = original.validate_curve(pd.read_csv(original.reference_file(a, cell)), cell)
    require(set(QUERY_COLS) <= set(frozen.columns), cell + ": incomplete query metadata")
    require(len(frozen) == original.N_QUERIES and not frozen["query_id"].duplicated().any(),
            cell + ": frozen query count")
    require(set(frozen["query_id"]) == set(wb["query_id"]), cell + ": query ids differ")
    matrices = []
    rows = []
    details = []
    for q in frozen.sort_values("query_id").itertuples(index=False):
        qid = str(q.query_id)
        sub = wb[wb["query_id"] == qid].sort_values("H")
        require(np.array_equal(sub["H"].to_numpy(float), HORIZONS),
                f"{cell}/{qid}: horizon coverage")
        for column in QUERY_COLS:
            expected = getattr(q, column)
            observed = sub[column].iloc[0]
            if column in {"rho", "A_G_l_max", "A_G_c_max", "A_G_q_min"}:
                require(abs(float(observed) - float(expected)) <= 1e-12,
                        f"{cell}/{qid}: query {column} changed")
            else:
                require(str(observed) == str(expected),
                        f"{cell}/{qid}: query {column} changed")
        states, breakdown = independently_reconstruct_query(
            ledger, latency_limit=float(q.A_G_l_max), cost_limit=float(q.A_G_c_max),
            quality_minimum=float(q.A_G_q_min), rho=float(q.rho),
        )
        counts = states.sum(axis=1, dtype=np.int64)
        declared = sub["wb_successes"].to_numpy(dtype=np.int64)
        mismatch = np.flatnonzero(counts != declared)
        require(len(mismatch) == 0,
                f"{cell}/{qid}: independent raw ledger mismatches frozen WB "
                f"at H={HORIZONS[mismatch[0]] if len(mismatch) else '?'}")
        require(np.allclose(counts / N, sub["sigma_wb"].to_numpy(float),
                            atol=1e-12, rtol=0), f"{cell}/{qid}: sigma mismatch")
        keep = np.array([float(h) in PRIMARY_HORIZONS for h in HORIZONS])
        matrices.append(states[keep].astype(np.uint8))
        rows.extend((cell, qid, int(h)) for h in HORIZONS[keep])
        details.append({
            "physical_cell_id": cell, "query_id": qid, "rho": float(q.rho),
            "rho_label": str(q.rho_label), "regime": str(q.regime),
            "A_G_l_max": float(q.A_G_l_max), "A_G_c_max": float(q.A_G_c_max),
            "A_G_q_min": float(q.A_G_q_min),
            "primary_mean_sigma_wb": float(counts[keep].mean() / N),
            "primary_min_sigma_wb": float(counts[keep].min() / N),
            "primary_max_sigma_wb": float(counts[keep].max() / N),
            **breakdown,
        })
    return pd.DataFrame(rows, columns=KEY), np.concatenate(matrices, axis=0), details


def validate_frozen_accuracy(a: argparse.Namespace, preflight: dict) -> dict:
    manifest_path = a.accuracy / "b0001_seven_method_accuracy_evaluation_v1.json"
    manifest = original.read_json(manifest_path)
    require(manifest["status"] == original.STATUS
            and manifest["reference_mechanical_audit_sha256"] == original.EXTERNAL_AUDIT_SHA256
            and manifest["final_reference_global_freeze_sha256"] == preflight["reference_global_sha256"]
            and manifest["final_reference_authorization_sha256"] == preflight["authorization_sha256"]
            and manifest["seven_arm_blind_freeze_sha256"] == preflight["seven_blind_freeze_sha256"]
            and manifest["registered_scoring_contract_sha256"] == preflight["historical_scoring_contract_sha256"]
            and manifest["evaluation_source_sha256"] == original.sha(Path(original.__file__))
            and tuple(manifest["methods"]) == original.METHODS
            and manifest["n_cells"] == 12 and manifest["total_pointwise_scores"] == 46620
            and manifest["reference_uncertainty_bootstrap"] == "NOT_RUN_SEPARATE_STAGE",
            "accuracy manifest incompatible with original seven-method freeze")
    for key, file_name in manifest["output_files"].items():
        require(original.sha(a.accuracy / file_name) == manifest["output_hashes_sha256"][key],
                "frozen accuracy file hash mismatch: " + key)
    return manifest


def preflight(a: argparse.Namespace) -> tuple[dict, dict]:
    # This original preflight checks all seven methods, the post-WB independent
    # reference audit, all individual WB ledgers, and the registered evaluation.
    evidence = original.preflight(a)
    original.check_output_path(a)
    require(a.out != a.accuracy and a.out not in a.accuracy.parents
            and a.accuracy not in a.out.parents,
            "output must not overlap frozen accuracy")
    evaluation = validate_frozen_accuracy(a, evidence)
    contract = original.read_json(original.PHASE5 / "config_phase5_evaluation_v3b_fullsupport.json")
    require(contract["bootstrap_reference_uncertainty"] == {
        "stage": "separate_after_deterministic_evaluation_freeze",
        "bootstrap_reps": N_REPS, "bootstrap_seed": SEED,
        "resampling_unit": "complete final-WB trajectory index",
        "joint_resample_across_physical_cells": True,
        "method_predictions_fixed": True, "interval": "percentile_95",
        "interpretation": "finite final-WB reference uncertainty only",
    }, "registered bootstrap contract changed")
    return evidence, evaluation


def aligned_prediction_matrix(a: argparse.Namespace, keys: pd.DataFrame) -> np.ndarray:
    pointwise = pd.read_csv(a.accuracy / "pointwise_primary_joined.csv")
    require(len(pointwise) == len(original.METHODS) * len(keys),
            "frozen pointwise matrix length mismatch")
    require(not pointwise.duplicated(list(KEY) + ["method_id"]).any(),
            "frozen pointwise duplicated")
    canonical = pd.MultiIndex.from_frame(keys[list(KEY)])
    require(canonical.is_unique, "raw reference primary keys duplicated")
    pivot = pointwise.pivot(index=list(KEY), columns="method_id", values="sigma_hat")
    require(len(pivot) == len(keys) and set(pivot.columns) == set(original.METHODS)
            and pivot.index.is_unique and pivot.notna().all().all(),
            "frozen method matrix incomplete")
    require(canonical.difference(pivot.index).empty and pivot.index.difference(canonical).empty,
            "frozen predictions and reconstructed WB keys mismatch")
    pred = pivot.reindex(canonical)[list(original.METHODS)].to_numpy(dtype=np.float64).T
    require(np.isfinite(pred).all() and ((pred >= -1e-12) & (pred <= 1 + 1e-12)).all(),
            "frozen predictions invalid")
    # The joined source includes the original WB value for every method. It
    # must agree with independently reconstructed trajectory-level means.
    return pred


def verify_joined_reference(a: argparse.Namespace, keys: pd.DataFrame, truth: np.ndarray) -> None:
    joined = pd.read_csv(a.accuracy / "pointwise_primary_joined.csv",
                         usecols=[*KEY, "method_id", "sigma_wb", "wb_successes"])
    idx = pd.MultiIndex.from_frame(keys[list(KEY)])
    for method, data in joined.groupby("method_id"):
        aligned = data.set_index(list(KEY)).reindex(idx)
        require(not aligned.isna().any().any(), f"joined reference incomplete for {method}")
        require(np.array_equal(aligned["wb_successes"].to_numpy(int), (truth * N).round().astype(int)),
                f"joined WB success counts disagree for {method}")
        require(np.allclose(aligned["sigma_wb"].to_numpy(float), truth,
                            rtol=0, atol=1e-12),
                f"joined WB values disagree for {method}")


def frozen_overall_check(a: argparse.Namespace, pred: np.ndarray, truth: np.ndarray) -> np.ndarray:
    score = np.mean(np.abs(pred - truth[None, :]), axis=1)
    overall = pd.read_csv(a.accuracy / "overall_accuracy.csv").set_index("method_id")
    require(set(overall.index) == set(original.METHODS), "missing frozen overall methods")
    expected = overall.reindex(list(original.METHODS))["MAE"].to_numpy(float)
    require(np.allclose(score, expected, atol=1e-12, rtol=0),
            "independently reconstructed overall MAE differs from frozen evaluation")
    return score


def paired_weights(rng: np.random.Generator, batch: int) -> np.ndarray:
    """One shared sequence of 1,000 sampled ordinals per replicate."""
    sampled = rng.integers(0, N, size=(batch, N), dtype=np.int32)
    weight = np.zeros((N, batch), dtype=np.float32)
    for i, draw in enumerate(sampled):
        weight[:, i] = np.bincount(draw, minlength=N)
    require(np.all(weight.sum(axis=0) == N), "invalid complete-trajectory bootstrap")
    return weight


def bootstrap(pred: np.ndarray, bits: np.ndarray, gpar_rows: np.ndarray,
              reps: int = N_REPS, seed: int = SEED, batch_size: int = 32,
              progress: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    require(pred.shape == (len(original.METHODS), bits.shape[0])
            and bits.shape[1] == N, "bootstrap array shapes")
    require(gpar_rows.dtype == bool and gpar_rows.shape == (bits.shape[0],)
            and gpar_rows.sum() == original.N_PRIMARY, "P1 G_PAR indicator")
    rng = np.random.default_rng(seed)
    raw = bits.astype(np.float32, copy=False)
    results = np.empty((reps, len(original.METHODS)), dtype=np.float64)
    anomaly = np.empty((reps, 2), dtype=np.float64)
    m1 = original.METHODS.index("M1")
    m3 = original.METHODS.index("M3_FULL343")
    for start in range(0, reps, batch_size):
        take = min(batch_size, reps - start)
        weights = paired_weights(rng, take)
        # BLAS can multiply all 6,660 correlated binary points by the SAME
        # sampled trajectory histogram, separately for each replicate.
        reference = raw @ weights / float(N)
        for j in range(take):
            delta = np.abs(pred - reference[:, j][None, :])
            results[start + j, :] = delta.mean(axis=1)
            anomaly[start + j, 0] = delta[m1, gpar_rows].mean()
            anomaly[start + j, 1] = delta[m3, gpar_rows].mean()
        if progress and (start + take == reps or (start + take) % 512 == 0):
            print(f"B0001_REFERENCE_BOOTSTRAP {start + take}/{reps}", flush=True)
    df = pd.DataFrame(results, columns=["MAE_" + method for method in original.METHODS])
    df.insert(0, "replicate", np.arange(1, reps + 1))
    df["MAE_M3_minus_M1"] = results[:, m3] - results[:, m1]
    df["P1_G_PAR_M1_MAE"] = anomaly[:, 0]
    df["P1_G_PAR_M3_MAE"] = anomaly[:, 1]
    df["P1_G_PAR_M3_minus_M1"] = anomaly[:, 1] - anomaly[:, 0]
    ranks = np.argsort(np.argsort(results, axis=1, kind="stable"), axis=1, kind="stable") + 1
    df["M1_rank"] = ranks[:, m1]
    df["M3_rank"] = ranks[:, m3]
    summary = []
    for i, method in enumerate(original.METHODS):
        values = results[:, i]
        summary.append({
            "method_id": method,
            "bootstrap_mean_MAE": float(np.mean(values)),
            "bootstrap_p025_MAE": float(np.quantile(values, .025)),
            "bootstrap_p975_MAE": float(np.quantile(values, .975)),
            "fraction_ranked_first": float(np.mean(ranks[:, i] == 1)),
            "fraction_ranked_top_two": float(np.mean(ranks[:, i] <= 2)),
        })
    return df, pd.DataFrame(summary)


def anomaly_report(keys: pd.DataFrame, pred: np.ndarray, truth: np.ndarray,
                   detail: list[dict]) -> tuple[pd.DataFrame, dict]:
    role = keys["physical_cell_id"].eq("P1__G_PAR").to_numpy()
    require(int(role.sum()) == original.N_PRIMARY, "P1__G_PAR primary point count")
    m1 = original.METHODS.index("M1")
    m3 = original.METHODS.index("M3_FULL343")
    qdetails = pd.DataFrame([r for r in detail if r["physical_cell_id"] == "P1__G_PAR"])
    reports = []
    for row in qdetails.itertuples(index=False):
        subset = role & keys["query_id"].eq(row.query_id).to_numpy()
        require(subset.sum() == len(original.PRIMARY_HORIZONS), "P1 G_PAR query support")
        reports.append({
            **row._asdict(),
            "M1_mean_sigma_hat": float(pred[m1, subset].mean()),
            "M3_mean_sigma_hat": float(pred[m3, subset].mean()),
            "M1_MAE": float(np.abs(pred[m1, subset] - truth[subset]).mean()),
            "M3_MAE": float(np.abs(pred[m3, subset] - truth[subset]).mean()),
            "M3_signed_bias": float((pred[m3, subset] - truth[subset]).mean()),
            "M3_underprediction_fraction": float(np.mean(pred[m3, subset] < truth[subset])),
        })
    summary = {
        "physical_cell_id": "P1__G_PAR",
        "n_primary_points": int(role.sum()),
        "M1_MAE": float(np.abs(pred[m1, role] - truth[role]).mean()),
        "M3_MAE": float(np.abs(pred[m3, role] - truth[role]).mean()),
        "M3_minus_M1_MAE": float(np.abs(pred[m3, role] - truth[role]).mean()
                                  - np.abs(pred[m1, role] - truth[role]).mean()),
        "M1_mean_prediction": float(pred[m1, role].mean()),
        "M3_mean_prediction": float(pred[m3, role].mean()),
        "WB_mean_reference": float(truth[role].mean()),
        "M3_underprediction_fraction": float(np.mean(pred[m3, role] < truth[role])),
        "all_735_raw_reference_points_exactly_reconstructed": True,
    }
    return pd.DataFrame(reports), summary


def _write_csv(frame: pd.DataFrame, path: Path, hashes: dict) -> None:
    frame.to_csv(path, index=False, float_format="%.17g")
    hashes[path.name] = original.sha(path)


def run(a: argparse.Namespace) -> None:
    evidence, accuracy_manifest = preflight(a)
    if a.check:
        print("B0001_RAW_REFERENCE_AND_BOOTSTRAP_PREFLIGHT_PASS")
        print("NO_REFERENCE_VALUES_READ / NO_SIMULATIONS / NO_WRITES")
        return

    keys_list, binary_list, query_details = [], [], []
    for cell in original.CELLS:
        key_frame, binary, detail = reconstruct_cell(a, cell)
        keys_list.append(key_frame)
        binary_list.append(binary)
        query_details.extend(detail)
        print(f"B0001_INDEPENDENT_RAW_SLA_REFERENCE_CELL_PASS {cell} 735/735", flush=True)
    keys = pd.concat(keys_list, ignore_index=True)
    bits = np.concatenate(binary_list, axis=0)
    require(len(keys) == len(original.CELLS) * original.N_PRIMARY
            and bits.shape == (6660, 1000), "missing independent primary trajectory states")
    truth = bits.mean(axis=1, dtype=np.float64)
    pred = aligned_prediction_matrix(a, keys)
    verify_joined_reference(a, keys, truth)
    observed_maes = frozen_overall_check(a, pred, truth)
    query_table, anomaly = anomaly_report(keys, pred, truth, query_details)
    gpar_rows = keys["physical_cell_id"].eq("P1__G_PAR").to_numpy()
    print("B0001_P1_G_PAR_RAW_LEDGER_ANOMALY_AUDIT_PASS", flush=True)
    print("P1_G_PAR_MAE", f"M1={anomaly['M1_MAE']:.6f}",
          f"M3={anomaly['M3_MAE']:.6f}", flush=True)
    print("B0001_ALL_8820_RAW_REFERENCE_SCORES_MATCH_FROZEN", flush=True)

    rep, method_summary = bootstrap(pred, bits, gpar_rows, progress=True)
    m1, m3 = original.METHODS.index("M1"), original.METHODS.index("M3_FULL343")
    diff = rep["MAE_M3_minus_M1"].to_numpy(float)
    gdiff = rep["P1_G_PAR_M3_minus_M1"].to_numpy(float)
    paired = {
        "contrast": "MAE(M3_FULL343) minus MAE(M1): positive favors M1",
        "frozen_observed_MAE_difference": float(observed_maes[m3] - observed_maes[m1]),
        "bootstrap_mean_difference": float(diff.mean()),
        "bootstrap_percentile_95": [float(x) for x in np.quantile(diff, [.025, .975])],
        "bootstrap_fraction_M1_better": float(np.mean(diff > 0)),
        "bootstrap_fraction_M3_better": float(np.mean(diff < 0)),
        "bootstrap_fraction_equal": float(np.mean(diff == 0)),
        "P1_G_PAR_observed_MAE_difference": anomaly["M3_minus_M1_MAE"],
        "P1_G_PAR_bootstrap_percentile_95": [float(x) for x in np.quantile(gdiff, [.025, .975])],
        "P1_G_PAR_fraction_M1_better": float(np.mean(gdiff > 0)),
    }
    manifest = {
        "status": STATUS,
        "original_accuracy_manifest_sha256": original.sha(a.accuracy / "b0001_seven_method_accuracy_evaluation_v1.json"),
        "original_accuracy_matrix_sha256": accuracy_manifest["output_hashes_sha256"]["pointwise_primary_joined"],
        "original_reference_global_freeze_sha256": evidence["reference_global_sha256"],
        "original_reference_mechanical_audit_sha256": original.EXTERNAL_AUDIT_SHA256,
        "registered_evaluation_contract_sha256": evidence["historical_scoring_contract_sha256"],
        "audit_and_bootstrap_source_sha256": original.sha(Path(__file__)),
        "raw_request_decision_semantics": "emission, completion, latency deadline, cost, quality, cumulative decided requests, zero-decision=1",
        "fully_reconstructed_cells": list(original.CELLS),
        "independent_raw_ledger_curve_points_verified": 12 * original.N_RAW,
        "reference_trajectory_indices_per_cell": N,
        "number_of_methods": len(original.METHODS),
        "primary_points_per_cell": original.N_PRIMARY,
        "bootstrap_reps": N_REPS, "bootstrap_seed": SEED,
        "numpy_bitgenerator": "default_rng/PCG64",
        "resampling_unit": "complete final-WB trajectory ordinal",
        "joint_resample_across_physical_cells": True,
        "frozen_predictions_unchanged": True,
        "confidence_interval_method": "bootstrap percentile 2.5%-97.5%",
        "inference_scope": "finite N=1000 white-box Monte Carlo reference uncertainty ONLY",
        "reference_or_predictions_modified": False, "simulations_run": 0,
        "P1_G_PAR_anomaly": anomaly,
        "M1_vs_M3_paired_reference_uncertainty": paired,
    }
    # Write only after passing every independent ledger/curve and frozen-score
    # gate and completing every registered bootstrap replicate.
    a.out.mkdir(parents=True, exist_ok=False)
    hashes = {}
    _write_csv(query_table, a.out / "p1_gpar_query_diagnostics.csv", hashes)
    _write_csv(method_summary, a.out / "seven_method_reference_uncertainty.csv", hashes)
    _write_csv(rep, a.out / "reference_bootstrap_10000_replicates.csv", hashes)
    manifest["output_sha256"] = hashes
    manifest_path = a.out / "b0001_raw_audit_reference_uncertainty_v1.json"
    with manifest_path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print("B0001_P1_G_PAR_AND_JOINT_REFERENCE_UNCERTAINTY_V1_PASS", flush=True)
    print("M1_VS_M3_OBSERVED_DELTA", f"{paired['frozen_observed_MAE_difference']:.8f}", flush=True)
    print("M1_VS_M3_REFERENCE_BOOTSTRAP_95", paired["bootstrap_percentile_95"], flush=True)
    print("M1_BETTER_BOOTSTRAP_FRACTION", f"{paired['bootstrap_fraction_M1_better']:.4f}", flush=True)
    print("MANIFEST", manifest_path, flush=True)
    print("NO_SIMULATIONS / NO_PREDICTOR_CHANGES / NO_REFERENCE_CHANGES", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run", action="store_true")
    for name in ("authorization", "reference", "graph", "staging", "audit",
                 "seven-arm", "four-arm", "refaudit", "accuracy", "out"):
        p.add_argument("--" + name, required=True, type=Path, dest=name.replace("-", "_"))
    run(p.parse_args())


if __name__ == "__main__":
    main()
