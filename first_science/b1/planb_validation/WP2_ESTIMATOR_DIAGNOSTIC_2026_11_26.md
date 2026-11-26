# WP2 — Terminal-estimator diagnostic (26 November 2026)

Status: empirical diagnostic completed; scientific review pending. WP1 is frozen. No acquisition policy, reference matrix, or manuscript claim was changed in this diagnostic.

## Reproduce locally

From the repository root, with NumPy and pandas installed:

```bash
python first_science/b1/planb_validation/wp2_diagnostic.py ~/praise/planb_b1_.zip ~/praise/wp2_diagnostic_2026_11_26_v1
```

The input ZIP is the user-supplied archive, SHA-256 `21b57187cef0b3bd372aeb69ee4cf944286d68b60241f7a2445581d47c33b18e`, containing the original nested replay directory. Adjust its location as necessary. The output directory must not already exist. Keep raw histories, reconstructed matrices, and per-episode outputs local. The script checks the archived ledger hashes, reconstructs the fixed scoring matrices from the union of observed cells, and reproduces all archived E1 decisions, correctness indicators and regrets before summarizing. Original standalone matrix-file hashes were not reverified.

## Results

37,440 decisions (two archives, six nested policies, 12 starts, 20 replicates, 13 budgets). Zero E1/E2 recommendation disagreements. Maximum baseline regret reproduction error 5.55e-17. All regret and correct-selection outcomes are identical. RMSE across methods, episodes and budgets is slightly lower for E1 in all 12 archive-policy combinations.

| Archive | Policy | E1 RMSE | E2 RMSE | Shared mean regret | Shared PCS |
|---|---|---:|---:|---:|---:|
| fresh | balanced | .030539 | .030876 | .003446 | .357692 |
| fresh | informed | .031649 | .032106 | .002743 | .462179 |
| fresh | joint KG | .037537 | .038096 | .002212 | .626603 |
| fresh | adaptive two-stage KG | .038442 | .039013 | .001930 | .638141 |
| fresh | uniform two-stage KG | .041709 | .042343 | .002232 | .615705 |
| fresh | random | .035205 | .035554 | .003872 | .354487 |
| historical | balanced | .017662 | .017900 | .005155 | .769231 |
| historical | informed | .019338 | .019620 | .004759 | .779167 |
| historical | joint KG | .023186 | .023493 | .002847 | .867628 |
| historical | adaptive two-stage KG | .022962 | .023270 | .002664 | .874359 |
| historical | uniform two-stage KG | .025206 | .025538 | .003457 | .840705 |
| historical | random | .020899 | .021181 | .007097 | .704808 |

Top2 histories were unavailable; the three Top2 policies were not empirically rescored. Bootstrap intervals are nominal, paired within fixed start strata, conditional on the two frozen matrices. The findings do not establish universal RMSE superiority.

## Analytical explanation for review

For one method let O be the observed cells, K the latent cell covariance, m0=0.17, C=12, residual variance s2=0.055^2. The posterior latent prediction is p=m0*1+K[:,O]u, where u=(K[O,O]+s2*I)^(-1)(y_O-m0*1). E1=mean(p); E2=E1+sum(y_O-p_O)/C.

The balanced full factorial gives K constant row/column sum kappa=C*tau_alpha^2+4*tau_world^2+3*tau_graph^2=0.198475. Thus E1-m0=(kappa/C)*sum(u), while y_O-p_O=s2*u. It follows that E2=m0+(1+s2/kappa)*(E1-m0). The common slope is approximately 1.01524, strictly positive, independent of method, history and budget. This proves identical rankings for these estimators with shared prior parameters, independent per-method models, a balanced uniform catalogue, and a homoskedastic independent residual. It is not a general equivalence under arbitrary condition weights, covariance, or method-specific parameters.

Moreover, because the affine relation holds at every possible posterior history, one-step KG for the actual finite-population mean equals the existing latent-mean KG multiplied by that same positive constant (for the same predictive observation law). Max and mean aggregation preserve this scaling, and therefore the mathematical KG acquisition ranking is unchanged; implementation-level numerical tie tolerances may require separate verification. The existing KG need not be replaced solely because of the finite-catalogue estimand. This extension of the proof is a proposed analytical conclusion for scientific review, not a separately executed acquisition experiment.

E2 is the posterior mean of the finite-catalogue target under the assumed Gaussian discrepancy model; E1 has empirically lower RMSE on these specific fixed archives. Either yields the same terminal decisions under the frozen assumptions. Review before changing manuscript or closing WP2.


## Scientific review — 26 November 2026

**Decision: mathematical result accepted; WP2 ready for closure after manuscript clarification.** No new physical experiments or acquisition reruns are required to establish the exact-arithmetic equivalence.

For a general latent covariance K and uniform catalogue, constant column sum kappa > 0 is sufficient for the affine relationship. More generally, a normalized target weight vector w satisfying w^T K = kappa w^T is sufficient when the independent residual variance is common. The common weighted prior mean and scaling must also be shared across methods. A balanced factorial with exchangeable level variances is one sufficient construction, not a necessary one. For irregular catalogues, nonuniform weights, heteroskedastic discrepancies, or method-specific parameters, the equivalence must be re-established, not assumed.

KG proof: if m2(H)=d+lambda*m1(H) componentwise for all histories H, with lambda>0, the expected decrease in the minimum posterior mean under the same predictive observation law is KG2=lambda*KG1. This is exact for joint KG; the mean-over-remaining-conditions and maximum operations in the two-stage rule preserve the ordering. The existing KG code was inspected: its formula uses the same latent-mean gaps and prospective mean-update SD, both scaling by lambda. A fixed absolute numerical tie tolerance of 1e-12 would need to scale by lambda if scores were explicitly transformed. No implementation change is needed when retaining the existing scores.

Top2's recommendation and shortlist are likewise invariant; its variance-reduction acquisition scores scale by lambda^2 if defined as the variance of the prospective posterior-mean update. Informed uses posterior variances in its gap weighting: the actual target's posterior variance need not be lambda^2 times the latent target's posterior variance, so do not claim equivalence of a redefined Informed acquisition policy. Its archived implementation can be preserved as a baseline.

E2 is the posterior mean of the stated finite target and the Bayes-optimal estimator under squared loss for the assumed model. E1's lower empirical RMSE on the two fixed archives is compatible with model misspecification and/or conditional archive effects; it is not evidence that E1 is universally superior. At complete catalogue coverage E2 equals the realized target exactly, whereas E1 generally does not. This is an analytical boundary case, not an observed B=84 result (the archived maximum is B=80).

Recommended minimal manuscript intervention: define E2 as the finite-target posterior mean, present the affine equivalence as a proposition with proof, explain the KG consequence, and report the 37,440-decision diagnostic briefly. Retain the existing acquisition and recommendation implementations and their reported decision metrics. Keep WP1 frozen; do not extend abstract novelty or anticipate new empirical evidence. Prior-art novelty of the proposition has not been established. Original standalone matrix hashes were not independently checked during this diagnostic; Top2 action histories were unavailable; no new physical simulations or numerical tie-equivalence replay was performed.
