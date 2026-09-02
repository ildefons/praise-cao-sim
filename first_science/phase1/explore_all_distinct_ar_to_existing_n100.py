"""Explore every distinct N=10 AR on the already generated N=100 trajectories.

RESULT ANALYSIS ONLY. This utility never modifies the frozen whitebox manifest,
never changes simulator parameters, and never reruns AICon/YAFS. It evaluates
all distinct admissibility regions A=(l_max,c_max,q_min) from the matched
physical regime on the existing N=100 trajectory bank. Any candidate identified
from this analysis is exploratory and requires a new independent confirmation
seed bank before it can replace a frozen whitebox.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from atlas_analysis import calculate_first_violation_observation_for_trajectory

TARGET_SURVIVAL = 0.95


def deduplicate_exact_admissibility_regions(
    full_regions: pd.DataFrame,
    physical_setting_id: str,
) -> pd.DataFrame:
    """Keep one provenance row for each exact A in the requested physical regime.

    Region IDs may differ even when the underlying admissibility thresholds are
    identical (for example original and full-domain augmentation provenance).
    Scientific transfer is therefore evaluated once per exact threshold tuple.

    Called by:
        - ``execute_all_ar_transfer_exploration`` in this module.
    """
    physical = full_regions[
        full_regions["physical_setting_id"].astype(str) == str(physical_setting_id)
    ].copy()
    if physical.empty:
        raise ValueError(f"no N=10 AR rows found for {physical_setting_id}")

    key_columns = ["l_max", "c_max", "q_min"]
    grouped_rows: list[dict[str, object]] = []
    for key, group in physical.groupby(key_columns, sort=True, dropna=False):
        sigma_values = group["sigma_anchor"].astype(float).round(12).unique()
        if len(sigma_values) != 1:
            raise ValueError(f"duplicate exact A has inconsistent N=10 sigma values: {key}")
        row = group.iloc[0].to_dict()
        row["equivalent_region_count"] = int(len(group))
        row["equivalent_region_ids"] = ";".join(sorted(group["region_id"].astype(str).tolist()))
        grouped_rows.append(row)
    return pd.DataFrame(grouped_rows).reset_index(drop=True)


def evaluate_all_distinct_regions_on_existing_n100(
    regions: pd.DataFrame,
    n100_ledgers: pd.DataFrame,
    anchor_horizon: float,
    stop_time: float,
) -> pd.DataFrame:
    """Evaluate every exact A using the frozen first-violation semantics.

    Called by:
        - ``execute_all_ar_transfer_exploration`` in this module.
    """
    trajectory_groups = list(n100_ledgers.groupby("trajectory", sort=True))
    if len(trajectory_groups) != 100:
        raise ValueError(f"expected 100 existing trajectories, found {len(trajectory_groups)}")

    rows: list[dict[str, object]] = []
    for _, candidate in regions.iterrows():
        observations = [
            calculate_first_violation_observation_for_trajectory(
                trajectory_ledger,
                latency_threshold=float(candidate["l_max"]),
                cost_threshold=float(candidate["c_max"]),
                quality_threshold=float(candidate["q_min"]),
                stop_time=float(stop_time),
            )
            for _, trajectory_ledger in trajectory_groups
        ]
        sigma_anchor = sum(
            observation.time is None or float(observation.time) > float(anchor_horizon)
            for observation in observations
        ) / len(observations)
        sigma_stop = sum(
            observation.time is None or float(observation.time) > float(stop_time)
            for observation in observations
        ) / len(observations)
        causes = pd.Series([observation.cause for observation in observations]).value_counts()
        latency_count = int(causes.get("latency", 0))
        cost_count = int(causes.get("cost", 0))
        censored_count = int(causes.get("censored", 0))
        total_lc = latency_count + cost_count
        if latency_count > 0 and cost_count == 0:
            descriptive_role = "latency_only"
        elif cost_count > 0 and latency_count == 0:
            descriptive_role = "cost_only"
        elif latency_count > 0 and cost_count > 0:
            descriptive_role = "mixed"
        else:
            descriptive_role = "no_lc_failure"
        rows.append(
            {
                "region_id": str(candidate["region_id"]),
                "equivalent_region_count": int(candidate["equivalent_region_count"]),
                "equivalent_region_ids": str(candidate["equivalent_region_ids"]),
                "ar_augmentation_type": str(candidate.get("ar_augmentation_type", "UNKNOWN")),
                "l_max": float(candidate["l_max"]),
                "c_max": float(candidate["c_max"]),
                "q_min": float(candidate["q_min"]),
                "n10_sigma_120": float(candidate["sigma_anchor"]),
                "n100_sigma_120": float(sigma_anchor),
                "n100_sigma_240": float(sigma_stop),
                "n100_abs_target_error": abs(float(sigma_anchor) - TARGET_SURVIVAL),
                "n100_latency_first_count": latency_count,
                "n100_cost_first_count": cost_count,
                "n100_censored_count": censored_count,
                "n100_total_lc_failures": total_lc,
                "n100_cost_fraction_among_lc_failures": (
                    float(cost_count / total_lc) if total_lc > 0 else float("nan")
                ),
                "n100_unique_first_violation_times": int(
                    len({float(o.time) for o in observations if o.time is not None})
                ),
                "descriptive_n100_role": descriptive_role,
            }
        )
    return pd.DataFrame(rows)


def print_top_distinct_regions(summary: pd.DataFrame, top_n: int) -> None:
    """Print target-near candidates separately by observed N=100 failure structure."""
    columns = [
        "descriptive_n100_role",
        "region_id",
        "l_max",
        "c_max",
        "n10_sigma_120",
        "n100_sigma_120",
        "n100_sigma_240",
        "n100_latency_first_count",
        "n100_cost_first_count",
        "n100_censored_count",
        "n100_unique_first_violation_times",
        "n100_abs_target_error",
    ]
    for role in ("latency_only", "mixed", "cost_only", "no_lc_failure"):
        group = summary[summary["descriptive_n100_role"] == role].copy()
        if group.empty:
            continue
        group = group.sort_values(
            [
                "n100_abs_target_error",
                "n100_total_lc_failures",
                "n100_unique_first_violation_times",
                "l_max",
                "c_max",
            ],
            ascending=[True, False, False, True, True],
        )
        print(f"\n=== {role.upper()} TOP DISTINCT A ===")
        print(group[columns].head(int(top_n)).to_string(index=False))


def write_all_ar_transfer_plot(summary: pd.DataFrame, output_directory: Path) -> None:
    """Plot N=100 anchor survival against N=100 stop survival for every exact A."""
    figure, axis = plt.subplots(figsize=(6.8, 5.5))
    for role, group in summary.groupby("descriptive_n100_role", sort=False):
        axis.scatter(
            group["n100_sigma_120"],
            group["n100_sigma_240"],
            s=18,
            alpha=0.65,
            label=role,
        )
    axis.axvline(TARGET_SURVIVAL, linestyle=":", linewidth=1.0)
    axis.set_xlim(0.0, 1.01)
    axis.set_ylim(0.0, 1.01)
    axis.set_xlabel("Existing N=100 sigma(120)")
    axis.set_ylabel("Existing N=100 sigma(240)")
    axis.set_title("Exploratory transfer of all distinct N=10 ARs")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output_directory / "all_distinct_ar_n100_sigma120_vs_sigma240.png", dpi=180)
    plt.close(figure)


def execute_all_ar_transfer_exploration(
    n10_results_directory: Path,
    n100_results_directory: Path,
    frozen_manifest_path: Path,
    output_directory: Path,
    top_n: int,
) -> pd.DataFrame:
    """Evaluate all distinct N=10 ARs on the existing N=100 trajectory bank."""
    full_regions = pd.read_csv(n10_results_directory / "admissibility_regions.csv")
    n100_ledgers = pd.read_csv(n100_results_directory / "all_top_level_request_ledgers.csv")
    configuration = json.loads(
        (n100_results_directory / "effective_config.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8"))

    physical_ids = {str(item["physical_setting_id"]) for item in manifest["whiteboxes"]}
    if len(physical_ids) != 1:
        raise ValueError("all-AR transfer requires one matched physical regime")
    physical_setting_id = next(iter(physical_ids))
    n100_ids = set(n100_ledgers["physical_setting_id"].astype(str).unique())
    if n100_ids != {physical_setting_id}:
        raise ValueError("existing N=100 ledgers do not match the frozen physical regime")

    distinct_regions = deduplicate_exact_admissibility_regions(
        full_regions,
        physical_setting_id=physical_setting_id,
    )
    summary = evaluate_all_distinct_regions_on_existing_n100(
        distinct_regions,
        n100_ledgers,
        anchor_horizon=float(configuration["admissibility_calibration"]["anchor_horizon"]),
        stop_time=float(configuration["horizon"]["simulation_stop_time"]),
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    distinct_regions.to_csv(output_directory / "all_distinct_n10_regions.csv", index=False)
    summary.to_csv(output_directory / "all_distinct_n10_to_existing_n100.csv", index=False)
    write_all_ar_transfer_plot(summary, output_directory)

    print(
        "PHASE1_ALL_DISTINCT_AR_TO_EXISTING_N100_EXPLORATION_PASS",
        f"n_distinct_A={len(summary)}",
        "exploratory_only=true",
    )
    print_top_distinct_regions(summary, top_n=top_n)
    print(
        "IMPORTANT any candidate selected after this N=100 inspection requires "
        "a new independent confirmation seed bank"
    )
    print(f"output_directory={output_directory}")
    return summary


def main() -> None:
    """Command-line entry point for all-distinct-AR exploratory transfer."""
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
        default=module_directory / "results" / "all_distinct_ar_to_existing_n100",
    )
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()
    execute_all_ar_transfer_exploration(
        args.n10_results.resolve(),
        args.n100_results.resolve(),
        args.frozen_manifest.resolve(),
        args.output.resolve(),
        top_n=max(1, int(args.top)),
    )


if __name__ == "__main__":
    main()
