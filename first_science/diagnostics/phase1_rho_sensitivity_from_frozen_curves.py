"""Read-only rho sensitivity diagnostic for the frozen Phase-1 N=100 curves.

Scientific question
-------------------
For the already-frozen top-level admissibility regions A_G, how does

    sigma_G(A_G, H; rho) = P(c_G(A_G, H) >= rho)

move when rho is changed without changing A_G, the trajectories, or request
admissibility decisions?

This diagnostic does NOT rerun the simulator and does NOT recalibrate A_G. It
uses the stored per-trajectory cumulative compliance fractions c_G(A_G,H).
The original rho=0.95 curve is reconstructed as an internal consistency check.

Input
-----
A Phase-1 ``trajectory_compliance_curves.csv`` produced by the matched N=100
confirmation runner. The companion ``sigma_curves.csv`` is used, when present,
to verify exact reconstruction of the frozen rho=0.95 grid curve.

Output
------
A rho-family CSV, a compact H=120/H=240 summary, and one plot per frozen
latency/mixed/cost case. Outputs are diagnostic only.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EVENT_TOLERANCE = 1e-12
DEFAULT_RHOS = (0.90, 0.95, 0.975, 0.99, 1.0)


def _find_default_input(phase1_directory: Path) -> Path:
    """Locate the most likely frozen N=100 trajectory-compliance table."""
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


def recompute_sigma_family(
    trajectory_curves: pd.DataFrame,
    rho_values: tuple[float, ...],
) -> pd.DataFrame:
    """Threshold frozen c_j(A,H) values at several rho values and average over j."""
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

    rows: list[pd.DataFrame] = []
    for rho in rho_values:
        current = trajectory_curves[
            [
                "case_id",
                "selection_role",
                "trajectory",
                "horizon",
                "compliance_fraction",
            ]
        ].copy()
        current["rho"] = float(rho)
        current["passes_rho"] = (
            current["compliance_fraction"].astype(float) + EVENT_TOLERANCE
            >= float(rho)
        )
        sigma = (
            current.groupby(
                ["case_id", "selection_role", "rho", "horizon"],
                as_index=False,
            )
            .agg(
                sigma=("passes_rho", "mean"),
                n_trajectories=("passes_rho", "count"),
            )
        )
        rows.append(sigma)

    result = pd.concat(rows, ignore_index=True)
    counts = set(result["n_trajectories"].astype(int))
    if counts != {100}:
        raise ValueError(
            f"Expected exactly 100 trajectories at every point, found counts={sorted(counts)}"
        )
    return result.sort_values(
        ["selection_role", "rho", "horizon"]
    ).reset_index(drop=True)


def verify_frozen_rho_095(
    rho_family: pd.DataFrame,
    original_sigma_path: Path,
) -> float | None:
    """Verify that rho=.95 reproduces the stored frozen grid sigma exactly."""
    if not original_sigma_path.exists():
        return None
    original = pd.read_csv(original_sigma_path)
    required = {"case_id", "selection_role", "horizon", "sigma"}
    if required.difference(original.columns):
        return None

    reconstructed = rho_family[
        np.isclose(rho_family["rho"].astype(float), 0.95, atol=1e-12, rtol=0.0)
    ][["case_id", "selection_role", "horizon", "sigma"]].copy()
    merged = reconstructed.merge(
        original[["case_id", "selection_role", "horizon", "sigma"]],
        on=["case_id", "selection_role", "horizon"],
        suffixes=("_recomputed", "_frozen"),
        validate="one_to_one",
    )
    if len(merged) != len(reconstructed) or len(merged) != len(original):
        raise RuntimeError("rho=.95 verification did not align all frozen sigma points")
    difference = np.abs(
        merged["sigma_recomputed"].astype(float).to_numpy()
        - merged["sigma_frozen"].astype(float).to_numpy()
    )
    max_difference = float(difference.max(initial=0.0))
    if max_difference > 1e-12:
        raise RuntimeError(
            f"rho=.95 reconstruction differs from frozen sigma by {max_difference}"
        )
    return max_difference


def build_anchor_summary(rho_family: pd.DataFrame) -> pd.DataFrame:
    """Return sigma at H=120 and H=240 for rapid interpretation."""
    selected = rho_family[
        rho_family["horizon"].astype(float).isin([120.0, 240.0])
    ].copy()
    summary = selected.pivot_table(
        index=["selection_role", "rho"],
        columns="horizon",
        values="sigma",
        aggfunc="first",
    ).reset_index()
    summary.columns.name = None
    rename = {120.0: "sigma_120", 240.0: "sigma_240"}
    return summary.rename(columns=rename).sort_values(
        ["selection_role", "rho"]
    ).reset_index(drop=True)


def write_case_plots(rho_family: pd.DataFrame, output_directory: Path) -> None:
    """Write one rho-family plot for each frozen admissibility-role case."""
    labels = {
        "latency": "L-dominant",
        "mixed": "Mixed L/C",
        "cost": "C-dominant",
    }
    for role, case_data in rho_family.groupby("selection_role", sort=True):
        figure, axis = plt.subplots(figsize=(8.0, 5.2))
        for rho, curve in case_data.groupby("rho", sort=True):
            ordered = curve.sort_values("horizon")
            axis.step(
                ordered["horizon"],
                ordered["sigma"],
                where="post",
                linewidth=1.7,
                label=f"rho={float(rho):g}",
            )
        axis.set_xlim(0.0, 240.0)
        axis.set_ylim(0.0, 1.02)
        axis.set_xlabel("Horizon H since t=0")
        axis.set_ylabel("Empirical SLA compliance probability sigma(H; rho)")
        axis.set_title(
            f"Frozen Phase-1 {labels.get(str(role), str(role))}: rho sensitivity"
        )
        axis.grid(True, alpha=0.25)
        axis.legend()
        figure.tight_layout()
        figure.savefig(
            output_directory / f"rho_sensitivity_{role}.png",
            dpi=180,
        )
        plt.close(figure)


def main() -> None:
    """Run the read-only rho sensitivity diagnostic from frozen Phase-1 outputs."""
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
        default=phase1_directory / "results" / "rho_sensitivity_diagnostic",
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
    rho_values = tuple(sorted(set(float(value) for value in args.rhos)))
    if not rho_values or any(not 0.0 < value <= 1.0 for value in rho_values):
        raise ValueError("all rho values must satisfy 0 < rho <= 1")

    output_directory = args.output.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    trajectory_curves = pd.read_csv(input_path)
    rho_family = recompute_sigma_family(trajectory_curves, rho_values)
    max_difference = verify_frozen_rho_095(
        rho_family,
        input_path.parent / "sigma_curves.csv",
    )
    summary = build_anchor_summary(rho_family)

    rho_family.to_csv(output_directory / "rho_sigma_family.csv", index=False)
    summary.to_csv(output_directory / "rho_anchor_summary.csv", index=False)
    write_case_plots(rho_family, output_directory)

    print("PHASE1_RHO_SENSITIVITY_DIAGNOSTIC_PASS")
    print(f"input={input_path}")
    if max_difference is None:
        print("rho_095_frozen_grid_check=NOT_AVAILABLE")
    else:
        print(f"rho_095_frozen_grid_max_abs_diff={max_difference:.3g}")
    print(summary.to_string(index=False))
    print(f"output={output_directory}")


if __name__ == "__main__":
    main()
