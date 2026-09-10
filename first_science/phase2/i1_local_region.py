"""Deterministic provider-local A_i construction from T_i and rho_G.

Scientific rule
---------------
For one provider i, let T_i contain completed finite local observations
(L_i,C_i,Q_i). A single common empirical rank k defines the rectangular region

    A_i(k) = {L_i <= L_(k), C_i <= C_(k), Q_i >= Q_[k]},

where L_(k) and C_(k) are the kth ascending order statistics and Q_[k] is the
kth descending order statistic, all on the same joint-finite provider sample.
Choose the smallest rank k whose *joint* empirical coverage reaches rho_G:

    k_i* = min {k : P_hat_Ti[(L,C,Q) in A_i(k)] >= rho_G}.

This avoids the incorrect construction that separately placed every coordinate
at marginal rho_G coverage. The rule uses only T_i and rho_G. It does not use a
provider-local rho_i, a sigma target, A_G, M0/M1 outputs, or hidden generator
parameters.
"""
from __future__ import annotations

from math import ceil
from typing import Mapping

import numpy as np
import pandas as pd

EVENT_TOLERANCE = 1e-12
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
_REQUIRED_COLUMNS = {"L", "C", "Q"}


def _joint_finite_lcq(ledger: pd.DataFrame) -> pd.DataFrame:
    """Return exactly the rows where L, C and Q are all finite."""
    missing = _REQUIRED_COLUMNS.difference(ledger.columns)
    if missing:
        raise ValueError(
            "provider ledger missing columns: " + ", ".join(sorted(missing))
        )

    lcq = ledger[["L", "C", "Q"]].apply(pd.to_numeric, errors="coerce")
    values = lcq.to_numpy(dtype=float)
    finite_mask = np.isfinite(values).all(axis=1)
    joint = lcq.loc[finite_mask].reset_index(drop=True)
    if joint.empty:
        raise ValueError("cannot derive A_i from no joint-finite L/C/Q observations")
    return joint


def _candidate_at_common_rank(
    l_values: np.ndarray,
    c_values: np.ndarray,
    q_values: np.ndarray,
    sorted_l: np.ndarray,
    sorted_c: np.ndarray,
    sorted_q_desc: np.ndarray,
    rank: int,
) -> tuple[float, float, float, float, float, float, float]:
    """Return thresholds and joint/marginal coverages for one 1-based rank."""
    k = int(rank)
    n = len(l_values)
    if k < 1 or k > n:
        raise ValueError("common rank must lie in [1,n]")

    l_max = float(sorted_l[k - 1])
    c_max = float(sorted_c[k - 1])
    q_min = float(sorted_q_desc[k - 1])

    l_ok = l_values <= l_max + EVENT_TOLERANCE
    c_ok = c_values <= c_max + EVENT_TOLERANCE
    q_ok = q_values + EVENT_TOLERANCE >= q_min
    joint_ok = l_ok & c_ok & q_ok

    return (
        l_max,
        c_max,
        q_min,
        float(np.mean(joint_ok)),
        float(np.mean(l_ok)),
        float(np.mean(c_ok)),
        float(np.mean(q_ok)),
    )


def derive_joint_common_rank_region(
    provider_id: str,
    ledger: pd.DataFrame,
    rho_global: float,
) -> tuple[dict[str, object], dict[str, object]]:
    """Derive one A_i from a provider trace and rho_G by joint common rank.

    The predicate "joint coverage >= rho_G" is monotone in k because increasing
    k can only relax all three rectangular thresholds. A binary search therefore
    finds the minimal satisfying rank without an O(n^2) scan.
    """
    rho_g = float(rho_global)
    if not 0.0 < rho_g <= 1.0:
        raise ValueError("rho_global must lie in (0,1]")

    joint = _joint_finite_lcq(ledger)
    l_values = joint["L"].to_numpy(dtype=float)
    c_values = joint["C"].to_numpy(dtype=float)
    q_values = joint["Q"].to_numpy(dtype=float)
    n = len(joint)

    sorted_l = np.sort(l_values)
    sorted_c = np.sort(c_values)
    sorted_q_desc = np.sort(q_values)[::-1]

    # A rank below ceil(rho_G*n) cannot have marginal empirical coverage rho_G
    # in every coordinate, so it cannot be the first joint-feasible rank.
    low = max(1, int(ceil(rho_g * n)))
    high = n

    def evaluate(rank: int) -> tuple[float, float, float, float, float, float, float]:
        return _candidate_at_common_rank(
            l_values,
            c_values,
            q_values,
            sorted_l,
            sorted_c,
            sorted_q_desc,
            rank,
        )

    # At k=n the rectangle spans every joint-finite observation, hence coverage=1.
    if evaluate(high)[3] + EVENT_TOLERANCE < rho_g:
        raise RuntimeError("full common-rank rectangle failed to cover the finite sample")

    while low < high:
        mid = (low + high) // 2
        if evaluate(mid)[3] + EVENT_TOLERANCE >= rho_g:
            high = mid
        else:
            low = mid + 1

    rank = low
    (
        l_max,
        c_max,
        q_min,
        joint_coverage,
        l_coverage,
        c_coverage,
        q_coverage,
    ) = evaluate(rank)

    previous_joint_coverage: float | None = None
    if rank > 1:
        previous_joint_coverage = evaluate(rank - 1)[3]
        if previous_joint_coverage + EVENT_TOLERANCE >= rho_g:
            raise RuntimeError("binary search did not return the minimal feasible common rank")

    if joint_coverage + EVENT_TOLERANCE < rho_g:
        raise RuntimeError("derived A_i does not reach requested joint empirical coverage")

    region = {
        "region_id": f"{provider_id}_JOINT_COMMON_RANK_RHOG_V1",
        "l_max": l_max,
        "c_max": c_max,
        "q_min": q_min,
    }
    diagnostics = {
        "provider": str(provider_id),
        "rho_global": rho_g,
        "n_joint_finite": int(n),
        "common_rank": int(rank),
        "common_rank_fraction": float(rank / n),
        "joint_coverage": joint_coverage,
        "previous_rank_joint_coverage": previous_joint_coverage,
        "marginal_L_coverage": l_coverage,
        "marginal_C_coverage": c_coverage,
        "marginal_Q_coverage": q_coverage,
        "l_max": l_max,
        "c_max": c_max,
        "q_min": q_min,
        "rule": "minimal_common_rank_with_joint_empirical_coverage_at_least_rho_G",
    }
    return region, diagnostics


def derive_local_regions_from_traces(
    provider_ledgers: Mapping[str, pd.DataFrame],
    rho_global: float,
) -> tuple[dict[str, dict[str, object]], pd.DataFrame]:
    """Derive A_A,A_B,A_C from their own T_i and the common rho_G."""
    if set(provider_ledgers) != set(PROVIDERS):
        raise ValueError("provider ledgers must contain exactly ProviderA/B/C")

    regions: dict[str, dict[str, object]] = {}
    diagnostics: list[dict[str, object]] = []
    for provider in PROVIDERS:
        region, row = derive_joint_common_rank_region(
            provider,
            provider_ledgers[provider],
            rho_global,
        )
        regions[provider] = region
        diagnostics.append(row)

    return regions, pd.DataFrame(diagnostics)
