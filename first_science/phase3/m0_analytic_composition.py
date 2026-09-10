"""Topology-aware analytic M0 composition for PRAISE Phase 3.

M0 consumes already-fixed public I1 provider cards and a known composition graph.
It does not reconstruct hidden provider distributions and it never derives or
changes provider-local admissibility regions A_i.

The structural contract implemented here has two layers:

1. Forward boundary algebra. Fixed local rectangular LCQ boundaries are composed
   recursively through the public graph. For the currently supported operators:

       sequence:     L=sum, C=sum, Q=min
       parallel_all: L=max, C=sum, Q=min

   The resulting boundary A_G^M0 is a sufficient global boundary induced by the
   fixed local cards and deterministic graph terms. It can certify an exogenous
   global query A_G only when A_G^M0 is contained in A_G.

2. Probability certification for the deliberately independent all-required
   anchor. The global violation budget epsilon_G=1-rho_G is split equally over
   the m required stochastic providers, rho_i=1-epsilon_G/m. When the local and
   global cumulative accounting populations are aligned, the local violation
   sets imply the global rho_G requirement by a union-of-violations argument.
   Under independence of the required local trajectory-level events, the
   certificate probability is the product of the corresponding I1 sigma values.

If any hard precondition is not established, M0 returns NOT_CERTIFIED rather
than manufacturing a point estimate. This is an I1/M0 limitation and must not
reopen Phase 2.
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
class M0CertificateResult:
    """Result of applying the frozen M0 certificate preconditions."""

    status: str
    sigma_lower: float | None
    induced_global_boundary: AdmissibilityBoundary
    requested_global_boundary: AdmissibilityBoundary
    rho_global: float
    rho_local: Mapping[str, float]
    failed_preconditions: tuple[str, ...]

    @property
    def certified(self) -> bool:
        return self.status == "CERTIFIED"


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

    Graph schema
    ------------
    A leaf is ``{"type": "leaf", "id": "ProviderA"}``.
    An internal node is
    ``{"type": "sequence"|"parallel_all", "children": [...]}``.

    Deterministic stages and network terms are represented as ordinary leaves
    with deterministic LCQ boundaries. This keeps the algebra explicit and
    avoids benchmark-specific constants inside M0.
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
    """Return whether the induced sufficient boundary is contained in A_G.

    For rectangular LCQ sets this is exactly
    ``l_induced <= l_requested``, ``c_induced <= c_requested`` and
    ``q_induced >= q_requested``.
    """
    tol = float(tolerance)
    return bool(
        induced_boundary.l_max <= requested_boundary.l_max + tol
        and induced_boundary.c_max <= requested_boundary.c_max + tol
        and induced_boundary.q_min + tol >= requested_boundary.q_min
    )


def equal_violation_budget_rhos(
    rho_global: float,
    required_provider_ids: Sequence[str],
) -> dict[str, float]:
    """Allocate the global cumulative violation budget equally across providers.

    With rho_G=0.95 and three required stochastic providers this returns
    rho_i=0.9833333333333333, which is already present in the frozen I1 support.
    """
    rho_g = float(rho_global)
    if not 0.0 < rho_g <= 1.0:
        raise ValueError("rho_global must lie in (0,1]")
    provider_ids = tuple(str(provider).strip() for provider in required_provider_ids)
    if not provider_ids or any(not provider for provider in provider_ids):
        raise ValueError("at least one non-empty required provider id is required")
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("required provider ids must be unique")

    epsilon_global = 1.0 - rho_g
    epsilon_local = epsilon_global / len(provider_ids)
    rho_local = 1.0 - epsilon_local
    return {provider: float(rho_local) for provider in provider_ids}


def independent_product_probability(
    provider_sigma: Mapping[str, float],
) -> float:
    """Multiply required local-event probabilities for the independent anchor."""
    if not provider_sigma:
        raise ValueError("at least one provider sigma is required")
    probabilities = []
    for provider, sigma in provider_sigma.items():
        probability = float(sigma)
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"sigma for {provider} must lie in [0,1]")
        probabilities.append(probability)
    return float(prod(probabilities))


def evaluate_independent_m0_certificate(
    *,
    induced_global_boundary: AdmissibilityBoundary,
    requested_global_boundary: AdmissibilityBoundary,
    rho_global: float,
    provider_sigma: Mapping[str, float],
    accounting_aligned: bool,
    independent_local_events: bool,
    card_points_available: bool,
) -> M0CertificateResult:
    """Apply the frozen M0 certificate rule without silently relaxing failures.

    ``provider_sigma`` must contain the I1 sigma point for every required
    stochastic provider at the rho_i returned by the frozen equal-budget rule
    and at the common evaluated horizon H. This function intentionally does not
    interpolate card points or inspect private evidence.
    """
    provider_ids = tuple(provider_sigma.keys())
    rho_local = equal_violation_budget_rhos(rho_global, provider_ids)

    failed: list[str] = []
    if not boundary_is_sufficient_for_query(
        induced_global_boundary, requested_global_boundary
    ):
        failed.append("induced_boundary_not_contained_in_requested_A_G")
    if not bool(accounting_aligned):
        failed.append("local_global_request_accounting_not_aligned")
    if not bool(independent_local_events):
        failed.append("required_local_events_not_established_independent")
    if not bool(card_points_available):
        failed.append("required_I1_H_rho_points_not_available")

    if failed:
        return M0CertificateResult(
            status="NOT_CERTIFIED",
            sigma_lower=None,
            induced_global_boundary=induced_global_boundary,
            requested_global_boundary=requested_global_boundary,
            rho_global=float(rho_global),
            rho_local=rho_local,
            failed_preconditions=tuple(failed),
        )

    sigma_lower = independent_product_probability(provider_sigma)
    return M0CertificateResult(
        status="CERTIFIED",
        sigma_lower=sigma_lower,
        induced_global_boundary=induced_global_boundary,
        requested_global_boundary=requested_global_boundary,
        rho_global=float(rho_global),
        rho_local=rho_local,
        failed_preconditions=(),
    )
