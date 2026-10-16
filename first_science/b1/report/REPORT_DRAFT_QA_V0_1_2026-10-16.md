# PRAISE B1: Report draft v0.1 editorial QA and provenance status

**Date:** 2026-10-16  
**Object:** [B1_TECHNICAL_REPORT_DRAFT_V0_1.md](B1_TECHNICAL_REPORT_DRAFT_V0_1.md)  
**Git source blob SHA:** \`686b3e70b55a2dd9d4e0e413e0e0fbbcf68596a9\` as checked at this QA.  
**Status:** substantive first draft prepared; automated source-structure QA passed; no final publication clearance.

## Contents and source coverage

The report source is approximately **9,001 words** and 67,942 characters (measured after source-backed figure insertion). It includes:

- Executive synthesis;
- 12 numbered scientific chapters from objectives, SLA semantics, interfaces and versions to simulator, pilot, Phase5, Phase6/P2, uncertainty, threats and falsifiable questions;
- 3 appendices covering uncertainty mathematics, frozen provenance and the inherited *provisional* bibliography;
- 26 displayed mathematical formulas, including canonical finite-H estimand, methods, truncated-support bound, model/WB noise identities;
- 2 **source-backed vector figures**, [Phase5](figures/phase5_aggregate_mae_v0_1.svg) and [Phase6](figures/phase6_matched_mae_v0_1.svg), generated from previously verified primary MAE values, plus multiple numerical source tables.

The text does **not** silently carry over the old manuscript's 26-page pilot-centered abstract or claim to solve structural non-identifiability. It does not claim a certified SLA admission procedure.

## Automated checks

**15/15 PASS**, no failure:

1. All 12 new report chapter headings present.
2. Appendices A, B and C present.
3. Both Phase5 and Phase6 SVGs referenced in Markdown.
4. Canonical \(\sigma_G(A,H;\rho)\) probability estimand explicitly present.
5. \(\rho_r\) region content separated from \(\rho_q\) compliance fraction.
6. Unequal Phase5 M0 applicability (**1776** vs **6660** points) visible.
7. Pilot Top14 and executed FULL343 both labeled.
8. P2 gate exclusion explicitly stated.
9. Archived prediction freeze and WB timestamps retained.
10. Explicit no-public-release status.
11. Provisional bibliography and release caveat included.
12. Avoids Pandoc double section-numbering: manual numbered headings, \`numbersections: false\`.
13. Phase5 figure contains the verified M1/M2/M3 aggregate error values.
14. Phase6 figure contains all six compared error values.
15. 68-row [claim-to-draft traceability](CLAIM_TO_DRAFT_TRACEABILITY_V0_1.csv) included.

## Claim-disposition accountability

From [original 68-claim audit](../MANUSCRIPT_CLAIM_AUDIT_V0_1.csv), the new rowwise traceability table classifies:

| Draft state | Count | Meaning |
|---|---:|---|
| \`DRAFT_ADDRESSED\` | **58** | A concrete chapter/appendix location addresses the historical wording/claim issue; still subject to author check |
| \`BOUNDED\` | **2** | Avoided an overstrong detailed claim or carried correct caveat |
| \`EDIT_COMPLETED\` | **1** | The old nonexistent MC-width cross-reference is absent in new source |
| \`SOURCE_QA_PENDING\` | **1** | Exact full I1 region generation/coverage claim still needs a deeper raw-source check if expanded |
| \`NUMERIC_QA_PENDING\` | **2** | Ancillary original Top1/Top3 operational curves and M2 bootstrap width not independently recalculated |
| \`DISPLAY_ASSET_PENDING\` | **3** | Full original Figure1, provider-parameter Table4 and detailed pilot regime Table3 have not yet been visually rebuilt in B1 |
| \`HISTORICAL_ENV_PENDING\` | **1** | Exact clean-tree Oct7 AICon/YAFS imported package not attested |
| **Total** | **68** | All have target report locators |

**Interpretation:** these are **draft-level dispositions**. “DRAFT_ADDRESSED” is not equivalent to peer-review verification or certification of the original paper. Source-based quantitative conclusions remain as described in the sign-off and the report appendices.

## Publication-quality gaps

Before considering arXiv or using the report as a citable public technical reference:

1. Confirm author order, affiliations, title and explicit coauthor consent.
2. Verify the 20 inherited bibliography entries against published sources, add recent relevant work, and confirm any preprint/venue overlap policy.
3. Add the intended complete historical pilot figure/table assets or decide explicitly to archive them as linked supplementary provenance rather than main paper figures.
4. Obtain full row-level evidence, or keep clearly marked as reported-only, for operational Top1 B100/Top3 B300 and M2 paired-bootstrap numerical width.
5. Decide whether to conduct a focused original-I1 acquisition/nestedness recheck. Do not infer unproven formal coverage.
6. If exact bitwise reproducibility is claimed, reconstruct historical YAFS/AICon working tree/build; otherwise the current explicit limitation suffices for a candid technical report.
7. Do a final typeset/PDF page-and-equation/figure placement review. The [PDF build script](build_pdf.sh) is committed, but this GitHub-connector editing turn **has not executed the build against the full repository source on a local checkout**.
8. Conduct substantive author proofread of all 68 item locations, consistency of cost denominators, numeric precision and source citations.

No new YAFS simulations are required for **this drafting-stage sign-off**. A later focused methodological paper will need independently justified claims and possibly new confirmatory experiments depending on its eventual thesis.

**Result:** conditional 2.7 drafting authorization has been exercised: a substantial, academically structured, editable manuscript now exists separately from the frozen original CAiSE PDF and experiment artifacts.
