"""Noisy restrictive 9D constrained BO versus matched Sobol: engineering test only.

Uses BoTorch's qLogNoisyExpectedImprovement and optimize_acqf unchanged.
Each observation is seven correlated binomial survival counts from the same N
synthetic trajectories. No YAFS, no custom acquisition, no certification.

Run: python first_science/phase5/run_botorch_noisy_restrictive_10.py
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

from check_botorch_one_step import observations as smooth_oracle

D, INITIAL, STEPS, N = 9, 16, 10, 100
BOUND = 0.55
MARGIN_SHIFT = 0.145
OUT = Path(__file__).resolve().parent / "results" / "53_botorch_noisy_restrictive_10"


def population(x):
    """True graph survival and six provider probabilities/margins.

    A single latent uniform per trajectory induces correlated outcomes;
    these are synthetic marginal survival observations, not YAFS trajectories.
    """
    response = smooth_oracle(x).clone()
    true_margins = response[..., 1:] - MARGIN_SHIFT
    probabilities = torch.cat(
        [response[..., :1], BOUND + true_margins], dim=-1
    )
    assert bool(((probabilities > 0) & (probabilities < 1)).all())
    return probabilities, true_margins


def evaluate(x, generator):
    probabilities, truth = population(x)
    # Common per-trajectory random driver gives correlated provider / graph
    # outcomes while preserving the marginal binomial sampling laws.
    latent = torch.rand((N, 1), generator=generator, dtype=torch.double)
    counts = (latent < probabilities[0][None, :]).sum(dim=0)
    estimates = counts.double() / N
    observed_margins = estimates[1:] - BOUND
    observed = torch.cat((estimates[:1], observed_margins)).unsqueeze(0)
    # Independent GP output likelihoods: diagonal binomial plug-in variances.
    # Clamping prevents zero-variance fitting at empirical extremes.
    p = estimates.clamp(0.5 / N, 1 - 0.5 / N)
    yvar = (p * (1 - p) / N).clamp_min(1e-5).unsqueeze(0)
    return observed, yvar, truth


def propose(x, y, yvar):
    model = SingleTaskGP(
        train_X=x,
        train_Y=y,
        train_Yvar=yvar,
        outcome_transform=Standardize(m=7),
    )
    fit_gpytorch_mll(ExactMarginalLogLikelihood(model.likelihood, model))
    objective = GenericMCObjective(lambda samples, X=None: -samples[..., 0])
    constraints = [
        lambda samples, j=j: -samples[..., j] for j in range(1, 7)
    ]
    acq = qLogNoisyExpectedImprovement(
        model=model,
        X_baseline=x,
        objective=objective,
        constraints=constraints,
        prune_baseline=False,
    )
    bounds = torch.stack([torch.zeros(D), torch.ones(D)])
    candidate, value = optimize_acqf(
        acq_function=acq,
        bounds=bounds,
        q=1,
        num_restarts=4,
        raw_samples=64,
        options={"maxiter": 60},
    )
    assert candidate.shape == (1, D)
    assert bool(torch.isfinite(candidate).all())
    assert bool(((candidate >= 0) & (candidate <= 1)).all())
    assert bool(torch.isfinite(value).all())
    return candidate.detach(), float(value.detach())


def true_best(x):
    probabilities, margins = population(x)
    feasible = torch.all(margins >= 0, dim=-1)
    return (float(probabilities[feasible, 0].min()) if feasible.any() else float("nan"),
            int(feasible.sum()))


def main():
    torch.set_default_dtype(torch.double)
    torch.manual_seed(20261010)
    OUT.mkdir(parents=True, exist_ok=True)
    x0 = torch.quasirandom.SobolEngine(
        dimension=D, scramble=True, seed=314
    ).draw(INITIAL).double()
    x0[0] = 0.5

    # Evaluate common initialization once; methods receive identical noisy data.
    initial_generator = torch.Generator().manual_seed(12345)
    observations = [evaluate(x.unsqueeze(0), initial_generator) for x in x0]
    y0 = torch.cat([v[0] for v in observations])
    var0 = torch.cat([v[1] for v in observations])
    init_best, init_count = true_best(x0)
    print(f"INITIAL_TRUE_FEASIBLE {init_count}/{INITIAL}")
    print(f"INITIAL_TRUE_BEST {init_best:.8f}", flush=True)

    rows = []
    sobol = torch.quasirandom.SobolEngine(
        dimension=D, scramble=True, seed=271828
    )
    for method in ("botorch_qlognei", "sobol"):
        x, y, yvar = x0.clone(), y0.clone(), var0.clone()
        generator = torch.Generator().manual_seed(272727)
        false_accepts = 0
        for step in range(1, STEPS + 1):
            start = time.perf_counter()
            if method == "botorch_qlognei":
                candidate, acquisition = propose(x, y, yvar)
            else:
                candidate, acquisition = sobol.draw(1).double(), float("nan")
            seconds = time.perf_counter() - start
            y_new, var_new, truth = evaluate(candidate, generator)
            empirical_valid = bool((y_new[0, 1:] >= 0).all())
            actual_valid = bool((truth[0] >= 0).all())
            false_accepts += int(empirical_valid and not actual_valid)
            x = torch.cat((x, candidate))
            y = torch.cat((y, y_new))
            yvar = torch.cat((yvar, var_new))
            best, total_true_valid = true_best(x)
            row = dict(method=method, step=step, n=N,
                       candidate=str([round(float(v), 5) for v in candidate[0]]),
                       observed_graph=float(y_new[0, 0]),
                       true_graph=float(population(candidate)[0][0, 0]),
                       observed_min_margin=float(y_new[0, 1:].min()),
                       true_min_margin=float(truth[0].min()),
                       empirical_feasible=empirical_valid, true_feasible=actual_valid,
                       false_accept=bool(empirical_valid and not actual_valid),
                       total_true_feasible=total_true_valid,
                       best_true_feasible=best,
                       acquisition_log_value=acquisition,
                       selection_seconds=seconds)
            rows.append(row)
            print(method, f"{step}/{STEPS}",
                  f"observed_feasible={empirical_valid}",
                  f"true_feasible={actual_valid}",
                  f"best_true={best:.8f}", flush=True)
        final_best, total_valid = true_best(x)
        print("FINAL", method, "true_feasible", total_valid,
              "false_accepts", false_accepts,
              "best_true", f"{final_best:.8f}",
              "improvement", f"{init_best-final_best:.8f}", flush=True)

    with (OUT / "trace.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("BOTORCH_NOISY_RESTRICTIVE_10_PASS")
    print("TRACE", OUT / "trace.csv")
    print("NOTE: Observed feasibility is NOT certified; inspect false_accept counts.")


if __name__ == "__main__":
    main()
