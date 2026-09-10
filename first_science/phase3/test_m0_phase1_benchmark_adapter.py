"""Simulator-independent tests for the frozen Phase-1 G0 M0 boundary adapter."""
from __future__ import annotations

import json
from math import isclose
from pathlib import Path

from m0_analytic_composition import AdmissibilityBoundary, boundary_is_sufficient_for_query
from m0_phase1_benchmark_adapter import (
    build_phase1_g0_full_m0_boundary,
    deterministic_service_boundary,
    network_hop_latency,
)

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"


def main() -> None:
    configuration = json.loads(
        (PHASE1 / "config_phase1_discovery_v1.json").read_text(encoding="utf-8")
    )

    hop = network_hop_latency(
        message_bytes=1000,
        bandwidth_mbps=1000.0,
        propagation=0.001,
    )
    assert isclose(hop, 0.001001, abs_tol=1e-15)

    stage = deterministic_service_boundary(
        instructions=5_000_000.0,
        effective_ipt=1_000_000_000.0,
        cost_rate=3.0,
    )
    assert isclose(stage.l_max, 0.005, abs_tol=1e-15)
    assert isclose(stage.c_max, 0.015, abs_tol=1e-15)
    assert isclose(stage.q_min, 1.0, abs_tol=1e-15)

    provider_boundaries = {
        "ProviderA": AdmissibilityBoundary(0.2163258539999999, 0.64708116, 0.5),
        "ProviderB": AdmissibilityBoundary(0.2899073099999896, 0.7841586329999999, 0.5),
        "ProviderC": AdmissibilityBoundary(0.5746087740002395, 0.938831592, 0.5),
    }
    induced, breakdown = build_phase1_g0_full_m0_boundary(
        configuration,
        provider_boundaries,
    )

    assert isclose(breakdown.root_network_latency, 0.001001, abs_tol=1e-15)
    assert isclose(breakdown.branch_network_latency, 0.001001, abs_tol=1e-15)
    assert isclose(breakdown.join_network_latency, 0.001001, abs_tol=1e-15)
    assert isclose(breakdown.fixed_latency_outside_provider, 0.013003, abs_tol=1e-15)
    assert isclose(breakdown.fixed_cost_outside_provider, 0.03, abs_tol=1e-15)

    assert isclose(induced.l_max, 0.5876117740002395, abs_tol=1e-12)
    assert isclose(induced.c_max, 2.400071385, abs_tol=1e-12)
    assert isclose(induced.q_min, 0.5, abs_tol=1e-12)

    latency_query = AdmissibilityBoundary(
        0.68855284199994315,
        2.60390295517990822,
        0.5,
    )
    cost_query = AdmissibilityBoundary(
        0.74739413900001495,
        2.13979268099999986,
        0.5,
    )
    mixed_query = AdmissibilityBoundary(
        0.74739413900001495,
        2.17409932499999980,
        0.5,
    )
    assert boundary_is_sufficient_for_query(induced, latency_query)
    assert not boundary_is_sufficient_for_query(induced, cost_query)
    assert not boundary_is_sufficient_for_query(induced, mixed_query)

    print("PHASE3_M0_PHASE1_BENCHMARK_ADAPTER_TESTS_PASS")
    print("M0_FIXED_NETWORK_LAW_PASS")
    print("M0_FIXED_PRE_POST_SERVICE_PASS")
    print("M0_FULL_G0_BOUNDARY_PASS")
    print("M0_V2_APPLICABILITY_LATENCY_ONLY_PASS")


if __name__ == "__main__":
    main()
