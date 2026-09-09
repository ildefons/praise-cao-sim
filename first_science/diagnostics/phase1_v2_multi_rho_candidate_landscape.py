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

Implementation note
-------------------
For each candidate/trajectory, the request-decision table is constructed once.
Its ordered cumulative admissibility fractions are then reused for every rho
and reporting horizon. This is mathematically equivalent to thresholding the
same c_j(A,H) process separately for every rho, but avoids repeated Pandas
groupby work. The script prints candidate progress because the full landscape
is intentionally a nontrivial offline diagnostic.
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
from sla_compliance_analysis import build_request_sla_decision_table  # noqa: E402

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
    """Keep one provenance row per exact (l_max,c_max,q_min) in one regime."""
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


def _trajectory_multi_rho_metrics(
    request_decisions: pd.DataFrame,
    rho_values: tuple[float, ...],
    report_horizons: tuple[float, ...],
    stop_time: float,
) -> tuple[dict[float, float], dict[tuple[float, float], bool]]:
    """Evaluate one trajectory's exact area and report-horizon states for all rho.

    The frozen Phase-1 convention is preserved: requests are included only once
    their decision time is at or before H; before the first decision the
    cumulative admissibility fraction is one. Between decision events the
    cumulative fraction is constant. Therefore exact area can be obtained by
    integrating those constant intervals and thresholding the same interval
    fractions for every rho.
    """
    stop = float(stop_time)
    if stop <= 0.0:
        raise ValueError("stop_time must be positive")

    decided = request_decisions[request_decisions["decision_time"].notna()].copy()
    if decided.empty:
        return (
            {float(rho): 1.0 for rho in rho_values},
            {
                (float(rho), float(horizon)): True
                for rho in rho_values
                for horizon in report_horizons
            },
        )

    times = decided["decision_time"].astype(float).to_numpy()
    compliant = (
        decided["compliant"].fillna(False).astype(bool).to_numpy(dtype=np.int64)
    )
    observable = times <= stop + EVENT_TOLERANCE
    times = times[observable]
    compliant = compliant[observable]
    if len(times) == 0:
        return (
            {float(rho): 1.0 for rho in rho_values},
            {
                (float(rho), float(horizon)): True
                for rho in rho_values
                for horizon in report_horizons
            },
        )

    order = np.argsort(times, kind="stable")
    times = times[order]
    compliant = compliant[order]
    unique_times, first_indices, counts = np.unique(
        times,
        return_index=True,
        return_counts=True,
    )
    compliant_at_time = np.add.reduceat(compliant, first_indices)
    cumulative_decisions = np.cumsum(counts, dtype=np.int64)
    cumulative_compliant = np.cumsum(compliant_at_time, dtype=np.int64)
    cumulative_fraction = cumulative_compliant / cumulative_decisions

    prior_count = int(
        np.searchsorted(unique_times, EVENT_TOLERANCE, side="right")
    )
    initial_fraction = (
        1.0 if prior_count == 0 else float(cumulative_fraction[prior_count - 1])
    )
    observable_end = int(
        np.searchsorted(unique_times, stop + EVENT_TOLERANCE, side="right")
    )
    future_times = np.minimum(unique_times[prior_count:observable_end], stop)
    interval_fractions = np.concatenate(
        (
            np.asarray([initial_fraction], dtype=float),
            cumulative_fraction[prior_count:observable_end].astype(float),
        )
    )
    boundaries = np.concatenate(
        (
            np.asarray([0.0], dtype=float),
            future_times.astype(float),
            np.asarray([stop], dtype=float),
        )
    )
    widths = np.diff(boundaries)
    if len(widths) != len(interval_fractions):
        raise RuntimeError("internal exact-area interval construction mismatch")
    if np.any(widths < -EVENT_TOLERANCE):
        raise RuntimeError("decision times produced negative exact-area intervals")
    widths = np.maximum(widths, 0.0)

    normalized_area: dict[float, float] = {}
    for rho in rho_values:
        passing = interval_fractions + EVENT_TOLERANCE >= float(rho)
        area = float(np.sum(widths * passing.astype(float)))
        normalized_area[float(rho)] = float(area / stop)

    passes_at_horizon: dict[tuple[float, float], bool] = {}
    horizon_fraction: dict[float, float] = {}
    for horizon in report_horizons:
        index = int(
            np.searchsorted(
                unique_times,
                float(horizon) + EVENT_TOLERANCE,
                side="right",
            )
        )
        horizon_fraction[float(horizon)] = (
            1.0 if index == 0 else float(cumulative_fraction[index - 1])
        )
    for rho in rho_values:
        for horizon in report_horizons:
            passes_at_horizon[(float(rho), float(horizon))] = bool(
                horizon_fraction[float(horizon)] + EVENT_TOLERANCE >= float(rho)
            )
    return normalized_area, passes_at_horizon


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
    progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate every distinct A_G under several rho values on one frozen bank."""
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
    n_candidates = int(len(regions))
    n_trajectories = int(len(trajectory_groups))

    for candidate_index, (_, candidate) in enumerate(regions.iterrows()):
        latency_threshold = float(candidate["l_max"])
        cost_threshold = float(candidate["c_max"])
        quality_threshold = float(candidate["q_min"])
        if progress:
            print(
                "PHASE1_V2_LANDSCAPE_PROGRESS "
                f"candidate={candidate_index + 1}/{n_candidates} "
                f"region_id={candidate['region_id']}",
                flush=True,
            )

        latency_failures = 0
        cost_failures = 0
        quality_failures = 0
        area_sums = {float(rho): 0.0 for rho in rhos}
        success_counts = {
            (float(rho), float(horizon)): 0
            for rho in rhos
            for horizon in horizons
        }

        for _, trajectory_ledger in trajectory_groups:
            decision_table = build_request_sla_decision_table(
                trajectory_ledger,
                latency_threshold=latency_threshold,
                cost_threshold=cost_threshold,
                quality_threshold=quality_threshold,
                stop_time=float(stop_time),
            )
            latency_failures += int(
                decision_table["latency_failed"].astype(bool).sum()
            )
            cost_failures += int(decision_table["cost_failed"].astype(bool).sum())
            quality_failures += int(
                decision_table["quality_failed"].astype(bool).sum()
            )
            trajectory_areas, trajectory_passes = _trajectory_multi_rho_metrics(
                decision_table,
                rhos,
                horizons,
                float(stop_time),
            )
            for rho in rhos:
                area_sums[float(rho)] += float(trajectory_areas[float(rho)])
                for horizon in horizons:
                    success_counts[(float(rho), float(horizon))] += int(
                        trajectory_passes[(float(rho), float(horizon))]
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
            "latency_failure_count": int(latency_failures),
            "cost_failure_count": int(cost_failures),
            "quality_failure_count": int(quality_failures),
            "n_trajectories": n_trajectories,
        }
        wide_row = dict(base)

        for rho in rhos:
            normalized_area = float(area_sums[float(rho)] / n_trajectories)
            row = dict(base)
            row["rho"] = float(rho)
            row["normalized_area"] = normalized_area
            tag = _rho_tag(rho)
            wide_row[f"area_rho_{tag}"] = normalized_area
            for horizon in horizons:
                sigma_value = float(
                    success_counts[(float(rho), float(horizon))] / n_trajectories
                )
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


def _load_frozen_dominance_ratio() -> float:
    """Load the role-classification ratio from the frozen discovery policy."""
    configuration_path = PHASE1_DIRECTORY / "config_phase1_discovery_v1.json"
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    try:
        value = configuration["selection_quality_gate"]["role_evidence"][
            "dominance_ratio"
        ]
    except KeyError as error:
        raise KeyError(
            "frozen Phase-1 discovery configuration lacks role_evidence.dominance_ratio"
        ) from error
    ratio = float(value)
    if ratio <= 1.0:
        raise ValueError("frozen dominance_ratio must exceed one")
    return ratio


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
    dominance_ratio = _load_frozen_dominance_ratio()
    rho_values = tuple(sorted(set(float(value) for value in args.rhos)))
    report_horizons = tuple(
        sorted(set(float(value) for value in args.report_horizons))
    )

    print(
        "PHASE1_V2_MULTI_RHO_CANDIDATE_LANDSCAPE_START "
        f"n_distinct_candidates={len(distinct_regions)} "
        f"n_trajectories={n100_ledgers['trajectory'].nunique()} "
        f"rhos={rho_values}",
        flush=True,
    )
    long_metrics, wide_summary = evaluate_candidate_landscape(
        distinct_regions,
        n100_ledgers,
        rho_values=rho_values,
        report_horizons=report_horizons,
        stop_time=stop_time,
        dominance_ratio=dominance_ratio,
        expected_trajectories=100,
        progress=True,
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
    print(f"dominance_ratio={dominance_ratio:g}")
    print("selection_performed=false")
    print("fresh_confirmation_required_for_any_selected_v2_candidate=true")
    print(role_ranges.to_string(index=False))
    print(f"output={output_directory}")


if __name__ == "__main__":
    main()
