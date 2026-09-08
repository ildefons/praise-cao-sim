"""Read-only distribution diagnostic for frozen Phase-1 trajectory compliance.

Scientific question
-------------------
For each already-frozen top-level admissibility region A_G, where does the
trajectory-level cumulative compliance fraction

    c_j(A_G, H)

actually lie at representative horizons H=120 and H=240?

This answers a different question from the rho-sensitivity plot. The latter
thresholds c_j at several rho values. Here we inspect the distribution of c_j
itself before thresholding, so we can see whether the selected A_G places the
system naturally around 0.95 or provides margin above the nominal rho=0.95 SLA.

This diagnostic does NOT rerun the simulator, does NOT change A_G, and does NOT
modify any frozen Phase-1 result. It consumes only the stored N=100
``trajectory_compliance_curves.csv`` table.

Outputs
-------
- ``compliance_fraction_summary.csv``: mean, median, standard deviation and
  quantiles of c_j(A_G,H) for H=120 and H=240.
- ``threshold_exceedance_summary.csv``: empirical P(c_j>=rho) at the selected
  diagnostic rho values, included as a cross-check against the rho-sensitivity
  diagnostic.
- one ECDF plot per latency/mixed/cost case, showing H=120 and H=240 together
  with vertical reference lines at rho={0.90,0.95,0.975,0.99,1.0}.

The outputs are diagnostic only and must not be used to silently recalibrate the
frozen benchmark.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EVENT_TOLERANCE = 1e-12
DEFAULT_HORIZONS = (120.0, 240.0)
DEFAULT_RHOS = (0.90, 0.95, 0.975, 0.99, 1.0)


def _find_default_input(phase1_directory: Path) -> Path:
    """Locate the preferred frozen N=100 trajectory-compliance table."""
    preferred = (
        phase1_directory
        / "results"
        / "final_n100_confirmation_v1"
        / "trajectory_compliance_curves.csv"
    )
    if preferred.exists():
        return preferred

    fallback = (
        phase1_directory
        / "results"
        / "n100_sla_confirmation"
        / "trajectory_compliance_curves.csv"
    )
    if fallback.exists():
        return fallback

    candidates = sorted(
        (phase1_directory / "results").glob("**/trajectory_compliance_curves.csv")
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            "No trajectory_compliance_curves.csv found under phase1/results"
        )
    raise FileNotFoundError(
        "Several trajectory_compliance_curves.csv files exist. "
        "Pass the intended frozen N=100 file explicitly with --input.\n"
        + "\n".join(str(path) for path in candidates)
    )


def select_horizon_samples(
    trajectory_curves: pd.DataFrame,
    horizons: tuple[float, ...],
) -> pd.DataFrame:
    """Extract exactly one c_j(A,H) value per trajectory, case and horizon.

    Scientific invariant
    --------------------
    The frozen matched confirmation contains N=100 trajectories for each case.
    Therefore every selected case/horizon pair must contain exactly 100 distinct
    trajectories. Missing or duplicated values indicate a malformed diagnostic
    input and are rejected rather than silently averaged.
    """
    required = {
        "case_id",
        "selection_role",
        "trajectory",
        "horizon",
        "compliance_fraction",
    }
    missing = required.difference(trajectory_curves.columns)
    if missing:
        raise ValueError(
            "trajectory compliance table missing columns: "
            + ", ".join(sorted(missing))
        )

    pieces: list[pd.DataFrame] = []
    for horizon in horizons:
        selected = trajectory_curves[
            np.isclose(
                trajectory_curves["horizon"].astype(float),
                float(horizon),
                atol=EVENT_TOLERANCE,
                rtol=0.0,
            )
        ][
            [
                "case_id",
                "selection_role",
                "trajectory",
                "horizon",
                "compliance_fraction",
            ]
        ].copy()
        if selected.empty:
            raise ValueError(f"requested horizon H={horizon:g} is absent")
        pieces.append(selected)

    samples = pd.concat(pieces, ignore_index=True)
    if samples[
        ["case_id", "selection_role", "trajectory", "horizon"]
    ].duplicated().any():
        raise ValueError("duplicate trajectory compliance values at selected horizons")

    counts = (
        samples.groupby(["case_id", "selection_role", "horizon"])["trajectory"]
        .nunique()
        .astype(int)
    )
    if set(counts.tolist()) != {100}:
        raise ValueError(
            "expected exactly 100 trajectories per case/horizon, found "
            + str(sorted(set(counts.tolist())))
        )
    return samples.sort_values(
        ["selection_role", "horizon", "trajectory"]
    ).reset_index(drop=True)


def build_distribution_summary(samples: pd.DataFrame) -> pd.DataFrame:
    """Summarize the unthresholded distribution of c_j(A,H)."""
    rows: list[dict[str, object]] = []
    quantiles = {
        "q01": 0.01,
        "q05": 0.05,
        "q10": 0.10,
        "q25": 0.25,
        "q50": 0.50,
        "q75": 0.75,
        "q90": 0.90,
        "q95": 0.95,
        "q99": 0.99,
    }
    for (case_id, role, horizon), group in samples.groupby(
        ["case_id", "selection_role", "horizon"], sort=True
    ):
        values = group["compliance_fraction"].astype(float)
        row: dict[str, object] = {
            "case_id": str(case_id),
            "selection_role": str(role),
            "horizon": float(horizon),
            "n_trajectories": int(len(values)),
            "mean": float(values.mean()),
            "std": float(values.std(ddof=1)),
            "min": float(values.min()),
            "max": float(values.max()),
        }
        for name, probability in quantiles.items():
            row[name] = float(values.quantile(probability))
        row["margin_mean_above_rho_095"] = float(values.mean() - 0.95)
        row["margin_median_above_rho_095"] = float(values.median() - 0.95)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["selection_role", "horizon"]
    ).reset_index(drop=True)


def build_threshold_exceedance_summary(
    samples: pd.DataFrame,
    rho_values: tuple[float, ...],
) -> pd.DataFrame:
    """Cross-check P(c_j>=rho) directly from the selected c_j samples."""
    rows: list[dict[str, object]] = []
    for (case_id, role, horizon), group in samples.groupby(
        ["case_id", "selection_role", "horizon"], sort=True
    ):
        values = group["compliance_fraction"].astype(float).to_numpy()
        for rho in rho_values:
            passes = values + EVENT_TOLERANCE >= float(rho)
            rows.append(
                {
                    "case_id": str(case_id),
                    "selection_role": str(role),
                    "horizon": float(horizon),
                    "rho": float(rho),
                    "sigma": float(np.mean(passes)),
                    "n_success": int(np.sum(passes)),
                    "n_trajectories": int(len(values)),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["selection_role", "horizon", "rho"]
    ).reset_index(drop=True)


def write_ecdf_plots(
    samples: pd.DataFrame,
    rho_values: tuple[float, ...],
    output_directory: Path,
) -> None:
    """Plot the c_j distribution itself, rather than only thresholded sigma."""
    labels = {
        "latency": "L-dominant",
        "mixed": "Mixed L/C",
        "cost": "C-dominant",
    }
    for role, case_data in samples.groupby("selection_role", sort=True):
        figure, axis = plt.subplots(figsize=(8.0, 5.2))

        for horizon, horizon_data in case_data.groupby("horizon", sort=True):
            values = np.sort(
                horizon_data["compliance_fraction"].astype(float).to_numpy()
            )
            ecdf = np.arange(1, len(values) + 1, dtype=float) / len(values)
            axis.step(
                values,
                ecdf,
                where="post",
                linewidth=1.8,
                label=f"H={float(horizon):g}",
            )

        for rho in rho_values:
            axis.axvline(
                float(rho),
                linestyle=":",
                linewidth=1.0,
                alpha=0.65,
            )
            axis.text(
                float(rho),
                0.02,
                f"rho={float(rho):g}",
                rotation=90,
                va="bottom",
                ha="right",
                fontsize=8,
            )

        axis.set_xlim(0.85, 1.002)
        axis.set_ylim(0.0, 1.02)
        axis.set_xlabel("Trajectory cumulative request compliance c_j(A,H)")
        axis.set_ylabel("Empirical cumulative fraction of trajectories")
        axis.set_title(
            "Frozen Phase-1 "
            + labels.get(str(role), str(role))
            + ": distribution of c_j(A,H)"
        )
        axis.grid(True, alpha=0.25)
        axis.legend()
        figure.tight_layout()
        figure.savefig(
            output_directory / f"compliance_fraction_ecdf_{role}.png",
            dpi=180,
        )
        plt.close(figure)


def main() -> None:
    """Run the read-only compliance-fraction distribution diagnostic."""
    diagnostics_directory = Path(__file__).resolve().parent
    first_science_directory = diagnostics_directory.parent
    phase1_directory = first_science_directory / "phase1"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Frozen N=100 trajectory_compliance_curves.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            phase1_directory
            / "results"
            / "compliance_fraction_distribution_diagnostic"
        ),
    )
    parser.add_argument(
        "--horizons",
        type=float,
        nargs="+",
        default=list(DEFAULT_HORIZONS),
    )
    parser.add_argument(
        "--rhos",
        type=float,
        nargs="+",
        default=list(DEFAULT_RHOS),
    )
    args = parser.parse_args()

    input_path = (
        args.input.resolve()
        if args.input is not None
        else _find_default_input(phase1_directory).resolve()
    )
    horizons = tuple(sorted(set(float(value) for value in args.horizons)))
    rho_values = tuple(sorted(set(float(value) for value in args.rhos)))
    if not horizons or any(value < 0.0 for value in horizons):
        raise ValueError("diagnostic horizons must be non-negative")
    if not rho_values or any(not 0.0 < value <= 1.0 for value in rho_values):
        raise ValueError("all rho values must satisfy 0 < rho <= 1")

    output_directory = args.output.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    trajectory_curves = pd.read_csv(input_path)
    samples = select_horizon_samples(trajectory_curves, horizons)
    distribution_summary = build_distribution_summary(samples)
    exceedance_summary = build_threshold_exceedance_summary(samples, rho_values)

    samples.to_csv(output_directory / "compliance_fraction_samples.csv", index=False)
    distribution_summary.to_csv(
        output_directory / "compliance_fraction_summary.csv", index=False
    )
    exceedance_summary.to_csv(
        output_directory / "threshold_exceedance_summary.csv", index=False
    )
    write_ecdf_plots(samples, rho_values, output_directory)

    display_columns = [
        "selection_role",
        "horizon",
        "mean",
        "q05",
        "q25",
        "q50",
        "q75",
        "q95",
        "min",
        "max",
        "margin_mean_above_rho_095",
    ]
    print("PHASE1_COMPLIANCE_FRACTION_DISTRIBUTION_DIAGNOSTIC_PASS")
    print(f"input={input_path}")
    print("\nUNTHRESHOLDED c_j(A,H) DISTRIBUTION")
    print(distribution_summary[display_columns].to_string(index=False))
    print("\nTHRESHOLD EXCEEDANCE CROSS-CHECK")
    print(
        exceedance_summary[
            ["selection_role", "horizon", "rho", "sigma"]
        ].to_string(index=False)
    )
    print(f"output={output_directory}")


if __name__ == "__main__":
    main()
