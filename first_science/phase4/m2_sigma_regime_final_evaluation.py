#!/usr/bin/env python3
"""Prospective final WB evaluation for the frozen sigma-regime battery.

Ordering:
  1. --prepare-only verifies the already-frozen blind prediction manifest and
     all prediction hashes without generating/reading final WB seeds.
  2. --evaluate re-verifies the same hashes, generates the single matched-D300
     WB ledger on seeds 34000..34099, evaluates the 15 frozen queries, and
     reports M0/M1/M2 errors. No repair or reselection is possible here.
"""
from __future__ import annotations

import argparse
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
)
from m0_analytic_composition import AdmissibilityBoundary
from m1_graph_simulator_v2 import execute_one_m1_graph_trajectory
from run_m1_graph_prediction_v2 import (
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json
from m2_g2_step0_calibration import _validate_hidden_model
from m2_sigma_regime_step0_calibration import _fixed_graph_spec

EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_FINAL_EVALUATION_V1"
EXPECTED_PREDICTION_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BLIND_PREDICTIONS_V1"
PREPARE_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_FINAL_EVAL_READY_V1"
COMPLETE_STATUS = "PHASE4_SIGMA_REGIME_FINAL_EVALUATION_COMPLETE_V1"
TOL = 1e-12


def _required_prediction_columns() -> set[str]:
    return {
        "rho_global", "regime", "horizon", "scale",
        "A_G_l_max", "A_G_c_max", "A_G_q_min",
        "sigma_m1", "sigma_m2_mean", "sigma_m2_min", "sigma_m2_max",
        "m0_status", "sigma_m0", "sigma_m0_raw_product",
    }


def _validate_predictions(
    *,
    contract: dict[str, Any],
    prediction_contract_path: Path,
    prediction_manifest_path: Path,
    prediction_path: Path,
    member_curves_path: Path,
    design_path: Path,
    ledger_hash_path: Path,
    selected_regions_path: Path,
    step0_manifest_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    manifest = _read_json(prediction_manifest_path)
    required_status = str(contract["required_prediction_manifest_status"])
    if manifest.get("status") != required_status or manifest.get("status") != EXPECTED_PREDICTION_STATUS:
        raise RuntimeError("blind prediction stage is not frozen complete")
    if bool(manifest.get("final_whitebox_read_or_generated")):
        raise RuntimeError("prediction manifest unexpectedly reports final WB access")
    if bool(manifest.get("M1_parameters_changed")) or bool(manifest.get("M2_members_changed")):
        raise RuntimeError("prediction manifest reports method changes")
    if bool(manifest.get("M2_weights_changed")) or bool(manifest.get("posthoc_member_selection")):
        raise RuntimeError("prediction manifest reports forbidden M2 adaptation")

    expected_hashes = {
        "prediction_contract_sha256": _sha256(prediction_contract_path),
        "step0_manifest_sha256": _sha256(step0_manifest_path),
        "step0_selected_regions_sha256": _sha256(selected_regions_path),
        "variant_design_sha256": _sha256(design_path),
        "member_curves_sha256": _sha256(member_curves_path),
        "blind_predictions_sha256": _sha256(prediction_path),
        "ledger_hash_table_sha256": _sha256(ledger_hash_path),
    }
    mismatch = [
        key for key, value in expected_hashes.items()
        if str(manifest.get(key)) != str(value)
    ]
    if mismatch:
        raise RuntimeError(
            "blind prediction artifacts changed after freeze: " + ", ".join(mismatch)
        )

    predictions = pd.read_csv(prediction_path)
    missing = sorted(_required_prediction_columns().difference(predictions.columns))
    if missing:
        raise RuntimeError("blind prediction file missing: " + ", ".join(missing))
    if predictions.duplicated(["rho_global", "regime", "horizon"]).any():
        raise RuntimeError("duplicate blind prediction points")
    if len(predictions[["rho_global","regime"]].drop_duplicates()) != 15:
        raise RuntimeError("blind prediction file does not contain 15 frozen queries")
    if int(manifest.get("n_m2_variants", -1)) != 27:
        raise RuntimeError("blind prediction manifest does not contain frozen 27-member M2")
    if int(manifest.get("n_total_variants", -1)) != 28:
        raise RuntimeError("blind prediction manifest does not contain 28 total variants")
    if int(manifest.get("prediction_seed_start", -1)) != 33000 or int(manifest.get("prediction_seed_end_inclusive", -1)) != 33099:
        raise RuntimeError("blind prediction seed bank changed")
    return manifest, predictions


def _write_prepare_freeze(
    *,
    output: Path,
    contract_path: Path,
    prediction_contract_path: Path,
    prediction_manifest_path: Path,
    prediction_path: Path,
    member_curves_path: Path,
    design_path: Path,
    ledger_hash_path: Path,
    selected_regions_path: Path,
    step0_manifest_path: Path,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    path = output / "sigma_regime_final_eval_prepare_manifest_v1.json"
    _write_json(path, {
        "status": PREPARE_STATUS,
        "final_evaluation_contract_sha256": _sha256(contract_path),
        "prediction_contract_sha256": _sha256(prediction_contract_path),
        "prediction_manifest_sha256": _sha256(prediction_manifest_path),
        "blind_predictions_sha256": _sha256(prediction_path),
        "member_curves_sha256": _sha256(member_curves_path),
        "variant_design_sha256": _sha256(design_path),
        "ledger_hash_table_sha256": _sha256(ledger_hash_path),
        "selected_regions_sha256": _sha256(selected_regions_path),
        "step0_manifest_sha256": _sha256(step0_manifest_path),
        "final_whitebox_read_or_generated": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    })
    return path


def _assert_prepare_freeze(
    *,
    prepare_path: Path,
    contract_path: Path,
    prediction_contract_path: Path,
    prediction_manifest_path: Path,
    prediction_path: Path,
    member_curves_path: Path,
    design_path: Path,
    ledger_hash_path: Path,
    selected_regions_path: Path,
    step0_manifest_path: Path,
) -> dict[str, Any]:
    if not prepare_path.exists():
        raise RuntimeError("final-evaluation prepare freeze absent; run --prepare-only first")
    freeze = _read_json(prepare_path)
    if freeze.get("status") != PREPARE_STATUS:
        raise RuntimeError("unexpected final-evaluation prepare status")
    expected = {
        "final_evaluation_contract_sha256": _sha256(contract_path),
        "prediction_contract_sha256": _sha256(prediction_contract_path),
        "prediction_manifest_sha256": _sha256(prediction_manifest_path),
        "blind_predictions_sha256": _sha256(prediction_path),
        "member_curves_sha256": _sha256(member_curves_path),
        "variant_design_sha256": _sha256(design_path),
        "ledger_hash_table_sha256": _sha256(ledger_hash_path),
        "selected_regions_sha256": _sha256(selected_regions_path),
        "step0_manifest_sha256": _sha256(step0_manifest_path),
    }
    mismatch = [k for k,v in expected.items() if str(freeze.get(k)) != str(v)]
    if mismatch:
        raise RuntimeError("frozen final-evaluation inputs changed: " + ", ".join(mismatch))
    if bool(freeze.get("final_whitebox_read_or_generated")):
        raise RuntimeError("prepare freeze unexpectedly reports final WB access")
    return freeze


def _generate_or_load_final_wb(
    *,
    path: Path,
    provider_surrogates: dict[str, Any],
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
) -> tuple[pd.DataFrame, bool]:
    if path.exists():
        ledger = pd.read_csv(path)
        actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique()))
        if actual != seeds:
            raise RuntimeError("existing final WB ledger uses wrong seed bank")
        if int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError("existing final WB ledger trajectory count mismatch")
        if ledger[["trajectory","request_id"]].duplicated().any():
            raise RuntimeError("existing final WB ledger has duplicate requests")
        print("Final WB: loaded completed checkpoint ledger", flush=True)
        return ledger, True

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
        one.insert(0, "trajectory", int(trajectory))
        one.insert(1, "trajectory_seed", int(seed))
        frames.append(one)
        if trajectory == 0 or (trajectory+1)%25 == 0 or trajectory+1 == len(seeds):
            print(f"  Sigma-regime-final-WB: {trajectory+1}/{len(seeds)}", flush=True)
    ledger = pd.concat(frames, ignore_index=True)
    ledger.to_csv(path, index=False)
    return ledger, False


def _build_wb_curves(
    *,
    ledger: pd.DataFrame,
    predictions: pd.DataFrame,
    horizons: list[float],
    workload: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    queries = predictions[
        ["rho_global","regime","scale","A_G_l_max","A_G_c_max","A_G_q_min"]
    ].drop_duplicates().sort_values(["rho_global","regime"])
    if len(queries) != 15:
        raise RuntimeError("prediction query bank is not exactly 15")
    for _, q in queries.iterrows():
        boundary = AdmissibilityBoundary(
            l_max=float(q["A_G_l_max"]),
            c_max=float(q["A_G_c_max"]),
            q_min=float(q["A_G_q_min"]),
        )
        curve = build_empirical_graph_sigma_curve(
            ledger,
            boundary=boundary,
            rho_global=float(q["rho_global"]),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column="sigma_whitebox",
        )
        curve.insert(0, "regime", str(q["regime"]))
        curve.insert(0, "rho_global", float(q["rho_global"]))
        curve["scale"] = float(q["scale"])
        curve["A_G_l_max"] = float(boundary.l_max)
        curve["A_G_c_max"] = float(boundary.c_max)
        curve["A_G_q_min"] = float(boundary.q_min)
        rows.append(curve)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global","regime","horizon"]
    ).reset_index(drop=True)


def _metrics(frame: pd.DataFrame, pred_col: str) -> dict[str, float]:
    valid = frame[pred_col].notna() & frame["sigma_whitebox"].notna()
    x = frame.loc[valid, pred_col].astype(float).to_numpy()
    y = frame.loc[valid, "sigma_whitebox"].astype(float).to_numpy()
    if len(x) == 0:
        return {"n_points":0,"mae":np.nan,"rmse":np.nan,"bias":np.nan,"max_abs_error":np.nan}
    e = x-y
    return {
        "n_points": int(len(e)),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e*e))),
        "bias": float(np.mean(e)),
        "max_abs_error": float(np.max(np.abs(e))),
    }


def _summary_rows(comparison: pd.DataFrame, *, window_label: str) -> pd.DataFrame:
    rows = []
    methods = {"M0":"sigma_m0","M1":"sigma_m1","M2":"sigma_m2_mean"}

    groups: list[tuple[str, Any, pd.DataFrame]] = [("whole_battery","ALL",comparison)]
    groups.extend(("per_regime", str(k), g) for k,g in comparison.groupby("regime", sort=True))
    groups.extend(("per_rho", f"{float(k):.15g}", g) for k,g in comparison.groupby("rho_global", sort=True))
    groups.extend(
        ("per_rho_x_regime", f"rho={float(rho):.15g}|{regime}", g)
        for (rho,regime),g in comparison.groupby(["rho_global","regime"], sort=True)
    )

    for level,key,group in groups:
        for method,col in methods.items():
            met = _metrics(group,col)
            rows.append({
                "window": window_label,
                "summary_level": level,
                "summary_key": key,
                "method": method,
                **met,
                "n_queries": int(group[["rho_global","regime"]].drop_duplicates().shape[0]),
                "n_not_applicable_queries": (
                    int(group.loc[group["m0_status"].astype(str)=="NOT_APPLICABLE",["rho_global","regime"]].drop_duplicates().shape[0])
                    if method=="M0" else 0
                ),
            })
    return pd.DataFrame(rows)


def _ambiguity_rows(comparison: pd.DataFrame, *, window_label: str) -> pd.DataFrame:
    point = comparison.copy()
    wb = point["sigma_whitebox"].astype(float).to_numpy()
    lo = point["sigma_m2_min"].astype(float).to_numpy()
    hi = point["sigma_m2_max"].astype(float).to_numpy()
    point["m2_range_width"] = hi-lo
    point["m2_wb_inside"] = (wb >= lo-TOL) & (wb <= hi+TOL)
    point["m2_distance_outside"] = np.maximum(np.maximum(lo-wb, wb-hi),0.0)

    groups: list[tuple[str, Any, pd.DataFrame]] = [("whole_battery","ALL",point)]
    groups.extend(("per_regime", str(k), g) for k,g in point.groupby("regime", sort=True))
    groups.extend(("per_rho", f"{float(k):.15g}", g) for k,g in point.groupby("rho_global", sort=True))
    groups.extend(
        ("per_rho_x_regime", f"rho={float(rho):.15g}|{regime}", g)
        for (rho,regime),g in point.groupby(["rho_global","regime"], sort=True)
    )
    rows=[]
    for level,key,g in groups:
        rows.append({
            "window":window_label,
            "summary_level":level,
            "summary_key":key,
            "n_points":int(len(g)),
            "whitebox_coverage_fraction":float(g["m2_wb_inside"].astype(bool).mean()),
            "mean_range_width":float(g["m2_range_width"].astype(float).mean()),
            "max_range_width":float(g["m2_range_width"].astype(float).max()),
            "mean_distance_outside_range":float(g["m2_distance_outside"].astype(float).mean()),
            "max_distance_outside_range":float(g["m2_distance_outside"].astype(float).max()),
        })
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    started=time.perf_counter()
    contract_path=args.contract.resolve()
    contract=_read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected final evaluation contract status")

    prediction_manifest, predictions = _validate_predictions(
        contract=contract,
        prediction_contract_path=args.prediction_contract.resolve(),
        prediction_manifest_path=args.prediction_manifest.resolve(),
        prediction_path=args.predictions.resolve(),
        member_curves_path=args.member_curves.resolve(),
        design_path=args.variant_design.resolve(),
        ledger_hash_path=args.ledger_hashes.resolve(),
        selected_regions_path=args.selected_regions.resolve(),
        step0_manifest_path=args.step0_manifest.resolve(),
    )

    metadata,_,_=load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rhos=sorted(float(v) for v in common_same_rho_support(metadata))
    horizons=[float(v) for v in common_horizon_support(metadata)]
    workload=_common_workload_contract(metadata)
    pred_rhos=sorted(float(v) for v in predictions["rho_global"].unique())
    if not np.allclose(rhos,pred_rhos,atol=TOL,rtol=0.0):
        raise RuntimeError("prediction rho support differs from frozen I1")

    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    prepare_path=output/"sigma_regime_final_eval_prepare_manifest_v1.json"

    if args.prepare_only:
        path=_write_prepare_freeze(
            output=output,
            contract_path=contract_path,
            prediction_contract_path=args.prediction_contract.resolve(),
            prediction_manifest_path=args.prediction_manifest.resolve(),
            prediction_path=args.predictions.resolve(),
            member_curves_path=args.member_curves.resolve(),
            design_path=args.variant_design.resolve(),
            ledger_hash_path=args.ledger_hashes.resolve(),
            selected_regions_path=args.selected_regions.resolve(),
            step0_manifest_path=args.step0_manifest.resolve(),
        )
        print("SIGMA_REGIME_FINAL_EVAL_PREPARE_PASS_NO_FINAL_WHITEBOX")
        print("primary_metrics_window=full_frozen_horizon_support")
        print("secondary_metrics_window=H60..H240")
        print(f"prediction_points={len(predictions)}")
        print(f"prediction_manifest_sha256={_sha256(args.prediction_manifest.resolve())}")
        print(f"blind_predictions_sha256={_sha256(args.predictions.resolve())}")
        print(f"prepare_manifest={path}")
        print(f"python_wall_seconds={time.perf_counter()-started:.3f}")
        return

    _assert_prepare_freeze(
        prepare_path=prepare_path,
        contract_path=contract_path,
        prediction_contract_path=args.prediction_contract.resolve(),
        prediction_manifest_path=args.prediction_manifest.resolve(),
        prediction_path=args.predictions.resolve(),
        member_curves_path=args.member_curves.resolve(),
        design_path=args.variant_design.resolve(),
        ledger_hash_path=args.ledger_hashes.resolve(),
        selected_regions_path=args.selected_regions.resolve(),
        step0_manifest_path=args.step0_manifest.resolve(),
    )

    step0_contract=_read_json(args.step0_contract.resolve())
    provider_surrogates,execution_fraction,provenance=_validate_hidden_model(
        step0_contract,phase1_config_path=args.phase1_config.resolve()
    )
    if str(provenance["case_id"]) != "D300000000_d0.200":
        raise RuntimeError("final WB provider process is not matched D300")
    graph_spec=_fixed_graph_spec(_read_json(args.m0_contract.resolve()))

    wb_cfg=dict(contract["final_whitebox"])
    seeds=tuple(range(int(wb_cfg["seed_start"]),int(wb_cfg["seed_end_inclusive"])+1))
    if seeds != tuple(range(34000,34100)) or len(seeds) != int(wb_cfg["n_trajectories"]):
        raise RuntimeError("final WB seed bank changed")

    ledger_path=output/"sigma_regime_final_whitebox_ledger.csv"
    ledger,reused=_generate_or_load_final_wb(
        path=ledger_path,
        provider_surrogates=provider_surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    wb_curves=_build_wb_curves(
        ledger=ledger,predictions=predictions,horizons=horizons,workload=workload
    )
    wb_path=output/"sigma_regime_final_whitebox_curves.csv"
    wb_curves.to_csv(wb_path,index=False)

    comparison=predictions.merge(
        wb_curves[["rho_global","regime","horizon","sigma_whitebox"]],
        on=["rho_global","regime","horizon"],
        how="inner",validate="one_to_one"
    )
    if len(comparison) != len(predictions):
        raise RuntimeError("final WB curve support does not match blind predictions")
    comparison["error_m0"]=comparison["sigma_m0"]-comparison["sigma_whitebox"]
    comparison["error_m1"]=comparison["sigma_m1"]-comparison["sigma_whitebox"]
    comparison["error_m2"]=comparison["sigma_m2_mean"]-comparison["sigma_whitebox"]
    comparison["m2_whitebox_inside_range"]=(
        (comparison["sigma_whitebox"] >= comparison["sigma_m2_min"]-TOL)
        & (comparison["sigma_whitebox"] <= comparison["sigma_m2_max"]+TOL)
    )
    comparison_path=output/"sigma_regime_final_comparison.csv"
    comparison.to_csv(comparison_path,index=False)

    full_summary=_summary_rows(comparison,window_label="FULL_FROZEN_HORIZON_SUPPORT")
    diag=comparison[(comparison["horizon"].astype(float)>=60-TOL)&(comparison["horizon"].astype(float)<=240+TOL)].copy()
    diag_summary=_summary_rows(diag,window_label="H60_H240")
    summary=pd.concat([full_summary,diag_summary],ignore_index=True)
    summary_path=output/"sigma_regime_final_error_metrics.csv"
    summary.to_csv(summary_path,index=False)

    ambiguity=pd.concat([
        _ambiguity_rows(comparison,window_label="FULL_FROZEN_HORIZON_SUPPORT"),
        _ambiguity_rows(diag,window_label="H60_H240"),
    ],ignore_index=True)
    ambiguity_path=output/"sigma_regime_final_m2_ambiguity_metrics.csv"
    ambiguity.to_csv(ambiguity_path,index=False)

    regime_means=diag.groupby(["rho_global","regime"],as_index=False).agg(
        sigma_whitebox_mean=("sigma_whitebox","mean"),
        sigma_m0_mean=("sigma_m0","mean"),
        sigma_m1_mean=("sigma_m1","mean"),
        sigma_m2_mean=("sigma_m2_mean","mean"),
        sigma_m2_min_mean=("sigma_m2_min","mean"),
        sigma_m2_max_mean=("sigma_m2_max","mean"),
    )
    regime_means_path=output/"sigma_regime_final_regime_means_H60_H240.csv"
    regime_means.to_csv(regime_means_path,index=False)

    manifest_path=output/"sigma_regime_final_evaluation_manifest_v1.json"
    _write_json(manifest_path,{
        "status":COMPLETE_STATUS,
        "final_evaluation_contract_sha256":_sha256(contract_path),
        "prepare_manifest_sha256":_sha256(prepare_path),
        "prediction_manifest_sha256":_sha256(args.prediction_manifest.resolve()),
        "blind_predictions_sha256":_sha256(args.predictions.resolve()),
        "final_whitebox_ledger_sha256":_sha256(ledger_path),
        "final_whitebox_curves_sha256":_sha256(wb_path),
        "comparison_sha256":_sha256(comparison_path),
        "error_metrics_sha256":_sha256(summary_path),
        "m2_ambiguity_metrics_sha256":_sha256(ambiguity_path),
        "regime_means_H60_H240_sha256":_sha256(regime_means_path),
        "provider_process_sha256":provenance["provider_process_sha256"],
        "final_whitebox_seed_start":seeds[0],
        "final_whitebox_seed_end_inclusive":seeds[-1],
        "n_final_whitebox_trajectories":len(seeds),
        "whitebox_ledger_reused":bool(reused),
        "no_repair_after_final_WB":True,
        "M1_parameters_changed":False,
        "M2_members_changed":False,
        "M2_weights_changed":False,
        "posthoc_member_selection":False,
        "M2_closed_after_this_evaluation":True,
        "python_wall_seconds":float(time.perf_counter()-started),
        "git_commit":_git_head(FIRST_SCIENCE.parent),
    })

    headline=summary[
        (summary["window"]=="H60_H240")
        & (summary["summary_level"].isin(["whole_battery","per_regime"]))
    ]
    print("\nSIGMA_REGIME_FINAL_HEADLINE_ERROR_METRICS_H60_H240")
    print(headline.to_string(index=False))
    headline_amb=ambiguity[
        (ambiguity["window"]=="H60_H240")
        & (ambiguity["summary_level"].isin(["whole_battery","per_regime"]))
    ]
    print("\nSIGMA_REGIME_FINAL_M2_AMBIGUITY_H60_H240")
    print(headline_amb.to_string(index=False))
    print("\nSIGMA_REGIME_FINAL_REGIME_MEANS_H60_H240")
    print(regime_means.to_string(index=False))
    print("\nSIGMA_REGIME_FINAL_EVALUATION_COMPLETE")
    print(f"manifest={manifest_path}")
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p=argparse.ArgumentParser(description="Prospective final evaluation of frozen sigma-regime predictions")
    p.add_argument("--contract",type=Path,default=HERE/"config_phase4_sigma_regime_final_evaluation_v1.json")
    p.add_argument("--prediction-contract",type=Path,default=HERE/"config_phase4_sigma_regime_blind_prediction_v1.json")
    p.add_argument("--prediction-manifest",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1"/"sigma_regime_prediction_manifest_v1.json")
    p.add_argument("--predictions",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1"/"sigma_regime_blind_predictions.csv")
    p.add_argument("--member-curves",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1"/"sigma_regime_member_curves.csv")
    p.add_argument("--variant-design",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1"/"sigma_regime_variant_design.csv")
    p.add_argument("--ledger-hashes",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1"/"sigma_regime_ledger_hashes.csv")
    p.add_argument("--selected-regions",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v2"/"sigma_regime_v2_selected_regions_frozen.csv")
    p.add_argument("--step0-manifest",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v2"/"sigma_regime_v2_calibration_manifest.json")
    p.add_argument("--step0-contract",type=Path,default=HERE/"config_phase4_sigma_regime_battery_step0_v2.json")
    p.add_argument("--phase1-config",type=Path,default=PHASE1/"config_phase1_discovery_v1.json")
    p.add_argument("--m0-contract",type=Path,default=PHASE3/"config_phase3_m0_contract_v1.json")
    p.add_argument("--i1-card-root",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public")
    p.add_argument("--i1-manifest",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public"/"i1_rho_conditioned_manifest_v1.json")
    p.add_argument("--output",type=Path,default=HERE/"results"/"sigma_regime_final_evaluation_v1")
    stages=p.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only",action="store_true")
    stages.add_argument("--evaluate",action="store_true")
    args=p.parse_args()
    run(args)

if __name__=="__main__":
    main()
