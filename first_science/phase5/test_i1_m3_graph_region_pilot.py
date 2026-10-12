"""Engineering tests for rho-conditioned I1-M3 graph region pilot."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from i1_m3_graph_region_pilot import (
    completed_requests,
    graph_rho_regions,
    m3_weighted_request_sample,
)


def _ledger(mean: float, count: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    latency = np.exp(rng.normal(np.log(mean), 0.17, count))
    cost = latency * rng.uniform(1.0, 1.3, count)
    return pd.DataFrame({
        "completion": rng.uniform(0.0, 240.0, count),
        "L": latency, "C": cost, "Q": np.full(count, 0.5),
    })


def test_weighted_sampling_reproducible_and_respects_model_weights():
    a = _ledger(1.0, 90, 10)
    b = _ledger(9.0, 15, 11)
    # Unequal row counts must not turn 90:15 into the mixing ratio.
    sample1 = m3_weighted_request_sample(
        {1: a, 2: b}, {1: 0.2, 2: 0.8},
        n_requests=10000, seed=987,
    )
    sample2 = m3_weighted_request_sample(
        {1: a, 2: b}, {1: 0.2, 2: 0.8},
        n_requests=10000, seed=987,
    )
    pd.testing.assert_frame_equal(sample1, sample2)
    assert (sample1["L"] > 4.0).mean() > 0.70


def test_graph_regions_nested_and_detect_shift():
    base, _ = graph_rho_regions(
        _ledger(1.0, 170, 10), [0.75, 0.9],
        model_samples=1000, random_state=71,
    )
    higher, _ = graph_rho_regions(
        _ledger(4.0, 170, 10), [0.75, 0.9],
        model_samples=1000, random_state=71,
    )
    assert base["l_max"].is_monotonic_increasing
    assert base["c_max"].is_monotonic_increasing
    assert higher["l_max"].iloc[0] > base["l_max"].iloc[0]
    assert higher["c_max"].iloc[0] > base["c_max"].iloc[0]
    assert (base["q_min"] == 0.5).all()


def test_reject_missing_or_nondegenerate_quality():
    with pytest.raises(ValueError):
        completed_requests(pd.DataFrame({"L": [1.0]}))
    src = _ledger(1.0, 100, 12)
    src.loc[0, "Q"] = 0.75
    with pytest.raises(NotImplementedError):
        graph_rho_regions(src, [0.9], model_samples=1000)


def test_reject_invalid_mixture():
    with pytest.raises(ValueError):
        m3_weighted_request_sample(
            {1: _ledger(1.0, 20, 2)}, {1: 0.7},
            n_requests=1000, seed=2,
        )
