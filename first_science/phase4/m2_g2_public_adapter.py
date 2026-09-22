"""Public deterministic adapter for the frozen G2 calibrated condition.

This module contains no white-box evidence. It materializes the predeclared
moderate symmetric G2 network embedding and composes the frozen provider
admissibility boundaries into the uncalibrated G2 base boundary. Step-0 may
only relax that base boundary according to the separately frozen G2 contract.
"""
from __future__ import annotations

from typing import Mapping

from m0_analytic_composition import AdmissibilityBoundary

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TOL = 1e-12

G2_CONDITION_ID = "G2_MODERATE_SYMMETRIC_PARALL_V1"
G2_PROVIDER_PR_SECONDS = {
    "ProviderA": 0.004,
    "ProviderB": 0.004,
    "ProviderC": 0.004,
}
G2_FIXED_COMMON_LATENCY_SECONDS = 0.012002
G2_BRANCH_FIXED_LATENCY_SECONDS = {
    "ProviderA": 0.008001,
    "ProviderB": 0.008001,
    "ProviderC": 0.008001,
}


def build_g2_public_graph_spec() -> dict[str, object]:
    """Return the frozen public G2 graph specification."""
    return {
        "status": "FROZEN_PUBLIC_G2_MODERATE_SYMMETRIC_NETWORK_ADAPTER_V1",
        "condition_id": G2_CONDITION_ID,
        "graph": "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost",
        "network_model": {
            "law": "latency_hop=message_bytes/(BW_mbps*1e6)+PR",
            "request_bytes": 1000,
            "branch_bytes": 1000,
            "join_bytes": 1000,
            "completion_control_bytes": 0,
            "BW_mbps": 1000.0,
            # Compatibility field required by create_m1_graph_application.
            # The G2 topology itself uses PR_seconds below explicitly.
            "PR": 0.001,
            "PR_seconds": {
                "Source_to_Fpre": 0.001,
                "Fpre_to_ProviderA": 0.004,
                "Fpre_to_ProviderB": 0.004,
                "Fpre_to_ProviderC": 0.004,
                "Fpre_to_Fpost_join": 0.001,
            },
            "cost_per_hop": 0.0,
            "qos_neutral": True,
        },
        "fixed_service_model": {
            "Fpre_instructions": 5_000_000.0,
            "Fpost_instructions": 5_000_000.0,
            "effective_IPT": 1_000_000_000.0,
            "COST_rate": 3.0,
            "Fpre_latency": 0.005,
            "Fpost_latency": 0.005,
            "Fpre_cost": 0.015,
            "Fpost_cost": 0.015,
            "qos_neutral": True,
        },
        "fixed_terms_outside_provider_boundaries": {
            "common_latency_seconds": G2_FIXED_COMMON_LATENCY_SECONDS,
            "provider_branch_fixed_latency_seconds": dict(
                G2_BRANCH_FIXED_LATENCY_SECONDS
            ),
            "cost": 0.03,
        },
        "full_boundary_formula": {
            "latency": "l_G2_base=0.020003+max(l_A,l_B,l_C)",
            "cost": "c_G2_base=0.03+c_A+c_B+c_C",
            "quality": "q_G2_base=min(q_A,q_B,q_C)",
        },
        "whitebox_sigma_used": False,
    }


def validate_g2_public_graph_spec(graph_spec: Mapping[str, object]) -> None:
    """Validate the public G2 condition against the frozen contract."""
    if str(graph_spec.get("condition_id")) != G2_CONDITION_ID:
        raise ValueError("unexpected G2 condition id")
    if str(graph_spec.get("graph")) != (
        "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost"
    ):
        raise ValueError("unexpected G2 graph grammar")

    network = graph_spec.get("network_model")
    fixed = graph_spec.get("fixed_service_model")
    if not isinstance(network, Mapping) or not isinstance(fixed, Mapping):
        raise ValueError("G2 public graph spec lacks network/fixed mappings")
    if abs(float(network.get("BW_mbps", -1.0)) - 1000.0) > TOL:
        raise ValueError("G2 bandwidth differs from frozen contract")

    pr = network.get("PR_seconds")
    if not isinstance(pr, Mapping):
        raise ValueError("G2 public graph spec lacks PR_seconds")
    expected_pr = {
        "Source_to_Fpre": 0.001,
        "Fpre_to_ProviderA": 0.004,
        "Fpre_to_ProviderB": 0.004,
        "Fpre_to_ProviderC": 0.004,
        "Fpre_to_Fpost_join": 0.001,
    }
    for key, expected in expected_pr.items():
        if abs(float(pr.get(key, float("nan"))) - expected) > TOL:
            raise ValueError(f"G2 propagation delay mismatch for {key}")


def build_g2_base_global_boundary(
    provider_boundaries: Mapping[str, AdmissibilityBoundary],
) -> AdmissibilityBoundary:
    """Forward-compose frozen provider boundaries through public G2 algebra."""
    if set(provider_boundaries) != set(PROVIDERS):
        raise ValueError("provider_boundaries must contain ProviderA/B/C")

    branch_latency = {
        provider: (
            float(provider_boundaries[provider].l_max)
            + float(G2_BRANCH_FIXED_LATENCY_SECONDS[provider])
        )
        for provider in PROVIDERS
    }
    return AdmissibilityBoundary(
        l_max=float(G2_FIXED_COMMON_LATENCY_SECONDS)
        + max(branch_latency.values()),
        c_max=0.03
        + sum(float(provider_boundaries[p].c_max) for p in PROVIDERS),
        q_min=min(float(provider_boundaries[p].q_min) for p in PROVIDERS),
    )


def relax_g2_boundary(
    base: AdmissibilityBoundary,
    *,
    latency_scale: float,
    cost_scale: float,
) -> AdmissibilityBoundary:
    """Apply one frozen Step-0 relaxation to the public G2 base boundary."""
    s_l = float(latency_scale)
    s_c = float(cost_scale)
    if s_l < 1.0 - TOL or s_c < 1.0 - TOL:
        raise ValueError("G2 Step-0 regions may only relax the base boundary")
    return AdmissibilityBoundary(
        l_max=s_l * float(base.l_max),
        c_max=s_c * float(base.c_max),
        q_min=float(base.q_min),
    )
