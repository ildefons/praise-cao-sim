# Phase-5 V3b full-support M3 graph-execution revision

**Frozen:** 2026-10-06  
**Classification:** pre-graph-WB method development, after the Top14 pre-execution mass diagnostic and before any scientific graph prediction.

The original V3b graph-execution contract retained M3 ranks 1..14. Its pre-execution freeze showed that the retained mass depends strongly on provider world:

- P1: 0.551984
- P3: 0.961909
- P4: 0.866545

No graph trajectory and no graph white-box result had been used. The diagnostic therefore exposed a numerical representation problem before scientific graph execution: Top14 is not a uniformly adequate approximation to the frozen M3 distribution, especially for P1.

The provider reconstruction is **not** reopened. Candidate identities, local rescore evidence, Gibbs energies, provider weights, and the 343-member joint ranking remain exactly frozen.

## Revised M3

The primary M3 prediction is now the complete weighted finite support,

`M3_FULL343`.

All 343 joint models are propagated. The total graph budget remains B=1400 per eligible physical cell.

For provider world P, let w_j be its frozen joint weights, j=1,...,343. Since the full support is used, the weights already sum to one. Allocate at least one trajectory to every joint model, then assign each of the remaining 1057 trajectories by the deterministic marginal rule

`j* = argmax_j w_j^2 / [N_j (N_j+1)]`.

Exact ties go to lower joint rank. This is the same frozen minimax Bernoulli variance-bound allocation principle used previously, now applied to the complete support rather than a truncated subset.

The allocation is frozen separately for P1, P3 and P4 because their weights differ, then reused across the four eligible graph structures in each provider world.

## Nested support diagnostics

Top1, Top3 and Top14 remain useful diagnostics but are no longer the primary M3 numerical approximation. They are computed from the same full-support simulation ledgers, using the trajectory counts assigned to those ranks by the full-support B=1400 allocation and renormalizing the frozen joint weights within each nested subset.

Thus no additional graph simulation is spent on Top1, Top3 or Top14.

Their omitted-mass bounds remain descriptive approximation bounds relative to the full finite M3 distribution. The full-support M3 truncation error is exactly zero.

## Seeds

M1 and M2 retain the frozen N=100 common bank 56900..56999.

M3 extends the already frozen deterministic rank-stream convention from ranks 1..14 to ranks 1..343:

`seed(r,k) = 7000000 + (r-1)*10000 + k`.

The stride is unchanged and is much larger than any possible per-rank allocation under B=1400. Corresponding rank streams are reused across eligible cells as CRN.

## Provenance

This revision was triggered only by the already-frozen retained-mass diagnostic. It is **not prospective relative to that diagnostic**, but remains blind to all end-to-end graph prediction accuracy and all final graph white-box outcomes.

The previous Top14 pre-execution artifacts remain immutable provenance under `results/04_prediction_v3b/`. Revised full-support scientific graph predictions will use a new namespace, `results/04_prediction_v3b_fullsupport/`.

The final white-box bank 54000..54999 remains unread and embargoed until the new full-support global prediction freeze is complete.
