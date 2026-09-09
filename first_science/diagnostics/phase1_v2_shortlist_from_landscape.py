"""Read-only Phase-1 v2 shortlist extraction from the calibrated landscape.

This script applies the proposed v2 admissibility-region gate to an already
computed candidate landscape. It performs no simulation, no recomputation of
sigma, and no final confirmation. Its purpose is to expose the deterministic
candidate shortlist for human scientific review before any v2 A_G is frozen.

Proposed gate under review
--------------------------
Healthy nominal operation:
    R_0.95 >= 0.95

Informative stricter-query behavior:
    0.50 <= R_0.99 <= 0.95

Within each latency/cost/mixed role, passing candidates are ordered by largest
R_0.95 first. Numerical threshold values are used only as deterministic
secondary tie-breakers, followed by region_id. No midpoint target is used.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_ROLES = ("latency", "cost", "mixed")
DEFAULT_NOMINAL_MIN = 0.95
DEFAULT_STRESS_MIN = 0.50
DEFAULT_STRESS_MAX = 0.95


def extract_v2_shortlist(
    landscape: pd.DataFrame,
    *,
    nominal_min: float = DEFAULT_NOMINAL_MIN,
    stress_min: float = DEFAULT_STRESS_MIN,
    stress_max: float = DEFAULT_STRESS_MAX,
) -> pd.DataFrame:
    """Apply the proposed v2 gate and deterministically rank passing candidates."""
    required = {
        "region_id",
        "descriptive_role",
        "l_max",
        "c_max",
        "q_min",
        "area_rho_0p95",
        "area_rho_0p99",
    }
    missing = required.difference(landscape.columns)
    if missing:
        raise ValueError(
            "landscape missing columns: " + ", ".join(sorted(missing))
        )
    if not 0.0 <= float(nominal_min) <= 1.0:
        raise ValueError("nominal_min must lie in [0,1]")
    if not 0.0 <= float(stress_min) <= float(stress_max) <= 1.0:
        raise ValueError("stress gate must satisfy 0 <= min <= max <= 1")

    selected = landscape[
        (landscape["area_rho_0p95"].astype(float) >= float(nominal_min))
        & (landscape["area_rho_0p99"].astype(float) >= float(stress_min))
        & (landscape["area_rho_0p99"].astype(float) <= float(stress_max))
        & (landscape["descriptive_role"].astype(str).isin(REQUIRED_ROLES))
    ].copy()

    selected = selected.sort_values(
        [
            "descriptive_role",
            "area_rho_0p95",
            "area_rho_0p99",
            "l_max",
            "c_max",
            "q_min",
            "region_id",
        ],
        ascending=[True, False, True, True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    selected["role_rank"] = (
        selected.groupby("descriptive_role", sort=False).cumcount() + 1
    )
    selected["v2_nominal_gate_pass"] = True
    selected["v2_stress_gate_pass"] = True
    return selected


def build_role_summary(shortlist: pd.DataFrame) -> pd.DataFrame:
    """Summarize the number and range of passing candidates by role."""
    if shortlist.empty:
        return pd.DataFrame(
            columns=[
                "descriptive_role",
                "n_passing",
                "R95_min",
                "R95_max",
                "R99_min",
                "R99_max",
            ]
        )
    return (
        shortlist.groupby("descriptive_role", as_index=False)
        .agg(
            n_passing=("region_id", "count"),
            R95_min=("area_rho_0p95", "min"),
            R95_max=("area_rho_0p95", "max"),
            R99_min=("area_rho_0p99", "min"),
            R99_max=("area_rho_0p99", "max"),
        )
        .sort_values("descriptive_role")
        .reset_index(drop=True)
    )


def top_candidates(shortlist: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Return the first N ranked candidates in each role."""
    if int(top_n) < 1:
        raise ValueError("top_n must be positive")
    return shortlist[shortlist["role_rank"].astype(int) <= int(top_n)].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "first_science/phase1/results/"
            "v2_multi_rho_candidate_landscape_D300000000_d0.200/"
            "candidate_multi_rho_summary.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "first_science/phase1/results/"
            "v2_multi_rho_candidate_landscape_D300000000_d0.200/"
            "v2_shortlist_proposed_gate.csv"
        ),
    )
    parser.add_argument("--nominal-min", type=float, default=DEFAULT_NOMINAL_MIN)
    parser.add_argument("--stress-min", type=float, default=DEFAULT_STRESS_MIN)
    parser.add_argument("--stress-max", type=float, default=DEFAULT_STRESS_MAX)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()

    landscape = pd.read_csv(args.input)
    shortlist = extract_v2_shortlist(
        landscape,
        nominal_min=args.nominal_min,
        stress_min=args.stress_min,
        stress_max=args.stress_max,
    )
    summary = build_role_summary(shortlist)
    top = top_candidates(shortlist, args.top)

    missing_roles = [role for role in REQUIRED_ROLES if role not in set(shortlist["descriptive_role"].astype(str))]
    if missing_roles:
        raise RuntimeError(
            "proposed v2 gate leaves no candidate for roles: " + ", ".join(missing_roles)
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    shortlist.to_csv(args.output, index=False)

    print("PHASE1_V2_SHORTLIST_PROPOSED_GATE_PASS")
    print(
        f"gate=R95>={args.nominal_min:g}; "
        f"{args.stress_min:g}<=R99<={args.stress_max:g}"
    )
    print("selection_frozen=false")
    print("human_review_required_before_freeze=true")
    print("\n=== PASSING CANDIDATES BY ROLE ===")
    print(summary.to_string(index=False))
    print(f"\n=== TOP {int(args.top)} PER ROLE BY R95 ===")
    columns = [
        "descriptive_role",
        "role_rank",
        "region_id",
        "l_max",
        "c_max",
        "q_min",
        "area_rho_0p95",
        "area_rho_0p975",
        "area_rho_0p99",
        "sigma_120_rho_0p95",
        "sigma_240_rho_0p95",
        "sigma_120_rho_0p99",
        "sigma_240_rho_0p99",
    ]
    available = [column for column in columns if column in top.columns]
    print(top[available].to_string(index=False))
    print(f"\noutput={args.output.resolve()}")


if __name__ == "__main__":
    main()
