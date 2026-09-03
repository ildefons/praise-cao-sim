"""Compute SLA metrics on the current SLA-native Phase-1 AR candidate battery.

This entry point replaces the historical first-passage AR substrate in the
current finalist-selection workflow while reusing the same sealed physical N=10
request ledgers and the same optimized SLA-compliance metric machinery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from selection_policy import load_sla_compliance_area_selection_policy
from sla_compliance_candidate_metrics import (
    compute_metrics_for_one_physical_setting,
    deduplicate_exact_admissibility_regions,
)


def compute_sla_native_candidate_metrics(
    results_directory: Path,
    policy_configuration_path: Path,
    regions_path: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Evaluate SLA-native A candidates using the sealed N=10 physical traces.

    Args:
        results_directory: Existing physical N=10 discovery result directory.
        policy_configuration_path: Current frozen Phase-1 SLA configuration.
        regions_path: SLA-native AR candidate CSV. Defaults to the output of
            ``generate_sla_native_admissibility_regions.py``.
        output_path: Optional metrics CSV override.

    Returns:
        One SLA-metric row per distinct physical-setting/A tuple.

    Side effects:
        Writes ``whitebox_selection/sla_candidate_metrics.csv``.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(
        policy_configuration_path.read_text(encoding="utf-8")
    )
    policy = load_sla_compliance_area_selection_policy(configuration)
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    reporting_anchor = float(
        configuration["admissibility_calibration"]["anchor_horizon"]
    )

    if regions_path is None:
        regions_path = (
            results_directory
            / "whitebox_selection"
            / "sla_native_admissibility_regions.csv"
        )
    if not regions_path.exists():
        raise FileNotFoundError(
            f"missing SLA-native AR candidates: {regions_path}; run "
            "`python generate_sla_native_admissibility_regions.py` first"
        )

    regions = deduplicate_exact_admissibility_regions(pd.read_csv(regions_path))
    if "ar_generation_semantics" not in regions.columns:
        raise ValueError("candidate table is not labeled as SLA-native")
    if set(regions["ar_generation_semantics"].astype(str)) != {
        "SLA_NATIVE_EMPIRICAL_REQUEST_QUANTILES_V1"
    }:
        raise ValueError("unexpected SLA-native AR generation semantics")

    ledgers_path = results_directory / "all_top_level_request_ledgers.csv"
    if not ledgers_path.exists():
        raise FileNotFoundError(f"missing sealed N=10 request ledgers: {ledgers_path}")
    ledgers = pd.read_csv(ledgers_path)

    frames: list[pd.DataFrame] = []
    for setting_id, setting_regions in regions.groupby(
        "physical_setting_id", sort=True
    ):
        setting_ledgers = ledgers[
            ledgers["physical_setting_id"].astype(str) == str(setting_id)
        ].copy()
        if setting_ledgers.empty:
            raise ValueError(f"no sealed request ledgers for {setting_id}")
        frames.append(
            compute_metrics_for_one_physical_setting(
                setting_regions,
                setting_ledgers,
                reporting_anchor_horizon=reporting_anchor,
                stop_time=stop_time,
                policy=policy,
            )
        )

    metrics = pd.concat(frames, ignore_index=True)
    if output_path is None:
        output_path = (
            results_directory
            / "whitebox_selection"
            / "sla_candidate_metrics.csv"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_path, index=False)

    print(
        "PHASE1_SLA_NATIVE_CANDIDATE_METRICS_PASS",
        f"n_distinct_A={len(metrics)}",
        f"rho={policy.sla_definition.rho:.6g}",
        f"area_band=[{policy.area_min:.6g},{policy.area_max:.6g}]",
        "accounting=cumulative_[0,H]_from_t0",
        f"regions={regions_path}",
        f"output={output_path}",
    )
    return metrics


def main() -> None:
    """Command-line entry point for SLA-native N=10 candidate reranking."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory
        / "results"
        / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument("--regions", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    compute_sla_native_candidate_metrics(
        args.results.resolve(),
        args.policy_config.resolve(),
        None if args.regions is None else args.regions.resolve(),
        None if args.output is None else args.output.resolve(),
    )


if __name__ == "__main__":
    main()
