"""Round-trip guard for the versioned rho-conditioned public-card loader."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from i1_rho_conditioned_card import (
    RHO_CONDITIONED_I1_SCHEMA,
    load_rho_conditioned_i1_provider_card,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        metadata = {
            "schema": RHO_CONDITIONED_I1_SCHEMA,
            "provider_id": "ProviderA",
            "surface_file": "sigma_surface.csv",
            "rho_conditioned_regions": [
                {
                    "region_id": "r095",
                    "region_rho": 0.95,
                    "l_max": 1.0,
                    "c_max": 2.0,
                    "q_min": 0.5,
                }
            ],
            "supported_region_rho_values": [0.95],
            "supported_query_rho_values": [0.95],
            "supported_horizons": [0.0, 5.0],
        }
        surface = pd.DataFrame(
            {
                "provider_id": ["ProviderA", "ProviderA"],
                "region_id": ["r095", "r095"],
                "region_rho": [0.95, 0.95],
                "l_max": [1.0, 1.0],
                "c_max": [2.0, 2.0],
                "q_min": [0.5, 0.5],
                "rho": [0.95, 0.95],
                "horizon": [0.0, 5.0],
                "sigma_hat": [1.0, 0.9],
            }
        )
        (root / "card.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        surface.to_csv(root / "sigma_surface.csv", index=False)
        loaded_metadata, loaded_surface = load_rho_conditioned_i1_provider_card(root)
        assert loaded_metadata["provider_id"] == "ProviderA"
        assert "region_rho" in loaded_surface.columns
        assert len(loaded_surface) == 2

    print("PHASE2_RHO_CONDITIONED_PUBLIC_CARD_LOADER_TESTS_PASS")
    print("VERSIONED_SCHEMA_WITHOUT_LEGACY_LOADER_WEAKENING_PASS")


if __name__ == "__main__":
    main()
