"""Read-only Phase-1 v2 multi-rho candidate-landscape diagnostic.

Scientific question
-------------------
The historical Phase-1 v1 admissibility-region selection was driven by the
normalized area of

    sigma_G(A,H;rho=0.95) = P(c_G(A,H) >= 0.95),

which produced final A_G whose trajectory-level cumulative admissibility
fractions were concentrated near rho=0.95. Before defining a replacement v2
selection rule, inspect the existing candidate landscape under several rho
values without changing the simulator, the physical regime, or the accounting
semantics.

This diagnostic evaluates every distinct candidate A_G from the existing
Phase-1 candidate set on the already generated N=100 top-level request ledgers.
For each candidate it computes exact normalized admissibility area and selected
horizon sigma values for rho in {0.95, 0.975, 0.99} by default.

Important scientific boundary
-----------------------------
This script is calibration/exploration only. The N=100 bank used here has
already been inspected and therefore MUST NOT be used as the final confirmation
bank for any v2 region selected after this analysis. A newly selected v2 A_G
requires a fresh independent confirmation seed bank.

No AICon/YAFS execution occurs here. The script reuses the frozen Phase-1
request-decision and cumulative-admissibility semantics read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DIAGNOSTICS_DIRECTORY = Path(__file__).resolve().parent
FIRST_SCIENCE_DIRECTORY = DIAGNOSTICS_DIRECTORY.parent
PHASE1_DIRECTORY = FIRST_SCIENCE_DIRECTORY / "phase1"
if str(PHASE1_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(PHASE1_DIRECTORY))

from selection_policy import classify_lc_failure_role  # noqa: E402
from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
    calculate_exact_empirical_sla_compliance_area,
)

EVENT_TOLERANCE = 1e-12
DEFAULT_RHOS = (0.95, 0.975, 0.99)
DEFAULT_REPORT_HORIZONS = (120.0, 240.0)


def _rho_tag(rho: float) -> str:
    """Return a stable CSV-column suffix for one rho value."""
    text = f"{float(rho):.6f}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def deduplicate_exact_admissibility_regions(
    full_regions: pd.DataFrame,
    physical_setting_id: str,
) -> pd.DataFrame:
    """Keep one provenance row per exact (l_max,c_max,q_min) in one regime.

    Different generator branches may emit distinct region_ids for the same
    numerical admissibility region. Landscape analysis must count that region
    once, while preserving its provenance IDs.
    """
    required = {"physical_setting_id", "region_id", "l_max", "c_max", "q_min"}
    missing = required.difference(full_regions.columns)
    if missing:
        raise ValueError(
            "candidate region table missing columns: " + ", ".join(sorted(missing))
        )

    physical = full_regions[
        full_regions["physical_setting_id"].astype(str) == str(physical_setting_id)
    ].copy()
    if physical.empty:
        raise ValueError(f"no candidate regions found for {physical_setting_id}")

    rows: list[dict[str, object]] = []
    for _, group in physical.groupby(
        ["l_max", "c_max", "q_min"], sort=True, dropna=False
    ):
        row = group.iloc[0].to_dict()
        row["equivalent_region_count"] = int(len(group))
        row["equivalent_region_ids"] = ";".join(
            sorted(group["region_id"].astype(str).tolist())
        )
        rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def _extract_sigma_at_horizon(sigma_curve: pd.DataFrame, horizon: float) -> float:
    """Return the unique sigma value at one requested report horizon."""
    mask = np.isclose(
        sigma_curve["horizon"].astype(float),
        float(horizon),
        atol=EVENT_TOLERANCE,
        rtol=0.0,
    )
    selected = sigma_curve.loc[mask, "sigma"]
    if len(selected) != 1:
        raise RuntimeError(
            f"expected one sigma point at H={float(horizon)}, found {len(selected)}"
        )
    return float(selected.iloc[0])


def _assert_candidate_rho_monotonicity(
    candidate_rows: pd.DataFrame,
    rho_values: tuple[float, ...],
    report_horizons: tuple[float, ...],
) -> None:
    """Enforce the identity that stricter rho cannot increase sigma or its area."""
    ordered_rhos = tuple(sorted(map(float, rho_values)))
    for candidate_id, group in candidate_rows.groupby("candidate_index", sort=False):
        by_rho = group.set_index("rho").sort_index()
        if tuple(map(float, by_rho.index)) != ordered_rhos:
            raise RuntimeError(f"candidate {candidate_id} has incomplete rho support")

        area_values = by_rho["normalized_area"].astype(float).to_numpy()
        if np.any(area_values[:-1] + EVENT_TOLERANCE < area_values[1:]):
            raise RuntimeError(
                f"candidate {candidate_id} violates monotonicity of area in rho"
            )

        for horizon in report_horizons:
            column = f"sigma_{int(round(float(horizon)))}"
            sigma_values = by_rho[column].astype(float).to_numpy()
            if np.any(sigma_values[:-1] + EVENT_TOLERANCE < sigma_values[1:]):
                raise RuntimeError(
                    f"candidate {candidate_id} violates sigma monotonicity in rho at H={horizon}"
                )


def evaluate_candidate_landscape(
    regions: pd.DataFrame,
    n100_ledgers: pd.DataFrame,
    *,
    rho_values: Iterable[float],
    report_horizons: Iterable[float],
    stop_time: float,
    dominance_ratio: float,
    expected_trajectories: int | None = 100,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate every distinct A_G under several rho values on one frozen bank.

    Returns
    -------
    ``(long_metrics, wide_summary)``. The long table contains one row per
    candidate/rho. The wide summary contains one row per candidate and is meant
    for landscape plotting and inspection.
    """
    rhos = tuple(sorted(set(float(value) for value in rho_values)))
    horizons = tuple(sorted(set(float(value) for value in report_horizons)))
    if not rhos or any(not 0.0 < rho <= 1.0 for rho in rhos):
        raise ValueError("rho values must satisfy 0 < rho <= 1")
    if not horizons or horizons[0] < -EVENT_TOLERANCE:
        raise ValueError("report horizons must be non-empty and non-negative")
    if horizons[-1] > float(stop_time) + EVENT_TOLERANCE:
        raise ValueError("report horizons must not exceed stop_time")
    if float(dominance_ratio) <= 1.0:
        raise ValueError("dominance_ratio must exceed one")
    if "trajectory" not in n100_ledgers.columns:
        raise ValueError("N=100 ledger table must contain trajectory")

    trajectory_groups = list(n100_ledgers.groupby("trajectory", sort=True))
    if expected_trajectories is not None and len(trajectory_groups) != int(
        expected_trajectories
    ):
        raise ValueError(
            f"expected {int(expected_trajectories)} trajectories, found {len(trajectory_groups)}"
        )
    if not trajectory_groups:
        raise ValueError("at least one trajectory is required")

    long_rows: list[dict[str, object]] = []
    wide_rows: list[dict[str, object]] = []

    for candidate_index, (_, candidate) in enumerate(regions.iterrows()):
        latency_threshold = float(candidate["l_max"])
        cost_threshold = float(candidate["c_max"])
        quality_threshold = float(candidate["q_min"])

        decision_tables = [
            build_request_sla_decision_table(
                trajectory_ledger,
                latency_threshold=latency_threshold,
                cost_threshold=cost_threshold,
                quality_threshold=quality_threshold,
                stop_time=float(stop_time),
            )
            for _, trajectory_ledger in trajectory_groups
        ]

        latency_failures = int(
            sum(int(table["latency_failed"].astype(bool).sum()) for table in decision_tables)
        )
        cost_failures = int(
            sum(int(table["cost_failed"].astype(bool).sum()) for table in decision_tables)
        )
        quality_failures = int(
            sum(int(table["quality_failed"].astype(bool).sum()) for table in decision_tables)
        )
        role = classify_lc_failure_role(
            latency_failures,
            cost_failures,
            float(dominance_ratio),
        )

        base: dict[str, object] = {
            "candidate_index": int(candidate_index),
            "region_id": str(candidate["region_id"]),
            "equivalent_region_count": int(candidate.get("equivalent_region_count", 1)),
            "equivalent_region_ids": str(
                candidate.get("equivalent_region_ids", candidate["region_id"])
            ),
            "ar_augmentation_type": str(
                candidate.get("ar_augmentation_type", "UNKNOWN")
            ),
            "l_max": latency_threshold,
            "c_max": cost_threshold,
            "q_min": quality_threshold,
            "descriptive_role": role,
            "latency_failure_count": latency_failures,
            "cost_failure_count": cost_failures,
            "quality_failure_count": quality_failures,
            "n_trajectories": int(len(trajectory_groups)),
        }
        wide_row = dict(base)

        for rho in rhos:
            definition = SlaComplianceDefinition(
                rho=float(rho),
                accounting_origin=0.0,
                zero_decision_compliance=1.0,
            )
            _, normalized_area = calculate_exact_empirical_sla_compliance_area(
                decision_tables,
                definition,
                horizon_min=0.0,
                horizon_max=float(stop_time),
            )
            sigma_curve, _ = calculate_empirical_sla_sigma_from_decision_tables(
                decision_tables,
                horizons,
                definition,
            )

            row = dict(base)
            row["rho"] = float(rho)
            row["normalized_area"] = float(normalized_area)
            tag = _rho_tag(rho)
            wide_row[f"area_rho_{tag}"] = float(normalized_area)
            for horizon in horizons:
                sigma_value = _extract_sigma_at_horizon(sigma_curve, horizon)
                horizon_tag = int(round(float(horizon)))
                row[f"sigma_{horizon_tag}"] = sigma_value
                wide_row[f"sigma_{horizon_tag}_rho_{tag}"] = sigma_value
            long_rows.append(row)

        wide_rows.append(wide_row)

    long_metrics = pd.DataFrame(long_rows).sort_values(
        ["descriptive_role", "candidate_index", "rho"]
    ).reset_index(drop=True)
    wide_summary = pd.DataFrame(wide_rows).sort_values(
        ["descriptive_role", "l_max", "c_max", "q_min"]
    ).reset_index(drop=True)

    _assert_candidate_rho_monotonicity(long_metrics, rhos, horizons)
    return long_metrics, wide_summary


def build_role_ranges(long_metrics: pd.DataFrame) -> pd.DataFrame:
    """Summarize landscape ranges without ranking or selecting candidates."""
    return (
        long_metrics.groupby(["descriptive_role", "rho"], as_index=False)
        .agg(
            n_candidates=("candidate_index", "nunique"),
            area_min=("normalized_area", "min"),
            area_q25=("normalized_area", lambda x: float(x.quantile(0.25))),
            area_median=("normalized_area", "median"),
            area_q75=("normalized_area", lambda x: float(x.quantile(0.75))),
            area_max=("normalized_area", "max"),
        )
        .sort_values(["descriptive_role", "rho"])
        .reset_index(drop=True)
    )


def write_landscape_plots(
    wide_summary: pd.DataFrame,
    output_directory: Path,
    rho_values: tuple[float, ...],
) -> None:
    """Plot nominal rho=.95 area against each stricter-rho area by role."""
    if 0.95 not in rho_values:
        raise ValueError("landscape plots require rho=0.95 as the nominal reference")
    nominal_column = f"area_rho_{_rho_tag(0.95)}"

    for strict_rho in rho_values:
        if strict_rho <= 0.95 + EVENT_TOLERANCE:
            continue
        strict_column = f"area_rho_{_rho_tag(strict_rho)}"
        figure, axis = plt.subplots(figsize=(7.2, 5.8))
        for role, group in wide_summary.groupby("descriptive_role", sort=True):
            axis.scatter(
                group[nominal_column],
                group[strict_column],
                s=28,
                alpha=0.70,
                label=str(role),
            )
        axis.plot([0.0, 1.0], [0.0, 1.0], linestyle=":", linewidth=1.0)
        axis.set_xlim(0.0, 1.01)
        axis.set_ylim(0.0, 1.01)
        axis.set_xlabel("Exact normalized area R at rho=0.95")
        axis.set_ylabel(f"Exact normalized area R at rho={strict_rho:g}")
        axis.set_title("Phase-1 v2 candidate landscape: nominal vs stricter rho")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
        figure.tight_layout()
        figure.savefig(
            output_directory
            / f"candidate_landscape_area_rho095_vs_rho{_rho_tag(strict_rho)}.png",
            dpi=180,
        )
        plt.close(figure)


def _find_physical_setting_id(n100_ledgers: pd.DataFrame) -> str:
    """Require the existing N=100 ledger bank to contain one physical regime."""
    if "physical_setting_id" not in n100_ledgers.columns:
        raise ValueError("N=100 ledgers must contain physical_setting_id")
    physical_ids = sorted(n100_ledgers["physical_setting_id"].astype(str).unique())
    if len(physical_ids) != 1:
        raise ValueError(
            f"candidate landscape requires one physical regime, found {physical_ids}"
        )
    return str(physical_ids[0])


def main() -> None:
    """Run the read-only multi-rho candidate-landscape diagnostic."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-results",
        type=Path,
        default=(
            PHASE1_DIRECTORY / "results" / "scientific_discovery_v1_full_domain_ar"
        ),
    )
    parser.add_argument(
        "--n100-results",
        type=Path,
        default=PHASE1_DIRECTORY / "results" / "n100_matched_confirmation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PHASE1_DIRECTORY / "results" / "v2_multi_rho_candidate_landscape",
    )
    parser.add_argument(
        "--rhos",
        type=float,
        nargs="+",
        default=list(DEFAULT_RHOS),
    )
    parser.add_argument(
        "--report-horizons",
        type=float,
        nargs="+",
        default=list(DEFAULT_REPORT_HORIZONS),
    )
    args = parser.parse_args()

    candidate_results = args.candidate_results.resolve()
    n100_results = args.n100_results.resolve()
    output_directory = args.output.resolve()

    full_regions = pd.read_csv(candidate_results / "admissibility_regions.csv")
    n100_ledgers = pd.read_csv(n100_results / "all_top_level_request_ledgers.csv")
    effective_configuration = json.loads(
        (n100_results / "effective_config.json").read_text(encoding="utf-8")
    )

    physical_setting_id = _find_physical_setting_id(n100_ledgers)
    distinct_regions = deduplicate_exact_admissibility_regions(
        full_regions,
        physical_setting_id,
    )

    stop_time = float(effective_configuration["horizon"]["simulation_stop_time"])
    role_configuration = effective_configuration["selection_quality_gate"][
        "role_evidence"
    ]
    dominance_ratio = float(role_configuration["dominance_ratio"])
    rho_values = tuple(sorted(set(float(value) for value in args.rhos)))
    report_horizons = tuple(
        sorted(set(float(value) for value in args.report_horizons))
    )

    long_metrics, wide_summary = evaluate_candidate_landscape(
        distinct_regions,
        n100_ledgers,
        rho_values=rho_values,
        report_horizons=report_horizons,
        stop_time=stop_time,
        dominance_ratio=dominance_ratio,
        expected_trajectories=100,
    )
    role_ranges = build_role_ranges(long_metrics)

    output_directory.mkdir(parents=True, exist_ok=True)
    distinct_regions.to_csv(
        output_directory / "distinct_candidate_regions.csv", index=False
    )
    long_metrics.to_csv(
        output_directory / "candidate_multi_rho_metrics_long.csv", index=False
    )
    wide_summary.to_csv(
        output_directory / "candidate_multi_rho_summary.csv", index=False
    )
    role_ranges.to_csv(output_directory / "role_area_ranges.csv", index=False)
    write_landscape_plots(wide_summary, output_directory, rho_values)

    print("PHASE1_V2_MULTI_RHO_CANDIDATE_LANDSCAPE_PASS")
    print(f"physical_setting_id={physical_setting_id}")
    print(f"n_distinct_candidates={len(wide_summary)}")
    print(f"rho_values={rho_values}")
    print("selection_performed=false")
    print("fresh_confirmation_required_for_any_selected_v2_candidate=true")
    print(role_ranges.to_string(index=False))
    print(f"output={output_directory}")


if __name__ == "__main__":
    main()
