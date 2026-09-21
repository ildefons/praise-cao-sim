"""Public deterministic adapter for the frozen G1 prospective condition.

This module contains no white-box information. It only materializes the
predeclared asymmetric public network embedding and composes already-frozen
provider admissibility boundaries forward through that graph.
"""
from __future__ import annotations

from typing import Mapping

from m0_analytic_composition import AdmissibilityBoundary

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TOL = 1e-12

G1_CONDITION_ID = "G1_ASYM_PARALL_V1"

G1_PROVIDER_PR_SECONDS = {
    "ProviderA": 0.005,
    "ProviderB": 0.015,
    "ProviderC": 0.001,
}

G1_FIXED_COMMON_LATENCY_SECONDS = 0.012002
G1_BRANCH_FIXED_LATENCY_SECONDS = {
    "ProviderA": 0.010001,
    "ProviderB": 0.030001,
    "ProviderC": 0.002001,
}


def build_g1_public_graph_spec() -> dict[str, object]:
    """Return the frozen public G1 graph specification."""
    return {
        "status": "FROZEN_PUBLIC_G1_ASYMMETRIC_NETWORK_ADAPTER_V1",
        "condition_id": G1_CONDITION_ID,
        "graph": "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost",
        "network_model": {
            "law": "latency_hop=message_bytes/(BW_mbps*1e6)+PR",
            "request_bytes": 1000,
            "branch_bytes": 1000,
            "join_bytes": 1000,
            "completion_control_bytes": 0,
            "BW_mbps": 1000.0,
            # Retained for compatibility with the existing public application
            # builder. G1 topology creation uses PR_seconds below explicitly.
            "PR": 0.001,
            "PR_seconds": {
                "Source_to_Fpre": 0.001,
                "Fpre_to_ProviderA": 0.005,
                "Fpre_to_ProviderB": 0.015,
                "Fpre_to_ProviderC": 0.001,
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
            "common_latency_seconds": G1_FIXED_COMMON_LATENCY_SECONDS,
            "provider_branch_fixed_latency_seconds": dict(
                G1_BRANCH_FIXED_LATENCY_SECONDS
            ),
            "cost": 0.03,
        },
        "full_boundary_formula": {
            "latency": (
                "l_G1=0.012002+max("
                "l_A+0.010001,l_B+0.030001,l_C+0.002001)"
            ),
            "cost": "c_G1=0.03+c_A+c_B+c_C",
            "quality": "q_G1=min(q_A,q_B,q_C)",
        },
        "whitebox_sigma_used": False,
    }


def validate_g1_public_graph_spec(graph_spec: Mapping[str, object]) -> None:
    if str(graph_spec.get("condition_id")) != G1_CONDITION_ID:
        raise ValueError("unexpected G1 condition id")
    if str(graph_spec.get("graph")) != (
        "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost"
    ):
        raise ValueError("unexpected G1 graph grammar")
    network = graph_spec.get("network_model")
    fixed = graph_spec.get("fixed_service_model")
    if not isinstance(network, Mapping) or not isinstance(fixed, Mapping):
        raise ValueError("G1 public graph spec lacks network/fixed mappings")
    if float(network.get("BW_mbps", -1.0)) != 1000.0:
        raise ValueError("G1 bandwidth differs from frozen contract")
    pr = network.get("PR_seconds")
    if not isinstance(pr, Mapping):
        raise ValueError("G1 public graph spec lacks PR_seconds")
    expected_pr = {
        "Source_to_Fpre": 0.001,
        "Fpre_to_ProviderA": 0.005,
        "Fpre_to_ProviderB": 0.015,
        "Fpre_to_ProviderC": 0.001,
        "Fpre_to_Fpost_join": 0.001,
    }
    for key, expected in expected_pr.items():
        if abs(float(pr.get(key, float("nan"))) - expected) > TOL:
            raise ValueError(f"G1 propagation delay mismatch for {key}")


def build_g1_induced_global_boundary(
    provider_boundaries: Mapping[str, AdmissibilityBoundary],
) -> AdmissibilityBoundary:
    """Compose frozen provider boundaries through the public G1 algebra."""
    if set(provider_boundaries) != set(PROVIDERS):
        raise ValueError("provider_boundaries must contain ProviderA/B/C")

    branch_latency = {
        provider: (
            float(provider_boundaries[provider].l_max)
            + float(G1_BRANCH_FIXED_LATENCY_SECONDS[provider])
        )
        for provider in PROVIDERS
    }
    return AdmissibilityBoundary(
        l_max=float(G1_FIXED_COMMON_LATENCY_SECONDS)
        + max(branch_latency.values()),
        c_max=0.03
        + sum(float(provider_boundaries[p].c_max) for p in PROVIDERS),
        q_min=min(float(provider_boundaries[p].q_min) for p in PROVIDERS),
    )
