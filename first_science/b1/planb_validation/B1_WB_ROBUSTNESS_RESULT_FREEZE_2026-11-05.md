# PRAISE B1 — Frozen WB-reference robustness outcome (2026-11-05)

**Status:** positive retrospective robustness milestone; **independent-world validation not performed**.  
**Source:** user-executed local terminal log of `b1_wb_reference_robustness_v1.py` on branch `praise-identifiability-feasibility` at commit `ea89ea1514895e6f7c46d053b43becd79f482491`.  
**Interpretation protocol:** [B1_WB_REFERENCE_ROBUSTNESS_PROTOCOL_V1.md](B1_WB_REFERENCE_ROBUSTNESS_PROTOCOL_V1.md).  
**Original development freeze:** [B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md](B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md).

## Completion and provenance

- `git pull --ff-only` updated the local checkout to commit `ea89ea1`.
- **7 synthetic tests passed**. The numerical-boundary logs show only machine-roundoff on M3_FULL343; exactly 147 tiny overshoots (45 P1/G_PARSEQ, 98 P1/G_SEQ, 4 P1/G_SEQPAR), with maxima `1.0000000000000002`. The auditor clipped these within its fixed `1e-12` tolerance after checking frozen hashes.
- **300/300 WB trajectory bootstrap draws** completed.
- **Four disjoint 500/500 WB partitions**, both directions, completed.
- The runner printed `WB_REFERENCE_INPUT_PASS 7 methods x 12 cells; 1,000 trajectories x 6,660 query columns`.
- The runner printed `AUDIT_OUTPUT /home/ildefons/praise/planb_b1_wb_robustness_v1` **after writing the final `audit_manifest.json`**. The previous NumPy boolean serialization failure is resolved.
- **Evidence handling:** numerical findings below are transcribed from the successful local terminal output, **not separately audited from an uploaded `audit_manifest.json` or raw bootstrap CSVs**. The generated files remain in the user's local output directory. Their archived hashes should be recorded if/when copied to the project evidence registry.

## Numerical results

| Pre-frozen gate | Observed result | Gate |
|---|---:|---|
| Reproduce seven-method reference domain and 84 cell MAEs | `WB_REFERENCE_INPUT_PASS` | **PASS** |
| M3_FULL343 is bootstrap reference-best in at least 90% of draws | **300/300 = 100%** | **PASS** |
| 95% WB-reference percentile interval for the original frozen Top2-minus-balanced contrast lies below zero | mean **−0.002756**; interval **[−0.002853, −0.002647]** | **PASS** |
| Disjoint-half rerun's aggregate mean Top2-minus-balanced regret is negative | **−0.003976** | **PASS** |

The runner's explicit result was **`INDEPENDENT_WORLD_STUDY_SCREEN PLAN_ELIGIBLE`**.

## Scientific interpretation

1. The reference-best algorithm **M3_FULL343** is stable to the tested finite-WB-trajectory resampling; the originally reported Top2 advantage is also insensitive to this source of reference uncertainty in the frozen-decision re-scoring.
2. The **unchanged** B1 decision policies retained a negative aggregate Top2-minus-balanced regret contrast when selection used one 500-trajectory WB half and scoring used the disjoint half.
3. The narrow WB reference interval **must not** be presented as the complete uncertainty interval for the acquisition-policy advantage. It holds the original terminal recommendations fixed and conditions on the same 12 cells and three provider worlds. It does not incorporate new-world variability, all algorithm-side MC uncertainty, or a joint confidence interval with replay-sequence variability.
4. The disjoint-half experiment's four overlapping partitions and repeated random action sequences are **not independent worlds or independent validation populations**.
5. The local output and success message justify **planning**, not claiming completion of, an independent-world confirmation study.

## Decision / freeze

**Freeze the positive B1 reference-uncertainty outcome. Do not modify the seven algorithm variants, B1 policy, 50% balanced / 50% Top2 schedule, five budget values, Gaussian priors, terminal estimator, or selection controls to optimize these results.**

The next stage is **independent-world validation feasibility and experimental design**. It needs an explicit definition of new-world independent sampling units, a validated provenance firewall, and a real cost audit before approving new simulations. The continuation-with-extra-budget question remains deferred until after that stage.

**Not a preregistered independent-world study. No claim of method novelty or compute-hour savings.**
