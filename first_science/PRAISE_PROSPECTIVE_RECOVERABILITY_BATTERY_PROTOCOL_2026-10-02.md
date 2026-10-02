# PRAISE/CAO: Prospective Recoverability Battery Protocol

**Status:** FROZEN BEFORE SCIENTIFIC EXECUTION  
**Date:** 2 October 2026  
**Machine-readable source:** `phase5/config_phase5_recoverability_battery_v1.json`  
**Seed registry:** `phase5/config_phase5_seed_registry_v1.json`  
**Method-instantiation rules:** `phase5/config_phase5_method_instantiation_v1.json`

This document governs the new confirmatory battery. Historical pilot files remain immutable provenance.

## 1. Scientific purpose

The battery asks when graph-level SLA-survival prediction is recoverable from limited provider disclosure and how recoverability changes with hidden provider operating condition, composition structure, SLA query regime, and integration method.

The authoritative target remains

$$
Σ_G(A,H;ρ)=P(c_G(A,H)≥ρ).
$$

The experiment has no numerical performance pass/fail threshold. Its purpose is to produce an interpretable empirical map:

$$
\text{controlled battery}
\rightarrow
\text{empirical regularities}
\rightarrow
\text{mechanistic interpretation}
\rightarrow
\text{candidate theory}.
$$

Poor prediction in a valid frozen condition is a scientific result, not an experimental failure.

## 2. Development/confirmatory separation

The completed pilot world

$$
P_{dev}=(D=300\text{ M},δ=0.20)
$$

is development evidence only and is excluded from the confirmatory battery. The new battery contains four new provider worlds and four graph structures, giving 16 new physical conditions.

No pilot graph-WB result may be used to repair a method after this protocol freeze.

## 3. Frozen workload and provider family

Workload is invariant:

$$
W=W_0,\qquad T_{arrival}=0.2\text{ s}.
$$

Workload is not an experimental axis. Graph-induced downstream timing differences are graph consequences, not workload changes.

All provider worlds retain the pilot physical family:

- three providers A/B/C;
- one-server FCFS native provider modules;
- Gamma service/instruction variability;
- $CV=0.3$;
- effective $IPT=10^9$;
- cost rate $κ=3$;
- execution fraction $x=0.5$;
- current degenerate quality $Q=0.5$.

The hidden world family is

$$
μ_A=D(1-δ),\qquad μ_B=D,\qquad μ_C=D(1+δ).
$$

## 4. Frozen provider worlds

| ID | $D$ | $δ$ | hidden means A/B/C (M instr.) | approx. utilization A/B/C |
|---|---:|---:|---:|---:|
| P1 | 330 M | 0.00 | 330 / 330 / 330 | 0.825 / 0.825 / 0.825 |
| P2 | 330 M | 0.15 | 280.5 / 330 / 379.5 | 0.701 / 0.825 / 0.949 |
| P3 | 360 M | 0.00 | 360 / 360 / 360 | 0.900 / 0.900 / 0.900 |
| P4 | 360 M | 0.10 | 324 / 360 / 396 | 0.810 / 0.900 / 0.990 |

Utilization is interpretive only and is not exposed to reconstruction methods.

## 5. Frozen graph structures

Provider placement is fixed exactly as written:

- **G_PAR:** `ParAll(A,B,C)`
- **G_SEQ:** `Seq(A,B,C)`
- **G_SEQPAR:** `Seq(A,ParAll(B,C))`
- **G_PARSEQ:** `ParAll(A,Seq(B,C))`

The full graph remains `Source -> Fpre -> <provider composition> -> Fpost`.

Deterministic stages, network semantics, bandwidth, propagation delay, message-size conventions, and native composition-control semantics are inherited from the frozen pilot benchmark. Only the composition motif changes.

The primary battery uses only `sequence` and `parallel_all`. Choice, retries, loops, dynamic reconfiguration, provider permutations, and provider-count changes are deferred.

## 6. Public I1

Each provider world gets newly generated rho-conditioned public I1 cards using the same frozen I1 interface/acquisition semantics as the pilot.

The public rho support remains

$$
ρ\in\{0.95,0.975,0.9833333333333333,0.99,0.995\}.
$$

The same I1 cards for a provider world are reused across all four graphs.

I1 region construction and public-sigma estimation use disjoint $N=100$ provider-local evidence banks. They are also disjoint from Step-0, method-simulation, and final-WB evidence.

The strict PPG firewall remains in force.

## 7. Easy/Mid/Stress query construction

For every $(P,G,ρ)$, Step 0 constructs three nondegenerate query regimes using

$$
\bar{σ}_{60:240}
=
\operatorname{mean}_{H\in\{60,65,\ldots,240\}}
Σ_G(A,H;ρ).
$$

| Regime | target mean-$σ$ interval | target center |
|---|---:|---:|
| Easy | [0.95,1.00] | 0.975 |
| Mid | [0.75,0.90] | 0.825 |
| Stress | [0.40,0.75] | 0.575 |

Minimum adjacent mean-$σ$ separation is 0.10.

For each $(P,G,ρ)$, forward-compose the public I1 provider boundaries to obtain $A_G^{base}$, then search

$$
A_G(s,ρ)=(s l_{base},s c_{base},q_{base})
$$

over $s\in[0.5,2.0]$ with step 0.01. The inherited V2 selection/tie-breaking rule applies and

$$
s_{Stress}<s_{Mid}<s_{Easy}.
$$

Step-0 calibration uses $N=200$ WB trajectories per physical cell. After regions are selected and frozen, fresh disjoint $N=200$ WB trajectories confirm only those selected regions. No reselection after confirmation is allowed.

If the frozen confirmation gate fails, that protocol version stops for the affected design. Any redesign must receive a new explicit version.

## 8. Battery size

There are

$$
4P\times4G=16
$$

new physical conditions and

$$
5ρ\times3Q=15
$$

queries per physical condition, for

$$
240
$$

$(P,G,ρ,Q)$ query cells.

## 9. Frozen method set

The confirmatory readouts are

$$
M0,\ M1,\ M2,\ M3\text{-Top1},\ M3\text{-Top3},\ M3\text{-Top14}.
$$

### M0

Frozen topology-aware analytic baseline. Sequence uses latency sum/cost sum/quality min; parallel-all uses latency max/cost sum/quality min. Operational M0 is scored only when its frozen boundary-containment precondition holds; otherwise it reports `NOT_APPLICABLE`.

### M1

One public-I1-only simulator-compatible latent reconstruction per provider, using the frozen M1 inverse-simulation algorithm. The graph is consulted only after provider reconstruction is frozen.

A generic one-round public-I1-only boundary-expansion rule is defined in the Phase-5 method-instantiation contract. Graph-WB can never trigger expansion.

### M2

Three independently confirmed, deliberately diverse public-I1-compatible surrogates per provider, propagated as the $3^3=27$ equal-weight Cartesian portfolio. The finite member range remains a model-ambiguity diagnostic, not a confidence interval.

### M3

M3 uses the 48/provider nonadaptive LHS proposal, fresh public-I1-only KL rescoring, factorized Gibbs weights with frozen $λ=30$, ranked joint support, and weighted graph composition.

The production run simulates the **fixed first 14 ranked joint reconstructions** with total graph budget

$$
B=1400.
$$

Top1, Top3, and Top14 are nested readouts from those same production member ledgers. No extra graph simulation is required for Top1 or Top3.

This is not an equal-total-budget support ablation. Retained and omitted Gibbs mass are reported for each support size. A truncation bound concerns only finite-support M3 approximation, never error to WB truth.

## 10. White-box reference

Final graph-WB precision is frozen to

$$
N_{WB}=200
$$

per physical $(P,G)$ condition. One physical WB ledger is reused across its 15 queries.

Final WB evidence is generated/revealed only after all method predictions are materialized and hash-frozen.

Finite-$N$ WB uncertainty is reported explicitly. Differences smaller than WB resolution are not over-interpreted. Any later higher-precision experiment is a separately declared follow-up.

## 11. Evaluation

Primary horizon window: $H=60..240$ s on the frozen 5 s grid.

Primary prediction metrics:

- MAE;
- RMSE;
- signed bias;
- maximum absolute error.

Required summaries include whole battery, provider world, graph, Easy/Mid/Stress, rho, provider-world x graph, graph x regime, provider-world x regime, and rho x regime.

M0 applicability is reported separately. M2 ambiguity spread remains separate from statistical uncertainty. M3 additionally reports Top1/Top3/Top14 retained mass, omitted mass, applicable truncation bound, Monte Carlo precision diagnostics, and graph trajectory counts.

Computational cost remains a first-class method property.

## 12. Decision interpretation

Main SLA decision threshold:

$$
β=0.90.
$$

Accept when $\hat{σ}_G≥β$. Decision agreement is evaluated only where the WB uncertainty interval does not cross $β$.

$β=0.80$ and $0.95$ may be retained as secondary sensitivity analyses. None is a battery pass/fail threshold.

## 13. Prospective execution gates

1. **Provenance:** verify provider world, workload, graph, network, horizon/rho support, no stale selector, and PPG firewall.
2. **I1:** generate and freeze new public I1 cards from disjoint evidence.
3. **Step-0 calibration:** choose Easy/Mid/Stress queries without method results.
4. **Step-0 confirmation:** confirm frozen queries on fresh evidence; no reselection.
5. **Provider reconstruction:** instantiate/freeze M1, M2, M3 from public I1 only.
6. **Blind graph prediction:** run frozen methods, preserve M3 member ledgers, materialize/hashes.
7. **Final WB:** only now generate/reveal fresh $N=200$ WB.
8. **Analysis:** compute predeclared metrics; do not repair, reweight, replace, retune, or omit because of outcome.
9. **Mechanism/theory:** interpret the full empirical pattern and derive candidate theory after results are open.

## 14. Evidence separation

Exact banks are frozen in `config_phase5_seed_registry_v1.json`.

The scientific requirement is that I1 region, I1 sigma, Step-0 calibration, Step-0 confirmation, method-local evidence, method graph evidence, and final WB evidence are stage-disjoint.

Common random numbers inside a stage or across physical cells are allowed and deliberately used where helpful. They do not relax cross-stage separation.

## 15. Failure/repair policy

A scientific outcome cannot trigger method repair.

A genuine implementation defect can be corrected only by explicit versioning, a stated semantic/implementation diagnosis, invalidation rather than silent overwrite of contaminated outputs, and regeneration of downstream evidence when required.

If a frozen method cannot be instantiated under its public-information-only local rules, record that status rather than relaxing the rule using graph-WB evidence.

## 16. Deferred axes

Deferred from the primary battery: workload variation, provider count, service-family misspecification, CV variation, cost-rate variation, quality variation, provider permutations, overloaded worlds, choice/race/retry/loop operators, dynamic reconfiguration, richer disclosure levels, and all PPG mechanisms.

## 17. Authority

This document is the human-readable scientific contract. Exact executable constants live in the Phase-5 JSON files named at the top.

The new battery inherits the authoritative pilot semantics only where explicitly referenced. Historical pilot files are provenance and must not be rewritten to make the new experiment appear cleaner or more prospective than it is.
