"""Inspect the materialized Phase-2 I1 cards before the final freeze.

This is a local-evidence audit. It does not modify cards, rerun AICon/YAFS, or
select any rho slice. It validates that the materialized public I1 objects match
the frozen Phase-2 declaration and prints compact representative sigma values
plus SHA-256 fingerprints for the subsequent freeze manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from i1_provider_card import load_i1_provider_card

HERE = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_RHOS = (0.95, 0.975, 0.9833333333333333, 0.99, 1.0)
EXPECTED_HORIZONS = tuple(float(x) for x in range(0, 241, 5))
EXPECTED_REGIONS = ("V2_LATENCY_LOCAL", "V2_COST_LOCAL", "V2_MIXED_LOCAL")
EXPECTED_ROWS_PER_PROVIDER = 3 * 5 * 49


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_close_sequence(actual, expected, *, atol: float = 1e-12) -> None:
    actual_values = np.asarray(list(actual), dtype=float)
    expected_values = np.asarray(list(expected), dtype=float)
    assert actual_values.shape == expected_values.shape
    assert np.allclose(actual_values, expected_values, atol=atol, rtol=0.0)


def inspect_cards(cards_directory: Path, declaration_path: Path) -> None:
    declaration = _load_json(declaration_path)
    assert declaration["status"] == "FROZEN_PHASE2_I1_EXACT_QUERY_DECLARATION_V1"
    assert declaration["rho_localization_performed"] is False
    assert declaration["same_materialized_cards_for_M0_and_M1"] is True

    manifest_path = cards_directory / "card_set_manifest.json"
    card_set_manifest = _load_json(manifest_path)
    assert card_set_manifest["status"] == "MATERIALIZED_PUBLIC_I1_CARD_SET_V1"
    assert card_set_manifest["same_card_for_M0_and_M1"] is True
    assert card_set_manifest["rho_slice_selected_by_phase2"] is False
    assert card_set_manifest["freeze_pending_hash_validation"] is True
    assert set(card_set_manifest["providers"]) == set(PROVIDERS)
    _assert_close_sequence(card_set_manifest["R"], EXPECTED_RHOS)
    _assert_close_sequence(card_set_manifest["H"], EXPECTED_HORIZONS)

    representative_rows: list[dict[str, object]] = []
    hash_rows: list[dict[str, str]] = []

    for provider in PROVIDERS:
        provider_directory = cards_directory / provider
        metadata, surface = load_i1_provider_card(provider_directory)

        assert metadata["provider_id"] == provider
        assert metadata["status"] == "PUBLIC_PROVIDER_SIGMA_SURFACE_CARD"
        assert metadata["same_card_for_M0_and_M1"] is True
        assert metadata["A_i_owned_by_phase2_information_instantiation"] is True
        assert int(metadata["n_trajectories"]) == 100
        assert int(metadata["n_local_regions"]) == 3
        assert len(surface) == EXPECTED_ROWS_PER_PROVIDER
        assert set(surface["region_id"].astype(str)) == set(EXPECTED_REGIONS)
        _assert_close_sequence(sorted(surface["rho"].astype(float).unique()), EXPECTED_RHOS)
        _assert_close_sequence(sorted(surface["horizon"].astype(float).unique()), EXPECTED_HORIZONS)
        assert set(surface["n_trajectories"].astype(int)) == {100}
        assert np.allclose(
            surface["sigma_hat"].astype(float).to_numpy(),
            surface["n_success"].astype(float).to_numpy() / 100.0,
            atol=1e-12,
            rtol=0.0,
        )

        # Every declared A_i must appear exactly with the declared L/C/Q values.
        declared = {
            str(region["region_id"]): region
            for region in declaration["regions_by_provider"][provider]
        }
        assert set(declared) == set(EXPECTED_REGIONS)
        for region_id, region in declared.items():
            region_surface = surface.loc[surface["region_id"].astype(str) == region_id]
            assert len(region_surface) == 5 * 49
            assert np.allclose(region_surface["l_max"], float(region["l_max"]), atol=1e-12, rtol=0.0)
            assert np.allclose(region_surface["c_max"], float(region["c_max"]), atol=1e-12, rtol=0.0)
            assert np.allclose(region_surface["q_min"], float(region["q_min"]), atol=1e-12, rtol=0.0)

            # One complete H curve must exist for each rho.
            counts = region_surface.groupby("rho")["horizon"].count().to_numpy()
            assert np.all(counts == 49)

            def sigma_at(horizon: float, rho: float) -> float:
                mask = np.isclose(region_surface["horizon"].astype(float), horizon, atol=1e-12, rtol=0.0) & np.isclose(
                    region_surface["rho"].astype(float), rho, atol=1e-12, rtol=0.0
                )
                point = region_surface.loc[mask]
                assert len(point) == 1
                return float(point.iloc[0]["sigma_hat"])

            representative_rows.append(
                {
                    "provider": provider,
                    "region": region_id,
                    "s120_r095": sigma_at(120.0, 0.95),
                    "s240_r095": sigma_at(240.0, 0.95),
                    "s120_r09833": sigma_at(120.0, 0.9833333333333333),
                    "s240_r09833": sigma_at(240.0, 0.9833333333333333),
                    "s120_r099": sigma_at(120.0, 0.99),
                    "s240_r099": sigma_at(240.0, 0.99),
                }
            )

        hash_rows.append(
            {
                "provider": provider,
                "card_json_sha256": _sha256(provider_directory / "card.json"),
                "sigma_surface_sha256": _sha256(provider_directory / "sigma_surface.csv"),
            }
        )

    print("PHASE2_FINAL_I1_CARD_INSPECTION_PASS")
    print(f"rows_per_provider={EXPECTED_ROWS_PER_PROVIDER}")
    print("n_trajectories_per_provider=100")
    print("n_A_i_per_provider=3")
    print("n_rho=5")
    print("n_horizons=49")
    print("same_card_for_M0_and_M1=true")
    print("rho_slice_selected_by_phase2=false")
    print("\nREPRESENTATIVE_SIGMA_POINTS")
    print(pd.DataFrame(representative_rows).to_string(index=False))
    print("\nSHA256_FINGERPRINTS")
    hashes = pd.DataFrame(hash_rows)
    print(hashes.to_string(index=False))
    print(f"query_declaration_sha256={_sha256(declaration_path)}")
    print(f"card_set_manifest_sha256={_sha256(manifest_path)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cards",
        type=Path,
        default=HERE / "results" / "i1_cards_phase2_final_v1",
    )
    parser.add_argument(
        "--declaration",
        type=Path,
        default=HERE / "phase2_i1_exact_query_declaration_v1.json",
    )
    args = parser.parse_args()
    inspect_cards(args.cards.resolve(), args.declaration.resolve())


if __name__ == "__main__":
    main()
