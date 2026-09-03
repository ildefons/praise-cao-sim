"""Topology-aware M0 SLA contract composition for PRAISE Phase 2.

M0 consumes I1 provider cards and the public graph/topology contract. It does
not reconstruct provider distributions or inspect hidden Phase-1 provider
parameters. For the frozen first anchor

    Fpre -> ParAll(A,B,C) -> Fpost

M0 performs two distinct decompositions:

1. global L/C/Q admissibility boundary -> sufficient provider-local boundaries;
2. global cumulative request-violation budget -> local rho_i requirements.

The probability composition for the deliberately independent anchor is the
product of the corresponding I1 local SLA-compliance probabilities.

Important: the trajectory-level counting certificate assumes that the local and
global cumulative fractions refer to the same aligned set of logical root
requests. The pure counting helper below makes that precondition explicit. The
real Phase-2 anchor must audit this alignment before the product curve is called
a formal lower-bound certificate under decision-time horizon accounting.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
M0_METHOD_ID = "M0_TOPOLOGY_AWARE_SLA_CERTIFICATION_V1"
EVENT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class GlobalAdmissibilityRegion:
    """Top-level joint SLA boundary for the composed offering."""

    region_id: str
    l_max: float
    c_max: float
    q_min: float
    rho_global: float = 0.95


@dataclass(frozen=True)
class Phase1FixedBoundaryContext:
    """Known deterministic/public boundary terms surrounding ParAll(A,B,C).

    ``latency_common`` excludes provider-branch ingress links. Hence the exact
    no-post-queue algebra is

        L_G = latency_common + max_i(branch_network_latency_i + L_i).

    ``fixed_execution_cost`` contains only deterministic Fpre/Fpost execution
    cost. Network communication is not charged by the frozen request-cost rule.
    """

    latency_common: float
    branch_network_latency: tuple[float, float, float]
    fixed_execution_cost: float
    fixed_quality_floor: float
    pre_service_time: float
    post_service_time: float
    root_network_latency: float
    join_network_latency: float


@dataclass(frozen=True)
class LocalProviderBoundary:
    """One provider-local I1 query boundary induced by M0."""

    provider_id: str
    global_region_id: str
    l_max: float
    c_max: float
    q_min: float
    epsilon_local: float
    rho_local: float


def yafs_single_link_latency(message_bytes: float, bandwidth_mbps: float, propagation: float) -> float:
    """Return the latency used by the current AICon/YAFS network implementation.

    Current YAFS computes transmission as ``message.bytes / (BW * 1e6)`` and
    adds link propagation ``PR``.
    """
    size = float(message_bytes)
    bandwidth = float(bandwidth_mbps)
    pr = float(propagation)
    if size < 0.0 or bandwidth <= 0.0 or pr < 0.0:
        raise ValueError("invalid network parameters")
    return size / (bandwidth * 1_000_000.0) + pr


def derive_phase1_fixed_boundary_context(configuration: Mapping[str, object]) -> Phase1FixedBoundaryContext:
    """Derive deterministic boundary terms from the frozen public Phase-1 config.

    This function uses only graph/topology/runtime parameters that define the
    public composition context; it does not use provider Dbar/delta, Gamma CV,
    provider traces, or any white-box sigma values.
    """
    graph = configuration["graph"]
    topology = configuration["topology"]
    provider_family = configuration["provider_family"]

    ipt = float(provider_family["effective_ipt"])
    cost_rate = float(provider_family["cost_rate"])
    if ipt <= 0.0 or cost_rate < 0.0:
        raise ValueError("invalid public IPT/COST values")

    pre_service = float(graph["pre_instructions"]) / ipt
    post_service = float(graph["post_instructions"]) / ipt

    bw = float(topology["network_bw_mbps"])
    pr = float(topology["network_pr"])
    root_network = yafs_single_link_latency(topology["request_bytes"], bw, pr)
    branch_network = yafs_single_link_latency(topology["branch_bytes"], bw, pr)
    join_network = yafs_single_link_latency(topology["join_bytes"], bw, pr)

    # Root link + Fpre service + join link + Fpost service are common to every
    # branch. The identical Fpre->provider ingress link is retained branch-wise
    # so the formula also generalizes cleanly to asymmetric public links later.
    latency_common = root_network + pre_service + join_network + post_service
    fixed_cost = cost_rate * (pre_service + post_service)

    return Phase1FixedBoundaryContext(
        latency_common=float(latency_common),
        branch_network_latency=(float(branch_network),) * 3,
        fixed_execution_cost=float(fixed_cost),
        fixed_quality_floor=1.0,
        pre_service_time=float(pre_service),
        post_service_time=float(post_service),
        root_network_latency=float(root_network),
        join_network_latency=float(join_network),
    )


def validate_global_region(region: GlobalAdmissibilityRegion) -> None:
    if not str(region.region_id):
        raise ValueError("global region_id must be non-empty")
    if region.l_max < 0.0 or region.c_max < 0.0:
        raise ValueError("global L/C thresholds must be non-negative")
    if not 0.0 < region.rho_global <= 1.0:
        raise ValueError("global rho must satisfy 0 < rho <= 1")


def equal_error_budget_rho(rho_global: float, n_providers: int = 3) -> tuple[float, float]:
    """Return (epsilon_i, rho_i) for the frozen first M0 equal split."""
    rho = float(rho_global)
    m = int(n_providers)
    if not 0.0 < rho <= 1.0 or m <= 0:
        raise ValueError("invalid global rho/provider count")
    epsilon_i = (1.0 - rho) / m
    return float(epsilon_i), float(1.0 - epsilon_i)


def decompose_global_region_equal_m0(
    region: GlobalAdmissibilityRegion,
    context: Phase1FixedBoundaryContext,
    providers: Sequence[str] = PROVIDERS,
) -> list[LocalProviderBoundary]:
    """Map one global AR to sufficient local ARs for the first M0 pilot.

    Latency uses the ParAll maximum rule, so every branch receives the complete
    residual latency after subtracting known common and branch-ingress terms.
    Cost is additive, so the first low-information symmetric policy splits the
    residual execution-cost budget equally across the required providers.
    Quality uses weakest-link/minimum semantics, so each provider must meet the
    global q_min when the deterministic fixed stages are quality-neutral.

    This is a transparent topology-only decomposition. It deliberately does not
    use provider-specific hidden means to favor one branch over another.
    """
    validate_global_region(region)
    provider_ids = tuple(map(str, providers))
    if len(provider_ids) != len(context.branch_network_latency):
        raise ValueError("provider count must match branch-network terms")
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("provider identifiers must be unique")
    if context.fixed_quality_floor + EVENT_TOLERANCE < float(region.q_min):
        raise ValueError("deterministic fixed stages cannot satisfy global quality threshold")

    residual_cost = float(region.c_max) - float(context.fixed_execution_cost)
    if residual_cost < -EVENT_TOLERANCE:
        raise ValueError("global cost budget is smaller than deterministic fixed cost")
    residual_cost = max(0.0, residual_cost)
    local_cost = residual_cost / len(provider_ids)

    epsilon_i, rho_i = equal_error_budget_rho(region.rho_global, len(provider_ids))
    local_boundaries: list[LocalProviderBoundary] = []
    for provider_id, branch_network in zip(provider_ids, context.branch_network_latency):
        local_latency = (
            float(region.l_max)
            - float(context.latency_common)
            - float(branch_network)
        )
        if local_latency < -EVENT_TOLERANCE:
            raise ValueError(
                f"global latency budget leaves negative residual for {provider_id}"
            )
        local_boundaries.append(
            LocalProviderBoundary(
                provider_id=provider_id,
                global_region_id=str(region.region_id),
                l_max=max(0.0, float(local_latency)),
                c_max=float(local_cost),
                q_min=float(region.q_min),
                epsilon_local=float(epsilon_i),
                rho_local=float(rho_i),
            )
        )
    return local_boundaries


def compose_phase1_boundary_from_local_metrics(
    local_latency: Mapping[str, float],
    local_cost: Mapping[str, float],
    local_quality: Mapping[str, float],
    context: Phase1FixedBoundaryContext,
    providers: Sequence[str] = PROVIDERS,
) -> tuple[float, float, float]:
    """Compose one aligned root request using the M0 L/C/Q boundary algebra.

    This algebra assumes no additional stochastic queueing contribution in the
    deterministic Fpost stage beyond its declared service time. The real anchor
    audit must check that assumption before claiming exact request-level
    certification for latency.
    """
    provider_ids = tuple(map(str, providers))
    for mapping, label in (
        (local_latency, "latency"),
        (local_cost, "cost"),
        (local_quality, "quality"),
    ):
        missing = set(provider_ids).difference(mapping)
        if missing:
            raise ValueError(f"local {label} missing providers: {sorted(missing)}")

    branch_terms = [
        float(context.branch_network_latency[index]) + float(local_latency[provider])
        for index, provider in enumerate(provider_ids)
    ]
    global_latency = float(context.latency_common) + max(branch_terms)
    global_cost = float(context.fixed_execution_cost) + sum(
        float(local_cost[provider]) for provider in provider_ids
    )
    global_quality = min(
        [float(context.fixed_quality_floor)]
        + [float(local_quality[provider]) for provider in provider_ids]
    )
    return float(global_latency), float(global_cost), float(global_quality)


def local_boundaries_to_frame(boundaries: Iterable[LocalProviderBoundary]) -> pd.DataFrame:
    rows = [boundary.__dict__.copy() for boundary in boundaries]
    if not rows:
        raise ValueError("at least one local boundary is required")
    return pd.DataFrame(rows).sort_values("provider_id").reset_index(drop=True)


def verify_request_level_sufficient_condition(
    region: GlobalAdmissibilityRegion,
    boundaries: Sequence[LocalProviderBoundary],
    context: Phase1FixedBoundaryContext,
    local_latency: Mapping[str, float],
    local_cost: Mapping[str, float],
    local_quality: Mapping[str, float],
) -> bool:
    """Check the deterministic implication local conjunction => global A_G."""
    by_provider = {boundary.provider_id: boundary for boundary in boundaries}
    local_pass = all(
        float(local_latency[provider]) <= by_provider[provider].l_max + EVENT_TOLERANCE
        and float(local_cost[provider]) <= by_provider[provider].c_max + EVENT_TOLERANCE
        and float(local_quality[provider]) + EVENT_TOLERANCE >= by_provider[provider].q_min
        for provider in by_provider
    )
    if not local_pass:
        return True  # implication is vacuously true
    global_l, global_c, global_q = compose_phase1_boundary_from_local_metrics(
        local_latency, local_cost, local_quality, context, tuple(by_provider)
    )
    return bool(
        global_l <= float(region.l_max) + EVENT_TOLERANCE
        and global_c <= float(region.c_max) + EVENT_TOLERANCE
        and global_q + EVENT_TOLERANCE >= float(region.q_min)
    )


def aligned_request_counting_certificate(
    local_request_pass: Mapping[str, Sequence[bool]],
    rho_global: float,
    rho_local: Mapping[str, float],
) -> dict[str, object]:
    """Apply the deterministic SLA counting argument on one aligned request set.

    Every provider vector must refer to exactly the same ordered logical root
    requests. The sufficient global request-pass event is the conjunction of all
    local pass flags. If every provider's local violation fraction is at most its
    epsilon_i and sum epsilon_i <= epsilon_G, the conjunction fraction is at
    least rho_G by a counting/union-bound argument.
    """
    providers = tuple(local_request_pass)
    if not providers:
        raise ValueError("at least one provider is required")
    if set(providers) != set(rho_local):
        raise ValueError("rho_local keys must exactly match provider pass vectors")
    lengths = {len(local_request_pass[p]) for p in providers}
    if len(lengths) != 1 or next(iter(lengths)) <= 0:
        raise ValueError("all provider pass vectors must be non-empty and aligned")

    matrix = np.column_stack(
        [np.asarray(local_request_pass[p], dtype=bool) for p in providers]
    )
    local_fraction = {
        p: float(np.mean(matrix[:, index])) for index, p in enumerate(providers)
    }
    conjunction = np.all(matrix, axis=1)
    global_sufficient_fraction = float(np.mean(conjunction))
    epsilon_sum = float(sum(1.0 - float(rho_local[p]) for p in providers))
    epsilon_global = 1.0 - float(rho_global)
    local_slas_hold = all(
        local_fraction[p] + EVENT_TOLERANCE >= float(rho_local[p]) for p in providers
    )
    budget_valid = epsilon_sum <= epsilon_global + EVENT_TOLERANCE
    certified = bool(
        local_slas_hold
        and budget_valid
        and global_sufficient_fraction + EVENT_TOLERANCE >= float(rho_global)
    )
    return {
        "n_aligned_requests": int(matrix.shape[0]),
        "local_compliance_fraction": local_fraction,
        "global_sufficient_conjunction_fraction": global_sufficient_fraction,
        "rho_global": float(rho_global),
        "epsilon_sum": epsilon_sum,
        "epsilon_global": epsilon_global,
        "local_slas_hold": bool(local_slas_hold),
        "budget_valid": bool(budget_valid),
        "certified": certified,
    }


def compose_independent_i1_probabilities(
    local_sigma: Mapping[str, float],
    providers: Sequence[str] = PROVIDERS,
) -> float:
    """Return the independent-anchor M0 probability product.

    This product is a certificate for the conjunction event only when the local
    SLA events are independent and the request-level sufficient-condition and
    aligned-accounting preconditions hold.
    """
    provider_ids = tuple(map(str, providers))
    if set(local_sigma) != set(provider_ids):
        raise ValueError("local sigma keys must exactly match required providers")
    values = [float(local_sigma[p]) for p in provider_ids]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("local sigma values must lie in [0,1]")
    return float(reduce(mul, values, 1.0))


def compose_i1_surface_independent_m0(
    provider_surfaces: Mapping[str, pd.DataFrame],
    boundaries: Sequence[LocalProviderBoundary],
) -> pd.DataFrame:
    """Compose exact I1 card points into an M0 curve on their common horizons.

    The surfaces must already be restricted to the exact boundary/rho associated
    with one global diagnostic region. No interpolation is performed here.
    """
    by_provider = {boundary.provider_id: boundary for boundary in boundaries}
    if set(provider_surfaces) != set(by_provider):
        raise ValueError("provider surfaces must match local boundaries")

    frames: list[pd.DataFrame] = []
    for provider, surface in provider_surfaces.items():
        boundary = by_provider[provider]
        required = {"l_max", "c_max", "q_min", "rho", "horizon", "sigma_hat"}
        missing = required.difference(surface.columns)
        if missing:
            raise ValueError(f"{provider} I1 surface missing {sorted(missing)}")
        mask = (
            np.isclose(surface["l_max"].astype(float), boundary.l_max, atol=1e-10, rtol=0.0)
            & np.isclose(surface["c_max"].astype(float), boundary.c_max, atol=1e-10, rtol=0.0)
            & np.isclose(surface["q_min"].astype(float), boundary.q_min, atol=1e-10, rtol=0.0)
            & np.isclose(surface["rho"].astype(float), boundary.rho_local, atol=1e-10, rtol=0.0)
        )
        selected = surface.loc[mask, ["horizon", "sigma_hat"]].copy()
        if selected.empty:
            raise KeyError(f"{provider} card does not contain required M0 boundary/rho")
        if selected["horizon"].duplicated().any():
            raise ValueError(f"{provider} I1 surface has duplicate horizons")
        selected = selected.rename(columns={"sigma_hat": f"sigma_{provider}"})
        frames.append(selected)

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="horizon", how="inner", validate="one_to_one")
    if merged.empty:
        raise ValueError("provider I1 surfaces have no common horizons")

    sigma_columns = [f"sigma_{provider}" for provider in by_provider]
    merged["sigma_m0_independent_product"] = merged[sigma_columns].prod(axis=1)
    merged["m0_method"] = M0_METHOD_ID
    merged["global_region_id"] = boundaries[0].global_region_id
    return merged.sort_values("horizon").reset_index(drop=True)
