"""Public loader/validator for rho-conditioned I1 provider cards."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from i1_provider_card import (
    assert_i1_surface_monotone_in_rho,
    assert_public_i1_card_has_no_forbidden_information,
)

RHO_CONDITIONED_I1_SCHEMA = "PRAISE_I1_PROVIDER_RHO_CONDITIONED_CARD_V1"
REQUIRED_SURFACE_COLUMNS = {
    "provider_id",
    "region_id",
    "region_rho",
    "l_max",
    "c_max",
    "q_min",
    "rho",
    "horizon",
    "sigma_hat",
}


def load_rho_conditioned_i1_provider_card(
    card_directory: Path,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Load one rho-conditioned public card without weakening the v1 loader."""
    metadata_path = card_directory / "card.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema") != RHO_CONDITIONED_I1_SCHEMA:
        raise ValueError("unexpected rho-conditioned I1 provider-card schema")
    surface_name = str(metadata.get("surface_file", "sigma_surface.csv"))
    surface = pd.read_csv(card_directory / surface_name)

    missing = REQUIRED_SURFACE_COLUMNS.difference(surface.columns)
    if missing:
        raise ValueError(
            "rho-conditioned I1 surface missing columns: "
            + ", ".join(sorted(missing))
        )
    if not isinstance(metadata.get("rho_conditioned_regions"), list):
        raise ValueError("rho-conditioned card metadata lacks region list")
    if not metadata.get("supported_region_rho_values"):
        raise ValueError("rho-conditioned card metadata lacks region-rho support")
    if not metadata.get("supported_query_rho_values"):
        raise ValueError("rho-conditioned card metadata lacks query-rho support")

    assert_i1_surface_monotone_in_rho(surface)
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    return metadata, surface
