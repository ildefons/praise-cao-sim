# A1 implementation verification — evidence-backed I/M inventory (first pass)

**Date:** 6 November 2026  
**Status:** SOURCE-VERIFIED FOR THE B1 SEVEN-PREDICTOR EVALUATION; UPSTREAM I×M combinations outside B1 still require source-by-source mapping. No new scientific run.

## What has been checked directly in executable source

The checked [B1 baseline program](b1_budget_comparison_v1.py) fixes the worlds `P1, P3, P4`, graphs `G_PAR, G_PARSEQ, G_SEQ, G_SEQPAR`, and **exactly seven** named predictors. The [matrix verifier](verify_seven_method_matrix_v1.py) reconstructs 84 method×condition MAEs and fails if any required provenance or hash is invalid. The B1 builder reads three independently archived evaluation groups, using source manifests and SHA-256 checks rather than manual text summaries:

| Provenance group | Executed B1 predictor IDs | Archived evaluation source |
|---|---|---|
| Phase II / Phase 5 | `M1`, `M2`, `M3_FULL343` | `first_science/phase5/results/06_evaluation_v3b_fullsupport/primary_metrics.csv` and deterministic evaluation manifest |
| Original-style retrospective | `ORIGINAL_TOP14_B1400`, `ORIGINAL_TOP1_B1400` | `first_science/phase5/results/b1_pilot_m3_retrospective_v1/evaluation/metrics_retrospective.csv` and evaluation manifest |
| Fixed-CV retrospective | `FIXED_CV_TOP14`, `FIXED_CV_TOP1` | `first_science/phase5/results/b1_fixed_cv_top1_top14_b1400_v1/evaluation/metrics.csv` and evaluation manifest |

The evaluator checks **12 cells for each predictor** and exactly **555 query–horizon measurements per cell**, plus MAE range, numerical consistency with published 12-cell method means, and provenance hashes. This establishes **seven implemented, source-backed predictor variants on the same comparison domain**, not seven independent provider disclosure interfaces.

## Why this is not yet an exhaustive I×M compatibility audit

The seven frozen predictor IDs are a **method/variant portfolio**, not a fully crossed factorial experiment over interfaces `I1, I2a, I2b, I5` and integration methods `M0, M1, M2, M3`. The B1 source-aggregation code does not encode a per-method `I` field and therefore cannot prove the information contract used by each upstream computation. Calling all seven `I1+M*` without inspecting their generation scripts would be an unjustified inference.

**Current source audit verdict:**

| Question | Verified? | Implication |
|---|---|---|
| Are all seven B1 predictors actually backed by frozen evaluation evidence? | **Yes, via source file and manifest verification contract**, and the validated replay | Eligible to show in B1 method-selection architecture |
| Does B1 compare 3 provider worlds × 4 graphs for each method? | **Yes** | Exactly 84 actions / 12 domain conditions |
| Is the M3 family split into full, Top14, Top1, original-style and fixed-CV variants? | **Yes** | Represent as method variants rather than distinct I sources |
| Was M0 included in seven-predictor selector? | **No** | M0 belongs only in upstream I×M discussion, not current B1 candidate menu |
| Does the B1 matrix itself establish I1/I2a/I2b/I5 support for each method? | **No** | Full I×M table remains an open upstream implementation check |
| Does the selector execute predictor simulations on demand? | **No** | It reveals previously frozen aggregated MAE from 7×12 matrix |
| Does it recommend a method per graph or SLA query? | **No** | One final *domain-level* predictor recommendation per episode |
| Can the selector observe all 84 losses before selecting? | **No** | Hidden entries are accessed by replay/reference evaluator, not acquisition |

## Correct architecture depiction until upstream scripts are traced

The architecture should show **(A) provider information and composition-level prediction**, with its several disclosed interfaces and M0/M1/M2/M3 families, adjacent to **(B) an implemented offline seven-variant validation and selection layer**, not falsely imply a live all-interface-by-all-method runtime. Any diagram arrow from provider telemetry, WB reference, or selector to an online orchestrator should be marked **proposed / external**, unless a repository implementation can be cited.

## Remaining upstream questions

1. Which exact evidence/disclosure contract is consumed by each of the three Phase-5 base predictors M1/M2/M3_FULL343? Record their source functions and their provider-world conditions.
2. Which original-style Top14/Top1 and fixed-CV Top14/Top1 scripts construct their provider-model posterior/weights, and which I-level inputs do they access?
3. Which I2a/I2b evaluation(s) are comparable on the same graphs, same loss target and WB reference, and why are they not in the frozen seven-method portfolio?
4. Which upstream methods depend on privileged information? Distinguish WB-only evaluation from operational disclosure.

**Gate before final manuscript Figure 1:** close at least the I-contract trace for the seven B1 variants. The full cross-product is unnecessary if not part of the paper's demonstrated system.

## Real worked-example extraction

The original B1 code writes `episode_action_history.csv` and `terminal_episodes.csv`, which **are not currently committed** to Git, but have been produced locally in the original reproducible B1 run. A read-only and source-checking extractor is provided by [b1_extract_worked_episode_v1.py](b1_extract_worked_episode_v1.py). It checks the 84-entry matrix, seven common initial actions, no repeats, exact trace values, recomputes the posterior recommendation and verifies retrospective regret. **Until its actual output is brought into GitHub, no episode-specific MAE trace or recommendation should be claimed.**

Recommended illustrative episode: original budget-aware Top2 at B=15, start index 1 = P1 / G_PARSEQ, replicate 0. This is a deterministic indexing choice, **not selected for a favorable outcome**. It shows one condition only as the initial observation; the 15 actions sample additional worlds/graphs and the terminal selection targets the full 12-cell domain.
