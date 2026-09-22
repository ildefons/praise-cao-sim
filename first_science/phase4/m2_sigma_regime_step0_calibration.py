#!/usr/bin/env python3
"""Step-0 calibration for the fixed-graph G0/G1/G2 sigma-regime battery.

Scientific ordering
-------------------
1. --prepare-only validates the frozen design with zero new WB simulation.
2. --selection-only generates one matched-D300 WB ledger on the exact fixed G0
   graph, scans the predeclared scalar query-tightness grid, selects G0/G1/G2
   query regions by WB sigma bands only, and hash-freezes the selections.
3. --confirm-and-freeze uses an independent WB seed bank, evaluates only the
   already-selected 15 rho x regime queries, and freezes the battery if every
   query remains inside its predeclared sigma band.

M0/M1/M2 are never loaded or evaluated during Step 0.
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
for directory in (PHASE1, PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_analytic_composition import AdmissibilityBoundary
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary
from m1_graph_simulator_v2 import (
    execute_one_m1_graph_trajectory,
    validate_public_graph_spec,
)
from run_m1_graph_prediction_v2 import (
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from sla_compliance_analysis import EVENT_TOLERANCE
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json
from m2_g2_step0_calibration import _validate_hidden_model

EXPECTED_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BATTERY_STEP0_V1"
SELECTION_FREEZE_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_SELECTION_V1"
CALIBRATION_PASS_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_CALIBRATION_PASS_V1"
CALIBRATION_FAIL_STATUS = "PHASE4_SIGMA_REGIME_CALIBRATION_FAIL_V1"
TOL = 1e-12


def _scale_grid(spec: dict[str, Any]) -> np.ndarray:
    low = float(spec["minimum"])
    high = float(spec["maximum"])
    step = float(spec["step"])
    if low <= 0 or high < low or step <= 0:
        raise RuntimeError("invalid frozen scale grid")
    n = int(round((high - low) / step))
    grid = low + step * np.arange(n + 1, dtype=float)
    if abs(float(grid[-1]) - high) > 1e-10:
        raise RuntimeError("scale-grid endpoint does not match step")
    return np.round(grid, 12)


def _seed_bank(start: int, end: int, expected_n: int, label: str) -> tuple[int, ...]:
    seeds = tuple(range(int(start), int(end) + 1))
    if len(seeds) != int(expected_n):
        raise RuntimeError(f"{label} seed-bank length mismatch")
    if not seeds:
        raise RuntimeError(f"{label} seed bank is empty")
    return seeds


def _fixed_graph_spec(m0_contract: dict[str, Any]) -> dict[str, Any]:
    if m0_contract.get("status") != "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO":
        raise RuntimeError("unexpected M0 contract status")
    adapter = dict(m0_contract["phase1_benchmark_adapter"])
    spec = {
        "graph": str(adapter["graph"]),
        "network_model": dict(adapter["network_model"]),
        "fixed_service_model": dict(adapter["fixed_service_model"]),
    }
    validate_public_graph_spec(spec)
    if spec["graph"] != "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost":
        raise RuntimeError("logical graph changed")
    net = spec["network_model"]
    if abs(float(net["PR"]) - 0.001) > TOL:
        raise RuntimeError("fixed battery must use exact G0 PR=0.001 s")
    if abs(float(net["BW_mbps"]) - 1000.0) > TOL:
        raise RuntimeError("fixed battery bandwidth changed")
    for key in ("request_bytes", "branch_bytes", "join_bytes"):
        if int(net[key]) != 1000:
            raise RuntimeError(f"fixed G0 field changed: {key}")
    return spec


def _base_regions(
    phase1_config: dict[str, Any],
    metadata: dict[str, dict[str, object]],
    rho_values: list[float],
) -> pd.DataFrame:
    rows = []
    for rho in rho_values:
        local = provider_boundaries_at_region_rho(metadata, float(rho))
        base, breakdown = build_phase1_g0_full_m0_boundary(phase1_config, local)
        rows.append(
            {
                "rho_global": float(rho),
                "base_l_max": float(base.l_max),
                "base_c_max": float(base.c_max),
                "base_q_min": float(base.q_min),
                "fixed_latency_outside_provider": float(
                    breakdown.fixed_latency_outside_provider
                ),
                "fixed_cost_outside_provider": float(
                    breakdown.fixed_cost_outside_provider
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("rho_global").reset_index(drop=True)


def _validate_seed_banks(contract: dict[str, Any]) -> None:
    step0 = dict(contract["step0_calibration"])
    pred = dict(contract["blind_prediction_protocol_after_calibration"])
    final = dict(contract["final_whitebox_evaluation"])
    specs = [
        (
            "selection",
            step0["selection_seed_start"],
            step0["selection_seed_end_inclusive"],
            step0["selection_n_trajectories"],
        ),
        (
            "confirmation",
            step0["confirmation_seed_start"],
            step0["confirmation_seed_end_inclusive"],
            step0["confirmation_n_trajectories"],
        ),
        (
            "prediction",
            pred["prediction_seed_start"],
            pred["prediction_seed_end_inclusive"],
            pred["n_prediction_trajectories_per_variant"],
        ),
        (
            "final",
            final["trajectory_seed_start"],
            final["trajectory_seed_end_inclusive"],
            final["n_trajectories"],
        ),
    ]
    banks = []
    for label, start, end, n in specs:
        bank = set(_seed_bank(start, end, n, label))
        banks.append((label, bank))
    for i, (name_i, bank_i) in enumerate(banks):
        for name_j, bank_j in banks[i + 1 :]:
            if bank_i.intersection(bank_j):
                raise RuntimeError(f"seed banks overlap: {name_i}/{name_j}")


def _validate_common_contract(
    contract: dict[str, Any],
    *,
    horizons: list[float],
    workload: dict[str, float],
) -> tuple[np.ndarray, list[float], dict[str, tuple[float, float, float]]]:
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected sigma-regime contract status")

    freeze = dict(contract["method_freeze"])
    required_true = (
        "I1_unchanged",
        "M0_semantics_unchanged",
        "M1_parameters_unchanged",
        "M2_provider_members_unchanged",
    )
    for key in required_true:
        if not bool(freeze.get(key)):
            raise RuntimeError(f"method freeze false: {key}")
    if bool(freeze["step0_may_read_or_run_M0_M1_M2"]):
        raise RuntimeError("Step-0 predictor firewall is open")
    if int(freeze["M2_joint_members"]) != 27:
        raise RuntimeError("M2 member count changed")
    if str(freeze["M2_member_weight"]) != "1/27":
        raise RuntimeError("M2 weights changed")

    step0 = dict(contract["step0_calibration"])
    window = dict(step0["diagnostic_horizon_window"])
    hmin = float(window["minimum_horizon_seconds"])
    hmax = float(window["maximum_horizon_seconds"])
    diagnostic_horizons = [
        float(h) for h in horizons if hmin - TOL <= float(h) <= hmax + TOL
    ]
    if not diagnostic_horizons:
        raise RuntimeError("empty diagnostic horizon window")
    if abs(diagnostic_horizons[0] - hmin) > TOL:
        raise RuntimeError("diagnostic Hmin not on frozen support")
    if abs(diagnostic_horizons[-1] - hmax) > TOL:
        raise RuntimeError("diagnostic Hmax not on frozen support")
    if abs(float(max(horizons)) - float(workload["horizon_max"])) > TOL:
        raise RuntimeError("I1 Hmax/workload mismatch")

    regimes = dict(step0["regimes"])
    expected_bands = {
        "G0": (0.95, 1.00, 0.975),
        "G1": (0.75, 0.90, 0.825),
        "G2": (0.40, 0.75, 0.575),
    }
    if tuple(regimes.keys()) != ("G0", "G1", "G2"):
        raise RuntimeError("regimes must be ordered G0,G1,G2")
    for name, (low, high, center) in expected_bands.items():
        rec = dict(regimes[name])
        if (
            abs(float(rec["sigma_lower"]) - low) > TOL
            or abs(float(rec["sigma_upper"]) - high) > TOL
            or abs(float(rec["target_center"]) - center) > TOL
        ):
            raise RuntimeError(f"{name} frozen sigma band changed")

    scales = _scale_grid(dict(step0["candidate_family"]["scale_grid"]))
    _validate_seed_banks(contract)
    return scales, diagnostic_horizons, expected_bands


def _generate_or_load_ledger(
    *,
    path: Path,
    label: str,
    provider_surrogates: dict[str, Any],
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
            raise RuntimeError(f"{label} trajectory count mismatch")
        if ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{label} ledger contains duplicate requests")
        print(f"{label}: loaded completed checkpoint ledger", flush=True)
        return ledger, True

    frames: list[pd.DataFrame] = []
    for trajectory, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            one = execute_one_m1_graph_trajectory(
                provider_surrogates=provider_surrogates,
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


def _scaled_boundary(base: AdmissibilityBoundary, scale: float) -> AdmissibilityBoundary:
    s = float(scale)
    if s <= 0.0:
        raise ValueError("query scale must be positive")
    return AdmissibilityBoundary(
        l_max=s * float(base.l_max),
        c_max=s * float(base.c_max),
        q_min=float(base.q_min),
    )


def _candidate_sigma_matrix(
    ledger: pd.DataFrame,
    *,
    base: AdmissibilityBoundary,
    rho: float,
    scales: np.ndarray,
    horizons: list[float],
) -> np.ndarray:
    """Exact Step-0 sigma for the one-dimensional scalar query family.

    Output shape is (n_scales, n_horizons). The request-decision semantics
    match the canonical SLA implementation used elsewhere in the benchmark.
    """
    hs = np.asarray(horizons, dtype=float)
    counts = np.zeros((len(scales), len(hs)), dtype=np.int32)
    trajectories = list(ledger.groupby("trajectory", sort=True))
    if not trajectories:
        raise RuntimeError("candidate evaluator received no trajectories")

    for _, frame in trajectories:
        ordered = frame.sort_values(["emission", "request_id"])
        emission = ordered["emission"].astype(float).to_numpy()
        completion = pd.to_numeric(
            ordered["completion"], errors="coerce"
        ).to_numpy(dtype=float)
        cost = pd.to_numeric(ordered["C"], errors="coerce").to_numpy(dtype=float)
        quality = pd.to_numeric(ordered["Q"], errors="coerce").to_numpy(dtype=float)
        finite_completion = np.isfinite(completion)

        for si, scale in enumerate(scales):
            l_threshold = float(base.l_max) * float(scale)
            c_threshold = float(base.c_max) * float(scale)
            deadline = emission + l_threshold
            in_time = finite_completion & (
                completion <= deadline + EVENT_TOLERANCE
            )
            decision_time = np.where(in_time, completion, deadline)
            decided = np.searchsorted(
                np.sort(decision_time),
                hs + EVENT_TOLERANCE,
                side="right",
            ).astype(np.int32)

            eligible = (
                in_time
                & np.isfinite(cost)
                & np.isfinite(quality)
                & (quality >= float(base.q_min))
                & (cost <= c_threshold + EVENT_TOLERANCE)
            )
            compliant_times = np.sort(completion[eligible])
            compliant = np.searchsorted(
                compliant_times,
                hs + EVENT_TOLERANCE,
                side="right",
            ).astype(np.int32)

            passing = np.zeros(len(hs), dtype=bool)
            zero = decided == 0
            passing[zero] = bool(1.0 + EVENT_TOLERANCE >= float(rho))
            nonzero = ~zero
            if np.any(nonzero):
                fraction = compliant[nonzero].astype(float) / decided[nonzero].astype(float)
                passing[nonzero] = (
                    fraction + EVENT_TOLERANCE >= float(rho)
                )
            counts[si, :] += passing.astype(np.int32)

    return counts.astype(float) / float(len(trajectories))


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


def _validate_matrix_sentinels(
    ledger: pd.DataFrame,
    *,
    base: AdmissibilityBoundary,
    rho: float,
    scales: np.ndarray,
    horizons: list[float],
    matrix: np.ndarray,
    workload: dict[str, float],
) -> None:
    sentinel_indices = (0, len(scales) // 2, len(scales) - 1)
    for si in sentinel_indices:
        boundary = _scaled_boundary(base, float(scales[si]))
        canonical = _canonical_curve(
            ledger,
            boundary=boundary,
            rho=float(rho),
            horizons=horizons,
            workload=workload,
            column="sigma_sentinel",
        )
        expected = canonical["sigma_sentinel"].astype(float).to_numpy()
        actual = matrix[si, :].astype(float)
        if len(expected) != len(actual) or not np.allclose(
            expected, actual, atol=TOL, rtol=0.0
        ):
            raise RuntimeError(
                f"rho={rho:g}: scalar grid evaluator disagrees with canonical "
                f"SLA semantics at scale={scales[si]:g}"
            )


def _candidate_diagnostics(
    *,
    rho: float,
    regime: str,
    base: AdmissibilityBoundary,
    scales: np.ndarray,
    matrix: np.ndarray,
    band: tuple[float, float, float],
) -> pd.DataFrame:
    low, high, center = band
    rows = []
    for si, scale in enumerate(scales):
        sigma = matrix[si, :].astype(float)
        sigma_min = float(np.min(sigma))
        sigma_max = float(np.max(sigma))
        sigma_mean = float(np.mean(sigma))
        feasible = bool(
            np.all(sigma >= low - TOL) and np.all(sigma <= high + TOL)
        )
        boundary_margin = float(
            min(sigma_min - low, high - sigma_max)
        )
        rows.append(
            {
                "rho_global": float(rho),
                "regime": str(regime),
                "scale": float(scale),
                "A_G_l_max": float(base.l_max) * float(scale),
                "A_G_c_max": float(base.c_max) * float(scale),
                "A_G_q_min": float(base.q_min),
                "sigma_min_H60_H240": sigma_min,
                "sigma_mean_H60_H240": sigma_mean,
                "sigma_max_H60_H240": sigma_max,
                "sigma_H60": float(sigma[0]),
                "sigma_H240": float(sigma[-1]),
                "distance_mean_to_target": abs(sigma_mean - center),
                "minimum_margin_to_band_edges": boundary_margin,
                "distance_log_scale_to_base": abs(math.log(float(scale))),
                "feasible": feasible,
            }
        )
    return pd.DataFrame(rows)


def _select_candidate(
    diagnostics: pd.DataFrame,
    *,
    rho: float,
    regime: str,
) -> pd.Series:
    feasible = diagnostics[diagnostics["feasible"].astype(bool)].copy()
    if feasible.empty:
        raise RuntimeError(
            f"rho={rho:g} regime={regime}: no feasible scalar query candidate"
        )
    feasible["negative_margin"] = -feasible["minimum_margin_to_band_edges"].astype(float)
    ordered = feasible.sort_values(
        [
            "distance_mean_to_target",
            "negative_margin",
            "distance_log_scale_to_base",
            "scale",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    return ordered.iloc[0]


def _selection_stage(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    m0_contract_path: Path,
    i1_manifest_path: Path,
    metadata: dict[str, dict[str, object]],
    rho_values: list[float],
    horizons: list[float],
    workload: dict[str, float],
    scales: np.ndarray,
    diagnostic_horizons: list[float],
    bands: dict[str, tuple[float, float, float]],
    output: Path,
) -> None:
    provider_surrogates, execution_fraction, provenance = _validate_hidden_model(
        contract, phase1_config_path=phase1_config_path
    )
    graph_spec = _fixed_graph_spec(_read_json(m0_contract_path))
    phase1_config = _read_json(phase1_config_path)
    base_regions = _base_regions(phase1_config, metadata, rho_values)

    output.mkdir(parents=True, exist_ok=True)
    public_condition_path = output / "sigma_regime_public_condition_manifest_v1.json"
    _write_json(
        public_condition_path,
        {
            "status": "FIXED_G0_GRAPH_FOR_SIGMA_REGIME_BATTERY_V1",
            "graph_spec": graph_spec,
            "graph_changed_across_regimes": False,
            "provider_process": provenance["canonical_provider_process"],
            "provider_process_sha256": provenance["provider_process_sha256"],
            "contract_sha256": _sha256(contract_path),
            "m0_contract_sha256": _sha256(m0_contract_path),
            "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        },
    )
    base_path = output / "sigma_regime_step0_base_regions.csv"
    base_regions.to_csv(base_path, index=False)

    step0 = dict(contract["step0_calibration"])
    seeds = _seed_bank(
        step0["selection_seed_start"],
        step0["selection_seed_end_inclusive"],
        step0["selection_n_trajectories"],
        "selection",
    )
    ledger_path = output / "sigma_regime_step0_selection_whitebox_ledger.csv"
    ledger, reused = _generate_or_load_ledger(
        path=ledger_path,
        label="Sigma-regime-Step0-selection",
        provider_surrogates=provider_surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    all_diagnostics: list[pd.DataFrame] = []
    selected_rows: list[dict[str, Any]] = []
    selected_curves: list[pd.DataFrame] = []
    failures: list[str] = []

    for rho in rho_values:
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
            f"Sigma-regime candidate grid rho={rho:g} n_scales={len(scales)}",
            flush=True,
        )
        matrix = _candidate_sigma_matrix(
            ledger,
            base=base,
            rho=float(rho),
            scales=scales,
            horizons=diagnostic_horizons,
        )
        _validate_matrix_sentinels(
            ledger,
            base=base,
            rho=float(rho),
            scales=scales,
            horizons=diagnostic_horizons,
            matrix=matrix,
            workload=workload,
        )

        rho_selected: dict[str, pd.Series] = {}
        for regime in ("G0", "G1", "G2"):
            diagnostics = _candidate_diagnostics(
                rho=float(rho),
                regime=regime,
                base=base,
                scales=scales,
                matrix=matrix,
                band=bands[regime],
            )
            all_diagnostics.append(diagnostics)
            try:
                chosen = _select_candidate(
                    diagnostics, rho=float(rho), regime=regime
                )
            except RuntimeError as exc:
                failures.append(str(exc))
                print(str(exc), flush=True)
                continue
            rho_selected[regime] = chosen
            boundary = _scaled_boundary(base, float(chosen["scale"]))
            canonical = _canonical_curve(
                ledger,
                boundary=boundary,
                rho=float(rho),
                horizons=horizons,
                workload=workload,
                column="sigma_selection",
            )
            canonical.insert(0, "regime", regime)
            canonical.insert(0, "rho_global", float(rho))
            canonical["scale"] = float(chosen["scale"])
            canonical["A_G_l_max"] = float(boundary.l_max)
            canonical["A_G_c_max"] = float(boundary.c_max)
            canonical["A_G_q_min"] = float(boundary.q_min)
            selected_curves.append(canonical)
            selected_rows.append(
                {
                    **{
                        key: chosen[key]
                        for key in chosen.index
                        if key != "negative_margin"
                    },
                    "selection_seed_start": int(seeds[0]),
                    "selection_seed_end_inclusive": int(seeds[-1]),
                }
            )
            print(
                f"  rho={rho:g} {regime}: scale={float(chosen['scale']):.3f} "
                f"mean={float(chosen['sigma_mean_H60_H240']):.3f} "
                f"range=[{float(chosen['sigma_min_H60_H240']):.3f},"
                f"{float(chosen['sigma_max_H60_H240']):.3f}]",
                flush=True,
            )

        if set(rho_selected) == {"G0", "G1", "G2"}:
            s0 = float(rho_selected["G0"]["scale"])
            s1 = float(rho_selected["G1"]["scale"])
            s2 = float(rho_selected["G2"]["scale"])
            if not (s2 + TOL < s1 and s1 + TOL < s0):
                failures.append(
                    f"rho={rho:g}: cross-regime scale ordering failed "
                    f"(G2={s2}, G1={s1}, G0={s0})"
                )

    diagnostics_frame = (
        pd.concat(all_diagnostics, ignore_index=True)
        if all_diagnostics
        else pd.DataFrame()
    )
    diagnostics_path = output / "sigma_regime_step0_selection_candidate_diagnostics.csv"
    diagnostics_frame.to_csv(diagnostics_path, index=False)

    selected_frame = pd.DataFrame(selected_rows)
    selected_path = output / "sigma_regime_step0_selected_regions_from_selection.csv"
    selected_frame.to_csv(selected_path, index=False)

    curves_frame = (
        pd.concat(selected_curves, ignore_index=True)
        if selected_curves
        else pd.DataFrame()
    )
    curves_path = output / "sigma_regime_step0_selected_selection_curves.csv"
    curves_frame.to_csv(curves_path, index=False)

    if failures or len(selected_frame) != len(rho_values) * 3:
        failure_path = output / "sigma_regime_step0_selection_failure_manifest_v1.json"
        _write_json(
            failure_path,
            {
                "status": CALIBRATION_FAIL_STATUS,
                "stage": "selection",
                "failures": failures,
                "n_selected": int(len(selected_frame)),
                "expected_selected": int(len(rho_values) * 3),
                "selection_ledger_sha256": _sha256(ledger_path),
                "candidate_diagnostics_sha256": _sha256(diagnostics_path),
                "contract_sha256": _sha256(contract_path),
                "git_commit": _git_head(FIRST_SCIENCE.parent),
            },
        )
        raise RuntimeError(
            "SIGMA_REGIME_STEP0_SELECTION_FAIL: " + " | ".join(failures)
        )

    freeze_path = output / "sigma_regime_step0_selection_freeze_manifest_v1.json"
    _write_json(
        freeze_path,
        {
            "status": SELECTION_FREEZE_STATUS,
            "contract_sha256": _sha256(contract_path),
            "public_condition_sha256": _sha256(public_condition_path),
            "base_regions_sha256": _sha256(base_path),
            "selection_ledger_sha256": _sha256(ledger_path),
            "candidate_diagnostics_sha256": _sha256(diagnostics_path),
            "selected_regions_sha256": _sha256(selected_path),
            "selected_curves_sha256": _sha256(curves_path),
            "provider_process_sha256": provenance["provider_process_sha256"],
            "selection_seed_start": int(seeds[0]),
            "selection_seed_end_inclusive": int(seeds[-1]),
            "n_selected_queries": int(len(selected_frame)),
            "selection_ledger_reused": bool(reused),
            "M0_M1_M2_used": False,
            "git_commit": _git_head(FIRST_SCIENCE.parent),
        },
    )
    print("SIGMA_REGIME_STEP0_SELECTION_FROZEN_BEFORE_CONFIRMATION_PASS")
    print(f"selected_queries={len(selected_frame)}")
    print(f"selection_freeze={freeze_path}")


def _validate_selection_freeze(
    *,
    output: Path,
    contract_path: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    freeze_path = output / "sigma_regime_step0_selection_freeze_manifest_v1.json"
    if not freeze_path.exists():
        raise RuntimeError("selection freeze is absent; run --selection-only first")
    freeze = _read_json(freeze_path)
    if freeze.get("status") != SELECTION_FREEZE_STATUS:
        raise RuntimeError("unexpected selection-freeze status")
    selected_path = output / "sigma_regime_step0_selected_regions_from_selection.csv"
    diagnostics_path = output / "sigma_regime_step0_selection_candidate_diagnostics.csv"
    ledger_path = output / "sigma_regime_step0_selection_whitebox_ledger.csv"
    checks = {
        "contract_sha256": _sha256(contract_path),
        "selection_ledger_sha256": _sha256(ledger_path),
        "candidate_diagnostics_sha256": _sha256(diagnostics_path),
        "selected_regions_sha256": _sha256(selected_path),
    }
    mismatches = [
        key for key, value in checks.items()
        if str(freeze.get(key)) != str(value)
    ]
    if mismatches:
        raise RuntimeError(
            "selection artifacts changed after freeze: " + ", ".join(mismatches)
        )
    selected = pd.read_csv(selected_path)
    if len(selected) != int(freeze["n_selected_queries"]):
        raise RuntimeError("selected query count changed after freeze")
    return selected, freeze


def _confirmation_stage(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    m0_contract_path: Path,
    rho_values: list[float],
    horizons: list[float],
    workload: dict[str, float],
    diagnostic_horizons: list[float],
    bands: dict[str, tuple[float, float, float]],
    output: Path,
) -> None:
    selected, selection_freeze = _validate_selection_freeze(
        output=output, contract_path=contract_path
    )
    provider_surrogates, execution_fraction, provenance = _validate_hidden_model(
        contract, phase1_config_path=phase1_config_path
    )
    if str(provenance["provider_process_sha256"]) != str(
        selection_freeze["provider_process_sha256"]
    ):
        raise RuntimeError("provider process changed after selection freeze")
    graph_spec = _fixed_graph_spec(_read_json(m0_contract_path))

    step0 = dict(contract["step0_calibration"])
    seeds = _seed_bank(
        step0["confirmation_seed_start"],
        step0["confirmation_seed_end_inclusive"],
        step0["confirmation_n_trajectories"],
        "confirmation",
    )
    ledger_path = output / "sigma_regime_step0_confirmation_whitebox_ledger.csv"
    ledger, reused = _generate_or_load_ledger(
        path=ledger_path,
        label="Sigma-regime-Step0-confirmation",
        provider_surrogates=provider_surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    curve_rows = []
    summary_rows = []
    failures = []
    diagnostic_set = np.asarray(diagnostic_horizons, dtype=float)

    for _, rec in selected.sort_values(["rho_global", "regime"]).iterrows():
        rho = float(rec["rho_global"])
        regime = str(rec["regime"])
        scale = float(rec["scale"])
        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = _canonical_curve(
            ledger,
            boundary=boundary,
            rho=rho,
            horizons=horizons,
            workload=workload,
            column="sigma_confirmation",
        )
        curve.insert(0, "regime", regime)
        curve.insert(0, "rho_global", rho)
        curve["scale"] = scale
        curve["A_G_l_max"] = float(boundary.l_max)
        curve["A_G_c_max"] = float(boundary.c_max)
        curve["A_G_q_min"] = float(boundary.q_min)
        curve_rows.append(curve)

        mask = np.isclose(
            curve["horizon"].astype(float).to_numpy()[:, None],
            diagnostic_set[None, :],
            atol=TOL,
            rtol=0.0,
        ).any(axis=1)
        diag = curve.loc[mask].sort_values("horizon")
        if len(diag) != len(diagnostic_horizons):
            raise RuntimeError("confirmation curve lacks diagnostic horizons")
        sigma = diag["sigma_confirmation"].astype(float).to_numpy()
        low, high, center = bands[regime]
        passed = bool(
            np.all(sigma >= low - TOL) and np.all(sigma <= high + TOL)
        )
        if not passed:
            failures.append(
                f"rho={rho:g} regime={regime}: confirmation left "
                f"[{low},{high}] with observed "
                f"[{float(np.min(sigma))},{float(np.max(sigma))}]"
            )
        summary_rows.append(
            {
                "rho_global": rho,
                "regime": regime,
                "scale": scale,
                "sigma_min_H60_H240": float(np.min(sigma)),
                "sigma_mean_H60_H240": float(np.mean(sigma)),
                "sigma_max_H60_H240": float(np.max(sigma)),
                "sigma_H60": float(sigma[0]),
                "sigma_H240": float(sigma[-1]),
                "target_center": center,
                "band_lower": low,
                "band_upper": high,
                "confirmation_pass": passed,
            }
        )

    curves = pd.concat(curve_rows, ignore_index=True)
    curves_path = output / "sigma_regime_step0_selected_confirmation_curves.csv"
    curves.to_csv(curves_path, index=False)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["rho_global", "regime"]
    ).reset_index(drop=True)
    summary_path = output / "sigma_regime_step0_confirmation_summary.csv"
    summary.to_csv(summary_path, index=False)

    selected_frozen_path = output / "sigma_regime_step0_selected_regions_frozen.csv"
    selected.to_csv(selected_frozen_path, index=False)

    manifest_path = output / "sigma_regime_step0_calibration_manifest_v1.json"
    status = CALIBRATION_PASS_STATUS if not failures else CALIBRATION_FAIL_STATUS
    _write_json(
        manifest_path,
        {
            "status": status,
            "contract_sha256": _sha256(contract_path),
            "selection_freeze_sha256": _sha256(
                output / "sigma_regime_step0_selection_freeze_manifest_v1.json"
            ),
            "confirmation_ledger_sha256": _sha256(ledger_path),
            "confirmation_curves_sha256": _sha256(curves_path),
            "confirmation_summary_sha256": _sha256(summary_path),
            "selected_regions_frozen_sha256": _sha256(selected_frozen_path),
            "provider_process_sha256": provenance["provider_process_sha256"],
            "confirmation_seed_start": int(seeds[0]),
            "confirmation_seed_end_inclusive": int(seeds[-1]),
            "n_selected_queries": int(len(selected)),
            "n_confirmation_pass": int(summary["confirmation_pass"].astype(bool).sum()),
            "failures": failures,
            "confirmation_ledger_reused": bool(reused),
            "M0_M1_M2_used": False,
            "git_commit": _git_head(FIRST_SCIENCE.parent),
        },
    )
    if failures:
        print("SIGMA_REGIME_STEP0_CALIBRATION_FAIL")
        print("\n".join(failures))
        raise RuntimeError("Step-0 independent confirmation failed")

    print("SIGMA_REGIME_STEP0_CALIBRATION_FROZEN_PASS")
    print(summary.to_string(index=False))
    print(f"calibration_manifest={manifest_path}")


def _prepare(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    phase1_config_path: Path,
    m0_contract_path: Path,
    i1_manifest_path: Path,
    metadata: dict[str, dict[str, object]],
    rho_values: list[float],
    workload: dict[str, float],
    scales: np.ndarray,
    diagnostic_horizons: list[float],
    bands: dict[str, tuple[float, float, float]],
) -> None:
    phase1_config = _read_json(phase1_config_path)
    graph_spec = _fixed_graph_spec(_read_json(m0_contract_path))
    _, _, provenance = _validate_hidden_model(
        contract, phase1_config_path=phase1_config_path
    )
    if str(provenance["case_id"]) != "D300000000_d0.200":
        raise RuntimeError("provider process is not matched D300")
    if not bool(provenance["matched_i1_provider_process"]):
        raise RuntimeError("hidden provider process is not matched to I1")
    base = _base_regions(phase1_config, metadata, rho_values)

    step0 = contract["step0_calibration"]
    pred = contract["blind_prediction_protocol_after_calibration"]
    final = contract["final_whitebox_evaluation"]
    print("SIGMA_REGIME_STEP0_PREPARE_PASS_NO_WHITEBOX")
    print("graph_changed_across_regimes=false")
    print(f"fixed_graph={graph_spec['graph']}")
    print(f"fixed_PR_seconds={graph_spec['network_model']['PR']}")
    print(f"provider_process={provenance['case_id']}")
    print(f"provider_process_sha256={provenance['provider_process_sha256']}")
    print(f"rho_values={rho_values}")
    print(
        f"diagnostic_horizons={diagnostic_horizons[0]:g}.."
        f"{diagnostic_horizons[-1]:g} n={len(diagnostic_horizons)}"
    )
    print(
        f"scale_grid={float(scales[0]):g}..{float(scales[-1]):g} "
        f"step={float(scales[1]-scales[0]):g} n={len(scales)}"
    )
    print("sigma_bands=" + json.dumps(bands))
    print("\nBASE_G0_GRAPH_REGIONS")
    print(base.to_string(index=False))
    print("\nSEED_BANKS")
    print(
        f"selection={step0['selection_seed_start']}.."
        f"{step0['selection_seed_end_inclusive']}"
    )
    print(
        f"confirmation={step0['confirmation_seed_start']}.."
        f"{step0['confirmation_seed_end_inclusive']}"
    )
    print(
        f"prediction={pred['prediction_seed_start']}.."
        f"{pred['prediction_seed_end_inclusive']}"
    )
    print(
        f"final_WB={final['trajectory_seed_start']}.."
        f"{final['trajectory_seed_end_inclusive']}"
    )
    print("\nHASHES")
    print(f"contract_sha256={_sha256(contract_path)}")
    print(f"m0_contract_sha256={_sha256(m0_contract_path)}")
    print(f"public_i1_manifest_sha256={_sha256(i1_manifest_path)}")


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    phase1_config_path = args.phase1_config.resolve()
    m0_contract_path = args.m0_contract.resolve()
    i1_manifest_path = args.i1_manifest.resolve()
    contract = _read_json(contract_path)

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), i1_manifest_path
    )
    rho_values = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    scales, diagnostic_horizons, bands = _validate_common_contract(
        contract, horizons=horizons, workload=workload
    )

    if args.prepare_only:
        _prepare(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            m0_contract_path=m0_contract_path,
            i1_manifest_path=i1_manifest_path,
            metadata=metadata,
            rho_values=rho_values,
            workload=workload,
            scales=scales,
            diagnostic_horizons=diagnostic_horizons,
            bands=bands,
        )
    elif args.selection_only:
        _selection_stage(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            m0_contract_path=m0_contract_path,
            i1_manifest_path=i1_manifest_path,
            metadata=metadata,
            rho_values=rho_values,
            horizons=horizons,
            workload=workload,
            scales=scales,
            diagnostic_horizons=diagnostic_horizons,
            bands=bands,
            output=args.output.resolve(),
        )
    elif args.confirm_and_freeze:
        _confirmation_stage(
            contract_path=contract_path,
            contract=contract,
            phase1_config_path=phase1_config_path,
            m0_contract_path=m0_contract_path,
            rho_values=rho_values,
            horizons=horizons,
            workload=workload,
            diagnostic_horizons=diagnostic_horizons,
            bands=bands,
            output=args.output.resolve(),
        )
    else:
        raise RuntimeError("choose exactly one Step-0 stage")

    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate fixed-graph three-sigma-regime Step-0 battery"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_sigma_regime_battery_step0_v1.json",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json",
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
        default=HERE / "results" / "sigma_regime_step0_calibration_v1",
    )
    stages = parser.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only", action="store_true")
    stages.add_argument("--selection-only", action="store_true")
    stages.add_argument("--confirm-and-freeze", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
