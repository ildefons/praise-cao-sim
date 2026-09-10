"""Diagnose provider-local A_i candidates directly from frozen Phase-2 traces.

Scientific purpose
------------------
The direct-I1 design requires each provider-local admissibility region A_i to
come from that provider's own acquisition evidence. This diagnostic reuses the
already established Phase-1 style of AR calibration locally: empirical L/C
candidate thresholds are generated from the provider trace, then candidate
sigma behavior is inspected for a healthy rho=0.95 contour and an informative
rho=0.99 contour.

There is deliberately no A_G input, no global budget decomposition, and no
M0/M1. This file is diagnostic only: it does not select or freeze A_i.

Performance note
----------------
The first implementation repeatedly built thousands of Pandas decision tables
and was unnecessarily slow. This version preserves the same frozen request
accounting semantics but evaluates each trajectory with NumPy arrays directly.
No simulator rerun occurs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
ACQUISITION = HERE / "results" / "i1_acquisition_v1"
EVIDENCE_MANIFEST = HERE / "phase2_i1_freeze_manifest_v1.json"
PHASE1_AR_GENERATOR = PHASE1 / "config_phase1_sla_ar_generator_v1.json"
PHASE1_V2_FREEZE = PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
REPORT_HORIZONS = (120.0, 240.0)
EVENT_TOLERANCE = 1e-12


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def empirical_higher_quantile(values: pd.Series, level: float) -> float:
    """Return one observed upper order statistic, matching Phase-1 AR generation."""
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[np.isfinite(numeric.to_numpy(dtype=float))]
    if numeric.empty:
        raise ValueError("cannot derive a local threshold from no finite values")
    return float(numeric.quantile(float(level), interpolation="higher"))


def build_local_mixed_candidates(
    ledger: pd.DataFrame,
    provider: str,
    levels: list[float],
) -> list[dict[str, object]]:
    """Build only joint L/C provider-local candidates from provider evidence."""
    finite_q = pd.to_numeric(ledger["Q"], errors="coerce")
    finite_q = finite_q[np.isfinite(finite_q.to_numpy(dtype=float))]
    if finite_q.empty:
        raise ValueError(f"{provider} has no finite quality observations")

    q_min = float(finite_q.min())
    latency_thresholds = {
        level: empirical_higher_quantile(ledger["L"], level) for level in levels
    }
    cost_thresholds = {
        level: empirical_higher_quantile(ledger["C"], level) for level in levels
    }

    candidates: list[dict[str, object]] = []
    for latency_level in levels:
        for cost_level in levels:
            candidates.append(
                {
                    "provider": provider,
                    "candidate_id": (
                        f"{provider}_LQ{latency_level:.3f}_CQ{cost_level:.3f}"
                    ),
                    "latency_quantile": float(latency_level),
                    "cost_quantile": float(cost_level),
                    "l_max": float(latency_thresholds[latency_level]),
                    "c_max": float(cost_thresholds[cost_level]),
                    "q_min": q_min,
                }
            )
    return candidates


def _trajectory_metrics_numpy(
    emission: np.ndarray,
    completion: np.ndarray,
    cost: np.ndarray,
    quality: np.ndarray,
    *,
    latency_threshold: float,
    cost_threshold: float,
    quality_threshold: float,
    rho_values: tuple[float, ...],
    stop_time: float,
) -> tuple[dict[float, float], dict[tuple[float, float], bool]]:
    """Evaluate one trajectory using the exact frozen request-accounting semantics.

    A request completing by its local latency deadline is decided at completion.
    Otherwise it is decided as a latency failure at the deadline. Requests whose
    decision occurs after the simulation stop are unresolved. Exact normalized
    area is then integrated over the resulting cumulative compliance step
    process. This is numerically equivalent to the Phase-1 Pandas implementation
    but avoids constructing intermediate DataFrames.
    """
    deadline = emission + float(latency_threshold)
    completion_finite = np.isfinite(completion)
    completed_in_time = completion_finite & (
        completion <= deadline + EVENT_TOLERANCE
    )
    decision_time = np.where(completed_in_time, completion, deadline)
    decided = decision_time <= float(stop_time) + EVENT_TOLERANCE

    compliant = (
        decided
        & completed_in_time
        & np.isfinite(cost)
        & np.isfinite(quality)
        & (cost <= float(cost_threshold) + EVENT_TOLERANCE)
        & (quality + EVENT_TOLERANCE >= float(quality_threshold))
    )

    times = decision_time[decided].astype(float)
    passes = compliant[decided].astype(np.int64)
    if len(times) == 0:
        areas = {float(rho): 1.0 for rho in rho_values}
        horizon_states = {
            (float(rho), float(horizon)): True
            for rho in rho_values
            for horizon in REPORT_HORIZONS
        }
        return areas, horizon_states

    order = np.argsort(times, kind="stable")
    times = times[order]
    passes = passes[order]
    unique_times, first_indices, counts = np.unique(
        times, return_index=True, return_counts=True
    )
    pass_at_time = np.add.reduceat(passes, first_indices)
    cumulative_count = np.cumsum(counts, dtype=np.int64)
    cumulative_pass = np.cumsum(pass_at_time, dtype=np.int64)
    cumulative_fraction = cumulative_pass / cumulative_count

    observable = unique_times <= float(stop_time) + EVENT_TOLERANCE
    unique_times = unique_times[observable]
    cumulative_fraction = cumulative_fraction[observable]

    # Before the first decision c_i=1. After every decision event the new
    # cumulative fraction holds until the next event.
    boundaries = np.concatenate(
        (
            np.asarray([0.0], dtype=float),
            np.minimum(unique_times, float(stop_time)),
            np.asarray([float(stop_time)], dtype=float),
        )
    )
    widths = np.diff(boundaries)
    widths = np.maximum(widths, 0.0)
    interval_fraction = np.concatenate(
        (np.asarray([1.0], dtype=float), cumulative_fraction.astype(float))
    )
    if len(widths) != len(interval_fraction):
        raise RuntimeError("internal local exact-area construction mismatch")

    areas: dict[float, float] = {}
    for rho in rho_values:
        passing = interval_fraction + EVENT_TOLERANCE >= float(rho)
        areas[float(rho)] = float(
            np.sum(widths * passing.astype(float)) / float(stop_time)
        )

    fraction_at_horizon: dict[float, float] = {}
    for horizon in REPORT_HORIZONS:
        index = int(
            np.searchsorted(
                unique_times, float(horizon) + EVENT_TOLERANCE, side="right"
            )
        )
        fraction_at_horizon[float(horizon)] = (
            1.0 if index == 0 else float(cumulative_fraction[index - 1])
        )

    horizon_states = {
        (float(rho), float(horizon)): bool(
            fraction_at_horizon[float(horizon)] + EVENT_TOLERANCE >= float(rho)
        )
        for rho in rho_values
        for horizon in REPORT_HORIZONS
    }
    return areas, horizon_states


def _trajectory_arrays(ledger: pd.DataFrame) -> list[tuple[np.ndarray, ...]]:
    """Convert each provider trajectory once to compact numerical arrays."""
    required = {"trajectory", "emission", "completion", "C", "Q"}
    missing = required.difference(ledger.columns)
    if missing:
        raise ValueError(f"provider ledger missing columns: {sorted(missing)}")

    arrays: list[tuple[np.ndarray, ...]] = []
    for _, trajectory in ledger.groupby("trajectory", sort=True):
        arrays.append(
            (
                pd.to_numeric(trajectory["emission"], errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(trajectory["completion"], errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(trajectory["C"], errors="coerce").to_numpy(dtype=float),
                pd.to_numeric(trajectory["Q"], errors="coerce").to_numpy(dtype=float),
            )
        )
    if not arrays:
        raise ValueError("provider ledger contains no trajectories")
    return arrays


def evaluate_candidate_fast(
    trajectory_arrays: list[tuple[np.ndarray, ...]],
    candidate: dict[str, object],
    rho_values: tuple[float, ...],
    stop_time: float,
) -> dict[str, object]:
    """Evaluate one local A_i without repeated Pandas decision-table construction."""
    area_sum = {float(rho): 0.0 for rho in rho_values}
    success_count = {
        (float(rho), float(horizon)): 0
        for rho in rho_values
        for horizon in REPORT_HORIZONS
    }

    for emission, completion, cost, quality in trajectory_arrays:
        areas, states = _trajectory_metrics_numpy(
            emission,
            completion,
            cost,
            quality,
            latency_threshold=float(candidate["l_max"]),
            cost_threshold=float(candidate["c_max"]),
            quality_threshold=float(candidate["q_min"]),
            rho_values=rho_values,
            stop_time=float(stop_time),
        )
        for rho in rho_values:
            area_sum[float(rho)] += areas[float(rho)]
            for horizon in REPORT_HORIZONS:
                success_count[(float(rho), float(horizon))] += int(
                    states[(float(rho), float(horizon))]
                )

    n_trajectories = len(trajectory_arrays)
    result = dict(candidate)
    for rho in rho_values:
        tag = str(rho).replace(".", "p")
        result[f"R_{tag}"] = float(area_sum[float(rho)] / n_trajectories)
        result[f"sigma120_{tag}"] = float(
            success_count[(float(rho), 120.0)] / n_trajectories
        )
        result[f"sigma240_{tag}"] = float(
            success_count[(float(rho), 240.0)] / n_trajectories
        )
    return result


def main() -> None:
    evidence_manifest = _load_json(EVIDENCE_MANIFEST)
    ar_generator = _load_json(PHASE1_AR_GENERATOR)
    phase1_freeze = _load_json(PHASE1_V2_FREEZE)

    levels = [float(value) for value in ar_generator["quantile_levels"]]
    if levels != [0.90, 0.925, 0.95, 0.975, 0.99]:
        raise RuntimeError("unexpected Phase-1 AR quantile battery")

    nominal_gate = phase1_freeze["selection_policy"]["nominal_health_gate"]
    stress_gate = phase1_freeze["selection_policy"]["stress_informativeness_gate"]
    nominal_rho = float(nominal_gate["rho"])
    stress_rho = float(stress_gate["rho"])
    rho_values = (nominal_rho, 0.975, stress_rho)
    stop_time = float(evidence_manifest["workload_contract"]["horizon_max"])

    print("PHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC")
    print("selection_performed=false")
    print("A_G_used=false")
    print("global_budget_split=false")
    print("M0_M1_used=false")
    print("implementation=numpy_fast_v2")
    print(f"candidate_quantiles={levels}")
    print(
        "local_diagnostic_gate="
        f"R_{nominal_rho}>={float(nominal_gate['minimum'])},"
        f" {float(stress_gate['minimum'])}<=R_{stress_rho}<="
        f"{float(stress_gate['maximum'])}"
    )

    for provider in PROVIDERS:
        print(f"\n{provider}: loading frozen local evidence...", flush=True)
        ledger_path = (
            ACQUISITION / "private" / provider / "provider_request_ledgers.csv"
        )
        expected_hash = evidence_manifest["provider_corpus_sha256"][provider]
        if _sha256(ledger_path) != expected_hash:
            raise RuntimeError(f"{provider} frozen provider-corpus SHA-256 mismatch")
        ledger = pd.read_csv(ledger_path)
        trajectories = _trajectory_arrays(ledger)
        candidates = build_local_mixed_candidates(ledger, provider, levels)

        rows: list[dict[str, object]] = []
        for index, candidate in enumerate(candidates, start=1):
            rows.append(
                evaluate_candidate_fast(
                    trajectories, candidate, rho_values, stop_time
                )
            )
            if index in (5, 10, 15, 20, 25):
                print(
                    f"{provider}: evaluated {index}/{len(candidates)} candidates",
                    flush=True,
                )

        frame = pd.DataFrame(rows)
        nominal_column = f"R_{str(nominal_rho).replace('.', 'p')}"
        stress_column = f"R_{str(stress_rho).replace('.', 'p')}"
        eligible = frame[
            (frame[nominal_column] + EVENT_TOLERANCE >= float(nominal_gate["minimum"]))
            & (frame[stress_column] + EVENT_TOLERANCE >= float(stress_gate["minimum"]))
            & (frame[stress_column] <= float(stress_gate["maximum"]) + EVENT_TOLERANCE)
        ].copy()
        eligible = eligible.sort_values(
            [nominal_column, stress_column, "latency_quantile", "cost_quantile"],
            ascending=[False, True, True, True],
        ).reset_index(drop=True)

        print(f"\n{provider}_LOCAL_CANDIDATES")
        print(f"n_candidates={len(frame)} n_gate_passing={len(eligible)}")
        if eligible.empty:
            closest = frame.sort_values(
                [nominal_column, stress_column], ascending=[False, True]
            ).head(5)
            print("NO_GATE_PASSING_CANDIDATE; TOP_DIAGNOSTIC_ROWS")
            with pd.option_context("display.max_columns", None, "display.width", 260):
                print(closest.to_string(index=False))
        else:
            with pd.option_context("display.max_columns", None, "display.width", 260):
                print(eligible.to_string(index=False))

    print("\nPHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC_PASS")
    print("selection_performed=false")


if __name__ == "__main__":
    main()
