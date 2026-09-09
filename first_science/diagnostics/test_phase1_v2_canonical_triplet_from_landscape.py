"""Simulator-independent tests for canonical Phase-1 v2 triplet extraction."""
from __future__ import annotations

import pandas as pd

from phase1_v2_canonical_triplet_from_landscape import (
    canonical_axis_value,
    collapse_epsilon_brackets,
    select_canonical_v2_triplet,
)


def _row(
    region_id: str,
    role: str,
    source: str,
    l_max: float,
    c_max: float,
    r95: float,
    r99: float,
) -> dict[str, object]:
    return {
        "region_id": region_id,
        "descriptive_role": role,
        "ar_augmentation_type": source,
        "l_max": l_max,
        "c_max": c_max,
        "q_min": 0.5,
        "area_rho_0p95": r95,
        "area_rho_0p975": (r95 + r99) / 2.0,
        "area_rho_0p99": r99,
        "latency_failure_count": 10,
        "cost_failure_count": 10,
    }


def run_all_tests() -> None:
    eps = 1e-9

    axis = pd.Series([0.4 - eps, 0.4, 0.4 + eps, 2.0]).to_numpy()
    assert abs(canonical_axis_value(0.4 - eps, axis, eps) - 0.4) < 1e-15
    assert abs(canonical_axis_value(0.4, axis, eps) - 0.4) < 1e-15
    assert abs(canonical_axis_value(0.4 + eps, axis, eps) - 0.4) < 1e-15
    assert abs(canonical_axis_value(2.0, axis, eps) - 2.0) < 1e-15

    # Build deliberate epsilon triplets. Upper brackets have tiny metric
    # advantages to verify that canonicalization selects the actual middle row
    # before ranking rather than exploiting sub-resolution differences.
    rows: list[dict[str, object]] = []
    for suffix, l_value, bump in (
        ("minus", 0.5 - eps, 0.0),
        ("mid", 0.5, 1e-14),
        ("plus", 0.5 + eps, 2e-14),
    ):
        rows.append(
            _row(
                f"lat_fdc_{suffix}",
                "latency",
                "FULL_DOMAIN_LOOSE_COST",
                l_value,
                3.0,
                0.99 + bump,
                0.90,
            )
        )
        rows.append(
            _row(
                f"lat_original_{suffix}",
                "latency",
                "ORIGINAL_ANCHOR_INFORMED",
                l_value,
                2.5,
                0.999,
                0.91,
            )
        )

    # Cost has no passing FULL_DOMAIN_LOOSE_LATENCY row, so the selector must
    # fall back to ORIGINAL_ANCHOR_INFORMED and choose the central C threshold.
    c_center = 2.0
    c_step = eps * c_center
    for suffix, c_value, bump in (
        ("minus", c_center - c_step, 0.0),
        ("mid", c_center, 1e-14),
        ("plus", c_center + c_step, 2e-14),
    ):
        rows.append(
            _row(
                f"cost_original_{suffix}",
                "cost",
                "ORIGINAL_ANCHOR_INFORMED",
                0.8,
                c_value,
                0.995 + bump,
                0.92,
            )
        )
    rows.append(
        _row(
            "cost_fdl_fails_gate",
            "cost",
            "FULL_DOMAIN_LOOSE_LATENCY",
            4.0,
            2.0,
            0.99,
            0.97,
        )
    )

    # Mixed always uses the original family and central cost threshold.
    mixed_center = 2.2
    mixed_step = eps * mixed_center
    for suffix, c_value in (
        ("minus", mixed_center - mixed_step),
        ("mid", mixed_center),
        ("plus", mixed_center + mixed_step),
    ):
        rows.append(
            _row(
                f"mixed_{suffix}",
                "mixed",
                "ORIGINAL_ANCHOR_INFORMED",
                0.8,
                c_value,
                0.996,
                0.93,
            )
        )

    landscape = pd.DataFrame(rows)
    canonical = collapse_epsilon_brackets(landscape, eps)

    # The exact central rows must survive the collapse.
    assert "lat_fdc_mid" in set(canonical["region_id"].astype(str))
    assert "cost_original_mid" in set(canonical["region_id"].astype(str))
    assert "mixed_mid" in set(canonical["region_id"].astype(str))
    assert "lat_fdc_plus" not in set(canonical["region_id"].astype(str))
    assert "cost_original_plus" not in set(canonical["region_id"].astype(str))

    selected = select_canonical_v2_triplet(canonical)
    assert set(selected["selection_role"].astype(str)) == {"latency", "cost", "mixed"}

    latency = selected[selected["selection_role"] == "latency"].iloc[0]
    cost = selected[selected["selection_role"] == "cost"].iloc[0]
    mixed = selected[selected["selection_role"] == "mixed"].iloc[0]

    # Semantic source preference dominates a numerically higher R95 original
    # latency candidate when the full-domain-loose-cost family passes.
    assert latency["region_id"] == "lat_fdc_mid"
    assert latency["v2_selected_source"] == "FULL_DOMAIN_LOOSE_COST"

    # Cost falls back because its full-domain-loose-latency candidate fails the
    # stress gate. Mixed remains original by construction.
    assert cost["region_id"] == "cost_original_mid"
    assert cost["v2_selected_source"] == "ORIGINAL_ANCHOR_INFORMED"
    assert mixed["region_id"] == "mixed_mid"
    assert mixed["v2_selected_source"] == "ORIGINAL_ANCHOR_INFORMED"

    print("PHASE1_V2_CANONICAL_TRIPLET_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
