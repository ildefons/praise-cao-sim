"""Step-0 admissibility-region calibration for the frozen G2 condition.

This file performs experimental-design calibration only. It never loads or
runs M0/M1/M2 predictions.

Scientific ordering
-------------------
1. --prepare-only validates the frozen contract, public I1 support, G2 public
   adapter, hidden Phase-1 physical model provenance, grids and seed banks.
2. --selection-only generates the independent G2 hidden-model selection ledger
   (seeds 32000..32099), evaluates the full predeclared A_G candidate grid for
   each rho, selects exactly one candidate by the frozen rule, and freezes that
   selection before confirmation evidence exists.
3. --confirm-and-freeze validates the selection freeze, generates a fresh
   confirmation ledger (seeds 32100..32199), evaluates only the five already
   selected regions, applies the same feasibility gates and the nesting check,
   and freezes A_G2 only if every check passes.

If Step 0 fails, this script records the failure and stops. The contract must
not be edited after observing calibration evidence; a separately named G2b
contract is required.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE1, PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from sla_compliance_analysis import EVENT_TOLERANCE  # noqa: E402
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_g2_graph_simulator import execute_one_g2_trajectory  # noqa: E402
from m2_g2_public_adapter import (  # noqa: E402
    G2_BRANCH_FIXED_LATENCY_SECONDS,
    G2_CONDITION_ID,
    G2_FIXED_COMMON_LATENCY_SECONDS,
    G2_PROVIDER_PR_SECONDS,
    build_g2_base_global_boundary,
    build_g2_public_graph_spec,
    relax_g2_boundary,
    validate_g2_public_graph_spec,
)

EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_M2_G2_STEP0_CALIBRATED_VALIDATION_V1"
SELECTION_STATUS = "FROZEN_PHASE4_M2_G2_STEP0_SELECTION_V1"
CALIBRATION_COMPLETE_STATUS = "FROZEN_PHASE4_M2_G2_STEP0_CALIBRATION_COMPLETE_V1"
CALIBRATION_FAILED_STATUS = "PHASE4_M2_G2_STEP0_CALIBRATION_FAILED_V1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TOL = 1e-12


def _float_grid(spec: dict[str, Any]) -> np.ndarray:
    low = float(spec["minimum"])
    high = float(spec["maximum"])
    step = float(spec["step"])
    if step <= 0.0 or high < low:
        raise ValueError("invalid frozen Step-0 scale grid")
    n = int(round((high - low) / step))
    grid = low + step * np.arange(n + 1, dtype=float)
    if abs(float(grid[-1]) - high) > 1e-10:
        raise RuntimeError("Step-0 scale grid endpoints are not integral in step")
    return np.round(grid, 12)


def _seed_bank(start: int, end: int, expected_n: int, label: str) -> tuple[int, ...]:
    seeds = tuple(range(int(start), int(end) + 1))
    if len(seeds) != int(expected_n):
        raise RuntimeError(f"{label} seed-bank length differs from frozen contract")
    if not seeds:
        raise RuntimeError(f"{label} seed bank is empty")
    return seeds


def _validate_contract(
    contract: dict[str, Any],
    *,
    metadata: dict[str, dict[str, object]],
    horizons: list[float],
    rho_support: list[float],
    workload: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected frozen G2 Step-0 contract status")

    freeze = dict(contract["method_freeze"])
    required_true = (
        "I1_unchanged",
        "M0_semantics_unchanged",
        "M1_parameters_unchanged",
        "M2_provider_members_unchanged",
    )
    for key in required_true:
        if not bool(freeze.get(key)):
            raise RuntimeError(f"G2 method-freeze invariant is false: {key}")
    if int(freeze["M2_joint_members"]) != 27:
        raise RuntimeError("G2 contract no longer freezes 27 M2 members")
    if str(freeze["M2_member_weight"]) != "1/27":
        raise RuntimeError("G2 contract no longer freezes equal 1/27 M2 weights")
    if bool(freeze["M1_is_M2_member"]):
        raise RuntimeError("G2 contract unexpectedly includes M1 in M2")
    if bool(freeze["G1_driven_method_repair_allowed"]):
        raise RuntimeError("G2 contract unexpectedly permits G1-driven M2 repair")

    graph_spec = build_g2_public_graph_spec()
    validate_g2_public_graph_spec(graph_spec)
    condition = dict(contract["G2_public_condition"])
    if str(condition["condition_id"]) != G2_CONDITION_ID:
        raise RuntimeError("G2 condition ID differs from public adapter")
    contract_pr = {
        key: float(value)
        for key, value in condition["network_model"]["PR_seconds"].items()
    }
    adapter_pr = dict(graph_spec["network_model"]["PR_seconds"])
    if contract_pr != {key: float(value) for key, value in adapter_pr.items()}:
        raise RuntimeError("G2 propagation delays differ between contract and adapter")

    algebra = dict(contract["G2_base_boundary_algebra"])
    if abs(
        float(algebra["common_latency_seconds_excluding_provider_branch_and_local_provider"])
        - G2_FIXED_COMMON_LATENCY_SECONDS
    ) > TOL:
        raise RuntimeError("G2 common latency term differs from public adapter")
    branch = {
        key: float(value)
        for key, value in algebra["provider_branch_fixed_latency_seconds"].items()
    }
    if branch != {
        key: float(value) for key, value in G2_BRANCH_FIXED_LATENCY_SECONDS.items()
    }:
        raise RuntimeError("G2 branch latency terms differ from public adapter")

    expected_workload = dict(condition["workload"])
    if abs(float(workload["period"]) - float(expected_workload["period_seconds"])) > TOL:
        raise RuntimeError("public I1 workload period differs from G2 contract")
    if (
        abs(
            float(workload["accounting_origin"])
            - float(expected_workload["accounting_origin"])
        )
        > TOL
    ):
        raise RuntimeError("public I1 accounting origin differs from G2 contract")
    if (
        abs(
            float(workload["horizon_max"])
            - float(expected_workload["horizon_max_seconds"])
        )
        > TOL
    ):
        raise RuntimeError("public I1 Hmax differs from G2 contract")

    expected_rhos = sorted(float(v) for v in expected_workload["rho_values"])
    if len(rho_support) != len(expected_rhos) or not np.allclose(
        np.asarray(sorted(rho_support), dtype=float),
        np.asarray(expected_rhos, dtype=float),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("public I1 rho support differs from G2 contract")

    if abs(float(max(horizons)) - float(workload["horizon_max"])) > TOL:
        raise RuntimeError("public horizon support and workload Hmax disagree")

    step0 = dict(contract["step0_calibration"])
    family = dict(step0["candidate_region_family"])
    l_grid = _float_grid(dict(family["latency_scale_grid"]))
    c_grid = _float_grid(dict(family["cost_scale_grid"]))
    if l_grid[0] < 1.0 - TOL or c_grid[0] < 1.0 - TOL:
        raise RuntimeError("G2 candidate grid contains a tightening below base A_G")

    window = dict(step0["diagnostic_horizon_window"])
    hmin = float(window["minimum_horizon_seconds"])
    hmax = float(window["maximum_horizon_seconds"])
    diagnostic_horizons = [
        float(h) for h in horizons if h >= hmin - TOL and h <= hmax + TOL
    ]
    if not diagnostic_horizons:
        raise RuntimeError("G2 diagnostic horizon window contains no frozen horizons")
    if abs(diagnostic_horizons[0] - hmin) > TOL:
        raise RuntimeError("G2 diagnostic Hmin is not on the frozen horizon grid")
    if abs(diagnostic_horizons[-1] - hmax) > TOL:
        raise RuntimeError("G2 diagnostic Hmax is not on the frozen horizon grid")

    _seed_bank(
        step0["selection_seed_start"],
        step0["selection_seed_end_inclusive"],
        step0["selection_n_trajectories"],
        "G2 Step-0 selection",
    )
    _seed_bank(
        step0["confirmation_seed_start"],
        step0["confirmation_seed_end_inclusive"],
        step0["confirmation_n_trajectories"],
        "G2 Step-0 confirmation",
    )

    prediction = dict(contract["blind_prediction_protocol_after_calibration"])
    final_eval = dict(contract["final_whitebox_evaluation"])
    selection_seeds = set(
        range(
            int(step0["selection_seed_start"]),
            int(step0["selection_seed_end_inclusive"]) + 1,
        )
    )
    confirmation_seeds = set(
        range(
            int(step0["confirmation_seed_start"]),
            int(step0["confirmation_seed_end_inclusive"]) + 1,
        )
    )
    prediction_seeds = set(
        range(
            int(prediction["prediction_seed_start"]),
            int(prediction["prediction_seed_end_inclusive"]) + 1,
        )
    )
    final_seeds = set(
        range(
            int(final_eval["trajectory_seed_start"]),
            int(final_eval["trajectory_seed_end_inclusive"]) + 1,
        )
    )
    banks = [
        ("selection", selection_seeds),
        ("confirmation", confirmation_seeds),
        ("prediction", prediction_seeds),
        ("final", final_seeds),
    ]
    for i, (name_a, bank_a) in enumerate(banks):
        for name_b, bank_b in banks[i + 1 :]:
            if bank_a.intersection(bank_b):
                raise RuntimeError(f"G2 seed banks overlap: {name_a} and {name_b}")

    return l_grid, c_grid, diagnostic_horizons


def _validate_hidden_model(
    contract: dict[str, Any],
    *,
    phase1_config_path: Path,
) -> tuple[dict[str, GraphProviderSurrogate], float, dict[str, Any]]:
    phase1 = _read_json(phase1_config_path)
    hidden = dict(contract["hidden_whitebox_model"])

    if str(hidden["case_id"]) not in str(
        phase1["confirmation"]["frozen_after_selection"]
    ):
        raise RuntimeError("Phase-1 config does not confirm the frozen G2 hidden case")

    family = dict(phase1["provider_family"])
    checks = {
        "instruction_cv": float(hidden["instruction_cv"]),
        "effective_ipt": float(hidden["effective_IPT"]),
        "cost_rate": float(hidden["cost_rate"]),
        "x": float(hidden["execution_fraction_x"]),
    }
    for key, expected in checks.items():
        if abs(float(family[key]) - expected) > TOL:
            raise RuntimeError(f"Phase-1 hidden-model {key} differs from G2 contract")

    center = float(hidden["center_instruction_mean"])
    delta = float(hidden["dispersion"])
    derived_instructions = {
        "ProviderA": center * (1.0 - delta),
        "ProviderB": center,
        "ProviderC": center * (1.0 + delta),
    }
    frozen_instructions = {
        key: float(value)
        for key, value in hidden["provider_instruction_means"].items()
    }
    for provider in PROVIDERS:
        if abs(derived_instructions[provider] - frozen_instructions[provider]) > TOL:
            raise RuntimeError(f"{provider}: hidden instruction mean mismatch")

    x = float(hidden["execution_fraction_x"])
    ipt = float(hidden["effective_IPT"])
    cv = float(hidden["instruction_cv"])
    cost_rate = float(hidden["cost_rate"])
    surrogates = {
        provider: GraphProviderSurrogate(
            mean_service_time=float(derived_instructions[provider]) * x / ipt,
            cost_rate=cost_rate,
            service_cv=cv,
        )
        for provider in PROVIDERS
    }
    provenance = {
        "case_id": str(hidden["case_id"]),
        "center_instruction_mean": center,
        "dispersion": delta,
        "provider_instruction_means": derived_instructions,
        "instruction_cv": cv,
        "effective_IPT": ipt,
        "cost_rate": cost_rate,
        "execution_fraction_x": x,
        "quality": float(hidden["quality"]),
        "derived_mean_service_times": {
            provider: float(surrogates[provider].mean_service_time)
            for provider in PROVIDERS
        },
        "phase1_config_sha256": _sha256(phase1_config_path),
    }
    return surrogates, x, provenance


def _base_regions(
    metadata: dict[str, dict[str, object]],
    rho_support: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for rho in rho_support:
        provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
        base = build_g2_base_global_boundary(provider_boundaries)
        rows.append(
            {
                "rho_global": float(rho),
                "base_l_max": float(base.l_max),
                "base_c_max": float(base.c_max),
                "base_q_min": float(base.q_min),
            }
        )
    return pd.DataFrame(rows).sort_values("rho_global").reset_index(drop=True)


def _generate_or_load_ledger(
    *,
    path: Path,
    label: str,
    surrogates: dict[str, GraphProviderSurrogate],
    graph_spec: dict[str, Any],
    workload: dict[str, float],
    seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
) -> tuple[pd.DataFrame, bool]:
    if path.exists():
        ledger = pd.read_csv(path)
        required = {"trajectory", "trajectory_seed", "request_id"}
        missing = sorted(required.difference(ledger.columns))
        if missing:
            raise RuntimeError(f"{label} ledger missing fields: {missing}")
        actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique().tolist()))
        if actual != seeds:
            raise RuntimeError(f"{label} ledger uses a different seed bank")
        if int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{label} ledger trajectory count mismatch")
        if ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{label} ledger contains duplicate requests")
        print(f"{label}: loaded completed checkpoint ledger", flush=True)
        return ledger, True

    frames: list[pd.DataFrame] = []
    for trajectory, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            one = execute_one_g2_trajectory(
                provider_surrogates=surrogates,
                graph_spec=graph_spec,
                workload_period=float(workload["period"]),
                stop_time=float(workload["horizon_max"]),
                trajectory_seed=int(seed),
                canonical_ipt=float(canonical_ipt),
                execution_fraction=float(execution_fraction),
            )
        one.insert(0, "trajectory", int(trajectory))
        one.insert(1, "trajectory_seed", int(seed))
        frames.append(one)
        if trajectory == 0 or (trajectory + 1) % 25 == 0 or trajectory + 1 == len(seeds):
            print(f"  {label}: {trajectory + 1}/{len(seeds)}", flush=True)

    ledger = pd.concat(frames, ignore_index=True)
    ledger.to_csv(path, index=False)
    return ledger, False


def _candidate_sigma_cube(
    ledger: pd.DataFrame,
    *,
    base: AdmissibilityBoundary,
    rho: float,
    latency_scales: np.ndarray,
    cost_scales: np.ndarray,
    horizons: list[float],
) -> np.ndarray:
    """Evaluate the frozen candidate grid exactly but efficiently.

    Returns sigma with shape (n_latency_scales, n_cost_scales, n_horizons).
    The implementation reproduces the frozen SLA decision semantics:
    completion no later than emission + latency threshold is in-time; otherwise
    the request is decided as a latency failure at its deadline; cost is
    inclusive; unresolved requests are excluded; zero decided requests imply
    compliance 1.
    """
    l_thresholds = float(base.l_max) * latency_scales.astype(float)
    c_thresholds = float(base.c_max) * cost_scales.astype(float)
    q_threshold = float(base.q_min)
    hs = np.asarray(horizons, dtype=float)

    counts = np.zeros(
        (len(l_thresholds), len(c_thresholds), len(hs)),
        dtype=np.int32,
    )
    trajectories = list(ledger.groupby("trajectory", sort=True))
    if not trajectories:
        raise RuntimeError("candidate-grid evaluation received no trajectories")

    for _, frame in trajectories:
        ordered = frame.sort_values(["emission", "request_id"])
        emission = ordered["emission"].astype(float).to_numpy()
        completion = pd.to_numeric(
            ordered["completion"], errors="coerce"
        ).to_numpy(dtype=float)
        cost = pd.to_numeric(ordered["C"], errors="coerce").to_numpy(dtype=float)
        quality = pd.to_numeric(ordered["Q"], errors="coerce").to_numpy(dtype=float)
        finite_completion = np.isfinite(completion)

        for li, l_threshold in enumerate(l_thresholds):
            deadline = emission + float(l_threshold)
            in_time = finite_completion & (
                completion <= deadline + EVENT_TOLERANCE
            )
            decision_time = np.where(in_time, completion, deadline)
            decided_counts = np.asarray(
                [
                    int(np.count_nonzero(decision_time <= h + EVENT_TOLERANCE))
                    for h in hs
                ],
                dtype=np.int32,
            )

            eligible = (
                in_time
                & np.isfinite(cost)
                & np.isfinite(quality)
                & (quality >= q_threshold)
            )
            eligible_time = completion[eligible]
            eligible_cost = cost[eligible]
            if len(eligible_time):
                order = np.argsort(eligible_time, kind="mergesort")
                event_time = eligible_time[order]
                event_cost = eligible_cost[order]
                first_passing_cost_index = np.searchsorted(
                    c_thresholds,
                    event_cost,
                    side="left",
                )
            else:
                event_time = np.empty(0, dtype=float)
                first_passing_cost_index = np.empty(0, dtype=int)

            histogram = np.zeros(len(c_thresholds) + 1, dtype=np.int32)
            pointer = 0
            compliant_by_h_c = np.zeros(
                (len(hs), len(c_thresholds)),
                dtype=np.int32,
            )
            for hi, horizon in enumerate(hs):
                new_pointer = int(
                    np.searchsorted(
                        event_time,
                        float(horizon) + EVENT_TOLERANCE,
                        side="right",
                    )
                )
                if new_pointer > pointer:
                    histogram += np.bincount(
                        first_passing_cost_index[pointer:new_pointer],
                        minlength=len(c_thresholds) + 1,
                    ).astype(np.int32)
                    pointer = new_pointer
                compliant_by_h_c[hi, :] = np.cumsum(histogram[: len(c_thresholds)])

            passing = np.zeros(
                (len(hs), len(c_thresholds)),
                dtype=bool,
            )
            zero = decided_counts == 0
            if np.any(zero):
                passing[zero, :] = bool(1.0 + EVENT_TOLERANCE >= float(rho))
            nonzero = ~zero
            if np.any(nonzero):
                fractions = (
                    compliant_by_h_c[nonzero, :].astype(float)
                    / decided_counts[nonzero, None].astype(float)
                )
                passing[nonzero, :] = (
                    fractions + EVENT_TOLERANCE >= float(rho)
                )
            counts[li, :, :] += passing.T.astype(np.int32)

    return counts.astype(float) / float(len(trajectories))


def _gate_metrics(
    sigma: np.ndarray,
    *,
    at_or_below_threshold: float = 0.98,
) -> dict[str, np.ndarray]:
    return {
        "sigma_min": np.min(sigma, axis=-1),
        "sigma_mean": np.mean(sigma, axis=-1),
        "sigma_max": np.max(sigma, axis=-1),
        "sigma_H240": sigma[..., -1],
        "sigma_range": np.max(sigma, axis=-1) - np.min(sigma, axis=-1),
        "fraction_at_or_below_0p98": np.mean(
            sigma <= float(at_or_below_threshold) + TOL,
            axis=-1,
        ),
    }


def _feasible_mask(
    metrics: dict[str, np.ndarray],
    gate: dict[str, Any],
) -> np.ndarray:
    return (
        (metrics["sigma_min"] >= float(gate["minimum_sigma_over_diagnostic_window"]) - TOL)
        & (
            metrics["sigma_mean"]
            >= float(gate["mean_sigma_over_diagnostic_window_minimum"]) - TOL
        )
        & (
            metrics["sigma_mean"]
            <= float(gate["mean_sigma_over_diagnostic_window_maximum"]) + TOL
        )
        & (metrics["sigma_H240"] >= float(gate["sigma_at_H240_minimum"]) - TOL)
        & (metrics["sigma_H240"] <= float(gate["sigma_at_H240_maximum"]) + TOL)
        & (
            metrics["sigma_range"]
            >= float(gate["minimum_sigma_range_over_diagnostic_window"]) - TOL
        )
        & (
            metrics["fraction_at_or_below_0p98"]
            >= float(gate["minimum_fraction_of_diagnostic_points_at_or_below_0p98"])
            - TOL
        )
    )


def _candidate_diagnostics(
    *,
    rho: float,
    base: AdmissibilityBoundary,
    latency_scales: np.ndarray,
    cost_scales: np.ndarray,
    sigma_cube: np.ndarray,
    gate: dict[str, Any],
) -> pd.DataFrame:
    metrics = _gate_metrics(sigma_cube)
    feasible = _feasible_mask(metrics, gate)
    rows: list[dict[str, Any]] = []
    for li, s_l in enumerate(latency_scales):
        for ci, s_c in enumerate(cost_scales):
            rows.append(
                {
                    "rho_global": float(rho),
                    "latency_scale": float(s_l),
                    "cost_scale": float(s_c),
                    "A_G_l_max": float(base.l_max) * float(s_l),
                    "A_G_c_max": float(base.c_max) * float(s_c),
                    "A_G_q_min": float(base.q_min),
                    "expansion_distance": float(
                        math.sqrt((float(s_l) - 1.0) ** 2 + (float(s_c) - 1.0) ** 2)
                    ),
                    "sigma_min_H60_H240": float(metrics["sigma_min"][li, ci]),
                    "sigma_mean_H60_H240": float(metrics["sigma_mean"][li, ci]),
                    "sigma_max_H60_H240": float(metrics["sigma_max"][li, ci]),
                    "sigma_H240": float(metrics["sigma_H240"][li, ci]),
                    "sigma_range_H60_H240": float(metrics["sigma_range"][li, ci]),
                    "fraction_at_or_below_0p98": float(
                        metrics["fraction_at_or_below_0p98"][li, ci]
                    ),
                    "feasible": bool(feasible[li, ci]),
                    "distance_mean_sigma_to_0p95": abs(
                        float(metrics["sigma_mean"][li, ci]) - 0.95
                    ),
                    "distance_sigma_H240_to_0p95": abs(
                        float(metrics["sigma_H240"][li, ci]) - 0.95
                    ),
                }
            )
    return pd.DataFrame(rows)


def _select_candidate(diagnostics: pd.DataFrame, rho: float) -> pd.Series:
    feasible = diagnostics[diagnostics["feasible"].astype(bool)].copy()
    if feasible.empty:
        raise RuntimeError(f"rho={rho:g}: no feasible G2 Step-0 candidate")
    ordered = feasible.sort_values(
        [
            "expansion_distance",
            "distance_mean_sigma_to_0p95",
            "distance_sigma_H240_to_0p95",
            "latency_scale",
            "cost_scale",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    return ordered.iloc[0]


def _canonical_curve(
    ledger: pd.DataFrame,
    *,
    boundary: AdmissibilityBoundary,
    rho: float,
    horizons: list[float],
    workload: dict[str, float],
    column: str,
) -> pd.DataFrame:
    return build_empirical_graph_sigma_curve(
        ledger,
        boundary=boundary,
        rho_global=float(rho),
        horizons=horizons,
        stop_time=float(workload["horizon_max"]),
        accounting_origin=float(workload["accounting_origin"]),
        output_column=column,
    )


def _summarize_curve_gate(
    curve: pd.DataFrame,
    *,
    diagnostic_horizons: list[float],
    sigma_column: str,
    gate: dict[str, Any],
) -> dict[str, Any]:
    selected = curve[
        curve["horizon"].astype(float).isin(
            [float(h) for h in diagnostic_horizons]
        )
    ].sort_values("horizon")
    if len(selected) != len(diagnostic_horizons):
        raise RuntimeError("canonical curve lacks diagnostic horizons")
    sigma = selected[sigma_column].astype(float).to_numpy()
    metrics = {
        "sigma_min_H60_H240": float(np.min(sigma)),
        "sigma_mean_H60_H240": float(np.mean(sigma)),
        "sigma_max_H60_H240": float(np.max(sigma)),
        "sigma_H240": float(sigma[-1]),
        "sigma_range_H60_H240": float(np.max(sigma) - np.min(sigma)),
        "fraction_at_or_below_0p98": float(np.mean(sigma <= 0.98 + TOL)),
    }
    array_metrics = {
        "sigma_min": np.asarray(metrics["sigma_min_H60_H240"]),
        "sigma_mean": np.asarray(metrics["sigma_mean_H60_H240"]),
        "sigma_max": np.asarray(metrics["sigma_max_H60_H240"]),
        "sigma_H240": np.asarray(metrics["sigma_H240"]),
        "sigma_range": np.asarray(metrics["sigma_range_H60_H240"]),
        "fraction_at_or_below_0p98": np.asarray(
            metrics["fraction_at_or_below_0p98"]
        ),
    }
    feasible = bool(_feasible_mask(array_metrics, gate))
    metrics["feasible"] = feasible
    return metrics


def _selection_stage(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    i1_manifest_path: Path,
    metadata: dict[str, dict[str, object]],
    rho_support: list[float],
    horizons: list[float],
    workload: dict[str, float],
    latency_scales: np.ndarray,
    cost_scales: np.ndarray,
    diagnostic_horizons: list[float],
    output: Path,
) -> None:
    surrogates, execution_fraction, hidden_provenance = _validate_hidden_model(
        contract,
        phase1_config_path=phase1_config_path,
    )
    graph_spec = build_g2_public_graph_spec()
    validate_g2_public_graph_spec(graph_spec)

    step0 = dict(contract["step0_calibration"])
    seeds = _seed_bank(
        step0["selection_seed_start"],
        step0["selection_seed_end_inclusive"],
        step0["selection_n_trajectories"],
        "G2 Step-0 selection",
    )

    public_condition_path = output / "m2_g2_public_condition_manifest_v1.json"
    public_condition_payload = {
        **graph_spec,
        "g2_contract_sha256": _sha256(contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
    }
    _write_json(public_condition_path, public_condition_payload)

    base_regions = _base_regions(metadata, rho_support)
    base_regions_path = output / "m2_g2_step0_base_regions.csv"
    base_regions.to_csv(base_regions_path, index=False)

    ledger_path = output / "m2_g2_step0_selection_whitebox_ledger.csv"
    ledger, reused = _generate_or_load_ledger(
        path=ledger_path,
        label="G2-Step0-selection",
        surrogates=surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(hidden_provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    gate = dict(step0["selection_feasibility_gate_per_rho"])
    all_diagnostics: list[pd.DataFrame] = []
    selected_rows: list[dict[str, Any]] = []
    selected_curves: list[pd.DataFrame] = []

    for rho in rho_support:
        rec = base_regions[
            np.isclose(
                base_regions["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
        ].iloc[0]
        base = AdmissibilityBoundary(
            l_max=float(rec["base_l_max"]),
            c_max=float(rec["base_c_max"]),
            q_min=float(rec["base_q_min"]),
        )
        print(
            f"G2-Step0 candidate grid rho={rho:g} "
            f"n={len(latency_scales) * len(cost_scales)}",
            flush=True,
        )
        sigma_cube = _candidate_sigma_cube(
            ledger,
            base=base,
            rho=float(rho),
            latency_scales=latency_scales,
            cost_scales=cost_scales,
            horizons=diagnostic_horizons,
        )
        diagnostics = _candidate_diagnostics(
            rho=float(rho),
            base=base,
            latency_scales=latency_scales,
            cost_scales=cost_scales,
            sigma_cube=sigma_cube,
            gate=gate,
        )
        all_diagnostics.append(diagnostics)

        selected = _select_candidate(diagnostics, float(rho))
        boundary = relax_g2_boundary(
            base,
            latency_scale=float(selected["latency_scale"]),
            cost_scale=float(selected["cost_scale"]),
        )
        canonical = _canonical_curve(
            ledger,
            boundary=boundary,
            rho=float(rho),
            horizons=horizons,
            workload=workload,
            column="sigma_selection",
        )
        canonical.insert(0, "rho_global", float(rho))
        canonical["A_G_l_max"] = float(boundary.l_max)
        canonical["A_G_c_max"] = float(boundary.c_max)
        canonical["A_G_q_min"] = float(boundary.q_min)
        selected_curves.append(canonical)

        canonical_metrics = _summarize_curve_gate(
            canonical,
            diagnostic_horizons=diagnostic_horizons,
            sigma_column="sigma_selection",
            gate=gate,
        )
        if not canonical_metrics["feasible"]:
            raise RuntimeError(
                f"rho={rho:g}: vectorized selected candidate does not pass canonical SLA evaluation"
            )
        for key in (
            "sigma_min_H60_H240",
            "sigma_mean_H60_H240",
            "sigma_H240",
            "sigma_range_H60_H240",
            "fraction_at_or_below_0p98",
        ):
            if abs(float(selected[key]) - float(canonical_metrics[key])) > TOL:
                raise RuntimeError(
                    f"rho={rho:g}: candidate-grid and canonical SLA metric disagree for {key}"
                )

        selected_rows.append(
            {
                "rho_global": float(rho),
                "base_l_max": float(base.l_max),
                "base_c_max": float(base.c_max),
                "base_q_min": float(base.q_min),
                "latency_scale": float(selected["latency_scale"]),
                "cost_scale": float(selected["cost_scale"]),
                "A_G_l_max": float(boundary.l_max),
                "A_G_c_max": float(boundary.c_max),
                "A_G_q_min": float(boundary.q_min),
                "expansion_distance": float(selected["expansion_distance"]),
                **canonical_metrics,
            }
        )

    diagnostics_table = pd.concat(all_diagnostics, ignore_index=True)
    diagnostics_path = output / "m2_g2_step0_selection_candidate_diagnostics.csv"
    diagnostics_table.to_csv(diagnostics_path, index=False)

    selected_table = pd.DataFrame(selected_rows).sort_values("rho_global")
    selected_path = output / "m2_g2_step0_selected_regions_from_selection.csv"
    selected_table.to_csv(selected_path, index=False)

    curves_table = pd.concat(selected_curves, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    )
    curves_path = output / "m2_g2_step0_selected_selection_curves.csv"
    curves_table.to_csv(curves_path, index=False)

    manifest = {
        "status": SELECTION_STATUS,
        "condition_id": G2_CONDITION_ID,
        "selection_only": True,
        "confirmation_whitebox_generated": False,
        "confirmation_whitebox_read": False,
        "prediction_methods_run": False,
        "M0_read_or_run": False,
        "M1_read_or_run": False,
        "M2_read_or_run": False,
        "selection_seed_start": int(seeds[0]),
        "selection_seed_end_inclusive": int(seeds[-1]),
        "n_selection_trajectories": len(seeds),
        "candidate_grid": {
            "n_latency_scales": int(len(latency_scales)),
            "n_cost_scales": int(len(cost_scales)),
            "n_candidates_per_rho": int(len(latency_scales) * len(cost_scales)),
            "n_total_candidate_rho_pairs": int(
                len(rho_support) * len(latency_scales) * len(cost_scales)
            ),
        },
        "diagnostic_horizons": [float(h) for h in diagnostic_horizons],
        "hidden_model_provenance": hidden_provenance,
        "g2_contract_sha256": _sha256(contract_path),
        "phase1_config_sha256": _sha256(phase1_config_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "g2_public_adapter_sha256": _sha256(HERE / "m2_g2_public_adapter.py"),
        "g2_simulator_sha256": _sha256(HERE / "m2_g2_graph_simulator.py"),
        "g2_calibration_runner_sha256": _sha256(Path(__file__).resolve()),
        "public_condition_manifest_sha256": _sha256(public_condition_path),
        "base_regions_sha256": _sha256(base_regions_path),
        "selection_ledger_sha256": _sha256(ledger_path),
        "candidate_diagnostics_sha256": _sha256(diagnostics_path),
        "selected_regions_sha256": _sha256(selected_path),
        "selected_selection_curves_sha256": _sha256(curves_path),
        "checkpoint_reused": bool(reused),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": (
            "Run --confirm-and-freeze. It must validate this exact selection freeze, "
            "generate fresh seeds 32100..32199, evaluate only these selected regions, "
            "and freeze A_G2 only if all gates and nesting pass."
        ),
    }
    manifest_path = output / "m2_g2_step0_selection_freeze_manifest_v1.json"
    _write_json(manifest_path, manifest)

    print("M2_G2_STEP0_SELECTION_FROZEN_BEFORE_CONFIRMATION_PASS")
    print("\nSELECTED_G2_REGIONS_FROM_SELECTION")
    print(selected_table.to_string(index=False))
    print(f"manifest={manifest_path}")


def _validate_selection_freeze(
    *,
    contract_path: Path,
    phase1_config_path: Path,
    i1_manifest_path: Path,
    output: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    manifest_path = output / "m2_g2_step0_selection_freeze_manifest_v1.json"
    if not manifest_path.exists():
        raise RuntimeError("G2 Step-0 selection freeze is absent; run --selection-only first")
    manifest = _read_json(manifest_path)
    if manifest.get("status") != SELECTION_STATUS:
        raise RuntimeError("unexpected G2 Step-0 selection-freeze status")
    if bool(manifest.get("confirmation_whitebox_generated")) or bool(
        manifest.get("confirmation_whitebox_read")
    ):
        raise RuntimeError("G2 selection freeze claims confirmation evidence existed")
    if bool(manifest.get("prediction_methods_run")):
        raise RuntimeError("G2 selection freeze claims prediction methods already ran")

    current_hashes = {
        "g2_contract_sha256": _sha256(contract_path),
        "phase1_config_sha256": _sha256(phase1_config_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "g2_public_adapter_sha256": _sha256(HERE / "m2_g2_public_adapter.py"),
        "g2_simulator_sha256": _sha256(HERE / "m2_g2_graph_simulator.py"),
        "g2_calibration_runner_sha256": _sha256(Path(__file__).resolve()),
        "public_condition_manifest_sha256": _sha256(
            output / "m2_g2_public_condition_manifest_v1.json"
        ),
        "base_regions_sha256": _sha256(output / "m2_g2_step0_base_regions.csv"),
        "selection_ledger_sha256": _sha256(
            output / "m2_g2_step0_selection_whitebox_ledger.csv"
        ),
        "candidate_diagnostics_sha256": _sha256(
            output / "m2_g2_step0_selection_candidate_diagnostics.csv"
        ),
        "selected_regions_sha256": _sha256(
            output / "m2_g2_step0_selected_regions_from_selection.csv"
        ),
        "selected_selection_curves_sha256": _sha256(
            output / "m2_g2_step0_selected_selection_curves.csv"
        ),
    }
    for key, actual in current_hashes.items():
        if str(manifest.get(key)) != str(actual):
            raise RuntimeError(f"G2 Step-0 selection-freeze hash changed: {key}")

    selected = pd.read_csv(
        output / "m2_g2_step0_selected_regions_from_selection.csv"
    )
    if len(selected) != 5 or int(selected["rho_global"].nunique()) != 5:
        raise RuntimeError("G2 selection freeze must contain exactly five rho regions")
    if not selected["feasible"].astype(bool).all():
        raise RuntimeError("G2 selection freeze contains a non-feasible selected region")
    return manifest, selected


def _confirmation_stage(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    i1_manifest_path: Path,
    metadata: dict[str, dict[str, object]],
    rho_support: list[float],
    horizons: list[float],
    workload: dict[str, float],
    diagnostic_horizons: list[float],
    output: Path,
) -> None:
    selection_manifest, selected = _validate_selection_freeze(
        contract_path=contract_path,
        phase1_config_path=phase1_config_path,
        i1_manifest_path=i1_manifest_path,
        output=output,
    )
    surrogates, execution_fraction, hidden_provenance = _validate_hidden_model(
        contract,
        phase1_config_path=phase1_config_path,
    )
    graph_spec = build_g2_public_graph_spec()
    validate_g2_public_graph_spec(graph_spec)

    step0 = dict(contract["step0_calibration"])
    seeds = _seed_bank(
        step0["confirmation_seed_start"],
        step0["confirmation_seed_end_inclusive"],
        step0["confirmation_n_trajectories"],
        "G2 Step-0 confirmation",
    )
    ledger_path = output / "m2_g2_step0_confirmation_whitebox_ledger.csv"
    ledger, reused = _generate_or_load_ledger(
        path=ledger_path,
        label="G2-Step0-confirmation",
        surrogates=surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(hidden_provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    gate = dict(step0["selection_feasibility_gate_per_rho"])
    curves: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for rho in rho_support:
        row = selected[
            np.isclose(
                selected["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
        ]
        if len(row) != 1:
            raise RuntimeError(f"rho={rho:g}: selection freeze does not contain one region")
        rec = row.iloc[0]
        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = _canonical_curve(
            ledger,
            boundary=boundary,
            rho=float(rho),
            horizons=horizons,
            workload=workload,
            column="sigma_confirmation",
        )
        curve.insert(0, "rho_global", float(rho))
        curve["A_G_l_max"] = float(boundary.l_max)
        curve["A_G_c_max"] = float(boundary.c_max)
        curve["A_G_q_min"] = float(boundary.q_min)
        curves.append(curve)
        metrics = _summarize_curve_gate(
            curve,
            diagnostic_horizons=diagnostic_horizons,
            sigma_column="sigma_confirmation",
            gate=gate,
        )
        summary_rows.append(
            {
                "rho_global": float(rho),
                "latency_scale": float(rec["latency_scale"]),
                "cost_scale": float(rec["cost_scale"]),
                "A_G_l_max": float(boundary.l_max),
                "A_G_c_max": float(boundary.c_max),
                "A_G_q_min": float(boundary.q_min),
                **metrics,
            }
        )

    curves_table = pd.concat(curves, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    )
    curves_path = output / "m2_g2_step0_selected_confirmation_curves.csv"
    curves_table.to_csv(curves_path, index=False)

    confirmation = pd.DataFrame(summary_rows).sort_values("rho_global").reset_index(drop=True)
    confirmation_path = output / "m2_g2_step0_confirmation_summary.csv"
    confirmation.to_csv(confirmation_path, index=False)

    all_confirmation_pass = bool(confirmation["feasible"].astype(bool).all())

    nesting_cfg = dict(step0["nesting_check_after_confirmation"])
    l_values = confirmation["A_G_l_max"].astype(float).to_numpy()
    c_values = confirmation["A_G_c_max"].astype(float).to_numpy()
    q_values = confirmation["A_G_q_min"].astype(float).to_numpy()
    nesting_latency = bool(np.all(np.diff(l_values) >= -TOL))
    nesting_cost = bool(np.all(np.diff(c_values) >= -TOL))
    nesting_quality = bool(np.all(np.diff(q_values) >= -TOL))
    nesting_pass = bool(nesting_latency and nesting_cost and nesting_quality)

    selected_frozen_path = output / "m2_g2_step0_selected_regions_frozen.csv"
    if all_confirmation_pass and nesting_pass:
        merged = selected.drop(columns=["feasible"], errors="ignore").merge(
            confirmation.add_prefix("confirmation_").rename(
                columns={"confirmation_rho_global": "rho_global"}
            ),
            on="rho_global",
            how="inner",
            validate="one_to_one",
        )
        merged.insert(
            len(merged.columns),
            "step0_calibration_pass",
            True,
        )
        merged.to_csv(selected_frozen_path, index=False)

    calibration_pass = bool(all_confirmation_pass and nesting_pass)
    final_manifest = {
        "status": (
            CALIBRATION_COMPLETE_STATUS
            if calibration_pass
            else CALIBRATION_FAILED_STATUS
        ),
        "condition_id": G2_CONDITION_ID,
        "calibration_pass": calibration_pass,
        "selection_frozen_before_confirmation": True,
        "selection_freeze_manifest_sha256": _sha256(
            output / "m2_g2_step0_selection_freeze_manifest_v1.json"
        ),
        "selection_seed_start": int(selection_manifest["selection_seed_start"]),
        "selection_seed_end_inclusive": int(
            selection_manifest["selection_seed_end_inclusive"]
        ),
        "confirmation_seed_start": int(seeds[0]),
        "confirmation_seed_end_inclusive": int(seeds[-1]),
        "n_confirmation_trajectories": len(seeds),
        "selection_and_confirmation_independent": True,
        "confirmation_reselection_performed": False,
        "M0_read_or_run": False,
        "M1_read_or_run": False,
        "M2_read_or_run": False,
        "all_five_confirmation_gates_pass": all_confirmation_pass,
        "nesting": {
            "required": bool(nesting_cfg["required"]),
            "latency_nondecreasing": nesting_latency,
            "cost_nondecreasing": nesting_cost,
            "quality_nondecreasing_or_equal": nesting_quality,
            "pass": nesting_pass,
        },
        "hidden_model_provenance": hidden_provenance,
        "g2_contract_sha256": _sha256(contract_path),
        "phase1_config_sha256": _sha256(phase1_config_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "g2_public_adapter_sha256": _sha256(HERE / "m2_g2_public_adapter.py"),
        "g2_simulator_sha256": _sha256(HERE / "m2_g2_graph_simulator.py"),
        "g2_calibration_runner_sha256": _sha256(Path(__file__).resolve()),
        "selection_ledger_sha256": _sha256(
            output / "m2_g2_step0_selection_whitebox_ledger.csv"
        ),
        "confirmation_ledger_sha256": _sha256(ledger_path),
        "candidate_diagnostics_sha256": _sha256(
            output / "m2_g2_step0_selection_candidate_diagnostics.csv"
        ),
        "selected_from_selection_sha256": _sha256(
            output / "m2_g2_step0_selected_regions_from_selection.csv"
        ),
        "selected_selection_curves_sha256": _sha256(
            output / "m2_g2_step0_selected_selection_curves.csv"
        ),
        "confirmation_summary_sha256": _sha256(confirmation_path),
        "selected_confirmation_curves_sha256": _sha256(curves_path),
        "selected_regions_frozen_sha256": (
            _sha256(selected_frozen_path) if calibration_pass else None
        ),
        "checkpoint_reused": bool(reused),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": (
            "Calibration passed. Implement blind G2 M0/M1/M2 prediction on seeds "
            "33000..33099 using only the frozen selected A_G2 battery; freeze all "
            "prediction artifacts before generating final WB seeds 34000..34099."
            if calibration_pass
            else
            "Calibration failed under the frozen G2 contract. Do not run G2 prediction. "
            "A separately named G2b contract is required for any redesigned calibration."
        ),
    }
    manifest_path = output / "m2_g2_step0_calibration_manifest_v1.json"
    _write_json(manifest_path, final_manifest)

    print("\nG2_STEP0_CONFIRMATION_SUMMARY")
    print(confirmation.to_string(index=False))
    print(
        "\nNESTING "
        f"latency={nesting_latency} cost={nesting_cost} "
        f"quality={nesting_quality} pass={nesting_pass}"
    )
    if calibration_pass:
        print("M2_G2_STEP0_CALIBRATION_FROZEN_PASS")
        print(f"frozen_regions={selected_frozen_path}")
    else:
        print("M2_G2_STEP0_CALIBRATION_FAIL")
    print(f"manifest={manifest_path}")


def _prepare(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    i1_manifest_path: Path,
    metadata: dict[str, dict[str, object]],
    rho_support: list[float],
    workload: dict[str, float],
    latency_scales: np.ndarray,
    cost_scales: np.ndarray,
    diagnostic_horizons: list[float],
) -> None:
    _, _, hidden_provenance = _validate_hidden_model(
        contract,
        phase1_config_path=phase1_config_path,
    )
    base = _base_regions(metadata, rho_support)
    print("M2_G2_STEP0_PREPARE_PASS_NO_CALIBRATION_WHITEBOX")
    print(f"condition_id={G2_CONDITION_ID}")
    print(
        "provider_PR_seconds="
        + json.dumps(G2_PROVIDER_PR_SECONDS, sort_keys=True)
    )
    print(
        f"candidate_grid={len(latency_scales)}x{len(cost_scales)}="
        f"{len(latency_scales) * len(cost_scales)} per rho"
    )
    print(
        f"diagnostic_horizons={diagnostic_horizons[0]:g}.."
        f"{diagnostic_horizons[-1]:g} n={len(diagnostic_horizons)}"
    )
    step0 = contract["step0_calibration"]
    print(
        f"selection_seeds={step0['selection_seed_start']}.."
        f"{step0['selection_seed_end_inclusive']}"
    )
    print(
        f"confirmation_seeds={step0['confirmation_seed_start']}.."
        f"{step0['confirmation_seed_end_inclusive']}"
    )
    print("\nG2_BASE_REGIONS")
    print(base.to_string(index=False))
    print("\nHIDDEN_MODEL_PROVENANCE")
    print(json.dumps(hidden_provenance, indent=2))
    print(f"contract_sha256={_sha256(contract_path)}")
    print(f"public_i1_manifest_sha256={_sha256(i1_manifest_path)}")
    print(f"phase1_config_sha256={_sha256(phase1_config_path)}")


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    phase1_config_path = args.phase1_config.resolve()
    i1_manifest_path = args.i1_manifest.resolve()
    contract = _read_json(contract_path)

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(),
        i1_manifest_path,
    )
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    latency_scales, cost_scales, diagnostic_horizons = _validate_contract(
        contract,
        metadata=metadata,
        horizons=horizons,
        rho_support=rho_support,
        workload=workload,
    )

    if args.prepare_only:
        _prepare(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            i1_manifest_path=i1_manifest_path,
            metadata=metadata,
            rho_support=rho_support,
            workload=workload,
            latency_scales=latency_scales,
            cost_scales=cost_scales,
            diagnostic_horizons=diagnostic_horizons,
        )
        print(f"python_wall_seconds={time.perf_counter() - started:.3f}")
        return

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if args.selection_only:
        _selection_stage(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            i1_manifest_path=i1_manifest_path,
            metadata=metadata,
            rho_support=rho_support,
            horizons=horizons,
            workload=workload,
            latency_scales=latency_scales,
            cost_scales=cost_scales,
            diagnostic_horizons=diagnostic_horizons,
            output=output,
        )
        print(f"python_wall_seconds={time.perf_counter() - started:.3f}")
        return

    if args.confirm_and_freeze:
        _confirmation_stage(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            i1_manifest_path=i1_manifest_path,
            metadata=metadata,
            rho_support=rho_support,
            horizons=horizons,
            workload=workload,
            diagnostic_horizons=diagnostic_horizons,
            output=output,
        )
        print(f"python_wall_seconds={time.perf_counter() - started:.3f}")
        return

    raise RuntimeError(
        "choose exactly one stage: --prepare-only, --selection-only, or --confirm-and-freeze"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run frozen G2 Step-0 admissibility-region calibration"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_g2_step0_calibrated_validation_v1.json",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_g2_step0_calibration_v1",
    )
    stages = parser.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only", action="store_true")
    stages.add_argument("--selection-only", action="store_true")
    stages.add_argument("--confirm-and-freeze", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
