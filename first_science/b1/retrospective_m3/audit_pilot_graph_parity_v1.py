#!/usr/bin/env python3
"""Non-WB parity test: Phase-4 native G0 vs Phase-5 native G_PAR."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent.parent
PHASE3, PHASE5 = FIRST / "phase3", FIRST / "phase5"
override = os.environ.get("PRAISE_YAFS_SRC")
options = ([Path(override).expanduser()] if override else []) + [
    FIRST.parent.parent / "aicon" / "src" / "yafs" / "src"
]
for path in options:
    if (path / "yafs" / "application.py").is_file():
        sys.path.insert(0, str(path.resolve()))
        break
for path in (PHASE3, PHASE5):
    sys.path.insert(0, str(path))

from yafs.application import Application  # noqa: E402
if not callable(getattr(Application, "add_service_module_praise", None)):
    raise SystemExit("The PRAISE-modified YAFS runtime is required.")
from m1_graph_simulator_v2 import (  # noqa: E402
    GraphProviderSurrogate, execute_one_m1_graph_trajectory
)
from phase5_graph_simulator_v2 import (  # noqa: E402
    execute_one_phase5_graph_trajectory
)

NUMERIC = ["emission", "completion", "L", "C", "Q", "stop_time"]
CATEGORICAL = ["completed_by_stop", "status"]
COLUMNS = ["request_id", *NUMERIC, *CATEGORICAL]


def compare(label, seed, x, y, tol):
    for frame in (x, y):
        if not set(COLUMNS).issubset(frame.columns):
            raise RuntimeError(f"Missing ledger columns: {set(COLUMNS) - set(frame.columns)}")
    a = x[COLUMNS].sort_values("request_id").reset_index(drop=True)
    b = y[COLUMNS].sort_values("request_id").reset_index(drop=True)
    if not a["request_id"].equals(b["request_id"]):
        print(f"DIFFERENT {label} seed={seed}: request identities differ "
              f"({len(a)} versus {len(b)})", flush=True)
        return False
    mismatch = {}
    max_abs = {}
    for col in NUMERIC:
        aa, bb = a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float)
        close = np.isclose(aa, bb, atol=tol, rtol=tol, equal_nan=True)
        mismatch[col] = int((~close).sum())
        finite = np.isfinite(aa) & np.isfinite(bb)
        max_abs[col] = float(max(abs(aa[finite] - bb[finite]), default=0.0))
    for col in CATEGORICAL:
        mismatch[col] = int((a[col].astype(str) != b[col].astype(str)).sum())
    ok = all(value == 0 for value in mismatch.values())
    print(f"{'MATCH' if ok else 'DIFFERENT'} {label} seed={seed}: "
          f"requests={len(a)} mismatched={mismatch}, "
          f"max_numeric_diff={max_abs}", flush=True)
    return ok


def main(seeds, stop, tol):
    p3 = json.loads((PHASE3 / "config_phase3_m0_contract_v1.json").read_text())
    p5 = json.loads((PHASE5 / "config_phase5_recoverability_battery_v2.json").read_text())
    spec = p3["phase1_benchmark_adapter"]
    graph = next(item for item in p5["graphs"] if item["id"] == "G_PAR")
    family = p5["provider_family"]
    inv = dict(p5["graph_invariants"])
    inv["effective_IPT"] = float(family["effective_IPT"])
    inv["cost_rate"] = float(family["cost_rate"])
    period = float(p5["workload"]["period_seconds"])
    fraction = float(family["execution_fraction_x"])
    # Explicit diagnostic surrogate, not an inferred result or a WB lookup.
    models = {
        "ProviderA": GraphProviderSurrogate(0.12, 3.0, 0.3),
        "ProviderB": GraphProviderSurrogate(0.15, 3.0, 0.3),
        "ProviderC": GraphProviderSurrogate(0.18, 3.0, 0.3),
    }
    start = time.perf_counter()
    valid = True
    print("Native graph parity diagnostic only; no public I1, Step-0 or WB read.",
          flush=True)
    for seed in range(3600000, 3600000 + seeds):
        legacy = execute_one_m1_graph_trajectory(
            provider_surrogates=models, graph_spec=spec,
            workload_period=period, stop_time=stop, trajectory_seed=seed,
            canonical_ipt=1e6, execution_fraction=fraction
        )
        common = dict(
            graph_id="G_PAR", graph_ast=graph["ast"],
            provider_surrogates=models, graph_invariants=inv,
            workload_period=period, stop_time=stop, trajectory_seed=seed,
            execution_fraction=fraction
        )
        new_low, _ = execute_one_phase5_graph_trajectory(
            **common, canonical_ipt=1e6
        )
        new_high, _ = execute_one_phase5_graph_trajectory(
            **common, canonical_ipt=float(family["effective_IPT"])
        )
        valid &= compare("G0_vs_G_PAR_at_IPT1e6", seed, legacy, new_low, tol)
        valid &= compare("G_PAR_IPT1e6_vs_IPT1e9", seed, new_low, new_high, tol)
    print(f"Elapsed: {time.perf_counter()-start:.1f}s", flush=True)
    print("B1_NATIVE_GRAPH_PARITY_PASS" if valid else
          "B1_NATIVE_GRAPH_PARITY_DIFFERENCE", flush=True)
    return 0 if valid else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--stop", type=float, default=60)
    ap.add_argument("--tol", type=float, default=1e-8)
    a = ap.parse_args()
    if not 1 <= a.seeds <= 20 or a.stop <= 0 or a.tol <= 0:
        ap.error("Seeds 1..20, stop>0, tol>0 required")
    raise SystemExit(main(a.seeds, a.stop, a.tol))
