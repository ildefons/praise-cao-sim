# PRAISE B1: Substep 2.6, Manuscript Preservation and Rewrite Blueprint

**Status:** EDITORIAL BLUEPRINT PROPOSED AND SOURCE-GROUNDED, NOT MANUSCRIPT REWRITTEN  
**Prepared:** 2026-10-16  
**Frozen source:** \`praise_caise_workshop_note_v11_45(1).pdf\` (26 pages, pdfTeX, 2026-10-02; SHA-256 \`e2734dc446fe9cc4991dc04800cd5e828af8784269a1dbc274036be3b7f46ada\`).  
**Controlled evidence:** \`b1/evidence_registry_v1_0.json\`, \`b1/METHOD_VERSION_CHRONOLOGY_2026-10-16.md\`; all Step2.1–2.5 audit reports, 68-entry claim ledger and the 94-pass runtime provenance review.

## Executive editorial decision

**B1 is the internal *scientific record* of PRAISE/CAO service-composition prediction, not a CAiSE-length advocacy paper or a claim of solved inverse recovery.** Preserve the strong existing definitions, formulas, actual historical pilot and uncertainty derivations. Rebuild the main narrative around the later multi-world/graph evaluation, its **negative/conditional** outcomes, and the subsequent interface and search diagnostics. Preserve the chronology of methodological revisions. A reviewer should be able to tell which statements were registered before a test, chosen after inspecting local/public calibration, or developed after seeing a graph result.

Working B1 title:

> **End-to-End SLA Estimation from Limited Provider Disclosures: Methods, Experimental Record, and Limits of Reconstruction**

This intentionally avoids the original title's unqualified “dependable”/“non-identifiability” promise. It does not preclude using those terms *when rigorously defined* in the body.

### Publication-quality drafting standard

**Keep the existing B1 scope, chapter architecture, and evidence classifications unchanged.** Although developed first as an internal technical report, draft B1 to **academic publication standards from the outset**, so it can later be considered as a standalone arXiv technical reference for a more focused methodological paper.

- **Mathematical definitions:** fully specified estimands, assumptions, method versions, derivations and decision/uncertainty limitations; consistent symbols and equation references.
- **Reproducibility:** exact experimental populations, contracts, versioned code and artifact paths, seed banks, validation gates, method changes and known provenance limitations.
- **Figures and tables:** based only on archived verified data, with clear methods, denominators, budgets, reference uncertainty, experimental role, reproducible sources and accurate captions.
- **Limitations and negative evidence:** preserve the incomplete/failed results, exploratory status and confounds prominently rather than selecting only favorable outcomes.
- **References:** complete and properly checked bibliography, plus a traceable distinction between prior work, implemented methods and observed findings.

**Public release is a later decision**, subject to scientific completeness, coauthor agreement and any relevant venue/preprint policies. An eventual methodological paper should present a distinct focused contribution and may cite B1 for expanded methods, experiments and reproducibility, without assuming such a citation or public release is already approved.

### Immutable scientific guardrails

1. Canonical estimand:
   \(\sigma_G(A,H;\rho)=P(c_G(A,H)\ge\rho)\);
   \(c_G\) is the cumulative compliance fraction among **decided** requests by H, deadlines are decided failures, unresolved requests excluded, zero decided means compliant. This is **not** absorbing first-violation survival and need not be monotonic in H.
2. Maintain \(\tau=(I,M)\), distinguishing *disclosure representation* from *integration/reconstruction rule*. The pair actually evaluated matters. Never attribute Phase6 differences solely to information quantity while losses change.
3. Public-local \(\rho_{\mathrm{region}}\) and query \(\rho_{\mathrm{query}}\) are separate parameters. The baseline I1 graph-boundary composition, gamma-scaled evaluation regions, and October P2 induced-only evaluation region are different protocols.
4. Never turn finite explored model sets, MC precision, Gibbs retained mass or WB reference-resampling intervals into guarantees about unknown system truth.
5. Do not conflate historical M3 pilot (48/provider -> Top14), registered Phase5 V2 Top14, executed V3/V3b FULL343 (7/provider -> all343), or M2's different pilot/V3b/Phase6 portfolio selection.
6. Keep a strict PRAISE/PPG separation. Do not import unpublished GP+DVI, readiness scoring or old PPG QR/YOLO/Lidar experiment/data/code into this technical report.
7. No new scientific experiments or YAFS replay are required to construct the report. Never manufacture missing numerical subgroups. Unverified ancillary results remain explicitly labeled.
8. **Never overwrite the 26-page PDF, frozen experimental scripts, contracts, or results.** Draft B1 in a new document path and retain this migration map as a traceability record.

## A. Exact disposition of each source section

Here REUSE means preserve scientific content (not blindly copy old wording), REVISE means retain core but qualify/version it, MOVE means historical/technical appendix, REPLACE means write anew.

| Source in v11_45 | Editorial decision | Target B1 material | Mandatory qualification |
|---|---|---|---|
| Title and abstract p1 | **REPLACE** | Title + executive summary | No general solution to non-identifiability, certification, or all-graph success; results extend through Phase6 |
| §1 Introduction pp1–3 | **REVISE** | Ch1 Question and scope, Ch2 conceptual frame | Keep CAO \(o=(G,s,\sigma,r)\), \(\tau=(I,M)\), Eq2; frame *inverse feasibility*, not established impossibility |
| §2 Related Work pp3–4 | **MOVE + REVISE** | Ch1 short background; appendix literature review | Retain citations as historically sourced, bibliography/novelty not yet externally re-audited; no blanket comprehensive SOTA claim |
| §3 initial objectives pp4–5 | **REVISE** | Ch2 Definitions and reconstruction question | Replace finite-model “non-identifiability” generalization with *empirical ambiguity/search failure* under a specified model family |
| §3.1 SLA satisfaction p4 | **REUSE WITH QUALIFICATION** | Ch2 SLA estimand and numerical decision conventions | Eq4 is an optional modeled threshold rule, not a certified true-SLA admission |
| §3.2 candidate sets/envelopes pp4–5 | **REVISE** | Ch2 finite exploration; Ch4 methods/uncertainty | Eq5 conditional on explicitly enumerated propagated joint models, not all true I1-equivalent models |
| §3.3 public I1 p5 | **REVISE** | Ch3 Provider disclosure | Preserve public rectangular local regions, two rhos, observed I1; annotate acquisition/region nestedness and the unverified full raw-I1 semantics where necessary |
| §3.4 fixed graph and gamma test battery p6 | **MOVE + REVISE** | Ch5 historical pilot setup | Eq6 *pilot gamma-scaled query construction*; do not reuse as Phase5 generic Step0 or October P2 induced-region definition |
| §4 Methods pp6–10 | **REUSE FAMILY ALGEBRA, REWRITE IMPLEMENTATIONS** | Ch4 versioned methods | Eqs7–12; split pilot versus V2 registered versus V3b executed; include budgets, selection gates and candidate-set changes |
| §5 pilot results pp10–13 | **MOVE TO HISTORICAL CHAPTER** | Ch7 original pilot | Results confirmed; describe as single-condition test, not main project-wide result |
| §5.1 retrospective mechanisms pp13–15 | **MOVE TO DIAGNOSTIC CHAPTER** | Ch9a pilot post-hoc | Preserve Top1/3, weighting, truth table, biases; never claim larger support intrinsically required or one isolated mechanism identified |
| §6 interpretation pp15–16 | **REPLACE** | Ch10 cross-experiment synthesis | Answer new RQs over Phase5+Phase6+P2; old “in this pilot yes” can be quoted only with pilot scope |
| §7 validity p16 | **REPLACE + EXPAND** | Ch11 limitations/provenance | Add incomplete P2, method revisions, finite bank, identical simulator family, fixed physical embedding, no runtime controllers, external YAFS pin |
| §8 conclusion p17 | **REPLACE** | Ch12 decisions/open questions | Be candid: improved aggregate method rankings but substantial hard-case errors; feasibility conditional |
| References pp17–18 | **REUSE WITH LATER VERIFICATION** | References/related-work appendix | Keep citation keys but verify DOI/venue and current relevance during drafting, not guessed in blueprint |
| Appendix A pp19–22 | **REUSE MATHEMATICS; EDIT INTERPRETATION** | Technical appendix TA, and Ch10 short synopsis | Covariance and MC/reference-noise expectation formulas valid under assumptions; clipping diagnostics not confidence intervals or truth guarantees |
| Appendix B pp22–25 | **REUSE CONDITIONALLY** | Technical appendix TB | Wilson/paired bootstrap/normal approximations pointwise, M3 clipping to [0,1], fixed model support, width projections not observed MAE |
| Appendix C pp25–26 | **REPLACE** | Technical appendix TC: model-conditional decision examples | No true SLA guarantee, no assertion further simulation “does not change” decisions, note optional stopping and persistent model bias |

## B. Equation-by-equation migration ledger

**Original labels are retained as provenance identifiers here. New report numbering can be regenerated only *after* the section order is frozen.**

| Old label | Meaning | New placement/action |
|---|---|---|
| **(1)** | CAO offering \(o=(G,s,\sigma,r)\) | **KEEP** Ch2. Explain that SLA-satisfaction \(\sigma\) is one operational instantiation, not every historical CAO survival definition |
| **(2)** | \(\sigma_G(s)=P[f_G(A,H)\ge\rho]\) | **KEEP AS PRIMARY** Ch2. Spell out decided, deadline, unresolved, zero-decided; no first-passage semantics |
| **(3)** | \(\tau=(I,M)\) | **KEEP AS PRIMARY** Ch2. Distinguish interface \(I\) vs method \(M\) formally and when jointly varying |
| **(4)** | \(\hat D=1\{\hat\sigma_G^{(M)}\ge\beta\}\) | **KEEP AS DEFINED RULE** Ch2/uncertainty. A modeled decision, not dependable admission proof |
| **(5)** | finite model lower/upper \(\min/\max_{\vartheta\in\mathcal M_M}\sigma_G(s|\vartheta)\) | **KEEP WITH SET EXPLICIT** Ch4 + TA. Clarify finite *method-generated* propagated set, MC error on extrema, no coverage guarantee |
| **(6)** | pilot \(A_G(\gamma,\rho)\) SLA region scaling | **KEEP PILOT-ONLY** Ch5/Ch7. Mark distinct from Phase5 Step0 and public-induced-region October P2 |
| **(7)** | M0 same-\(\rho\) product | **KEEP BASELINE-ONLY** Ch4. Applicable region containment, not bound, M0 scores on a different denominator |
| **(8)** | provider-level I1 inverse minimum squared-distance fitting | **KEEP AS TEMPLATE** Ch4. Frozen M1-v2 TPE selection differs from executed V3b 7 independent 25-trial runs+fresh N100 selection |
| **(9)** | equal 27-member M2 mean | **KEEP** Ch4. Phase4 diversity portfolio excludes M1 anchor; V3b RMSE top3 *includes* its M1 rank1 |
| **(10)** | Gibbs weights \(w_{ik}\propto e^{-\lambda E_{ik}}\) | **KEEP WITH LOSS + VERSION** Ch4. Pilot 48-candidate Gibbs weighting, V3b 7-candidate KL weights; not calibrated Bayesian posterior |
| **(11)** | weighted graph \(\sum_{j\in S}\alpha_j\hat\sigma_{G,j}\) | **KEEP** Ch4. Explicit per-version selected \(S\), graph trajectory allocation and whether full support |
| **(12)** | \(|\Sigma_{\rm full}-\Sigma_S|\le1-m_S\) | **KEEP EXACT** Ch4/TA. Bound only within same finite weighted model distribution; FULL343 zero internal truncation not zero truth error |
| **(A.1), (A.2)** | weighted variance/covariance, independent-member bound | **KEEP** TA, conditions on seeds, weights and fixed model support |
| **(A.3)–(A.5)** | raw model spread and MC subtraction | **KEEP AS PLUG-IN DIAGNOSTIC** TA; expectation identities require unbiased estimators, clipping is biased and not a guaranteed error interval |
| **(A.6)–(A.8)** | finite WB discrepancy and noise decomposition | **KEEP** TA; requires independence of WB/method estimators and unbiasedness; label nonnegative estimator only |
| **(A.9)** | proposed model-spread to prediction-error calibration | **MOVE TO OPEN HYPOTHESES** Ch12/TA; **not validated** and not deployable without independent calibration |
| **(B.1), (B.2)** | \(c/\sqrt B\) width extrapolation and inverse | **KEEP AS PROJECTION** TB; fixed support/design, not predicted model error or repeated-look decision guarantee |
| Unnumbered graph LCQ composition algebra | sum/max latency, additive cost, min quality | **KEEP WITH CONTEXT** Ch2/Ch5; physical fixed-stage constants apply to **pilot graph only**, not every Phase5 graph |
| Unnumbered admission-envelope cases | all finite models above/below/straddle \(\beta\) | **KEEP AS TRIVIAL SET PROPERTY** TA; neither a statistical proposition about the hidden model nor an externally calibrated risk guarantee |

## C. Disposition of all four tables and three figures

| Original object | Decision | Precise placement and treatment |
|---|---|---|
| **Table 1** p7, M0–M3 hierarchy | **REVISE** | Ch4. Keep *as historical Phase4 method taxonomy*; add a new **version matrix** including registered V2 vs executed V3b/Phase6 |
| **Table 2** p10, pilot MAE/decision/mass/cost | **REVISE AND SPLIT** | Ch7. Separate original prospective production methods from retrospective Top1/Top3/Top14 operational readouts. Denominators: M0 **333** applicable predictions and **274** certain WB decisions; others **555** and **481** respectively. “Graph traj.” ≠ total computational cost |
| **Figure 1** p12, 15-cell sigma curves | **RETAIN HISTORICAL** | Ch7 figure with caption “fixed ParAll pilot; matched-B=1400 retrospective Top1/Top3 overlays.” Label absence of method MC bands and M0 applicability. Do not place ahead of Phase5 main evidence |
| **Table 3** p13, MAE/bias by regime | **RETAIN HISTORICAL** | Ch7. Each regime 185 related query–horizon points. Top1/3 are matched-B retrospective, not operational B100/300 |
| **Table 4** p14, hidden provider parameters & I1 fits | **RETAIN RETROSPECTIVE** | Ch9a. All archived parameter and loss values reconciled; privilege after-freeze, no structural identification theorem |
| **Figure 2** p22, accuracy–graph trajectories | **REBUILD OR RESTRICT** | Ch7/technical appendix. Original dotted “nondominated” line **cannot** be called a frontier over all Table2 operating points because Top1 B100/.0399 dominates M1 B100/.1852 in the plotted 2D plane. Either restrict caption to prospectively chosen primary points or redraw with explicit post-hoc status and local search cost as third dimension. Do not infer total economic optimality |
| **Figure 3** p25, numerical MC-width budget | **RETAIN TECHNICAL PROJECTION** | TB. Explicit \(B^{-1/2}\) planning assumption, *clipped* M3 normal bands, and that M2's .0563 width source is not independently recomputed from shared-seed arrays. No MAE/operational guarantee extrapolation |

**Verified display source:** all 22/22 collected original files and 13/13 selected archive manifest hashes; main pilot methods, Table3 Top3 regime results, Table4 values, Fig2 WB bootstrap and Fig3 M1/M3 width anchors match saved records. Two *narrow* outstanding checks are Table2 operational B100/B300 Top1/3 numerical curves and Fig3's M2 paired-bootstrap width; retain them as **reported but not independently recomputed** until primary rows are sourced. Other preidentified issues are **interpretive** and must be fixed even when their numeric values match.

## D. Proposed B1 internal report skeleton (in reading order)

| New chapter | Purpose / essential contents | Evidence | Existing material to reuse |
|---|---|---|---|
| **0. Executive synthesis** | Status as of Oct16; achieved benchmark, primary successes/failures, incomplete questions, provenance summary | Core E01–E12 | Abstract **rewritten** |
| **1. Research problem and scope** | CAO background, why infer end-to-end SLA from provider-local disclosures, research questions, terminology and distinction from PPG | E01, relevant background | §1–2 **condense** |
| **2. Formal objective and benchmark model** | \(o\), \(\tau\), \(c_G\), \(\sigma_G\), region algebra, SLA assessment, zero-decided/deadline semantics, physical model boundaries | E01, E05 | §1, §3.1, selected §3.4 |
| **3. Provider information** | Public I1 acquisition and rho-conditioned provider rectangles/surfaces; exact producer-vs-consumer evidence boundary; I2a/I2b disclosure structures and how losses depend on interface | E01, E07 | §3.3 + new Phase6 |
| **4. Integration algorithms by version** | M0–M3 equations, provider fit families, portfolio selection, weights, finite supports and graph trajectory allocations; **pilot/V2/V3/V3b/Phase6** matrix | E02–E07, E09 | §3.2 + §4 extensively revised |
| **5. Simulator and experiment protocol** | AICon patched YAFS controller, Phase5 graph AST, fixed physical topology, workload, FCFS/Gamma and LCQ; Phase4 gamma regions vs Phase5 Step0 vs October public region; design/freeze methodology and explicit revisions | E01–E06 and 2.5 audit | §3.4 + new provenance |
| **6. Research chronology** | Phase1–4 historical development, Phase5 preregistration and implementation revisions, Phase6 after graph evidence, P2 follow-ups | E01–E12 | Mostly new; backed by B1 chronology |
| **7. Historical fixed-graph pilot** | M0–M3 performance, M0 applicability, Easy/Mid/Stress, operational vs matched budgets, hidden truth retrospective, decision agreement conditional on WB uncertainty | E02–E03 | §5 + old Tables 1–4/Fig1/Fig2 corrected |
| **8. Main multi-world, multi-graph evaluation** | 16 planned/12 eligible, P2 excluded; Method V3b FULL343 errors, bias, topology contrasts, Step0 sensitivity, WB N1000, finite reference bootstrap, graph-budget comparison; primary *positive and negative* outcomes | E04–E06 | **New**, frozen Phase5 outputs |
| **9. Post-main methodological investigations** | (9a) pilot mechanism ablation, (9b) Phase6 matched I1strong/I2 family at P4/G_SEQPAR, (9c) October P2 public-induced-region native budgets, (9d) truth-in-domain and perturbation diagnostics. Clearly development/retrospective, not new independent prospective validation | E03,E07–E12 | §5.1 plus new Phase6/P2 |
| **10. Across-study synthesis and uncertainty** | Empirical inverse-search limitation versus formal identifiability; weighting/support not intrinsically sufficient; geometry-dependent errors; numerical vs model-vs-WB variance; safe interpretations of admission threshold | E02–E12 | §6 and App A/B rewritten |
| **11. Validity, reproduction, and missing experiments** | Generator-in-family limit, three-provider fixed physical model, Step0 P2 gate, different method versions and simulation budgets, I2 information–loss confound, smoke-order deviation, external YAFS dependency, all remaining artifact gaps | E01–E12 and 2.5 audit | §7 replaced |
| **12. Conclusions and next falsifiable questions** | Condense what is established, not established, lowest-cost needed next steps. Separate future hypotheses from manuscript claims | E01–E12 | §8 replaced |
| **Technical appendices** | TA equations and assumptions; TB numerical width; TC threshold demonstration; TD archived method/provenance IDs and exact source tables; TE selected related work | Relevant | Appendices A–C and citations, corrected |

This structure is intentionally **not optimized yet for page count or venue**. It allows the B1 evidence record to be complete; a later CAiSE paper may selectively focus on a sharper falsifiable thesis.

## E. New tables/figures required in B1 (source-only; no simulations)

**Priority 1 (needed before coherent report):**

- **New Table N1:** dated method family/implementation matrix: pilot Phase4; registered Phase5 V2; executed V3/V3b FULL343; Phase6 M2 variants; selection loss, candidate count, graph support, graph trajectories, evidence role.
- **New Table N2:** design/eligibility matrix of 4 provider worlds ×4 logical graph ASTs, frozen Step0 status, 12/16 eligibility, N1000 final WB, 15 query cells and horizon grid. Mark all P2 world × graph cells ineligible and exclude them from main outcome denominators.
- **New Figure N1:** native three-provider graph and four logical dependency maps; show that physical embedding is fixed, and arrows encode logical completion dependencies. No “heterogeneous physical topologies” claim.
- **New Figure N2:** time-stamped evidence/freeze flow from I1 through Step0, V3b model selection, pre-WB FULL343 revision, 12-cell prediction freeze and independent N1000 final WB. Mark nonconforming smoke-order and method-revision points.
- **New Table N3:** main Phase5 method MAE, RMSE, bias, applicability and graph budget. 6660 M1/M2/M3 points; M0 1776 points not directly comparable. Include group/per-world/per-graph breakdown, not only aggregate.
- **New Figure N3:** Phase5 world × graph per-method MAE/bias and topology contrasts from frozen evaluation tables. Label P2 as *Step0 excluded*, not imputed; show contradictory Seq-vs-Par directions across worlds.
- **New Table N4:** Phase6 matched six-way P4/G_SEQPAR outcomes, same 555-point set, M2/27 joint members, 2700 graph trajectories per variant; explicitly state interface **and reconstruction loss** change.
- **New Table N5:** October P2 public-induced-region comparison M1/M2/M3 with native **unmatched** budgets (100/2700/1400) and separate truth-fit/search-gap diagnostics; not part of Phase5 excluded cells.

**Priority 2 (valuable if frozen data support):**

- **New Figure N4:** divergence between selected provider I1 fits and privileged hidden truth, separating local fit loss, parameter distance and graph error (P2 truth audit).
- **New Table N6:** ledger of negative/uncertain hypotheses: broad identifiability, adequacy of Top14 mass, necessity of ensembling, directional topology masking, improvement from richer I2, P2 failure vs public-induced region, operational assurance.
- **New Table N7:** sensitivity/uncertainty taxonomy: pointwise MC variance, model spread, retained support mass, WB seed reference bootstrap, between-physical-world variation. No unverified blanket confidence bound.
- **New figure or appendix data:** Phase5 sigma(H) trajectories for selected eligible Easy/Mid/Stress cases with correctly labeled finite WB and method support, only from archived points.

No new graphics should be generated from invented time series or guessed graph-level values. If the frozen data are not available to the B1 writing environment, the correct action is a read-only source extraction.

## F. Claim scope and presentation contract

Every quantitative display carries, visibly in table/caption or footnote, **all**:

1. **Evidence role**: registered/planned, calibrated design, frozen same-condition pilot, pre-final-WB method revision, held-out final-WB evaluation of frozen V3b, or retrospective/development diagnostic.
2. **Method implementation**: M1-v2 vs M1-V3b; M2-diverse vs M2-top3-RMSE vs Phase6 M2; M3 Top14 pilot vs V3b FULL343; full vs diagnostic Top1/Top3. Use exact local IDs in provenance appendix.
3. **Population and denominator**: provider world, graph, query/rho/regime, \(H\) grid, number of cells, WB N, M0 applicability. No 555 or 6660 *correlated* query-horizon points counted as independent physical replicates.
4. **SLA region construction**: gamma scaled pilot/Phase5 Step0 vs deterministic public-induced P2.
5. **Cost/uncertainty meaning**: local search trajectories vs graph trajectories, MC intervals vs WB reference bootstrap, support truncation vs model-truth error.
6. **Numerical verification tier**: source-contract checked, independently re-scored saved data, primary raw ledger replayed (not accomplished), or reported/ancillary pending.

### Core claim-level phrasing for B1

| Topic | Allowed source-grounded claim | Forbidden implication |
|---|---|---|
| Feasibility | Pilot M3 achieves .030368 MAE with WB N200 in *one* physical ParAll graph | Accurate recovery is established across arbitrary service graphs |
| Broader prediction | Phase5 M3 FULL343 has lowest aggregate MAE .121890 vs M1 .157015 and M2 .133951 on 12 eligible cells (N1000 WB), **with substantial residual errors** | The inverse problem has been solved, or FULL343 provides a reliable SLA guarantee |
| Identifiability | Distinct fitted candidates and P2 truth-better-than-selected fits document an empirical search/reconstruction gap | Mathematical impossibility of inferring generating model from I1 |
| Multi-model | Weighting helps on same 14 models in pilot StageB; Top1 matched B1400 .028784 outperforms production Top14 .030368 in that pilot | Averaging 14/343 models is inherently necessary or universally best |
| Richer I2 | I2a/I2b variants do not uniformly improve matched *information–loss* pipelines in P4/G_SEQPAR | The extra public information is useless, or a purely informational causal effect was isolated |
| P2 induced region | M1 .132000, M2 .140584, M3 .127867 MAE over 185 points, with unmatched budgets and a deterministic common public boundary | The Phase5 excluded P2 Step0 cells were salvaged; M3 won a cost-matched competition |
| Admission | Thresholding of \(\hat\sigma_G\) and conditional numerical bands yields modeled/diagnostic decisions | A system-wide or deployment-valid certification of hidden SLA risk |
| Simulator | Four fixed logical DAGs were compiled into native YAFS completion barriers; saved outputs/revisions/freeze hashes are documented | Four fundamentally different physical continuum deployments, general graph theory validation, active online multiagent control |
| Reproducibility | 12/12 prediction hashes and 12/12 final-WB backlinks confirmed; recorded freeze preceded earliest WB start | Every historical external YAFS package and actual execution binary was bitwise attested |

## G. Exact rewrite order, safeguards, and next gate

**Do not write the report chronologically from its original Introduction.** Produce source-backed sections in dependency order:

1. **Data contract:** freeze this blueprint, event/estimand terminology, method naming, chapter/source migration and requested new-display specifications.
2. **Definitions/methods:** draft Ch2–5 using the old manuscript's sound formulas and the 2.3 audits; have no unqualified non-identifiability, Bayesian-confidence or first-passage statements.
3. **Results before storytelling:** draft Ch7–9 using verified pilot, Phase5, Phase6 and P2 tables, tagging all data by phase/role/population. New tables/figures must cite frozen CSVs, not copied old prose.
4. **Synthesis:** draft Ch10–12, including negative results and explicit untestable/unevaluated claims. Cross-check the 68 claim-audit items before finalizing any assertion.
5. **Appendices:** migrate A/B, rewrite C, include exact source/sha provenance and all known reproducibility gaps.
6. **Executive summary + abstract:** write **last**, once numbers and limitations are fixed, to avoid reinstating the old pilot-centric claim.
7. **Bibliography and consistency pass:** check technical units, beta/rho, graph names, dataset source, pointwise vs simultaneous intervals, stage labels, all equation/cross-references and caption denominators.

### Pending checks that must not silently become confirmed facts

- The old Table2 **operational** Top1 B100 and Top3 B300 outcomes and Appendix B's M2 B2700 bootstrap width remain **reported but not independently recomputed from original source arrays**.
- Formal provider-I1 region-construction nestedness/source details beyond the already audited implementation chain may require a targeted source-level revisit.
- Current installed AICon git/head/source hashes are known; exact historical imported source/dirty status not attested.
- Prior manuscript's citation bibliography was not freshly validated; no novelty claims should rely solely on an old citation list.

These do not block an **honest draft** when visibly qualified. For publication-grade final sign-off they become explicit editorial or targeted-read-only evidence actions, not requests for new scientific simulations.

## Step 2.6 disposition and Step 2.7 hand-off

**2.6 blueprint is complete and actionable.** No existing scientific manuscript or simulator/experiment file was modified. A companion \`MANUSCRIPT_MIGRATION_MATRIX_V0_1.csv\` gives each original block and requested new display a stable traceability ID.

**Proposed Step 2.7 sign-off gate:** verify (i) every major old chapter/equation/table/figure is mapped; (ii) every high-priority claim in the 68-entry ledger is assigned a replacement/scope instruction; (iii) no claim of solved inverse-identifiability or SLA guarantee appears in the planned summary; (iv) all data sources/evidence roles are explicit; (v) remaining source-level checks are explicitly marked; (vi) draft paths/new figures are separate from frozen science; (vii) PPG firewall is preserved.

If these checks pass, create a *new B1 document file* (not an in-place revision of the CAiSE pilot manuscript) and proceed to drafting.
