"""Restrictive-feasibility follow-up: SAME BoTorch BO, harder provider margins.

Only the synthetic provider-margin intercept changes from 0.18 to 0.035.
Graph-survival oracle, initial design, BoTorch GP/acquisition/optimizer,
Sobol comparator and 10-step budget are unchanged. No YAFS.

Run: python first_science/phase5/run_botorch_restrictive_10.py
"""
import csv
import time
from pathlib import Path
import torch

from run_botorch_closed_loop_10 import (
    DIMENSION, INITIAL, STEPS, bo_candidate, best_feasible,
)
from check_botorch_one_step import observations as original_observations

OUT = Path(__file__).resolve().parent / "results" / "52_botorch_restrictive_10"
# Strictly change provider constraint thresholds, NOT optimization machinery.
MARGIN_SHIFT = 0.145


def observations(X):
    outputs = original_observations(X).clone()
    outputs[..., 1:] -= MARGIN_SHIFT
    return outputs


def main():
    torch.set_default_dtype(torch.double)
    torch.manual_seed(20261010)
    OUT.mkdir(parents=True, exist_ok=True)

    X0 = torch.quasirandom.SobolEngine(
        dimension=DIMENSION, scramble=True, seed=314
    ).draw(INITIAL).double()
    X0[0] = 0.5
    Y0 = observations(X0)
    assert Y0.shape == (INITIAL, 7)
    assert torch.all(Y0[0, 1:] > 0)
    initial_feasible = int(torch.all(Y0[:, 1:] >= 0, dim=-1).sum())
    initial_best = best_feasible(Y0)
    print("RESTRICTIVE_PROVIDER_MARGIN_SHIFT", MARGIN_SHIFT, flush=True)
    print("INITIAL_FEASIBLE", initial_feasible, "of", INITIAL, flush=True)
    print("INITIAL_BEST", f"{initial_best:.8f}", flush=True)

    rows = []
    sobol = torch.quasirandom.SobolEngine(
        dimension=DIMENSION, scramble=True, seed=271828
    )
    for name in ("botorch_qlognei", "sobol"):
        X, Y = X0.clone(), Y0.clone()
        for step in range(1, STEPS + 1):
            tic = time.perf_counter()
            if name == "botorch_qlognei":
                candidate, acq = bo_candidate(X, Y)
            else:
                candidate, acq = sobol.draw(1).double(), float("nan")
            selection_seconds = time.perf_counter() - tic
            outcome = observations(candidate)
            X = torch.cat((X, candidate))
            Y = torch.cat((Y, outcome))
            feasible = bool(torch.all(outcome[0, 1:] >= 0))
            count = int(torch.all(Y[:, 1:] >= 0, dim=-1).sum())
            best = best_feasible(Y)
            rows.append(dict(
                method=name, step=step,
                candidate=str([round(float(v), 6) for v in candidate[0]]),
                candidate_feasible=feasible,
                min_margin=float(outcome[0, 1:].min()),
                graph_survival=float(outcome[0, 0]),
                feasible_count=count, best_feasible=best,
                acquisition_log_value=acq,
                selection_seconds=selection_seconds,
            ))
            print(name, f"{step}/{STEPS}",
                  f"candidate_feasible={feasible}",
                  f"feasible_count={count}",
                  f"best={best:.8f}", flush=True)
        print("FINAL", name,
              "feasible", count,
              "best", f"{best:.8f}",
              "improvement", f"{initial_best-best:.8f}",
              flush=True)

    with (OUT / "trace.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("BOTORCH_RESTRICTIVE_10_PASS")
    print("TRACE", OUT / "trace.csv")
    print("NOTE: Diagnostic of restrictive constraints; one synthetic instance only.")


if __name__ == "__main__":
    main()
