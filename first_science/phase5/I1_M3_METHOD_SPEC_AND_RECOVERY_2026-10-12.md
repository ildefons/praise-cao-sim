# I1-M3 method specification and recovery guide

**Documented:** 2026-10-12  
**Authority:** Existing frozen Phase-5 V3/V3b contracts and implementation, not this explanatory document.  
**Purpose:** Make M3 recoverable without re-deriving its design from conversations or silently substituting M0, M1, or M2.  
**Current canonical Phase-5 variant:** `M3_FULL343` (V3b provider selection plus full-support graph propagation).

## 1. Scientific role and inputs

I1 is the *external provider disclosure* consisting of rho-conditioned local admissibility rectangles and cumulative-compliance survival surfaces:

\[
I_{1,p}=\{A_p(\rho_{region}),\;\sigma_p(A_p,H;\rho_{query})\}.
\]

Here `rho_region` indexes the provider's disclosed region, and `rho_query` sets the fraction of decisions satisfying the SLA. These are distinct even when the experiment uses the same-rho diagonal. Horizon-dependent sigma follows the existing cumulative-fraction-of-decided-requests semantics (unresolved requests excluded, zero-decisions compliant), **not** first-violation survival.

The consumer sees public I1, workload contract and graph topology. Provider model parameters, native private traces and graph white-box outcomes are hidden. Provider SLA regions are independently chosen/published, not optimized by the graph entrepreneur. No artificial equality constraint across the providers, even if the generating simulation happens to have equal parameters.

The present graph-survival pilot must distinguish (a) public-I1-induced graph region construction and (b) graph survival prediction. Historical M1/M2 same-region experiments used the shared public boundary composer as a *query constructor*; M3's stochastic advance is its inferred-provider ensemble and graph propagation. Do not call sum/max/min M3's stochastic composition rule.

## 2. Reconstruct seven independent models per provider (Phase-5 V3)

For each of ProviderA, ProviderB, ProviderC, in each world:

- Latent standalone surrogate: one-server FCFS Gamma service behavior with \(\theta_p=(\mu_p,\kappa_p,CV_p)\), meaning mean service time, cost rate, and coefficient of variation. Use the existing local YAFS simulator, not the composed graph simulator, to evaluate candidates.
- Search domains: previously frozen public-I1-derived domain registry, not hidden parameter ranges or WB-assisted optimization.
- Seven independent Optuna TPE runs, **25 trials each**, **5 startup trials**, distinct sampler seeds and **fresh disjoint 15-trajectory local search evidence per fit**.
- Retain the lowest search-MSE trial from each run: seven candidates per provider. Search MSE compares the predicted *complete disclosed I1 surface* against public observations.
- Re-evaluate all seven on a common, fresh **N=100** local evidence bank. The *V3b selection* orders candidates by ascending common-bank **I1 RMSE**, with candidate-ID tie break. (The original V3 selected behavioral-centroid ranks for M1/M2; V3b superseded that for the canonical variant.)
- A second independent **N=100** replay is **diagnostic only**, never allowed to change ranking, members or weights.
- **No hard RMSE compatibility gate.** Candidate diversity or replay quality may be reported, but never used for later selection.

Sources: `config_phase5_provider_reconstruction_v3.json`, `config_phase5_provider_reconstruction_v3b.json`, `run_phase5_provider_reconstruction_v3.py`, `phase5_reconstruction_v3_selection.py`, `run_phase5_m2_reconstruction_v2.py`, `run_m1_provider_lift_v2.py`.

## 3. M1/M2 and M3 distinctions under canonical V3b selection

| Property | M1 | M2 | M3 |
|---|---|---|---|
| Provider candidate support | Best common-N100 RMSE rank (1/provider) | Top 3 common-N100 RMSE ranks/provider | All 7 candidates/provider |
| Joint models | 1 | 27 | 343 |
| Joint weighting | Single | Uniform \(1/27\) | Product of KL-Gibbs provider weights |
| Graph propagation | Native graph simulations | Native simulation of all 27 joint members | Native simulation of all 343 joint members |
| Phase-5 graph simulation budget/cell | 100 | 27 × 100 = 2700 | **1400 total** across 343 |
| Point prediction | One curve | Uniform mean over 27 curves | Weighted mean over 343 curves |

M3 is **not** merely a larger equal-weight M2. M1/M2 baseline costs are not equal to M3; do not claim a cost-matched superiority from this principal comparison.

## 4. Reweighting the seven candidates

For each provider p and candidate j, simulate the candidate under the public standalone acquisition contract on the common N=100 rescore bank, obtaining a candidate surface \(q_{pj,k}\) at each public I1 observation k (all relevant H>0). Define the public surface \(u_{p,k}\).

Apply Jeffreys smoothing to each probability with N=100:

\[
\widetilde u=(100u+0.5)/101,\qquad
\widetilde q=(100q+0.5)/101.
\]

Average the directional Bernoulli KL over the complete public surface:

\[
D_{pj}=\frac1K\sum_{k=1}^K
\left[\widetilde u_k\log\frac{\widetilde u_k}{\widetilde q_{pj,k}}
+(1-\widetilde u_k)\log\frac{1-\widetilde u_k}{1-\widetilde q_{pj,k}}\right].
\]

Use frozen inverse temperature \(\lambda=30\) and equal prior mass \(1/7\):

\[
w_{pj}=\frac{\exp(-30D_{pj})}
{\sum_{j'=1}^7\exp(-30D_{pj'})}.
\]

The KL is public-I1 discrepancy, **not graph predictive accuracy**. Averaging correlated horizon/rho I1 points and fixing lambda are modeling choices. These Gibbs weights are heuristic likelihood-inspired weights, **not a calibrated posterior**.

Code: `phase5_reconstruction_v3_selection.py::bernoulli_kl_energy`, `gibbs_weights`.

## 5. Cartesian joint models and weighting

Enumerate all \(7^3=343\) triples \((a,b,c)\) of provider reconstructions:

\[
W_{abc}=w_{Aa}\,w_{Bb}\,w_{Cc},
\qquad \sum_{abc}W_{abc}=1.
\]

Sort by descending \(W\), with deterministic candidate-ID tie break. This factorization is an explicit modeling assumption (independently inferred provider reconstruction weights), **not** a claim that composed provider response times are independent: their dynamics are coupled by the actual graph simulator.

The canonical method uses **all 343 members**, including low-weight members. Earlier Top14-only M3 was superseded **before reading graph outcomes** because its pre-execution mass audit showed material lost weight (e.g. P1 retained 0.551984, P3 0.961909, P4 0.866545). Do not treat full343 as a retrospectively optimized winner.

Code: `phase5_reconstruction_v3_selection.py::joint_product_support`. Contract: `config_phase5_graph_prediction_v3b_fullsupport.json`.

## 6. Simulation allocation, estimator and nested diagnostics

For each eligible physical (world, graph) cell, distribute **B=1400** trajectory simulations across all 343 joint models. Initialize \(N_j=1\) for every member, then repeatedly allocate the next trajectory to the joint rank maximizing

\[
\frac{W_j^2}{N_j(N_j+1)}
\]

(ties: lower joint rank). This greedily minimizes the one-step reduction of the conservative variance criterion \(\tfrac14\sum_j W_j^2/N_j\). One allocation per provider world is reused across its eligible graph topologies. Distinct member seed blocks and frozen seed registry apply.

For each fixed graph region A, horizon H and compliance threshold rho_query, calculate member graph survival \(\widehat\sigma_{G,j}(A,H;\rho_{query})\) from its native *top-level request ledger*, using the existing M1 cumulative-compliance estimator. Predict

\[
\widehat\sigma_G^{M3}(A,H;\rho_{query})=
\sum_{j=1}^{343}W_j\widehat\sigma_{G,j}(A,H;\rho_{query}).
\]

Report plug-in conditional MC variance \(\sum_j W_j^2 \widehat p_j(1-\widehat p_j)/N_j\), the conservative upper bound \(\tfrac14\sum_jW_j^2/N_j\), and associated SEs. The plug-in approximation does **not** account for all reconstruction and model-misspecification uncertainty.

**Nested diagnostics:** Top1, Top3, Top14 re-normalize the weights of members already simulated under full343; no added graph simulations and **not cost-matched** against M1/M2. Report retained/omitted full-support mass and truncation diagnostics, which are bounds relative to the internal weighted support, **not bounds against white-box truth**.

Code: `run_phase5_graph_prediction_v3b_fullsupport.py` (allocation, graph ledger execution, `_member_curves`, `_m3_predictions`).

## 7. Graph-region construction: separate deterministic input from stochastic inference

In historic I1-M1/M2 same-region pilots, public I1 provider admissibility rectangles \(A_p(\rho_{region})\) were *forward-composed* according to known graph structure to define \(A_G^{I1}(\rho_{region})\), including known fixed stages:

- sequence: L boundaries sum, C boundaries sum, Q boundary min;
- parallel-all: L boundary max, C boundaries sum, Q boundary min;
- nested graph: recurse.

These are **M0-derived boundary-algebra rules reused as the common evaluation region**, not M1/M2/M3's method of propagating survival. The graph simulation captures actual queuing, interdependence and runtime effects when predicting survival *under* that common region.

When specifying the next I1-M3 pilot, follow the already agreed M1/M2 same-region procedure: derive graph queries from public I1, freeze query set, simulate reconstructed models, freeze M3 predictions, and evaluate WB *on exactly the same query region*. Neither the WB generator parameters nor outcome curves inform inference.

**Do not use** `i1_m3_graph_region_pilot.py::graph_rho_regions` as the primary new pilot's A_G construction. That file is a preliminary alternative experimental extraction from simulated graph data; it has four engineering tests but is **not the M1/M2-consistent primary method**. Its existence is not a reason to introduce a new graph-region inference objective.

The previous Phase-5 V3b graph prediction instead took 15 *Step-0 frozen scaled graph queries* per eligible physical cell (5 rho × Easy/Mid/Stress). This is distinct from a new pure induced-region pilot. Preserve old Phase-5 contracts and data unchanged.

## 8. Scope, evaluation, and firewall

**New pilot target:** \((I_1,G,\rho)\mapsto(A_G^{I1}(\rho),\widehat\sigma_G^{M3}(A_G^{I1}(\rho),H;\rho))\), on reasonable heterogeneous providers (P2 proposed for development, P4 available as later stress). The graph-region value must be reproducible from public I1 + known G and its fixed terms; evaluate sigma error against independent WB trajectories on matching queries.

**Important limitation:** Existing Phase-5 P2 failed **all four Step-0 eligible-cell gates** under the *old scaled-query battery*; therefore old Phase-5 P2 lacks a qualifying frozen V3b graph-prediction cell. A new induced-query pilot requires its own separately specified, pre-frozen protocol and evidence, without retroactively revising Phase-5 results or hiding this exclusion.

Primary graph survival score: RMSE over declared (rho,H,graph) points, with MAE/bias and per-regime diagnostics. Do not mistake reconstruction parameter error, local I1 RMSE, or agreement with WB's unknown generating parameters for the primary end-to-end scientific score. Note possible lack of informative variation (all near 0/1), even when configurations are physically realistic.

No algorithm selection, parameter weights, query construction, lambda, or simulation allocation may depend on hidden generating parameters or held-out white-box outcomes. Do not import PPG's unpublished GP+DVI mechanism, code/data, readiness score or old experimental setup.

Scientific limitations to report: finite seven-fit candidate coverage; local non-identifiability may be amplified by graph composition; weights not calibrated posteriors; correlated disclosed I1 evidence; fixed in-family Gamma/FCFS truth; high MC sparsity across 343 members; cost imbalance vs M1/M2; Step-0 gate conditioning in the old battery.

## 9. Exact recovery map

Read the following in order when resuming work:

1. **This document**, for consolidated method semantics and distinctions.
2. `config_phase5_provider_reconstruction_v3.json`: candidate generation, seeds, local rescore/replay.
3. `config_phase5_provider_reconstruction_v3b.json`: canonical common-bank RMSE M1/M2 selection and seven-member M3.
4. `phase5_reconstruction_v3_selection.py`: exact KL/Jeffreys formula, Gibbs normalization and joint support.
5. `config_phase5_graph_prediction_v3b_fullsupport.json`: weights, 343-member graph allocation, nested diagnostics, freeze/wall rules.
6. `config_phase5_seed_registry_v3b_fullsupport.json`: disjoint graph seed blocks.
7. `run_phase5_graph_prediction_v3b_fullsupport.py`: executable graph simulation/aggregation and data formats.
8. `run_m1_graph_prediction_v2.py::build_empirical_graph_sigma_curve`: actual graph survival estimator.
9. `phase3/m0_analytic_composition.py` and `phase3/run_m1_graph_prediction_v2.py::build_public_induced_global_boundary`: public-I1-induced graph region only.
10. `config_phase5_recoverability_battery_v2.json`, `run_phase5_step0_v2.py`, `phase5/README.md`: provider worlds, graph topologies, historical eligibility.
11. `I1_M3_JOINT_GOAL_FREEZE_2026-10-12.md`: revised pilot objective and its current boundary-composition clarification.

**Recovery rule:** Verify file contents and freeze manifests before editing or executing. Keep a separate new pilot namespace/configuration instead of modifying frozen Phase-5 artifacts. Do not silently swap original V3 behavioral-centroid selections, V3b RMSE selections, historical Top14, or current full343.
