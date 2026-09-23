#!/usr/bin/env python3
"""Fresh final evaluation for frozen M3-v4 dominant-mass predictions.

Protocol:
  1. --prepare-only verifies and hash-freezes the already-completed M3 prediction
     plus the frozen M0/M1/M2 baseline prediction artifacts. No fresh WB is read
     or generated.
  2. --evaluate re-verifies the prepare freeze, generates one new matched-D300
     WB ledger on seeds 38000..38199, and evaluates M0/M1/M2/M3-B1400/M3-B2000.
No method repair is permitted after this WB is opened.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)
from run_m1_graph_prediction_v2 import _common_workload_contract  # noqa: E402
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_g2_step0_calibration import _validate_hidden_model  # noqa: E402
from m2_sigma_regime_step0_calibration import _fixed_graph_spec  # noqa: E402
from m2_sigma_regime_final_evaluation import (  # noqa: E402
    _build_wb_curves,
    _generate_or_load_final_wb,
    _validate_predictions as _validate_m2_predictions,
)

EXPECTED_STATUS = "FROZEN_PHASE4_M3_V4_FINAL_EVALUATION_V1"
EXPECTED_M3_STATUS = "FROZEN_PHASE4_M3_V4_DOMINANT_MASS_GRAPH_PREDICTIONS"
PREPARE_STATUS = "FROZEN_PHASE4_M3_V4_FINAL_EVAL_READY_V1"
COMPLETE_STATUS = "PHASE4_M3_V4_FINAL_EVALUATION_COMPLETE_V1"
TOL = 1e-12


def _resolve(rel: str) -> Path:
    return (HERE / rel).resolve()


def _validate_m3(contract: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Path]]:
    cfg = dict(contract["m3_prediction"])
    paths = {
        "contract": _resolve(cfg["contract"]),
        "manifest": _resolve(cfg["manifest"]),
        "predictions": _resolve(cfg["predictions"]),
        "design": _resolve(cfg["design"]),
        "allocation": _resolve(cfg["allocation"]),
        "ledger_hashes": _resolve(cfg["ledger_hashes"]),
    }
    manifest = _read_json(paths["manifest"])
    if manifest.get("status") != str(cfg["required_manifest_status"]):
        raise RuntimeError("M3 prediction manifest is not frozen complete")
    if manifest.get("status") != EXPECTED_M3_STATUS:
        raise RuntimeError("unexpected M3 prediction status")
    if bool(manifest.get("graph_whitebox_read")) or bool(manifest.get("final_whitebox_generated")):
        raise RuntimeError("M3 prediction stage reports WB access")

    expected = {
        "contract_sha256": _sha256(paths["contract"]),
        "dominant_design_sha256": _sha256(paths["design"]),
        "allocation_table_sha256": _sha256(paths["allocation"]),
        "blind_predictions_sha256": _sha256(paths["predictions"]),
        "ledger_hashes_sha256": _sha256(paths["ledger_hashes"]),
    }
    mismatch = [k for k, v in expected.items() if str(manifest.get(k)) != str(v)]
    if mismatch:
        raise RuntimeError("M3 frozen prediction artifacts changed: " + ", ".join(mismatch))

    budgets = sorted(int(x) for x in cfg["budgets"])
    if sorted(int(x) for x in manifest.get("budgets", [])) != budgets:
        raise RuntimeError("M3 manifest budget set changed")
    pred = pd.read_csv(paths["predictions"])
    required = {
        "budget", "rho_global", "regime", "horizon", "scale",
        "A_G_l_max", "A_G_c_max", "A_G_q_min",
        "sigma_m3_dominant", "retained_mass", "omitted_mass",
        "deterministic_truncation_abs_error_bound",
        "worst_case_mc_variance_bound", "worst_case_mc_se_bound",
        "total_graph_trajectories",
    }
    missing = sorted(required.difference(pred.columns))
    if missing:
        raise RuntimeError("M3 prediction file missing: " + ", ".join(missing))
    if sorted(pred["budget"].astype(int).unique().tolist()) != budgets:
        raise RuntimeError("M3 prediction rows do not contain exactly frozen budgets")
    if pred.duplicated(["budget", "rho_global", "regime", "horizon"]).any():
        raise RuntimeError("duplicate M3 prediction points")
    if pred[["rho_global", "regime"]].drop_duplicates().shape[0] != 15:
        raise RuntimeError("M3 prediction does not contain exactly 15 queries")
    return manifest, pred, paths


def _validate_m2(contract: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Path]]:
    cfg = dict(contract["frozen_baselines"])
    qcfg = dict(contract["query_battery"])
    paths = {
        "final_contract": _resolve(cfg["m2_final_evaluation_contract"]),
        "prediction_contract": _resolve(cfg["m2_prediction_contract"]),
        "prediction_manifest": _resolve(cfg["m2_prediction_manifest"]),
        "predictions": _resolve(cfg["m2_predictions"]),
        "member_curves": _resolve(cfg["m2_member_curves"]),
        "variant_design": _resolve(cfg["m2_variant_design"]),
        "ledger_hashes": _resolve(cfg["m2_ledger_hashes"]),
        "selected_regions": _resolve(qcfg["selected_regions"]),
        "step0_manifest": _resolve(qcfg["step0_manifest"]),
    }
    old_final_contract = _read_json(paths["final_contract"])
    manifest, pred = _validate_m2_predictions(
        contract=old_final_contract,
        prediction_contract_path=paths["prediction_contract"],
        prediction_manifest_path=paths["prediction_manifest"],
        prediction_path=paths["predictions"],
        member_curves_path=paths["member_curves"],
        design_path=paths["variant_design"],
        ledger_hash_path=paths["ledger_hashes"],
        selected_regions_path=paths["selected_regions"],
        step0_manifest_path=paths["step0_manifest"],
    )
    return manifest, pred, paths


def _assert_identical_queries(m2: pd.DataFrame, m3: pd.DataFrame) -> None:
    cols = ["rho_global", "regime", "scale", "A_G_l_max", "A_G_c_max", "A_G_q_min"]
    a = m2[cols].drop_duplicates().sort_values(["rho_global", "regime"]).reset_index(drop=True)
    b = m3[cols].drop_duplicates().sort_values(["rho_global", "regime"]).reset_index(drop=True)
    if len(a) != 15 or len(b) != 15:
        raise RuntimeError("M2/M3 query banks are not both length 15")
    if a["regime"].astype(str).tolist() != b["regime"].astype(str).tolist():
        raise RuntimeError("M2/M3 regime order differs")
    for col in ["rho_global", "scale", "A_G_l_max", "A_G_c_max", "A_G_q_min"]:
        if not np.allclose(a[col].astype(float), b[col].astype(float), atol=1e-12, rtol=0.0):
            raise RuntimeError(f"M2/M3 frozen query field differs: {col}")


def _prepare_hash_payload(
    *,
    contract_path: Path,
    m3_paths: dict[str, Path],
    m2_paths: dict[str, Path],
) -> dict[str, Any]:
    payload = {
        "status": PREPARE_STATUS,
        "final_evaluation_contract_sha256": _sha256(contract_path),
        "M3_prediction_contract_sha256": _sha256(m3_paths["contract"]),
        "M3_prediction_manifest_sha256": _sha256(m3_paths["manifest"]),
        "M3_predictions_sha256": _sha256(m3_paths["predictions"]),
        "M3_design_sha256": _sha256(m3_paths["design"]),
        "M3_allocation_sha256": _sha256(m3_paths["allocation"]),
        "M3_ledger_hashes_sha256": _sha256(m3_paths["ledger_hashes"]),
        "M2_final_contract_sha256": _sha256(m2_paths["final_contract"]),
        "M2_prediction_contract_sha256": _sha256(m2_paths["prediction_contract"]),
        "M2_prediction_manifest_sha256": _sha256(m2_paths["prediction_manifest"]),
        "M2_predictions_sha256": _sha256(m2_paths["predictions"]),
        "M2_member_curves_sha256": _sha256(m2_paths["member_curves"]),
        "M2_variant_design_sha256": _sha256(m2_paths["variant_design"]),
        "M2_ledger_hashes_sha256": _sha256(m2_paths["ledger_hashes"]),
        "selected_regions_sha256": _sha256(m2_paths["selected_regions"]),
        "step0_manifest_sha256": _sha256(m2_paths["step0_manifest"]),
        "fresh_whitebox_read_or_generated": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    return payload


def _assert_prepare(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError("M3 final-evaluation prepare freeze absent; run --prepare-only first")
    frozen = _read_json(path)
    if frozen.get("status") != PREPARE_STATUS:
        raise RuntimeError("unexpected M3 final-evaluation prepare status")
    mismatch = [
        k for k, v in expected.items()
        if k != "git_commit" and str(frozen.get(k)) != str(v)
    ]
    if mismatch:
        raise RuntimeError("M3 final-evaluation frozen inputs changed: " + ", ".join(mismatch))
    if bool(frozen.get("fresh_whitebox_read_or_generated")):
        raise RuntimeError("prepare freeze unexpectedly reports fresh WB access")
    return frozen


def _wide_predictions(m2: pd.DataFrame, m3: pd.DataFrame) -> pd.DataFrame:
    keys = ["rho_global", "regime", "horizon"]
    m3_1400 = m3[m3["budget"].astype(int) == 1400][
        keys + [
            "sigma_m3_dominant",
            "retained_mass",
            "deterministic_truncation_abs_error_bound",
            "worst_case_mc_variance_bound",
            "worst_case_mc_se_bound",
            "total_graph_trajectories",
        ]
    ].rename(columns={
        "sigma_m3_dominant": "sigma_m3_B1400",
        "worst_case_mc_variance_bound": "m3_B1400_mc_var_bound",
        "worst_case_mc_se_bound": "m3_B1400_mc_se_bound",
        "total_graph_trajectories": "m3_B1400_graph_trajectories",
    })
    m3_2000 = m3[m3["budget"].astype(int) == 2000][
        keys + [
            "sigma_m3_dominant",
            "worst_case_mc_variance_bound",
            "worst_case_mc_se_bound",
            "total_graph_trajectories",
        ]
    ].rename(columns={
        "sigma_m3_dominant": "sigma_m3_B2000",
        "worst_case_mc_variance_bound": "m3_B2000_mc_var_bound",
        "worst_case_mc_se_bound": "m3_B2000_mc_se_bound",
        "total_graph_trajectories": "m3_B2000_graph_trajectories",
    })
    out = m2.merge(m3_1400, on=keys, how="inner", validate="one_to_one")
    out = out.merge(m3_2000, on=keys, how="inner", validate="one_to_one")
    if len(out) != len(m2):
        raise RuntimeError("M2/M3 prediction support mismatch")
    return out


def _metric(frame: pd.DataFrame, pred_col: str) -> dict[str, float]:
    valid = frame[pred_col].notna() & frame["sigma_whitebox"].notna()
    x = frame.loc[valid, pred_col].astype(float).to_numpy()
    y = frame.loc[valid, "sigma_whitebox"].astype(float).to_numpy()
    if len(x) == 0:
        return {
            "n_points": 0, "mae": np.nan, "rmse": np.nan,
            "bias": np.nan, "max_abs_error": np.nan,
        }
    e = x - y
    return {
        "n_points": int(len(e)),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e * e))),
        "bias": float(np.mean(e)),
        "max_abs_error": float(np.max(np.abs(e))),
    }


def _summaries(frame: pd.DataFrame, window: str) -> pd.DataFrame:
    methods = {
        "M0": "sigma_m0",
        "M1": "sigma_m1",
        "M2": "sigma_m2_mean",
        "M3_B1400": "sigma_m3_B1400",
        "M3_B2000": "sigma_m3_B2000",
    }
    groups: list[tuple[str, str, pd.DataFrame]] = [
        ("whole_battery", "ALL", frame)
    ]
    groups.extend(("per_regime", str(k), g) for k, g in frame.groupby("regime", sort=True))
    groups.extend(
        ("per_rho", f"{float(k):.15g}", g)
        for k, g in frame.groupby("rho_global", sort=True)
    )
    groups.extend(
        ("per_rho_x_regime", f"rho={float(rho):.15g}|{regime}", g)
        for (rho, regime), g in frame.groupby(["rho_global", "regime"], sort=True)
    )
    rows = []
    for level, key, g in groups:
        for method, col in methods.items():
            met = _metric(g, col)
            rows.append({
                "window": window,
                "summary_level": level,
                "summary_key": key,
                "method": method,
                **met,
                "n_queries": int(g[["rho_global", "regime"]].drop_duplicates().shape[0]),
                "n_not_applicable_queries": (
                    int(
                        g.loc[
                            g["m0_status"].astype(str) == "NOT_APPLICABLE",
                            ["rho_global", "regime"],
                        ].drop_duplicates().shape[0]
                    )
                    if method == "M0" else 0
                ),
            })
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M3-v4 final evaluation contract status")

    m3_manifest, m3_pred, m3_paths = _validate_m3(contract)
    m2_manifest, m2_pred, m2_paths = _validate_m2(contract)
    _assert_identical_queries(m2_pred, m3_pred)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    prepare_path = output / "m3_v4_final_eval_prepare_manifest.json"
    prepare_payload = _prepare_hash_payload(
        contract_path=contract_path,
        m3_paths=m3_paths,
        m2_paths=m2_paths,
    )

    if args.prepare_only:
        _write_json(prepare_path, prepare_payload)
        print("M3_V4_FINAL_EVAL_PREPARE_PASS_NO_FRESH_WHITEBOX")
        print("methods=M0,M1,M2,M3_B1400,M3_B2000")
        print("fresh_WB_seeds=38000..38199 n=200")
        print(f"M3_prediction_manifest_sha256={_sha256(m3_paths['manifest'])}")
        print(f"M3_predictions_sha256={_sha256(m3_paths['predictions'])}")
        print(f"prepare_manifest={prepare_path}")
        print(f"python_wall_seconds={time.perf_counter()-started:.3f}")
        return

    _assert_prepare(prepare_path, prepare_payload)

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    horizons = [float(v) for v in common_horizon_support(metadata)]
    rhos = sorted(float(v) for v in common_same_rho_support(metadata))
    workload = _common_workload_contract(metadata)
    if not np.allclose(
        rhos,
        sorted(float(v) for v in m3_pred["rho_global"].unique()),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("M3 prediction rho support differs from frozen I1")

    qcfg = dict(contract["query_battery"])
    step0_contract = _read_json(_resolve(qcfg["step0_contract"]))
    provider_surrogates, execution_fraction, provenance = _validate_hidden_model(
        step0_contract,
        phase1_config_path=args.phase1_config.resolve(),
    )
    if str(provenance["case_id"]) != "D300000000_d0.200":
        raise RuntimeError("fresh M3 WB provider process is not matched D300")
    graph_spec = _fixed_graph_spec(_read_json(args.m0_contract.resolve()))

    wbcfg = dict(contract["fresh_whitebox"])
    seeds = tuple(range(int(wbcfg["seed_start"]), int(wbcfg["seed_end_inclusive"]) + 1))
    if seeds != tuple(range(38000, 38200)) or len(seeds) != int(wbcfg["n_trajectories"]):
        raise RuntimeError("fresh M3 WB seed bank changed")

    ledger_path = output / "m3_v4_fresh_whitebox_ledger.csv"
    ledger, reused = _generate_or_load_final_wb(
        path=ledger_path,
        provider_surrogates=provider_surrogates,
        graph_spec=graph_spec,
        workload=workload,
        seeds=seeds,
        canonical_ipt=float(provenance["effective_IPT"]),
        execution_fraction=float(execution_fraction),
    )

    wide = _wide_predictions(m2_pred, m3_pred)
    wb = _build_wb_curves(
        ledger=ledger,
        predictions=wide,
        horizons=horizons,
        workload=workload,
    )
    wb_path = output / "m3_v4_fresh_whitebox_curves.csv"
    wb.to_csv(wb_path, index=False)

    comparison = wide.merge(
        wb[["rho_global", "regime", "horizon", "sigma_whitebox"]],
        on=["rho_global", "regime", "horizon"],
        how="inner",
        validate="one_to_one",
    )
    if len(comparison) != len(wide):
        raise RuntimeError("fresh WB support does not match prediction support")

    for label, col in {
        "m0": "sigma_m0",
        "m1": "sigma_m1",
        "m2": "sigma_m2_mean",
        "m3_B1400": "sigma_m3_B1400",
        "m3_B2000": "sigma_m3_B2000",
    }.items():
        comparison[f"error_{label}"] = comparison[col] - comparison["sigma_whitebox"]

    comparison_path = output / "m3_v4_final_comparison.csv"
    comparison.to_csv(comparison_path, index=False)

    full_summary = _summaries(comparison, "FULL_FROZEN_HORIZON_SUPPORT")
    diag = comparison[
        (comparison["horizon"].astype(float) >= 60 - TOL)
        & (comparison["horizon"].astype(float) <= 240 + TOL)
    ].copy()
    diag_summary = _summaries(diag, "H60_H240")
    summary = pd.concat([full_summary, diag_summary], ignore_index=True)
    summary_path = output / "m3_v4_final_error_metrics.csv"
    summary.to_csv(summary_path, index=False)

    regime_means = diag.groupby(["rho_global", "regime"], as_index=False).agg(
        sigma_whitebox_mean=("sigma_whitebox", "mean"),
        sigma_m0_mean=("sigma_m0", "mean"),
        sigma_m1_mean=("sigma_m1", "mean"),
        sigma_m2_mean=("sigma_m2_mean", "mean"),
        sigma_m3_B1400_mean=("sigma_m3_B1400", "mean"),
        sigma_m3_B2000_mean=("sigma_m3_B2000", "mean"),
    )
    regime_means_path = output / "m3_v4_final_regime_means_H60_H240.csv"
    regime_means.to_csv(regime_means_path, index=False)

    manifest_path = output / "m3_v4_final_evaluation_manifest.json"
    _write_json(
        manifest_path,
        {
            "status": COMPLETE_STATUS,
            "contract_sha256": _sha256(contract_path),
            "prepare_manifest_sha256": _sha256(prepare_path),
            "M3_prediction_manifest_sha256": _sha256(m3_paths["manifest"]),
            "M3_predictions_sha256": _sha256(m3_paths["predictions"]),
            "M2_prediction_manifest_sha256": _sha256(m2_paths["prediction_manifest"]),
            "M2_predictions_sha256": _sha256(m2_paths["predictions"]),
            "fresh_whitebox_ledger_sha256": _sha256(ledger_path),
            "fresh_whitebox_curves_sha256": _sha256(wb_path),
            "comparison_sha256": _sha256(comparison_path),
            "error_metrics_sha256": _sha256(summary_path),
            "regime_means_H60_H240_sha256": _sha256(regime_means_path),
            "provider_process_sha256": provenance["provider_process_sha256"],
            "fresh_whitebox_seed_start": int(seeds[0]),
            "fresh_whitebox_seed_end_inclusive": int(seeds[-1]),
            "n_fresh_whitebox_trajectories": int(len(seeds)),
            "fresh_whitebox_ledger_reused": bool(reused),
            "M3_lambda_changed": False,
            "M3_weights_changed": False,
            "M3_retained_set_changed": False,
            "M3_allocation_changed": False,
            "M3_budgets_changed": False,
            "M2_changed": False,
            "repair_after_whitebox": False,
            "M3_v4_closed_after_evaluation": True,
            "python_wall_seconds": float(time.perf_counter() - started),
            "git_commit": _git_head(FIRST_SCIENCE.parent),
        },
    )

    headline = summary[
        (summary["window"] == "H60_H240")
        & (summary["summary_level"].isin(["whole_battery", "per_regime"]))
    ]
    print("\nM3_V4_FINAL_HEADLINE_ERROR_METRICS_H60_H240")
    print(headline.to_string(index=False))
    print("\nM3_V4_FINAL_REGIME_MEANS_H60_H240")
    print(regime_means.to_string(index=False))
    print("\nM3_V4_FINAL_EVALUATION_COMPLETE")
    print(f"manifest={manifest_path}")
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Fresh final WB evaluation of frozen M3-v4")
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_v4_final_evaluation_v1.json",
    )
    p.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    p.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json",
    )
    p.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    p.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_v4_final_evaluation_v1",
    )
    stages = p.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only", action="store_true")
    stages.add_argument("--evaluate", action="store_true")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
