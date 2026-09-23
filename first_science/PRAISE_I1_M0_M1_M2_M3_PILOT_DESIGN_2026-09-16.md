> **SUPERSEDED BY:** `PRAISE_I1_M0_M1_M2_M3_PILOT_DESIGN_2026-09-23.md` is the current design/development source of truth. This 16 September document is retained for provenance.

# PRAISE/CAO: pilot design through I1-M3

**Status:** current pilot-program design source of truth. Phase 1 v2, rho-conditioned I1, M0, M1-v2, and the M2 joint-ensemble method are frozen. G0 is retrospective diagnostic evidence; G1 is retained as a prospective stress test. Final M2 validation is reopened for a Step-0-calibrated G2 condition before M3 begins.  
**Original date:** 16 September 2026. **M2 semantic freeze update:** 21 September 2026.

This note supersedes `PRAISE_I1_M0_M1_M2_DESIGN_2026-09-16.md` where the two conflict. The previous note remains part of the provenance record.

## 1. Scope: this is still the pilot program

The work described here is not yet the final PRAISE tau battery. It is a controlled pilot whose purpose is to learn what information and integration mechanisms are worth carrying into the broader program.

The immediate strategy is to **hold the information representation fixed at I1** and improve the integration method:

`(I1,M0) -> (I1,M1) -> (I1,M2) -> (I1,M3)`.

This isolates the M-axis. Any improvement across these cells must come from the integration method rather than richer provider disclosure.

Richer information technologies remain part of the wider design space, including a possible privacy-preserving transition between I1 and later richer disclosures in which provider sigma is conditioned on anonymous latent state. That information-axis work is deliberately deferred until the I1 method sweep has taught us what is actually missing.

## 2. Frozen pilot state

### Phase 1: white-box reference

Phase 1 v2 is frozen. The current physical regime is `D300000000_d0.200`, root period `0.2 s`, horizon support `H in [0,240] s`, with degenerate `Q=0.5` in the current pilot.

Authoritative admissibility semantics are cumulative compliance:

`Sigma_G(A,H;rho) = P(c_G(A,H) >= rho)`

where unresolved requests are excluded from the denominator and the zero-decision compliance fraction is `1.0`.

### I1: frozen public provider information

`I1_i = ({A_i(rho_region)}, W_i, R_region, R_query, {sigma_i(A_i(rho_region),H;rho_query)})`.

Current public support is

`R_region = R_query = {0.95,0.975,0.9833333333333333,0.99,0.995}`.

The first comparison uses the same-rho diagonal:

`rho_region = rho_query = rho_i = rho_G`.

I1 remains frozen during M2 and the first M3 pilot. Do not enrich I1 merely to improve a method result.

### M0: frozen analytic baseline

M0 uses direct boundary algebra and the provider-product probability rule. The corrected native G0 adapter is

`l_G = 0.014003 + max_i(l_i)`

`c_G = 0.03 + sum_i(c_i)`

`q_G = min_i(q_i)`.

M0 is systematically pessimistic in the current G0 comparison and is retained as the minimal analytic baseline.

### M1-v2: frozen point inverse lift

M1-v2 maps each public I1 card to one simulator-compatible provider surrogate

`theta_i = (mu_i, kappa_i, CV_i)`

and composes those point surrogates through native AICon/YAFS.

The selected A/B/C surrogates are frozen. M1 must not be retuned against graph-level WB.

On G0, M1 substantially improves MAE over M0 for every tested rho, but remains systematically optimistic and nearly saturates at `sigma_G=1` after short horizons. Request-level comparison shows that the reconstructed graph process is much faster and cheaper than WB and has too few tail violations.

Frozen interpretation:

`M0 loses composition structure; M1 restores native composition structure but collapses inverse ambiguity to one latent process.`

## 3. Short-term program: I1-M2 ensemble composition

M2 keeps exactly the same frozen I1 and the same native graph mechanics. Its first purpose is to determine whether the M1 failure is primarily caused by point-identification of a non-identifiable inverse problem.

### 3.1 M2 Gate A: identifiability test

Use the already-generated public-I1 reconstruction landscape to ask:

`Do substantially different theta_i values with similarly good local I1 reconstruction produce materially different graph-level sigma_G after composition?`

Candidate compatibility must be defined using **public-I1 reconstruction quality only**. Graph-level WB may not be used to select ensemble members, tune compatibility thresholds, or choose weights.

If near-equivalent local lifts produce materially different graph predictions, inverse non-identifiability is established as an important mechanism.

If they all produce essentially the same saturated graph prediction, the current Gamma/FCFS surrogate family is itself insufficient and M2 must then introduce a richer latent process family as a separate, explicitly documented step.

### 3.2 Frozen M2 semantics: small diverse joint ensemble

Gate A has established compositionally material inverse ambiguity, especially for Provider C. M2 therefore keeps the already-frozen M2-A4 portfolio of three independently confirmed, deliberately diverse public-I1-compatible surrogates per provider:

`P_A={theta_A1,theta_A2,theta_A3}`

`P_B={theta_B1,theta_B2,theta_B3}`

`P_C={theta_C1,theta_C2,theta_C3}`.

No new local search, GP acquisition, candidate replacement, or parameter retuning is part of the frozen M2 semantics.

The operational M2 graph portfolio is the full Cartesian product

`P_G = P_A x P_B x P_C`,

giving exactly `3 x 3 x 3 = 27` joint latent graph hypotheses. M1 is a separate baseline and is not an ensemble member.

The existing M2-B3 one-provider-at-a-time propagation remains an important diagnostic stage. It established that changing one provider reconstruction while holding the other M1 anchors fixed can materially change graph-level sigma and that Provider C dominates the observed ambiguity. It is not the final operational M2 ensemble.

### 3.3 Frozen M2 weighting and outputs

M2 assigns equal weight to the three frozen representatives of each provider and therefore product weight `1/27` to every joint combination. This is a principle-of-indifference ensemble convention over deliberately diverse representatives. It is **not** a Bayesian posterior, an estimate of natural parameter-space frequency, or a claim that the A4 maximin-selected representatives are iid samples.

For every graph query `(H,rho)`, the two primary M2 outputs are:

`sigma_bar_G^M2(H,rho) = (1/27) sum_m sigma_G^(m)(H,rho)`

and

`R_G^M2(H,rho) = [min_m sigma_G^(m)(H,rho), max_m sigma_G^(m)(H,rho)]`.

The equal-weight mean is the M2 central ensemble prediction. The min-max interval is the **finite-portfolio ambiguity range** induced by the frozen diverse representatives. It is not a statistical confidence interval and is not claimed to be the exact global range over all possible I1-compatible latent models.

Secondary descriptive outputs may include the portfolio median, standard deviation, quantiles, individual member curves, and the identities of the combinations attaining pointwise minima and maxima. Do not weight members by local reconstruction loss in frozen M2, and do not select or weight members using graph WB.

Monte Carlo uncertainty from the finite graph trajectory count is a separate uncertainty source. If reported, it must be displayed separately from the M2 model-ambiguity range.

The current same-region experiment keeps the same induced `A_G` for every joint member. M2 does not infer a new admissibility region in this test, so `D_A`/Jaccard is `N/A`, not zero.

### 3.4 M2 implementation handoff and validation discipline

The next implementation stage is M2-B5 joint portfolio propagation. It must enumerate all 27 frozen A4 combinations, use one fresh common-random-number graph seed bank across combinations, materialize every `sigma_G^(m)` curve, and aggregate the equal-weight mean and finite-portfolio min-max range before any WB evaluation. The exact fresh seed bank belongs in the B5 execution contract.

G0 remains a development and retrospective diagnostic case because its WB result was inspected before this revised M2 semantic freeze. In particular, `ProviderC_LHS_038` remains useful evidence that an independently discovered I1-compatible reconstruction can be highly accurate at graph level, but that post-hoc best member is not the operational M2 prediction.

A strong prospective M2 claim requires the frozen semantics above to be evaluated unchanged on at least one untouched composition/topology, workload, admissibility regime, or other predeclared WB condition.

Authoritative semantic contract: `phase4/config_phase4_m2_joint_ensemble_semantics_v1.json`.


### 3.5 G1 prospective stress test and validation reopening

The frozen M2 method was prospectively tested on G1 after a blind prediction freeze. G1 changed the public network embedding while preserving the logical ParAll graph, workload, provider cards, M1 parameters, M2 members, and M2 weights. Blind prediction used seeds `30000..30099`; independent WB generation used `31000..31099`.

The predeclared M2-vs-M1 criteria passed:

- M1 MAE `0.765469`;
- M2 MAE `0.617345`;
- M1 RMSE `0.804938`;
- M2 RMSE `0.672633`;
- M2 MAE lower than M1 in `5/5` rho slices.

However, inspection of the G1 sigma curves shows that the WB condition is strongly floor-degenerate for the intended dependable-service use case. For several rho values, the WB survival probability rapidly collapses toward zero over the horizon. M0 MAE is `0.202037`, substantially better than both reconstructed-process methods, while the M2 min-max range covers only `0.114286` of the WB surface and `0.885714` of WB points lie below the range.

Therefore G1 is retained as a **prospective stress test**, not as the final representative validation condition for M2.

This does not reopen the M2 method. I1, M1, the three frozen provider representatives, the 27-member Cartesian product, and equal `1/27` weights remain unchanged. No G1-driven repair is permitted.

What is reopened is only the final M2 validation conclusion. Before M3 begins, define a new prospective condition G2 with a predeclared **Step-0 admissibility-region calibration**. The purpose of Step 0 is to select and freeze a nondegenerate high-survival WB regime representative of dependable services before comparing M0/M1/M2.

The exact calibration target band, admissibility-region search rule, calibration seed bank, evaluation seed bank, and success criteria must all be frozen before G2 calibration or evaluation is run. Calibration evidence may choose admissibility regions only; it may not tune M1/M2, select members, alter weights, or optimize prediction error.

After calibration, freeze the selected G2 regions, materialize and hash blind M0/M1/M2 predictions, and only then generate fresh independent WB evaluation trajectories.

Authoritative reopening record: `phase4/M2_REOPENING_FOR_G2_2026-09-22.md`.

Current status:

`M2_METHOD_STATUS = FROZEN_UNCHANGED`

`M2_VALIDATION_STATUS = REOPENED_FOR_CALIBRATED_G2`

`G1_EVIDENCE_ROLE = PROSPECTIVE_STRESS_TEST`

`FINAL_M2_VALIDATION = PENDING_G2`


## 4. Mid-term program: I1-M3 dynamic integration

M3 remains within the pilot and keeps the **same information schema class I1**. It is intended to study dynamic integration rather than richer provider disclosure.

The provisional idea is that providers may emit successive I1-compatible snapshots or updates over time, while the compositor updates its belief/ensemble incrementally rather than rebuilding from scratch.

Conceptually:

`I1(t) + state_of_M2(t-) -> M3 update -> predictive belief over sigma_G(t:t+H)`.

M3 should therefore study at least:

- incremental update versus full rebuild;
- adaptation latency after provider/workload change;
- prediction quality during and after change;
- computational update cost;
- whether ensemble uncertainty contracts or expands appropriately as public evidence changes.

M3 is intentionally not frozen before M2 is understood. The pilot should not add latent-state disclosure to I1 merely to make M3 easier. A latent-state-enhanced information representation belongs to a later information-axis experiment.

## 5. Evaluation battery from M2 onward

Every tau cell should be assessed on three distinct dimensions:

1. **Prediction quality**
   - whole-horizon sigma MAE;
   - RMSE;
   - signed bias;
   - maximum absolute error;
   - curve/coverage diagnostics appropriate to interval-valued M2/M3 outputs.

2. **Admissibility-region quality**
   - geometric region agreement, including Jaccard/J_A where the method predicts or induces A;
   - boundary-component errors where useful;
   - same-region diagnostics when we want to isolate probability integration from region mismatch.

3. **Computational cost**
   - formal machine-independent cost accounting;
   - empirical wall-clock/CPU/memory accounting.

Prediction accuracy must not be reported without the corresponding computational budget once M2 development begins.

## 6. Computational-cost accounting protocol

From M2 onward, every scientific run should emit a cost manifest. M0 and M1 should be backfilled where reliable measurements already exist, but no historical number should be invented.

### 6.1 Formal cost counters

At minimum record:

- number of optimizer/objective evaluations;
- number of local provider simulation trajectories;
- number of graph simulation trajectories;
- number of ensemble members or posterior samples used;
- number of graph-member combinations actually evaluated;
- number of processed requests/events when available;
- for dynamic M3, number of updates and number of recomputed versus reused components.

Where possible, summarize asymptotic or structural cost separately for:

`C_build`: one-time construction/calibration cost;

`C_query`: cost of one graph prediction after the method is built;

`C_update`: cost of incorporating one new public update;

`M_peak`: peak retained model/ensemble state size.

### 6.2 Empirical cost counters

Record for each scientific run:

- wall-clock elapsed time;
- user CPU time;
- system CPU time;
- peak resident memory when practical;
- hardware identifier sufficient to contextualize timing;
- software/git revision and random-seed contract.

GNU `/usr/bin/time -v` or an equivalent reproducible wrapper is preferred for new runs so peak RSS is captured in addition to `real/user/sys`.

### 6.3 Accuracy-cost frontier

M2 should be evaluated over more than one computational budget, for example multiple ensemble sizes or sample counts selected before graph-WB inspection. The scientific object is then not only `error(M2)` but the trade-off

`prediction quality <-> computational cost`.

The same principle should carry into M3 via update frequency and incremental-update budget.

## 7. Pilot decision gates and priorities

### Immediate priority

Freeze and archive the M0/M1 evidence, then run the M2 identifiability gate using the existing public-I1 search landscapes.

### Next priority

If Gate A supports non-identifiability, implement the smallest ambiguity-preserving M2 ensemble and characterize its accuracy-cost curve. If Gate A instead implicates model-class insufficiency, define the smallest richer M2 latent family without changing I1.

### Fresh validation

The next scientific priority is G2: predeclare a Step-0 calibration rule, use calibration-only WB seeds to select a nondegenerate high-survival admissibility-region battery, freeze it, then perform blind M0/M1/M2 prediction followed by fresh independent WB evaluation.

### Mid-term

Do not begin M3 until G2 closes M2 validation. After G2, define M3 over the same frozen I1 schema and evaluate its intended mechanism under a scientifically informative validation regime.

### Deferred information-axis work

After the I1 method sweep, revisit the information ladder. A leading candidate is a privacy-preserving intermediate representation in which sigma remains the exposed primitive but is conditioned on anonymous latent operating state. Only after that should the pilot consider richer I2/I3-style disclosure.

## 8. Pilot guardrails

- Phase 1, I1, M0, and M1-v2 remain closed except for concrete scientific or implementation defects.
- M2 and M3 are new methods, not M1 repairs.
- Do not choose M2 members, weights, thresholds, or budgets using graph-WB performance.
- Do not enrich I1 during the I1 method sweep.
- Do not treat the current degenerate `Q=0.5` benchmark as a general PRAISE assumption.
- Do not confuse the current pilot roadmap with the final tau battery.
- Preserve the strict PPG firewall throughout.

The short/mid-term pilot question is therefore:

`With provider disclosure fixed at I1, how much graph-level reliability can be recovered by moving from analytic composition, to one reconstructed process, to ambiguity-preserving ensemble composition, and finally to dynamic integration, and at what computational cost?`
