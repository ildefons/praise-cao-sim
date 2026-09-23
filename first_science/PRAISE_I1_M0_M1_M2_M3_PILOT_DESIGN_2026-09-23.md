# PRAISE/CAO: I1 method-sweep design after final M2 sigma-regime validation

**Status:** current pilot-program design and development source of truth. I1, M0, M1-v2, and M2 are frozen and closed for the present pilot. The final fixed-graph sigma-regime battery has been completed prospectively. M3 is the next method-development stage.  
**Date:** 23 September 2026.

This note supersedes `PRAISE_I1_M0_M1_M2_M3_PILOT_DESIGN_2026-09-16.md` where the two conflict. Earlier notes and contracts remain part of the provenance record and must not be rewritten to make the final result look cleaner.

## 1. Scientific object

The pilot studies the pair

`tau = (I, M)`

where `I` is the provider information representation and `M` is the integration/composition method.

The present sweep holds the provider disclosure fixed at **I1** and changes only the method:

`(I1,M0) -> (I1,M1) -> (I1,M2) -> (I1,M3)`.

The purpose is to determine how much graph-level survival can be recovered from the same public provider cards by changing the integration mechanism rather than revealing more provider information.

The authoritative survival quantity remains

`Sigma_G(A,H;rho) = P(c_G(A,H) >= rho)`

where `c_G(A,H)` is the fraction of requests decided by horizon `H` that satisfy admissibility region `A`. Unresolved requests are excluded from the denominator and zero-decision compliance is `1.0`. Sigma is therefore a cumulative-compliance survival probability, not a first-passage/no-violation functional.

## 2. Frozen physical benchmark and public I1

The final pilot uses one physical process throughout the three sigma regimes:

- hidden provider regime: `D300000000_d0.200`;
- root workload period: `0.2 s`;
- exact logical graph: `Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`;
- exact symmetric G0 network embedding with `PR=0.001 s`;
- horizon support through `240 s`;
- degenerate pilot quality `Q=0.5`.

The public I1 cards remain the frozen rho-conditioned cards acquired from matched D300 evidence. Their public same-rho support is

`rho in {0.95, 0.975, 0.9833333333333333, 0.99, 0.995}`.

The final experiment changes **neither graph nor provider process nor workload nor I1** across G0/G1/G2.

## 3. Final sigma-regime design

The final battery was deliberately constructed to avoid the floor/ceiling degeneracy that made earlier graph-change experiments uninformative.

For each rho, first compose the frozen public I1 provider boundaries through the exact G0 graph to obtain the base global region

`A_G^base(rho) = (l_base, c_base, q_base)`.

The only regime control is a scalar query tightness

`A_G(s,rho) = (s*l_base(rho), s*c_base(rho), q_base(rho))`.

No physical execution parameter changes across regimes.

### 3.1 Regime targets

The final regime statistic is the mean sigma over every frozen horizon point from `H=60..240 s`:

`mean_sigma_60:240 = mean_H Sigma_G(A_G,H;rho)`.

The three target bands are:

| Regime | Target mean-sigma band | Target center | Interpretation |
| --- | ---: | ---: | --- |
| G0 | [0.95, 1.00] | 0.975 | high-survival / nominal |
| G1 | [0.75, 0.90] | 0.825 | intermediate |
| G2 | [0.40, 0.75] | 0.575 | low-survival / stress |

A minimum adjacent mean-sigma separation of `0.10` is required for every rho.

### 3.2 Step-0 development and confirmation

The first V1 calibration rule required every individual finite-N sigma estimate in the H=60..240 window to remain inside the target interval. Independent confirmation showed that this was an unnecessarily brittle extreme-value criterion. V1 is retained as failed development evidence.

V2 was frozen before opening new evidence. It uses the scientifically intended regime-level statistic, the mean sigma over H=60..240.

Development evidence:

- seeds `32000..32099` and `32100..32199`;
- pooled `N=200`;
- used only to select the scalar `s` values;
- M0/M1/M2 forbidden during Step 0.

Fresh independent confirmation:

- seeds `32200..32399`;
- `N=200`;
- selected regions fixed before confirmation;
- no reselection after confirmation.

All 15 rho x regime queries passed.

The confirmed regime means are approximately:

- G0: `0.964..0.977`;
- G1: `0.830..0.844`;
- G2: `0.587..0.639`.

Thus the final experiment provides three clearly separated survival regimes on the **same physical graph and same hidden provider process**.

## 4. Frozen methods

### M0: analytic product baseline

M0 keeps the frozen topology-aware boundary algebra and same-rho provider-product probability rule

`sigma_G^M0(H;rho) = product_i sigma_i(A_i(rho),H;rho)`.

Operational M0 is only valid when its induced public-I1 global boundary is sufficient for the requested calibrated `A_G`. In the final battery:

- G0: applicable for 5/5 rho values;
- G1: applicable for 4/5;
- G2: applicable for 0/5.

Where it is not applicable, the operational output is `NOT_APPLICABLE`; the raw product may be retained only as a labeled diagnostic.

### M1: one reconstructed latent process per provider

M1 maps each frozen public I1 card to one simulator-compatible point surrogate

`theta_i = (mu_i, kappa_i, CV_i)`

and composes the three point surrogates through the native graph.

M1 remains frozen exactly as selected from public-I1 reconstruction. No graph-WB retuning is allowed.

### M2: ambiguity-preserving joint ensemble

M2 preserves inverse ambiguity by carrying three independently confirmed, deliberately diverse I1-compatible surrogates for each provider.

The operational graph portfolio is

`P_G = P_A x P_B x P_C`

with exactly `3 x 3 x 3 = 27` members.

Every joint member has equal weight `1/27`. M1 is not an M2 member.

Primary M2 outputs are:

`sigma_bar_G^M2 = (1/27) sum_m sigma_G^(m)`

and the finite-portfolio ambiguity range

`R_G^M2 = [min_m sigma_G^(m), max_m sigma_G^(m)]`.

The range is a model-ambiguity diagnostic, **not** a confidence interval and not a calibrated posterior interval.

## 5. Blind prediction and final prospective evaluation

After Step-0 confirmation, the 15 query regions were frozen.

Blind prediction:

- seeds `33000..33099`;
- `N=100` trajectories per variant;
- 28 variants total: BASE_M1 + 27 frozen M2 members;
- common random numbers across all variants;
- one graph ledger per variant reused across all 15 queries;
- predictions and all hashes frozen before final WB.

Final prospective WB:

- seeds `34000..34099`;
- `N=100`;
- exact matched D300 process;
- exact same fixed graph;
- one WB ledger reused across all 15 queries;
- generated only after the blind-prediction freeze.

No method repair, member replacement, reweighting, or post-hoc member selection is allowed after this evaluation.

## 6. Final result

The most informative regime-focused comparison is H=60..240, the same window used to define the regimes.

| Regime | M0 MAE | M1 MAE | M2 MAE | M1 bias | M2 bias |
| --- | ---: | ---: | ---: | ---: | ---: |
| G0 | 0.6408 | **0.0137** | 0.0191 | +0.0137 | -0.0168 |
| G1 | 0.5229* | 0.1417 | **0.0842** | +0.1417 | +0.0220 |
| G2 | N/A | 0.4549 | **0.1918** | +0.4549 | +0.1918 |
| whole battery | 0.5884* | 0.2034 | **0.0984** | +0.2034 | +0.0656 |

`*` M0 is evaluated only on its applicable support, so its whole-battery and G1 numbers are not on identical support to M1/M2.

The main pattern is therefore not “M2 wins everywhere.”

- In G0, the single M1 surrogate is already sufficient and is slightly more accurate than the M2 mean.
- In G1, M2 reduces MAE from `0.1417` to `0.0842`.
- In G2, M2 reduces MAE from `0.4549` to `0.1918`.
- Across all 15 queries, M2 approximately halves M1 error.
- M1 becomes increasingly overoptimistic as the query tightens and remains near `sigma=1` even when WB survival falls strongly.
- M2 moves in the correct direction with regime difficulty and preserves substantially more compositionally relevant information, although it is still overoptimistic in G2.
- M0 is strongly conservative where applicable and loses applicability as the requested global region becomes tighter than the induced public-I1 boundary.

This supports the mechanism:

`M1 point-identification discards inverse ambiguity that is largely irrelevant near the nominal high-survival regime but becomes compositionally important as the admissibility query tightens.`

M2 is therefore the strongest **overall** method in the completed I1 sweep so far, while the G0 result shows that ambiguity preservation is not automatically beneficial when the operating/query regime is easy.

## 7. M2 ambiguity-range result

Across H=60..240, the finite M2 range has:

| Regime | WB coverage | Mean width | Max width |
| --- | ---: | ---: | ---: |
| G0 | 1.000 | 0.075 | 0.26 |
| G1 | 0.724 | 0.286 | 0.74 |
| G2 | 0.595 | 0.544 | 0.97 |

The range expands strongly as the regime becomes harder, which is qualitatively useful: the ensemble signals increasing inverse ambiguity.

However, coverage degrades from G0 to G2. The finite 27-member range is therefore **not calibrated uncertainty**. It should be interpreted only as the spread induced by the frozen representative portfolio.

## 8. Final diagnostic plot

The final frozen curves make the mechanism visible directly:

![Final fixed-graph sigma-regime curves: WB vs M0, M1 and M2](phase4/results/sigma_regime_final_evaluation_v1/sigma_regime_curves_5x3.png)

Legend convention:

- black solid: WB;
- orange dashed: operational M0;
- green dash-dot: M1;
- blue solid: M2 mean;
- blue band: M2 finite-portfolio min-max range.

The plot is generated by

`phase4/plot_sigma_regime_diagnostic.py`

from the frozen final comparison table. It does not rerun simulation or alter any scientific result.

## 9. Development method learned from M2

The M2 work establishes a development protocol that should be reused for later methods.

### Gate 0: provenance before method work

Before method comparison, verify that:

- hidden provider process matches the public information provenance;
- graph implementation is the intended graph;
- workload and rho/horizon support are fixed;
- no stale selector or superseded configuration is silently active.

A prediction result is not interpretable until provenance is clean.

### Gate 1: calibrate the evaluation regime without using the methods

Use WB only to construct a nondegenerate diagnostic regime battery. The calibration stage may choose **queries/conditions only**. It may not fit, select, weight, or repair M0/M1/M2.

This separates experimental design from method evaluation.

### Gate 2: independently confirm the regime battery

Use a fresh seed bank to confirm that the calibrated battery actually occupies the intended survival ranges. If confirmation fails, create a new explicitly versioned design. Do not silently retune a frozen design.

### Gate 3: freeze blind method predictions

Run the frozen methods on a fresh prediction bank, materialize all curves, and hash-freeze the outputs before opening the final WB evidence.

### Gate 4: open final WB once

Use a fresh, disjoint final WB bank. Compute the predeclared metrics and close the method regardless of whether the result is favorable.

### Gate 5: learn mechanism, not repair the result

A final failure may motivate a **new method class**, but it must not trigger post-hoc repair of the evaluated method.

This is now the standard development discipline for the rest of the I1 method sweep.

## 10. Historical G1 and provenance correction

The earlier asymmetric-network G1 experiment is retained only as historical forensic/stress evidence. It is not part of the final clean M-axis comparison because its original WB was generated from a D330 physical provider process while the frozen I1 cards came from D300.

That provenance mismatch was diagnosed and recorded before the final battery.

The current G0/G1/G2 labels refer exclusively to the **fixed-graph sigma-regime battery** above. They are regime labels, not graph-topology variants.

## 11. M3 result: weighted dominant-mass composition

M3 is now closed with a positive prospective same-condition replication result.

The original 100x20 versus 200x10 sampling plan was superseded before graph execution after the public-I1-selected weighted distribution was found to be strongly concentrated. The final M3 construction is:

`public I1 -> blocked-CV Gibbs weighting -> exact joint product weights -> 99.9% dominant-mass truncation -> minimax graph-trajectory allocation`.

Public-I1-only blocked cross-validation selected the global concentration parameter

`lambda = 30`.

The resulting joint distribution is highly concentrated. The minimal set exceeding 99.9% cumulative mass contains 14 joint latent hypotheses with retained mass

`m = 0.999174197`,

giving the pointwise deterministic bound

`|sigma_full(q)-sigma_top14(q)| <= 0.000825803`.

Two graph budgets were frozen before the fresh WB:

- M3 B=1400;
- M3 B=2000.

On the fresh matched-D300 WB bank, seeds 38000..38199 and N=200, the H60..240 whole-battery results were:

| Method | Graph trajectories | MAE | RMSE | Bias | Max abs. error |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | reference single latent model | 0.185171 | 0.230736 | +0.185171 | 0.535000 |
| M2 | 2700 | 0.068153 | 0.094141 | +0.047375 | 0.302593 |
| M3 B=1400 | 1400 | 0.030368 | 0.035783 | +0.028240 | 0.114088 |
| M3 B=2000 | 2000 | 0.027547 | 0.033064 | +0.024468 | 0.110645 |

Compared with M2, M3 B=1400 reduces MAE by about 55.4% while using about 48% fewer graph trajectories. M3 B=2000 reduces MAE by about 59.6% while using about 26% fewer graph trajectories.

The regime dependence is central:

- G0: M2 MAE 0.023640, M3 B=1400 0.023632, M3 B=2000 0.020931;
- G1: M2 0.070548, M3 B=1400 0.035529, M3 B=2000 0.031585;
- G2: M2 0.110273, M3 B=1400 0.031945, M3 B=2000 0.030127.

Thus M3 adds little in the easiest regime but strongly improves the intermediate and difficult regimes, especially by reducing M2's positive bias in G2.

The current pilot conclusion is:

`With provider disclosure fixed at I1, one latent reconstruction is adequate only in the easiest high-survival regime. Preserving inverse ambiguity improves harder composition queries, and weighting that ambiguity by public-I1 predictive plausibility plus certified dominant-mass quadrature substantially improves accuracy and computational efficiency without additional provider disclosure.`

Detailed M3 design, derivations, guardrails, and final result:

`PRAISE_I1_M3_WEIGHTED_SAMPLING_PLAN_2026-09-23.md`.

Dynamic/incremental integration remains deferred to a later method, provisionally M4.

## 12. Pilot guardrails

- I1 remains frozen during M3 unless an explicit information-axis experiment is opened.
- M0, M1 and M2 are closed; do not repair them against final WB.
- Preserve the PPG firewall.
- Keep graph/query-regime calibration separate from method fitting.
- Report applicability separately from prediction error.
- Do not call M2 min-max spread a confidence interval.
- Keep computational cost as a first-class method property.
- Do not use the present degenerate `Q=0.5` pilot as a general PRAISE assumption.

The current pilot conclusion is:

`With provider disclosure fixed at I1, preserving inverse ambiguity is unnecessary near the easiest high-survival regime but becomes increasingly valuable as the global admissibility query tightens. The remaining G2 bias motivates a new integration mechanism rather than repair of the frozen M2 ensemble.`
