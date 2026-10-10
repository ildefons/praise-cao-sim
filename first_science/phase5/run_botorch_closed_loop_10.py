"""Ten sequential BoTorch constrained acquisitions vs matched Sobol baseline.

Existing library algorithms only. Synthetic deterministic oracle, no YAFS.
Run: python first_science/phase5/run_botorch_closed_loop_10.py
"""
import csv
import time
from pathlib import Path

import torch
from botorch.acquisition.logei import qLogNoisyExpectedImprovement
from botorch.acquisition.objective import GenericMCObjective
from botorch.fit import fit_gpytorch_mll
from botorch.models import SingleTaskGP
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf
from gpytorch.mlls import ExactMarginalLogLikelihood

from check_botorch_one_step import observations

INITIAL = 16
STEPS = 10
DIMENSION = 9
HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "51_botorch_closed_loop_10"


def best_feasible(Y):
    feasible = torch.all(Y[:, 1:] >= 0, dim=-1)
    return float(Y[feasible, 0].min()) if feasible.any() else float("nan")


def bo_candidate(X, Y):
    model = SingleTaskGP(
        train_X=X,
        train_Y=Y,
        train_Yvar=torch.full_like(Y, 1e-5),
        outcome_transform=Standardize(m=7),
    )
    fit_gpytorch_mll(ExactMarginalLogLikelihood(model.likelihood, model))
    objective = GenericMCObjective(lambda samples, X=None: -samples[..., 0])
    constraints = [
        lambda samples, j=j: -samples[..., j] for j in range(1, 7)
    ]
    acq = qLogNoisyExpectedImprovement(
        model=model,
        X_baseline=X,
        objective=objective,
        constraints=constraints,
        prune_baseline=False,
    )
    bounds = torch.stack([torch.zeros(DIMENSION), torch.ones(DIMENSION)])
    candidate, value = optimize_acqf(
        acq_function=acq,
        bounds=bounds,
        q=1,
        num_restarts=4,
        raw_samples=64,
        options={"maxiter": 60},
    )
    assert candidate.shape == (1, DIMENSION)
    assert torch.isfinite(candidate).all() and torch.isfinite(value).all()
    assert bool(torch.all((candidate >= 0) & (candidate <= 1)))
    return candidate.detach(), float(value.detach())


def main():
    torch.set_default_dtype(torch.double)
    torch.manual_seed(20261010)
    OUT.mkdir(parents=True, exist_ok=True)
    X0 = torch.quasirandom.SobolEngine(
        dimension=DIMENSION, scramble=True, seed=314
    ).draw(INITIAL).double()
    X0[0] = 0.5
    Y0 = observations(X0)
    assert X0.shape == (INITIAL, DIMENSION) and Y0.shape == (INITIAL, 7)
    assert torch.all(Y0[0, 1:] > 0)

    # Unprivileged, identical initialization and a separate Sobol stream.
    sobol = torch.quasirandom.SobolEngine(
        dimension=DIMENSION, scramble=True, seed=271828
    )
    rows = []
    initial_best = best_feasible(Y0)
    print("INITIAL_BEST", f"{initial_best:.8f}", flush=True)
    for name in ("botorch_qlognei", "sobol"):
        X, Y = X0.clone(), Y0.clone()
        for step in range(STEPS + 1):
            feasible_count = int(torch.all(Y[:, 1:] >= 0, dim=-1).sum())
            best = best_feasible(Y)
            if step == STEPS:
                break
            tic = time.perf_counter()
            if name == "botorch_qlognei":
                candidate, acq = bo_candidate(X, Y)
            else:
                candidate = sobol.draw(1).double()
                acq = float("nan")
            overhead = time.perf_counter() - tic
            outcome = observations(candidate)
            X = torch.cat([X, candidate])
            Y = torch.cat([Y, outcome])
            row = dict(
                method=name, step=step + 1, observations=len(X),
                candidate=str([round(float(x), 6) for x in candidate[0]]),
                graph_survival=float(outcome[0, 0]),
                min_margin=float(outcome[0, 1:].min()),
                candidate_feasible=bool(torch.all(outcome[0, 1:] >= 0)),
                feasible_count=int(torch.all(Y[:, 1:] >= 0, dim=-1).sum()),
                best_feasible=best_feasible(Y),
                acquisition_log_value=acq,
                selection_seconds=overhead,
            )
            rows.append(row)
            print(
                name, f"{step + 1}/{STEPS}",
                f"candidate_feasible={row['candidate_feasible']}",
                f"best={row['best_feasible']:.8f}",
                f"selection_s={overhead:.3f}", flush=True
            )
        print(
            "FINAL", name, "feasible", feasible_count,
            "best", f"{best:.8f}", "improvement",
            f"{initial_best - best:.8f}", flush=True
        )

    with (OUT / "trace.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("BOTORCH_CLOSED_LOOP_10_PASS")
    print("TRACE", OUT / "trace.csv")
    print("NOTE: This is an engineering test on one synthetic function, not a BO performance validation.")


if __name__ == "__main__":
    main()
