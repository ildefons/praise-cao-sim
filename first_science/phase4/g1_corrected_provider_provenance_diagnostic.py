#!/usr/bin/env python3
"""Corrected G1 provider-provenance diagnostic.

Purpose
-------
Test one specific failure hypothesis without changing M0/M1/M2:

    Did G1 fail because its white-box used a different hidden provider regime
    from the regime that generated public I1?

The diagnostic holds fixed:
  * the frozen G1 graph and workload;
  * the frozen G1 A_G(rho) battery;
  * the already-materialized frozen G1 M0/M1/M2 predictions;
  * the exact same trajectory seeds used by the original G1 white-box.

It changes only the hidden provider regime for a new diagnostic WB:
  * original G1 WB: D330000000_d0.150
  * corrected WB:   D300000000_d0.200, read from the Phase-2 I1 acquisition
                    contracts.

For speed and mechanism diagnosis, the default uses the first 20 original G1
WB seeds (31000..31019). The original G1 ledger is subset to exactly those
same seeds, so original-vs-corrected WB is paired by seed. Only the corrected
20 trajectories are newly simulated.

Outputs
-------
  g1_corrected_wb_ledger_n20.csv
  g1_original_vs_corrected_wb_curves_n20.csv
  g1_corrected_diagnostic_metrics.csv
  g0_g1original_g1corrected_sigma_n20.png
  g1_corrected_provider_provenance_manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
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
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_g1_graph_simulator import execute_one_g1_prediction_trajectory  # noqa: E402
from m2_g1_public_adapter import build_g1_public_graph_spec, validate_g1_public_graph_spec  # noqa: E402

TOL = 1e-12
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _validate_i1_physical_reference(
    region_acq: dict[str, Any],
    sigma_acq: dict[str, Any],
) -> tuple[float, float]:
    r = dict(region_acq["frozen_physical_reference"])
    s = dict(sigma_acq["frozen_physical_reference"])
    for key in ("physical_setting_id", "center_instruction_mean", "dispersion"):
        if str(r[key]) != str(s[key]):
            raise RuntimeError(
                f"Phase-2 I1 region/sigma acquisition disagree on hidden reference: {key}"
            )
    center = float(r["center_instruction_mean"])
    delta = float(r["dispersion"])
    if str(r["physical_setting_id"]) != "D300000000_d0.200":
        raise RuntimeError(
            "This diagnostic was designed for the observed D300000000_d0.200 "
            f"I1 provenance, found {r['physical_setting_id']!r}"
        )
    return center, delta


def _corrected_surrogates(
    *,
    phase1: dict[str, Any],
    center: float,
    delta: float,
) -> tuple[dict[str, GraphProviderSurrogate], float, dict[str, Any]]:
    family = dict(phase1["provider_family"])
    cv = float(family["instruction_cv"])
    ipt = float(family["effective_ipt"])
    cost_rate = float(family["cost_rate"])
    x = float(family["x"])
    means = {
        "ProviderA": center * (1.0 - delta),
        "ProviderB": center,
        "ProviderC": center * (1.0 + delta),
    }
    surrogates = {
        provider: GraphProviderSurrogate(
            mean_service_time=float(means[provider]) * x / ipt,
            cost_rate=cost_rate,
            service_cv=cv,
        )
        for provider in PROVIDERS
    }
    provenance = {
        "physical_setting_id": "D300000000_d0.200",
        "center_instruction_mean": center,
        "dispersion": delta,
        "provider_instruction_means": means,
        "instruction_cv": cv,
        "effective_IPT": ipt,
        "cost_rate": cost_rate,
        "execution_fraction_x": x,
        "derived_mean_service_times": {
            p: float(surrogates[p].mean_service_time) for p in PROVIDERS
        },
    }
    return surrogates, x, provenance


def _generate_corrected_ledger(
    *,
    path: Path,
    seeds: tuple[int, ...],
    surrogates: dict[str, GraphProviderSurrogate],
    execution_fraction: float,
    workload: dict[str, float],
    graph_spec: dict[str, Any],
    canonical_ipt: float,
) -> pd.DataFrame:
    if path.exists():
        frame = pd.read_csv(path)
        actual = tuple(sorted(frame["trajectory_seed"].astype(int).unique().tolist()))
        if actual != seeds:
            raise RuntimeError("existing corrected G1 ledger uses a different seed bank")
        if int(frame["trajectory"].nunique()) != len(seeds):
            raise RuntimeError("existing corrected G1 ledger trajectory count mismatch")
        print("Corrected G1 WB: loaded completed checkpoint", flush=True)
        return frame

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
                canonical_ipt=float(canonical_ipt),
                execution_fraction=float(execution_fraction),
            )
        one.insert(0, "trajectory", int(trajectory))
        one.insert(1, "trajectory_seed", int(seed))
        frames.append(one)
        if trajectory == 0 or (trajectory + 1) % 5 == 0 or trajectory + 1 == len(seeds):
            print(f"  corrected G1 WB: {trajectory + 1}/{len(seeds)}", flush=True)

    frame = pd.concat(frames, ignore_index=True)
    frame.to_csv(path, index=False)
    return frame


def _subset_original_g1_ledger(
    ledger: pd.DataFrame,
    seeds: tuple[int, ...],
) -> pd.DataFrame:
    if "trajectory_seed" not in ledger.columns:
        raise RuntimeError("original G1 WB ledger lacks trajectory_seed")
    subset = ledger[ledger["trajectory_seed"].astype(int).isin(seeds)].copy()
    actual = tuple(sorted(subset["trajectory_seed"].astype(int).unique().tolist()))
    if actual != seeds:
        raise RuntimeError("original G1 WB ledger does not contain requested paired seeds")
    seed_to_traj = {seed: i for i, seed in enumerate(seeds)}
    subset["trajectory"] = subset["trajectory_seed"].astype(int).map(seed_to_traj)
    if subset[["trajectory", "request_id"]].duplicated().any():
        raise RuntimeError("paired original G1 subset contains duplicate requests")
    return subset


def _snap_frame_to_reference_grid(
    frame: pd.DataFrame,
    *,
    rhos: list[float],
    horizons: list[float],
    label: str,
) -> pd.DataFrame:
    """Normalize CSV-round-tripped rho/H values onto one canonical grid."""
    out = frame.copy()
    rho_ref = np.asarray(sorted(float(v) for v in rhos), dtype=float)
    h_ref = np.asarray(sorted(float(v) for v in horizons), dtype=float)

    def snap(values: pd.Series, reference: np.ndarray, axis: str) -> pd.Series:
        snapped: list[float] = []
        for raw in values.astype(float).to_numpy():
            matches = np.flatnonzero(np.abs(reference - float(raw)) <= TOL)
            if len(matches) != 1:
                raise RuntimeError(
                    f"{label}: {axis}={raw!r} has {len(matches)} matches "
                    f"within atol={TOL}"
                )
            snapped.append(float(reference[int(matches[0])]))
        return pd.Series(snapped, index=values.index, dtype=float)

    out["rho_global"] = snap(out["rho_global"], rho_ref, "rho_global")
    out["horizon"] = snap(out["horizon"], h_ref, "horizon")
    if out.duplicated(["rho_global", "horizon"]).any():
        raise RuntimeError(f"{label}: support snapping created duplicate points")
    return out


def _wb_curves(
    ledger: pd.DataFrame,
    *,
    ensemble: pd.DataFrame,
    rhos: list[float],
    horizons: list[float],
    workload: dict[str, float],
    output_column: str,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rho in rhos:
        region = ensemble[
            np.isclose(
                ensemble["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
        ][["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(region) != 1:
            raise RuntimeError(f"rho={rho:g}: frozen G1 predictions do not expose one A_G")
        rec = region.iloc[0]
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
            output_column=output_column,
        )
        curve.insert(0, "rho_global", float(rho))
        rows.append(curve)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)


def _metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, pd.DataFrame]] = [("ALL", curves)]
    groups.extend(
        (f"{float(rho):g}", group)
        for rho, group in curves.groupby("rho_global", sort=True)
    )
    for rho_label, group in groups:
        row: dict[str, Any] = {"rho": rho_label, "n_points": int(len(group))}
        for method, pred_col in (
            ("M0", "sigma_m0"),
            ("M1", "sigma_m1"),
            ("M2", "sigma_m2_mean"),
        ):
            for wb_name, wb_col in (
                ("original_D330_N20", "sigma_wb_original_n20"),
                ("corrected_D300_N20", "sigma_wb_corrected_n20"),
            ):
                err = (
                    group[pred_col].astype(float) - group[wb_col].astype(float)
                ).to_numpy()
                row[f"{method}_MAE_vs_{wb_name}"] = float(np.mean(np.abs(err)))
                row[f"{method}_bias_vs_{wb_name}"] = float(np.mean(err))

        shift = (
            group["sigma_wb_corrected_n20"].astype(float)
            - group["sigma_wb_original_n20"].astype(float)
        ).to_numpy()
        row["WB_corrected_minus_original_mean"] = float(np.mean(shift))
        row["WB_corrected_minus_original_MAE"] = float(np.mean(np.abs(shift)))
        row["WB_corrected_minus_original_max_abs"] = float(np.max(np.abs(shift)))
        rows.append(row)
    return pd.DataFrame(rows)


def _plot(
    *,
    g0: pd.DataFrame,
    comparison: pd.DataFrame,
    output_path: Path,
) -> None:
    rhos = sorted(float(v) for v in comparison["rho_global"].unique())
    fig, axes = plt.subplots(
        len(rhos),
        3,
        figsize=(17.0, 2.55 * len(rhos)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    for row_idx, rho in enumerate(rhos):
        g0g = g0[
            np.isclose(g0["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)
        ].sort_values("horizon")
        cg = comparison[
            np.isclose(comparison["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)
        ].sort_values("horizon")

        panels = (
            ("G0 WB reference (N=100)", g0g, "sigma_whitebox"),
            ("G1 original WB D330 (paired N=20)", cg, "sigma_wb_original_n20"),
            ("G1 corrected WB D300/I1-matched (paired N=20)", cg, "sigma_wb_corrected_n20"),
        )
        for col_idx, (title, frame, wb_col) in enumerate(panels):
            ax = axes[row_idx, col_idx]
            x = frame["horizon"].astype(float).to_numpy()
            ax.fill_between(
                x,
                frame["sigma_m2_min"].astype(float).to_numpy(),
                frame["sigma_m2_max"].astype(float).to_numpy(),
                alpha=0.15,
                label="M2 range",
            )
            ax.plot(x, frame[wb_col].astype(float).to_numpy(), linewidth=2.5, label="WB")
            ax.plot(x, frame["sigma_m0"].astype(float).to_numpy(), linestyle="--", linewidth=1.6, label="M0")
            ax.plot(x, frame["sigma_m1"].astype(float).to_numpy(), linestyle=":", linewidth=1.8, label="M1")
            ax.plot(x, frame["sigma_m2_mean"].astype(float).to_numpy(), linewidth=2.0, label="M2 mean")
            ax.set_title(f"{title}, rho={rho:g}", fontsize=9.5)
            ax.set_ylim(0.0, 1.02)
            ax.grid(True, alpha=0.2)

    axes[0, 0].legend(frameon=False, fontsize=7.5, ncol=5, loc="lower left")
    fig.suptitle(
        "Provider-provenance diagnostic: same frozen G1 predictions, corrected hidden WB",
        fontsize=14,
    )
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("Admissibility probability sigma")
    fig.tight_layout(rect=(0.035, 0.035, 1.0, 0.96))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run paired N=20 corrected G1 provider-provenance diagnostic"
    )
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "g1_corrected_provider_provenance_diagnostic_n20",
    )
    args = parser.parse_args()
    if int(args.n) <= 0 or int(args.n) > 100:
        raise ValueError("--n must satisfy 1 <= n <= 100")

    started = time.perf_counter()

    phase1_path = PHASE1 / "config_phase1_discovery_v1.json"
    region_acq_path = PHASE2 / "config_phase2_i1_acquisition_v1.json"
    sigma_acq_path = PHASE2 / "config_phase2_i1_sigma_acquisition_v1.json"
    i1_root = PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
    i1_manifest = i1_root / "i1_rho_conditioned_manifest_v1.json"

    phase1 = _read_json(phase1_path)
    region_acq = _read_json(region_acq_path)
    sigma_acq = _read_json(sigma_acq_path)
    center, delta = _validate_i1_physical_reference(region_acq, sigma_acq)
    surrogates, execution_fraction, corrected_provenance = _corrected_surrogates(
        phase1=phase1,
        center=center,
        delta=delta,
    )

    metadata, _, _ = load_rho_conditioned_i1_cards(i1_root, i1_manifest)
    rhos = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    graph_spec = build_g1_public_graph_spec()
    validate_g1_public_graph_spec(graph_spec)

    g1_dir = HERE / "results" / "m2_g1_prospective_validation_v1"
    g1_pred_dir = HERE / "results" / "m2_g1_blind_prediction_v1"
    g0_dir = HERE / "results" / "m2_b6_joint_ensemble_whitebox_v1"

    original_ledger_path = g1_dir / "m2_g1_whitebox_ledger.csv"
    original_ledger = pd.read_csv(original_ledger_path)
    all_original_seeds = tuple(
        sorted(original_ledger["trajectory_seed"].astype(int).unique().tolist())
    )
    if len(all_original_seeds) < int(args.n):
        raise RuntimeError("original G1 WB ledger has fewer seeds than requested")
    seeds = tuple(all_original_seeds[: int(args.n)])

    original_subset = _subset_original_g1_ledger(original_ledger, seeds)

    ensemble = pd.read_csv(g1_pred_dir / "m2_g1_ensemble_curve.csv")
    frozen_predictions = pd.read_csv(g1_dir / "m2_g1_pointwise_comparison.csv")
    required_pred = {
        "rho_global", "horizon", "sigma_m0", "sigma_m1", "sigma_m2_mean",
        "sigma_m2_min", "sigma_m2_max",
    }
    missing = sorted(required_pred.difference(frozen_predictions.columns))
    if missing:
        raise RuntimeError("frozen G1 pointwise comparison lacks: " + ", ".join(missing))

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    corrected_ledger_path = output / f"g1_corrected_wb_ledger_n{int(args.n)}.csv"
    corrected_ledger = _generate_corrected_ledger(
        path=corrected_ledger_path,
        seeds=seeds,
        surrogates=surrogates,
        execution_fraction=execution_fraction,
        workload=workload,
        graph_spec=graph_spec,
        canonical_ipt=float(phase1["provider_family"]["effective_ipt"]),
    )

    original_curve = _wb_curves(
        original_subset,
        ensemble=ensemble,
        rhos=rhos,
        horizons=horizons,
        workload=workload,
        output_column="sigma_wb_original_n20",
    )
    corrected_curve = _wb_curves(
        corrected_ledger,
        ensemble=ensemble,
        rhos=rhos,
        horizons=horizons,
        workload=workload,
        output_column="sigma_wb_corrected_n20",
    )
    # CSV serialization can move values such as rho=0.9833333333333333 by
    # one representable float. Scientific support is the frozen I1 grid, so
    # normalize all join keys to that grid before exact merges.
    original_curve = _snap_frame_to_reference_grid(
        original_curve, rhos=rhos, horizons=horizons, label="original G1 WB"
    )
    corrected_curve = _snap_frame_to_reference_grid(
        corrected_curve, rhos=rhos, horizons=horizons, label="corrected G1 WB"
    )
    frozen_for_join = _snap_frame_to_reference_grid(
        frozen_predictions[
            [
                "rho_global", "horizon", "sigma_m0", "sigma_m1",
                "sigma_m2_mean", "sigma_m2_min", "sigma_m2_max",
            ]
        ],
        rhos=rhos,
        horizons=horizons,
        label="frozen G1 predictions",
    )

    curves = original_curve.merge(
        corrected_curve,
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    ).merge(
        frozen_for_join,
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    )
    if len(curves) != len(rhos) * len(horizons):
        raise RuntimeError("corrected diagnostic support is incomplete")

    curves_path = output / f"g1_original_vs_corrected_wb_curves_n{int(args.n)}.csv"
    curves.to_csv(curves_path, index=False)

    metrics = _metrics(curves)
    metrics_path = output / "g1_corrected_diagnostic_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    g0 = pd.read_csv(g0_dir / "m2_b6_pointwise_comparison.csv")
    plot_path = output / f"g0_g1original_g1corrected_sigma_n{int(args.n)}.png"
    _plot(g0=g0, comparison=curves, output_path=plot_path)

    manifest = {
        "status": "G1_CORRECTED_PROVIDER_PROVENANCE_DIAGNOSTIC_COMPLETE",
        "scientific_role": "mechanism/provenance diagnostic, not prospective validation",
        "n_trajectories": int(args.n),
        "paired_seed_start": int(seeds[0]),
        "paired_seed_end": int(seeds[-1]),
        "same_seeds_original_and_corrected": True,
        "original_G1_hidden_regime": "D330000000_d0.150",
        "corrected_hidden_regime": corrected_provenance,
        "public_I1_hidden_reference_from_region_acquisition": dict(
            region_acq["frozen_physical_reference"]
        ),
        "public_I1_hidden_reference_from_sigma_acquisition": dict(
            sigma_acq["frozen_physical_reference"]
        ),
        "G1_graph_unchanged": True,
        "G1_A_G_unchanged": True,
        "M0_predictions_unchanged": True,
        "M1_predictions_unchanged": True,
        "M2_predictions_unchanged": True,
        "original_G1_ledger_sha256": _sha256(original_ledger_path),
        "corrected_G1_ledger_sha256": _sha256(corrected_ledger_path),
        "frozen_G1_pointwise_predictions_sha256": _sha256(
            g1_dir / "m2_g1_pointwise_comparison.csv"
        ),
        "phase1_config_sha256": _sha256(phase1_path),
        "phase2_region_acquisition_contract_sha256": _sha256(region_acq_path),
        "phase2_sigma_acquisition_contract_sha256": _sha256(sigma_acq_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest),
        "curves_sha256": _sha256(curves_path),
        "metrics_sha256": _sha256(metrics_path),
        "plot": plot_path.name,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    manifest_path = output / "g1_corrected_provider_provenance_manifest.json"
    _write_json(manifest_path, manifest)

    print("G1_CORRECTED_PROVIDER_PROVENANCE_DIAGNOSTIC_COMPLETE")
    print(
        f"paired_seeds={seeds[0]}..{seeds[-1]} n={len(seeds)} "
        "(same seeds as original G1 WB subset)"
    )
    print("\nCORRECTED_HIDDEN_PROVENANCE")
    print(json.dumps(corrected_provenance, indent=2))
    print("\nDIAGNOSTIC_METRICS")
    print(metrics.to_string(index=False))
    print(f"\nplot={plot_path}")
    print(f"manifest={manifest_path}")
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


if __name__ == "__main__":
    main()
