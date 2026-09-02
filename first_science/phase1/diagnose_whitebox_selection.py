"""Diagnose revised Phase-1 AUC-gated white-box selection.

This utility reads the selector ranking table and current versioned policy. It
never changes the configured area band. For each role it prints eligible cases;
if a role is missing it reports the closest area/role near misses so a later
physical discovery refinement can be evidence-driven rather than iterative
threshold tuning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from selection_policy import load_survival_area_selection_policy
from whitebox_candidate_selection import build_whitebox_candidate_table, rank_candidates_for_role

DISPLAY_COLUMNS = [
    "physical_setting_id", "region_id", "center_instruction_mean", "dispersion",
    "l_max", "c_max", "q_min", "normalized_restricted_survival_area",
    "restricted_survival_area_seconds", "sigma_120_reporting",
    "latency_first_count", "cost_first_count", "censored_count",
    "n_unique_first_violation_times", "longest_plateau_fraction_of_domain",
]


def add_auc_and_role_deficits(candidates: pd.DataFrame, role: str, policy) -> pd.DataFrame:
    """Add diagnostic distances without redefining the configured selection gate."""
    table = candidates.copy()
    area = table["normalized_restricted_survival_area"].astype(float)
    table["area_deficit"] = 0.0
    below = area < policy.area_min
    above = area > policy.area_max
    table.loc[below, "area_deficit"] = policy.area_min - area[below]
    table.loc[above, "area_deficit"] = area[above] - policy.area_max

    if role == "latency":
        table["cause_count_deficit"] = (
            policy.min_dominant_cause_count - table["latency_first_count"].astype(int)
        ).clip(lower=0)
        required = policy.dominance_ratio * table["cost_first_count"].astype(int).clip(lower=1)
        table["cause_structure_deficit"] = (
            required - table["latency_first_count"].astype(int)
        ).clip(lower=0)
    elif role == "cost":
        table["cause_count_deficit"] = (
            policy.min_dominant_cause_count - table["cost_first_count"].astype(int)
        ).clip(lower=0)
        required = policy.dominance_ratio * table["latency_first_count"].astype(int).clip(lower=1)
        table["cause_structure_deficit"] = (
            required - table["cost_first_count"].astype(int)
        ).clip(lower=0)
    elif role == "mixed":
        table["cause_count_deficit"] = (
            (policy.min_mixed_cause_count_each - table["latency_first_count"].astype(int)).clip(lower=0)
            + (policy.min_mixed_cause_count_each - table["cost_first_count"].astype(int)).clip(lower=0)
        )
        imbalance = (table["latency_first_count"] - table["cost_first_count"]).abs()
        table["cause_structure_deficit"] = (
            imbalance - policy.max_mixed_cause_imbalance
        ).clip(lower=0)
    else:
        raise ValueError(f"unknown role: {role}")
    table["role_deficit"] = table["cause_count_deficit"] + table["cause_structure_deficit"]
    return table


def diagnose_selection(ranking_csv: Path, policy_config: Path, top_n: int) -> None:
    """Print eligible role candidates and strongest fixed-gate near misses."""
    configuration = json.loads(policy_config.read_text(encoding="utf-8"))
    policy = load_survival_area_selection_policy(configuration)
    raw = pd.read_csv(ranking_csv)
    candidates = build_whitebox_candidate_table(raw, policy)

    missing_roles: list[str] = []
    for role in ("latency", "cost", "mixed"):
        eligible = rank_candidates_for_role(candidates, role, policy)
        print(f"\n=== {role.upper()} ===")
        if not eligible.empty:
            print(f"ELIGIBLE count={len(eligible)}")
            print(eligible[DISPLAY_COLUMNS].head(top_n).to_string(index=False))
            continue
        missing_roles.append(role)
        near = add_auc_and_role_deficits(candidates, role, policy).sort_values(
            ["area_deficit", "role_deficit", "n_unique_first_violation_times", "physical_setting_id", "region_id"],
            ascending=[True, True, False, True, True],
        ).head(top_n)
        print("NO_ELIGIBLE_CANDIDATE")
        print(near[DISPLAY_COLUMNS + ["area_deficit", "role_deficit"]].to_string(index=False))

    if missing_roles:
        print("\nPHASE1_WHITEBOX_AUC_SELECTION_DIAGNOSTIC_INCOMPLETE missing_roles=" + ",".join(missing_roles))
    else:
        print("\nPHASE1_WHITEBOX_AUC_SELECTION_DIAGNOSTIC_COMPLETE")


def main() -> None:
    """Command-line entry point."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ranking",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1_full_domain_ar" / "whitebox_selection" / "whitebox_candidate_ranking.csv",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    diagnose_selection(args.ranking.resolve(), args.policy_config.resolve(), max(1, int(args.top)))


if __name__ == "__main__":
    main()
