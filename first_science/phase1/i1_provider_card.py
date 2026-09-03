"""Minimal method-neutral I1 provider SLA card for PRAISE Phase 1.

I1 exposes only provider-local horizon-dependent SLA-compliance probabilities
for explicitly queried local admissibility regions.  The public card contains no
raw traces, generator parameters, provider instruction distributions, seeds, or
top-level white-box information.

The local SLA accounting semantics intentionally match the frozen top-level
Phase-1 semantics: cumulative [0,H] accounting from t=0, timeout at the local
latency deadline, and zero-decided-request compliance equal to one.

The rho dimension is part of I1.  This is required by M0, which may allocate the
global violation allowance across providers and therefore query local rho values
that differ from the top-level rho=0.95.
"""
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from sla_compliance_analysis import (
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
)

I1_CARD_SCHEMA = "PRAISE_I1_PROVIDER_SLA_CARD_V1"
I1_INFORMATION_TECHNOLOGY = "I1_LOCAL_SLA_SIGMA_CARD"
DEFAULT_WILSON_Z_95 = 1.959963984540054

_REQUIRED_LEDGER_COLUMNS = {
    "trajectory",
    "request_id",
    "emission",
    "completion",
    "L",
    "C",
    "Q",
}
_REQUIRED_REGION_FIELDS = {"region_id", "l_max", "c_max", "q_min"}
_REQUIRED_WORKLOAD_FIELDS = {
    "period",
    "accounting_origin",
    "horizon_max",
}

# These fields may exist in the private provider-side acquisition machinery, but
# they are forbidden from the public I1 card metadata/surface.
_FORBIDDEN_PUBLIC_FIELD_NAMES = {
    "seed",
    "seeds",
    "trajectory_seed",
    "instruction_mean",
    "center_instruction_mean",
    "dispersion",
    "instruction_cv",
    "gamma_shape",
    "gamma_scale",
    "raw_trace",
    "raw_traces",
    "top_level_sigma",
    "top_level_whitebox",
}


def wilson_binomial_interval(
    successes: int,
    trials: int,
    z: float = DEFAULT_WILSON_Z_95,
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial probability."""
    k = int(successes)
    n = int(trials)
    if n <= 0:
        raise ValueError("Wilson interval requires at least one trial")
    if k < 0 or k > n:
        raise ValueError("successes must satisfy 0 <= successes <= trials")
    z_value = float(z)
    if z_value <= 0.0:
        raise ValueError("Wilson z value must be positive")

    p = k / n
    z2 = z_value * z_value
    denominator = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denominator
    half_width = (
        z_value
        * sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _validate_private_provider_ledgers(ledgers: pd.DataFrame) -> None:
    missing = _REQUIRED_LEDGER_COLUMNS.difference(ledgers.columns)
    if missing:
        raise ValueError(
            "private provider ledgers missing columns: " + ", ".join(sorted(missing))
        )
    if ledgers.empty:
        raise ValueError("private provider ledgers must not be empty")
    if int(ledgers["trajectory"].nunique()) <= 0:
        raise ValueError("at least one provider trajectory is required")


def _validate_regions(local_regions: list[dict[str, object]]) -> None:
    if not local_regions:
        raise ValueError("I1 requires at least one local admissibility region")
    seen: set[str] = set()
    for region in local_regions:
        missing = _REQUIRED_REGION_FIELDS.difference(region)
        if missing:
            raise ValueError(
                "local region missing fields: " + ", ".join(sorted(missing))
            )
        region_id = str(region["region_id"])
        if not region_id or region_id in seen:
            raise ValueError("local region_id values must be non-empty and unique")
        seen.add(region_id)
        if float(region["l_max"]) < 0.0 or float(region["c_max"]) < 0.0:
            raise ValueError("local l_max and c_max must be non-negative")


def _validate_workload_contract(workload_contract: dict[str, object]) -> None:
    missing = _REQUIRED_WORKLOAD_FIELDS.difference(workload_contract)
    if missing:
        raise ValueError(
            "workload contract missing fields: " + ", ".join(sorted(missing))
        )
    if float(workload_contract["period"]) <= 0.0:
        raise ValueError("workload period must be positive")
    if abs(float(workload_contract["accounting_origin"])) > 1e-12:
        raise ValueError("Phase-1 I1 accounting origin must remain t=0")
    if float(workload_contract["horizon_max"]) <= 0.0:
        raise ValueError("workload horizon_max must be positive")


def _validate_rho_values(rho_values: list[float]) -> None:
    if not rho_values:
        raise ValueError("I1 requires at least one rho value")
    if len(set(rho_values)) != len(rho_values):
        raise ValueError("I1 rho values must be unique")
    for rho in rho_values:
        if not 0.0 < float(rho) <= 1.0:
            raise ValueError("I1 rho values must satisfy 0 < rho <= 1")


def _validate_horizons(horizons: list[float], horizon_max: float) -> None:
    if not horizons:
        raise ValueError("I1 requires at least one horizon")
    if len(set(horizons)) != len(horizons):
        raise ValueError("I1 horizons must be unique")
    if horizons != sorted(horizons):
        raise ValueError("I1 horizons must be sorted")
    if horizons[0] < -1e-12 or horizons[-1] > float(horizon_max) + 1e-12:
        raise ValueError("I1 horizons must lie inside [0,horizon_max]")


def assert_public_i1_card_has_no_forbidden_information(
    metadata: dict[str, object],
    surface: pd.DataFrame,
) -> None:
    """Reject accidental leakage of hidden/provider-private information."""

    def walk_keys(value: object) -> list[str]:
        keys: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                keys.append(str(key))
                keys.extend(walk_keys(child))
        elif isinstance(value, list):
            for child in value:
                keys.extend(walk_keys(child))
        return keys

    public_keys = set(walk_keys(metadata)) | set(map(str, surface.columns))
    leaked = sorted(_FORBIDDEN_PUBLIC_FIELD_NAMES.intersection(public_keys))
    if leaked:
        raise ValueError(
            "public I1 card leaks forbidden information fields: " + ", ".join(leaked)
        )


def build_i1_provider_card(
    provider_id: str,
    private_provider_ledgers: pd.DataFrame,
    local_regions: Iterable[dict[str, object]],
    rho_values: Iterable[float],
    horizons: Iterable[float],
    stop_time: float,
    workload_contract: dict[str, object],
    confidence_z: float = DEFAULT_WILSON_Z_95,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Build the public I1 SLA-sigma card from private provider observations.

    The private ledgers are used only inside this builder.  They are never copied
    into the returned metadata or surface.

    Args:
        provider_id: Public provider label, e.g. ``ProviderA``.
        private_provider_ledgers: One local request ledger per trajectory using
            the same columns as the top-level SLA accounting functions plus a
            ``trajectory`` column.
        local_regions: Explicit provider-local A_i={L<=l,C<=c,Q>=q} queries.
        rho_values: Supported local cumulative SLA fractions.  rho is part of I1.
        horizons: Supported H values.  Phase-1 v1 uses exact-grid queries only.
        stop_time: Provider observation stop time.
        workload_contract: Public workload/context declaration.  Must contain
            period, accounting_origin, and horizon_max.
        confidence_z: Normal quantile used by the Wilson binomial interval.

    Returns:
        ``(metadata, surface)``.  ``surface`` contains one row per
        (local region, rho, horizon) with empirical sigma and a Wilson interval.
    """
    provider = str(provider_id).strip()
    if not provider:
        raise ValueError("provider_id must be non-empty")
    _validate_private_provider_ledgers(private_provider_ledgers)

    regions = [dict(region) for region in local_regions]
    _validate_regions(regions)
    rhos = [float(value) for value in rho_values]
    _validate_rho_values(rhos)
    hs = [float(value) for value in horizons]
    _validate_workload_contract(workload_contract)
    _validate_horizons(hs, float(workload_contract["horizon_max"]))

    stop = float(stop_time)
    if stop <= 0.0 or stop + 1e-12 < float(workload_contract["horizon_max"]):
        raise ValueError("stop_time must cover the complete I1 horizon domain")

    grouped_ledgers = [
        group.copy()
        for _, group in private_provider_ledgers.groupby("trajectory", sort=True)
    ]
    n_trajectories = len(grouped_ledgers)
    rows: list[dict[str, object]] = []

    for region in regions:
        l_max = float(region["l_max"])
        c_max = float(region["c_max"])
        q_min = float(region["q_min"])
        decision_tables = [
            build_request_sla_decision_table(
                ledger,
                latency_threshold=l_max,
                cost_threshold=c_max,
                quality_threshold=q_min,
                stop_time=stop,
            )
            for ledger in grouped_ledgers
        ]

        for rho in rhos:
            definition = SlaComplianceDefinition(
                rho=rho,
                accounting_origin=float(workload_contract["accounting_origin"]),
                zero_decision_compliance=1.0,
            )
            sigma_curve, trajectory_curves = (
                calculate_empirical_sla_sigma_from_decision_tables(
                    decision_tables,
                    hs,
                    definition,
                )
            )
            counts = (
                trajectory_curves.groupby("horizon", as_index=False)
                .agg(
                    n_success=("sla_compliant", "sum"),
                    n_trajectories=("sla_compliant", "count"),
                )
                .sort_values("horizon")
            )
            merged = sigma_curve.merge(counts, on="horizon", validate="one_to_one")
            for row in merged.itertuples(index=False):
                successes = int(row.n_success)
                trials = int(row.n_trajectories)
                lower, upper = wilson_binomial_interval(
                    successes, trials, z=confidence_z
                )
                rows.append(
                    {
                        "provider_id": provider,
                        "region_id": str(region["region_id"]),
                        "l_max": l_max,
                        "c_max": c_max,
                        "q_min": q_min,
                        "rho": rho,
                        "horizon": float(row.horizon),
                        "sigma_hat": float(row.sigma),
                        "sigma_ci95_lower": float(lower),
                        "sigma_ci95_upper": float(upper),
                        "n_success": successes,
                        "n_trajectories": trials,
                    }
                )

    surface = pd.DataFrame(rows).sort_values(
        ["region_id", "rho", "horizon"]
    ).reset_index(drop=True)
    if surface.empty:
        raise RuntimeError("I1 provider-card construction produced no surface rows")
    if set(surface["n_trajectories"].astype(int)) != {n_trajectories}:
        raise RuntimeError("I1 surface trajectory counts are inconsistent")

    metadata: dict[str, object] = {
        "schema": I1_CARD_SCHEMA,
        "information_technology": I1_INFORMATION_TECHNOLOGY,
        "provider_id": provider,
        "status": "PUBLIC_PROVIDER_CARD",
        "semantics": {
            "local_admissibility": "A_i={L_i<=l_max,C_i<=c_max,Q_i>=q_min}",
            "sigma": "P(c_i(A_i,H)>=rho)",
            "accounting_window": "cumulative_[0,H]_from_t0",
            "zero_decided_requests_compliance": 1.0,
            "latency_timeout": "decision_at_local_latency_deadline",
            "cost_quality_after_timeout": "not_evaluated_after_latency_failure",
            "nonmonotone_in_horizon_allowed": True,
        },
        "local_metric_scope": {
            "L_i": "provider-local request arrival to provider completion",
            "C_i": "native provider execution cost for the local request",
            "Q_i": "provider-local observed quality",
        },
        "workload_contract": dict(workload_contract),
        "supported_rho_values": rhos,
        "supported_horizons": hs,
        "n_trajectories": n_trajectories,
        "n_local_regions": len(regions),
        "confidence_interval": "Wilson_95_percent",
        "query_semantics": "exact_supported_points_only_v1",
        "forbidden_public_information": sorted(_FORBIDDEN_PUBLIC_FIELD_NAMES),
    }
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    return metadata, surface


def query_i1_provider_card_exact(
    surface: pd.DataFrame,
    *,
    l_max: float,
    c_max: float,
    q_min: float,
    rho: float,
    horizon: float,
    tolerance: float = 1e-10,
) -> pd.Series:
    """Return one exact supported I1 query point; interpolation is forbidden v1."""
    required = {
        "l_max",
        "c_max",
        "q_min",
        "rho",
        "horizon",
        "sigma_hat",
        "sigma_ci95_lower",
        "sigma_ci95_upper",
    }
    missing = required.difference(surface.columns)
    if missing:
        raise ValueError("I1 surface missing columns: " + ", ".join(sorted(missing)))

    mask = (
        np.isclose(surface["l_max"].astype(float), float(l_max), atol=tolerance, rtol=0.0)
        & np.isclose(surface["c_max"].astype(float), float(c_max), atol=tolerance, rtol=0.0)
        & np.isclose(surface["q_min"].astype(float), float(q_min), atol=tolerance, rtol=0.0)
        & np.isclose(surface["rho"].astype(float), float(rho), atol=tolerance, rtol=0.0)
        & np.isclose(surface["horizon"].astype(float), float(horizon), atol=tolerance, rtol=0.0)
    )
    matches = surface.loc[mask]
    if len(matches) != 1:
        raise KeyError(
            "I1 exact query requires exactly one supported point; "
            f"found {len(matches)}"
        )
    return matches.iloc[0]


def write_i1_provider_card(
    metadata: dict[str, object],
    surface: pd.DataFrame,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Write public metadata JSON and sigma-surface CSV for one provider."""
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    output_directory.mkdir(parents=True, exist_ok=True)
    metadata_path = output_directory / "card.json"
    surface_path = output_directory / "sigma_surface.csv"
    payload = dict(metadata)
    payload["surface_file"] = surface_path.name
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    surface.to_csv(surface_path, index=False)
    return metadata_path, surface_path


def load_i1_provider_card(
    card_directory: Path,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Load and validate one public I1 provider card."""
    metadata_path = card_directory / "card.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema") != I1_CARD_SCHEMA:
        raise ValueError("unexpected I1 provider-card schema")
    surface_name = str(metadata.get("surface_file", "sigma_surface.csv"))
    surface = pd.read_csv(card_directory / surface_name)
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    return metadata, surface
