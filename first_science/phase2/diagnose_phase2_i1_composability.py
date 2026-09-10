"""Diagnose whether the materialized Phase-2 I1 cards remain composition-informative.

This is a read-only scientific diagnostic. It does not change A_i, rho support,
provider evidence, or any frozen Phase-1 object. Its purpose is to detect a
potentially degenerate I1 instantiation before the final public card set is
hash-frozen.

For each frozen global case and horizon, the script enumerates all provider rho
triples available on the I1 cards that satisfy the global violation-budget
condition

    sum_i (1-rho_i) <= 1-rho_G,

with rho_G=0.95. It then reports the largest independent-product value available
within that finite support. This is intentionally an optimistic diagnostic for
the simple product family: if even the best feasible allocation is zero, any M0
variant based on that product and the same local A_i must also be zero there.

No allocation selected here becomes part of M0. The script is diagnostic only.
"""
from __future__ import annotations

from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CARD_ROOT = HERE / "results" / "i1_cards_phase2_final_v1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
GLOBAL_RHO = 0.95
TOL = 1e-12


def _load_surface(provider: str) -> pd.DataFrame:
    path = CARD_ROOT / provider / "sigma_surface.csv"
    frame = pd.read_csv(path)
    required = {"region_id", "rho", "horizon", "sigma_hat"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{provider} surface missing {sorted(missing)}")
    return frame


def _lookup_sigma(frame: pd.DataFrame, region_id: str, rho: float, horizon: float) -> float:
    mask = (
        (frame["region_id"].astype(str) == str(region_id))
        & np.isclose(frame["rho"].astype(float), float(rho), atol=1e-12, rtol=0.0)
        & np.isclose(frame["horizon"].astype(float), float(horizon), atol=1e-12, rtol=0.0)
    )
    rows = frame.loc[mask, "sigma_hat"]
    if len(rows) != 1:
        raise ValueError(
            f"expected one I1 point for region={region_id}, rho={rho}, H={horizon}; found {len(rows)}"
        )
    return float(rows.iloc[0])


def main() -> None:
    manifest = json.loads((CARD_ROOT / "card_set_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "MATERIALIZED_PUBLIC_I1_CARD_SET_V1":
        raise ValueError("final Phase-2 I1 card set is not in materialized/pending-freeze state")
    if manifest.get("same_card_for_M0_and_M1") is not True:
        raise ValueError("diagnostic requires identical materialized cards for M0 and M1")

    surfaces = {provider: _load_surface(provider) for provider in PROVIDERS}
    rho_support = tuple(float(x) for x in manifest["R"])
    horizons = tuple(float(x) for x in manifest["H"])
    epsilon_global = 1.0 - GLOBAL_RHO

    feasible_allocations = [
        tuple(map(float, allocation))
        for allocation in product(rho_support, repeat=len(PROVIDERS))
        if sum(1.0 - float(rho) for rho in allocation) <= epsilon_global + TOL
    ]
    if not feasible_allocations:
        raise RuntimeError("no feasible rho allocation exists on frozen I1 support")

    reference_regions = tuple(
        surfaces[PROVIDERS[0]]["region_id"].astype(str).drop_duplicates().tolist()
    )
    for provider in PROVIDERS[1:]:
        regions = tuple(surfaces[provider]["region_id"].astype(str).drop_duplicates().tolist())
        if set(regions) != set(reference_regions):
            raise ValueError("provider cards do not expose the same benchmark region ids")

    # First report the least-strict card slice. If a provider is already zero at
    # rho=.95, every stricter rho in the frozen support is also zero there.
    floor_rows = []
    for region in reference_regions:
        for horizon in (120.0, 240.0):
            for provider in PROVIDERS:
                sigma = _lookup_sigma(surfaces[provider], region, min(rho_support), horizon)
                floor_rows.append(
                    {
                        "region": region,
                        "horizon": horizon,
                        "provider": provider,
                        "sigma_at_min_rho": sigma,
                    }
                )
    floor = pd.DataFrame(floor_rows)

    best_rows = []
    for region in reference_regions:
        for horizon in horizons:
            scored = []
            for allocation in feasible_allocations:
                sigmas = [
                    _lookup_sigma(surfaces[p], region, rho, horizon)
                    for p, rho in zip(PROVIDERS, allocation)
                ]
                value = float(np.prod(sigmas))
                scored.append((value, allocation, tuple(sigmas)))
            scored.sort(key=lambda item: (-item[0], item[1]))
            best_value, best_allocation, best_sigmas = scored[0]
            positive_count = sum(value > 0.0 for value, _, _ in scored)
            best_rows.append(
                {
                    "region": region,
                    "horizon": horizon,
                    "best_product": best_value,
                    "best_rho_A": best_allocation[0],
                    "best_rho_B": best_allocation[1],
                    "best_rho_C": best_allocation[2],
                    "sigma_A": best_sigmas[0],
                    "sigma_B": best_sigmas[1],
                    "sigma_C": best_sigmas[2],
                    "positive_feasible_allocations": positive_count,
                    "n_feasible_allocations": len(feasible_allocations),
                }
            )
    best = pd.DataFrame(best_rows)

    summary = (
        best.groupby("region", as_index=False)
        .agg(
            n_horizons=("horizon", "count"),
            horizons_with_positive_best_product=("best_product", lambda s: int((s > 0.0).sum())),
            max_best_product=("best_product", "max"),
            mean_best_product=("best_product", "mean"),
        )
    )
    summary["fraction_horizons_positive"] = (
        summary["horizons_with_positive_best_product"] / summary["n_horizons"]
    )

    representative = best[best["horizon"].isin([60.0, 120.0, 180.0, 240.0])].copy()

    print("PHASE2_I1_COMPOSABILITY_DIAGNOSTIC_PASS")
    print(f"global_rho={GLOBAL_RHO}")
    print(f"n_feasible_rho_allocations={len(feasible_allocations)}")
    print("selection_performed=false")
    print("card_values_modified=false")
    print("\nMIN_RHO_PROVIDER_CHECK")
    print(floor.to_string(index=False))
    print("\nBEST_FEASIBLE_PRODUCT_REPRESENTATIVE_HORIZONS")
    print(representative.to_string(index=False))
    print("\nBEST_FEASIBLE_PRODUCT_HORIZON_SUMMARY")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
