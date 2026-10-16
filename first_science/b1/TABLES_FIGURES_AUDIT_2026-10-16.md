# PRAISE B1. Substep 2.4: Tables and Figures Audit (2026-10-16)

**Source:** praise_caise_workshop_note_v11_45(1).pdf, 26 pages, 2026-10-02.  
**Scope:** all numbered tables (1–4), figures (1–3), captions, comparisons, denominators, budgets and cross-references.  
**Status:** visual/source-level review complete. Some ancillary cells still need direct archived CSV reconciliation. No manuscript changes or new simulations.

## Evidence categories

**Verified (V):** independently recomputed earlier from frozen pointwise results and checked selected manifest hashes. **Consistent (C):** arithmetic/layout matches already reported numbers but every original source row was not independently verified. **Source-checked (S):** correct under the cited frozen contract or implementation. **Unverified (U):** needs a targeted local artifact check. **Correction (X):** misleading or wrong in its stated scope, regardless of whether numbers were correctly copied.

The historical pilot covers one provider-world/graph, 15 rho-by-regime queries and 37 horizons per query (555 correlated points); white-box reference N=200. Phase5 V3b FULL343 is a separate design with 12 eligible world×graph cells and 6660 evaluation points. Never merge method versions or denominators.

## Table and figure disposition

| Display | Verdict | Verification | B1 treatment |
|---|---|---|---|
| Table 1, p7 | Retain as pilot method taxonomy | S | Pilot M3 is 48 candidates/provider and Top14; executed Phase5 uses 7/provider and FULL343; Phase4 M2 diversity support excludes M1 anchor whereas V3b M2 includes rank-1 M1 models |
| Table 2, p10 | Retain with provenance/cost corrections | V/C/U | Split prospective main M1/M2/M3 from post-hoc support readouts; include denominators and local-versus-recurring trajectory cost limits |
| Figure 1, p12 | Historical pilot figure | S/C | 5×3 horizon plots; its Top1/Top3 are matched B1400 retrospective diagnostics, NOT Table2 operational B100/B300; M0 is applicable only on 9/15 queries |
| Table 3, p13 | Retain historical regime table | V/C | Per regime 5×37=185 correlated points; aggregate MAEs arithmetically consistent; Top3 primary per-regime cells not independently reconciled |
| Table 4, p14 | Retain retrospective hidden-truth diagnosis | S/U | Parameter triples are truth/M1/M3 Top1; KL and MSE are separate public-I1 losses for M1/Top1, not latent-parameter errors. Need source-row check |
| Figure 2, p22 | Correct partial Pareto claim | X/V/C | Dashed nondominated frontier only among selected prospective primary operating points; it omits operational Top1 (B100, MAE .0399), which dominates plotted M1 (B100, .1852) in the displayed two-coordinate cost–MAE plane |
| Figure 3, p25 | Retain as projection, not result | C/S | M1 and M2 have one precision anchor each, production M3 two; B^-1/2 extrapolations do not imply MAE reduction, decision reliability or new experimental evidence |

## Verified historical pilot quantities

The earlier independent B1 pilot audit reproduced the following frozen whole-battery MAEs: M1 .185171, M2 .068153, production M3 B1400 .030368 and B2000 .027547. A separate retrospective Stage-B audit reproduced Top1 B1400 .028784, uniform14 equal B1400 .054903, weighted14 equal B1400 .042221 and weighted14 production B1400 .030368. These verified values support, but do not exhaustively verify, every cell in Tables 2 and 3.

**The pilot improvement is real within its setting, but does not generalize automatically to Phase5** (main eligible-battery MAE M1 .157015, M2 .133951, M3 FULL343 .121890). The result populations and M3 algorithms changed.

## T2: Specific fixes, p10

1. **M0 coverage** is 9/15 queries for MAE .5720. M0 decision agreement uses 274 applicable white-box-reference-certain points. M1/M2/M3 agreement is measured on 481 of 555 reference-certain points under illustrative beta=.90. These are conditional/descriptive comparisons, not identically covered method scores, deployment certificates or independent scenario replicates.
2. **Operational support rows** Top1 B100 MAE .0399, Top3 B300 MAE .0401 and Top14 100/member B1400 MAE .0422 are retrospective readouts. Their first two numerical cells were not directly rechecked by the previous small B1 numerical audit. Do not present them as independent prospective method evaluations.
3. **Graph cost** is trajectory count, not wall time: M1 100, M2 2700, production M3 1400 (or 2000). M3 B1400 uses 48.15% fewer graph trajectories than M2 B2700 in the original pilot. This does not include local fitting or the validity/generalization of predictions.
4. **Local trajectories** 12.0k M1, 21.6k M2 and 14.4k M3 are historical one-time provider construction counts, not a complete economic or wall-clock cost. They only amortize while the fitted provider cards/models remain reusable. M0 zero consumer-side simulation does not mean cost-free information acquisition.
5. **Retrospective bank chronology:** Phase4 Stage-B code explicitly generates or reuses a separate post-pilot collection of 14-member equal-100 trajectories plus a Top1-heavy bank. “Read-only support readout requires no NEW simulation at readout time” is not evidence these data or comparisons were available before the original M3 prospective evaluation. Keep prospective production and retrospective diagnostic stages separate.
6. **Allocation versus weighting:** Stage-B equal-support weighted and uniform predictors use exactly the same ledgers, so their comparison isolates the weighting convention. Stage-B weighted14 equal allocation .0422 versus production weighted14 allocation .0304 uses different allocation/seed banks and is descriptive, not a clean isolated causal estimate of allocation improvement.

## Fig1 and T3: Consistency and limits

Figure 1 has five rho rows × three Easy/Mid/Stress regimes. Legend and caption indicate original M0/M1/M2 versus M3 matched-B=1400 Top1, Top3 and production Top14. **Table2's Top1 B100 and Top3 B300 are different operating points** from the Figure1 Top1/Top3 curves; the near-overlap shown in Figure1 must not be cited as evidence that B100 and B300 are equally accurate or precise.

Table3 supplies three equal-sized regimes. Arithmetic from its printed four-decimal MAEs:

| Method | Arithmetic mean of Easy/Mid/Stress MAE | Independently verified or reported overall |
|---|---:|---|
| M1 | .185167 | .185171 (verified) |
| M2 | .068133 | .068153 (verified) |
| M3 Top1 B1400 | .028767 | .028784 (verified StageB) |
| M3 Top3 B1400 | .030567 | approximately .0305 (reported; primary rows pending) |
| M3 Top14 production | .030333 | .030368 (verified) |

All differences for the verified rows are consistent with rounding. Signed-bias convention is predicted minus white-box; positive is optimistic. A comparison of 185 or 555 horizon-query points must not treat them as independent draws of the underlying scenario configuration.

## Table4: Truth-only retrospective diagnostics

Table4 lists three provider truth/M1/Top1 parameter triplets for mu (seconds), kappa and CV, plus public-I1 KL and MSE losses for M1 and Top1. The relevant source code is phase4/m3_posthoc_mechanism_audit.py, and its retrospective output includes truth_candidate_audit.csv. The entire printed Table4 has not been independently matched to local provider M1/Top1 archives; **mark rowwise numeric evidence unverified until checked**. Physical truth was used only after method freeze for scientific audit. No theorem about structural non-identifiability or graph prediction follows from one parameter-distance example.

## Figure 2: A definite internal comparison error

As drawn, Figure2 plots primary M1 (B100, .1852), M2 (B2700, .0682), M3 production B1400 (.0304) and B2000 (.0275). Its dashed curve and caption call M1, M3 B1400 and M3 B2000 the nondominated set.

But Table2 also reports operational **M3 Top1 B100, MAE .0399**, which strictly dominates M1 at equal recurring B100 in Figure2's graph-cost-versus-MAE plane. Figure2's statement is therefore only valid if its choice set is explicitly restricted to the *original prospectively frozen primary implementations*. This restriction must be in the figure title/caption and adjacent claim. A full operating-point plot could include retrospective Top1/Top3 but must label their status and account for higher upstream local reconstruction cost (M3 local 14.4k versus M1 12.0k).

Within that restricted 2D plane M3 B1400 dominates M2. It is **not** a global model-family superiority or total-cost conclusion. The vertical error bars are 2.5–97.5% intervals of resampling the N200 **white-box reference** across shared horizon/query rows, **not** graph-method MC errors or uncertainty across new provider worlds.

## Figure 3: Arithmetic okay, interpretation narrow

The width/budget anchors and reported coefficients are consistent:

- M1: B100, mean pointwise numerical width .0375, coefficient c1=.375.
- M2: B2700, width .0563, coefficient c2≈2.925.
- M3 Top14: B1400/.0493 and B2000/.0425; weighted least-squares-through-origin coefficient c3≈1.868 for width≈c3/sqrt(B).

The projected B for desired width .03 is approximately 156, 9.5k and 3.9k, and for width .02 approximately 352, 21.4k and 8.7k, respectively. Those are arithmetic consequences of a **fixed-support/fixed-allocation asymptotic planning rule**, not observed accuracy results. For M2, increasing budget must preserve 27-member shared-seed batching, not treat 2700 individual trajectories as independent. M3 is still conditional on model choice and cannot reach truth by reducing MC error alone.

The raw source measurements and plotting table were not independently reconstructed from the archived per-trajectory data in this audit.

## Definite cross-reference error

Appendix A on p19 cites “the MC-width column of Table 2”, **but Table 2 has no MC-width column**. Redirect the reference to Appendix B's numerical width paragraphs or add a separate B1 precision table. This is an actual editorial defect.

## Remaining artifact-level verification gates

The PDF is completely reviewed as a display document. However, the prior B1 audit ZIPs contain only primary-result reconciliation summaries, not all ancillary raw display source tables. Before claiming every printed numerical cell has been independently verified, check locally:

- Pilot M0 error/decision denominator; operational Top1 B100 and Top3 B300 errors and their decision results;
- all Table3 per-regime row metrics including matched-B Top3;
- Table4 provider truth/M1/Top1 parameters and public-I1 loss values;
- Figure2 WB-bootstrap bar endpoints and Figure3 precision-width source values;
- exact Figure1 pointwise source series/legends versus frozen graph prediction tables.

These are *existing-data* integrity checks, not new experiments. If a source is missing or an expected column differs, record as unresolved rather than silently replacing with a plausible number.

## B1 design changes

Preserve all four original tables and all three figures as **historical pilot** assets, with corrections. The primary B1 results need separate Phase5, Phase6 and P2 displays, each explicitly tagged with its population, method version, horizon/reference bank, evidence role and simulation cost.

**2.4 verdict:** closed at visual, mathematical and source-provenance audit level. Do not sign off full row-by-row numerical accuracy of ancillary displays until the targeted archived-data check. No manuscript changes were made.
