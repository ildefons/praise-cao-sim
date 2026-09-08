"""Materialize public I1 cards from the frozen Phase-2 provider corpus.

Scientific role
---------------
A consuming integration method first declares the exact provider-local
admissibility regions A_i it needs, without inspecting I1 sigma values or
Phase-1 top-level white-box outcomes. This orchestration module then reads the
frozen provider evidence corpus and deterministically materializes those exact
public I1 H x rho surfaces.

Main call path
--------------
``main`` -> ``materialize_cards`` -> validate the predeclared query -> load the
frozen provider ledger -> ``i1_provider_card.build_i1_provider_card`` ->
``write_i1_provider_card``.

Scientific boundary
-------------------
This module does not select A_i, rerun the simulator, fit a provider model, or
inspect Phase-1 global outcomes. The resulting materialized card set is the same
public information intended for both M0 and M1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from i1_provider_card import build_i1_provider_card, write_i1_provider_card

PHASE2_DIRECTORY = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _read_json(path: Path) -> dict:
    """Read one frozen configuration, manifest, or query declaration."""
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_predeclared_i1_query_regions(
    query_declaration: dict,
) -> dict[str, list[dict]]:
    """Validate that exact A_i queries were declared before outcome inspection.

    Scientific purpose
    ------------------
    I1 is an information representation, not an optimization method. The local
    A_i boundaries must therefore come from the consuming method and be frozen
    before I1 sigma values or Phase-1 top-level outcomes are inspected.

    Returns
    -------
    A mapping from ProviderA/B/C to their exact predeclared local regions.

    Called by
    ---------
    ``materialize_cards``.
    """
    if query_declaration.get("status") != "FROZEN_I1_EXACT_QUERY_DECLARATION_V1":
        raise ValueError("unexpected I1 query declaration status")
    if query_declaration.get("declared_without_i1_sigma_inspection") is not True:
        raise ValueError("I1 query points must be declared before inspecting I1 sigma")
    if (
        query_declaration.get("declared_without_phase1_sigma_outcome_tuning")
        is not True
    ):
        raise ValueError("I1 query points must not be tuned to Phase-1 sigma outcomes")

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
    """Materialize one frozen public I1 card set for exact declared A_i values.

    Scientific sequence
    -------------------
    1. Load the frozen I1 H x rho card contract.
    2. Validate the consuming method's exact predeclared A_i query declaration.
    3. Verify that the frozen Phase-2 acquisition corpus completed successfully.
    4. Load each provider's private reduced ledger.
    5. Deterministically build and write that provider's public I1 surface.
    6. Freeze a public card-set manifest stating that the same cards are used by
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

    # PRIVATE EVIDENCE -> PUBLIC I1 MATERIALIZATION.
    # The exact same deterministic transformation is applied independently to
    # each provider ledger. Nothing in this loop chooses or tunes A_i.
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

        write_i1_provider_card(
            public_metadata,
            public_surface,
            output_directory / provider,
        )

    card_set_manifest = {
        "status": "FROZEN_PUBLIC_I1_CARD_SET_V1",
        "query_declaration_id": str(
            query_declaration.get("query_declaration_id", "UNNAMED")
        ),
        "providers": list(PROVIDERS),
        "R": rho_support,
        "H": horizon_support,
        "same_card_for_M0_and_M1": True,
        "source": (
            "deterministic post-processing of frozen Phase2 private acquisition corpus"
        ),
    }
    (output_directory / "card_set_manifest.json").write_text(
        json.dumps(card_set_manifest, indent=2), encoding="utf-8"
    )

    print("PHASE2_I1_CARD_MATERIALIZATION_PASS")
    print(f"query_declaration_id={card_set_manifest['query_declaration_id']}")
    print(f"output={output_directory.resolve()}")


def main() -> None:
    """Command-line entry point for deterministic I1 card materialization."""
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
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_cards_v1",
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
