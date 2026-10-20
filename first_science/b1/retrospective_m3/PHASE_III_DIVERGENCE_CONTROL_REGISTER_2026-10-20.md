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

## Remaining executable controls, all separately versioned and read-only

| ID | Script | Scope | Approximate runtime on laptop | Cost |
|:--|:--|:--|:--|:--|
| D6 | audit_pilot_estimator_parity_v1.py | Recompute Phase-4 pilot's 48/provider Gibbs weights using Phase-5 helper; check all 14 pilot joint candidate IDs/ranks, alpha and B1400 allocation | About 2–30 s | No simulations |
| D7 | audit_candidate_domain_transfer_v1.py | Check identical normalized 48-point LHS positions and report changes in mapped physical candidate domains, plus Top1 candidate-index changes | About 2–15 s | No simulations |
| D8 | audit_lambda_cv_transfer_v1.py | Rerun the exact frozen pilot 5-fold *public-I1-only* lambda CV formula on archived candidate curves for original and new worlds, report whether lambda=30 transfers | About 15–90 s | No simulations |
| D9 | audit_original_world_bridge_v1.py | First K frozen original pilot M3 hypotheses, same original pilot query regions and first N historical seeds: compare archived native G0 to new Phase-5 G_PAR at both IPT gauges | Typically about 1–3 min for K=3, N=2; native runtime varies | Only 12 native graph trajectories, no new local simulations |

**Execution order:** D6 -> D7 -> D8 -> D9. D9 requires original Phase-4 M3 v4 archived ledgers under the local repository results path. None of D6–D9 reads final white-box outcomes or changes frozen predictions. Source-level validation workflows are distinct from scientific execution. Mark each as COMPLETE only after the local output has been inspected.

**Interpretation rules:**
- D6 PASS proves archived-input and numerical estimator parity in the original pilot, not external prediction performance.
- D7 quantifies candidate-domain shifts. A changed Top1 index does not isolate whether the cause is physical-domain mapping, new I1 observations or stochastic local rescoring.
- D8 can demonstrate whether transferred lambda=30 was or was not preferred under new public-I1-only cross-validation; its world-specific CV scores are retrospective diagnostics, **not permission to retune frozen methods**.
- D9 exact native and query-curve parity at IPT=1e6 would eliminate a major graph implementation concern for the checked model-seed subset. IPT=1e9 differences are evaluated on *the original pilot query thresholds*, the missing bridge from D3's new P3/G_PAR thresholds.
- If all controls pass, the remaining source of divergence is not established as a unique mechanism: **provider-generating worlds, their public disclosures, domain mapping and independently calibrated global queries co-vary**. Further causal isolation requires a separate one-axis-at-a-time design with fresh evidence and an explicitly declared cost. It is legitimate to close B1 Phase III as a bounded, reproducible forensic account without a universal cause.

## Scientific framing

**Predictive-sufficiency challenge:** Similar local I1 approximation accuracy need not lead to similar composition accuracy. This does not prove inherent insufficiency of the I1 interface because search, weighting, candidate support and query conditioning remain confounded.

**Protocol/operational-fidelity challenge:** A method's pilot and extended instantiation can have substantively different observed behavior because of different candidate domains, selected hyperparameters, graph execution rules, random seeds, query calibrations and evaluation units. Matching the high-level method label and propagation budget does not establish full equivalence.

These are candidate lessons for the later methodological note on defensible empirical evidence for hierarchical computing-continuum management, not already demonstrated general theorems.
