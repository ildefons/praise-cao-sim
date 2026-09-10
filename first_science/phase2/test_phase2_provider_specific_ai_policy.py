"""Simulator-independent tests for the provider-specific Phase-2 A_i policy."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from diagnose_phase2_provider_specific_ai import (
    PROVIDERS,
    derive_public_fixed_terms,
    empirical_quantile,
    solve_equal_percentile_cost_allocation,
)

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"


def run_all_tests() -> None:
    # Synthetic scaled provider families.  Equal-percentile allocation should
    # recover the same percentile independently of provider scale.
    base = np.linspace(1.0, 2.0, 101)
    samples = {
        "ProviderA": base,
        "ProviderB": 2.0 * base,
        "ProviderC": 3.0 * base,
    }
    target_p = 0.8
    target_budget = sum(empirical_quantile(samples[p], target_p) for p in PROVIDERS)
    p_star, caps = solve_equal_percentile_cost_allocation(samples, target_budget)

    assert abs(p_star - target_p) < 1e-10
    assert abs(sum(caps.values()) - target_budget) < 1e-10
    assert abs(caps["ProviderB"] / caps["ProviderA"] - 2.0) < 1e-12
    assert abs(caps["ProviderC"] / caps["ProviderA"] - 3.0) < 1e-12

    # The public structural terms are fixed by the benchmark graph, not by
    # provider-private parameters or sigma outcomes.
    configuration = json.loads(
        (PHASE1 / "config_phase1_discovery_v1.json").read_text(encoding="utf-8")
    )
    fixed = derive_public_fixed_terms(configuration)
    assert abs(float(fixed["latency_common"]) - 0.012002) < 1e-15
    assert abs(float(fixed["fixed_execution_cost"]) - 0.03) < 1e-15
    assert abs(float(fixed["fixed_quality_floor"]) - 1.0) < 1e-15
    assert all(
        abs(float(fixed["branch_network_latency"][provider]) - 0.001001) < 1e-15
        for provider in PROVIDERS
    )

    # No silent extrapolation is allowed when a global additive budget lies
    # outside the empirical provider support.
    minimum_supported = sum(empirical_quantile(samples[p], 0.0) for p in PROVIDERS)
    try:
        solve_equal_percentile_cost_allocation(samples, minimum_supported - 1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("outside-support cost budget should be rejected")

    print("PHASE2_PROVIDER_SPECIFIC_AI_POLICY_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
