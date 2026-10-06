# Phase-5 V3b graph-prediction execution contract

**Frozen:** 2026-10-06  
**Status:** pre-graph-prediction. No V3b graph prediction or final graph white-box result has been used to choose this contract.

This contract freezes the graph-prediction stage after the completed V3b reconstruction-selection audit.

## 1. Eligibility

Use the already frozen Step-0 eligibility map exactly. The runner reads the frozen eligibility manifest/table rather than recomputing eligibility.

- P1: four graph cells eligible.
- P2: all four graph cells remain `GATE_FAILED_STEP0`; no graph prediction is run for P2.
- P3: four graph cells eligible.
- P4: four graph cells eligible.

Thus 12 of 16 physical cells receive blind predictions. There is no Step-0 repair, reselection, or recalibration.

## 2. Methods

The V3b battery contains exactly M0, M1, M2, M3-Top1, M3-Top3, and M3-Top14.

The old V2 `LHS_MSE_TOP1_DIAG` is not carried forward because it was defined on the old 48-point LHS bank and no longer isolates a meaningful scoring contrast in the seven-candidate V3b construction.

M0 is unchanged.

M1 propagates the single V3b RMSE-rank-1 provider reconstruction for A, B, and C.

M2 propagates the Cartesian product of the three best V3b provider reconstructions, giving 27 equal-weight joint models. Its operational point prediction is the equal-weight mean. All 27 member curves are retained. Their pointwise minimum and maximum are reported only as a descriptive finite spread among the three-best reconstruction combinations, not as a confidence interval and not as a deliberately diversity-maximized ambiguity range.

M3 retains all seven candidates per provider and the already frozen Jeffreys-smoothed Bernoulli-KL Gibbs weights. The full support is 343 joint models. Rank the support by descending product weight and retain frozen ranks 1..14 for graph execution.

## 3. Graph Monte Carlo

M1 and every M2 joint member use the frozen common seed bank 56900..56999, N=100. The same seed bank is reused across models and eligible physical cells as common random numbers.

M3 has total graph budget B=1400 per eligible physical cell. Let alpha_j be each Top14 joint weight renormalized over ranks 1..14. Freeze the integer allocation before graph execution by initializing N_j=1 for every retained rank and repeatedly assigning the next trajectory to the rank maximizing

`alpha_j^2 / [N_j (N_j+1)]`.

Ties go to the lower rank. This is the frozen greedy marginal minimizer of the query-independent worst-case Bernoulli variance bound.

Rank r uses seeds

`7000000 + (r-1)*10000 + k`,  k=0,...,N_r-1.

Rank streams are disjoint. The corresponding rank stream is reused across eligible cells as CRN.

Top1, Top3, and Top14 are nested readouts of this same B=1400 Top14 execution. There is no additional cost-matched Top1 or Top3 simulation:

- Top1 uses rank 1 only and renormalizes its weight to one.
- Top3 uses ranks 1..3 and renormalizes their original frozen weights within that subset.
- Top14 uses all retained ranks and renormalizes within Top14.

No graph outcome may alter weights, ranks, support, lambda, allocation, or budget.

## 4. Queries and horizons

Every eligible physical cell uses its 15 already frozen Step-0 queries: five rho values times Easy, Mid, and Stress. No query is regenerated or replaced.

Prediction curves use H=0,5,...,240 s. Primary evaluation later uses H=60,65,...,240 s.

## 5. Provenance and white-box firewall

V3b prediction artifacts are written only under `results/04_prediction_v3b/`. Earlier prediction namespaces remain untouched.

A battery-level global V3b prediction freeze must enumerate all 16 physical cells: 12 hash-frozen prediction cells and four P2 `GATE_FAILED_STEP0` cells. The still-unread final-WB bank, seeds 54000..54999 with N=1000, remains embargoed until that global prediction freeze exists and passes its checks.

Graph prediction may consume public I1, public graph mechanics, frozen eligible-cell query definitions, frozen V3/V3b reconstruction artifacts, and frozen graph seeds. It must not consume hidden generating parameters, private I1 traces, Step-0 white-box values beyond eligibility/query definitions, final graph white-box data, or PPG mechanisms.

## 6. Next gate

Before any scientific graph prediction, a real graph-adapter smoke must execute the frozen graph stack with engineering-only seeds and verify the V3b method plumbing, M2 aggregation, M3 allocation/nested readouts, manifests, hashes, and global-freeze logic. Smoke output is non-scientific and cannot become a scientific input.
