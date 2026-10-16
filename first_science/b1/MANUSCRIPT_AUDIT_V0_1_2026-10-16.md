# PRAISE B1: Manuscript audit v0.1 (2026-10-16)

**Status:** INITIAL CLAIM-LEVEL AUDIT COMPLETE; technical and artifact-by-artifact cross-check still pending. **No scientific manuscript has been rewritten.**

- Historical source: `praise_caise_workshop_note_v11_45(1).pdf`, 26 pp., generated on 2026-10-02 (UTC), SHA-256 `e2734dc446fe9cc4991dc04800cd5e828af8784269a1dbc274036be3b7f46ada`.
- Authoritative B1 source: [`evidence_registry_v1_0.json`](evidence_registry_v1_0.json) and [`METHOD_VERSION_CHRONOLOGY_2026-10-16.md`](METHOD_VERSION_CHRONOLOGY_2026-10-16.md).
- Individual issue/action ledger: [`MANUSCRIPT_CLAIM_AUDIT_V0_1.csv`](MANUSCRIPT_CLAIM_AUDIT_V0_1.csv) with **45 page-anchored entries**: 21 P0, 21 P1, 3 P2. Priority P0 means mandatory correction before reporting, *not* 21 proven mathematical errors.

## Step-2 substeps and current status

| Substep | Question | Status | Artifact / exit gate |
|---|---|---|---|
| **2.1 Baseline and scope** | Which manuscript, scientific era and evidence are being reviewed? | **Done** | Exact 26-page PDF and SHA; v1 evidence registry |
| **2.2 Claim inventory and chronology** | What does each section assert; are results pilot, prospective, development or post-hoc? | **Initial pass done** | 45-entry claim ledger; chronologically separated M3 variants |
| **2.3 Definitions and mathematical semantics** | Is each SLA, I1, M0/M1/M2/M3, uncertainty and cost definition valid under its implementation? | **2.3a SLA and 2.3b method source audits complete; statistical-uncertainty mathematics pending** | [SLA audit](SLA_SEMANTICS_SOURCE_AUDIT_2026-10-16.md), [method-definition audit](METHOD_DEFINITION_SOURCE_AUDIT_2026-10-16.md) |
| **2.4 Tables and figures** | Are each number, reference cohort, budget and claimed ranking consistent? | **Main saved-result metrics verified; figure/appendix internal consistency issues identified** | Review original figures and appendices, compare with verified tables |
| **2.5 Engineering/reproducibility** | What YAFS/AICon changes, provenance and processing gates can be documented? | **Pending** | Inventory actual code changes and frozen manifests, no new experiments |
| **2.6 Preservation and reuse plan** | Which prose/formulas survive in B1 and which must be moved or rewritten? | **First-pass map below** | Approved section-by-section reuse plan |
| **2.7 Audit sign-off** | Can report drafting begin without importing misleading claims? | **Not yet** | All critical P0 definitions and quantitative inconsistencies addressed or explicitly flagged as unresolved |

## Section-by-section disposition

| Manuscript location | Proposed B1 treatment | Main reason |
|---|---|---|
| Title / Abstract (p1) | **Rewrite** | Single successful pilot cannot lead a full project's neutral internal record. No formal demonstration of structural non-identifiability. |
| §1 Introduction (pp1–3) | **Preserve CAO and tau; rewrite claims/RQs** | `o=(G,s,sigma,r)` and `tau=(I,M)` stand, but research stages and scope expanded. |
| §2 Related work (pp3–4) | **Retain as background; update positioning** | Publication novelty claims are not the internal report's objective, and bibliography completeness was not audited here. |
| §3.1 SLA satisfaction (p4) | **Preserve formula; qualify admission** | Numerical MC intervals do not guarantee hidden-system dependability. |
| §3.2 Inverse ambiguity (pp4–5) | **Preserve conditional finite-model construction; qualify 'non-identifiability'** | Distinguish candidate ambiguity and optimizer failures from mathematical identifiability. Avoid unqualified M3 counts. |
| §3.3 I1 (p5) | **Preserve with semantic audit** | Keep `rho_region` and `rho_query` distinct, and public evidence vs hidden provider traces separate. |
| §3.4 Pilot graph and SLA battery (p6) | **Preserve as historical experiment design** | `gamma`-scaled Step0 regions are not the public-induced-region P2 experiment, and not all Phase5 graph structures. |
| §4 Methods (pp6–10) | **Retain base algebra, split by version** | M3 pilot 48 candidates/provider, top14 vs Phase5 V3b 7/provider FULL343; M1 and M2 variants also differ. |
| §5 pilot results (pp10–15) | **Keep as historical evidence chapter** | Its pointwise MAEs, signed errors and post-hoc audit were verified; do not transfer performance to other graphs/worlds. |
| §6 interpretation (pp15–16) | **Replace** | Phase5 and Phase6 results materially restrict interpretation. |
| §7 validity (p16) | **Expand** | Include Step0 exclusions, finite candidate search, common simulator family, limited workload/scenario support, method-development provenance. |
| §8 conclusion (p17) | **Replace** | Should summarize observed progress and unresolved difficulties, not promote an overall winning integration method. |
| References (pp17–18) | **Keep with bibliographic audit pending** | Journal-style positioning can move to a background section; no external DOI verification performed in this audit. |
| Appendix A (pp19–22) | **Retain only after detailed audit** | MC/model-spread/finite-WB decomposition is valuable; no calibration guarantee follows. |
| Appendix B (pp22–25) | **Retain conditionally** | Width–budget projections valid only for frozen estimators and assumptions; numerical precision is not predictive accuracy. |
| Appendix C (pp25–26) | **Rewrite operational assertions** | A resolved Monte Carlo band gives a numerically stable decision *conditional on the reconstructed model*, not a dependable service admission guarantee. |

## Highest-priority scientific corrections

### 1. The target estimand must stay unchanged

The manuscript correctly introduces

`sigma_G(A,H;rho_query) = Pr[c_G(A,H) >= rho_query]`

with `c_G` the fraction of **decided** requests that meet the graph-level latency/cost/quality region by H. A request may be decided by a completed request or a missed deadline; unresolved requests are excluded and zero decided is treated compliant. This is **not** the first-passage probability `Pr(T_first_violation > H)`. The former is not guaranteed monotone in horizon H. Retain `sigma` as historical notation, but in B1 prefer **horizon-dependent SLA-satisfaction probability** where precision is needed. Any exploratory first-violation work must be labeled as a *different target*.

### 2. The manuscript's 'non-identifiability' framing is stronger than what was demonstrated

Several candidates with distinct hidden parameters and nearby finite public-I1 losses are evidence of an empirically difficult inverse problem and/or reconstruction ambiguity. The P2 true-parameter audit indicates that the true parameters fit public I1 better than the selected candidates despite lying within the search domain. **This is direct evidence of a search/reconstruction gap, not a proof that the interface cannot uniquely determine the hidden parameters.** Without an established equivalence class, tolerance/noise model, and indistinguishable observation map, avoid unqualified theoretical non-identifiability claims.

### 3. Do not apply one M3 definition to all phases

- Pilot: 48 latent proposals/provider; Gibbs weights over `48^3`; 14 dominant joint models propagated; B1400/B2000 operating points.
- Phase5 V2 registered Top14, followed by documented V3/V3b provider reconstruction changes and a **pre-graph-WB** change to full `7^3=343` support at B1400. This is a real method-development revision and must be declared.
- Phase6: matched I1strong/I2 variants evaluated with 27-member equal-weight **M2**-style ensembles, but with different local reconstruction objectives.
- P2 induced-region: deterministic public boundary composition shared by M1/M2/M3, while stochastic sigma estimates differ; native graph simulation budgets are unmatched.

A reader must always know *which* M3, *which* graph/workload, *which* SLA region constructor, *which* WB reference and *which* evidence role produced a number.

### 4. Replace broad 'works' conclusions with calibrated evidence

The Phase4 pilot gives MAE 0.185171/0.068153/0.030368 (M1/M2/M3-B1400) on one graph, N200 WB, 555 points. The Phase5 12-cell eligible battery gives 0.157015/0.133951/0.121890 (M1/M2/M3-FULL343), N1000 WB, 6660 points. The latter is an improvement in aggregate ranking but not accurate survival recovery in many nontrivial Mid/Stress panels. Phase6 richer disclosures did not consistently beat a matched stronger I1 reconstruction on the studied P4/G_SEQPAR cell.

Do **not** compare absolute MAE as if the populations and algorithms were the same, or treat the 12 eligible cells as a representative sample of all 16 planned. Four P2 physical cells failed prospective Step0. Registered heterogeneous-vs-symmetric contrast could not be estimated.

### 5. Preserve genuine pilot mechanisms while restricting causal claims

Matched frozen 14-member pilot support: uniform-weight MAE .05490 vs evidence-weighted equal-allocation MAE .04222. That supports a *within-support weighting effect*. But cost-matched Top1 MAE .02878 is below the full weighted14 production MAE .03037 in this pilot. **The experiment does not demonstrate that multimodel averaging is intrinsically necessary**, nor that M3's overall advantage was caused uniquely by weighting, support size, search coverage or simulation allocation.

### 6. Remove unsupported 'assurance' terminology

Equation (4) is a legitimate thresholding rule on an estimated probability. Appendix B's MC bands characterize conditional numerical uncertainty for a fixed reconstructed model family and sampling design. They do not cover the unknown hidden-system `sigma_G` when the reconstruction is biased. The phrase 'largest assurance threshold' (§3.1) and 'certifiable recursive depth' (§6) overstate the evidential claim. Appendix C should discuss **numerical decision resolution conditional on a model**, not actual SLA certification.

### 7. Concrete internal inconsistency: Figure 2 cost–accuracy frontier

On p22, Fig2 describes the nondominated pilot points as M1 (B100, MAE .1852), M3-B1400 and M3-B2000, while plotting a selected subset. But Table2 on p10 reports **M3 Top1 at B100, MAE .0399** under its explicit operational readout. In that same recurring graph-cost/MAE plane, the reported Top1 point dominates M1, so M1 cannot be called nondominated among *all reported operating points*. Either:

- explicitly call Fig2 a frontier **restricted to the original prospectively selected method implementations** (not the full reported operational choice set); or
- update the figure and Pareto analysis to incorporate the operational Top1/Top3 points, while separately showing provider-reconstruction up-front cost and retrospective status.

For B1, this should be reported as a historical analytic inconsistency, not concealed by deleting the figure.

### 8. Concrete editorial/structural inconsistency: MC-width column

Appendix A on p19 states that Appendix B documents 'the MC-width column of Table 2', but the printed Table 2 does not contain any MC-width column. This cross-reference must be corrected when reusing the uncertainty appendix.

### 9. Topology hypothesis and recursive composition need status changes

The pilot's possible masking of faster branches was only a hypothesis. The completed Phase5 prospective topology contrast gives inconsistent sequence-minus-parallel direction across provider worlds, and P2's exclusion prevents the registered heterogeneous-minus-symmetric contrast. Recursive composition depth was **not experimentally evaluated**; do not imply it is established.

## Proposed B1 report architecture (after audit)

1. Objectives, historical formulation and evidence classifications.
2. Simulation infrastructure and extensions, including the native graph-branch execution model.
3. Provider disclosures: I1 and I2 variants, precise SLA semantics.
4. Integration methods: M0/M1/M2/M3 method families **and chronological versions**.
5. Experimental design and provenance: Phase1–6, Step0, frozen bank/gate policies.
6. Results organized by episode: pilot; Phase5 cross-world/topology battery; Phase6 matched interfaces; independent P2 induced-region experiment.
7. Diagnostic evidence: model spread, candidate selection, true-parameter fit/sensitivity, operator sensitivities, time/numerical cost.
8. Cross-experiment synthesis: supported findings, unsupported hypotheses, sources of uncertainty, applicability limitations.
9. Technical reproducibility, exact artifact registry, versioned method/evidence references.
10. Open questions and possible future directions, without claiming a successful prediction solution.

Keep rich technical material as appendices, but all formulas and graphs carry a **scope/version tag**.

## Sign-off and next limited checks before any rewrite

- **2.3a (done at static-source level)** The canonical cumulative-SLA decision extraction and zero-decided convention were checked against Phase1/Phase3/Phase5 code. See [source-level SLA semantics audit](SLA_SEMANTICS_SOURCE_AUDIT_2026-10-16.md). The separate I1 public-region/query construction and raw-ledger replay are still unverified.
- **2.3b (static source inspection complete, archived-identity check pending)** M0, M1, M2, M3 variants, provider-selection rules, weighting and finite-support propagation have been source-audited. See [method-definition audit](METHOD_DEFINITION_SOURCE_AUDIT_2026-10-16.md) and run [method-support verification](verify_method_support_v0_1.py) to independently check saved support tables.
- **2.3c** Audit `sigma_G` vs first-violation labels and the statistical interpretation of the confidence/Monte Carlo bands.
- **2.4** Resolve the Fig2 frontier inconsistency and missing MC-width reference, plus compare all manuscript tables against exact frozen experiment identities; don't mix local estimation and graph simulation budgets.
- **2.5** Inventory simulator extensions and chronology in concrete code terms (not claims of generic simulator novelty).
- **2.6** Agree final retain/update/rewrite plan. Only then begin editing the historical manuscript source or opening a fresh B1 report branch.

**No additional scientific simulations are required for these audits.**
