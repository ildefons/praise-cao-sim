#!/usr/bin/env python3
"""Compare frozen G0 and G1 WB/M0/M1/M2 sigma curves side by side.

This is a read-only diagnostic. It performs no simulation, fitting, selection,
calibration, or model changes. It reads the already-materialized pointwise
comparison CSVs from G0 B6 and G1 prospective validation, verifies compatible
rho/horizon support, and writes:

  * g0_g1_sigma_comparison.png
  * g0_g1_sigma_condition_shift_summary.csv

The figure has one row per rho and two columns:
  left  = G0 retrospective diagnostic
  right = G1 prospective stress test

Each panel shows WB, M0, M1, M2 mean, and the frozen M2 min-max ambiguity range.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TOL = 1e-12


def _load_condition(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} comparison file not found: {path}")
    frame = pd.read_csv(path)

    required = {
        "rho_global",
        "horizon",
        "sigma_whitebox",
        "sigma_m0",
        "sigma_m1",
        "sigma_m2_mean",
        "sigma_m2_min",
        "sigma_m2_max",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"{label} comparison file lacks columns: {', '.join(missing)}"
        )
    if frame.duplicated(["rho_global", "horizon"]).any():
        raise RuntimeError(f"{label} has duplicate rho/horizon points")

    out = frame[
        [
            "rho_global",
            "horizon",
            "sigma_whitebox",
            "sigma_m0",
            "sigma_m1",
            "sigma_m2_mean",
            "sigma_m2_min",
            "sigma_m2_max",
        ]
    ].copy()
    for column in out.columns:
        out[column] = pd.to_numeric(out[column], errors="raise")
    return out.sort_values(["rho_global", "horizon"]).reset_index(drop=True)


def _snap_support(
    frame: pd.DataFrame,
    *,
    rhos: list[float],
    horizons: list[float],
    label: str,
) -> pd.DataFrame:
    out = frame.copy()

    def snap(values: pd.Series, reference: list[float], axis: str) -> pd.Series:
        ref = np.asarray(reference, dtype=float)
        snapped: list[float] = []
        for raw in values.astype(float).to_numpy():
            matches = np.flatnonzero(np.abs(ref - float(raw)) <= TOL)
            if len(matches) != 1:
                raise RuntimeError(
                    f"{label}: {axis}={raw!r} has {len(matches)} matches "
                    f"on frozen support within atol={TOL}"
                )
            snapped.append(float(ref[int(matches[0])]))
        return pd.Series(snapped, index=values.index, dtype=float)

    out["rho_global"] = snap(out["rho_global"], rhos, "rho")
    out["horizon"] = snap(out["horizon"], horizons, "horizon")
    if out.duplicated(["rho_global", "horizon"]).any():
        raise RuntimeError(f"{label}: snapping created duplicate support points")
    return out


def _condition_shift_summary(g0: pd.DataFrame, g1: pd.DataFrame) -> pd.DataFrame:
    merged = g0.merge(
        g1,
        on=["rho_global", "horizon"],
        how="inner",
        suffixes=("_g0", "_g1"),
        validate="one_to_one",
    )
    if len(merged) != len(g0) or len(merged) != len(g1):
        raise RuntimeError("G0 and G1 support do not align completely")

    method_columns = {
        "WB": "sigma_whitebox",
        "M0": "sigma_m0",
        "M1": "sigma_m1",
        "M2": "sigma_m2_mean",
    }

    rows: list[dict[str, float | int | str]] = []
    groups: list[tuple[str, pd.DataFrame]] = [("ALL", merged)]
    groups.extend(
        (f"{float(rho):g}", group)
        for rho, group in merged.groupby("rho_global", sort=True)
    )

    for rho_label, group in groups:
        row: dict[str, float | int | str] = {
            "rho": rho_label,
            "n_points": int(len(group)),
        }
        for method, column in method_columns.items():
            delta = (
                group[f"{column}_g1"].astype(float)
                - group[f"{column}_g0"].astype(float)
            ).to_numpy()
            row[f"{method}_mean_signed_G1_minus_G0"] = float(np.mean(delta))
            row[f"{method}_mean_abs_G1_minus_G0"] = float(np.mean(np.abs(delta)))
            row[f"{method}_max_abs_G1_minus_G0"] = float(np.max(np.abs(delta)))
        rows.append(row)
    return pd.DataFrame(rows)


def _plot(g0: pd.DataFrame, g1: pd.DataFrame, output_path: Path) -> None:
    rhos = sorted(float(v) for v in g0["rho_global"].unique())
    fig, axes = plt.subplots(
        len(rhos),
        2,
        figsize=(13.0, 2.55 * len(rhos)),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    conditions = (
        ("G0 retrospective", g0),
        ("G1 prospective stress", g1),
    )

    for row_idx, rho in enumerate(rhos):
        for col_idx, (condition_name, frame) in enumerate(conditions):
            ax = axes[row_idx, col_idx]
            group = frame[
                np.isclose(
                    frame["rho_global"].astype(float),
                    float(rho),
                    atol=TOL,
                    rtol=0.0,
                )
            ].sort_values("horizon")
            x = group["horizon"].astype(float).to_numpy()

            ax.fill_between(
                x,
                group["sigma_m2_min"].astype(float).to_numpy(),
                group["sigma_m2_max"].astype(float).to_numpy(),
                alpha=0.15,
                label="M2 range",
            )
            ax.plot(
                x,
                group["sigma_whitebox"].astype(float).to_numpy(),
                linewidth=2.5,
                label="WB",
            )
            ax.plot(
                x,
                group["sigma_m0"].astype(float).to_numpy(),
                linestyle="--",
                linewidth=1.7,
                label="M0",
            )
            ax.plot(
                x,
                group["sigma_m1"].astype(float).to_numpy(),
                linestyle=":",
                linewidth=1.9,
                label="M1",
            )
            ax.plot(
                x,
                group["sigma_m2_mean"].astype(float).to_numpy(),
                linewidth=2.0,
                label="M2 mean",
            )
            ax.set_ylim(0.0, 1.02)
            ax.grid(True, alpha=0.2)
            ax.set_title(f"{condition_name}, rho={rho:g}")

    axes[0, 0].legend(frameon=False, fontsize=8, ncol=5, loc="lower left")
    fig.suptitle(
        "Frozen sigma predictions under two white-box conditions\n"
        "same I1/M0/M1/M2 machinery, different WB reference",
        fontsize=14,
    )
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("Admissibility probability sigma")
    fig.tight_layout(rect=(0.035, 0.035, 1.0, 0.955))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot frozen G0/G1 WB, M0, M1 and M2 sigma curves"
    )
    parser.add_argument(
        "--g0",
        type=Path,
        default=HERE
        / "results"
        / "m2_b6_joint_ensemble_whitebox_v1"
        / "m2_b6_pointwise_comparison.csv",
    )
    parser.add_argument(
        "--g1",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_prospective_validation_v1"
        / "m2_g1_pointwise_comparison.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "g0_g1_sigma_diagnostic_v1",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    g0 = _load_condition(args.g0.resolve(), "G0")
    g1 = _load_condition(args.g1.resolve(), "G1")

    g0_rhos = sorted(float(v) for v in g0["rho_global"].unique())
    g0_horizons = sorted(float(v) for v in g0["horizon"].unique())
    g1 = _snap_support(
        g1,
        rhos=g0_rhos,
        horizons=g0_horizons,
        label="G1",
    )

    if len(g0) != len(g1):
        raise RuntimeError(
            f"G0/G1 point counts differ: G0={len(g0)} G1={len(g1)}"
        )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_path = output_dir / "g0_g1_sigma_comparison.png"
    summary_path = output_dir / "g0_g1_sigma_condition_shift_summary.csv"

    _plot(g0, g1, plot_path)
    summary = _condition_shift_summary(g0, g1)
    summary.to_csv(summary_path, index=False)

    print("G0_G1_SIGMA_DIAGNOSTIC_COMPLETE")
    print("\nCONDITION_SHIFT_SUMMARY")
    print(summary.to_string(index=False))
    print(f"\nplot={plot_path}")
    print(f"summary={summary_path}")
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


if __name__ == "__main__":
    main()
