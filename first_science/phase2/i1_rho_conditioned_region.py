"""Rho-conditioned local admissibility regions for I1.

This module replaces the historical single-A_i calibration with a trace-native
joint distribution construction for the current Phase-1/2 benchmark.

For provider evidence T_i and a predeclared region-content level rho_region,
it fits a Gaussian mixture to (log L, log C), chooses K by BIC, samples that
joint model deterministically, and extracts the minimum-area origin-anchored
rectangle containing at least rho_region model mass. Regions are extracted in
ascending rho_region with nesting enforced.

Current benchmark Q is constant. The implementation refuses non-degenerate Q
rather than inventing a general multivariate quality-region rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

REQUIRED_LEDGER_COLUMNS = {"trajectory", "completion", "L", "C", "Q"}
DEFAULT_RANDOM_STATE = 271828
DEFAULT_MAX_COMPONENTS = 4
DEFAULT_MODEL_SAMPLES = 100_000
TOLERANCE = 1e-12


@dataclass(frozen=True)
class LogLCGMMFit:
    """Private fit object. GMM parameters never belong in the public I1 card."""

    model: GaussianMixture
    n_components: int
    bic_by_components: dict[int, float]
    n_fit_rows: int
    q_value: float


class _Fenwick:
    """Fenwick tree for exact order statistics on one empirical joint sample."""

    def __init__(self, size: int) -> None:
        self.tree = np.zeros(int(size) + 1, dtype=np.int64)

    def add(self, index0: int, value: int = 1) -> None:
        i = int(index0) + 1
        while i < len(self.tree):
            self.tree[i] += int(value)
            i += i & -i

    def prefix_sum(self, index0: int) -> int:
        i = int(index0) + 1
        total = 0
        while i > 0:
            total += int(self.tree[i])
            i -= i & -i
        return total

    def kth(self, k: int) -> int:
        """Return zero-based index of the k-th inserted item, where k is 1-based."""
        total = self.prefix_sum(len(self.tree) - 2)
        if k <= 0 or k > total:
            raise ValueError("k outside inserted Fenwick mass")
        idx = 0
        bit = 1 << (len(self.tree).bit_length() - 1)
        while bit:
            nxt = idx + bit
            if nxt < len(self.tree) and self.tree[nxt] < k:
                idx = nxt
                k -= int(self.tree[nxt])
            bit >>= 1
        return idx


def _completed_log_lc_and_q(
    provider_ledger: pd.DataFrame,
) -> tuple[np.ndarray, float]:
    missing = REQUIRED_LEDGER_COLUMNS.difference(provider_ledger.columns)
    if missing:
        raise ValueError(
            "provider ledger missing columns: " + ", ".join(sorted(missing))
        )
    completed = provider_ledger[
        provider_ledger["completion"].notna()
        & provider_ledger["L"].notna()
        & provider_ledger["C"].notna()
        & provider_ledger["Q"].notna()
    ].copy()
    if completed.empty:
        raise ValueError(
            "no completed provider samples available for rho-conditioned I1"
        )
    lc = completed[["L", "C"]].astype(float).to_numpy()
    if not np.all(np.isfinite(lc)) or np.any(lc <= 0.0):
        raise ValueError(
            "completed L and C samples must be finite and strictly positive"
        )
    q = completed["Q"].astype(float).to_numpy()
    if not np.all(np.isfinite(q)):
        raise ValueError("completed Q samples must be finite")
    if float(np.max(q) - np.min(q)) > TOLERANCE:
        raise NotImplementedError(
            "rho-conditioned I1 v1 supports the current degenerate-Q benchmark only"
        )
    return np.log(lc), float(q[0])


def fit_log_lc_gmm(
    provider_ledger: pd.DataFrame,
    *,
    max_components: int = DEFAULT_MAX_COMPONENTS,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> LogLCGMMFit:
    """Fit a full-covariance log(L,C) GMM and choose K by minimum BIC."""
    x, q_value = _completed_log_lc_and_q(provider_ledger)
    max_k = int(max_components)
    if max_k < 1:
        raise ValueError("max_components must be >= 1")
    max_k = min(max_k, len(x))

    models: dict[int, GaussianMixture] = {}
    bic: dict[int, float] = {}
    for k in range(1, max_k + 1):
        model = GaussianMixture(
            n_components=k,
            covariance_type="full",
            reg_covar=1e-8,
            n_init=3,
            max_iter=500,
            random_state=int(random_state) + k,
        )
        model.fit(x)
        models[k] = model
        bic[k] = float(model.bic(x))

    chosen = min(bic, key=lambda k: (bic[k], k))
    return LogLCGMMFit(
        model=models[chosen],
        n_components=int(chosen),
        bic_by_components=bic,
        n_fit_rows=int(len(x)),
        q_value=q_value,
    )


def draw_joint_lc_samples(
    fit: LogLCGMMFit,
    *,
    n_samples: int = DEFAULT_MODEL_SAMPLES,
) -> np.ndarray:
    """Draw deterministic positive (L,C) samples from the fitted log-GMM."""
    n = int(n_samples)
    if n < 1000:
        raise ValueError("n_samples must be >= 1000 for stable region extraction")
    log_lc, _ = fit.model.sample(n)
    lc = np.exp(log_lc)
    if not np.all(np.isfinite(lc)) or np.any(lc <= 0.0):
        raise RuntimeError("log-GMM produced invalid L/C samples")
    return lc


def _minimum_area_box_for_mass(
    lc_samples: np.ndarray,
    rho: float,
    *,
    lower_l: float = 0.0,
    lower_c: float = 0.0,
) -> tuple[float, float, float]:
    """Exact minimum-area origin box on an empirical joint sample.

    Among rectangles [0,l]x[0,c] containing at least ceil(rho*n) sampled
    points, find the minimum l*c subject to l>=lower_l and c>=lower_c.
    """
    samples = np.asarray(lc_samples, dtype=float)
    if samples.ndim != 2 or samples.shape[1] != 2 or len(samples) == 0:
        raise ValueError("lc_samples must have shape (n,2)")
    if not 0.0 < float(rho) < 1.0:
        raise ValueError("rho region content must satisfy 0 < rho < 1")
    n = len(samples)
    required = int(ceil(float(rho) * n))

    order_l = np.argsort(samples[:, 0], kind="mergesort")
    ordered_l = samples[order_l, 0]
    ordered_c = samples[order_l, 1]

    c_values = np.sort(np.unique(samples[:, 1]))
    c_ranks = np.searchsorted(c_values, ordered_c, side="left")
    fenwick = _Fenwick(len(c_values))

    best: tuple[float, float, float] | None = None
    for j in range(n):
        fenwick.add(int(c_ranks[j]))
        if j + 1 < required:
            continue
        if float(ordered_l[j]) + TOLERANCE < float(lower_l):
            continue
        l = float(ordered_l[j])
        c_mass = float(c_values[fenwick.kth(required)])
        c = max(c_mass, float(lower_c))
        area = l * c
        candidate = (area, l, c)
        if best is None or candidate < best:
            best = candidate

    if best is None:
        raise RuntimeError("could not find a nested box satisfying requested mass")

    _, l_best, c_best = best
    inside = (
        (samples[:, 0] <= l_best + TOLERANCE)
        & (samples[:, 1] <= c_best + TOLERANCE)
    )
    coverage = float(np.mean(inside))
    if coverage + 1.0 / n < float(rho):
        raise RuntimeError("extracted box failed requested model-mass constraint")
    return l_best, c_best, coverage


def derive_nested_rho_regions(
    provider_ledger: pd.DataFrame,
    rho_values: Iterable[float],
    *,
    max_components: int = DEFAULT_MAX_COMPONENTS,
    model_samples: int = DEFAULT_MODEL_SAMPLES,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    """Derive A_i(rho_region) from one provider's private evidence.

    The GMM is fit once. A single deterministic joint sample is drawn from it.
    Region levels are processed in ascending order and constrained to contain
    the preceding region, so A_i(rho_1) subseteq A_i(rho_2) whenever rho_1<rho_2.
    """
    rho_support = tuple(float(r) for r in rho_values)
    if not rho_support or len(set(rho_support)) != len(rho_support):
        raise ValueError("rho_values must be non-empty and unique")
    if tuple(sorted(rho_support)) != rho_support:
        raise ValueError("rho_values must be sorted")
    if any(not 0.0 < r < 1.0 for r in rho_support):
        raise ValueError(
            "rho-conditioned finite GMM regions require 0 < rho < 1"
        )

    fit = fit_log_lc_gmm(
        provider_ledger,
        max_components=max_components,
        random_state=random_state,
    )
    samples = draw_joint_lc_samples(fit, n_samples=model_samples)

    regions: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    lower_l = 0.0
    lower_c = 0.0
    for rho in rho_support:
        l_max, c_max, coverage = _minimum_area_box_for_mass(
            samples,
            rho,
            lower_l=lower_l,
            lower_c=lower_c,
        )
        region_id = (
            f"rho_region_{rho:.9f}".rstrip("0").rstrip(".").replace(".", "p")
        )
        region = {
            "region_id": region_id,
            "region_rho": float(rho),
            "l_max": float(l_max),
            "c_max": float(c_max),
            "q_min": float(fit.q_value),
        }
        regions.append(region)
        audit_rows.append(
            {
                **region,
                "synthetic_model_coverage": float(coverage),
                "gmm_n_components": int(fit.n_components),
                "gmm_fit_rows": int(fit.n_fit_rows),
                "gmm_bic": float(fit.bic_by_components[fit.n_components]),
                "model_samples": int(model_samples),
            }
        )
        lower_l = l_max
        lower_c = c_max

    for previous, current in zip(regions, regions[1:]):
        if (
            float(current["l_max"]) + TOLERANCE < float(previous["l_max"])
            or float(current["c_max"]) + TOLERANCE < float(previous["c_max"])
            or abs(float(current["q_min"]) - float(previous["q_min"])) > TOLERANCE
        ):
            raise RuntimeError("rho-conditioned regions are not nested")

    return regions, pd.DataFrame(audit_rows)
