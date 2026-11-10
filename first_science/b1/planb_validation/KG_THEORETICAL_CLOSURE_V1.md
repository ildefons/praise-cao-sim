# Theoretical closure: initial KG indifference and its limits (10 November 2026)

**Status:** Research note, separate from manuscript v0.60 and frozen B1 evidence.
This note distinguishes proved statements, model-specific observations, and counterexamples.

## Definitions

For each method a, an independent Gaussian-linear posterior describes its domain-average loss M_a. Given available action e=(a,c), its observation updates the posterior mean of M_a by kappa_(a,c) Z, Z~N(0,1), while its posterior covariance and available action menu update deterministically. Let U(D)=-min_a E[M_a|D]. With t remaining evaluations, define the optimal expected acquisition improvement relative to the current state:

V_t(D) = sup_(adaptive policies pi over t actions) E[U(D_t)] - U(D).

Here V_0=0. The exact two-step acquisition value for a proposed first action e is

Q_2(e|D) = KG_1(e|D) + E_Z[max_(e' available after e) KG_1(e'|D,e,Z)].

The second action is selected *after* observing the first measurement. Both formulas use posterior-predictive observations, never the hidden frozen outcomes.

## Proposition 1: two leading methods tie under initial one-step KG

When all methods have equal posterior covariance and identical available condition sets, the predictive standard deviation s_c of the update to the target mean is common across methods for a given c. The independent-Gaussian one-step KG is

KG_1(a,c) = h(d_a,s_c),
h(d,s) = s phi(d/s) - d Phi(-d/s),

where d_a is the absolute posterior-mean gap between a and its strongest competitor (for loss minimization). In particular the leading and runner-up methods share d=mu_(2)-mu_(1). All remaining methods have gap >= d. Since h decreases in d and increases in s, both leaders maximize KG at any condition attaining maximum s_c. Additional ties are possible if further means coincide.

**Initial B1 condition orbits.** The initial observation is obtained at the same condition for all 7 methods. Prior covariance is common and invariant under permutations of the 2 *unobserved* provider-world labels and the 3 *unobserved* graph labels. The 11 remaining conditions form orbits of sizes 3 (same world, new graph), 2 (new world, same graph), and 6 (new world, new graph). The last orbit has the largest target-mean update SD for the frozen hyperparameters. The 12 top KG1 actions are exactly the 2 leading methods times the 6 members of that orbit. This result is specific to the initial state; the orbit structure may change after subsequent observations.

## Theorem 2: initial two-method symmetry under arbitrary finite adaptive lookahead

**Assumptions:** Exactly two independent Gaussian methods, any two posterior mean values, equal posterior covariance, identical sets of admissible condition actions, equal conditional observation-noise laws, a terminal recommendation minimizing posterior expected loss, and an action budget t >= 1. The action model is invariant to interchanging method labels. For any admissible condition c common to both methods:

Q_t((1,c)|D) = Q_t((2,c)|D).

This is an equality of *expected optimal posterior utility* for the remaining finite horizon, NOT an equality of actual hidden losses or realized regret.

**Proof.** Set d=mu_1-mu_2. Let L_i denote the posterior covariance and remaining condition menu of method i. Since the posterior mean of each method is a martingale, and

min(mu_1,mu_2) = (mu_1+mu_2-|d|)/2,

maximizing expected terminal utility is equivalent (for fixed current state) to maximizing E|d_t|. Let F_t(d,L_1,L_2) denote the optimal expected |d_t| with t evaluations remaining. The base F_0=|d|. Gaussian observation innovations are symmetric around zero. By induction, F_t is even in d, and F_t(d,L_1,L_2)=F_t(d,L_2,L_1). Indeed, swapping the two methods changes the sign of the gap; reversing each normal innovation recovers its original law and preserves the available actions. These operations establish both identities at every Bellman step.

Starting with L_1=L_2, taking the same condition c on method 1 yields d'=d+kappa_c Z and remaining states (L',L). Taking c on method 2 yields d'=d-kappa_c Z and states (L,L'). Since Z is symmetric, and F_(t-1) is symmetric under exchanging L and L', the two actions have equal expected continuation. Their current KG1 values also coincide, establishing the claim.

The result extends from scalar posterior variances to identical Gaussian-linear covariance matrices and matched condition menus; the complete covariance and menu are components of L_i. The theorem does NOT claim all actions are equivalent, only matched actions of the two methods.

## Proposition 3: initial condition equivalence at any finite horizon

For the B1 initial state, permutations of the unseen provider-world labels and unseen graph labels preserve the prior, target-average feature vector, initial information, all admissible actions, and posterior predictive laws. They therefore preserve any finite-horizon optimal Bayesian acquisition value. In particular, the six new-world/new-graph conditions have exactly equal values for a *fixed first method* for every finite lookahead horizon. Increasing horizon alone cannot break this symmetry.

## A third-method counterexample: the two-method theorem does not automatically extend

A simple independent Gaussian posterior experiment has three methods with current expected losses (0, 0.2, 0.4), posterior mean-update SDs (0.12, 0.12, 0.20), and at most one observation per method. Sampling a method updates its mean by s_a Z and eliminates that action. All three have independent standard-normal innovations. The two leading methods have identical KG1 scores:

KG1(1)=KG1(2)=0.0023791862; KG1(3)=0.0016981405.

Nevertheless numerical integration of the adaptive two-step criterion gives

Q2(1)=0.0100415821, Q2(2)=0.0104928524,
Q2(1)-Q2(2)=-0.0004512703.

Thus the best and second-best methods are globally tied for largest one-step KG, but are *not* tied for two-step KG. In this example, the third method has a different posterior uncertainty. An equal-third-uncertainty control at s_3=0.12 produces indistinguishable Q2 values for the leaders (approximately 0.0099486187 each).

These calculations establish the limits of the two-method theorem. They do not show that third-method effects are nonzero in the *initial B1 model*, where all seven methods initially share the same posterior covariance and admissible menus.

## What the B1 evidence does and does not establish

The initial B1 experiment had 12 tied KG1 first actions in each of 12 starting states. Reduced paired numerical integration found virtually zero leader Q2 differences in 11 states. One anomalous state gave a 1.67e-7 paired difference, but its independently integrated difference disagreed by about 3.10e-8, far beyond its reported numerical error. Other individual states also showed consistency problems. IntegrationWarning was emitted. **Do not claim a genuine two-step leader preference from that calculation.**

An exact theorem for all-seven-method, equal-covariance initial B1 states is **not established** here. The present evidence suggests that leader Q2 differences are negligible or possibly zero, but the two-method theorem does not by itself prove that fact. Further numerical quadrature alone is not a priority unless a theoretical counterexample or practical performance implication appears.

## Research decision

The mathematically defensible contribution is the *information-symmetry characterization* (theorem, condition orbits, and explicit counterexample under broken symmetry), not an unverified KG2 improvement. Under the present time budget, stop further KG2 algorithm development for now. Prioritize independent provider-world / graph validation and measured systems costs. Revisit deeper lookahead if new conditions break the symmetry or produce informative multi-step improvements.

The synthetic counterexample is checked by `kg_symmetry_theory_check_v1.py`; it is not an additional B1 systems benchmark.
