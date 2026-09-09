"""Phase-3A structural query decomposition for M0.

This module deliberately stops before I1 sigma lookup or probability composition.
It consumes only the frozen Phase-1 v2 global admissibility regions and public
composition constants, then derives exact provider-local A_i and rho_i queries.

The real benchmark's provider-local and top-level decision-time subsets at the
same horizon are not assumed aligned here. The aligned counting helper requires
explicit identical logical-root identifiers and therefore cannot silently turn
that unresolved runtime condition into a theorem.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence


EVENT_TOLERANCE = 1e-12
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_PHASE1_V2_STATUS = "FROZEN_PHASE1_V2_AR_SELECTION_V1"
EXPECTED_PHASE2_I1_STATUS = "FROZEN_PHASE2_I1_V1"
EXPECTED_PHASE3A_STATUS = "DRAFT_PHASE3A_M0_STRUCTURAL_CONTRACT_V1"


@dataclass(frozen=True)
class GlobalAdmissibilityQuery:
    case_id: str
    selection_role: str
    region_id: str
    l_max: float
    c_max: float
    q_min: float
    rho_global: float


@dataclass(frozen=True)
class PublicBoundaryContext:
    latency_common: float
    branch_network_latency: tuple[float, ...]
    fixed_execution_cost: float
    fixed_quality_floor: float
    pre_service_time: float
    post_service_time: float
    root_network_latency: float
    join_network_latency: float


@dataclass(frozen=True)
class LocalAdmissibilityQuery:
    provider_id: str
    global_case_id: str
    global_region_id: str
    l_max: float
    c_max: float
    q_min: float
    epsilon_local: float
    rho_local: float


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def yafs_single_link_latency(message_bytes: float, bandwidth_mbps: float, propagation: float) -> float:
    """Return the frozen public YAFS single-link latency expression."""
    size = float(message_bytes)
    bandwidth = float(bandwidth_mbps)
    pr = float(propagation)
    if size < 0.0 or bandwidth <= 0.0 or pr < 0.0:
        raise ValueError("invalid public network parameters")
    return size / (bandwidth * 1_000_000.0) + pr


def derive_public_boundary_context(configuration: Mapping[str, object]) -> PublicBoundaryContext:
    """Derive only deterministic/public graph-boundary terms used by M0."""
    graph = configuration["graph"]
    topology = configuration["topology"]
    provider_family = configuration["provider_family"]

    ipt = float(provider_family["effective_ipt"])
    cost_rate = float(provider_family["cost_rate"])
    if ipt <= 0.0 or cost_rate < 0.0:
        raise ValueError("invalid public IPT/COST values")

    pre_service = float(graph["pre_instructions"]) / ipt
    post_service = float(graph["post_instructions"]) / ipt
    bandwidth = float(topology["network_bw_mbps"])
    propagation = float(topology["network_pr"])
    root_network = yafs_single_link_latency(topology["request_bytes"], bandwidth, propagation)
    branch_network = yafs_single_link_latency(topology["branch_bytes"], bandwidth, propagation)
    join_network = yafs_single_link_latency(topology["join_bytes"], bandwidth, propagation)

    # Public structural model under audit. Any extra stochastic Fpost queue wait
    # is intentionally not hidden in this value and must be handled by the later
    # runtime alignment/boundary audit before formal certification claims.
    latency_common = root_network + pre_service + join_network + post_service
    fixed_cost = cost_rate * (pre_service + post_service)
    return PublicBoundaryContext(
        latency_common=float(latency_common),
        branch_network_latency=(float(branch_network),) * len(PROVIDERS),
        fixed_execution_cost=float(fixed_cost),
        fixed_quality_floor=1.0,
        pre_service_time=float(pre_service),
        post_service_time=float(post_service),
        root_network_latency=float(root_network),
        join_network_latency=float(join_network),
    )


def load_frozen_global_queries(manifest: Mapping[str, object]) -> list[GlobalAdmissibilityQuery]:
    """Extract only the exogenous A_G/rho_G fields allowed to Phase 3A."""
    if manifest.get("status") != EXPECTED_PHASE1_V2_STATUS:
        raise ValueError("Phase-1 v2 AR manifest is not frozen")
    whiteboxes = manifest.get("whiteboxes")
    if not isinstance(whiteboxes, list) or len(whiteboxes) != 3:
        raise ValueError("Phase 3A requires exactly three frozen global regions")

    queries = [
        GlobalAdmissibilityQuery(
            case_id=str(item["case_id"]),
            selection_role=str(item["selection_role"]),
            region_id=str(item["region_id"]),
            l_max=float(item["l_max"]),
            c_max=float(item["c_max"]),
            q_min=float(item["q_min"]),
            rho_global=float(item["rho"]),
        )
        for item in whiteboxes
    ]
    expected_roles = {"latency", "cost", "mixed"}
    if {q.selection_role for q in queries} != expected_roles:
        raise ValueError("frozen global queries must contain latency/cost/mixed roles")
    return sorted(queries, key=lambda q: q.selection_role)


def equal_violation_budget(rho_global: float, n_providers: int) -> tuple[float, float]:
    rho = float(rho_global)
    n = int(n_providers)
    if not 0.0 < rho <= 1.0 or n <= 0:
        raise ValueError("invalid global rho/provider count")
    epsilon_local = (1.0 - rho) / n
    return float(epsilon_local), float(1.0 - epsilon_local)


def decompose_global_query_equal_m0(
    query: GlobalAdmissibilityQuery,
    context: PublicBoundaryContext,
    providers: Sequence[str] = PROVIDERS,
) -> list[LocalAdmissibilityQuery]:
    """Derive the transparent equal-budget M0 local structural queries."""
    provider_ids = tuple(map(str, providers))
    if len(provider_ids) != len(context.branch_network_latency):
        raise ValueError("provider count does not match public branch terms")
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("provider identifiers must be unique")
    if query.l_max < 0.0 or query.c_max < 0.0 or not 0.0 < query.rho_global <= 1.0:
        raise ValueError("invalid global admissibility query")
    if context.fixed_quality_floor + EVENT_TOLERANCE < query.q_min:
        raise ValueError("fixed stages cannot satisfy the global quality threshold")

    residual_cost = query.c_max - context.fixed_execution_cost
    if residual_cost < -EVENT_TOLERANCE:
        raise ValueError("global cost threshold is below deterministic fixed cost")
    local_cost = max(0.0, residual_cost) / len(provider_ids)
    epsilon_local, rho_local = equal_violation_budget(query.rho_global, len(provider_ids))

    output: list[LocalAdmissibilityQuery] = []
    for provider, branch_network in zip(provider_ids, context.branch_network_latency):
        local_latency = query.l_max - context.latency_common - branch_network
        if local_latency < -EVENT_TOLERANCE:
            raise ValueError(f"negative residual latency for {provider}")
        output.append(
            LocalAdmissibilityQuery(
                provider_id=provider,
                global_case_id=query.case_id,
                global_region_id=query.region_id,
                l_max=max(0.0, float(local_latency)),
                c_max=float(local_cost),
                q_min=float(query.q_min),
                epsilon_local=float(epsilon_local),
                rho_local=float(rho_local),
            )
        )
    return output


def compose_request_boundary(
    local_latency: Mapping[str, float],
    local_cost: Mapping[str, float],
    local_quality: Mapping[str, float],
    context: PublicBoundaryContext,
    providers: Sequence[str] = PROVIDERS,
) -> tuple[float, float, float]:
    """Compose one request under the declared structural L/C/Q algebra."""
    provider_ids = tuple(map(str, providers))
    for values, label in (
        (local_latency, "latency"),
        (local_cost, "cost"),
        (local_quality, "quality"),
    ):
        if set(values) != set(provider_ids):
            raise ValueError(f"local {label} keys must exactly match providers")

    branch_terms = [
        context.branch_network_latency[index] + float(local_latency[provider])
        for index, provider in enumerate(provider_ids)
    ]
    global_latency = context.latency_common + max(branch_terms)
    global_cost = context.fixed_execution_cost + sum(float(local_cost[p]) for p in provider_ids)
    global_quality = min(
        [context.fixed_quality_floor] + [float(local_quality[p]) for p in provider_ids]
    )
    return float(global_latency), float(global_cost), float(global_quality)


def request_level_implication_holds(
    query: GlobalAdmissibilityQuery,
    local_queries: Sequence[LocalAdmissibilityQuery],
    context: PublicBoundaryContext,
) -> bool:
    """Check local-boundary conjunction => global boundary at the exact limits."""
    by_provider = {q.provider_id: q for q in local_queries}
    if set(by_provider) != set(PROVIDERS):
        raise ValueError("local query set must contain exactly the three providers")
    local_latency = {p: by_provider[p].l_max for p in PROVIDERS}
    local_cost = {p: by_provider[p].c_max for p in PROVIDERS}
    local_quality = {p: by_provider[p].q_min for p in PROVIDERS}
    global_l, global_c, global_q = compose_request_boundary(
        local_latency, local_cost, local_quality, context
    )
    return bool(
        global_l <= query.l_max + EVENT_TOLERANCE
        and global_c <= query.c_max + EVENT_TOLERANCE
        and global_q + EVENT_TOLERANCE >= query.q_min
    )


def aligned_counting_certificate(
    local_pass_by_root: Mapping[str, Mapping[str, bool]],
    rho_global: float,
    rho_local: Mapping[str, float],
) -> dict[str, object]:
    """Validate the violation-budget theorem only on explicitly aligned root IDs.

    Each provider supplies a mapping ``root_id -> local_pass``. Provider root-id
    sets must be exactly identical. This is deliberately stricter than merely
    having equal vector lengths and prevents accidental use on different
    decision-time subsets at the same horizon.
    """
    if set(local_pass_by_root) != set(rho_local):
        raise ValueError("rho_local keys must exactly match provider pass mappings")
    providers = tuple(local_pass_by_root)
    if not providers:
        raise ValueError("at least one provider is required")
    root_sets = [set(local_pass_by_root[p]) for p in providers]
    if not root_sets[0] or any(roots != root_sets[0] for roots in root_sets[1:]):
        raise ValueError("provider-local logical root-id sets are not exactly aligned")

    roots = sorted(root_sets[0])
    local_fraction = {
        p: sum(bool(local_pass_by_root[p][root]) for root in roots) / len(roots)
        for p in providers
    }
    conjunction_fraction = sum(
        all(bool(local_pass_by_root[p][root]) for p in providers) for root in roots
    ) / len(roots)
    epsilon_global = 1.0 - float(rho_global)
    epsilon_sum = sum(1.0 - float(rho_local[p]) for p in providers)
    local_targets_hold = all(
        local_fraction[p] + EVENT_TOLERANCE >= float(rho_local[p]) for p in providers
    )
    budget_valid = epsilon_sum <= epsilon_global + EVENT_TOLERANCE
    certified = bool(
        local_targets_hold
        and budget_valid
        and conjunction_fraction + EVENT_TOLERANCE >= float(rho_global)
    )
    return {
        "n_aligned_roots": len(roots),
        "local_admissibility_fraction": local_fraction,
        "global_sufficient_conjunction_fraction": float(conjunction_fraction),
        "epsilon_global": float(epsilon_global),
        "epsilon_sum": float(epsilon_sum),
        "local_targets_hold": bool(local_targets_hold),
        "budget_valid": bool(budget_valid),
        "certified": certified,
    }


def validate_phase3a_contract_sources(
    phase3a_config: Mapping[str, object],
    phase1_manifest: Mapping[str, object],
    phase2_freeze: Mapping[str, object],
    phase2_card_contract: Mapping[str, object],
) -> None:
    """Validate status/firewall and exact rho-grid compatibility."""
    if phase3a_config.get("status") != EXPECTED_PHASE3A_STATUS:
        raise ValueError("unexpected Phase3A contract status")
    if phase1_manifest.get("status") != EXPECTED_PHASE1_V2_STATUS:
        raise ValueError("Phase1 v2 AR dependency is not frozen")
    if phase2_freeze.get("status") != EXPECTED_PHASE2_I1_STATUS:
        raise ValueError("Phase2 I1 dependency is not frozen")

    firewall = phase3a_config["information_firewall"]
    forbidden_true = [
        "may_read_phase2_private_provider_ledgers",
        "may_read_I1_sigma_values_during_structural_definition",
        "may_read_phase1_whitebox_sigma_outcomes_during_structural_definition",
        "may_read_hidden_provider_generator_parameters",
        "may_read_M1_results",
    ]
    if any(firewall[key] is not False for key in forbidden_true):
        raise ValueError("Phase3A information firewall is not closed")

    rho_global = float(phase3a_config["rho_global"])
    epsilon_local, rho_local = equal_violation_budget(rho_global, len(PROVIDERS))
    frozen_rhos = [float(v) for v in phase2_card_contract["R"]["values"]]
    if not any(abs(value - rho_local) <= 1e-12 for value in frozen_rhos):
        raise ValueError("Phase3A local rho is absent from the frozen I1 grid")
    declared = phase3a_config["tolerance_allocation"]
    if abs(float(declared["epsilon_local"]) - epsilon_local) > 1e-15:
        raise ValueError("declared local epsilon differs from equal allocation")
    if abs(float(declared["rho_local"]) - rho_local) > 1e-15:
        raise ValueError("declared local rho differs from equal allocation")


def main() -> None:
    here = Path(__file__).resolve().parent
    phase3a = load_json(here / "config_phase3a_m0_structural_contract_v1.json")
    phase1_manifest = load_json(here.parent / "phase1" / "phase1_v2_ar_freeze_manifest_v1.json")
    phase1_config = load_json(here.parent / "phase1" / "config_phase1_discovery_v1.json")
    phase2_freeze = load_json(here.parent / "phase2" / "phase2_i1_freeze_manifest_v1.json")
    phase2_card = load_json(here.parent / "phase2" / "config_phase2_i1_provider_card_v1.json")
    validate_phase3a_contract_sources(phase3a, phase1_manifest, phase2_freeze, phase2_card)

    context = derive_public_boundary_context(phase1_config)
    global_queries = load_frozen_global_queries(phase1_manifest)
    print("PHASE3A_M0_STRUCTURAL_QUERY_DERIVATION_PASS")
    print("phase3a_frozen=false")
    print("real_decision_time_horizon_alignment=UNRESOLVED_REQUIRES_SEPARATE_AUDIT")
    print("selection_role provider_id l_max c_max q_min rho_local")
    for global_query in global_queries:
        for local in decompose_global_query_equal_m0(global_query, context):
            print(
                f"{global_query.selection_role} {local.provider_id} "
                f"{local.l_max:.17g} {local.c_max:.17g} {local.q_min:.17g} {local.rho_local:.17g}"
            )


if __name__ == "__main__":
    main()
