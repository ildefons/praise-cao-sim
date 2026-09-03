"""Simulator-independent tests for Phase-2 M0 contract composition."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from m0_contract_composition import (
    PROVIDERS,
    GlobalAdmissibilityRegion,
    aligned_request_counting_certificate,
    compose_i1_surface_independent_m0,
    compose_independent_i1_probabilities,
    compose_phase1_boundary_from_local_metrics,
    decompose_global_region_equal_m0,
    derive_phase1_fixed_boundary_context,
    equal_error_budget_rho,
    verify_request_level_sufficient_condition,
    yafs_single_link_latency,
)


PHASE1_CONFIG = Path(__file__).resolve().parents[1] / "phase1" / "config_phase1_discovery_v1.json"


def _load_phase1_public_config() -> dict:
    return json.loads(PHASE1_CONFIG.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    configuration = _load_phase1_public_config()
    context = derive_phase1_fixed_boundary_context(configuration)

    # Current native YAFS link rule: bytes / (BW * 1e6) + PR.
    expected_link = 1000.0 / (1000.0 * 1_000_000.0) + 0.001
    assert abs(yafs_single_link_latency(1000, 1000, 0.001) - expected_link) < 1e-15
    assert abs(context.root_network_latency - 0.001001) < 1e-15
    assert abs(context.join_network_latency - 0.001001) < 1e-15
    assert abs(context.pre_service_time - 0.005) < 1e-15
    assert abs(context.post_service_time - 0.005) < 1e-15
    assert abs(context.latency_common - 0.012002) < 1e-15
    assert all(abs(value - 0.001001) < 1e-15 for value in context.branch_network_latency)
    assert abs(context.fixed_execution_cost - 0.03) < 1e-15

    epsilon_i, rho_i = equal_error_budget_rho(0.95, 3)
    assert abs(epsilon_i - (0.05 / 3.0)) < 1e-15
    assert abs(rho_i - 0.9833333333333333) < 1e-15

    latency_region = GlobalAdmissibilityRegion(
        region_id="S4_latency",
        l_max=0.421031,
        c_max=2.603903,
        q_min=0.5,
        rho_global=0.95,
    )
    boundaries = decompose_global_region_equal_m0(latency_region, context)
    assert [boundary.provider_id for boundary in boundaries] == list(PROVIDERS)
    for boundary in boundaries:
        assert abs(boundary.l_max - 0.408028) < 1e-12
        assert abs(boundary.c_max - ((2.603903 - 0.03) / 3.0)) < 1e-12
        assert abs(boundary.q_min - 0.5) < 1e-15
        assert abs(boundary.rho_local - rho_i) < 1e-15

    # At the local boundaries, the topology algebra reaches the global L/C/Q
    # boundary exactly (up to floating-point tolerance).
    local_l = {b.provider_id: b.l_max for b in boundaries}
    local_c = {b.provider_id: b.c_max for b in boundaries}
    local_q = {b.provider_id: b.q_min for b in boundaries}
    global_l, global_c, global_q = compose_phase1_boundary_from_local_metrics(
        local_l, local_c, local_q, context
    )
    assert abs(global_l - latency_region.l_max) < 1e-12
    assert abs(global_c - latency_region.c_max) < 1e-12
    assert abs(global_q - latency_region.q_min) < 1e-15
    assert verify_request_level_sufficient_condition(
        latency_region, boundaries, context, local_l, local_c, local_q
    )

    # Hand-checkable cumulative counting certificate: 60 aligned root requests,
    # one distinct failure at each provider. Every local fraction is 59/60 =
    # 0.983333..., while the all-provider conjunction is 57/60 = 0.95.
    n = 60
    local_pass = {provider: np.ones(n, dtype=bool) for provider in PROVIDERS}
    local_pass["ProviderA"][3] = False
    local_pass["ProviderB"][17] = False
    local_pass["ProviderC"][42] = False
    certificate = aligned_request_counting_certificate(
        local_pass,
        rho_global=0.95,
        rho_local={provider: rho_i for provider in PROVIDERS},
    )
    assert certificate["local_slas_hold"]
    assert certificate["budget_valid"]
    assert certificate["certified"]
    assert abs(certificate["global_sufficient_conjunction_fraction"] - 0.95) < 1e-15

    # Independent-anchor probability composition.
    product = compose_independent_i1_probabilities(
        {"ProviderA": 0.8, "ProviderB": 0.9, "ProviderC": 0.7}
    )
    assert abs(product - 0.504) < 1e-15

    # Exact-card surface composition; no interpolation is introduced by M0.
    surfaces = {}
    local_sigmas = {
        "ProviderA": [0.8, 0.75],
        "ProviderB": [0.9, 0.85],
        "ProviderC": [0.7, 0.65],
    }
    for boundary in boundaries:
        surfaces[boundary.provider_id] = pd.DataFrame(
            {
                "l_max": [boundary.l_max, boundary.l_max],
                "c_max": [boundary.c_max, boundary.c_max],
                "q_min": [boundary.q_min, boundary.q_min],
                "rho": [boundary.rho_local, boundary.rho_local],
                "horizon": [120.0, 240.0],
                "sigma_hat": local_sigmas[boundary.provider_id],
            }
        )
    curve = compose_i1_surface_independent_m0(surfaces, boundaries)
    assert list(curve["horizon"]) == [120.0, 240.0]
    assert abs(float(curve.iloc[0]["sigma_m0_independent_product"]) - 0.504) < 1e-15
    assert abs(
        float(curve.iloc[1]["sigma_m0_independent_product"])
        - (0.75 * 0.85 * 0.65)
    ) < 1e-15

    # The other two frozen diagnostic shapes produce feasible exact local
    # boundary points as well. These rounded values mirror the paper-facing v3
    # checksum; the real runner will read the full-precision frozen manifest.
    for region in (
        GlobalAdmissibilityRegion("S4_cost", 240.0, 1.792964, 0.5, 0.95),
        GlobalAdmissibilityRegion("S4_mixed", 0.476841, 1.886981, 0.5, 0.95),
    ):
        local = decompose_global_region_equal_m0(region, context)
        assert len(local) == 3
        assert all(boundary.l_max >= 0.0 and boundary.c_max >= 0.0 for boundary in local)

    print("PHASE2_M0_CONTRACT_COMPOSITION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
