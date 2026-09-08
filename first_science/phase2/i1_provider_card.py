"""Build and validate the frozen Phase-2 public I1 provider card.

Scientific role
---------------
The private Phase-2 acquisition corpus contains provider-local request evidence.
This module converts that evidence into the public information technology I1:

    sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)

for exact predeclared provider-local admissibility regions A_i and the frozen
H x rho support. I1 does not choose A_i. A consuming method declares the exact
A_i query first; this module only materializes the corresponding surface.

Main call path
--------------
``materialize_i1_cards.materialize_cards`` -> ``build_i1_provider_card``
-> frozen Phase-1 SLA decision/accounting functions -> public H x rho surface
-> ``write_i1_provider_card``.

Information boundary
--------------------
Provider traces, acquisition seeds, hidden generator parameters, and Phase-1
top-level white-box outcomes are forbidden from the public card. The same
materialized card is intended to be supplied unchanged to M0 and M1.
"""
from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PHASE1_DIRECTORY = Path(__file__).resolve().parents[1] / "phase1"
if str(PHASE1_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(PHASE1_DIRECTORY))

from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
)

I1_CARD_SCHEMA = "PRAISE_I1_PROVIDER_SLA_CARD_V1"
I1_INFORMATION_TECHNOLOGY = "I1_LOCAL_SLA_SIGMA_SURFACE_CARD"
DEFAULT_WILSON_Z_95 = 1.959963984540054

_REQUIRED_LEDGER_COLUMNS = {
    "trajectory", "request_id", "emission", "completion", "L", "C", "Q"
}
_REQUIRED_REGION_FIELDS = {"region_id", "l_max", "c_max", "q_min"}
_REQUIRED_WORKLOAD_FIELDS = {"period", "accounting_origin", "horizon_max"}

_FORBIDDEN_PUBLIC_FIELD_NAMES = {
    "seed",
    "seeds",
    "seed_bank",
    "trajectory_seed",
    "instruction_mean",
    "provider_instruction_mean",
    "center_instruction_mean",
    "physical_setting_id",
    "dispersion",
    "delta",
    "instruction_cv",
    "gamma_shape",
    "gamma_scale",
    "raw_trace",
    "raw_traces",
    "private_provider_ledgers",
    "top_level_sigma",
    "top_level_whitebox",
}


def wilson_binomial_interval(
    successes: int,
    trials: int,
    z: float = DEFAULT_WILSON_Z_95,
) -> tuple[float, float]:
    """Return the Wilson 95%-style interval for one empirical sigma estimate.

    Here one Bernoulli trial is one *trajectory*, not one request. A trajectory
    is a success at (A_i,H,rho) when its cumulative decided-request compliance
    fraction is at least rho.
    """
    success_count = int(successes)
    trial_count = int(trials)
    z_value = float(z)
    if trial_count <= 0:
        raise ValueError("Wilson interval requires at least one trial")
    if success_count < 0 or success_count > trial_count:
        raise ValueError("successes must satisfy 0 <= successes <= trials")
    if z_value <= 0.0:
        raise ValueError("Wilson z value must be positive")

    probability_hat = success_count / trial_count
    z_squared = z_value * z_value
    denominator = 1.0 + z_squared / trial_count
    center = (
        probability_hat + z_squared / (2.0 * trial_count)
    ) / denominator
    half_width = (
        z_value
        * sqrt(
            (probability_hat * (1.0 - probability_hat) / trial_count)
            + z_squared / (4.0 * trial_count * trial_count)
        )
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _validate_i1_card_inputs(
    private_provider_ledgers: pd.DataFrame,
    local_regions: list[dict[str, object]],
    rho_support: list[float],
    horizon_support: list[float],
    workload_contract: dict[str, object],
    stop_time: float,
) -> None:
    """Validate the exact inputs allowed to materialize a frozen I1 card.

    This validation protects the scientific contract rather than merely Python
    types: the private corpus must contain the provider-local evidence schema,
    A_i queries must be explicit and unique, H and rho supports must be sorted
    and finite within the frozen workload domain, and t=0 accounting must remain
    unchanged.

    Called by
    ---------
    ``build_i1_provider_card``.
    """
    missing_ledger_columns = _REQUIRED_LEDGER_COLUMNS.difference(
        private_provider_ledgers.columns
    )
    if missing_ledger_columns:
        raise ValueError(
            "private provider ledgers missing columns: "
            + ", ".join(sorted(missing_ledger_columns))
        )
    if (
        private_provider_ledgers.empty
        or int(private_provider_ledgers["trajectory"].nunique()) <= 0
    ):
        raise ValueError("at least one private provider trajectory is required")

    if not local_regions:
        raise ValueError("I1 requires at least one exact local admissibility region")
    seen_region_ids: set[str] = set()
    for local_region in local_regions:
        missing_region_fields = _REQUIRED_REGION_FIELDS.difference(local_region)
        if missing_region_fields:
            raise ValueError(
                "local region missing fields: "
                + ", ".join(sorted(missing_region_fields))
            )
        region_id = str(local_region["region_id"])
        if not region_id or region_id in seen_region_ids:
            raise ValueError("local region_id values must be non-empty and unique")
        seen_region_ids.add(region_id)
        if (
            float(local_region["l_max"]) < 0.0
            or float(local_region["c_max"]) < 0.0
        ):
            raise ValueError("local l_max and c_max must be non-negative")

    if not rho_support or len(set(rho_support)) != len(rho_support):
        raise ValueError("I1 rho values must be non-empty and unique")
    if rho_support != sorted(rho_support):
        raise ValueError("I1 rho values must be sorted")
    if any(not 0.0 < rho <= 1.0 for rho in rho_support):
        raise ValueError("I1 rho values must satisfy 0 < rho <= 1")

    missing_workload_fields = _REQUIRED_WORKLOAD_FIELDS.difference(
        workload_contract
    )
    if missing_workload_fields:
        raise ValueError(
            "workload contract missing fields: "
            + ", ".join(sorted(missing_workload_fields))
        )
    if float(workload_contract["period"]) <= 0.0:
        raise ValueError("workload period must be positive")
    if abs(float(workload_contract["accounting_origin"])) > 1e-12:
        raise ValueError("I1 accounting origin must remain t=0")

    horizon_max = float(workload_contract["horizon_max"])
    if horizon_max <= 0.0:
        raise ValueError("workload horizon_max must be positive")

    if not horizon_support or len(set(horizon_support)) != len(horizon_support):
        raise ValueError("I1 horizons must be non-empty and unique")
    if horizon_support != sorted(horizon_support):
        raise ValueError("I1 horizons must be sorted")
    if (
        horizon_support[0] < -1e-12
        or horizon_support[-1] > horizon_max + 1e-12
    ):
        raise ValueError("I1 horizons must lie inside [0,horizon_max]")
    if float(stop_time) + 1e-12 < horizon_max:
        raise ValueError("stop_time must cover the complete I1 horizon domain")


def assert_public_i1_card_has_no_forbidden_information(
    metadata: dict[str, object],
    surface: pd.DataFrame,
) -> None:
    """Enforce the public/private information firewall for I1.

    Scientific purpose
    ------------------
    M0 and M1 are allowed to see only the public I1 representation. This check
    rejects accidental leakage of acquisition seeds, hidden physical parameters,
    raw traces, private ledgers, or Phase-1 top-level white-box outcomes through
    either metadata keys or public surface columns.
    """

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
    leaked_fields = sorted(_FORBIDDEN_PUBLIC_FIELD_NAMES.intersection(public_keys))
    if leaked_fields:
        raise ValueError(
            "public I1 card leaks forbidden fields: "
            + ", ".join(leaked_fields)
        )


def assert_i1_surface_monotone_in_rho(
    surface: pd.DataFrame,
    tolerance: float = 1e-12,
) -> None:
    """Check the invariant rho -> P(c_i>=rho) is non-increasing at fixed H.

    The surface is allowed to be non-monotone in horizon because cumulative SLA
    compliance can recover after later successful requests. Monotonicity in rho,
    however, is a mathematical identity and therefore a hard validation rule.
    """
    required_columns = {"region_id", "horizon", "rho", "sigma_hat"}
    missing_columns = required_columns.difference(surface.columns)
    if missing_columns:
        raise ValueError("I1 surface missing monotonicity columns")

    for (_, _), fixed_region_horizon_surface in surface.groupby(
        ["region_id", "horizon"], sort=False
    ):
        ordered_by_rho = fixed_region_horizon_surface.sort_values("rho")
        sigma_values = ordered_by_rho["sigma_hat"].astype(float).to_numpy()
        if np.any(
            sigma_values[:-1] + float(tolerance) < sigma_values[1:]
        ):
            raise RuntimeError("I1 sigma surface violates monotonicity in rho")


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
    """Materialize one provider's public I1 H x rho SLA-compliance surface.

    Scientific object
    -----------------
    For every exact requested A_i, every frozen horizon H, and every frozen rho,
    estimate

        sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)

    by giving equal Monte Carlo weight to each private provider trajectory.

    Important boundary
    ------------------
    This function does not choose A_i and does not run the simulator. It receives
    an exact A_i query from the consuming method and deterministically reduces
    the already frozen Phase-2 provider corpus using the frozen Phase-1 SLA
    decision/accounting semantics.

    Returns
    -------
    ``metadata`` describing the public card contract and ``surface`` containing
    the exact materialized (A_i,H,rho) points with empirical sigma and Wilson
    intervals.

    Called by
    ---------
    ``materialize_i1_cards.materialize_cards`` and simulator-independent tests.
    """
    provider = str(provider_id).strip()
    if not provider:
        raise ValueError("provider_id must be non-empty")

    requested_local_regions = [dict(region) for region in local_regions]
    rho_support = [float(value) for value in rho_values]
    horizon_support = [float(value) for value in horizons]
    _validate_i1_card_inputs(
        private_provider_ledgers,
        requested_local_regions,
        rho_support,
        horizon_support,
        workload_contract,
        stop_time,
    )

    # One Monte Carlo trial is one provider trajectory. Requests within a
    # trajectory determine c_i(A_i,H); they do not receive independent sigma
    # weight.
    trajectory_ledgers = [
        trajectory_ledger.copy()
        for _, trajectory_ledger in private_provider_ledgers.groupby(
            "trajectory", sort=True
        )
    ]
    number_of_trajectories = len(trajectory_ledgers)
    surface_rows: list[dict[str, object]] = []

    for local_region in requested_local_regions:
        latency_threshold = float(local_region["l_max"])
        cost_threshold = float(local_region["c_max"])
        quality_threshold = float(local_region["q_min"])

        # REQUEST-LEVEL SLA STEP.
        # Reuse the frozen Phase-1 accounting semantics read-only. Each private
        # provider trajectory becomes one request-decision table for this A_i.
        decision_tables = [
            build_request_sla_decision_table(
                trajectory_ledger,
                latency_threshold=latency_threshold,
                cost_threshold=cost_threshold,
                quality_threshold=quality_threshold,
                stop_time=float(stop_time),
            )
            for trajectory_ledger in trajectory_ledgers
        ]

        # H x R SURFACE STEP.
        # The request decisions do not depend on rho, so the same decision tables
        # are reused across every frozen rho contour.
        for rho in rho_support:
            sla_definition = SlaComplianceDefinition(
                rho=rho,
                accounting_origin=float(workload_contract["accounting_origin"]),
                zero_decision_compliance=1.0,
            )
            sigma_curve, trajectory_compliance_curves = (
                calculate_empirical_sla_sigma_from_decision_tables(
                    decision_tables, horizon_support, sla_definition
                )
            )
            success_counts_by_horizon = (
                trajectory_compliance_curves.groupby("horizon", as_index=False)
                .agg(
                    n_success=("sla_compliant", "sum"),
                    n_trajectories=("sla_compliant", "count"),
                )
                .sort_values("horizon")
            )
            sigma_with_counts = sigma_curve.merge(
                success_counts_by_horizon,
                on="horizon",
                validate="one_to_one",
            )

            for sigma_point in sigma_with_counts.itertuples(index=False):
                success_count = int(sigma_point.n_success)
                trial_count = int(sigma_point.n_trajectories)
                confidence_lower, confidence_upper = wilson_binomial_interval(
                    success_count, trial_count, z=confidence_z
                )
                surface_rows.append(
                    {
                        "provider_id": provider,
                        "region_id": str(local_region["region_id"]),
                        "l_max": latency_threshold,
                        "c_max": cost_threshold,
                        "q_min": quality_threshold,
                        "rho": rho,
                        "horizon": float(sigma_point.horizon),
                        "sigma_hat": float(sigma_point.sigma),
                        "sigma_ci95_lower": float(confidence_lower),
                        "sigma_ci95_upper": float(confidence_upper),
                        "n_success": success_count,
                        "n_trajectories": trial_count,
                    }
                )

    surface = pd.DataFrame(surface_rows).sort_values(
        ["region_id", "rho", "horizon"]
    ).reset_index(drop=True)
    if surface.empty:
        raise RuntimeError("I1 provider-card surface is empty")
    if set(surface["n_trajectories"].astype(int)) != {
        number_of_trajectories
    }:
        raise RuntimeError("I1 provider-card trajectory counts are inconsistent")
    assert_i1_surface_monotone_in_rho(surface)

    metadata: dict[str, object] = {
        "schema": I1_CARD_SCHEMA,
        "information_technology": I1_INFORMATION_TECHNOLOGY,
        "provider_id": provider,
        "status": "PUBLIC_PROVIDER_SIGMA_SURFACE_CARD",
        "phase": "phase2_i1",
        "card_instance": "I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho)})",
        "semantics": {
            "local_admissibility": "A_i={L_i<=l_max,C_i<=c_max,Q_i>=q_min}",
            "sigma": "P(c_i(A_i,H)>=rho)",
            "accounting_window": "cumulative_[0,H]_from_t0",
            "zero_decided_requests_compliance": 1.0,
            "latency_timeout": "decision_at_provider_local_latency_deadline",
            "cost_quality_after_timeout": "not_evaluated_after_latency_failure",
            "unresolved_at_H": "excluded_from_c_i_denominator",
            "nonmonotone_in_horizon_allowed": True,
            "monotone_in_rho_at_fixed_H": True,
        },
        "local_metric_scope": {
            "L_i": "provider-local request arrival to provider completion including queue wait and service",
            "C_i": "native provider execution cost for the local request",
            "Q_i": "provider-local observed quality",
        },
        "workload_contract": dict(workload_contract),
        "supported_rho_values": rho_support,
        "supported_horizons": horizon_support,
        "n_trajectories": number_of_trajectories,
        "n_local_regions": len(requested_local_regions),
        "confidence_interval": "Wilson_95_percent",
        "query_semantics": "exact_materialized_A_i_H_rho_points_only_v1",
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
    """Return exactly one previously materialized (A_i,H,rho) surface point.

    I1 v1 deliberately provides no interpolation or extrapolation. A consuming
    method must request a point that exists exactly in the materialized card.
    """
    required_columns = {
        "l_max",
        "c_max",
        "q_min",
        "rho",
        "horizon",
        "sigma_hat",
        "sigma_ci95_lower",
        "sigma_ci95_upper",
    }
    missing_columns = required_columns.difference(surface.columns)
    if missing_columns:
        raise ValueError(
            "I1 surface missing columns: " + ", ".join(sorted(missing_columns))
        )

    exact_point_mask = (
        np.isclose(
            surface["l_max"].astype(float),
            float(l_max),
            atol=tolerance,
            rtol=0.0,
        )
        & np.isclose(
            surface["c_max"].astype(float),
            float(c_max),
            atol=tolerance,
            rtol=0.0,
        )
        & np.isclose(
            surface["q_min"].astype(float),
            float(q_min),
            atol=tolerance,
            rtol=0.0,
        )
        & np.isclose(
            surface["rho"].astype(float),
            float(rho),
            atol=tolerance,
            rtol=0.0,
        )
        & np.isclose(
            surface["horizon"].astype(float),
            float(horizon),
            atol=tolerance,
            rtol=0.0,
        )
    )
    matching_points = surface.loc[exact_point_mask]
    if len(matching_points) != 1:
        raise KeyError(
            "I1 exact query requires exactly one materialized point; "
            f"found {len(matching_points)}"
        )
    return matching_points.iloc[0]


def write_i1_provider_card(
    metadata: dict[str, object],
    surface: pd.DataFrame,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Write one validated public I1 card as metadata JSON plus surface CSV."""
    assert_i1_surface_monotone_in_rho(surface)
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    output_directory.mkdir(parents=True, exist_ok=True)

    metadata_path = output_directory / "card.json"
    surface_path = output_directory / "sigma_surface.csv"
    public_metadata = dict(metadata)
    public_metadata["surface_file"] = surface_path.name
    metadata_path.write_text(
        json.dumps(public_metadata, indent=2), encoding="utf-8"
    )
    surface.to_csv(surface_path, index=False)
    return metadata_path, surface_path


def load_i1_provider_card(
    card_directory: Path,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Load one public I1 card and re-enforce its public invariants."""
    metadata = json.loads(
        (card_directory / "card.json").read_text(encoding="utf-8")
    )
    if metadata.get("schema") != I1_CARD_SCHEMA:
        raise ValueError("unexpected I1 provider-card schema")
    surface_name = str(metadata.get("surface_file", "sigma_surface.csv"))
    surface = pd.read_csv(card_directory / surface_name)
    assert_i1_surface_monotone_in_rho(surface)
    assert_public_i1_card_has_no_forbidden_information(metadata, surface)
    return metadata, surface
