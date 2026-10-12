"""Pilot-only rho-conditioned graph-region reconstruction from completed ledgers.

Uses the identical nested log-(L,C) GMM region extractor as provider I1.
Graph ledger inputs have the same request-level fields completion,L,C,Q.
For M3, each joint-model ledger carries a *model* probability weight and
is resampled according to w_j / n_completed,j. This is a finite-sample
approximation to the weighted graph-request mixture; it is NOT a proof
of optimality, exact region identification, or calibrated uncertainty.

No simulator execution, white-box import, graph prediction tuning, or
existing Phase-5 scientific-output mutation occurs here.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from pathlib import Path
import sys

PHASE2 = Path(__file__).resolve().parent.parent / "phase2"
if str(PHASE2) not in sys.path:
    sys.path.insert(0, str(PHASE2))

from i1_rho_conditioned_region import derive_nested_rho_regions

REQUIRED = {"completion", "L", "C", "Q"}
TOL = 1e-12


def completed_requests(ledger: pd.DataFrame) -> pd.DataFrame:
    """Return only completed graph requests, with finite, valid LCQ values."""
    missing = REQUIRED - set(ledger.columns)
    if missing:
        raise ValueError("graph ledger missing fields: " + ", ".join(sorted(missing)))
    out = ledger.loc[ledger["completion"].notna(), ["completion", "L", "C", "Q"]].copy()
    if out.empty:
        raise ValueError("no completed graph requests")
    vals = out[["completion", "L", "C", "Q"]].to_numpy(float)
    if not np.isfinite(vals).all() or np.any(vals[:, 1:3] <= 0):
        raise ValueError("invalid completed graph LCQ values")
    return out.reset_index(drop=True)


def m3_weighted_request_sample(
    member_ledgers: dict[int, pd.DataFrame],
    joint_weights: dict[int, float],
    *,
    n_requests: int,
    seed: int,
) -> pd.DataFrame:
    """Draw reproducible requests from the completed-request conditional M3 mixture.

    Each joint model gets probability w_j, then a uniform completed request
    from that model. Never pool raw rows across models without correcting
    for their different simulation allocations. The mixture is conditional on
    graph-request completion, matching the historical I1 region extraction.
    """
    if set(member_ledgers) != set(joint_weights) or not member_ledgers:
        raise ValueError("member ledgers and weights must match exactly")
    if n_requests < 1000:
        raise ValueError("need at least 1000 draws")
    ranks = sorted(member_ledgers)
    w = np.asarray([float(joint_weights[r]) for r in ranks])
    if not np.isfinite(w).all() or np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=TOL, rtol=0):
        raise ValueError("invalid full-support model weights")
    data = [completed_requests(member_ledgers[r]) for r in ranks]
    q_values = np.concatenate([d["Q"].to_numpy(float) for d in data])
    if float(q_values.max()-q_values.min()) > TOL:
        raise NotImplementedError("rho-region extraction currently requires constant Q")
    rng = np.random.default_rng(int(seed))
    chosen = rng.choice(len(ranks), size=n_requests, p=w)
    portions = []
    for index in np.unique(chosen):
        count = int(np.sum(chosen == index))
        local = data[int(index)]
        ix = rng.integers(0, len(local), size=count)
        piece = local.iloc[ix].copy()
        piece["draw_index"] = np.flatnonzero(chosen == index)
        portions.append(piece)
    sampled = pd.concat(portions, ignore_index=True).sort_values("draw_index")
    sampled = sampled.drop(columns=["draw_index"]).reset_index(drop=True)
    sampled.insert(0, "trajectory", np.arange(n_requests))
    return sampled


def graph_rho_regions(
    ledger: pd.DataFrame,
    rho_values: Iterable[float],
    *,
    model_samples: int = 100_000,
    random_state: int = 271828,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply frozen I1 extractor semantics to graph-level completed requests.

    Caller is responsible for keeping prediction ledgers separate from
    white-box ledgers and for running them on disjoint evidence streams.
    """
    completed = completed_requests(ledger)
    completed.insert(0, "trajectory", np.arange(len(completed), dtype=int))
    regions, audit = derive_nested_rho_regions(
        completed,
        tuple(rho_values),
        model_samples=model_samples,
        random_state=random_state,
    )
    return pd.DataFrame(regions), audit
