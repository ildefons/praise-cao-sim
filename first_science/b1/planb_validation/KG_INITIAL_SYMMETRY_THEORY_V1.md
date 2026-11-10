# Mathematical structure of the initial B1 acquisition decision

Status: **development theory note**, not yet incorporated into manuscript v0.60.
The statements below apply to the **initial state** after one observation
of every method at the same condition, with the frozen independent-method
Gaussian-linear model. They do not automatically apply after arbitrary
adaptive observations.

## 1. Statistical setup

Each method has independent parameters

```
theta_a ~ N(mu_0, Sigma_0)
Y_(a,c) | theta_a ~ N(x_c^T theta_a, sigma^2).
m_a = v^T theta_a,    v = mean_c(x_c).
```

For B1, `x_c` contains an intercept, one world indicator (3 worlds), and
one graph indicator (4 graphs). The prior covariance `Sigma_0` is diagonal:
intercept variance 0.12^2, world-indicator variance 0.07^2, graph-indicator
variance 0.045^2, with independent measurement noise variance 0.055^2.
All methods use the same prior and are initially measured at the same
condition `c0`, although their observed losses differ.

After these common-location measurements, the covariance of EVERY method is

```
S = Sigma_0 - Sigma_0 x_0 x_0^T Sigma_0
                   / (sigma^2 + x_0^T Sigma_0 x_0).
```

The covariance does not depend on the observed loss, so it is common across
methods, while posterior means differ.

## 2. Why the two leading methods tie under KG1

Write posterior domain-loss estimates in ascending order as
`m_(1) <= m_(2) <= ...`. For action (a,c), the standard deviation of the
**update to the posterior mean of domain-average loss** is

```
s_c = |v^T S x_c| / sqrt(sigma^2 + x_c^T S x_c).
```

This is independent of method at the common-start state.

For a candidate method, `d_a` is the absolute difference between its
posterior expected loss and the smallest mean among other methods.
One-step KG is

```
KG1(a,c) = s_c phi(d_a/s_c) - d_a Phi(-d_a/s_c)
```

for `s_c > 0`, with the obvious zero limit. The derivative with respect
to the absolute gap is `-Phi(-d_a/s_c) < 0`.

The best and runner-up methods have the SAME gap
`d_(1)=d_(2)=m_(2)-m_(1)`. Every other method has a gap at least as large.
Consequently, at a given condition, both leading methods tie for maximum
one-step KG (up to further exact method-mean ties).

**This is a mathematical property of the frozen initial model, not evidence
that the two methods are equally good.**

## 3. Why six conditions tie for each leading method

The group of world-label permutations fixing the initial world and graph-label
permutations fixing the initial graph preserves:
- the prior covariance (equal variance within each indicator type);
- the domain-average target `v`;
- the observed initial condition `x_0`;
- the complete catalogue of still-available actions.

Thus any remaining condition is characterized by whether it shares the
initial world and whether it shares the initial graph. Within each category
the acquisition score is identical by symmetry.

There are 2 other-world/same-graph choices and 3
same-world/other-graph choices.
The other-world/other-graph group contains `2*3 = 6` conditions.
The already observed same-world/same-graph condition is unavailable for
every method.

For the frozen B1 parameters, the posterior update standard deviations
for a canonical initial state are approximately:

| Other condition relative to initial | Multiplicity | Posterior mean-shift SD |
| --- | ---: | ---: |
| Same world, different graph | 3 | 0.03605194 |
| Different world, same graph | 2 | 0.04672806 |
| Different world, different graph | 6 | 0.05370946 |

The last category gives the largest update SD. Because KG1 is increasing
in this SD, every one of the six conditions is a maximum for each of the
two leading methods. Hence **2 x 6 = 12 initially tied KG1 actions**.

## 4. What happens under two-step KG?

Let e=(a,c) be the first evaluation. Define:

```
KG2(e|D) = KG1(e|D)
         + E_z [max_{e' != e} KG1(e' | D, e, z)].
```

The second evaluation can adapt to the first observation. Under the same
permutation group as above, all six different-world/different-graph
conditions of a GIVEN first method remain equivalent in KG2:
the permutation transforms the first action and the subsequent action
catalogue together while preserving the Gaussian predictive law.
Therefore these six KG2 values are **exactly equal under the model**.

However, exchanging the two leading METHODS is not generally a symmetry:
their posterior means differ, and the other five method means can make
later KG decisions respond differently to their possible observations.
Thus KG2 can, in principle, differentiate the two tied leading methods.

Importantly, the symmetry holds only for the common-start state and
specified model; after collecting observations in other conditions, the
invariance subgroup may shrink.

## 5. Numerically isolate the only remaining comparison

Rather than integrate 12 effectively duplicate first actions for each
initial state, compare only two representatives: the best and runner-up
methods, each under a canonical other-world/other-graph condition.

The script `kg_initial_symmetry_paired_v1.py` first checks the exact
one-step tie structure in each of the 12 historical starting states.
It then uses SciPy adaptive quadrature, integrating the **paired
difference in future optimal one-step KG at matched standardized
Gaussian innovations**. This cancellation often improves precision
when absolute KG2 integrals have similar numerical errors.

The script also calculates separate KG2 values, their numerical
error estimates, and a consistency check with the paired integral.
Quadrature error estimates are numerical diagnostics, not certified
bounds, and truncated Gaussian tails remain (negligible at +/-10).

## Run

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/kg_initial_symmetry_paired_v1.py \
  --matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --out ~/praise/planb_b1_kg_initial_symmetry_paired_v1
```

Requires `numpy` and `scipy` in the active environment.
Outputs: `two_method_comparison.csv` and `manifest.json`.

This is **theory plus model-internal numerical validation**. It neither
demonstrates lower terminal regret nor replaces independent provider-world
and graph validation.
