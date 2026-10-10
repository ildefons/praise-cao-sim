"""PRAISE step 1: dependency / output-sign smoke test (no simulation).

Usage:
    python first_science/phase5/check_botorch_prerequisites.py

This is intentionally NOT an optimizer or a surrogate implementation.
"""
import inspect
import sys


def main():
    try:
        import torch
        import botorch
        from botorch.acquisition.logei import qLogNoisyExpectedImprovement
        from botorch.acquisition.objective import GenericMCObjective
        from botorch.models import SingleTaskGP, ModelListGP
        from botorch.fit import fit_gpytorch_mll
        from botorch.optim import optimize_acqf
        from botorch.sampling.normal import SobolQMCNormalSampler
        from gpytorch.mlls import ExactMarginalLogLikelihood
    except ImportError as exc:
        print("BOTORCH_DEPENDENCY_MISSING:", exc)
        print("Install in the praise-cao environment: python -m pip install botorch")
        return 2

    sig = inspect.signature(qLogNoisyExpectedImprovement)
    for name in ("model", "X_baseline", "objective", "constraints"):
        if name not in sig.parameters:
            raise RuntimeError(f"Required BoTorch API missing: {name}")

    # Our seven-output response convention:
    # y[0] = graph first-violation survival, which we MINIMIZE.
    # y[1:7] = provider survival minus disclosed bound, must be >= 0.
    objective = GenericMCObjective(lambda samples, X=None: -samples[..., 0])
    constraints = [
        (lambda samples, j=j: -samples[..., j])
        for j in range(1, 7)
    ]
    # BoTorch treats constraints as satisfied when their output <= 0.
    valid = torch.tensor([[0.30, 0.1, 0.2, 0.1, 0.3, 0.2, 0.1]], dtype=torch.double)
    invalid = torch.tensor([[0.20, 0.1, 0.2, -0.01, 0.3, 0.2, 0.1]], dtype=torch.double)
    assert objective(valid).item() == -0.30
    assert all(fn(valid).item() <= 0 for fn in constraints)
    assert not all(fn(invalid).item() <= 0 for fn in constraints)

    print("BOTORCH_PRAISE_API_SMOKE_PASS")
    print("python", sys.version.split()[0])
    print("torch", torch.__version__)
    print("botorch", botorch.__version__)
    print("output_order", "graph_survival, six_signed_provider_margins")
    print("optimization", "maximize negative graph survival")
    print("constraints", "negative margins <= 0")
    print("status", "API/sign checks only: no fitting, acquisition or YAFS runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
