"""Materialize public I1 cards from the frozen private provider corpus.

A consuming method must first declare exact provider-local admissibility regions
without inspecting I1 sigma values or Phase-1 top-level white-box outcomes. This
script then deterministically post-processes the frozen acquisition corpus into
the same public cards that can be supplied unchanged to M0 and M1.
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
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_query_declaration(declaration: dict) -> dict[str, list[dict]]:
    if declaration.get("status") != "FROZEN_I1_EXACT_QUERY_DECLARATION_V1":
        raise ValueError("unexpected I1 query declaration status")
    if declaration.get("declared_without_i1_sigma_inspection") is not True:
        raise ValueError("I1 query points must be declared before inspecting I1 sigma")
    if declaration.get("declared_without_phase1_sigma_outcome_tuning") is not True:
        raise ValueError("I1 query points must not be tuned to Phase-1 sigma outcomes")
    regions_by_provider = declaration.get("regions_by_provider")
    if not isinstance(regions_by_provider, dict):
        raise ValueError("regions_by_provider must be a mapping")
    if set(regions_by_provider) != set(PROVIDERS):
        raise ValueError("query declaration must contain exactly ProviderA/B/C")
    for provider in PROVIDERS:
        regions = regions_by_provider[provider]
        if not isinstance(regions, list) or not regions:
            raise ValueError(f"{provider} must declare at least one exact A_i")
        ids = [str(region.get("region_id", "")) for region in regions]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{provider} region ids must be non-empty and unique")
        for region in regions:
            for field in ("l_max", "c_max", "q_min"):
                if field not in region:
                    raise ValueError(f"{provider} region missing {field}")
    return regions_by_provider


def materialize_cards(
    card_config_path: Path,
    acquisition_directory: Path,
    query_declaration_path: Path,
    output_directory: Path,
) -> None:
    card_config = _read_json(card_config_path)
    if card_config.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V1":
        raise ValueError("I1 card contract is not frozen v1")
    declaration = _read_json(query_declaration_path)
    regions_by_provider = _validate_query_declaration(declaration)

    rho_values = [float(value) for value in card_config["R"]["values"]]
    horizons = [float(value) for value in card_config["H"]["values"]]
    workload = dict(card_config["workload_contract"])
    stop_time = float(workload["horizon_max"])

    public_summary_path = acquisition_directory / "acquisition_public_summary.json"
    acquisition_summary = _read_json(public_summary_path)
    if acquisition_summary.get("status") != "PHASE2_I1_ACQUISITION_COMPLETE":
        raise ValueError("I1 acquisition corpus is not complete")

    output_directory.mkdir(parents=True, exist_ok=True)
    for provider in PROVIDERS:
        ledger_path = (
            acquisition_directory
            / "private"
            / provider
            / "provider_request_ledgers.csv"
        )
        ledgers = pd.read_csv(ledger_path)
        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=ledgers,
            local_regions=regions_by_provider[provider],
            rho_values=rho_values,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract=workload,
        )
        metadata["query_declaration_id"] = str(
            declaration.get("query_declaration_id", "UNNAMED")
        )
        metadata["rho_surface_semantics"] = "sigma_i(A_i,H;rho) over frozen H x R"
        metadata["same_card_for_M0_and_M1"] = True
        write_i1_provider_card(metadata, surface, output_directory / provider)

    manifest = {
        "status": "FROZEN_PUBLIC_I1_CARD_SET_V1",
        "query_declaration_id": str(declaration.get("query_declaration_id", "UNNAMED")),
        "providers": list(PROVIDERS),
        "R": rho_values,
        "H": horizons,
        "same_card_for_M0_and_M1": True,
        "source": "deterministic post-processing of frozen Phase2 private acquisition corpus",
    }
    (output_directory / "card_set_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("PHASE2_I1_CARD_MATERIALIZATION_PASS")
    print(f"query_declaration_id={manifest['query_declaration_id']}")
    print(f"output={output_directory.resolve()}")


def main() -> None:
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
