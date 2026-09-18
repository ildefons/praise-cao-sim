"""M2-B4: evaluate frozen M2-B3 graph predictions against Phase-1 white-box evidence.

Scientific ordering is enforced in two invocations:

1. --prepare-only fingerprints the already-materialized M2-B3 predictions without
   reading the graph white-box ledger.
2. The evaluation invocation refuses to proceed unless those fingerprints still
   match, then and only then opens the frozen Phase-1 graph ledger.

No graph simulation, provider search, candidate replacement, or parameter
retuning occurs in this stage.
"""
from __future__ import annotations

import argparse
import json
import math
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
for directory in (PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
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

EXPECTED_CONTRACT_STATUS = "PHASE4_M2_B4_FROZEN_PREDICTION_WHITEBOX_EVALUATION_V1"
EXPECTED_B3_STATUS = "PHASE4_M2_B3_A4_PORTFOLIO_GRAPH_PROPAGATION_COMPLETE_V1"
EXPECTED_FREEZE_STATUS = "PHASE4_M2_B4_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_V1"
TOL = 1e-12


def _required_prediction_columns() -> set[str]:
    return {
        "variant_id",
        "rho_global",
        "horizon",
        "sigma",
        "A_G_l_max",
        "A_G_c_max",
        "A_G_q_min",
    }


def _validate_b3_predictions(
    *,
    b3_manifest_path: Path,
    b3_curves_path: Path,
    b3_design_path: Path,
    i1_manifest_path: Path,
    expected_n_variants: int,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    manifest = _read_json(b3_manifest_path)
    if manifest.get("status") != EXPECTED_B3_STATUS:
        raise RuntimeError("unexpected M2-B3 manifest status")
    if bool(manifest.get("smoke_mode")):
        raise RuntimeError("M2-B4 cannot evaluate a smoke M2-B3 run")
    if bool(manifest.get("graph_whitebox_read")):
        raise RuntimeError("M2-B3 predictions were not white-box blind")
    if bool(manifest.get("graph_prediction_used_for_candidate_selection")):
        raise RuntimeError("M2-B3 graph predictions were used for candidate selection")
    if not bool(manifest.get("candidate_set_frozen_before_graph")):
        raise RuntimeError("M2-B3 candidate set was not frozen before graph simulation")
    if int(manifest.get("n_variants", -1)) != int(expected_n_variants):
        raise RuntimeError("unexpected M2-B3 variant count")
    if int(manifest.get("n_trajectories_per_variant", -1)) != 100:
        raise RuntimeError("M2-B4 requires the full N=100 M2-B3 run")
    if not bool(manifest.get("common_random_numbers_across_variants")):
        raise RuntimeError("M2-B3 did not use common random numbers")

    if str(manifest.get("public_i1_manifest_sha256")) != _sha256(i1_manifest_path):
        raise RuntimeError("public I1 manifest differs from the one used by M2-B3")

    curves = pd.read_csv(b3_curves_path)
    missing = sorted(_required_prediction_columns().difference(curves.columns))
    if missing:
        raise ValueError("M2-B3 curves missing fields: " + ", ".join(missing))
    if curves.duplicated(["variant_id", "rho_global", "horizon"]).any():
        raise RuntimeError("M2-B3 curves contain duplicate variant/rho/horizon rows")

    design = pd.read_csv(b3_design_path)
    if "variant_id" not in design.columns or design["variant_id"].astype(str).duplicated().any():
        raise RuntimeError("M2-B3 variant design must contain unique variant_id rows")

    manifest_ids = [str(v) for v in manifest.get("variant_ids", [])]
    curve_ids = sorted(curves["variant_id"].astype(str).unique().tolist())
    design_ids = sorted(design["variant_id"].astype(str).unique().tolist())
    if len(manifest_ids) != expected_n_variants:
        raise RuntimeError("M2-B3 manifest does not list the expected number of variants")
    if sorted(manifest_ids) != curve_ids or curve_ids != design_ids:
        raise RuntimeError("M2-B3 manifest, curves, and variant design disagree on variants")
    if "BASE_M1" not in curve_ids:
        raise RuntimeError("M2-B3 curves lack BASE_M1")

    # Every variant must expose exactly the same rho/horizon grid.
    grid = curves[["rho_global", "horizon"]].drop_duplicates().sort_values(
        ["rho_global", "horizon"]
    )
    expected_grid = len(grid)
    counts = curves.groupby("variant_id").size()
    if not (counts.astype(int) == expected_grid).all():
        raise RuntimeError("M2-B3 variants do not share one complete rho/horizon grid")

    reference = curves[curves["variant_id"].astype(str) == "BASE_M1"][
        ["rho_global", "horizon"]
    ].sort_values(["rho_global", "horizon"]).reset_index(drop=True)
    for variant_id, group in curves.groupby("variant_id"):
        candidate = group[["rho_global", "horizon"]].sort_values(
            ["rho_global", "horizon"]
        ).reset_index(drop=True)
        if not candidate.equals(reference):
            raise RuntimeError(f"{variant_id}: rho/horizon support differs from BASE_M1")

    # The induced A_G must be identical across variants at each rho.
    for rho, group in curves.groupby("rho_global"):
        triples = group[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"rho={rho}: A_G differs across M2-B3 variants")

    return manifest, curves, design


def _freeze_predictions(
    *,
    contract_path: Path,
    b3_manifest_path: Path,
    b3_curves_path: Path,
    b3_design_path: Path,
    i1_manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    contract = _read_json(contract_path)
    expected_n = int(contract["prediction_inputs"]["required_n_variants"])
    b3_manifest, curves, design = _validate_b3_predictions(
        b3_manifest_path=b3_manifest_path,
        b3_curves_path=b3_curves_path,
        b3_design_path=b3_design_path,
        i1_manifest_path=i1_manifest_path,
        expected_n_variants=expected_n,
    )
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": EXPECTED_FREEZE_STATUS,
        "contract_sha256": _sha256(contract_path),
        "b3_manifest_sha256": _sha256(b3_manifest_path),
        "b3_curves_sha256": _sha256(b3_curves_path),
        "b3_variant_design_sha256": _sha256(b3_design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "b3_status": b3_manifest.get("status"),
        "n_variants": int(curves["variant_id"].nunique()),
        "n_prediction_rows": int(len(curves)),
        "variant_ids": sorted(curves["variant_id"].astype(str).unique().tolist()),
        "rho_values": sorted(float(v) for v in curves["rho_global"].unique()),
        "horizons": sorted(float(v) for v in curves["horizon"].unique()),
        "graph_whitebox_read": False,
        "graph_simulation": False,
        "provider_search": False,
        "candidate_set_changed": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    path = output / "m2_b4_prediction_freeze_manifest_v1.json"
    _write_json(path, payload)
    return payload


def _assert_prediction_freeze_matches(
    *,
    freeze_path: Path,
    contract_path: Path,
    b3_manifest_path: Path,
    b3_curves_path: Path,
    b3_design_path: Path,
    i1_manifest_path: Path,
) -> dict[str, Any]:
    if not freeze_path.exists():
        raise RuntimeError(
            "M2-B4 prediction freeze manifest is absent. Run this script with "
            "--prepare-only before any white-box evaluation."
        )
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise RuntimeError("unexpected M2-B4 prediction-freeze status")
    expected_hashes = {
        "contract_sha256": _sha256(contract_path),
        "b3_manifest_sha256": _sha256(b3_manifest_path),
        "b3_curves_sha256": _sha256(b3_curves_path),
        "b3_variant_design_sha256": _sha256(b3_design_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
    }
    mismatches = [
        key for key, value in expected_hashes.items() if str(freeze.get(key)) != str(value)
    ]
    if mismatches:
        raise RuntimeError(
            "Frozen M2-B4 prediction inputs changed after prepare-only: "
            + ", ".join(mismatches)
        )
    if bool(freeze.get("graph_whitebox_read")):
        raise RuntimeError("prediction freeze manifest unexpectedly reports white-box access")
    return freeze


def _metrics(prediction: pd.Series, truth: pd.Series) -> dict[str, float]:
    error = prediction.to_numpy(float) - truth.to_numpy(float)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def _build_whitebox_curves(
    *,
    curves: pd.DataFrame,
    whitebox: pd.DataFrame,
    horizons: list[float],
    rho_support: list[float],
    stop_time: float,
    accounting_origin: float,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rho in rho_support:
        selected = curves[np.isclose(curves["rho_global"].astype(float), float(rho), atol=TOL, rtol=0.0)]
        triples = selected[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"rho={rho}: expected exactly one frozen M2-B3 A_G")
        rec = triples.iloc[0]
        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        wb_curve = build_empirical_graph_sigma_curve(
            whitebox,
            boundary=boundary,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(stop_time),
            accounting_origin=float(accounting_origin),
            output_column="sigma_whitebox",
        )
        wb_curve.insert(0, "rho_global", float(rho))
        wb_curve["A_G_l_max"] = float(boundary.l_max)
        wb_curve["A_G_c_max"] = float(boundary.c_max)
        wb_curve["A_G_q_min"] = float(boundary.q_min)
        rows.append(wb_curve)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)


def _variant_accuracy(
    curves: pd.DataFrame,
    wb_curves: pd.DataFrame,
    design: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comparison = curves.merge(
        wb_curves[
            [
                "rho_global", "horizon", "sigma_whitebox",
                "A_G_l_max", "A_G_c_max", "A_G_q_min",
            ]
        ],
        on=["rho_global", "horizon", "A_G_l_max", "A_G_c_max", "A_G_q_min"],
        how="inner",
        validate="many_to_one",
    )
    if len(comparison) != len(curves):
        raise RuntimeError("white-box comparison did not cover every frozen prediction row")
    comparison = comparison.rename(columns={"sigma": "sigma_prediction"})
    comparison["error_prediction_minus_whitebox"] = (
        comparison["sigma_prediction"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
    )

    overall_rows: list[dict[str, Any]] = []
    rho_rows: list[dict[str, Any]] = []
    for variant_id, group in comparison.groupby("variant_id"):
        m = _metrics(group["sigma_prediction"], group["sigma_whitebox"])
        overall_rows.append({"variant_id": str(variant_id), **m})
        for rho, rg in group.groupby("rho_global"):
            mr = _metrics(rg["sigma_prediction"], rg["sigma_whitebox"])
            rho_rows.append({"variant_id": str(variant_id), "rho_global": float(rho), **mr})

    overall = pd.DataFrame(overall_rows).merge(
        design, on="variant_id", how="left", validate="one_to_one"
    )
    baseline_mae = float(
        overall.loc[overall["variant_id"].astype(str) == "BASE_M1", "mae"].iloc[0]
    )
    overall["mae_improvement_vs_BASE_M1"] = baseline_mae - overall["mae"].astype(float)
    overall["accuracy_rank_by_mae"] = overall["mae"].rank(
        method="min", ascending=True
    ).astype(int)
    overall = overall.sort_values(["mae", "variant_id"], kind="mergesort").reset_index(drop=True)

    per_rho = pd.DataFrame(rho_rows).merge(
        design, on="variant_id", how="left", validate="many_to_one"
    ).sort_values(["rho_global", "mae", "variant_id"], kind="mergesort").reset_index(drop=True)
    return comparison, overall, per_rho


def _envelope_rows(
    comparison: pd.DataFrame,
    *,
    scope: str,
    variant_ids: set[str],
) -> pd.DataFrame:
    selected = comparison[comparison["variant_id"].astype(str).isin(variant_ids)].copy()
    if selected.empty:
        raise RuntimeError(f"{scope}: no variants selected for envelope")
    grouped = selected.groupby(["rho_global", "horizon"], as_index=False).agg(
        prediction_min=("sigma_prediction", "min"),
        prediction_max=("sigma_prediction", "max"),
        sigma_whitebox=("sigma_whitebox", "first"),
        n_predictions=("variant_id", "nunique"),
    )
    grouped["envelope_scope"] = scope
    grouped["envelope_width"] = (
        grouped["prediction_max"].astype(float) - grouped["prediction_min"].astype(float)
    )
    wb = grouped["sigma_whitebox"].astype(float)
    lo = grouped["prediction_min"].astype(float)
    hi = grouped["prediction_max"].astype(float)
    grouped["whitebox_inside_envelope"] = (wb >= lo - TOL) & (wb <= hi + TOL)
    grouped["whitebox_below_envelope"] = wb < lo - TOL
    grouped["whitebox_above_envelope"] = wb > hi + TOL
    grouped["distance_outside_envelope"] = np.maximum(
        np.maximum(lo.to_numpy() - wb.to_numpy(), wb.to_numpy() - hi.to_numpy()),
        0.0,
    )
    return grouped


def _aggregate_envelope(envelope: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, sg in envelope.groupby("envelope_scope"):
        groups: list[tuple[float | None, pd.DataFrame]] = [(None, sg)]
        groups.extend((float(rho), rg) for rho, rg in sg.groupby("rho_global"))
        for rho, group in groups:
            rows.append({
                "envelope_scope": str(scope),
                "rho_global": np.nan if rho is None else rho,
                "n_points": int(len(group)),
                "coverage_fraction_of_whitebox_points": float(
                    group["whitebox_inside_envelope"].astype(bool).mean()
                ),
                "mean_envelope_width": float(group["envelope_width"].astype(float).mean()),
                "max_envelope_width": float(group["envelope_width"].astype(float).max()),
                "mean_distance_outside_envelope": float(
                    group["distance_outside_envelope"].astype(float).mean()
                ),
                "max_distance_outside_envelope": float(
                    group["distance_outside_envelope"].astype(float).max()
                ),
                "fraction_whitebox_below_envelope": float(
                    group["whitebox_below_envelope"].astype(bool).mean()
                ),
                "fraction_whitebox_above_envelope": float(
                    group["whitebox_above_envelope"].astype(bool).mean()
                ),
            })
    return pd.DataFrame(rows).sort_values(
        ["envelope_scope", "rho_global"], na_position="first"
    ).reset_index(drop=True)


def _plot_c_variants(
    comparison: pd.DataFrame,
    design: pd.DataFrame,
    output_path: Path,
) -> None:
    c_ids = set(
        design[design.get("changed_provider", pd.Series(dtype=str)).astype(str) == "ProviderC"][
            "variant_id"
        ].astype(str)
    )
    ids = {"BASE_M1", *c_ids}
    selected = comparison[comparison["variant_id"].astype(str).isin(ids)]
    rho_values = sorted(float(v) for v in selected["rho_global"].unique())
    fig, axes = plt.subplots(2, 3, figsize=(13.0, 7.4), sharex=True, sharey=True)
    axes_flat = list(axes.flat)
    for axis, rho in zip(axes_flat, rho_values):
        rg = selected[np.isclose(selected["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)]
        wb = rg[["horizon", "sigma_whitebox"]].drop_duplicates().sort_values("horizon")
        axis.plot(wb["horizon"], wb["sigma_whitebox"], linewidth=2.4, label="White-box")
        for variant_id, vg in rg.groupby("variant_id"):
            axis.plot(
                vg.sort_values("horizon")["horizon"],
                vg.sort_values("horizon")["sigma_prediction"],
                linewidth=1.6,
                label=str(variant_id),
            )
        axis.set_title(f"rho={rho:g}")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.2)
    for axis in axes_flat[len(rho_values):]:
        axis.axis("off")
    axes_flat[0].legend(frameon=False, fontsize=7)
    fig.suptitle("M2-B4: frozen Provider-C counterfactuals vs graph white-box")
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("sigma_G")
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _plot_envelope(
    envelope: pd.DataFrame,
    output_path: Path,
    scope: str,
) -> None:
    selected = envelope[envelope["envelope_scope"].astype(str) == scope]
    rho_values = sorted(float(v) for v in selected["rho_global"].unique())
    fig, axes = plt.subplots(2, 3, figsize=(13.0, 7.4), sharex=True, sharey=True)
    axes_flat = list(axes.flat)
    for axis, rho in zip(axes_flat, rho_values):
        rg = selected[np.isclose(selected["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)].sort_values("horizon")
        x = rg["horizon"].to_numpy(float)
        lo = rg["prediction_min"].to_numpy(float)
        hi = rg["prediction_max"].to_numpy(float)
        wb = rg["sigma_whitebox"].to_numpy(float)
        axis.fill_between(x, lo, hi, alpha=0.25, label="Frozen prediction envelope")
        axis.plot(x, wb, linewidth=2.2, label="White-box")
        axis.set_title(f"rho={rho:g}")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.2)
    for axis in axes_flat[len(rho_values):]:
        axis.axis("off")
    axes_flat[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"M2-B4 white-box coverage: {scope}")
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("sigma_G")
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-B4 contract status")

    b3_manifest_path = args.b3_manifest.resolve()
    b3_curves_path = args.b3_curves.resolve()
    b3_design_path = args.b3_variant_design.resolve()
    i1_manifest_path = args.i1_manifest.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    freeze_path = output / "m2_b4_prediction_freeze_manifest_v1.json"

    if args.prepare_only:
        freeze = _freeze_predictions(
            contract_path=contract_path,
            b3_manifest_path=b3_manifest_path,
            b3_curves_path=b3_curves_path,
            b3_design_path=b3_design_path,
            i1_manifest_path=i1_manifest_path,
            output=output,
        )
        print("M2_B4_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_PASS")
        print(f"variants={freeze['n_variants']} prediction_rows={freeze['n_prediction_rows']}")
        print(f"b3_curves_sha256={freeze['b3_curves_sha256']}")
        print("M2_B4_PREPARE_ONLY_COMPLETE")
        print(f"output={output}")
        return

    freeze = _assert_prediction_freeze_matches(
        freeze_path=freeze_path,
        contract_path=contract_path,
        b3_manifest_path=b3_manifest_path,
        b3_curves_path=b3_curves_path,
        b3_design_path=b3_design_path,
        i1_manifest_path=i1_manifest_path,
    )

    expected_n = int(contract["prediction_inputs"]["required_n_variants"])
    b3_manifest, curves, design = _validate_b3_predictions(
        b3_manifest_path=b3_manifest_path,
        b3_curves_path=b3_curves_path,
        b3_design_path=b3_design_path,
        i1_manifest_path=i1_manifest_path,
        expected_n_variants=expected_n,
    )

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), i1_manifest_path
    )
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    curve_rhos = sorted(float(v) for v in curves["rho_global"].unique())
    curve_horizons = sorted(float(v) for v in curves["horizon"].unique())
    if curve_rhos != sorted(rho_support) or curve_horizons != sorted(horizons):
        raise RuntimeError("M2-B3 prediction support differs from frozen public I1 support")

    # White-box access begins only here, after prediction fingerprints were checked.
    wb_path = args.whitebox_ledgers.resolve()
    if not wb_path.exists():
        raise FileNotFoundError(f"graph white-box ledger not found: {wb_path}")
    whitebox = pd.read_csv(wb_path)
    if "trajectory" not in whitebox.columns:
        raise ValueError("graph white-box ledger lacks trajectory")
    expected_wb_n = int(contract["whitebox_input"]["expected_trajectories"])
    if int(whitebox["trajectory"].nunique()) != expected_wb_n:
        raise RuntimeError(
            f"expected {expected_wb_n} graph white-box trajectories, found "
            f"{whitebox['trajectory'].nunique()}"
        )

    wb_curves = _build_whitebox_curves(
        curves=curves,
        whitebox=whitebox,
        horizons=horizons,
        rho_support=rho_support,
        stop_time=float(workload["horizon_max"]),
        accounting_origin=float(workload["accounting_origin"]),
    )
    wb_curves.to_csv(output / "m2_b4_whitebox_same_region_curves.csv", index=False)

    comparison, overall, per_rho = _variant_accuracy(curves, wb_curves, design)
    comparison.to_csv(output / "m2_b4_prediction_whitebox_comparison.csv", index=False)
    overall.to_csv(output / "m2_b4_variant_accuracy_summary.csv", index=False)
    per_rho.to_csv(output / "m2_b4_per_rho_accuracy_summary.csv", index=False)

    all_ids = set(comparison["variant_id"].astype(str).unique())
    a4_ids = all_ids - {"BASE_M1"}
    envelope_all = _envelope_rows(
        comparison,
        scope="ALL_10_FROZEN_ONE_AT_A_TIME_PREDICTIONS",
        variant_ids=all_ids,
    )
    envelope_a4 = _envelope_rows(
        comparison,
        scope="NINE_A4_SUBSTITUTION_PREDICTIONS_WITHOUT_BASE_M1",
        variant_ids=a4_ids,
    )
    envelope = pd.concat([envelope_all, envelope_a4], ignore_index=True)
    envelope.to_csv(output / "m2_b4_prediction_envelopes.csv", index=False)
    envelope_metrics = _aggregate_envelope(envelope)
    envelope_metrics.to_csv(output / "m2_b4_envelope_metrics.csv", index=False)

    _plot_c_variants(
        comparison, design, output / "m2_b4_providerC_vs_whitebox.png"
    )
    _plot_envelope(
        envelope,
        output / "m2_b4_all10_envelope_vs_whitebox.png",
        "ALL_10_FROZEN_ONE_AT_A_TIME_PREDICTIONS",
    )

    manifest = {
        "status": "PHASE4_M2_B4_FROZEN_PREDICTION_WHITEBOX_EVALUATION_COMPLETE_V1",
        "prediction_freeze_manifest_sha256": _sha256(freeze_path),
        "contract_sha256": _sha256(contract_path),
        "b3_manifest_sha256": _sha256(b3_manifest_path),
        "b3_curves_sha256": _sha256(b3_curves_path),
        "b3_variant_design_sha256": _sha256(b3_design_path),
        "whitebox_ledger_sha256": _sha256(wb_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "predictions_frozen_before_whitebox": True,
        "freeze_manifest_graph_whitebox_read": bool(freeze.get("graph_whitebox_read")),
        "graph_whitebox_read": True,
        "graph_simulation": False,
        "provider_search": False,
        "candidate_set_changed": False,
        "provider_parameters_changed": False,
        "whitebox_used_for_candidate_selection": False,
        "same_global_regions_as_b3": True,
        "same_rho_diagonal": True,
        "n_variants": int(curves["variant_id"].nunique()),
        "n_whitebox_trajectories": int(whitebox["trajectory"].nunique()),
        "n_comparison_rows": int(len(comparison)),
        "python_wall_seconds": float(time.perf_counter() - started),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "whitebox_same_region_curves": "m2_b4_whitebox_same_region_curves.csv",
            "prediction_whitebox_comparison": "m2_b4_prediction_whitebox_comparison.csv",
            "variant_accuracy_summary": "m2_b4_variant_accuracy_summary.csv",
            "per_rho_accuracy_summary": "m2_b4_per_rho_accuracy_summary.csv",
            "prediction_envelopes": "m2_b4_prediction_envelopes.csv",
            "envelope_metrics": "m2_b4_envelope_metrics.csv",
            "providerC_plot": "m2_b4_providerC_vs_whitebox.png",
            "all10_envelope_plot": "m2_b4_all10_envelope_vs_whitebox.png",
        },
        "next_gate": contract["next_gate"],
    }
    _write_json(output / "m2_b4_whitebox_evaluation_manifest_v1.json", manifest)

    print("M2_B4_FROZEN_PREDICTION_WHITEBOX_EVALUATION_PASS")
    print("\nVARIANT_ACCURACY_WHOLE_SURFACE")
    cols = [
        "accuracy_rank_by_mae", "variant_id", "changed_provider",
        "mae", "rmse", "bias", "max_abs_error", "mae_improvement_vs_BASE_M1",
    ]
    print(overall[[c for c in cols if c in overall.columns]].to_string(index=False))
    print("\nPREDICTION_ENVELOPE_METRICS")
    print(envelope_metrics.to_string(index=False))
    print("M2_B4_FROZEN_PREDICTION_WHITEBOX_EVALUATION_COMPLETE")
    print(f"output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen M2-B3 predictions against graph white-box evidence"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_b4_frozen_prediction_whitebox_v1.json",
    )
    parser.add_argument(
        "--b3-manifest",
        type=Path,
        default=HERE / "results" / "m2_b3_a4_portfolio_graph_v1"
        / "m2_b3_graph_propagation_manifest_v1.json",
    )
    parser.add_argument(
        "--b3-curves",
        type=Path,
        default=HERE / "results" / "m2_b3_a4_portfolio_graph_v1"
        / "m2_b3_graph_sigma_curves.csv",
    )
    parser.add_argument(
        "--b3-variant-design",
        type=Path,
        default=HERE / "results" / "m2_b3_a4_portfolio_graph_v1"
        / "m2_b3_variant_design.csv",
    )
    parser.add_argument(
        "--whitebox-ledgers",
        type=Path,
        default=PHASE1 / "results" / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_b4_frozen_prediction_whitebox_v1",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="fingerprint frozen M2-B3 predictions without reading graph white-box evidence",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
