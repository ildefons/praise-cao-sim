"""Materialize the final public I1 cards from the frozen Phase-2 provider corpus.

Scientific role
---------------
A concrete I1 card includes its provider-local admissibility region A_i. The
exact A_i values are therefore frozen in Phase 2 by the method-independent
A_G -> A_i query-instantiation step before any composition method consumes I1.
This module reads that frozen declaration and deterministically materializes the
public H x rho surfaces from the already frozen private provider evidence.

Main call path
--------------
``main`` -> ``materialize_cards`` -> validate frozen Phase-2 A_i declaration ->
load frozen provider ledger -> ``i1_provider_card.build_i1_provider_card`` ->
``write_i1_provider_card``.

Scientific boundary
-------------------
This module does not choose A_i, choose a rho slice, rerun the simulator, fit a
provider model, or inspect Phase-1 global outcomes. The resulting materialized
card set is the identical public information supplied to M0 and M1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from i1_provider_card import build_i1_provider_card, write_i1_provider_card

PHASE2_DIRECTORY = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
QUERY_DECLARATION_STATUS = "FROZEN_PHASE2_I1_EXACT_QUERY_DECLARATION_V1"


def _read_json(path: Path) -> dict:
    """Read one frozen configuration, manifest, or query declaration."""
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_predeclared_i1_query_regions(
    query_declaration: dict,
) -> dict[str, list[dict]]:
    """Validate the method-independent exact A_i declaration frozen in Phase 2.

    I1 is the information representation supplied to M. Because A_i is part of
    the instantiated I1 object, M0/M1 may not choose or alter these boundaries.
    The declaration must be a deterministic consequence of the already frozen
    Phase-1 A_G battery and must precede inspection of I1 sigma values.
    """
    if query_declaration.get("status") != QUERY_DECLARATION_STATUS:
        raise ValueError("unexpected Phase-2 I1 query declaration status")
    if query_declaration.get("declared_without_i1_sigma_inspection") is not True:
        raise ValueError("I1 A_i points must be frozen before inspecting I1 sigma")
    if (
        query_declaration.get("derived_deterministically_from_already_frozen_A_G")
        is not True
    ):
        raise ValueError("I1 A_i points must derive from the already frozen A_G battery")
    if query_declaration.get("no_post_A_G_freeze_whitebox_outcome_tuning") is not True:
        raise ValueError("I1 A_i points may not use post-freeze white-box outcome tuning")
    if query_declaration.get("rho_localization_performed") is not False:
        raise ValueError("Phase 2 must expose full rho support rather than choose an M-specific slice")
    if query_declaration.get("same_materialized_cards_for_M0_and_M1") is not True:
        raise ValueError("M0 and M1 must receive identical materialized I1 cards")

    regions_by_provider = query_declaration.get("regions_by_provider")
    if not isinstance(regions_by_provider, dict):
        raise ValueError("regions_by_provider must be a mapping")
    if set(regions_by_provider) != set(PROVIDERS):
        raise ValueError("query declaration must contain exactly ProviderA/B/C")

    for provider in PROVIDERS:
        provider_regions = regions_by_provider[provider]
        if not isinstance(provider_regions, list) or not provider_regions:
            raise ValueError(f"{provider} must declare at least one exact A_i")

        region_ids = [
            str(local_region.get("region_id", ""))
            for local_region in provider_regions
        ]
        if any(not region_id for region_id in region_ids) or len(region_ids) != len(
            set(region_ids)
        ):
            raise ValueError(f"{provider} region ids must be non-empty and unique")

        for local_region in provider_regions:
            if "rho" in local_region or "rho_local" in local_region:
                raise ValueError("A_i declaration must not contain a method-specific rho")
            for required_field in ("l_max", "c_max", "q_min"):
                if required_field not in local_region:
                    raise ValueError(
                        f"{provider} region missing {required_field}"
                    )

    return regions_by_provider


def materialize_cards(
    card_config_path: Path,
    acquisition_directory: Path,
    query_declaration_path: Path,
    output_directory: Path,
) -> None:
    """Materialize the final public I1 card set for the frozen A_i declaration.

    Sequence
    --------
    1. Load the frozen I1 H x rho card contract.
    2. Validate the Phase-2 method-independent exact A_i declaration.
    3. Verify that the frozen Phase-2 acquisition corpus completed successfully.
    4. Load each provider's private reduced ledger.
    5. Deterministically build and write that provider's public I1 surface for
       all declared A_i, all frozen horizons H, and all frozen rho values R.
    6. Write a public card-set manifest stating that the same cards are inputs to
       M0 and M1.

    No simulator execution occurs in this function.
    """
    card_configuration = _read_json(card_config_path)
    if card_configuration.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V1":
        raise ValueError("I1 card contract is not frozen v1")

    query_declaration = _read_json(query_declaration_path)
    regions_by_provider = _validate_predeclared_i1_query_regions(
        query_declaration
    )

    rho_support = [float(value) for value in card_configuration["R"]["values"]]
    horizon_support = [
        float(value) for value in card_configuration["H"]["values"]
    ]
    workload_contract = dict(card_configuration["workload_contract"])
    simulation_stop_time = float(workload_contract["horizon_max"])

    public_acquisition_summary_path = (
        acquisition_directory / "acquisition_public_summary.json"
    )
    acquisition_summary = _read_json(public_acquisition_summary_path)
    if acquisition_summary.get("status") != "PHASE2_I1_ACQUISITION_COMPLETE":
        raise ValueError("I1 acquisition corpus is not complete")

    output_directory.mkdir(parents=True, exist_ok=True)

    # PRIVATE EVIDENCE -> FINAL PUBLIC I1.
    # A_i, H and R are already fixed inputs here. This loop does not choose or
    # tune any of them and does not depend on M0/M1.
    for provider in PROVIDERS:
        provider_ledger_path = (
            acquisition_directory
            / "private"
            / provider
            / "provider_request_ledgers.csv"
        )
        private_provider_ledgers = pd.read_csv(provider_ledger_path)

        public_metadata, public_surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=private_provider_ledgers,
            local_regions=regions_by_provider[provider],
            rho_values=rho_support,
            horizons=horizon_support,
            stop_time=simulation_stop_time,
            workload_contract=workload_contract,
        )
        public_metadata["query_declaration_id"] = str(
            query_declaration.get("query_declaration_id", "UNNAMED")
        )
        public_metadata[
            "rho_surface_semantics"
        ] = "sigma_i(A_i,H;rho) over frozen H x R"
        public_metadata["same_card_for_M0_and_M1"] = True
        public_metadata["A_i_owned_by_phase2_information_instantiation"] = True

        write_i1_provider_card(
            public_metadata,
            public_surface,
            output_directory / provider,
        )

    card_set_manifest = {
        "status": "MATERIALIZED_PUBLIC_I1_CARD_SET_V1",
        "phase": "phase2_i1",
        "query_declaration_id": str(
            query_declaration.get("query_declaration_id", "UNNAMED")
        ),
        "query_declaration_status": str(query_declaration["status"]),
        "providers": list(PROVIDERS),
        "number_of_A_i_per_provider": {
            provider: len(regions_by_provider[provider]) for provider in PROVIDERS
        },
        "R": rho_support,
        "H": horizon_support,
        "same_card_for_M0_and_M1": True,
        "rho_slice_selected_by_phase2": False,
        "source": (
            "deterministic post-processing of frozen Phase2 private acquisition corpus"
        ),
        "freeze_pending_hash_validation": True
    }
    (output_directory / "card_set_manifest.json").write_text(
        json.dumps(card_set_manifest, indent=2), encoding="utf-8"
    )

    print("PHASE2_I1_CARD_MATERIALIZATION_PASS")
    print(f"query_declaration_id={card_set_manifest['query_declaration_id']}")
    print("same_card_for_M0_and_M1=true")
    print("rho_slice_selected_by_phase2=false")
    print("freeze_pending_hash_validation=true")
    print(f"output={output_directory.resolve()}")


def main() -> None:
    """Command-line entry point for deterministic final I1 card materialization."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--card-config",
        type=Path,
        default=PHASE2_DIRECTORY / "config_phase2_i1_provider_card_v1.json",
    )
    parser.add_argument(
        "--acquisition",
        type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_acquisition_v1",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=PHASE2_DIRECTORY / "phase2_i1_exact_query_declaration_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_cards_phase2_final_v1",
    )
    args = parser.parse_args()
    materialize_cards(
        args.card_config.resolve(),
        args.acquisition.resolve(),
        args.queries.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
