# B1 Phase III: pilot–battery divergence control register

**Date:** 20 October 2026. **Purpose:** Complete the least expensive reproducible checks before making any causal or publication claim. Original pilot, Phase-5 and retrospective results remain immutable.

## Controls with reported outcomes

| ID | Control | Observation | Status | Limitation |
|:--|:--|:--|:--|:--|
| D0 | Static source/contract deviation matrix | Same logical G0/G_PAR; changed provider worlds, public cards, domain mappings, local and graph seeds, lambda-selection policy, support rule, calibrated SLA queries and WB precision | Completed | Describes confounded changes rather than attributing causality |
| D1 | Old G0 versus Phase-5 G_PAR native parity with identical fixed surrogate parameters and IPT=1e6 | Two seeds, 299 requests/seed; exact match in request identity, emission, completion, L/C/Q and completion status | Completed, user terminal | Synthetic provider models and short 60 s run |
| D2 | Numerical surrogate IPT-gauge sensitivity | Matched-gauge exact parity; when changing IPT=1e6 to 1e9, maximum observed native difference was 0.102 ms in latency and about 7.1e-6 cost | Completed, user terminal | Small differences can cross thresholds in other cases |
| D3 | Actual frozen P3/G_PAR Top1 IPT gauge counterfactual on same 3 seeds | 3,597 request rows; 555/555 primary query-horizon sigma predictions exactly unchanged | Completed, user terminal | One model and three trajectories, not full Top14 |
| D4 | Frozen local public-I1 reconstruction audit | Mean across A/B/C Full48 local MAE: pilot 0.1277, P1 0.1314, P3 0.1556, P4 0.1101; local fitting quality does not monotonically predict composed graph MAE | Completed, user terminal | Provider-local public I1 is not the same observable as graph SLA |
| D5 | Internal Top14 retained-mass comparison | Pilot adaptive 99.9% rule selected K14 (mass 0.999174); fixed-K14 retrospective masses P1 0.996404, P3 0.996771, P4 0.998925; 99.9% would need K19, K22, K15 | Completed from archived weights | Mass omission bounds only the inferred finite mixture, not prediction error to WB |

## Executed D6-D9 controls, from 2026-10-20 terminal logs

| ID | Archived-input check | Observed result | Status |
|:--|:--|:--|:--|
| D6 | audit_pilot_estimator_parity_v1.py | Provider Gibbs weights reproduced within 2.78e-16; exact 14/14 joint IDs/order; joint weights within 2.78e-16; retained mass 0.999174197017 and exact B1400 integer allocations | **PASS** |
| D7 | audit_candidate_domain_transfer_v1.py | Normalized LHS coordinates exactly matched; all 9 P-world/provider cases changed KL-Top1 candidate index; physical mu and/or kappa ranges changed while CV mapping remained unchanged | **PASS** |
| D8 | audit_lambda_cv_transfer_v1.py | The original public-I1-only five-fold blocked CV selected lambda=30 (pilot), lambda=3 (P1), lambda=5 (P3) and lambda=20 (P4). Transferring fixed lambda=30 adds 25.23%, 92.06% and 8.93% respectively to the *held-out public-local Bernoulli KL score* compared with each new world's selected minimum | **PASS, specific selection-policy divergence** |
| D9 | audit_original_world_bridge_v1.py | All 14 historical pilot M3 models replayed with the new G_PAR runtime: ranks 1–9 used two archived seeds each (2398 requests per rank); ranks 10–14 have just one archived B2000 seed each (1199 requests per rank). At matched IPT=1e6, every native ledger agrees to floating-point precision (maximum absolute difference about 5.7e-14). IPT=1e9 introduces small L/C/finish-time differences but no completed/incomplete status difference. On ranks 10–14, 555/555 original query-horizon SLA predictions remain unchanged at both gauges. | **COMPLETE**, with bounded seed-subset and scored-rank caveats |

D8 full held-out scores:
- P_DEV: selected lambda 30, KL 0.126042; fixed lambda30 KL 0.126042.
- P1: selected lambda 3, KL 0.099806; fixed lambda30 KL 0.124984 (excess 0.025178, +25.23%).
- P3: selected lambda 5, KL 0.082610; fixed lambda30 KL 0.158658 (excess 0.076048, +92.06%).
- P4: selected lambda 20, KL 0.090682; fixed lambda30 KL 0.098781 (excess 0.008099, +8.93%).

**Causal restraint:** These CV findings establish that transferring the *numerical value* lambda30 is not equivalent to transferring the original pilot's *public-I1 CV selection procedure*. They do **not** establish that a lower CV-KL choice would improve graph-white-box prediction. Changing lambda would change the joint support; absent simulated alternative members, original graph accuracy under reweighting is unknown. The D7 Top1 differences are similarly multicausal.

**D9 completed:** The corrected diagnostic preflighted the true rank-specific B2000 allocations and completed ranks 10–14 without rerunning ranks 1–9. The final 555 original-query comparison covers **ranks 10–14 only**. For ranks 1–9, equal native ledgers at the matched gauge imply equal deterministic scored values, but the high-gauge 555-point readout was not produced because the first attempt stopped before aggregation. No full B1400 reconstruction/replay or independent holdout is claimed.

**Phase III status:** the planned D0–D9 forensic-equivalence controls are completed. The *cause* of the original-to-battery MAE difference is still confounded by changed physical worlds, public I1 evidence, mapped parameter domains, inherited rather than re-cross-validated Gibbs lambda, and graph-level query regions. Further prospective one-axis interventions would be a distinct research stage, not necessary to close this bounded internal audit.

## Scientific framing

**Predictive-sufficiency challenge:** Similar local I1 approximation accuracy need not lead to similar composition accuracy. This does not prove inherent insufficiency of the I1 interface because search, weighting, candidate support and query conditioning remain confounded.

**Protocol/operational-fidelity challenge:** A method's pilot and extended instantiation can have substantively different observed behavior because of different candidate domains, selected hyperparameters, graph execution rules, random seeds, query calibrations and evaluation units. Matching the high-level method label and propagation budget does not establish full equivalence.

These are candidate lessons for the later methodological note on defensible empirical evidence for hierarchical computing-continuum management, not already demonstrated general theorems.
