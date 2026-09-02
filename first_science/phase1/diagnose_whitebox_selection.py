"""Diagnose Phase-1 white-box selection gates after N=10 discovery.

This module is simulator-independent and never changes selection criteria. It
reads the candidate-ranking CSV already written by ``whitebox_candidate_selection.py``
and reports which roles have eligible finalists plus the strongest near misses
for any missing role. It is intended for RESULT ANALYSIS before deciding whether
a targeted discovery refinement is scientifically justified.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from whitebox_candidate_selection import (
    MAX_MIXED_CAUSE_IMBALANCE,
    MAX_N10_TARGET_DISTANCE,
    MIN_DOMINANT_CAUSE_COUNT,
    MIN_FAILED_BY_STOP,
    MIN_MIXED_CAUSE_COUNT,
    MIN_UNIQUE_FIRST_VIOLATION_TIMES,
    rank_candidates_for_role,
)


DISPLAY_COLUMNS = [
    "physical_setting_id",
    "region_id",
    "center_instruction_mean",
    "dispersion",
    "l_max",
    "c_max",
    "q_min",
    "sigma_anchor",
    "latency_first_count",
    "cost_first_count",
    "n_failed_by_stop",
    "n_unique_first_violation_times",
    "n_distinct_sigma_levels",
    "longest_plateau_fraction_of_domain",
    "split_half_curve_supremum_difference",
]


def add_gate_deficits(candidates: pd.DataFrame, role: str) -> pd.DataFrame:
    """Add nonnegative deficits showing why candidates fail one role's gate.

    Args:
        candidates: Candidate-ranking rows produced by the selector.
        role: ``latency``, ``cost`` or ``mixed``.

    Returns:
        Copy with information, target, and role-specific deficit columns.

    Called by:
        - ``rank_near_misses_for_role`` in this module.
    """
    table = candidates.copy()
    table["target_deficit"] = (
        table["target_distance"].astype(float) - MAX_N10_TARGET_DISTANCE
    ).clip(lower=0.0)
    table["failed_by_stop_deficit"] = (
        MIN_FAILED_BY_STOP - table["n_failed_by_stop"].astype(int)
    ).clip(lower=0)
    table["unique_time_deficit"] = (
        MIN_UNIQUE_FIRST_VIOLATION_TIMES
        - table["n_unique_first_violation_times"].astype(int)
    ).clip(lower=0)
    table["sigma_level_deficit"] = (
        MIN_FAILED_BY_STOP - table["n_distinct_sigma_levels"].astype(int)
    ).clip(lower=0)
    table["information_deficit"] = (
        table["failed_by_stop_deficit"]
        + table["unique_time_deficit"]
        + table["sigma_level_deficit"]
    )

    if role == "latency":
        table["cause_count_deficit"] = (
            MIN_DOMINANT_CAUSE_COUNT - table["latency_first_count"].astype(int)
        ).clip(lower=0)
        required = 2 * table["cost_first_count"].astype(int).clip(lower=1)
        table["cause_dominance_deficit"] = (
            required - table["latency_first_count"].astype(int)
        ).clip(lower=0)
    elif role == "cost":
        table["cause_count_deficit"] = (
            MIN_DOMINANT_CAUSE_COUNT - table["cost_first_count"].astype(int)
        ).clip(lower=0)
        required = 2 * table["latency_first_count"].astype(int).clip(lower=1)
        table["cause_dominance_deficit"] = (
            required - table["cost_first_count"].astype(int)
        ).clip(lower=0)
    elif role == "mixed":
        table["cause_count_deficit"] = (
            (MIN_MIXED_CAUSE_COUNT - table["latency_first_count"].astype(int)).clip(lower=0)
            + (MIN_MIXED_CAUSE_COUNT - table["cost_first_count"].astype(int)).clip(lower=0)
        )
        imbalance = (
            table["latency_first_count"].astype(int)
            - table["cost_first_count"].astype(int)
        ).abs()
        table["cause_dominance_deficit"] = (
            imbalance - MAX_MIXED_CAUSE_IMBALANCE
        ).clip(lower=0)
    else:
        raise ValueError(f"unknown role: {role}")

    table["role_deficit"] = table["cause_count_deficit"] + table["cause_dominance_deficit"]
    return table


def rank_near_misses_for_role(candidates: pd.DataFrame, role: str) -> pd.DataFrame:
    """Rank near misses without weakening or redefining the frozen gate.

    The ordering is diagnostic only: first minimize target and information-gate
    deficits, then minimize the role-specific deficit, then prefer richer curves.

    Called by:
        - ``diagnose_selection`` in this module.
    """
    table = add_gate_deficits(candidates, role)
    return table.sort_values(
        [
            "target_deficit",
            "information_deficit",
            "role_deficit",
            "target_distance",
            "n_failed_by_stop",
            "n_unique_first_violation_times",
            "physical_setting_id",
            "region_id",
        ],
        ascending=[True, True, True, True, False, False, True, True],
    ).reset_index(drop=True)


def diagnose_selection(ranking_csv: Path, top_n: int) -> None:
    """Print eligible finalists and near misses for each diagnostic role.

    Args:
        ranking_csv: Existing ``whitebox_candidate_ranking.csv``.
        top_n: Number of near-miss rows to display when a role has no finalist.

    Called by:
        - ``main`` in this module.
    """
    candidates = pd.read_csv(ranking_csv)
    if candidates.empty:
        raise ValueError("candidate ranking is empty")

    missing_roles: list[str] = []
    for role in ("latency", "cost", "mixed"):
        eligible = rank_candidates_for_role(candidates, role)
        print(f"\n=== {role.upper()} ===")
        if not eligible.empty:
            print(f"ELIGIBLE count={len(eligible)}")
            print(eligible[DISPLAY_COLUMNS].head(top_n).to_string(index=False))
            continue

        missing_roles.append(role)
        print("NO_ELIGIBLE_CANDIDATE")
        near = rank_near_misses_for_role(candidates, role).head(top_n)
        diagnostic_columns = DISPLAY_COLUMNS + [
            "target_deficit",
            "information_deficit",
            "role_deficit",
            "failed_by_stop_deficit",
            "unique_time_deficit",
            "sigma_level_deficit",
            "cause_count_deficit",
            "cause_dominance_deficit",
        ]
        print("TOP_NEAR_MISSES")
        print(near[diagnostic_columns].to_string(index=False))

    if missing_roles:
        print(
            "\nPHASE1_WHITEBOX_SELECTION_DIAGNOSTIC_INCOMPLETE",
            "missing_roles=" + ",".join(missing_roles),
        )
    else:
        print("\nPHASE1_WHITEBOX_SELECTION_DIAGNOSTIC_COMPLETE")


def main() -> None:
    """Command-line entry point for post-discovery selection diagnostics."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ranking",
        type=Path,
        default=(
            module_directory
            / "results"
            / "scientific_discovery_v1"
            / "whitebox_selection"
            / "whitebox_candidate_ranking.csv"
        ),
    )
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    diagnose_selection(args.ranking.resolve(), top_n=max(1, int(args.top)))


if __name__ == "__main__":
    main()
