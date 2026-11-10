# Targeted two-step Knowledge Gradient diagnostic (v1)

This experiment tests the hypothesis arising from the controlled-tie audit: first evaluations with effectively equal **one-step KG** may have different expected values after an *adaptive* second evaluation.

No manuscript edits, provider simulations, terminal-replay claims, or modifications of the historical matrix are made.

## Mathematical definition

For the current observations `D` and an unobserved method–condition pair `e`, let `KG1(e | D)` be the existing Gaussian one-step KG. The two-evaluation acquisition value is:

```
KG2(e | D) = KG1(e | D)
            + E_{y_e | D} [ max_{e' available after e} KG1(e' | D, e, y_e) ]
```

The maximization over the second action occurs **inside** the expectation. This is essential: the second choice adapts to the first outcome. It does not assume knowledge of the true frozen loss values when planning.

The first observation is represented as a standard normal predictive innovation; Gaussian-linear conditioning updates the selected method's posterior mean and covariance analytically. Gauss–Hermite quadrature integrates over possible observations.

## Selection of states/actions

- 12 initial posterior states, one after evaluating all seven methods at one common starting condition.
- For each state, identify **all** available first actions with `KG1 >= max(KG1) - 1e-12`.
- Compute `KG2` for every one-step-tied first action.
- For the second action, consider **all remaining** unevaluated method–condition pairs, without restricting the method or condition.
- Run increasing quadrature orders 15, 31, 61. Compare consecutive orders to identify unstable rankings.

This is a targeted **discrimination diagnostic**, not a full two-step policy evaluation. A difference between orders is a numerical convergence diagnostic, not a certified error bound.

## Pull and run

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/kg_two_step_targeted_v1.py --smoke

python first_science/b1/planb_validation/kg_two_step_targeted_v1.py \
  --matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --out ~/praise/planb_b1_kg_two_step_targeted_v1
```

The matrix SHA-256 is verified by the original KG loader. The output directory must not already exist.

## Outputs

- `initial_state_summary.csv`: number of one-step ties, spread in two-step values, quadrature convergence difference, ranking stability, selected pair.
- `tied_action_values.csv`: KG1, KG2 at each quadrature order, and conditional future-KG contribution by candidate first pair.
- `manifest.json`: input matrix hash, quadrature orders, configuration, file hashes.

## Interpretation gate

A useful positive result requires **two-step values that differ substantially more than the observed numerical quadrature instability**, preferably with stable best-action ranking across increasing orders. Otherwise, strengthen numerical integration before interpreting small gaps.

Even a positive result does **not** establish improved terminal regret or superiority on new provider worlds. If the diagnostic is positive, the next question is whether an efficient approximation yields better final method selection without displacing the planned independent validation.
