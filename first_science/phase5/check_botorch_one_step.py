"""Small BoTorch fitting + constrained acquisition smoke test. No YAFS.

Run: python first_science/phase5/check_botorch_one_step.py
Requires BoTorch 0.16.1 as checked by check_botorch_prerequisites.py.
"""
import torch
from botorch.acquisition.logei import qLogNoisyExpectedImprovement
from botorch.acquisition.objective import GenericMCObjective
from botorch.fit import fit_gpytorch_mll
from botorch.models import SingleTaskGP
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf
from gpytorch.mlls import ExactMarginalLogLikelihood


def observations(X):
    """Synthetic 9D inputs -> graph survival and six provider margins."""
    # Known feasible starting point x=0.5; margins depend on all coordinates.
    displacement = X - 0.5
    radius = displacement.square().mean(dim=-1)
    graph = 0.25 + 0.5 * (X - 0.25).square().mean(dim=-1)
    margins = torch.stack(
        [0.18 - 0.5 * radius + 0.03 * displacement[:, i] for i in range(6)],
        dim=-1,
    )
    return torch.cat([graph.unsqueeze(-1), margins], dim=-1)


def main():
    torch.set_default_dtype(torch.double)
    torch.manual_seed(20261010)
    # Fixed Sobol design only for INITIAL observations, not for candidate search.
    X = torch.quasirandom.SobolEngine(dimension=9, scramble=True, seed=314).draw(16).double()
    X[0] = 0.5
    Y = observations(X)
    assert X.shape == (16, 9) and Y.shape == (16, 7)
    assert torch.all(Y[0, 1:] > 0)

    # Off-the-shelf BoTorch seven-output GP, with separate output likelihoods.
    # Deterministic synthetic measurements: a small fixed numerical nugget.
    # This is NOT a validated statistical noise model for YAFS.
    model = SingleTaskGP(
        train_X=X,
        train_Y=Y,
        train_Yvar=torch.full_like(Y, 1e-5),
        outcome_transform=Standardize(m=7),
    )
    fit_gpytorch_mll(ExactMarginalLogLikelihood(model.likelihood, model))

    objective = GenericMCObjective(lambda samples, X=None: -samples[..., 0])
    constraints = [lambda samples, j=j: -samples[..., j] for j in range(1, 7)]
    acquisition = qLogNoisyExpectedImprovement(
        model=model,
        X_baseline=X,
        objective=objective,
        constraints=constraints,
        prune_baseline=False,
    )
    bounds = torch.stack([torch.zeros(9), torch.ones(9)])
    candidate, acq_value = optimize_acqf(
        acq_function=acquisition,
        bounds=bounds,
        q=1,
        num_restarts=4,
        raw_samples=64,
        options={"maxiter": 60},
    )
    assert candidate.shape == (1, 9)
    assert torch.isfinite(candidate).all()
    assert torch.all((candidate >= 0) & (candidate <= 1))
    assert torch.isfinite(acq_value).all()
    # Probe posterior only to confirm fitting and prediction.
    with torch.no_grad():
        post = model.posterior(candidate)
        assert post.mean.shape == (1, 7)
        assert torch.isfinite(post.mean).all()
    print("BOTORCH_ONE_STEP_PASS")
    print("initial_observations", len(X))
    print("modeled_outputs", Y.shape[-1])
    print("candidate", [round(float(v), 5) for v in candidate[0]])
    print("acquisition_value", float(acq_value))
    print("predicted_graph_survival", float(post.mean[0, 0]))
    print("status", "synthetic model fit and one native BoTorch acquisition; no YAFS")


if __name__ == "__main__":
    main()
