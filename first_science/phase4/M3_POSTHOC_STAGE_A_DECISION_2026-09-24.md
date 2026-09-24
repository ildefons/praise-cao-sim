# Stage-A decision: proceed to a cost-matched mechanism ablation

**Date:** 24 September 2026  
**Stage-A result commit:** `9369030`  
**Decision:** PROCEED_TO_STAGE_B_COST_MATCHED_ABLATION

## Why Stage B is warranted

Stage A was frozen and executed as a zero-simulation post-hoc audit. It exposed two facts that make a direct ablation scientifically necessary.

1. **The hidden D300 process is not present in the 48-candidate bank.** No provider has an exact hidden tuple in the M3 support. The nearest hidden-parameter candidates are not the public-I1-preferred candidates and carry negligible Gibbs mass. This argues against a trivial hidden-truth leakage explanation.

2. **Composition-induced spread tracks difficulty.** Across the 15 frozen query cells, the plug-in MC-adjusted retained-model ambiguity variance has post-hoc Spearman correlation 0.754 with M1 MAE, 0.725 with the M1-to-M3(B=2000) MAE gain, and 0.654 with the M2-to-M3(B=2000) gain. This is descriptive evidence that latent-model spread is largest where point collapse is least reliable.

3. **However, the existing top-1 retained hypothesis is unexpectedly strong.** Using only its already available 900 graph trajectories, the top-1 diagnostic obtains whole-window MAE 0.02537, compared with 0.02755 for the frozen weighted M3(B=2000). Because that top-1 estimate is not cost matched and was not designed as an ablation, it cannot establish that ambiguity preservation is unnecessary. But it creates a concrete alternative explanation: M3 may work mainly because public-I1 weighting identifies a strong single reconstruction.

The Stage-A stop rule therefore does not justify stopping. The mechanism is unresolved in exactly the way Stage B was designed to test.

## Stage-B question

At the same total graph-simulation budget, does retaining multiple frozen compatible hypotheses improve prediction relative to using only the single highest-weight hypothesis, and does public-I1 weighting improve over an unweighted average of the same hypotheses?

## Frozen Stage-B comparison

Use the already frozen top-14 support and lambda=30 weights. No candidate, query, interface, or white-box result changes.

At total graph budget **B=1400** compare:

- **Top1-1400:** rank-1 hypothesis only, 1400 trajectories.
- **Uniform14-1400:** 14 retained hypotheses, exactly 100 trajectories each, equal weight 1/14.
- **Weighted14-EQ-1400:** the exact same 14×100 ledgers, frozen M3 renormalized weights.
- **Weighted14-MINIMAX-1400:** the already frozen production M3(B=1400) result, used as a reference for the effect of allocation.

The first 100 seeds are common across all 14 Stage-B hypotheses. Top1 uses those same 100 seeds plus 1300 additional seeds. Thus Uniform14 and Weighted14-EQ differ only in aggregation weights, not graph evidence.

## Interpretation rule

- Weighted14-EQ vs Uniform14 isolates **public-I1 weighting**.
- Weighted14-EQ vs Top1 tests **multi-hypothesis retention** under the same total graph budget.
- Frozen Weighted14-MINIMAX vs Weighted14-EQ is a secondary allocation-efficiency comparison and uses different frozen seed banks, so it is not treated as a paired causal ablation.

Stage B is post-hoc mechanism analysis. It does not convert the pilot into an untouched prospective validation.

## No further method development

Whatever Stage B shows, M3 remains closed. If Top1 matches or outperforms the weighted mixture within Monte Carlo resolution, the manuscript must narrow the ambiguity-preservation mechanism claim. If the weighted mixture improves robustly, the paper may report this as post-hoc mechanism evidence, clearly separated from the prospective frozen final evaluation.
