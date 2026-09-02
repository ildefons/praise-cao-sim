"""Explore how pre-existing N=10 admissibility regions transfer to N=100.

This is a RESULT-ANALYSIS utility. It never changes ``selected_whiteboxes.json``
and never recalibrates an admissibility region. It selects a small, deterministic
shortlist using N=10 discovery information only, then evaluates those exact A
regions on the already-generated paired N=100 physical trajectories.

Because the N=100 sample has already been inspected, results from this script are
exploratory. Any replacement whitebox chosen after seeing these results requires
a new independent confirmation seed bank.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from atlas_analysis import (
    calculate_empirical_survival_curve_from_first_violation_observations,
    calculate_first_violation_observation_for_trajectory,
)

TARGET_SURVIVAL = 0.95
TARGET_BRACKET_DISTANCE = 0.051
SHORTLIST_PER_ROLE_PER_SIGMA = 2
ROLES = ("latency", "mixed", "cost")


def rank_n10_candidates_for_role(candidates: pd.DataFrame, role: str) -> pd.DataFrame:
    """Rank exact N=10 AR rows for one descriptive failure-mechanism role.

    Args:
        candidates: Full discovery AR rows already restricted to the target
            physical regime and N=10 target bracket.
        role: ``latency``, ``mixed`` or ``cost``.

    Returns:
        Role-compatible rows ordered using N=10 information only.

    Called by:
        - ``build_n10_shortlist`` in this module.
        - ``test_n10_transfer_shortlist.py``.
    """
    table = candidates.copy()
    table["latency_first_count"] = table["latency_first_count"].astype(int)
    table["cost_first_count"] = table["cost_first_count"].astype(int)
    table["cause_imbalance"] = (
        table["latency_first_count"] - table["cost_first_count"]
    ).abs()
    table["balanced_support"] = table[
        ["latency_first_count", "cost_first_count"]
    ].min(axis=1)
    table["total_lc_failures"] = (
        table["latency_first_count"] + table["cost_first_count"]
    )

    if role == "latency":
        table = table[
            (table["latency_first_count"] > table["cost_first_count"])
            & (table["latency_first_count"] >= 1)
        ].copy()
        sort_columns = [
            "latency_first_count",
            "cost_first_count",
            "total_lc_failures",
            "l_max",
            "c_max",
            "region_id",
        ]
        ascending = [False, True, False, True, False, True]
    elif role == "cost":
        table = table[
            (table["cost_first_count"] > table["latency_first_count"])
            & (table["cost_first_count"] >= 1)
        ].copy()
        sort_columns = [
            "cost_first_count",
            "latency_first_count",
            "total_lc_failures",
            "c_max",
            "l_max",
            "region_id",
        ]
        ascending = [False, True, False, True, False, True]
    elif role == "mixed":
        table = table[
            (table["latency_first_count"] >= 1)
            & (table["cost_first_count"] >= 1)
        ].copy()
        sort_columns = [
            "cause_imbalance",
            "balanced_support",
            "total_lc_failures",
            "l_max",
            "c_max",
            "region_id",
        ]
        ascending = [True, False, False, True, True, True]
    else:
        raise ValueError(f"unknown role: {role}")

    return table.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def build_n10_shortlist(
    full_n10_regions: pd.DataFrame,
    frozen_manifest: dict,
    per_role_per_sigma: int = SHORTLIST_PER_ROLE_PER_SIGMA,
) -> pd.DataFrame:
    """Select a small exact-AR shortlist without consulting N=100 outcomes.

    Current frozen cases are always retained. Additional cases are chosen from
    the N=10 0.9/1.0 bracket, separately by role and empirical anchor level.

    Called by:
        - ``execute_n10_to_n100_transfer_exploration`` in this module.
        - ``test_n10_transfer_shortlist.py``.
    """
    whiteboxes = frozen_manifest.get("whiteboxes", [])
    if not whiteboxes:
        raise ValueError("frozen manifest contains no whiteboxes")
    physical_ids = {str(item["physical_setting_id"]) for item in whiteboxes}
    if len(physical_ids) != 1:
        raise ValueError("transfer exploration requires one matched physical regime")
    physical_setting_id = next(iter(physical_ids))

    physical_rows = full_n10_regions[
        full_n10_regions["physical_setting_id"].astype(str) == physical_setting_id
    ].copy()
    physical_rows["target_distance"] = (
        physical_rows["sigma_anchor"].astype(float) - TARGET_SURVIVAL
    ).abs().round(12)
    bracket = physical_rows[
        physical_rows["target_distance"] <= TARGET_BRACKET_DISTANCE
    ].copy()
    if bracket.empty:
        raise ValueError("no N=10 ARs in the 0.9/1.0 target bracket")

    frozen_role_by_region = {
        str(item["source_region_id"]): str(item["selection_role"])
        for item in whiteboxes
    }
    selected_rows: list[pd.Series] = []
    used_regions: set[str] = set()

    for source_region_id, role in frozen_role_by_region.items():
        matches = physical_rows[
            physical_rows["region_id"].astype(str) == source_region_id
        ]
        if len(matches) != 1:
            raise ValueError(f"frozen source region {source_region_id} is not unique in N=10 table")
        row = matches.iloc[0].copy()
        row["exploration_role"] = role
        row["shortlist_origin"] = "CURRENT_FROZEN"
        selected_rows.append(row)
        used_regions.add(source_region_id)

    sigma_levels = sorted(
        bracket["sigma_anchor"].astype(float).unique(),
        key=lambda value: (abs(value - TARGET_SURVIVAL), value),
    )
    for role in ROLES:
        for sigma_level in sigma_levels:
            level_rows = bracket[
                (bracket["sigma_anchor"].astype(float) - sigma_level).abs() <= 1e-12
            ].copy()
            ranked = rank_n10_candidates_for_role(level_rows, role)
            number_added = 0
            for _, row in ranked.iterrows():
                region_id = str(row["region_id"])
                if region_id in used_regions:
                    continue
                candidate = row.copy()
                candidate["exploration_role"] = role
                candidate["shortlist_origin"] = f"N10_SIGMA_{sigma_level:.1f}"
                selected_rows.append(candidate)
                used_regions.add(region_id)
                number_added += 1
                if number_added >= int(per_role_per_sigma):
                    break

    shortlist = pd.DataFrame(selected_rows).reset_index(drop=True)
    if shortlist.empty:
        raise ValueError("N=10 shortlist is empty")
    return shortlist


def evaluate_shortlist_on_existing_n100(
    shortlist: pd.DataFrame,
    n100_ledgers: pd.DataFrame,
    horizons: list[float],
    anchor_horizon: float,
    stop_time: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate exact shortlisted A regions on the existing 100 trajectories.

    Called by:
        - ``execute_n10_to_n100_transfer_exploration`` in this module.
    """
    trajectory_groups = list(n100_ledgers.groupby("trajectory", sort=True))
    if len(trajectory_groups) != 100:
        raise ValueError(f"expected 100 N=100 trajectories, found {len(trajectory_groups)}")

    summary_rows: list[dict[str, object]] = []
    curve_rows: list[pd.DataFrame] = []
    for _, candidate in shortlist.iterrows():
        observations = [
            calculate_first_violation_observation_for_trajectory(
                trajectory_ledger,
                latency_threshold=float(candidate["l_max"]),
                cost_threshold=float(candidate["c_max"]),
                quality_threshold=float(candidate["q_min"]),
                stop_time=stop_time,
            )
            for _, trajectory_ledger in trajectory_groups
        ]
        curve = calculate_empirical_survival_curve_from_first_violation_observations(
            observations,
            horizons=horizons,
            stop_time=stop_time,
        )
        curve.insert(0, "exploration_role", str(candidate["exploration_role"]))
        curve.insert(0, "region_id", str(candidate["region_id"]))
        curve_rows.append(curve)

        sigma_anchor = float(
            curve.loc[(curve["horizon"] - anchor_horizon).abs().idxmin(), "sigma"]
        )
        sigma_stop = float(
            curve.loc[(curve["horizon"] - stop_time).abs().idxmin(), "sigma"]
        )
        causes = pd.Series([observation.cause for observation in observations]).value_counts()
        summary_rows.append(
            {
                "exploration_role": str(candidate["exploration_role"]),
                "shortlist_origin": str(candidate["shortlist_origin"]),
                "region_id": str(candidate["region_id"]),
                "ar_augmentation_type": str(candidate.get("ar_augmentation_type", "UNKNOWN")),
                "l_max": float(candidate["l_max"]),
                "c_max": float(candidate["c_max"]),
                "q_min": float(candidate["q_min"]),
                "n10_sigma_120": float(candidate["sigma_anchor"]),
                "n10_latency_first_count": int(candidate["latency_first_count"]),
                "n10_cost_first_count": int(candidate["cost_first_count"]),
                "n100_sigma_120": sigma_anchor,
                "n100_sigma_240": sigma_stop,
                "n100_anchor_shift": sigma_anchor - float(candidate["sigma_anchor"]),
                "n100_abs_target_error": abs(sigma_anchor - TARGET_SURVIVAL),
                "n100_latency_first_count": int(causes.get("latency", 0)),
                "n100_cost_first_count": int(causes.get("cost", 0)),
                "n100_quality_first_count": int(causes.get("quality", 0)),
                "n100_censored_count": int(causes.get("censored", 0)),
                "n100_unique_first_violation_times": int(
                    len({float(o.time) for o in observations if o.time is not None})
                ),
            }
        )
    return pd.DataFrame(summary_rows), pd.concat(curve_rows, ignore_index=True)


def write_transfer_plots(
    summary: pd.DataFrame,
    curves: pd.DataFrame,
    output_directory: Path,
) -> None:
    """Write one anchor-transfer plot and one survival plot per role.

    Called by:
        - ``execute_n10_to_n100_transfer_exploration`` in this module.
    """
    figure, axis = plt.subplots(figsize=(6.2, 5.4))
    for role, group in summary.groupby("exploration_role", sort=False):
        axis.scatter(group["n10_sigma_120"], group["n100_sigma_120"], label=role)
    axis.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", linewidth=1.0)
    axis.axhline(TARGET_SURVIVAL, linestyle=":", linewidth=1.0)
    axis.set_xlim(0.85, 1.01)
    axis.set_ylim(0.0, 1.01)
    axis.set_xlabel("N=10 discovery σ(120)")
    axis.set_ylabel("Existing N=100 σ(120)")
    axis.set_title("Exploratory N=10 → N=100 anchor transfer")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_directory / "n10_to_n100_sigma120_transfer.png", dpi=180)
    plt.close(figure)

    for role in ROLES:
        role_summary = summary[summary["exploration_role"] == role].copy()
        if role_summary.empty:
            continue
        role_curves = curves[curves["exploration_role"] == role].copy()
        figure, axis = plt.subplots(figsize=(8.0, 5.2))
        for _, row in role_summary.iterrows():
            region_id = str(row["region_id"])
            curve = role_curves[role_curves["region_id"] == region_id].sort_values("horizon")
            label = (
                f"{row['shortlist_origin']} | N10={row['n10_sigma_120']:.1f} "
                f"→ N100={row['n100_sigma_120']:.2f}"
            )
            axis.step(curve["horizon"], curve["sigma"], where="post", linewidth=1.5, label=label)
        axis.set_xlim(0.0, float(role_curves["horizon"].max()))
        axis.set_ylim(0.0, 1.02)
        axis.set_xlabel("Horizon H")
        axis.set_ylabel("Empirical survival σ(H)")
        axis.set_title(f"Exploratory N=100 curves: {role} shortlist")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
        figure.tight_layout()
        figure.savefig(output_directory / f"n100_{role}_shortlist_sigma_curves.png", dpi=180)
        plt.close(figure)


def execute_n10_to_n100_transfer_exploration(
    n10_results_directory: Path,
    n100_results_directory: Path,
    frozen_manifest_path: Path,
    output_directory: Path,
) -> pd.DataFrame:
    """Run the complete offline N=10 to existing-N=100 transfer exploration.

    Side effects:
        Writes shortlist/transfer CSVs and four PNG diagnostics. Does not modify
        any frozen Phase-1 manifest or simulation result.

    Called by:
        - ``main`` in this module.
    """
    full_n10_regions = pd.read_csv(n10_results_directory / "admissibility_regions.csv")
    frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8"))
    n100_ledgers = pd.read_csv(n100_results_directory / "all_top_level_request_ledgers.csv")
    n100_configuration = json.loads(
        (n100_results_directory / "effective_config.json").read_text(encoding="utf-8")
    )

    physical_ids = {str(item["physical_setting_id"]) for item in frozen_manifest["whiteboxes"]}
    n100_physical_ids = set(n100_ledgers["physical_setting_id"].astype(str).unique())
    if physical_ids != n100_physical_ids:
        raise ValueError(
            f"N=10 matched physical regime {sorted(physical_ids)} differs from N=100 {sorted(n100_physical_ids)}"
        )

    shortlist = build_n10_shortlist(full_n10_regions, frozen_manifest)
    horizons = list(map(float, n100_configuration["horizon"]["grid"]))
    anchor_horizon = float(n100_configuration["admissibility_calibration"]["anchor_horizon"])
    stop_time = float(n100_configuration["horizon"]["simulation_stop_time"])
    summary, curves = evaluate_shortlist_on_existing_n100(
        shortlist,
        n100_ledgers,
        horizons=horizons,
        anchor_horizon=anchor_horizon,
        stop_time=stop_time,
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    shortlist.to_csv(output_directory / "n10_shortlist_exact_regions.csv", index=False)
    summary.to_csv(output_directory / "n10_to_existing_n100_transfer.csv", index=False)
    curves.to_csv(output_directory / "n100_shortlist_sigma_curves.csv", index=False)
    write_transfer_plots(summary, curves, output_directory)

    display_columns = [
        "exploration_role",
        "shortlist_origin",
        "region_id",
        "l_max",
        "c_max",
        "n10_sigma_120",
        "n100_sigma_120",
        "n100_sigma_240",
        "n100_latency_first_count",
        "n100_cost_first_count",
        "n100_censored_count",
    ]
    print("PHASE1_N10_TO_EXISTING_N100_TRANSFER_EXPLORATION_PASS")
    print(summary[display_columns].sort_values(["exploration_role", "shortlist_origin", "region_id"]).to_string(index=False))
    print(
        "IMPORTANT exploratory_only=true; any candidate chosen after inspecting this N=100 "
        "sample requires a new independent confirmation seed bank"
    )
    print(f"output_directory={output_directory}")
    return summary


def main() -> None:
    """Command-line entry point for offline N=10→N=100 transfer exploration."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n10-results",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--n100-results",
        type=Path,
        default=module_directory / "results" / "n100_matched_confirmation",
    )
    parser.add_argument(
        "--frozen-manifest",
        type=Path,
        default=module_directory / "selected_whiteboxes.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory / "results" / "n10_to_existing_n100_transfer",
    )
    args = parser.parse_args()
    execute_n10_to_n100_transfer_exploration(
        args.n10_results.resolve(),
        args.n100_results.resolve(),
        args.frozen_manifest.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
