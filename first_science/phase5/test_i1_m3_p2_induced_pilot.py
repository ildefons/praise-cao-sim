"""Fast no-simulation checks for isolated P2 M3 induced-region pilot."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from run_i1_m3_p2_induced_pilot import allocation


def test_full343_budget_and_determinism():
    w = np.exp(-np.linspace(0, 6, 343))
    w = w/w.sum()
    support = pd.DataFrame({
        "joint_rank":np.arange(1,344),
        "joint_weight":w,
    })
    a = allocation(support)
    b = allocation(support)
    pd.testing.assert_frame_equal(a,b)
    assert len(a)==343
    assert int(a.n_trajectories.sum())==1400
    assert int(a.n_trajectories.min())>=1
    assert int(a.seed_start.nunique())==343
    assert (a.seed_end_inclusive-a.seed_start+1 == a.n_trajectories).all()


def test_reject_missing_model():
    bad = pd.DataFrame({"joint_rank":[1,2],"joint_weight":[0.6,0.4]})
    with pytest.raises(ValueError):
        allocation(bad)
