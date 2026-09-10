"""Benchmark-specific deterministic boundary adapter for PRAISE Phase-3 M0.

This module instantiates the already-frozen generic M0 boundary algebra for the
frozen Phase-1 benchmark graph

    Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost.

Provider boundaries come from the public I1 cards.  Only deterministic benchmark
terms are added here:

* one Source->Fpre network hop;
* deterministic Fpre execution;
* one Fpre->Provider_i branch-network hop on each parallel branch;
* one composition-controller/Fpre->Fpost join-network hop;
* deterministic Fpost execution.

The network latency law is the exact law used by the AICon/YAFS fork employed by
Phase 1: ``message.bytes / (BW_mbps * 1e6) + PR`` per traversed link.  Network
terms add latency only.  Fpre/Fpost cost is ``COST * service_time`` and their QoS
is neutral.  No white-box sigma outcome enters this calculation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from m0_analytic_composition import AdmissibilityBoundary, compose_graph_boundary

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_GRAPH_GRAMMAR = "Fpre -> ParAll(A,B,C) -> Fpost"
TOLERANCE = 1e-12


@dataclass(frozen=True)
class Phase1G0BoundaryBreakdown:
    """Auditable deterministic components used to obtain the full M0 boundary."""

    root_network_latency: float
    pre_service_latency: float
    branch_network_latency: float
    join_network_latency: float
    post_service_latency: float
    pre_service_cost: float
    post_service_cost: float

    @property
    def fixed_latency_outside_provider(self) -> float:
        """Return fixed latency added to the slowest provider-local boundary."""
        return float(
            self.root_network_latency
            + self.pre_service_latency
            + self.branch_network_latency
            + self.join_network_latency
            + self.post_service_latency
        )

    @property
    def fixed_cost_outside_provider(self) -> float:
        """Return deterministic non-provider compute cost."""
        return float(self.pre_service_cost + self.post_service_cost)


def network_hop_latency(
    *,
    message_bytes: float,
    bandwidth_mbps: float,
    propagation: float,
) -> float:
    """Return the exact AICon/YAFS benchmark latency of one network hop."""
    size = float(message_bytes)
    bandwidth = float(bandwidth_mbps)
    propagation_delay = float(propagation)
    if size < 0.0:
        raise ValueError("message_bytes must be non-negative")
    if bandwidth <= 0.0:
        raise ValueError("bandwidth_mbps must be positive")
    if propagation_delay < 0.0:
        raise ValueError("propagation must be non-negative")
    return float(size / (bandwidth * 1_000_000.0) + propagation_delay)


def deterministic_service_boundary(
    *,
    instructions: float,
    effective_ipt: float,
    cost_rate: float,
) -> AdmissibilityBoundary:
    """Convert one deterministic QoS-neutral service into an LCQ boundary."""
    work = float(instructions)
    ipt = float(effective_ipt)
    rate = float(cost_rate)
    if work < 0.0:
        raise ValueError("instructions must be non-negative")
    if ipt <= 0.0:
        raise ValueError("effective_ipt must be positive")
    if rate < 0.0:
        raise ValueError("cost_rate must be non-negative")
    service = work / ipt
    return AdmissibilityBoundary(
        l_max=float(service),
        c_max=float(rate * service),
        q_min=1.0,
    )


def _network_boundary(latency: float) -> AdmissibilityBoundary:
    """Represent a deterministic QoS-neutral zero-cost network hop."""
    return AdmissibilityBoundary(l_max=float(latency), c_max=0.0, q_min=1.0)


def build_phase1_g0_full_m0_boundary(
    configuration: Mapping[str, object],
    provider_boundaries: Mapping[str, AdmissibilityBoundary],
) -> tuple[AdmissibilityBoundary, Phase1G0BoundaryBreakdown]:
    """Compose the full frozen Phase-1 G0 M0 boundary.

    ``provider_boundaries`` must contain exactly ProviderA/B/C.  The function
    validates the benchmark graph and reads all deterministic numerical terms
    from the frozen Phase-1 configuration rather than duplicating them as magic
    constants.
    """
    if set(provider_boundaries) != set(PROVIDERS):
        raise ValueError("provider_boundaries must contain exactly ProviderA/B/C")

    graph = configuration.get("graph")
    topology = configuration.get("topology")
    provider_family = configuration.get("provider_family")
    if not isinstance(graph, Mapping):
        raise ValueError("Phase-1 configuration lacks graph mapping")
    if not isinstance(topology, Mapping):
        raise ValueError("Phase-1 configuration lacks topology mapping")
    if not isinstance(provider_family, Mapping):
        raise ValueError("Phase-1 configuration lacks provider_family mapping")
    if str(graph.get("grammar")) != EXPECTED_GRAPH_GRAMMAR:
        raise ValueError("unexpected Phase-1 graph grammar for M0 benchmark adapter")

    effective_ipt = float(provider_family["effective_ipt"])
    cost_rate = float(provider_family["cost_rate"])
    pre = deterministic_service_boundary(
        instructions=float(graph["pre_instructions"]),
        effective_ipt=effective_ipt,
        cost_rate=cost_rate,
    )
    post = deterministic_service_boundary(
        instructions=float(graph["post_instructions"]),
        effective_ipt=effective_ipt,
        cost_rate=cost_rate,
    )

    bandwidth = float(topology["network_bw_mbps"])
    propagation = float(topology["network_pr"])
    root_network_latency = network_hop_latency(
        message_bytes=float(topology["request_bytes"]),
        bandwidth_mbps=bandwidth,
        propagation=propagation,
    )
    branch_network_latency = network_hop_latency(
        message_bytes=float(topology["branch_bytes"]),
        bandwidth_mbps=bandwidth,
        propagation=propagation,
    )
    join_network_latency = network_hop_latency(
        message_bytes=float(topology["join_bytes"]),
        bandwidth_mbps=bandwidth,
        propagation=propagation,
    )

    leaves: dict[str, AdmissibilityBoundary] = {
        "NetRoot": _network_boundary(root_network_latency),
        "Fpre": pre,
        "NetA": _network_boundary(branch_network_latency),
        "ProviderA": provider_boundaries["ProviderA"],
        "NetB": _network_boundary(branch_network_latency),
        "ProviderB": provider_boundaries["ProviderB"],
        "NetC": _network_boundary(branch_network_latency),
        "ProviderC": provider_boundaries["ProviderC"],
        "NetJoin": _network_boundary(join_network_latency),
        "Fpost": post,
    }
    benchmark_graph = {
        "type": "sequence",
        "children": [
            {"type": "leaf", "id": "NetRoot"},
            {"type": "leaf", "id": "Fpre"},
            {
                "type": "parallel_all",
                "children": [
                    {
                        "type": "sequence",
                        "children": [
                            {"type": "leaf", "id": "NetA"},
                            {"type": "leaf", "id": "ProviderA"},
                        ],
                    },
                    {
                        "type": "sequence",
                        "children": [
                            {"type": "leaf", "id": "NetB"},
                            {"type": "leaf", "id": "ProviderB"},
                        ],
                    },
                    {
                        "type": "sequence",
                        "children": [
                            {"type": "leaf", "id": "NetC"},
                            {"type": "leaf", "id": "ProviderC"},
                        ],
                    },
                ],
            },
            {"type": "leaf", "id": "NetJoin"},
            {"type": "leaf", "id": "Fpost"},
        ],
    }
    induced = compose_graph_boundary(benchmark_graph, leaves)
    breakdown = Phase1G0BoundaryBreakdown(
        root_network_latency=root_network_latency,
        pre_service_latency=pre.l_max,
        branch_network_latency=branch_network_latency,
        join_network_latency=join_network_latency,
        post_service_latency=post.l_max,
        pre_service_cost=pre.c_max,
        post_service_cost=post.c_max,
    )

    expected_latency = (
        breakdown.fixed_latency_outside_provider
        + max(boundary.l_max for boundary in provider_boundaries.values())
    )
    expected_cost = (
        breakdown.fixed_cost_outside_provider
        + sum(boundary.c_max for boundary in provider_boundaries.values())
    )
    expected_quality = min(boundary.q_min for boundary in provider_boundaries.values())
    if abs(induced.l_max - expected_latency) > TOLERANCE:
        raise RuntimeError("Phase-1 M0 graph adapter latency algebra mismatch")
    if abs(induced.c_max - expected_cost) > TOLERANCE:
        raise RuntimeError("Phase-1 M0 graph adapter cost algebra mismatch")
    if abs(induced.q_min - expected_quality) > TOLERANCE:
        raise RuntimeError("Phase-1 M0 graph adapter quality algebra mismatch")

    return induced, breakdown
