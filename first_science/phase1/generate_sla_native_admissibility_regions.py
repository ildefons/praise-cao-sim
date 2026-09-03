"""Generate SLA-native Phase-1 admissibility-region candidates offline.

This module consumes the sealed N=10 top-level request ledgers and derives a
compact static A=(l_max,c_max,q_min) candidate battery suited to the frozen
rho*=0.95 cumulative SLA semantics. It does not rerun AICon/YAFS and does not
use M0 or M1.

For each physical setting, latency and cost threshold candidates are empirical
request-level quantiles at the configured levels. The candidate battery contains
latency-only pressure (L quantile x loose C), cost-only pressure (loose L x C
quantile), and crossed L/C pressure. The historical first-passage AR generator
remains available only for provenance and is not used by the current selector.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_sla_native_ar_generator_policy(configuration: dict) -> dict:
    """Load and validate the frozen SLA-native AR generator specification.

    Args:
        configuration: Parsed Phase-1 scientific discovery configuration with
            the generator policy inserted under
            ``sla_admissibility_region_generator``.

    Returns:
        Validated generator policy dictionary.

    Side effects:
        None.

    Called by:
        - ``generate_sla_native_admissibility_regions`` in this module.
        - unit tests in ``test_sla_native_admissibility_regions.py``.
    """
    policy = configuration.get("sla_admissibility_region_generator")
    if not isinstance(policy, dict):
        raise ValueError("sla_admissibility_region_generator must be configured")
    if policy.get("status") != "FROZEN_SLA_NATIVE_AR_GENERATOR_V1":
        raise ValueError("SLA-native AR generator status is not frozen")

    levels = [float(value) for value in policy.get("quantile_levels", [])]
    if levels != [0.90, 0.925, 0.95, 0.975, 0.99]:
        raise ValueError(
            "Phase-1 SLA-native AR quantiles must remain "
            "[0.90,0.925,0.95,0.975,0.99]"
        )
    if policy.get("quantile_interpolation") != "higher":
        raise ValueError("SLA-native AR empirical quantiles must use higher interpolation")
    if policy.get("pooling") != "pooled_requests_within_physical_setting_across_N10":
        raise ValueError("SLA-native AR quantiles must pool requests within each N=10 setting")
    if policy.get("quality_threshold_rule") != "q_star=x":
        raise ValueError("SLA-native AR quality threshold must remain q*=x")
    if policy.get("loose_latency_rule") != "simulation_stop_time_plus_epsilon":
        raise ValueError("unexpected loose-latency rule")
    if policy.get("loose_cost_rule") != "max_finite_cost_times_multiplier_plus_epsilon":
        raise ValueError("unexpected loose-cost rule")
    if float(policy.get("loose_cost_multiplier", 0.0)) <= 1.0:
        raise ValueError("loose_cost_multiplier must exceed one")
    epsilon = float(policy.get("epsilon", 0.0))
    if not 0.0 < epsilon < 1e-3:
        raise ValueError("SLA-native AR epsilon must be small and positive")
    families = list(policy.get("candidate_families", []))
    expected_families = [
        "latency_quantile_x_cost_loose",
        "latency_loose_x_cost_quantile",
        "latency_quantile_x_cost_quantile",
    ]
    if families != expected_families:
        raise ValueError("unexpected SLA-native AR candidate families")
    if policy.get("m0_m1_allowed_in_generator") is not False:
        raise ValueError("M0/M1 must remain outside SLA-native AR generation")
    if policy.get("midpoint_or_area_target_used_in_generator") is not False:
        raise ValueError("AR generation may not target the area-gate midpoint")
    return policy


def empirical_higher_quantiles(values: pd.Series, quantile_levels: list[float]) -> list[float]:
    """Return unique empirical quantile thresholds using observed upper order statistics.

    Args:
        values: Finite request-level scalar outcomes.
        quantile_levels: Prespecified probabilities in (0,1).

    Returns:
        Unique thresholds in ascending order.

    Side effects:
        None.

    Called by:
        - ``build_sla_native_regions_for_one_physical_setting`` in this module.
        - unit tests in ``test_sla_native_admissibility_regions.py``.
    """
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[np.isfinite(numeric.to_numpy(dtype=float))]
    if numeric.empty:
        raise ValueError("cannot derive empirical quantiles from no finite values")
    thresholds = [
        float(numeric.quantile(float(level), interpolation="higher"))
        for level in quantile_levels
    ]
    return sorted(set(thresholds))


def build_sla_native_regions_for_one_physical_setting(
    setting_ledgers: pd.DataFrame,
    physical_setting_id: str,
    configuration: dict,
) -> pd.DataFrame:
    """Build axis-isolated and crossed SLA-native A candidates for one setting.

    Latency/cost empirical quantiles are computed from all finite completed
    request outcomes pooled across the frozen N=10 trajectories. ``l_loose`` is
    larger than every observable elapsed time in the [0,Hmax] benchmark, so no
    latency deadline can bind before stop. ``c_loose`` is above every finite
    observed request cost.

    Args:
        setting_ledgers: Sealed N=10 top-level request ledger for one setting.
        physical_setting_id: Stable physical-setting identifier.
        configuration: Frozen Phase-1 configuration including generator policy.

    Returns:
        Candidate admissibility-region table.

    Side effects:
        None.

    Called by:
        - ``generate_sla_native_admissibility_regions`` in this module.
        - unit tests in ``test_sla_native_admissibility_regions.py``.
    """
    required = {
        "physical_setting_id",
        "center_instruction_mean",
        "dispersion",
        "trajectory",
        "request_id",
        "L",
        "C",
        "Q",
    }
    missing = required.difference(setting_ledgers.columns)
    if missing:
        raise ValueError(f"request ledgers missing columns: {sorted(missing)}")

    policy = load_sla_native_ar_generator_policy(configuration)
    levels = [float(value) for value in policy["quantile_levels"]]
    finite_latency = pd.to_numeric(setting_ledgers["L"], errors="coerce")
    finite_cost = pd.to_numeric(setting_ledgers["C"], errors="coerce")
    latency_finite_values = finite_latency[
        np.isfinite(finite_latency.to_numpy(dtype=float))
    ]
    cost_finite_values = finite_cost[np.isfinite(finite_cost.to_numpy(dtype=float))]
    if latency_finite_values.empty or cost_finite_values.empty:
        raise ValueError("physical setting must expose finite completed L and C outcomes")

    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    epsilon = float(policy["epsilon"])
    loose_latency = stop_time + epsilon
    loose_cost = (
        float(cost_finite_values.max()) * float(policy["loose_cost_multiplier"])
        + epsilon
    )
    q_min = float(configuration["provider_family"]["x"])
    center = float(setting_ledgers["center_instruction_mean"].iloc[0])
    dispersion = float(setting_ledgers["dispersion"].iloc[0])

    quantile_to_latency = {
        float(level): float(
            latency_finite_values.quantile(float(level), interpolation="higher")
        )
        for level in levels
    }
    quantile_to_cost = {
        float(level): float(
            cost_finite_values.quantile(float(level), interpolation="higher")
        )
        for level in levels
    }

    raw_rows: list[dict[str, object]] = []
    for level in levels:
        raw_rows.append(
            {
                "generator_family": "latency_quantile_x_cost_loose",
                "latency_quantile": level,
                "cost_quantile": np.nan,
                "l_max": quantile_to_latency[level],
                "c_max": loose_cost,
            }
        )
    for level in levels:
        raw_rows.append(
            {
                "generator_family": "latency_loose_x_cost_quantile",
                "latency_quantile": np.nan,
                "cost_quantile": level,
                "l_max": loose_latency,
                "c_max": quantile_to_cost[level],
            }
        )
    for latency_level in levels:
        for cost_level in levels:
            raw_rows.append(
                {
                    "generator_family": "latency_quantile_x_cost_quantile",
                    "latency_quantile": latency_level,
                    "cost_quantile": cost_level,
                    "l_max": quantile_to_latency[latency_level],
                    "c_max": quantile_to_cost[cost_level],
                }
            )

    candidates = pd.DataFrame(raw_rows)
    candidates.insert(0, "q_min", q_min)
    candidates.insert(0, "dispersion", dispersion)
    candidates.insert(0, "center_instruction_mean", center)
    candidates.insert(0, "physical_setting_id", str(physical_setting_id))
    candidates["loose_latency_threshold"] = loose_latency
    candidates["loose_cost_threshold"] = loose_cost
    candidates["ar_generation_semantics"] = "SLA_NATIVE_EMPIRICAL_REQUEST_QUANTILES_V1"
    candidates["search_rho"] = float(configuration["sla_compliance"]["search_rho"])
    candidates["accounting_window"] = "cumulative_[0,H]_from_t0"

    dedup_keys = ["physical_setting_id", "l_max", "c_max", "q_min"]
    candidates = candidates.drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
    candidates.insert(
        1,
        "region_id",
        [
            f"{physical_setting_id}_SLA_A{index:04d}"
            for index in range(len(candidates))
        ],
    )
    return candidates


def generate_sla_native_admissibility_regions(
    results_directory: Path,
    configuration_path: Path,
    generator_configuration_path: Path,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Generate current Phase-1 AR candidates from sealed N=10 request ledgers.

    Args:
        results_directory: Existing physical N=10 discovery result directory.
        configuration_path: Frozen scientific discovery configuration.
        generator_configuration_path: Frozen SLA-native AR generator policy.
        output_path: Optional candidate CSV destination.

    Returns:
        SLA-native candidate table across all physical settings.

    Side effects:
        Writes ``whitebox_selection/sla_native_admissibility_regions.csv``.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    generator_policy = json.loads(
        generator_configuration_path.read_text(encoding="utf-8")
    )
    configuration["sla_admissibility_region_generator"] = generator_policy
    load_sla_native_ar_generator_policy(configuration)
    if abs(float(configuration["sla_compliance"]["search_rho"]) - 0.95) > 1e-12:
        raise ValueError("SLA-native AR generation requires frozen rho*=0.95")

    ledgers_path = results_directory / "all_top_level_request_ledgers.csv"
    if not ledgers_path.exists():
        raise FileNotFoundError(f"missing sealed N=10 request ledgers: {ledgers_path}")
    all_ledgers = pd.read_csv(ledgers_path)

    frames: list[pd.DataFrame] = []
    for setting_id, setting_ledgers in all_ledgers.groupby(
        "physical_setting_id", sort=True
    ):
        frames.append(
            build_sla_native_regions_for_one_physical_setting(
                setting_ledgers,
                str(setting_id),
                configuration,
            )
        )
    regions = pd.concat(frames, ignore_index=True)
    if output_path is None:
        output_path = (
            results_directory
            / "whitebox_selection"
            / "sla_native_admissibility_regions.csv"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    regions.to_csv(output_path, index=False)

    family_counts = regions["generator_family"].value_counts().sort_index()
    print(
        "PHASE1_SLA_NATIVE_AR_GENERATOR_PASS",
        f"n_physical_settings={regions['physical_setting_id'].nunique()}",
        f"n_regions={len(regions)}",
        "quantiles=[0.90,0.925,0.95,0.975,0.99]",
        f"output={output_path}",
    )
    print(family_counts.to_string())
    return regions


def main() -> None:
    """Command-line entry point for SLA-native offline AR generation."""
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
        "--config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--generator-config",
        type=Path,
        default=module_directory / "config_phase1_sla_ar_generator_v1.json",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    generate_sla_native_admissibility_regions(
        args.results.resolve(),
        args.config.resolve(),
        args.generator_config.resolve(),
        None if args.output is None else args.output.resolve(),
    )


if __name__ == "__main__":
    main()
