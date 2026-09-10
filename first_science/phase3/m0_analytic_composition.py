"""Topology-aware analytic M0 baseline for PRAISE Phase 3.

M0 consumes already-fixed public I1 provider cards and a known composition graph.
It never reconstructs hidden provider distributions and it never derives or
changes provider-local admissibility regions A_i.

The frozen baseline has two layers:

1. Forward boundary algebra. Fixed local rectangular LCQ boundaries are composed
   recursively through the public graph. For the currently supported operators:

       sequence:     L=sum, C=sum, Q=min
       parallel_all: L=max, C=sum, Q=min

   The resulting boundary A_G^M0 is compared with the exogenous requested A_G.
   M0 is applicable only when the induced boundary is contained in A_G.

2. Same-rho probability composition. For every required stochastic provider,
   M0 reads the I1 card at exactly rho_i=rho_G. Under its deliberately simple
   independence model, it multiplies the corresponding local sigma values:

       sigma_hat_G,M0(H;rho_G) = product_i sigma_i(A_i,H;rho_G).

This is intentionally a baseline prediction, not a guaranteed lower bound or
certificate for the global rho_G query. In particular, c_i>=rho_G for every
provider does not generally imply c_G>=rho_G. M0 does not compensate for that
limitation by redistributing the global violation budget. The resulting error
is part of what the benchmark is designed to measure.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Mapping, Sequence

TOLERANCE = 1e-12


@dataclass(frozen=True)
class AdmissibilityBoundary:
    """Rectangular latency/cost/quality admissibility boundary.

    The represented set is ``L <= l_max, C <= c_max, Q >= q_min``.
    """

    l_max: float
    c_max: float
    q_min: float

    def __post_init__(self) -> None:
        if self.l_max < 0.0 or self.c_max < 0.0:
            raise ValueError("latency and cost bounds must be non-negative")


@dataclass(frozen=True)
class M0PredictionResult:
    """Result of applying the frozen M0 same-rho baseline."""

    status: str
    sigma_hat: float | None
    induced_global_boundary: AdmissibilityBoundary
    requested_global_boundary: AdmissibilityBoundary
    rho_global: float
    rho_local: Mapping[str, float]
    failed_preconditions: tuple[str, ...]

    @property
    def predicted(self) -> bool:
        return self.status == "PREDICTED"


def compose_sequence(
    child_boundaries: Sequence[AdmissibilityBoundary],
) -> AdmissibilityBoundary:
    """Compose required sequential children: L=sum, C=sum, Q=min."""
    children = tuple(child_boundaries)
    if not children:
        raise ValueError("sequence requires at least one child")
    return AdmissibilityBoundary(
        l_max=float(sum(child.l_max for child in children)),
        c_max=float(sum(child.c_max for child in children)),
        q_min=float(min(child.q_min for child in children)),
    )


def compose_parallel_all(
    child_boundaries: Sequence[AdmissibilityBoundary],
) -> AdmissibilityBoundary:
    """Compose all-required parallel children: L=max, C=sum, Q=min."""
    children = tuple(child_boundaries)
    if not children:
        raise ValueError("parallel_all requires at least one child")
    return AdmissibilityBoundary(
        l_max=float(max(child.l_max for child in children)),
        c_max=float(sum(child.c_max for child in children)),
        q_min=float(min(child.q_min for child in children)),
    )


def compose_graph_boundary(
    graph_node: Mapping[str, object],
    leaf_boundaries: Mapping[str, AdmissibilityBoundary],
) -> AdmissibilityBoundary:
    """Recursively compose a graph built from leaf, sequence and parallel_all.

    A leaf is ``{"type": "leaf", "id": "ProviderA"}``.
    An internal node is
    ``{"type": "sequence"|"parallel_all", "children": [...]}``.

    Deterministic stages and network terms are represented as ordinary leaves
    with deterministic LCQ boundaries so the algebra remains explicit.
    """
    node_type = str(graph_node.get("type", ""))
    if node_type == "leaf":
        leaf_id = str(graph_node.get("id", ""))
        if not leaf_id:
            raise ValueError("leaf node requires a non-empty id")
        if leaf_id not in leaf_boundaries:
            raise KeyError(f"no boundary supplied for leaf {leaf_id}")
        return leaf_boundaries[leaf_id]

    children_object = graph_node.get("children")
    if not isinstance(children_object, list) or not children_object:
        raise ValueError(f"{node_type or 'graph node'} requires non-empty children")
    child_boundaries = [
        compose_graph_boundary(child, leaf_boundaries)
        for child in children_object
        if isinstance(child, Mapping)
    ]
    if len(child_boundaries) != len(children_object):
        raise ValueError("every graph child must be a mapping node")

    if node_type == "sequence":
        return compose_sequence(child_boundaries)
    if node_type == "parallel_all":
        return compose_parallel_all(child_boundaries)
    raise ValueError(f"unsupported M0 graph operator: {node_type!r}")


def boundary_is_sufficient_for_query(
    induced_boundary: AdmissibilityBoundary,
    requested_boundary: AdmissibilityBoundary,
    tolerance: float = TOLERANCE,
) -> bool:
    """Return whether the induced LCQ boundary is contained in requested A_G."""
    tol = float(tolerance)
    return bool(
        induced_boundary.l_max <= requested_boundary.l_max + tol
        and induced_boundary.c_max <= requested_boundary.c_max + tol
        and induced_boundary.q_min + tol >= requested_boundary.q_min
    )


def same_rho_as_global(
    rho_global: float,
    required_provider_ids: Sequence[str],
) -> dict[str, float]:
    """Return the frozen M0 policy ``rho_i = rho_G`` for every provider."""
    rho_g = float(rho_global)
    if not 0.0 < rho_g <= 1.0:
        raise ValueError("rho_global must lie in (0,1]")

    provider_ids = tuple(str(provider).strip() for provider in required_provider_ids)
    if not provider_ids or any(not provider for provider in provider_ids):
        raise ValueError("at least one non-empty required provider id is required")
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("required provider ids must be unique")

    return {provider: rho_g for provider in provider_ids}


def independent_product_probability(
    provider_sigma: Mapping[str, float],
) -> float:
    """Multiply required local sigma values under M0's independence model."""
    if not provider_sigma:
        raise ValueError("at least one provider sigma is required")
    probabilities = []
    for provider, sigma in provider_sigma.items():
        probability = float(sigma)
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"sigma for {provider} must lie in [0,1]")
        probabilities.append(probability)
    return float(prod(probabilities))


def evaluate_independent_m0_prediction(
    *,
    induced_global_boundary: AdmissibilityBoundary,
    requested_global_boundary: AdmissibilityBoundary,
    rho_global: float,
    provider_sigma: Mapping[str, float],
    card_points_available: bool,
) -> M0PredictionResult:
    """Apply the frozen same-rho M0 baseline.

    ``provider_sigma`` contains, for each required stochastic provider, the I1
    value ``sigma_i(A_i,H;rho_global)`` at the common evaluated horizon H.

    M0 deliberately does not tighten or redistribute ``rho_global``. Therefore
    the returned product is ``sigma_hat``, a baseline prediction, not a lower
    bound or certificate for the global query.
    """
    provider_ids = tuple(provider_sigma.keys())
    rho_local = same_rho_as_global(rho_global, provider_ids)

    failed: list[str] = []
    if not boundary_is_sufficient_for_query(
        induced_global_boundary, requested_global_boundary
    ):
        failed.append("induced_boundary_not_contained_in_requested_A_G")
    if not bool(card_points_available):
        failed.append("required_I1_H_rho_points_not_available")

    if failed:
        return M0PredictionResult(
            status="NOT_APPLICABLE",
            sigma_hat=None,
            induced_global_boundary=induced_global_boundary,
            requested_global_boundary=requested_global_boundary,
            rho_global=float(rho_global),
            rho_local=rho_local,
            failed_preconditions=tuple(failed),
        )

    return M0PredictionResult(
        status="PREDICTED",
        sigma_hat=independent_product_probability(provider_sigma),
        induced_global_boundary=induced_global_boundary,
        requested_global_boundary=requested_global_boundary,
        rho_global=float(rho_global),
        rho_local=rho_local,
        failed_preconditions=(),
    )
