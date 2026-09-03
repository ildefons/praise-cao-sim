"""Diagnose Phase-1 SLA-compliance white-box finalist selection.

This utility reads the SLA candidate metrics produced from the sealed N=10
request ledgers. It never changes rho*=0.95, the cumulative [0,H]-from-t=0
accounting semantics, or the configured area band. Its purpose is to determine
whether a missing latency/cost/mixed finalist is caused by the area gate, the
available admissibility-region substrate, or the L/C role evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from selection_policy import load_sla_compliance_area_selection_policy
from whitebox_candidate_selection import (
    build_whitebox_candidate_table,
    rank_candidates_for_role,
)

SELECTION_ROLES = ("latency", "cost", "mixed")

DISPLAY_COLUMNS = [
    "physical_setting_id",
    "region_id",
    "center_instruction_mean",
    "dispersion",
    "l_max",
    "c_max",
    "q_min",
    "normalized_sla_compliance_area",
    "sigma_120_reporting",
    "sigma_240_reporting",
    "decided_request_count",
    "failed_request_count",
    "latency_failure_count",
    "cost_failure_count",
    "latency_failure_fraction_of_lc",
    "cost_failure_fraction_of_lc",
    "n_sigma_transition_times",
    "longest_sigma_plateau_fraction_of_domain",
]


def add_area_deficit(candidates: pd.DataFrame, policy) -> pd.DataFrame:
    """Add distance from the fixed SLA-compliance-area interval.

    Called by:
        - ``diagnose_selection`` in this module.
    """
    table = candidates.copy()
    area = table["normalized_sla_compliance_area"].astype(float)
    table["area_deficit"] = 0.0
    below = area < float(policy.area_min)
    above = area > float(policy.area_max)
    table.loc[below, "area_deficit"] = float(policy.area_min) - area[below]
    table.loc[above, "area_deficit"] = area[above] - float(policy.area_max)
    return table


def add_role_deficit(candidates: pd.DataFrame, role: str, policy) -> pd.DataFrame:
    """Add a non-selection diagnostic distance from one L/C role criterion.

    The diagnostic is used only to rank near misses. It does not redefine or
    soften the selector's role rule.

    Called by:
        - ``diagnose_selection`` in this module.
    """
    if role not in SELECTION_ROLES:
        raise ValueError(f"unknown selection role: {role}")

    table = candidates.copy()
    latency = table["latency_failure_count"].astype(float)
    cost = table["cost_failure_count"].astype(float)
    ratio = float(policy.dominance_ratio)

    if role == "latency":
        required = ratio * cost.clip(lower=1.0)
        table["role_deficit"] = (required - latency).clip(lower=0.0)
        table.loc[latency <= 0.0, "role_deficit"] += 1.0
    elif role == "cost":
        required = ratio * latency.clip(lower=1.0)
        table["role_deficit"] = (required - cost).clip(lower=0.0)
        table.loc[cost <= 0.0, "role_deficit"] += 1.0
    else:
        smaller = pd.concat([latency, cost], axis=1).min(axis=1)
        larger = pd.concat([latency, cost], axis=1).max(axis=1)
        observed_ratio = larger / smaller.replace(0.0, np.nan)
        table["role_deficit"] = (observed_ratio - ratio).clip(lower=0.0)
        table.loc[(latency <= 0.0) | (cost <= 0.0), "role_deficit"] = np.inf
    return table


def print_role_population_summary(candidates: pd.DataFrame, policy) -> None:
    """Print how many candidates satisfy each role before and after the area gate.

    Called by:
        - ``diagnose_selection`` in this module.
    """
    inside = candidates[candidates["inside_sla_compliance_area_band"]].copy()
    print("=== SLA CANDIDATE POPULATION ===")
    print(f"total_distinct_A={len(candidates)}")
    print(
        f"area_gate=[{policy.area_min:.6g},{policy.area_max:.6g}] "
        f"inside_gate={len(inside)}"
    )
    print(
        f"rho={policy.sla_definition.rho:.6g} "
        "accounting=cumulative_[0,H]_from_t0"
    )
    for role in SELECTION_ROLES:
        eligible = rank_candidates_for_role(candidates, role, policy)
        role_any_area = add_role_deficit(candidates, role, policy)
        exact_role_any_area = role_any_area[role_any_area["role_deficit"] <= 1e-12]
        print(
            f"role={role:7s} eligible_inside_gate={len(eligible):6d} "
            f"role_valid_any_area={len(exact_role_any_area):6d}"
        )
        if not exact_role_any_area.empty:
            area = exact_role_any_area["normalized_sla_compliance_area"].astype(float)
            print(
                f"  role_area_range=[{area.min():.6f},{area.max():.6f}] "
                f"median={area.median():.6f}"
            )


def diagnose_selection(
    metrics_csv: Path,
    policy_config: Path,
    top_n: int,
) -> None:
    """Print eligible candidates and fixed-policy near misses for each role.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(policy_config.read_text(encoding="utf-8"))
    policy = load_sla_compliance_area_selection_policy(configuration)
    raw_metrics = pd.read_csv(metrics_csv)
    candidates = build_whitebox_candidate_table(raw_metrics, policy)
    print_role_population_summary(candidates, policy)

    missing_roles: list[str] = []
    for role in SELECTION_ROLES:
        eligible = rank_candidates_for_role(candidates, role, policy)
        print(f"\n=== {role.upper()} ===")
        if not eligible.empty:
            print(f"ELIGIBLE count={len(eligible)}")
            print(eligible[DISPLAY_COLUMNS].head(top_n).to_string(index=False))
            continue

        missing_roles.append(role)
        diagnostics = add_area_deficit(candidates, policy)
        diagnostics = add_role_deficit(diagnostics, role, policy)

        print("NO_ELIGIBLE_CANDIDATE")
        print("-- closest candidates satisfying the role, regardless of area --")
        role_valid = diagnostics[
            diagnostics["role_deficit"] <= 1e-12
        ].sort_values(
            [
                "area_deficit",
                "normalized_sla_compliance_area",
                "n_sigma_transition_times",
                "physical_setting_id",
                "region_id",
            ],
            ascending=[True, True, False, True, True],
        )
        if role_valid.empty:
            print("NONE: the existing A substrate contains no candidate with this role.")
        else:
            print(
                role_valid[
                    DISPLAY_COLUMNS + ["area_deficit", "role_deficit"]
                ].head(top_n).to_string(index=False)
            )

        print("-- closest candidates inside the area gate, regardless of role --")
        inside = diagnostics[
            diagnostics["inside_sla_compliance_area_band"]
        ].sort_values(
            [
                "role_deficit",
                "n_sigma_transition_times",
                "physical_setting_id",
                "region_id",
            ],
            ascending=[True, False, True, True],
        )
        if inside.empty:
            print("NONE: no candidate is inside the configured area gate.")
        else:
            print(
                inside[
                    DISPLAY_COLUMNS + ["area_deficit", "role_deficit"]
                ].head(top_n).to_string(index=False)
            )

    if missing_roles:
        print(
            "\nPHASE1_WHITEBOX_SLA_SELECTION_DIAGNOSTIC_INCOMPLETE "
            "missing_roles=" + ",".join(missing_roles)
        )
    else:
        print("\nPHASE1_WHITEBOX_SLA_SELECTION_DIAGNOSTIC_COMPLETE")


def main() -> None:
    """Command-line entry point for SLA finalist diagnostics."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics",
        type=Path,
        default=(
            module_directory
            / "results"
            / "scientific_discovery_v1_full_domain_ar"
            / "whitebox_selection"
            / "sla_candidate_metrics.csv"
        ),
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    diagnose_selection(
        args.metrics.resolve(),
        args.policy_config.resolve(),
        max(1, int(args.top)),
    )


if __name__ == "__main__":
    main()
