"""Instantiate provider-local A_i queries for the frozen Phase-1 v2 A_G battery.

Scientific role
---------------
A_i is part of a concrete I1 card. Therefore the mapping A_G -> {A_i} belongs
here, in Phase 2, before any composition method consumes I1. The mapping uses
only the frozen global query and public composition structure. It does not use
I1 sigma values, provider-private parameters, or post-freeze white-box outcomes.

The result is one exact local admissibility region per global benchmark case and
provider. These A_i values are then passed to ``materialize_i1_cards.py``. M0
and M1 must receive the resulting card set unchanged.

Rho is deliberately not localized here. A materialized I1 card contains the
entire frozen rho support R; choosing which rho slice(s) to consume belongs to
M, not to I1 instantiation.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

PHASE2_DIRECTORY = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EVENT_TOLERANCE = 1e-12
EXPECTED_PHASE1_STATUS = "FROZEN_PHASE1_V2_AR_SELECTION_V1"
EXPECTED_INSTANTIATION_STATUS = "FROZEN_PHASE2_I1_QUERY_INSTANTIATION_V1"
QUERY_DECLARATION_STATUS = "FROZEN_PHASE2_I1_EXACT_QUERY_DECLARATION_V1"


@dataclass(frozen=True)
class PublicLocalizationContext:
    """Public deterministic terms needed to map global L/C/Q into local L/C/Q."""

    latency_common: float
    branch_network_latency: tuple[float, ...]
    fixed_execution_cost: float
    fixed_quality_floor: float


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def yafs_single_link_latency(
    message_bytes: float,
    bandwidth_mbps: float,
    propagation: float,
) -> float:
    """Return the frozen public YAFS single-link latency."""
    size = float(message_bytes)
    bandwidth = float(bandwidth_mbps)
    pr = float(propagation)
    if size < 0.0 or bandwidth <= 0.0 or pr < 0.0:
        raise ValueError("invalid public network parameters")
    return size / (bandwidth * 1_000_000.0) + pr


def derive_public_localization_context(
    phase1_configuration: Mapping[str, Any],
    providers: Sequence[str] = PROVIDERS,
) -> PublicLocalizationContext:
    """Derive only the public deterministic composition terms needed for A_i."""
    provider_ids = tuple(map(str, providers))
    if not provider_ids or len(set(provider_ids)) != len(provider_ids):
        raise ValueError("providers must be non-empty and unique")

    graph = phase1_configuration["graph"]
    topology = phase1_configuration["topology"]
    provider_family = phase1_configuration["provider_family"]

    ipt = float(provider_family["effective_ipt"])
    cost_rate = float(provider_family["cost_rate"])
    if ipt <= 0.0 or cost_rate < 0.0:
        raise ValueError("invalid public execution parameters")

    pre_service = float(graph["pre_instructions"]) / ipt
    post_service = float(graph["post_instructions"]) / ipt

    bw = float(topology["network_bw_mbps"])
    pr = float(topology["network_pr"])
    root_network = yafs_single_link_latency(topology["request_bytes"], bw, pr)
    branch_network = yafs_single_link_latency(topology["branch_bytes"], bw, pr)
    join_network = yafs_single_link_latency(topology["join_bytes"], bw, pr)

    latency_common = root_network + pre_service + join_network + post_service
    fixed_execution_cost = cost_rate * (pre_service + post_service)

    return PublicLocalizationContext(
        latency_common=float(latency_common),
        branch_network_latency=(float(branch_network),) * len(provider_ids),
        fixed_execution_cost=float(fixed_execution_cost),
        fixed_quality_floor=1.0,
    )


def localize_one_global_region(
    whitebox: Mapping[str, Any],
    context: PublicLocalizationContext,
    providers: Sequence[str] = PROVIDERS,
) -> dict[str, list[dict[str, Any]]]:
    """Map one frozen A_G to one sufficient local A_i for each provider.

    Latency keeps the full residual on every parallel branch because the global
    composition uses a maximum. Cost splits the additive residual equally among
    providers. Quality copies the global minimum threshold to every provider.
    """
    provider_ids = tuple(map(str, providers))
    if len(provider_ids) != len(context.branch_network_latency):
        raise ValueError("provider count does not match public branch terms")

    global_l = float(whitebox["l_max"])
    global_c = float(whitebox["c_max"])
    global_q = float(whitebox["q_min"])
    case_id = str(whitebox["case_id"])
    role = str(whitebox["selection_role"])

    if context.fixed_quality_floor + EVENT_TOLERANCE < global_q:
        raise ValueError("fixed stages cannot satisfy the global quality threshold")

    residual_cost = global_c - context.fixed_execution_cost
    if residual_cost < -EVENT_TOLERANCE:
        raise ValueError("global cost threshold is below deterministic fixed cost")
    local_cost = max(0.0, residual_cost) / len(provider_ids)

    output: dict[str, list[dict[str, Any]]] = {}
    for provider, branch_latency in zip(provider_ids, context.branch_network_latency):
        local_latency = global_l - context.latency_common - float(branch_latency)
        if local_latency < -EVENT_TOLERANCE:
            raise ValueError(f"global latency threshold leaves negative residual for {provider}")
        output[provider] = [
            {
                "region_id": f"{case_id}_LOCAL",
                "global_case_id": case_id,
                "global_selection_role": role,
                "l_max": max(0.0, float(local_latency)),
                "c_max": float(local_cost),
                "q_min": global_q,
            }
        ]
    return output


def build_exact_i1_query_declaration(
    phase1_manifest: Mapping[str, Any],
    phase1_configuration: Mapping[str, Any],
    instantiation_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the complete method-independent Phase-2 A_i declaration."""
    if phase1_manifest.get("status") != EXPECTED_PHASE1_STATUS:
        raise ValueError("Phase-1 v2 A_G manifest is not frozen")
    if instantiation_contract.get("status") != EXPECTED_INSTANTIATION_STATUS:
        raise ValueError("unexpected Phase-2 I1 query-instantiation contract")
    if instantiation_contract.get("same_instantiated_I1_for_M0_and_M1") is not True:
        raise ValueError("Phase-2 must freeze identical instantiated I1 for M0 and M1")

    whiteboxes = phase1_manifest.get("whiteboxes")
    if not isinstance(whiteboxes, list) or len(whiteboxes) != 3:
        raise ValueError("expected the three frozen Phase-1 v2 global cases")
    roles = {str(w["selection_role"]) for w in whiteboxes}
    if roles != {"latency", "cost", "mixed"}:
        raise ValueError("global battery must contain latency, cost and mixed cases")

    context = derive_public_localization_context(phase1_configuration)
    regions_by_provider = {provider: [] for provider in PROVIDERS}
    for whitebox in whiteboxes:
        localized = localize_one_global_region(whitebox, context)
        for provider in PROVIDERS:
            regions_by_provider[provider].extend(localized[provider])

    return {
        "status": QUERY_DECLARATION_STATUS,
        "query_declaration_id": "PHASE2_I1_FROM_FROZEN_PHASE1_V2_AG_V1",
        "scientific_role": "method-independent exact A_i declaration used to instantiate the public I1 cards before M0/M1",
        "source_global_manifest_status": str(phase1_manifest["status"]),
        "source_physical_setting_id": str(
            phase1_manifest["physical_setting"]["physical_setting_id"]
        ),
        "declared_without_i1_sigma_inspection": True,
        "derived_deterministically_from_already_frozen_A_G": True,
        "no_post_A_G_freeze_whitebox_outcome_tuning": True,
        "rho_localization_performed": False,
        "rho_reason": "I1 exposes the complete frozen rho support R; rho-slice consumption belongs to M.",
        "same_materialized_cards_for_M0_and_M1": True,
        "public_localization_context": {
            "latency_common": context.latency_common,
            "branch_network_latency": list(context.branch_network_latency),
            "fixed_execution_cost": context.fixed_execution_cost,
            "fixed_quality_floor": context.fixed_quality_floor,
        },
        "regions_by_provider": regions_by_provider,
    }


def validate_exact_i1_query_declaration(declaration: Mapping[str, Any]) -> None:
    """Reject a declaration that violates the corrected Phase-2/M separation."""
    if declaration.get("status") != QUERY_DECLARATION_STATUS:
        raise ValueError("unexpected Phase-2 exact I1 query declaration status")
    if declaration.get("declared_without_i1_sigma_inspection") is not True:
        raise ValueError("A_i must be declared before I1 sigma inspection")
    if declaration.get("derived_deterministically_from_already_frozen_A_G") is not True:
        raise ValueError("A_i must be derived from the frozen A_G battery")
    if declaration.get("no_post_A_G_freeze_whitebox_outcome_tuning") is not True:
        raise ValueError("A_i may not be tuned using post-freeze white-box outcomes")
    if declaration.get("rho_localization_performed") is not False:
        raise ValueError("Phase 2 must not select a method-specific rho slice")
    if declaration.get("same_materialized_cards_for_M0_and_M1") is not True:
        raise ValueError("M0 and M1 must receive the same materialized I1 cards")

    regions = declaration.get("regions_by_provider")
    if not isinstance(regions, dict) or set(regions) != set(PROVIDERS):
        raise ValueError("declaration must contain exactly ProviderA/B/C")
    for provider in PROVIDERS:
        provider_regions = regions[provider]
        if not isinstance(provider_regions, list) or len(provider_regions) != 3:
            raise ValueError(f"{provider} must contain exactly three benchmark A_i regions")
        ids = [str(r.get("region_id", "")) for r in provider_regions]
        if len(set(ids)) != 3 or any(not x for x in ids):
            raise ValueError(f"{provider} local region ids must be unique")
        for region in provider_regions:
            if "rho" in region or "rho_local" in region:
                raise ValueError("A_i query declaration must not contain a method-specific rho")
            for key in ("l_max", "c_max", "q_min"):
                if key not in region:
                    raise ValueError(f"{provider} region missing {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase1-manifest",
        type=Path,
        default=PHASE2_DIRECTORY.parent / "phase1" / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE2_DIRECTORY.parent / "phase1" / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=PHASE2_DIRECTORY / "config_phase2_i1_query_instantiation_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PHASE2_DIRECTORY / "phase2_i1_exact_query_declaration_v1.json",
    )
    args = parser.parse_args()

    declaration = build_exact_i1_query_declaration(
        _read_json(args.phase1_manifest),
        _read_json(args.phase1_config),
        _read_json(args.contract),
    )
    validate_exact_i1_query_declaration(declaration)
    args.output.write_text(json.dumps(declaration, indent=2), encoding="utf-8")

    rows = []
    for provider, regions in declaration["regions_by_provider"].items():
        for region in regions:
            rows.append({"provider_id": provider, **region})
    frame = pd.DataFrame(rows)
    print("PHASE2_I1_QUERY_INSTANTIATION_PASS")
    print("rho_localization_performed=false")
    print("same_materialized_cards_for_M0_and_M1=true")
    print(frame.to_string(index=False))
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
