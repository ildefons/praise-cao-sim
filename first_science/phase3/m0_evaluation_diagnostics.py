"""Evaluation-only diagnostics for the frozen Phase-3 M0 baseline.

This module does not change I1 or M0. It adds two measurements around the
already-frozen method:

1. Global-region agreement between the white-box/reference A_G and the
   bottom-up analytically induced A_G^M0.
2. Sensitivity of the M0 probability-composition operator to the provider-local
   rho vector (rho_A, rho_B, rho_C), using only rho slices already exposed by
   the hash-frozen public I1 cards.

Only the same-rho diagonal rho_A=rho_B=rho_C=rho_G is the official frozen M0
prediction rule. Off-diagonal rho vectors are diagnostic sensitivity points and
must not be interpreted as predictions for a common global rho_G.
"""
from __future__ import annotations

from itertools import product
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from m0_analytic_composition import AdmissibilityBoundary, independent_product_probability

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TOLERANCE = 1e-12


def _boundary_relation(
    induced: AdmissibilityBoundary,
    reference: AdmissibilityBoundary,
    tolerance: float = TOLERANCE,
) -> str:
    """Classify the set relation between A_G^M0 and the reference A_G."""
    tol = float(tolerance)
    same = (
        abs(induced.l_max - reference.l_max) <= tol
        and abs(induced.c_max - reference.c_max) <= tol
        and abs(induced.q_min - reference.q_min) <= tol
    )
    if same:
        return "EQUAL"

    induced_in_reference = (
        induced.l_max <= reference.l_max + tol
        and induced.c_max <= reference.c_max + tol
        and induced.q_min + tol >= reference.q_min
    )
    reference_in_induced = (
        reference.l_max <= induced.l_max + tol
        and reference.c_max <= induced.c_max + tol
        and reference.q_min + tol >= induced.q_min
    )
    if induced_in_reference:
        return "M0_SUBSET_WB"
    if reference_in_induced:
        return "WB_SUBSET_M0"
    return "PARTIAL_OVERLAP"


def boundary_overlap_metrics(
    induced: AdmissibilityBoundary,
    reference: AdmissibilityBoundary,
    *,
    quality_upper: float | None = None,
    tolerance: float = TOLERANCE,
) -> dict[str, float | str | bool]:
    """Measure geometric overlap of two rectangular LCQ admissibility regions.

    Regions have the benchmark form

        0 <= L <= l_max, 0 <= C <= c_max, Q >= q_min.

    In the current frozen benchmark both compared regions have the same quality
    threshold (Q>=0.5). In that case the common Q factor cancels exactly from
    intersection-over-union, so J_A is computed on the L-C projection without
    introducing an arbitrary quality ceiling.

    If quality thresholds differ, callers must provide a finite ``quality_upper``
    defining the evaluation domain for Q. The resulting 3-D Jaccard then uses
    Q in [q_min, quality_upper].
    """
    tol = float(tolerance)
    same_quality_threshold = abs(induced.q_min - reference.q_min) <= tol

    if same_quality_threshold:
        wb_measure = float(reference.l_max * reference.c_max)
        m0_measure = float(induced.l_max * induced.c_max)
        intersection_measure = float(
            min(reference.l_max, induced.l_max)
            * min(reference.c_max, induced.c_max)
        )
        measure_semantics = "LC_projection_exact_same_Q_threshold"
        q_upper_used = float("nan")
    else:
        if quality_upper is None:
            raise ValueError(
                "quality_upper is required when A_G quality thresholds differ"
            )
        q_upper = float(quality_upper)
        if q_upper <= max(reference.q_min, induced.q_min) + tol:
            raise ValueError("quality_upper must exceed both q_min thresholds")
        wb_measure = float(
            reference.l_max * reference.c_max * (q_upper - reference.q_min)
        )
        m0_measure = float(
            induced.l_max * induced.c_max * (q_upper - induced.q_min)
        )
        intersection_measure = float(
            min(reference.l_max, induced.l_max)
            * min(reference.c_max, induced.c_max)
            * (q_upper - max(reference.q_min, induced.q_min))
        )
        measure_semantics = "LCQ_volume_on_declared_finite_Q_domain"
        q_upper_used = q_upper

    union_measure = wb_measure + m0_measure - intersection_measure
    if union_measure <= tol:
        jaccard = 1.0
    else:
        jaccard = intersection_measure / union_measure

    wb_coverage = (
        1.0 if wb_measure <= tol and intersection_measure <= tol
        else intersection_measure / wb_measure if wb_measure > tol
        else 0.0
    )
    m0_coverage = (
        1.0 if m0_measure <= tol and intersection_measure <= tol
        else intersection_measure / m0_measure if m0_measure > tol
        else 0.0
    )

    return {
        "region_relation": _boundary_relation(induced, reference, tolerance=tol),
        "J_A": float(jaccard),
        "intersection_measure": float(intersection_measure),
        "union_measure": float(union_measure),
        "intersection_over_A_G_WB": float(wb_coverage),
        "intersection_over_A_G_M0": float(m0_coverage),
        "delta_l_M0_minus_WB": float(induced.l_max - reference.l_max),
        "delta_c_M0_minus_WB": float(induced.c_max - reference.c_max),
        "delta_q_M0_minus_WB": float(induced.q_min - reference.q_min),
        "measure_semantics": measure_semantics,
        "quality_upper_used": q_upper_used,
        "same_quality_threshold": bool(same_quality_threshold),
    }


def common_rho_support(provider_surfaces: Mapping[str, pd.DataFrame]) -> tuple[float, ...]:
    """Return the exact common public rho support across the required providers."""
    supports: list[tuple[float, ...]] = []
    for provider in PROVIDERS:
        if provider not in provider_surfaces:
            raise KeyError(f"missing public I1 surface for {provider}")
        surface = provider_surfaces[provider]
        if "rho" not in surface.columns:
            raise ValueError(f"{provider} surface has no rho column")
        support = tuple(sorted(set(surface["rho"].astype(float).tolist())))
        supports.append(support)
    if len(set(supports)) != 1:
        raise RuntimeError("provider public I1 rho supports differ")
    return supports[0]


def _exact_sigma(
    surface: pd.DataFrame,
    *,
    rho: float,
    horizon: float,
    tolerance: float = TOLERANCE,
) -> float:
    selected = surface[
        np.isclose(surface["rho"].astype(float), float(rho), atol=tolerance, rtol=0.0)
        & np.isclose(
            surface["horizon"].astype(float), float(horizon), atol=tolerance, rtol=0.0
        )
    ]
    if len(selected) != 1:
        raise RuntimeError(
            f"expected one public I1 point at H={horizon:g}, rho={rho:g}; found {len(selected)}"
        )
    return float(selected.iloc[0]["sigma_hat"])


def build_rho_vector_sigma_family(
    provider_surfaces: Mapping[str, pd.DataFrame],
    horizons: Sequence[float],
    rho_values: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Evaluate the M0 product over the public Cartesian rho-vector support.

    This is an evaluation/sensitivity family. The rows with
    ``is_same_rho_diagonal=True`` coincide with M0's official same-rho rule.
    Off-diagonal rows are deliberately labelled diagnostic-only.
    """
    common_support = common_rho_support(provider_surfaces)
    if rho_values is None:
        selected_support = common_support
    else:
        requested = tuple(float(value) for value in rho_values)
        if len(set(requested)) != len(requested):
            raise ValueError("rho_values must be unique")
        for rho in requested:
            if not any(abs(rho - exposed) <= TOLERANCE for exposed in common_support):
                raise ValueError(f"rho={rho:g} is not exposed by every public I1 card")
        selected_support = requested

    horizon_values = tuple(float(value) for value in horizons)
    if not horizon_values:
        raise ValueError("at least one horizon is required")

    rows: list[dict[str, float | bool | str]] = []
    for rho_a, rho_b, rho_c in product(selected_support, repeat=3):
        diagonal = (
            abs(rho_a - rho_b) <= TOLERANCE
            and abs(rho_a - rho_c) <= TOLERANCE
        )
        vector_role = "OFFICIAL_M0_SAME_RHO_DIAGONAL" if diagonal else "DIAGNOSTIC_RHO_VECTOR_SENSITIVITY"
        for horizon in horizon_values:
            sigma_a = _exact_sigma(
                provider_surfaces["ProviderA"], rho=rho_a, horizon=horizon
            )
            sigma_b = _exact_sigma(
                provider_surfaces["ProviderB"], rho=rho_b, horizon=horizon
            )
            sigma_c = _exact_sigma(
                provider_surfaces["ProviderC"], rho=rho_c, horizon=horizon
            )
            sigma_hat = independent_product_probability(
                {"ProviderA": sigma_a, "ProviderB": sigma_b, "ProviderC": sigma_c}
            )
            rows.append(
                {
                    "rho_ProviderA": float(rho_a),
                    "rho_ProviderB": float(rho_b),
                    "rho_ProviderC": float(rho_c),
                    "is_same_rho_diagonal": bool(diagonal),
                    "rho_vector_role": vector_role,
                    "horizon": float(horizon),
                    "sigma_hat_m0_rho_vector": float(sigma_hat),
                    "sigma_ProviderA": sigma_a,
                    "sigma_ProviderB": sigma_b,
                    "sigma_ProviderC": sigma_c,
                }
            )
    return pd.DataFrame(rows)


def summarize_rho_vector_shapes(
    rho_vector_family: pd.DataFrame,
    *,
    snapshot_horizons: Sequence[float] = (0.0, 60.0, 120.0, 180.0, 240.0),
) -> pd.DataFrame:
    """Summarize each H->sigma_hat curve without assigning a global rho to it."""
    required = {
        "rho_ProviderA", "rho_ProviderB", "rho_ProviderC",
        "is_same_rho_diagonal", "rho_vector_role", "horizon",
        "sigma_hat_m0_rho_vector",
    }
    missing = required.difference(rho_vector_family.columns)
    if missing:
        raise ValueError("rho-vector family missing columns: " + ", ".join(sorted(missing)))

    group_columns = [
        "rho_ProviderA", "rho_ProviderB", "rho_ProviderC",
        "is_same_rho_diagonal", "rho_vector_role",
    ]
    rows: list[dict[str, float | bool | str]] = []
    for keys, curve in rho_vector_family.groupby(group_columns, sort=True, dropna=False):
        ordered = curve.sort_values("horizon")
        h = ordered["horizon"].to_numpy(dtype=float)
        s = ordered["sigma_hat_m0_rho_vector"].to_numpy(dtype=float)
        if len(h) == 1:
            normalized_area = float(s[0])
        else:
            duration = float(h[-1] - h[0])
            if duration <= 0.0:
                raise ValueError("rho-vector horizons must span a positive interval")
            area = float(np.trapz(s, h))
            normalized_area = area / duration

        row: dict[str, float | bool | str] = {
            "rho_ProviderA": float(keys[0]),
            "rho_ProviderB": float(keys[1]),
            "rho_ProviderC": float(keys[2]),
            "is_same_rho_diagonal": bool(keys[3]),
            "rho_vector_role": str(keys[4]),
            "normalized_sigma_area": float(normalized_area),
            "sigma_min": float(np.min(s)),
            "sigma_max": float(np.max(s)),
        }
        for target in snapshot_horizons:
            mask = np.isclose(h, float(target), atol=TOLERANCE, rtol=0.0)
            if int(mask.sum()) == 1:
                row[f"sigma_H{float(target):g}"] = float(s[mask][0])
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["rho_ProviderA", "rho_ProviderB", "rho_ProviderC"]
    ).reset_index(drop=True)
