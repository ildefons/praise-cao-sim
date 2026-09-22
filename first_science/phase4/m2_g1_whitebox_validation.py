"""Prospective G1 white-box generation and validation for frozen M2.

This stage is legal only after the full blind G1 prediction freeze exists.

Two-step usage:
  1. --generate-only:
       validate the pinned pre-whitebox prediction freeze, then generate the
       independent hidden-model G1 white-box ledger on seeds 31000..31099.
  2. default:
       verify the frozen prediction and white-box-generation manifests, then
       evaluate M0, M1 and the frozen equal-weight M2 ensemble exactly once
       against the prospective G1 white-box curve.

No fitting, candidate selection, reweighting, graph redesign or threshold
selection occurs in this file.
"""
from __future__ import annotations

import argparse
import json
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
)
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_b6_joint_ensemble_whitebox import (  # noqa: E402
    _ambiguity_table,
    _plot_four_way,
    _point_summaries,
    _snap_frame_to_frozen_grid,
)
from m2_g1_graph_simulator import execute_one_g1_prediction_trajectory  # noqa: E402
from m2_g1_public_adapter import (  # noqa: E402
    build_g1_public_graph_spec,
    validate_g1_public_graph_spec,
)

EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_M2_G1_PROSPECTIVE_WHITEBOX_VALIDATION_V1"
EXPECTED_PREDICTION_STATUS = "FROZEN_PHASE4_M2_G1_BLIND_PREDICTIONS_V1"
EXPECTED_GENERATION_STATUS = "PHASE4_M2_G1_WHITEBOX_GENERATION_COMPLETE_V1"
EXPECTED_EVALUATION_STATUS = "PHASE4_M2_G1_PROSPECTIVE_VALIDATION_COMPLETE_V1"
TOL = 1e-12
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _validate_prediction_freeze(
    *,
    contract: dict[str, Any],
    prediction_manifest_path: Path,
    ensemble_path: Path,
    m0_path: Path,
    design_path: Path,
    candidate_path: Path,
    joint_curves_path: Path,
    public_condition_path: Path,
) -> dict[str, Any]:
    freeze_cfg = dict(contract["prediction_freeze"])
    required_sha = str(freeze_cfg["required_sha256"])
    actual_sha = _sha256(prediction_manifest_path)
    if actual_sha != required_sha:
        raise RuntimeError(
            "G1 prediction-freeze manifest hash mismatch: "
            f"expected={required_sha} actual={actual_sha}"
        )

    manifest = _read_json(prediction_manifest_path)
    if manifest.get("status") != EXPECTED_PREDICTION_STATUS:
        raise RuntimeError("unexpected G1 prediction-freeze status")
    if bool(manifest.get("smoke_mode")):
        raise RuntimeError("prospective G1 evaluation requires the full non-smoke prediction run")
    if str(manifest.get("condition_id")) != str(freeze_cfg["required_condition_id"]):
        raise RuntimeError("G1 prediction condition ID mismatch")
    if bool(manifest.get("G1_whitebox_generated")):
        raise RuntimeError("prediction freeze says G1 white-box was generated before freeze")
    if bool(manifest.get("G1_whitebox_read")):
        raise RuntimeError("prediction freeze says G1 white-box was read before freeze")
    if bool(manifest.get("phase1_graph_reference_read")):
        raise RuntimeError("prediction stage unexpectedly read the Phase-1 graph reference")
    if bool(manifest.get("provider_private_trace_read")):
        raise RuntimeError("prediction stage unexpectedly read private provider traces")
    if bool(manifest.get("provider_private_parameter_read")):
        raise RuntimeError("prediction stage unexpectedly read private provider parameters")
    if bool(manifest.get("provider_search")):
        raise RuntimeError("prediction stage unexpectedly performed provider search")
    if bool(manifest.get("candidate_set_changed")):
        raise RuntimeError("prediction stage changed the frozen candidate set")
    if bool(manifest.get("candidate_parameters_changed")):
        raise RuntimeError("prediction stage changed frozen candidate parameters")
    if bool(manifest.get("ensemble_weights_changed")):
        raise RuntimeError("prediction stage changed frozen ensemble weights")
    if not bool(manifest.get("equal_weight_joint_ensemble")):
        raise RuntimeError("prediction stage is not the frozen equal-weight ensemble")
    if bool(manifest.get("M1_in_M2_ensemble")):
        raise RuntimeError("prediction stage unexpectedly includes M1 in M2")

    integer_checks = {
        "prediction_seed_start": int(freeze_cfg["required_prediction_seed_start"]),
        "prediction_seed_end_inclusive": int(
            freeze_cfg["required_prediction_seed_end_inclusive"]
        ),
        "n_trajectories_per_variant": int(
            freeze_cfg["required_n_trajectories_per_variant"]
        ),
        "n_m2_joint_variants": int(freeze_cfg["required_n_m2_joint_variants"]),
    }
    for key, expected in integer_checks.items():
        if int(manifest.get(key, -1)) != expected:
            raise RuntimeError(f"G1 prediction-freeze {key} mismatch")

    required_hashes = dict(freeze_cfg["required_artifact_hashes"])
    for field, expected in required_hashes.items():
        if str(manifest.get(field)) != str(expected):
            raise RuntimeError(f"G1 prediction-freeze field {field} changed")

    actual_artifacts = {
        "ensemble_curve_sha256": _sha256(ensemble_path),
        "m0_curve_sha256": _sha256(m0_path),
        "variant_design_sha256": _sha256(design_path),
        "frozen_candidate_set_sha256": _sha256(candidate_path),
        "joint_graph_sigma_curves_sha256": _sha256(joint_curves_path),
        "public_condition_manifest_sha256": _sha256(public_condition_path),
    }
    for field, actual in actual_artifacts.items():
        expected = str(manifest.get(field))
        if str(actual) != expected:
            raise RuntimeError(
                f"current prediction artifact hash differs from frozen manifest: {field}"
            )

    # The prospective WB generator reuses exactly the public G1 simulator and
    # public adapter that were hashed before white-box access.
    if _sha256(HERE / "m2_g1_graph_simulator.py") != str(
        manifest["g1_simulator_sha256"]
    ):
        raise RuntimeError("G1 simulator changed after blind prediction freeze")
    if _sha256(HERE / "m2_g1_public_adapter.py") != str(
        manifest["g1_public_adapter_sha256"]
    ):
        raise RuntimeError("G1 public adapter changed after blind prediction freeze")

    return manifest


def _validate_hidden_model(
    *,
    contract: dict[str, Any],
    phase1_config_path: Path,
) -> tuple[dict[str, GraphProviderSurrogate], float, dict[str, Any]]:
    cfg = _read_json(phase1_config_path)
    wb = dict(contract["whitebox_model"])

    if str(wb["case_id"]) not in str(cfg["confirmation"]["frozen_after_selection"]):
        raise RuntimeError("Phase-1 config does not confirm the frozen hidden physical case")

    family = dict(cfg["provider_family"])
    checks = {
        "instruction_cv": float(wb["instruction_cv"]),
        "effective_ipt": float(wb["effective_IPT"]),
        "cost_rate": float(wb["cost_rate"]),
        "x": float(wb["execution_fraction_x"]),
    }
    for key, expected in checks.items():
        if abs(float(family[key]) - expected) > TOL:
            raise RuntimeError(f"Phase-1 hidden-model {key} differs from G1 WB contract")

    center = float(wb["center_instruction_mean"])
    delta = float(wb["dispersion"])
    derived_instruction_means = {
        "ProviderA": center * (1.0 - delta),
        "ProviderB": center,
        "ProviderC": center * (1.0 + delta),
    }
    frozen_instruction_means = {
        str(k): float(v) for k, v in wb["provider_instruction_means"].items()
    }
    for provider in PROVIDERS:
        if abs(
            derived_instruction_means[provider] - frozen_instruction_means[provider]
        ) > TOL:
            raise RuntimeError(f"{provider}: hidden instruction-mean derivation mismatch")

    x = float(wb["execution_fraction_x"])
    ipt = float(wb["effective_IPT"])
    cv = float(wb["instruction_cv"])
    cost_rate = float(wb["cost_rate"])
    frozen_mu = {
        str(k): float(v)
        for k, v in wb["derived_mean_service_times_for_native_G1_runner"].items()
    }
    surrogates: dict[str, GraphProviderSurrogate] = {}
    for provider in PROVIDERS:
        mu = float(derived_instruction_means[provider]) * x / ipt
        if abs(mu - frozen_mu[provider]) > TOL:
            raise RuntimeError(f"{provider}: hidden service-time derivation mismatch")
        surrogates[provider] = GraphProviderSurrogate(
            mean_service_time=mu,
            cost_rate=cost_rate,
            service_cv=cv,
        )

    hidden_manifest = {
        "case_id": str(wb["case_id"]),
        "center_instruction_mean": center,
        "dispersion": delta,
        "provider_instruction_means": derived_instruction_means,
        "instruction_cv": cv,
        "effective_IPT": ipt,
        "cost_rate": cost_rate,
        "execution_fraction_x": x,
        "quality": float(wb["quality"]),
        "derived_mean_service_times": {
            provider: float(surrogates[provider].mean_service_time)
            for provider in PROVIDERS
        },
        "phase1_config_sha256": _sha256(phase1_config_path),
    }
    return surrogates, x, hidden_manifest


def _whitebox_seeds(contract: dict[str, Any]) -> tuple[int, ...]:
    cfg = dict(contract["whitebox_generation"])
    seeds = tuple(
        range(
            int(cfg["trajectory_seed_start"]),
            int(cfg["trajectory_seed_end_inclusive"]) + 1,
        )
    )
    if len(seeds) != int(cfg["n_trajectories"]):
        raise RuntimeError("G1 WB seed bank length differs from frozen contract")
    return seeds


def _generate_whitebox(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    prediction_manifest_path: Path,
    prediction_manifest: dict[str, Any],
    public_condition_path: Path,
    phase1_config_path: Path,
    i1_card_root: Path,
    i1_manifest_path: Path,
    output: Path,
) -> None:
    surrogates, execution_fraction, hidden_model = _validate_hidden_model(
        contract=contract,
        phase1_config_path=phase1_config_path,
    )

    public_condition = _read_json(public_condition_path)
    graph_spec = build_g1_public_graph_spec()
    validate_g1_public_graph_spec(graph_spec)
    if public_condition != graph_spec:
        raise RuntimeError("frozen G1 public condition differs from current public adapter")

    metadata, _, _ = load_rho_conditioned_i1_cards(
        i1_card_root.resolve(), i1_manifest_path.resolve()
    )
    workload = _common_workload_contract(metadata)
    seeds = _whitebox_seeds(contract)

    ledger_path = output / "m2_g1_whitebox_ledger.csv"
    if ledger_path.exists():
        ledger = pd.read_csv(ledger_path)
        required = {"trajectory", "trajectory_seed", "request_id"}
        missing = sorted(required.difference(ledger.columns))
        if missing:
            raise RuntimeError("existing G1 WB ledger lacks checkpoint fields: " + ", ".join(missing))
        actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique().tolist()))
        if actual != seeds:
            raise RuntimeError("existing G1 WB ledger uses a different seed bank")
        if int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError("existing G1 WB ledger trajectory count mismatch")
        if ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError("existing G1 WB ledger contains duplicate requests")
        reused = True
        print("M2-G1 WB resume: loaded completed white-box ledger", flush=True)
    else:
        frames: list[pd.DataFrame] = []
        for trajectory, seed in enumerate(seeds):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                one = execute_one_g1_prediction_trajectory(
                    provider_surrogates=surrogates,
                    graph_spec=graph_spec,
                    workload_period=float(workload["period"]),
                    stop_time=float(workload["horizon_max"]),
                    trajectory_seed=int(seed),
                    canonical_ipt=float(hidden_model["effective_IPT"]),
                    execution_fraction=float(execution_fraction),
                )
            one.insert(0, "trajectory", int(trajectory))
            one.insert(1, "trajectory_seed", int(seed))
            frames.append(one)
            if (
                trajectory == 0
                or (trajectory + 1) % 25 == 0
                or trajectory + 1 == len(seeds)
            ):
                print(f"  G1-WB: {trajectory + 1}/{len(seeds)}", flush=True)
        ledger = pd.concat(frames, ignore_index=True)
        ledger.to_csv(ledger_path, index=False)
        reused = False

    generation_manifest = {
        "status": EXPECTED_GENERATION_STATUS,
        "condition_id": str(prediction_manifest["condition_id"]),
        "prediction_freeze_manifest_sha256": _sha256(prediction_manifest_path),
        "prediction_freeze_validated_before_generation": True,
        "whitebox_generated_after_prediction_freeze": True,
        "whitebox_used_for_model_selection": False,
        "whitebox_used_for_weight_selection": False,
        "whitebox_used_for_graph_design": False,
        "whitebox_used_for_success_criteria": False,
        "whitebox_seed_start": int(seeds[0]),
        "whitebox_seed_end_inclusive": int(seeds[-1]),
        "n_whitebox_trajectories": int(len(seeds)),
        "seed_bank_independent_of_prediction_bank": True,
        "hidden_model": hidden_model,
        "g1_public_condition_sha256": _sha256(public_condition_path),
        "g1_simulator_sha256": _sha256(HERE / "m2_g1_graph_simulator.py"),
        "g1_public_adapter_sha256": _sha256(HERE / "m2_g1_public_adapter.py"),
        "contract_sha256": _sha256(contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "whitebox_ledger_sha256": _sha256(ledger_path),
        "n_request_rows": int(len(ledger)),
        "checkpoint_reused": bool(reused),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "next_gate": (
            "Evaluate only the already-frozen G1 M0/M1/M2 predictions against "
            "this generated white-box ledger. No M2 changes are permitted."
        ),
    }
    manifest_path = output / "m2_g1_whitebox_generation_manifest_v1.json"
    _write_json(manifest_path, generation_manifest)

    print("M2_G1_WHITEBOX_GENERATION_COMPLETE_AFTER_PREDICTION_FREEZE")
    print(f"whitebox_seed_bank={seeds[0]}..{seeds[-1]} n={len(seeds)}")
    print(f"n_request_rows={len(ledger)}")
    print(f"ledger={ledger_path}")
    print(f"manifest={manifest_path}")


def _validate_generation(
    *,
    contract: dict[str, Any],
    prediction_manifest_path: Path,
    generation_manifest_path: Path,
    ledger_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if not generation_manifest_path.exists():
        raise RuntimeError(
            "G1 white-box generation manifest is absent. Run --generate-only first."
        )
    manifest = _read_json(generation_manifest_path)
    if manifest.get("status") != EXPECTED_GENERATION_STATUS:
        raise RuntimeError("unexpected G1 white-box generation status")
    if str(manifest.get("prediction_freeze_manifest_sha256")) != _sha256(
        prediction_manifest_path
    ):
        raise RuntimeError("G1 WB generation is not tied to the current frozen prediction manifest")
    if not bool(manifest.get("prediction_freeze_validated_before_generation")):
        raise RuntimeError("G1 WB generation did not validate prediction freeze first")
    if not bool(manifest.get("whitebox_generated_after_prediction_freeze")):
        raise RuntimeError("G1 WB generation ordering is invalid")
    if bool(manifest.get("whitebox_used_for_model_selection")):
        raise RuntimeError("G1 WB was used for model selection")
    if bool(manifest.get("whitebox_used_for_weight_selection")):
        raise RuntimeError("G1 WB was used for weight selection")
    if bool(manifest.get("whitebox_used_for_graph_design")):
        raise RuntimeError("G1 WB was used for graph design")
    if bool(manifest.get("whitebox_used_for_success_criteria")):
        raise RuntimeError("G1 WB was used for success criteria")

    seeds = _whitebox_seeds(contract)
    if int(manifest.get("whitebox_seed_start", -1)) != seeds[0]:
        raise RuntimeError("G1 WB generation seed start mismatch")
    if int(manifest.get("whitebox_seed_end_inclusive", -1)) != seeds[-1]:
        raise RuntimeError("G1 WB generation seed end mismatch")
    if int(manifest.get("n_whitebox_trajectories", -1)) != len(seeds):
        raise RuntimeError("G1 WB generation trajectory count mismatch")
    if str(manifest.get("whitebox_ledger_sha256")) != _sha256(ledger_path):
        raise RuntimeError("G1 WB ledger changed after generation freeze")

    ledger = pd.read_csv(ledger_path)
    actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique().tolist()))
    if actual != seeds:
        raise RuntimeError("G1 WB ledger seed bank mismatch")
    if int(ledger["trajectory"].nunique()) != len(seeds):
        raise RuntimeError("G1 WB ledger trajectory count mismatch")
    if ledger[["trajectory", "request_id"]].duplicated().any():
        raise RuntimeError("G1 WB ledger contains duplicate requests")
    return manifest, ledger


def _build_whitebox_curve(
    *,
    ensemble: pd.DataFrame,
    ledger: pd.DataFrame,
    horizons: list[float],
    rho_support: list[float],
    workload: dict[str, Any],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rho in rho_support:
        selected = ensemble[
            np.isclose(
                ensemble["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
        ]
        triples = selected[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"rho={rho}: frozen G1 prediction does not expose one A_G")
        rec = triples.iloc[0]

        # Import here to keep the hidden-generation stage simple.
        from m0_analytic_composition import AdmissibilityBoundary

        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = build_empirical_graph_sigma_curve(
            ledger,
            boundary=boundary,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column="sigma_whitebox",
        )
        curve.insert(0, "rho_global", float(rho))
        curve["A_G_l_max"] = float(boundary.l_max)
        curve["A_G_c_max"] = float(boundary.c_max)
        curve["A_G_q_min"] = float(boundary.q_min)
        rows.append(curve)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)


def _evaluate(
    *,
    contract_path: Path,
    contract: dict[str, Any],
    prediction_manifest_path: Path,
    generation_manifest_path: Path,
    ledger_path: Path,
    ensemble_path: Path,
    m0_path: Path,
    i1_card_root: Path,
    i1_manifest_path: Path,
    output: Path,
) -> None:
    generation_manifest, ledger = _validate_generation(
        contract=contract,
        prediction_manifest_path=prediction_manifest_path,
        generation_manifest_path=generation_manifest_path,
        ledger_path=ledger_path,
    )

    metadata, _, _ = load_rho_conditioned_i1_cards(
        i1_card_root.resolve(), i1_manifest_path.resolve()
    )
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    ensemble = pd.read_csv(ensemble_path)
    m0 = pd.read_csv(m0_path)
    wb = _build_whitebox_curve(
        ensemble=ensemble,
        ledger=ledger,
        horizons=horizons,
        rho_support=rho_support,
        workload=workload,
    )

    frozen_rhos = sorted(float(v) for v in ensemble["rho_global"].unique())
    frozen_horizons = sorted(float(v) for v in ensemble["horizon"].unique())

    m0_join = _snap_frame_to_frozen_grid(
        m0[["rho_global", "horizon", "sigma_i1_m0"]],
        frozen_rhos=frozen_rhos,
        frozen_horizons=frozen_horizons,
        label="G1 M0",
    ).rename(columns={"sigma_i1_m0": "sigma_m0"})

    wb_join = _snap_frame_to_frozen_grid(
        wb[
            [
                "rho_global",
                "horizon",
                "sigma_whitebox",
                "A_G_l_max",
                "A_G_c_max",
                "A_G_q_min",
            ]
        ],
        frozen_rhos=frozen_rhos,
        frozen_horizons=frozen_horizons,
        label="G1 whitebox",
    ).rename(
        columns={
            "A_G_l_max": "wb_A_G_l_max",
            "A_G_c_max": "wb_A_G_c_max",
            "A_G_q_min": "wb_A_G_q_min",
        }
    )

    comparison = ensemble.merge(
        m0_join,
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    ).merge(
        wb_join,
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    )
    if len(comparison) != len(ensemble):
        raise RuntimeError("prospective G1 comparison did not cover every frozen prediction point")

    for base_col, wb_col in (
        ("A_G_l_max", "wb_A_G_l_max"),
        ("A_G_c_max", "wb_A_G_c_max"),
        ("A_G_q_min", "wb_A_G_q_min"),
    ):
        if not np.allclose(
            comparison[base_col].astype(float).to_numpy(),
            comparison[wb_col].astype(float).to_numpy(),
            atol=TOL,
            rtol=0.0,
        ):
            raise RuntimeError(f"prospective G1 WB {base_col} differs from frozen prediction A_G")
    comparison = comparison.drop(
        columns=["wb_A_G_l_max", "wb_A_G_c_max", "wb_A_G_q_min"]
    ).rename(columns={"sigma_m1_same_seed_bank": "sigma_m1"})

    comparison["error_m0_minus_whitebox"] = (
        comparison["sigma_m0"].astype(float) - comparison["sigma_whitebox"].astype(float)
    )
    comparison["error_m1_minus_whitebox"] = (
        comparison["sigma_m1"].astype(float) - comparison["sigma_whitebox"].astype(float)
    )
    comparison["error_m2_minus_whitebox"] = (
        comparison["sigma_m2_mean"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
    )

    ambiguity_points, ambiguity_summary = _ambiguity_table(comparison)
    comparison = comparison.merge(
        ambiguity_points[
            [
                "rho_global",
                "horizon",
                "range_width",
                "whitebox_inside_range",
                "whitebox_below_range",
                "whitebox_above_range",
                "distance_outside_range",
            ]
        ],
        on=["rho_global", "horizon"],
        how="left",
        validate="one_to_one",
    )

    overall, per_rho = _point_summaries(comparison)

    overall_rec = overall.iloc[0]
    primary_pass = float(overall_rec["m2_mae"]) < float(overall_rec["m1_mae"])
    confirmatory_pass = float(overall_rec["m2_rmse"]) < float(overall_rec["m1_rmse"])
    rho_m2_better = int((per_rho["m2_mae"] < per_rho["m1_mae"]).sum())
    rho_consistency_pass = rho_m2_better >= 3

    pointwise_path = output / "m2_g1_pointwise_comparison.csv"
    overall_path = output / "m2_g1_overall_point_summary.csv"
    per_rho_path = output / "m2_g1_per_rho_point_summary.csv"
    ambiguity_path = output / "m2_g1_ambiguity_summary.csv"
    wb_path = output / "m2_g1_whitebox_curve.csv"
    plot_path = output / "m2_g1_m0_m1_m2_whitebox.png"

    comparison.to_csv(pointwise_path, index=False)
    overall.to_csv(overall_path, index=False)
    per_rho.to_csv(per_rho_path, index=False)
    ambiguity_summary.to_csv(ambiguity_path, index=False)
    wb.to_csv(wb_path, index=False)
    _plot_four_way(comparison, plot_path)

    manifest = {
        "status": EXPECTED_EVALUATION_STATUS,
        "evidence_role": "prospective validation evidence",
        "condition_id": "G1_ASYM_PARALL_V1",
        "prediction_freeze_manifest_sha256": _sha256(prediction_manifest_path),
        "whitebox_generation_manifest_sha256": _sha256(generation_manifest_path),
        "whitebox_ledger_sha256": _sha256(ledger_path),
        "contract_sha256": _sha256(contract_path),
        "prediction_frozen_before_whitebox_generation": True,
        "whitebox_used_for_model_selection": False,
        "whitebox_used_for_weight_selection": False,
        "whitebox_used_for_graph_design": False,
        "whitebox_used_for_success_criteria": False,
        "M2_changed_after_G1_whitebox": False,
        "primary_criterion": str(contract["prospective_success_criteria"]["primary"]),
        "primary_pass": bool(primary_pass),
        "confirmatory_criterion": str(
            contract["prospective_success_criteria"]["confirmatory"]
        ),
        "confirmatory_pass": bool(confirmatory_pass),
        "rho_consistency_criterion": str(
            contract["prospective_success_criteria"]["rho_consistency"]
        ),
        "rho_slices_M2_MAE_better_than_M1": int(rho_m2_better),
        "rho_consistency_pass": bool(rho_consistency_pass),
        "overall_metrics": {
            key: float(value)
            for key, value in overall_rec.items()
            if key != "n_points"
        },
        "n_points": int(overall_rec["n_points"]),
        "n_whitebox_trajectories": int(
            generation_manifest["n_whitebox_trajectories"]
        ),
        "range_is_confidence_interval": False,
        "Jaccard_D_A": "N/A",
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "whitebox_curve": wb_path.name,
            "pointwise_comparison": pointwise_path.name,
            "overall_point_summary": overall_path.name,
            "per_rho_point_summary": per_rho_path.name,
            "ambiguity_summary": ambiguity_path.name,
            "plot": plot_path.name,
        },
        "chapter_close_rule": str(
            contract["prospective_success_criteria"]["chapter_close"]
        ),
        "next_gate": (
            "Write and freeze the final M2 chapter-close note. Do not modify M2 "
            "from G1. Subsequent methodological development belongs to M3."
        ),
    }
    manifest_path = output / "m2_g1_prospective_validation_manifest_v1.json"
    _write_json(manifest_path, manifest)

    outcome = "PASS" if primary_pass else "FAIL"
    print(f"M2_G1_PROSPECTIVE_PRIMARY_{outcome}")
    print("\nOVERALL_POINT_PREDICTION")
    print(overall.to_string(index=False))
    print("\nPER_RHO_POINT_PREDICTION")
    print(per_rho.to_string(index=False))
    print("\nM2_AMBIGUITY_RANGE")
    print(ambiguity_summary.to_string(index=False))
    print("\nPROSPECTIVE_CRITERIA")
    print(f"primary_M2_MAE_lt_M1={primary_pass}")
    print(f"confirmatory_M2_RMSE_lt_M1={confirmatory_pass}")
    print(
        f"rho_consistency_M2_MAE_better={rho_m2_better}/5 "
        f"pass={rho_consistency_pass}"
    )
    print("M2_G1_PROSPECTIVE_VALIDATION_COMPLETE")
    print(f"plot={plot_path}")
    print(f"manifest={manifest_path}")


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected G1 WB validation-contract status")

    prediction_manifest_path = args.prediction_manifest.resolve()
    ensemble_path = args.ensemble_curve.resolve()
    m0_path = args.m0_curve.resolve()
    design_path = args.variant_design.resolve()
    candidate_path = args.candidate_set.resolve()
    joint_curves_path = args.joint_curves.resolve()
    public_condition_path = args.public_condition.resolve()

    prediction_manifest = _validate_prediction_freeze(
        contract=contract,
        prediction_manifest_path=prediction_manifest_path,
        ensemble_path=ensemble_path,
        m0_path=m0_path,
        design_path=design_path,
        candidate_path=candidate_path,
        joint_curves_path=joint_curves_path,
        public_condition_path=public_condition_path,
    )

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if args.generate_only:
        _generate_whitebox(
            contract_path=contract_path,
            contract=contract,
            prediction_manifest_path=prediction_manifest_path,
            prediction_manifest=prediction_manifest,
            public_condition_path=public_condition_path,
            phase1_config_path=args.phase1_config.resolve(),
            i1_card_root=args.i1_card_root.resolve(),
            i1_manifest_path=args.i1_manifest.resolve(),
            output=output,
        )
        print(f"python_wall_seconds={time.perf_counter() - started:.3f}")
        return

    generation_manifest_path = (
        output / "m2_g1_whitebox_generation_manifest_v1.json"
    )
    ledger_path = output / "m2_g1_whitebox_ledger.csv"
    _evaluate(
        contract_path=contract_path,
        contract=contract,
        prediction_manifest_path=prediction_manifest_path,
        generation_manifest_path=generation_manifest_path,
        ledger_path=ledger_path,
        ensemble_path=ensemble_path,
        m0_path=m0_path,
        i1_card_root=args.i1_card_root.resolve(),
        i1_manifest_path=args.i1_manifest.resolve(),
        output=output,
    )
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and evaluate the prospective G1 white-box reference"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_g1_whitebox_validation_v1.json",
    )
    parser.add_argument(
        "--prediction-manifest",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_prediction_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--ensemble-curve",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_ensemble_curve.csv",
    )
    parser.add_argument(
        "--m0-curve",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_m0_curve.csv",
    )
    parser.add_argument(
        "--joint-curves",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_joint_graph_sigma_curves.csv",
    )
    parser.add_argument(
        "--variant-design",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_joint_variant_design.csv",
    )
    parser.add_argument(
        "--candidate-set",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_frozen_candidate_set.csv",
    )
    parser.add_argument(
        "--public-condition",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_public_condition_manifest_v1.json",
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
        default=HERE / "results" / "m2_g1_prospective_validation_v1",
    )
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
