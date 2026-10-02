# PRAISE/CAO: Prospective Recoverability Battery Protocol V2

**Status:** FROZEN BEFORE SCIENTIFIC EXECUTION  
**Date:** 2 October 2026  
**Supersedes:** `PRAISE_PROSPECTIVE_RECOVERABILITY_BATTERY_PROTOCOL_2026-10-02.md` (V1)  
**Machine-readable source:** `phase5/config_phase5_recoverability_battery_v2.json`  
**Seed registry:** `phase5/config_phase5_seed_registry_v2.json`  
**Method-instantiation rules:** `phase5/config_phase5_method_instantiation_v2.json`  
**Execution/artifact contract:** `phase5/config_phase5_execution_contract_v2.json`  
**Prospective analysis contract:** `phase5/config_phase5_analysis_addendum_v2.json`

V2 was frozen before any Phase-5 scientific execution. V1 remains immutable provenance. The V2 revision sharpens reference precision, prospective analysis, provenance, and one secondary scoring diagnostic; it does not alter the four provider worlds, four graphs, workload, public-I1 interface, Step-0 query family, M0-M3 primary methods, M3 lambda, M3 Top14 rank count, or primary prediction budgets.

## 1. Scientific purpose

The battery asks when graph-level SLA-survival prediction is recoverable from limited provider disclosure and how recoverability changes with hidden provider operating condition, composition structure, SLA query regime, and integration method.

The authoritative target is

$$
\Sigma_G(A,H;\rho)=P(c_G(A,H)\geq\rho).
$$

There is no numerical performance pass/fail threshold. The intended scientific sequence is

$$
\text{controlled battery}
\rightarrow
\text{empirical regularities}
\rightarrow
\text{mechanistic interpretation}
\rightarrow
\text{candidate theory}.
$$

Poor prediction in a valid frozen condition is a scientific result.

## 2. Development/confirmatory separation

The completed pilot world

$$
P_{dev}=(D=300\text{ M},\delta=0.20)
$$

is development evidence only and is excluded from the confirmatory battery.

No pilot graph-WB result may be used to repair a Phase-5 method after this freeze. The pilot fixed, among other things, M3's Jeffreys-smoothed Bernoulli-KL scoring family, $\lambda=30$, and the fixed Top14 production support rule.

## 3. Frozen workload and provider family

The workload is invariant:

$$
W=W_0,\qquad T_{arrival}=0.2\text{ s}.
$$

Workload is not an experimental axis. Graph-induced downstream timing changes are graph consequences.

All four worlds use the same hidden provider family as the pilot:

- three providers A/B/C;
- one-server FCFS native provider modules;
- Gamma service/instruction variability;
- hidden $CV=0.3$;
- effective $IPT=10^9$;
- hidden cost rate $\kappa=3$;
- execution fraction $x=0.5$;
- quality $Q=0.5$.

The hidden means are

$$
\mu_A=D(1-\delta),\qquad
\mu_B=D,\qquad
\mu_C=D(1+\delta).
$$

This battery is therefore a **well-specified-family** experiment: operating condition and load concentration vary, but the hidden process remains inside the simulator family searched by M1-M3. Robustness to service-family or server-structure misspecification is explicitly deferred to a separate follow-up experiment.

## 4. Frozen provider worlds

| ID | $D$ | $\delta$ | hidden means A/B/C (M instr.) | approx. utilization A/B/C |
|---|---:|---:|---:|---:|
| P1 | 330 M | 0.00 | 330 / 330 / 330 | 0.825 / 0.825 / 0.825 |
| P2 | 330 M | 0.15 | 280.5 / 330 / 379.5 | 0.701 / 0.825 / 0.949 |
| P3 | 360 M | 0.00 | 360 / 360 / 360 | 0.900 / 0.900 / 0.900 |
| P4 | 360 M | 0.10 | 324 / 360 / 396 | 0.810 / 0.900 / 0.990 |

Utilization is interpretive only and is never exposed to reconstruction methods.

P1/P3 are symmetric worlds. P2/P4 jointly introduce provider spread and concentrate utilization toward ProviderC. Therefore P2/P4 versus P1/P3 is not interpreted as a pure heterogeneity effect.

## 5. Frozen graph structures

Provider placement is fixed:

- **G_PAR:** `ParAll(A,B,C)`
- **G_SEQ:** `Seq(A,B,C)`
- **G_SEQPAR:** `Seq(A,ParAll(B,C))`
- **G_PARSEQ:** `ParAll(A,Seq(B,C))`

The full graph remains

`Source -> Fpre -> <provider composition> -> Fpost`.

Deterministic stages, network semantics, bandwidth, propagation delay, message sizes, placement, and native composition-control semantics are inherited from the frozen pilot. The primary battery uses only `sequence` and `parallel_all`.

## 6. Public I1

Each provider world receives newly generated rho-conditioned public I1 cards using the frozen pilot interface/acquisition semantics.

The public rho support is

$$
\rho\in\{0.95,0.975,0.9833333333333333,0.99,0.995\}.
$$

For each provider world:

- I1 region construction uses $N=100$ provider-local trajectories;
- public-sigma estimation uses a disjoint $N=100$ provider-local trajectories;
- the same frozen public cards are reused across all four graphs.

I1 evidence is disjoint from Step-0, provider-reconstruction, graph-prediction, and final-WB evidence. The PPG firewall remains in force.

## 7. Step-0 Easy/Mid/Stress query construction

For every $(P,G,\rho)$, Step 0 chooses three nondegenerate SLA regions using

$$
\bar{\sigma}_{60:240}
=
\operatorname{mean}_{H\in\{60,65,\ldots,240\}}
\Sigma_G(A,H;\rho).
$$

| Regime | target mean-$\sigma$ interval | target center |
|---|---:|---:|
| Easy | [0.95,1.00] | 0.975 |
| Mid | [0.75,0.90] | 0.825 |
| Stress | [0.40,0.75] | 0.575 |

Minimum adjacent mean-$\sigma$ separation is 0.10.

For each $(P,G,\rho)$, public I1 provider boundaries are forward-composed through the exact graph to obtain $A_G^{base}$, then

$$
A_G(s,\rho)=(s l_{base},s c_{base},q_{base})
$$

is searched over $s\in[0.5,2.0]$ in steps of 0.01, with

$$
s_{Stress}<s_{Mid}<s_{Easy}.
$$

Calibration uses $N=200$ WB trajectories per physical cell. After the 15 queries are selected and frozen, fresh disjoint $N=200$ trajectories confirm them. No reselection is allowed.

A failed Step-0 confirmation excludes **only that physical $(P,G)$ cell** as `GATE_FAILED_STEP0`. The failed cell is reported, not repaired or replaced, and receives no blind prediction or final WB. Other eligible cells continue.

## 8. Battery size

Before any Step-0 exclusions there are

$$
4P\times4G=16
$$

physical cells and

$$
5\rho\times3\text{ regimes}=15
$$

queries per physical cell, for 240 query cells.

## 9. Primary methods

The six primary readouts remain

$$
M0,\ M1,\ M2,\ M3\text{-Top1},\ M3\text{-Top3},\ M3\text{-Top14}.
$$

### M0

Frozen topology-aware analytic baseline. Sequence uses latency sum, cost sum, quality min. Parallel-all uses latency max, cost sum, quality min. If its frozen boundary-containment precondition fails, report `NOT_APPLICABLE`.

### M1

One public-I1-only simulator-compatible reconstruction per provider,

$$
\theta_i=(\mu_i,\kappa_i,CV_i),
$$

using the frozen TPE/MSE inverse-simulation procedure. One public-I1-only boundary expansion is allowed under the frozen rule. Graph-WB can never trigger expansion.

### M2

Three independently confirmed public-I1-compatible surrogates per provider, propagated as the complete $3^3=27$ equal-weight Cartesian portfolio. Its finite member range is model ambiguity, not a confidence interval.

### M3

M3 uses the 48/provider nonadaptive LHS proposal, fresh public-I1-only Jeffreys-smoothed Bernoulli-KL rescoring, factorized Gibbs weights with frozen $\lambda=30$, and fixed joint ranks 1..14.

The production graph budget is

$$
B=1400
$$

per eligible physical cell. Top1, Top3 and Top14 are nested readouts from the same production member ledgers. They are **not** an equal-total-budget support ablation; their effective graph-MC sample sizes differ according to the frozen Top14 allocation.

Retained/omitted Gibbs mass and the finite-support truncation bound are reported per world. The truncation bound is internal to the finite M3 support and is never interpreted as a truth-error guarantee.

## 10. Secondary common-bank scoring diagnostic

A prospectively declared secondary diagnostic, `LHS_MSE_TOP1_DIAG`, uses the same 48/provider nonadaptive LHS candidate bank and the same fresh $N=100$ M3 local-rescore ledgers.

For each provider, define raw-sigma MSE on the complete public I1 surface with $H>0$:

$$
E_{MSE}(\theta)=
\operatorname{mean}(\sigma^{I1}-\sigma^{\theta})^2.
$$

Select the minimum-MSE candidate independently per provider and form the corresponding three-provider joint Top1 model.

Graph propagation uses $N=100$ trajectories per eligible physical cell on exactly the first 100 seeds of the M3 rank-1 stream. The matched KL comparator is the M3 KL-ranked Top1 evaluated on the first 100 trajectories of its production rank-1 ledger using the same seeds.

Thus LHS-MSE versus LHS-KL compares scoring rules on a common candidate bank, common local evidence, and paired graph Monte Carlo. M1 versus LHS-MSE is interpreted only as a broader search/candidate-generation-pipeline contrast, not a pure causal search ablation.

This diagnostic adds no provider-local simulation and is not a headline method.

## 11. Final white-box reference

Final graph-WB precision is frozen prospectively to

$$
\boxed{N_{WB}=1000}
$$

per eligible physical $(P,G)$ condition.

One physical WB ledger is reused across the cell's 15 queries. Seeds are 54000..54999.

No final-WB trajectory may be generated or opened until a **battery-level global prediction-freeze manifest** records every one of the 16 physical cells as either:

1. prediction-frozen, with hashes for all primary and diagnostic prediction artifacts; or
2. `GATE_FAILED_STEP0`.

Finite-$N$ reference uncertainty remains reported explicitly. Any later increase beyond $N=1000$ is a separately declared follow-up.

## 12. Evaluation and continuous recoverability profile

Primary evaluation uses $H=60,65,\ldots,240$ s.

Primary metrics are:

- MAE;
- RMSE;
- signed bias;
- maximum absolute error.

Required summaries include whole battery, provider world, graph, Easy/Mid/Stress, rho, provider-world x graph, graph x regime, provider-world x regime, and rho x regime.

Each eligible physical cell also receives a continuous recoverability profile containing MAE, RMSE, signed bias, maximum absolute error, reference-noise-adjusted RMSE, false-accept rate, and false-reject rate. No arbitrary binary recoverable/not-recoverable threshold is introduced.

The reference-noise-adjusted RMSE is

$$
\operatorname{RMSE}_{adj}
=
\sqrt{
\max\left(
0,
\operatorname{mean}
\left[
(\hat\sigma-\hat\sigma_{WB})^2
-
\frac{\hat\sigma_{WB}(1-\hat\sigma_{WB})}{N_{WB}-1}
\right]
\right)
}.
$$

This adjusts only for estimated finite-WB sampling variance. It is not a full correction for method uncertainty.

## 13. Decision interpretation and directional error

The primary SLA decision threshold is

$$
\beta=0.90,
$$

with $\beta=0.80$ and 0.95 as secondary sensitivities.

Accept when $\hat\sigma_G\geq\beta$. Decision agreement, false accepts and false rejects are evaluated on WB-resolvable points where the WB 95% interval does not cross $\beta$.

Signed bias is

$$
\operatorname{Bias}
=
\operatorname{mean}(\hat\sigma-\hat\sigma_{WB}).
$$

A 10,000-replicate reference-only trajectory-cluster bootstrap is predeclared. Predictions remain fixed. Complete WB trajectory indices are resampled jointly across all queries/horizons, and jointly across physical cells wherever the same CRN trajectory index is reused. The interval quantifies finite final-WB reference fluctuation only.

## 14. Prospective topology-sensitivity hypothesis

The pilot motivates a directional masking hypothesis: parallel composition may hide reconstruction errors in provider components to which the composed SLA is relatively insensitive.

For method $M$ and provider world $P$, define

$$
\Delta_P^M
=
\operatorname{MAE}_M(P,G_{SEQ})
-
\operatorname{MAE}_M(P,G_{PAR}).
$$

The masking hypothesis predicts

$$
\Delta_P^M>0.
$$

Define

$$
\Delta_{het}^M
=
\frac{\Delta_{P2}^M+\Delta_{P4}^M}{2}
-
\frac{\Delta_{P1}^M+\Delta_{P3}^M}{2}.
$$

The masking/load-concentration hypothesis predicts

$$
\Delta_{het}^M>0.
$$

These are directional hypotheses, not pass/fail thresholds.

The mixed graphs G_SEQPAR and G_PARSEQ are used for mechanistic triangulation. They are **not** treated as a clean factorial separation of aggregation from workload shift, because topology also changes downstream arrival processes.

## 15. Passive mechanism diagnostics

Where native traces expose the information without changing execution, record:

- SLA violation component: latency, cost, quality, or multiple;
- controlling child at each `parallel_all` join;
- per-provider arrival statistics: number of arrivals, mean/std/CV interarrival time, and p10/p50/p90 interarrival time.

These are analysis-only artifacts. They are never method inputs and cannot alter a method or query. If a passive diagnostic cannot be exposed without semantic changes, record `NOT_AVAILABLE`; this does not invalidate the primary battery.

## 16. M3 Monte Carlo precision

Top1, Top3 and Top14 use the same plug-in weighted Bernoulli variance family:

$$
\widehat{V}(\hat\sigma)
=
\sum_{j\in S}
\tilde w_j^2
\frac{\hat p_j(1-\hat p_j)}{N_j},
$$

where $\tilde w_j$ are weights renormalized within the reported support $S$.

Also report the conservative bound

$$
V_{max}
=
\sum_{j\in S}
\frac{\tilde w_j^2}{4N_j}.
$$

Top1 is simply the $|S|=1$ special case.

## 17. Prospective secondary analyses after the primary battery

The following analyses are declared now but executed only after primary Phase-5 predictions and final-WB evaluation are frozen. They cannot feed back into the methods:

1. **Hidden-truth I1 scoring.** Score the generating $\theta$ on the frozen public I1 and compare its energy/rank with reconstructed candidates.
2. **M3 support as decision warning.** Test whether retained-support ambiguity/envelope diagnostics identify false accepts or false rejects.
3. **Public-sigma card bootstrap.** Conditional on the already frozen I1 region geometry, resample the $N=100$ public-sigma acquisition trajectories, recompute public sigma surfaces and candidate energies/weights from frozen candidate ledgers, and report Top1 identity frequency and weight variability. Candidate trajectories remain fixed and no new simulation is used.

## 18. Prospective execution gates

1. **Engineering smoke:** throwaway seeds and separate `smoke/` outputs; verify all four ASTs, checkpoint/resume, hashes/manifests, M3 nested readouts, LHS-MSE diagnostic, and global-freeze logic. Smoke outputs are not scientific evidence.
2. **Provenance:** verify provider world, workload, graph, network, horizon/rho support, no stale selector, and PPG firewall.
3. **I1:** generate and freeze new public I1 cards.
4. **Step-0 calibration:** choose Easy/Mid/Stress queries without method outcomes.
5. **Step-0 confirmation:** freeze each cell as eligible or `GATE_FAILED_STEP0`; no reselection.
6. **Provider reconstruction:** instantiate/freeze M1, M2, M3 from public I1 only.
7. **Blind graph prediction:** run primary methods and LHS-MSE diagnostic for eligible cells.
8. **Global prediction freeze:** hash-freeze the complete battery prediction state.
9. **Final WB:** only now generate/reveal fresh $N=1000$ WB for eligible cells.
10. **Primary evaluation:** compute the predeclared metrics and contrasts.
11. **Secondary mechanism analyses:** only after the primary evaluation is frozen.
12. **Theory:** interpret the full empirical pattern.

## 19. Evidence separation and seeds

Exact scientific banks are frozen in `config_phase5_seed_registry_v2.json`.

I1 region, I1 sigma, Step-0 calibration, Step-0 confirmation, method-local evidence, method graph evidence, and final WB evidence are stage-disjoint. Common random numbers within a stage and across physical cells are allowed where explicitly declared. No independence claim is made across cells sharing CRN.

## 20. Failure/repair policy

A scientific outcome cannot trigger repair.

A Step-0 gate failure is a cell-level exclusion and does not stop unrelated cells.

If M1 or M2 cannot be instantiated under their frozen public-information-only local rules, record `NOT_INSTANTIABLE`; do not relax rules using graph-WB evidence.

A genuine implementation defect can be corrected only through explicit versioning, documented diagnosis, invalidation of contaminated outputs, and regeneration of all affected downstream artifacts.

## 21. Deferred axes

Deferred from this confirmatory battery are workload variation, provider count, service-family misspecification, server-count misspecification, CV variation, cost-rate variation, quality variation, provider permutations, deliberately overloaded worlds, choice/race/retry/loop operators, dynamic reconfiguration, richer disclosure levels, and all PPG mechanisms.

## 22. Authority

This V2 document and the V2 machine-readable files named at the top are the current Phase-5 source of truth.

V1 files remain immutable provenance and must not be rewritten. Historical pilot files remain provenance and must not be rewritten to make the new experiment appear cleaner or more prospective than it was.
