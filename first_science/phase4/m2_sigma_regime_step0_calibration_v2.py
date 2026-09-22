#!/usr/bin/env python3
"""Robust Step-0 v2 for the fixed-graph three-regime sigma battery.

V1 selection and failed confirmation are explicitly reclassified as development
evidence. V2 pools those 200 trajectories for query selection, then uses a fresh
independent N=200 seed bank (32200..32399) for confirmation. M0/M1/M2 are never
read or run here.
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
from m1_graph_simulator_v2 import execute_one_m1_graph_trajectory
from run_m1_graph_prediction_v2 import _common_workload_contract
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json
from m2_g2_step0_calibration import _validate_hidden_model
from m2_sigma_regime_step0_calibration import (
    _candidate_sigma_matrix,
    _canonical_curve,
    _fixed_graph_spec,
    _scale_grid,
)

EXPECTED_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BATTERY_STEP0_V2"
SELECTION_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_SELECTION_V2"
PASS_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_CALIBRATION_PASS_V2"
FAIL_STATUS = "PHASE4_SIGMA_REGIME_CALIBRATION_FAIL_V2"
TOL = 1e-12


def _bands(contract: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    regimes = dict(contract["step0_calibration"]["regimes"])
    expected = {
        "G0": (0.95, 1.00, 0.975),
        "G1": (0.75, 0.90, 0.825),
        "G2": (0.40, 0.75, 0.575),
    }
    for name, values in expected.items():
        rec = dict(regimes[name])
        actual = (
            float(rec["mean_sigma_lower"]),
            float(rec["mean_sigma_upper"]),
            float(rec["target_center"]),
        )
        if not np.allclose(actual, values, atol=TOL, rtol=0.0):
            raise RuntimeError(f"{name} V2 regime changed")
    return expected


def _diagnostic_horizons(contract: dict[str, Any], horizons: list[float]) -> list[float]:
    window = dict(contract["step0_calibration"]["diagnostic_horizon_window"])
    low = float(window["minimum_horizon_seconds"])
    high = float(window["maximum_horizon_seconds"])
    selected = [float(h) for h in horizons if low - TOL <= float(h) <= high + TOL]
    if not selected or abs(selected[0]-low)>TOL or abs(selected[-1]-high)>TOL:
        raise RuntimeError("V2 diagnostic horizon support mismatch")
    return selected


def _base_regions(
    phase1_config: dict[str, Any],
    metadata: dict[str, dict[str, object]],
    rho_values: list[float],
) -> pd.DataFrame:
    rows = []
    for rho in rho_values:
        local = provider_boundaries_at_region_rho(metadata, float(rho))
        base, _ = build_phase1_g0_full_m0_boundary(phase1_config, local)
        rows.append({
            "rho_global": float(rho),
            "base_l_max": float(base.l_max),
            "base_c_max": float(base.c_max),
            "base_q_min": float(base.q_min),
        })
    return pd.DataFrame(rows).sort_values("rho_global").reset_index(drop=True)


def _load_v1_development_pool(path: Path) -> pd.DataFrame:
    first = path / "sigma_regime_step0_selection_whitebox_ledger.csv"
    second = path / "sigma_regime_step0_confirmation_whitebox_ledger.csv"
    if not first.exists() or not second.exists():
        raise FileNotFoundError(
            "V2 needs both completed V1 development ledgers: " + str(path)
        )
    a = pd.read_csv(first)
    b = pd.read_csv(second)
    expected_a = tuple(range(32000, 32100))
    expected_b = tuple(range(32100, 32200))
    actual_a = tuple(sorted(a["trajectory_seed"].astype(int).unique()))
    actual_b = tuple(sorted(b["trajectory_seed"].astype(int).unique()))
    if actual_a != expected_a or actual_b != expected_b:
        raise RuntimeError("V1 development seed banks differ from frozen V2 contract")
    pooled = pd.concat([a, b], ignore_index=True)
    seed_order = {seed: i for i, seed in enumerate(sorted(pooled["trajectory_seed"].astype(int).unique()))}
    pooled["trajectory"] = pooled["trajectory_seed"].astype(int).map(seed_order).astype(int)
    if int(pooled["trajectory"].nunique()) != 200:
        raise RuntimeError("V2 development pool must contain 200 trajectories")
    if pooled[["trajectory", "request_id"]].duplicated().any():
        raise RuntimeError("V2 development pool contains duplicate requests")
    return pooled


def _mean_candidate_table(
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
    for i, scale in enumerate(scales):
        sigma = matrix[i, :].astype(float)
        mean = float(np.mean(sigma))
        margin = float(min(mean-low, high-mean))
        rows.append({
            "rho_global": float(rho),
            "regime": regime,
            "scale": float(scale),
            "A_G_l_max": float(base.l_max)*float(scale),
            "A_G_c_max": float(base.c_max)*float(scale),
            "A_G_q_min": float(base.q_min),
            "sigma_mean_H60_H240": mean,
            "sigma_min_H60_H240": float(np.min(sigma)),
            "sigma_max_H60_H240": float(np.max(sigma)),
            "distance_mean_to_target": abs(mean-center),
            "mean_margin_to_nearest_band_edge": margin,
            "distance_log_scale_to_base": abs(math.log(float(scale))),
            "feasible": bool(low-TOL <= mean <= high+TOL),
        })
    return pd.DataFrame(rows)


def _pick(table: pd.DataFrame, rho: float, regime: str) -> pd.Series:
    feasible = table[table["feasible"].astype(bool)].copy()
    if feasible.empty:
        raise RuntimeError(f"rho={rho:g} {regime}: no V2 feasible mean-regime candidate")
    feasible["neg_margin"] = -feasible["mean_margin_to_nearest_band_edge"].astype(float)
    feasible = feasible.sort_values(
        ["distance_mean_to_target","neg_margin","distance_log_scale_to_base","scale"],
        kind="mergesort",
    ).reset_index(drop=True)
    return feasible.iloc[0]


def _selected_curve_from_matrix(
    matrix: np.ndarray,
    scales: np.ndarray,
    chosen_scale: float,
    horizons: list[float],
) -> np.ndarray:
    idx = np.flatnonzero(np.isclose(scales, float(chosen_scale), atol=TOL, rtol=0.0))
    if len(idx) != 1:
        raise RuntimeError("selected scale is not unique on frozen grid")
    sigma = matrix[int(idx[0]), :].astype(float)
    if len(sigma) != len(horizons):
        raise RuntimeError("selected diagnostic curve length mismatch")
    return sigma


def _joint_gate(
    selected: dict[str, pd.Series],
    curves: dict[str, np.ndarray],
    *,
    rho: float,
    minimum_gap: float,
) -> list[str]:
    failures = []
    s0 = float(selected["G0"]["scale"])
    s1 = float(selected["G1"]["scale"])
    s2 = float(selected["G2"]["scale"])
    if not (s2 + TOL < s1 and s1 + TOL < s0):
        failures.append(f"rho={rho:g}: scale order failed G2={s2}, G1={s1}, G0={s0}")
    m0 = float(np.mean(curves["G0"]))
    m1 = float(np.mean(curves["G1"]))
    m2 = float(np.mean(curves["G2"]))
    if m0 - m1 < minimum_gap - TOL:
        failures.append(f"rho={rho:g}: G0-G1 mean gap {m0-m1:.6f} < {minimum_gap}")
    if m1 - m2 < minimum_gap - TOL:
        failures.append(f"rho={rho:g}: G1-G2 mean gap {m1-m2:.6f} < {minimum_gap}")
    return failures


def _prepare(args, contract, metadata, rho_values, horizons, workload) -> None:
    bands = _bands(contract)
    diagnostic = _diagnostic_horizons(contract, horizons)
    scales = _scale_grid(dict(contract["step0_calibration"]["candidate_family"]["scale_grid"]))
    pool = _load_v1_development_pool(args.v1_output.resolve())
    graph_spec = _fixed_graph_spec(_read_json(args.m0_contract.resolve()))
    _, _, provenance = _validate_hidden_model(
        contract, phase1_config_path=args.phase1_config.resolve()
    )
    if str(provenance["case_id"]) != "D300000000_d0.200":
        raise RuntimeError("V2 provider process is not matched D300")
    fresh = dict(contract["step0_calibration"]["fresh_confirmation"])
    confirm = set(range(int(fresh["seed_start"]), int(fresh["seed_end_inclusive"])+1))
    pred = set(range(
        int(contract["blind_prediction_protocol_after_calibration"]["prediction_seed_start"]),
        int(contract["blind_prediction_protocol_after_calibration"]["prediction_seed_end_inclusive"])+1,
    ))
    final = set(range(
        int(contract["final_whitebox_evaluation"]["trajectory_seed_start"]),
        int(contract["final_whitebox_evaluation"]["trajectory_seed_end_inclusive"])+1,
    ))
    dev = set(pool["trajectory_seed"].astype(int).unique())
    if dev & confirm or dev & pred or dev & final or confirm & pred or confirm & final or pred & final:
        raise RuntimeError("V2 seed-bank firewall failed")
    print("SIGMA_REGIME_V2_PREPARE_PASS_NO_NEW_WHITEBOX")
    print(f"development_pool_n={pool['trajectory'].nunique()} seeds=32000..32199")
    print(f"fresh_confirmation={min(confirm)}..{max(confirm)} n={len(confirm)}")
    print(f"fixed_graph={graph_spec['graph']}")
    print(f"provider_process={provenance['case_id']}")
    print(f"diagnostic_horizons={diagnostic[0]:g}..{diagnostic[-1]:g} n={len(diagnostic)}")
    print(f"scale_grid={scales[0]:g}..{scales[-1]:g} n={len(scales)}")
    print("regime_statistic=mean_sigma_H60_H240")
    print("bands="+json.dumps(bands))
    print(f"minimum_adjacent_mean_sigma_gap={contract['step0_calibration']['minimum_adjacent_mean_sigma_gap']}")
    print(f"contract_sha256={_sha256(args.contract.resolve())}")


def _selection(args, contract, metadata, rho_values, horizons, workload) -> None:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bands = _bands(contract)
    diagnostic = _diagnostic_horizons(contract, horizons)
    scales = _scale_grid(dict(contract["step0_calibration"]["candidate_family"]["scale_grid"]))
    minimum_gap = float(contract["step0_calibration"]["minimum_adjacent_mean_sigma_gap"])
    phase1 = _read_json(args.phase1_config.resolve())
    base_regions = _base_regions(phase1, metadata, rho_values)
    pool = _load_v1_development_pool(args.v1_output.resolve())

    diagnostics_all = []
    selected_rows = []
    curve_rows = []
    failures = []

    for rho in rho_values:
        rec = base_regions[np.isclose(base_regions["rho_global"], rho, atol=TOL, rtol=0.0)].iloc[0]
        base = AdmissibilityBoundary(
            l_max=float(rec["base_l_max"]),
            c_max=float(rec["base_c_max"]),
            q_min=float(rec["base_q_min"]),
        )
        print(f"V2 pooled-development candidate grid rho={rho:g}", flush=True)
        matrix = _candidate_sigma_matrix(
            pool, base=base, rho=float(rho), scales=scales, horizons=diagnostic
        )
        chosen = {}
        chosen_curves = {}
        for regime in ("G0","G1","G2"):
            table = _mean_candidate_table(
                rho=float(rho), regime=regime, base=base, scales=scales,
                matrix=matrix, band=bands[regime],
            )
            diagnostics_all.append(table)
            row = _pick(table, float(rho), regime)
            chosen[regime] = row
            sigma = _selected_curve_from_matrix(
                matrix, scales, float(row["scale"]), diagnostic
            )
            chosen_curves[regime] = sigma
            selected_rows.append({k: row[k] for k in row.index if k != "neg_margin"})
            for h, value in zip(diagnostic, sigma):
                curve_rows.append({
                    "rho_global": float(rho),
                    "regime": regime,
                    "horizon": float(h),
                    "sigma_development": float(value),
                    "scale": float(row["scale"]),
                })
            print(
                f"  {regime}: scale={float(row['scale']):.3f} "
                f"mean={float(np.mean(sigma)):.3f} "
                f"range=[{float(np.min(sigma)):.3f},{float(np.max(sigma)):.3f}]",
                flush=True,
            )
        failures.extend(_joint_gate(
            chosen, chosen_curves, rho=float(rho), minimum_gap=minimum_gap
        ))

    diagnostics = pd.concat(diagnostics_all, ignore_index=True)
    selected = pd.DataFrame(selected_rows).sort_values(["rho_global","regime"]).reset_index(drop=True)
    curves = pd.DataFrame(curve_rows).sort_values(["rho_global","regime","horizon"]).reset_index(drop=True)
    diagnostics_path = output / "sigma_regime_v2_development_candidate_diagnostics.csv"
    selected_path = output / "sigma_regime_v2_selected_regions_from_development.csv"
    curves_path = output / "sigma_regime_v2_selected_development_curves.csv"
    diagnostics.to_csv(diagnostics_path, index=False)
    selected.to_csv(selected_path, index=False)
    curves.to_csv(curves_path, index=False)

    if failures or len(selected) != 15:
        _write_json(output / "sigma_regime_v2_selection_failure_manifest.json", {
            "status": FAIL_STATUS,
            "stage": "development_selection",
            "failures": failures,
            "n_selected": int(len(selected)),
            "contract_sha256": _sha256(args.contract.resolve()),
        })
        raise RuntimeError("SIGMA_REGIME_V2_SELECTION_FAIL: " + " | ".join(failures))

    freeze_path = output / "sigma_regime_v2_selection_freeze_manifest.json"
    v1_sel = args.v1_output.resolve() / "sigma_regime_step0_selection_whitebox_ledger.csv"
    v1_con = args.v1_output.resolve() / "sigma_regime_step0_confirmation_whitebox_ledger.csv"
    _write_json(freeze_path, {
        "status": SELECTION_STATUS,
        "contract_sha256": _sha256(args.contract.resolve()),
        "v1_selection_ledger_sha256": _sha256(v1_sel),
        "v1_confirmation_ledger_sha256": _sha256(v1_con),
        "selected_regions_sha256": _sha256(selected_path),
        "selected_curves_sha256": _sha256(curves_path),
        "candidate_diagnostics_sha256": _sha256(diagnostics_path),
        "development_n": 200,
        "M0_M1_M2_used": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    })
    print("SIGMA_REGIME_V2_SELECTION_FROZEN_BEFORE_FRESH_CONFIRMATION_PASS")
    print(f"selected_queries={len(selected)}")
    print(f"selection_freeze={freeze_path}")


def _fresh_ledger(
    *,
    path: Path,
    provider_surrogates: dict[str, Any],
    graph_spec: dict[str, Any],
    workload: dict[str, float],
    seeds: tuple[int,...],
    canonical_ipt: float,
    execution_fraction: float,
) -> pd.DataFrame:
    if path.exists():
        ledger = pd.read_csv(path)
        actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique()))
        if actual != seeds or int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError("existing V2 confirmation ledger uses wrong seeds")
        print("V2 confirmation: loaded completed checkpoint ledger", flush=True)
        return ledger
    frames = []
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
        one.insert(0, "trajectory", trajectory)
        one.insert(1, "trajectory_seed", seed)
        frames.append(one)
        if trajectory == 0 or (trajectory+1)%25==0 or trajectory+1==len(seeds):
            print(f"  Sigma-regime-V2-confirmation: {trajectory+1}/{len(seeds)}", flush=True)
    ledger = pd.concat(frames, ignore_index=True)
    ledger.to_csv(path, index=False)
    return ledger


def _confirmation(args, contract, metadata, rho_values, horizons, workload) -> None:
    output = args.output.resolve()
    freeze_path = output / "sigma_regime_v2_selection_freeze_manifest.json"
    if not freeze_path.exists():
        raise RuntimeError("V2 selection freeze absent; run --selection-only first")
    freeze = _read_json(freeze_path)
    if freeze.get("status") != SELECTION_STATUS:
        raise RuntimeError("unexpected V2 selection freeze status")
    if str(freeze["contract_sha256"]) != _sha256(args.contract.resolve()):
        raise RuntimeError("V2 contract changed after selection freeze")

    selected_path = output / "sigma_regime_v2_selected_regions_from_development.csv"
    if str(freeze["selected_regions_sha256"]) != _sha256(selected_path):
        raise RuntimeError("V2 selected regions changed after freeze")
    selected = pd.read_csv(selected_path)
    bands = _bands(contract)
    diagnostic = _diagnostic_horizons(contract, horizons)
    minimum_gap = float(contract["step0_calibration"]["minimum_adjacent_mean_sigma_gap"])

    provider_surrogates, execution_fraction, provenance = _validate_hidden_model(
        contract, phase1_config_path=args.phase1_config.resolve()
    )
    graph_spec = _fixed_graph_spec(_read_json(args.m0_contract.resolve()))
    fresh = dict(contract["step0_calibration"]["fresh_confirmation"])
    seeds = tuple(range(int(fresh["seed_start"]), int(fresh["seed_end_inclusive"])+1))
    if len(seeds) != int(fresh["n_trajectories"]):
        raise RuntimeError("V2 confirmation seed count mismatch")
    ledger_path = output / "sigma_regime_v2_fresh_confirmation_whitebox_ledger.csv"
    ledger = _fresh_ledger(
        path=ledger_path,
        provider_surrogates=provider_surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    summaries = []
    curves_all = []
    failures = []
    for _, rec in selected.sort_values(["rho_global","regime"]).iterrows():
        rho = float(rec["rho_global"])
        regime = str(rec["regime"])
        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = _canonical_curve(
            ledger, boundary=boundary, rho=rho, horizons=horizons,
            workload=workload, column="sigma_confirmation",
        )
        curve.insert(0,"regime",regime)
        curve.insert(0,"rho_global",rho)
        curve["scale"] = float(rec["scale"])
        curves_all.append(curve)
        diag = curve[curve["horizon"].astype(float).isin(diagnostic)].sort_values("horizon")
        sigma = diag["sigma_confirmation"].astype(float).to_numpy()
        mean = float(np.mean(sigma))
        low, high, center = bands[regime]
        passed = bool(low-TOL <= mean <= high+TOL)
        if not passed:
            failures.append(
                f"rho={rho:g} {regime}: confirmation mean {mean:.6f} outside [{low},{high}]"
            )
        summaries.append({
            "rho_global":rho,"regime":regime,"scale":float(rec["scale"]),
            "sigma_mean_H60_H240":mean,
            "sigma_min_H60_H240":float(np.min(sigma)),
            "sigma_max_H60_H240":float(np.max(sigma)),
            "band_lower":low,"band_upper":high,"target_center":center,
            "per_query_pass":passed,
        })

    summary = pd.DataFrame(summaries).sort_values(["rho_global","regime"]).reset_index(drop=True)
    for rho, group in summary.groupby("rho_global"):
        means = {str(r["regime"]):float(r["sigma_mean_H60_H240"]) for _,r in group.iterrows()}
        if means["G0"]-means["G1"] < minimum_gap-TOL:
            failures.append(f"rho={rho:g}: fresh G0-G1 mean gap {means['G0']-means['G1']:.6f} < {minimum_gap}")
        if means["G1"]-means["G2"] < minimum_gap-TOL:
            failures.append(f"rho={rho:g}: fresh G1-G2 mean gap {means['G1']-means['G2']:.6f} < {minimum_gap}")

    curves = pd.concat(curves_all, ignore_index=True)
    curves_path = output / "sigma_regime_v2_fresh_confirmation_curves.csv"
    summary_path = output / "sigma_regime_v2_fresh_confirmation_summary.csv"
    frozen_path = output / "sigma_regime_v2_selected_regions_frozen.csv"
    curves.to_csv(curves_path,index=False)
    summary.to_csv(summary_path,index=False)
    selected.to_csv(frozen_path,index=False)

    manifest_path = output / "sigma_regime_v2_calibration_manifest.json"
    status = PASS_STATUS if not failures else FAIL_STATUS
    _write_json(manifest_path,{
        "status":status,
        "contract_sha256":_sha256(args.contract.resolve()),
        "selection_freeze_sha256":_sha256(freeze_path),
        "confirmation_ledger_sha256":_sha256(ledger_path),
        "confirmation_curves_sha256":_sha256(curves_path),
        "confirmation_summary_sha256":_sha256(summary_path),
        "selected_regions_frozen_sha256":_sha256(frozen_path),
        "confirmation_seed_start":seeds[0],
        "confirmation_seed_end_inclusive":seeds[-1],
        "n_confirmation_trajectories":len(seeds),
        "failures":failures,
        "M0_M1_M2_used":False,
        "git_commit":_git_head(FIRST_SCIENCE.parent),
    })
    print("\nSIGMA_REGIME_V2_FRESH_CONFIRMATION_SUMMARY")
    print(summary.to_string(index=False))
    if failures:
        print("SIGMA_REGIME_V2_CALIBRATION_FAIL")
        for item in failures:
            print(item)
        raise RuntimeError("V2 fresh confirmation failed")
    print("SIGMA_REGIME_V2_CALIBRATION_FROZEN_PASS")
    print(f"calibration_manifest={manifest_path}")


def run(args: argparse.Namespace) -> None:
    started=time.perf_counter()
    contract=_read_json(args.contract.resolve())
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected V2 contract status")
    metadata,_,_=load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rho_values=[float(v) for v in common_same_rho_support(metadata)]
    horizons=[float(v) for v in common_horizon_support(metadata)]
    workload=_common_workload_contract(metadata)
    if args.prepare_only:
        _prepare(args,contract,metadata,rho_values,horizons,workload)
    elif args.selection_only:
        _selection(args,contract,metadata,rho_values,horizons,workload)
    elif args.confirm_and_freeze:
        _confirmation(args,contract,metadata,rho_values,horizons,workload)
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p=argparse.ArgumentParser(description="Robust fixed-graph sigma-regime Step-0 v2")
    p.add_argument("--contract",type=Path,default=HERE/"config_phase4_sigma_regime_battery_step0_v2.json")
    p.add_argument("--phase1-config",type=Path,default=PHASE1/"config_phase1_discovery_v1.json")
    p.add_argument("--m0-contract",type=Path,default=PHASE3/"config_phase3_m0_contract_v1.json")
    p.add_argument("--i1-card-root",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public")
    p.add_argument("--i1-manifest",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public"/"i1_rho_conditioned_manifest_v1.json")
    p.add_argument("--v1-output",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v1")
    p.add_argument("--output",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v2")
    stages=p.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only",action="store_true")
    stages.add_argument("--selection-only",action="store_true")
    stages.add_argument("--confirm-and-freeze",action="store_true")
    args=p.parse_args()
    run(args)

if __name__=="__main__":
    main()
