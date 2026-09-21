"""M2-B6: external evaluation of the frozen M2-B5 joint ensemble.

Scientific ordering is enforced in two invocations:

1. --prepare-only validates and fingerprints the already-materialized blind B5
   predictions without reading graph white-box evidence.
2. The evaluation invocation refuses to proceed unless those fingerprints still
   match, then opens the frozen Phase-1 graph ledger and evaluates M0, the
   same-seed B5 M1 reference, the frozen M2 equal-weight mean, and the frozen
   M2 finite-portfolio ambiguity range on identical A_G/rho/H support.

No graph simulation, provider search, candidate replacement, retuning, or
ensemble reweighting occurs in B6.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
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
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402

EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_M2_B6_JOINT_ENSEMBLE_WHITEBOX_EVALUATION_V1"
EXPECTED_B5_STATUS = "PHASE4_M2_B5_JOINT_ENSEMBLE_GRAPH_COMPLETE_V1"
EXPECTED_FREEZE_STATUS = "PHASE4_M2_B6_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_V1"
COMPLETE_STATUS = "PHASE4_M2_B6_JOINT_ENSEMBLE_WHITEBOX_EVALUATION_COMPLETE_V1"
TOL = 1e-12


def _required_ensemble_columns() -> set[str]:
    return {
        "rho_global",
        "horizon",
        "A_G_l_max",
        "A_G_c_max",
        "A_G_q_min",
        "n_m2_members",
        "sigma_m2_mean",
        "sigma_m2_min",
        "sigma_m2_max",
        "sigma_m1_same_seed_bank",
    }


def _required_joint_columns() -> set[str]:
    return {
        "variant_id",
        "rho_global",
        "horizon",
        "sigma",
        "A_G_l_max",
        "A_G_c_max",
        "A_G_q_min",
    }


def _validate_b5_predictions(
    *,
    contract: dict[str, Any],
    b5_manifest_path: Path,
    ensemble_path: Path,
    joint_curves_path: Path,
    design_path: Path,
    i1_manifest_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest = _read_json(b5_manifest_path)
    required = dict(contract["prediction_inputs"])
    if manifest.get("status") != EXPECTED_B5_STATUS:
        raise RuntimeError("unexpected M2-B5 manifest status")
    if bool(manifest.get("smoke_mode")) != bool(required["required_smoke_mode"]):
        raise RuntimeError("M2-B6 requires the full non-smoke B5 run")
    if bool(manifest.get("graph_whitebox_read")):
        raise RuntimeError("B5 graph predictions were not white-box blind")
    if bool(manifest.get("phase1_graph_reference_read")):
        raise RuntimeError("B5 unexpectedly read the Phase-1 graph reference")
    if bool(manifest.get("graph_prediction_used_for_member_selection")):
        raise RuntimeError("B5 graph prediction was used for member selection")
    if not bool(manifest.get("candidate_set_frozen_before_graph")):
        raise RuntimeError("B5 candidate set was not frozen before graph propagation")
    if not bool(manifest.get("equal_weight_joint_ensemble")):
        raise RuntimeError("B5 was not the frozen equal-weight joint ensemble")
    if bool(manifest.get("M1_in_M2_ensemble")):
        raise RuntimeError("B5 unexpectedly included M1 inside the M2 ensemble")

    integer_checks = {
        "n_m2_joint_variants": int(required["required_n_m2_joint_variants"]),
        "n_total_simulated_variants_including_m1": int(
            required["required_n_total_variants_including_m1"]
        ),
        "n_trajectories_per_variant": int(required["required_n_trajectories_per_variant"]),
        "graph_trajectory_seed_start": int(required["required_graph_seed_start"]),
        "graph_trajectory_seed_end_inclusive": int(
            required["required_graph_seed_end_inclusive"]
        ),
    }
    for key, expected in integer_checks.items():
        if int(manifest.get(key, -1)) != expected:
            raise RuntimeError(f"B5 manifest {key} mismatch: expected {expected}")

    actual_hashes = {
        "ensemble_curve_sha256": _sha256(ensemble_path),
        "joint_graph_sigma_curves_sha256": _sha256(joint_curves_path),
        "variant_design_sha256": _sha256(design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
    }
    for key, actual in actual_hashes.items():
        if str(manifest.get(key)) != str(actual):
            raise RuntimeError(f"B5 manifest hash mismatch for {key}")

    ensemble = pd.read_csv(ensemble_path)
    missing = sorted(_required_ensemble_columns().difference(ensemble.columns))
    if missing:
        raise ValueError("B5 ensemble curve missing fields: " + ", ".join(missing))
    if ensemble.duplicated(["rho_global", "horizon"]).any():
        raise RuntimeError("B5 ensemble curve contains duplicate rho/horizon points")
    expected_members = int(required["required_n_m2_joint_variants"])
    if not (ensemble["n_m2_members"].astype(int) == expected_members).all():
        raise RuntimeError("B5 ensemble curve does not use 27 members at every point")
    mean = ensemble["sigma_m2_mean"].astype(float)
    lower = ensemble["sigma_m2_min"].astype(float)
    upper = ensemble["sigma_m2_max"].astype(float)
    if ((mean < lower - TOL) | (mean > upper + TOL)).any():
        raise RuntimeError("B5 ensemble mean falls outside its frozen min-max range")
    if ((lower < -TOL) | (upper > 1.0 + TOL)).any():
        raise RuntimeError("B5 ensemble range is outside probability support")

    joint = pd.read_csv(joint_curves_path)
    missing = sorted(_required_joint_columns().difference(joint.columns))
    if missing:
        raise ValueError("B5 joint curves missing fields: " + ", ".join(missing))
    if joint.duplicated(["variant_id", "rho_global", "horizon"]).any():
        raise RuntimeError("B5 joint curves contain duplicate variant/rho/horizon rows")
    if int(joint["variant_id"].nunique()) != int(
        required["required_n_total_variants_including_m1"]
    ):
        raise RuntimeError("B5 joint curves do not contain exactly 28 variants")
    if "BASE_M1" not in set(joint["variant_id"].astype(str)):
        raise RuntimeError("B5 joint curves lack BASE_M1")

    design = pd.read_csv(design_path)
    required_design = {"variant_id", "ensemble_member", "joint_weight"}
    missing = sorted(required_design.difference(design.columns))
    if missing:
        raise ValueError("B5 variant design missing fields: " + ", ".join(missing))
    if design["variant_id"].astype(str).duplicated().any():
        raise RuntimeError("B5 variant design contains duplicate variant IDs")
    if set(design["variant_id"].astype(str)) != set(joint["variant_id"].astype(str)):
        raise RuntimeError("B5 joint curves and variant design disagree on variant IDs")
    m2_design = design[design["ensemble_member"].astype(bool)]
    if len(m2_design) != expected_members:
        raise RuntimeError("B5 design does not contain exactly 27 M2 ensemble members")
    if not np.allclose(
        m2_design["joint_weight"].astype(float).to_numpy(),
        np.full(expected_members, 1.0 / expected_members),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("B5 design no longer has equal 1/27 weights")

    # Confirm the B5 aggregate's same-seed M1 column is exactly the frozen
    # BASE_M1 curve in the member bank.
    base = joint[joint["variant_id"].astype(str) == "BASE_M1"][
        ["rho_global", "horizon", "sigma", "A_G_l_max", "A_G_c_max", "A_G_q_min"]
    ].rename(columns={"sigma": "sigma_m1_from_joint_curves"})
    check = ensemble.merge(
        base,
        on=[
            "rho_global",
            "horizon",
            "A_G_l_max",
            "A_G_c_max",
            "A_G_q_min",
        ],
        how="inner",
        validate="one_to_one",
    )
    if len(check) != len(ensemble):
        raise RuntimeError("B5 ensemble and BASE_M1 curve supports do not align")
    if not np.allclose(
        check["sigma_m1_same_seed_bank"].astype(float).to_numpy(),
        check["sigma_m1_from_joint_curves"].astype(float).to_numpy(),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("B5 ensemble M1 reference differs from BASE_M1 curve")

    return manifest, ensemble, joint, design


def _freeze_predictions(
    *,
    contract_path: Path,
    b5_manifest_path: Path,
    ensemble_path: Path,
    joint_curves_path: Path,
    design_path: Path,
    i1_manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    contract = _read_json(contract_path)
    manifest, ensemble, joint, design = _validate_b5_predictions(
        contract=contract,
        b5_manifest_path=b5_manifest_path,
        ensemble_path=ensemble_path,
        joint_curves_path=joint_curves_path,
        design_path=design_path,
        i1_manifest_path=i1_manifest_path,
    )
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": EXPECTED_FREEZE_STATUS,
        "contract_sha256": _sha256(contract_path),
        "b5_manifest_sha256": _sha256(b5_manifest_path),
        "b5_ensemble_curve_sha256": _sha256(ensemble_path),
        "b5_joint_curves_sha256": _sha256(joint_curves_path),
        "b5_variant_design_sha256": _sha256(design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "b5_status": manifest.get("status"),
        "n_m2_members": int(
            design[design["ensemble_member"].astype(bool)]["variant_id"].nunique()
        ),
        "n_total_variants": int(joint["variant_id"].nunique()),
        "n_prediction_points": int(len(ensemble)),
        "rho_values": sorted(float(v) for v in ensemble["rho_global"].unique()),
        "horizons": sorted(float(v) for v in ensemble["horizon"].unique()),
        "graph_whitebox_read": False,
        "graph_simulation": False,
        "provider_search": False,
        "candidate_set_changed": False,
        "ensemble_weights_changed": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    path = output / "m2_b6_prediction_freeze_manifest_v1.json"
    _write_json(path, payload)
    return payload


def _assert_freeze_matches(
    *,
    freeze_path: Path,
    contract_path: Path,
    b5_manifest_path: Path,
    ensemble_path: Path,
    joint_curves_path: Path,
    design_path: Path,
    i1_manifest_path: Path,
) -> dict[str, Any]:
    if not freeze_path.exists():
        raise RuntimeError(
            "M2-B6 prediction freeze is absent. Run --prepare-only before "
            "opening graph white-box evidence."
        )
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise RuntimeError("unexpected M2-B6 prediction-freeze status")
    expected = {
        "contract_sha256": _sha256(contract_path),
        "b5_manifest_sha256": _sha256(b5_manifest_path),
        "b5_ensemble_curve_sha256": _sha256(ensemble_path),
        "b5_joint_curves_sha256": _sha256(joint_curves_path),
        "b5_variant_design_sha256": _sha256(design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
    }
    mismatches = [
        key for key, value in expected.items() if str(freeze.get(key)) != str(value)
    ]
    if mismatches:
        raise RuntimeError(
            "Frozen B6 prediction inputs changed after prepare-only: "
            + ", ".join(mismatches)
        )
    if bool(freeze.get("graph_whitebox_read")):
        raise RuntimeError("B6 prediction-freeze manifest unexpectedly reports WB access")
    return freeze


def _metrics(prediction: pd.Series, truth: pd.Series) -> dict[str, float]:
    error = prediction.astype(float).to_numpy() - truth.astype(float).to_numpy()
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def _build_whitebox_curves(
    *,
    ensemble: pd.DataFrame,
    whitebox: pd.DataFrame,
    horizons: list[float],
    rho_support: list[float],
    stop_time: float,
    accounting_origin: float,
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
            raise RuntimeError(f"rho={rho}: B5 ensemble does not expose one frozen A_G")
        rec = triples.iloc[0]
        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = build_empirical_graph_sigma_curve(
            whitebox,
            boundary=boundary,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(stop_time),
            accounting_origin=float(accounting_origin),
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


def _build_m0_curves(
    *,
    provider_surfaces: dict[str, pd.DataFrame],
    rho_support: list[float],
    horizons: list[float],
) -> pd.DataFrame:
    rows = [
        build_same_rho_conditioned_m0_curve(
            provider_surfaces,
            rho=float(rho),
            horizons=horizons,
        )
        for rho in rho_support
    ]
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)


def _point_summaries(comparison: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    methods = {
        "m0": "sigma_m0",
        "m1": "sigma_m1",
        "m2": "sigma_m2_mean",
    }

    overall: dict[str, Any] = {"n_points": int(len(comparison))}
    overall_metrics: dict[str, dict[str, float]] = {}
    for name, column in methods.items():
        met = _metrics(comparison[column], comparison["sigma_whitebox"])
        overall_metrics[name] = met
        for key, value in met.items():
            overall[f"{name}_{key}"] = value
    overall["m0_mae_minus_m1_mae"] = (
        overall_metrics["m0"]["mae"] - overall_metrics["m1"]["mae"]
    )
    overall["m0_mae_minus_m2_mae"] = (
        overall_metrics["m0"]["mae"] - overall_metrics["m2"]["mae"]
    )
    overall["m1_mae_minus_m2_mae"] = (
        overall_metrics["m1"]["mae"] - overall_metrics["m2"]["mae"]
    )

    per_rho_rows: list[dict[str, Any]] = []
    for rho, group in comparison.groupby("rho_global"):
        row: dict[str, Any] = {
            "rho_global": float(rho),
            "n_points": int(len(group)),
        }
        metrics_by_method: dict[str, dict[str, float]] = {}
        for name, column in methods.items():
            met = _metrics(group[column], group["sigma_whitebox"])
            metrics_by_method[name] = met
            for key, value in met.items():
                row[f"{name}_{key}"] = value
        row["m0_mae_minus_m1_mae"] = (
            metrics_by_method["m0"]["mae"] - metrics_by_method["m1"]["mae"]
        )
        row["m0_mae_minus_m2_mae"] = (
            metrics_by_method["m0"]["mae"] - metrics_by_method["m2"]["mae"]
        )
        row["m1_mae_minus_m2_mae"] = (
            metrics_by_method["m1"]["mae"] - metrics_by_method["m2"]["mae"]
        )
        per_rho_rows.append(row)

    return pd.DataFrame([overall]), pd.DataFrame(per_rho_rows).sort_values(
        "rho_global"
    ).reset_index(drop=True)


def _ambiguity_table(comparison: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pointwise = comparison[
        [
            "rho_global",
            "horizon",
            "sigma_whitebox",
            "sigma_m2_min",
            "sigma_m2_max",
        ]
    ].copy()
    pointwise["range_width"] = (
        pointwise["sigma_m2_max"].astype(float)
        - pointwise["sigma_m2_min"].astype(float)
    )
    wb = pointwise["sigma_whitebox"].astype(float)
    lo = pointwise["sigma_m2_min"].astype(float)
    hi = pointwise["sigma_m2_max"].astype(float)
    pointwise["whitebox_inside_range"] = (wb >= lo - TOL) & (wb <= hi + TOL)
    pointwise["whitebox_below_range"] = wb < lo - TOL
    pointwise["whitebox_above_range"] = wb > hi + TOL
    pointwise["distance_outside_range"] = np.maximum(
        np.maximum(lo.to_numpy() - wb.to_numpy(), wb.to_numpy() - hi.to_numpy()),
        0.0,
    )

    def summarize(group: pd.DataFrame, rho: float | None) -> dict[str, Any]:
        return {
            "rho_global": np.nan if rho is None else float(rho),
            "n_points": int(len(group)),
            "whitebox_coverage_fraction": float(
                group["whitebox_inside_range"].astype(bool).mean()
            ),
            "mean_range_width": float(group["range_width"].astype(float).mean()),
            "max_range_width": float(group["range_width"].astype(float).max()),
            "mean_distance_outside_range": float(
                group["distance_outside_range"].astype(float).mean()
            ),
            "max_distance_outside_range": float(
                group["distance_outside_range"].astype(float).max()
            ),
            "fraction_whitebox_below_range": float(
                group["whitebox_below_range"].astype(bool).mean()
            ),
            "fraction_whitebox_above_range": float(
                group["whitebox_above_range"].astype(bool).mean()
            ),
        }

    rows = [summarize(pointwise, None)]
    rows.extend(
        summarize(group, float(rho))
        for rho, group in pointwise.groupby("rho_global")
    )
    summary = pd.DataFrame(rows).sort_values(
        "rho_global", na_position="first"
    ).reset_index(drop=True)
    return pointwise, summary


def _plot_four_way(comparison: pd.DataFrame, output_path: Path) -> None:
    rho_values = sorted(float(v) for v in comparison["rho_global"].unique())
    figure, axes = plt.subplots(2, 3, figsize=(13.4, 7.6), sharex=True, sharey=True)
    flat = list(axes.flat)
    for axis, rho in zip(flat, rho_values):
        group = comparison[
            np.isclose(
                comparison["rho_global"].astype(float),
                rho,
                atol=TOL,
                rtol=0.0,
            )
        ].sort_values("horizon")
        x = group["horizon"].astype(float).to_numpy()
        axis.fill_between(
            x,
            group["sigma_m2_min"].astype(float).to_numpy(),
            group["sigma_m2_max"].astype(float).to_numpy(),
            alpha=0.15,
            label="M2 ambiguity range",
        )
        axis.plot(x, group["sigma_whitebox"], linewidth=2.4, label="White-box")
        axis.plot(x, group["sigma_m0"], linestyle="--", linewidth=1.6, label="M0")
        axis.plot(x, group["sigma_m1"], linestyle=":", linewidth=1.8, label="M1")
        axis.plot(x, group["sigma_m2_mean"], linewidth=2.0, label="M2 mean")
        axis.set_title(f"rho={rho:g}")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.2)
    for axis in flat[len(rho_values):]:
        axis.axis("off")
    flat[0].legend(frameon=False, fontsize=8)
    figure.suptitle("Same-region graph prediction: WB vs M0, M1 and frozen M2")
    figure.supxlabel("Horizon H (s)")
    figure.supylabel("Admissibility probability")
    figure.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    b5_manifest_path = args.b5_manifest.resolve()
    ensemble_path = args.b5_ensemble_curve.resolve()
    joint_curves_path = args.b5_joint_curves.resolve()
    design_path = args.b5_variant_design.resolve()
    i1_manifest_path = args.i1_manifest.resolve()

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-B6 contract status")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    freeze_path = output / "m2_b6_prediction_freeze_manifest_v1.json"

    if args.prepare_only:
        payload = _freeze_predictions(
            contract_path=contract_path,
            b5_manifest_path=b5_manifest_path,
            ensemble_path=ensemble_path,
            joint_curves_path=joint_curves_path,
            design_path=design_path,
            i1_manifest_path=i1_manifest_path,
            output=output,
        )
        print("M2_B6_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_PASS")
        print(
            f"n_m2_members={payload['n_m2_members']} "
            f"n_points={payload['n_prediction_points']}"
        )
        print(f"freeze_manifest={freeze_path}")
        return

    _assert_freeze_matches(
        freeze_path=freeze_path,
        contract_path=contract_path,
        b5_manifest_path=b5_manifest_path,
        ensemble_path=ensemble_path,
        joint_curves_path=joint_curves_path,
        design_path=design_path,
        i1_manifest_path=i1_manifest_path,
    )
    b5_manifest, ensemble, _, _ = _validate_b5_predictions(
        contract=contract,
        b5_manifest_path=b5_manifest_path,
        ensemble_path=ensemble_path,
        joint_curves_path=joint_curves_path,
        design_path=design_path,
        i1_manifest_path=i1_manifest_path,
    )

    # Public I1 is loaded before WB because it is also the source of the frozen M0
    # prediction and public horizon/rho/workload support.
    metadata, provider_surfaces, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), i1_manifest_path
    )
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    if sorted(rho_support) != sorted(float(v) for v in ensemble["rho_global"].unique()):
        raise RuntimeError("B5 rho support differs from frozen public I1")
    if sorted(horizons) != sorted(float(v) for v in ensemble["horizon"].unique()):
        raise RuntimeError("B5 horizon support differs from frozen public I1")

    m0 = _build_m0_curves(
        provider_surfaces=provider_surfaces,
        rho_support=rho_support,
        horizons=horizons,
    )

    # External white-box evaluation begins only here, after the B6 freeze has
    # been verified and all prediction-side inputs have been revalidated.
    whitebox_path = args.whitebox_ledgers.resolve()
    if not whitebox_path.exists():
        raise FileNotFoundError(f"white-box ledger not found: {whitebox_path}")
    whitebox = pd.read_csv(whitebox_path)
    expected_wb = int(contract["whitebox_input"]["expected_trajectories"])
    if int(whitebox["trajectory"].nunique()) != expected_wb:
        raise RuntimeError(
            f"B6 expected {expected_wb} WB trajectories, "
            f"found {whitebox['trajectory'].nunique()}"
        )

    wb = _build_whitebox_curves(
        ensemble=ensemble,
        whitebox=whitebox,
        horizons=horizons,
        rho_support=rho_support,
        stop_time=float(workload["horizon_max"]),
        accounting_origin=float(workload["accounting_origin"]),
    )

    comparison = ensemble.merge(
        m0[["rho_global", "horizon", "sigma_i1_m0"]],
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    ).merge(
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
        on=[
            "rho_global",
            "horizon",
            "A_G_l_max",
            "A_G_c_max",
            "A_G_q_min",
        ],
        how="inner",
        validate="one_to_one",
    )
    if len(comparison) != len(ensemble):
        raise RuntimeError("B6 comparison did not cover every frozen B5 point")
    comparison = comparison.rename(
        columns={
            "sigma_i1_m0": "sigma_m0",
            "sigma_m1_same_seed_bank": "sigma_m1",
        }
    )
    comparison["error_m0_minus_whitebox"] = (
        comparison["sigma_m0"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
    )
    comparison["error_m1_minus_whitebox"] = (
        comparison["sigma_m1"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
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

    comparison_path = output / "m2_b6_pointwise_comparison.csv"
    overall_path = output / "m2_b6_overall_point_summary.csv"
    per_rho_path = output / "m2_b6_per_rho_point_summary.csv"
    ambiguity_path = output / "m2_b6_ambiguity_summary.csv"
    wb_path = output / "m2_b6_whitebox_curve.csv"
    plot_path = output / "m2_b6_m0_m1_m2_whitebox.png"

    comparison.to_csv(comparison_path, index=False)
    overall.to_csv(overall_path, index=False)
    per_rho.to_csv(per_rho_path, index=False)
    ambiguity_summary.to_csv(ambiguity_path, index=False)
    wb.to_csv(wb_path, index=False)
    _plot_four_way(comparison, plot_path)

    evaluation_manifest = {
        "status": COMPLETE_STATUS,
        "evidence_status": contract["evidence_status"]["G0"],
        "prediction_freeze_sha256": _sha256(freeze_path),
        "b5_manifest_sha256": _sha256(b5_manifest_path),
        "b5_ensemble_curve_sha256": _sha256(ensemble_path),
        "b5_joint_curves_sha256": _sha256(joint_curves_path),
        "b5_variant_design_sha256": _sha256(design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "whitebox_ledger_sha256": _sha256(whitebox_path),
        "whitebox_used_only_after_prediction_freeze": True,
        "whitebox_used_for_candidate_selection": False,
        "whitebox_used_for_weight_selection": False,
        "graph_simulation": False,
        "provider_search": False,
        "candidate_set_changed": False,
        "ensemble_weights_changed": False,
        "same_global_regions": True,
        "same_rho_diagonal": True,
        "Jaccard_D_A": "N/A",
        "primary_surface_includes_H0": bool(
            contract["evaluation_semantics"]["primary_surface_includes_H0"]
        ),
        "n_prediction_points": int(len(comparison)),
        "n_whitebox_trajectories": int(expected_wb),
        "b5_graph_seed_start": int(b5_manifest["graph_trajectory_seed_start"]),
        "b5_graph_seed_end_inclusive": int(
            b5_manifest["graph_trajectory_seed_end_inclusive"]
        ),
        "portfolio_range_is_confidence_interval": False,
        "python_wall_seconds": float(time.perf_counter() - started),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "pointwise_comparison": comparison_path.name,
            "overall_point_summary": overall_path.name,
            "per_rho_point_summary": per_rho_path.name,
            "ambiguity_summary": ambiguity_path.name,
            "whitebox_curve": wb_path.name,
            "plot": plot_path.name,
        },
        "next_gate": contract["next_gate"],
    }
    manifest_path = output / "m2_b6_evaluation_manifest_v1.json"
    _write_json(manifest_path, evaluation_manifest)

    print("M2_B6_EXTERNAL_WHITEBOX_EVALUATION_COMPLETE")
    print("\nOVERALL_POINT_PREDICTION")
    print(overall.to_string(index=False))
    print("\nPER_RHO_POINT_PREDICTION")
    print(per_rho.to_string(index=False))
    print("\nM2_AMBIGUITY_RANGE")
    print(ambiguity_summary.to_string(index=False))
    print(f"\nplot={plot_path}")
    print(f"output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze then externally evaluate the frozen M2-B5 ensemble"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_b6_joint_ensemble_whitebox_v1.json",
    )
    parser.add_argument(
        "--b5-manifest",
        type=Path,
        default=HERE / "results" / "m2_b5_joint_ensemble_graph_v1" / "m2_b5_manifest_v1.json",
    )
    parser.add_argument(
        "--b5-ensemble-curve",
        type=Path,
        default=HERE / "results" / "m2_b5_joint_ensemble_graph_v1" / "m2_b5_ensemble_curve.csv",
    )
    parser.add_argument(
        "--b5-joint-curves",
        type=Path,
        default=HERE / "results" / "m2_b5_joint_ensemble_graph_v1" / "m2_b5_joint_graph_sigma_curves.csv",
    )
    parser.add_argument(
        "--b5-variant-design",
        type=Path,
        default=HERE / "results" / "m2_b5_joint_ensemble_graph_v1" / "m2_b5_joint_variant_design.csv",
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
        "--whitebox-ledgers",
        type=Path,
        default=PHASE1
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_b6_joint_ensemble_whitebox_v1",
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
