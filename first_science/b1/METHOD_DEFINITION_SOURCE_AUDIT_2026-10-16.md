# PRAISE B1 manuscript audit 2.3b: Method-definition and version audit

**Date:** 2026-10-16  
**Status:** STATIC SOURCE/CONTRACT AUDIT COMPLETE. Frozen model-selection and weight identities remain subject to the separate read-only local verification script.  
**Historical manuscript:** \`praise_caise_workshop_note_v11_45(1).pdf\`, principally §§3–4 and methods-dependent interpretations in §5 and Appendices A–C.  
**Reference:** \`b1/evidence_registry_v1_0.json\`; \`b1/METHOD_VERSION_CHRONOLOGY_2026-10-16.md\`.  
**Scope:** original Phase3/4 I1 methods, registered Phase5 V2, executed Phase5 V3/V3b FULL343, later P2 induced-region comparison, and Phase6 matched I1/I2 method families. Code and frozen contracts, not old manuscript prose, are the method authority.

## 1. General method/estimand separation

The two axes of \(\tau=(I,M)\) have distinct roles:

- \(I\): **what a provider actually discloses**, including public \(\rho_\text{region}\)-indexed rectangular admissibility regions and \(\sigma_p(A_p,H;\rho_\text{query})\) surfaces under I1. I2a adds anonymous full marginals of trajectory compliance; I2b also provides anonymous paired within-window temporal compliance measures.
- \(M\): **what the entrepreneur computes** from disclosure, a known graph and public workload. A method may analytically compose boundaries, fit stochastic provider surrogates and simulate a graph, or combine multiple graph predictions. Local search loss, model family, candidate set, aggregation and simulation budget are part of the method, not merely incidental implementation details.
- Public-region construction and graph-sigma estimation must be reported separately. For the October P2 induced-region experiment, \(A_G^{I1}=\operatorname{Compose}_G(A_A,A_B,A_C)\) is a **common deterministic boundary**, not a separately learned region for M1, M2 or M3. Phase5 Step0, by contrast, selected *scale-calibrated evaluation queries* rather than evaluating only the unscaled induced public region.
- The score \(\sigma_G(A,H;\rho)\) is the probability that a trajectory's **cumulative decided-request compliance fraction** is at least \(\rho\). The source-level SLA audit confirms missed deadlines enter as decided failures. This is not absorbing first-violation survival.

## 2. Frozen M0: analytic boundary-composition and product predictor

**Source:** \`phase3/m0_analytic_composition.py\`; \`phase3/config_phase3_m0_contract_v1.json\`; \`phase5/run_phase5_step0_v2.py::_base_boundary\`; \`phase5/run_phase5_graph_prediction_v3b_fullsupport.py::_m0_predictions\`.

- Given fixed disclosed local LCQ boundaries, recursively compose **sequence: L sum, C sum, Q minimum; parallel_all: L maximum, C sum, Q minimum**, plus known deterministic network and fixed-stage terms.
- With an **exogenous requested graph region** \(A_G\), M0 is numerically applicable only when the public induced rectangle is contained in the requested \(A_G\). \`boundary_is_sufficient_for_query\` implements \`l_induced<=l_requested\`, \`c_induced<=c_requested\`, \`q_induced>=q_requested\` (up to tolerance).
- M0 reads every required public I1 provider survival value at the **same rho_query as the global query** and computes
  \[
  \widehat\sigma_G^{M0}(H;\rho)=\prod_{p}\sigma_p(A_p,H;\rho).
  \]
- The multiplication is a **deliberate modeling simplification**. Even assuming independence of these local *events*, simultaneous local compliance fractions each at least \(\rho\) does not generally imply the global graph satisfies \(\rho\), because violating request sets can differ and the graph's topology/execution coupling matters. Consequently M0 is **neither a lower bound nor an admission certificate**.
- M0 is not a hidden-process reconstruction; the boundary composer is not M3's stochastic composition mechanism.
- Pilot and Phase5 use different region/calibration contexts. In the Phase5 broad battery M0 is scored on only 1776 eligible points versus 6660 M1/M2/M3 points; comparing its aggregate error with M1–M3 as though the support were identical is invalid.

**Disposition for manuscript:** retain boundary algebra and same-rho product *as an explicitly labeled baseline*, with applicability and scope. Remove any lower-bound, theorem, or guarantee implication. Do not imply that M0 alone estimates hidden provider parameters.

## 3. Frozen pilot M1 and subsequent V3b M1 are different procedures

**Source:** \`phase3/run_m1_provider_lift_v2.py\`; \`phase3/config_phase3_m1_contract_v2.json\`; \`phase5/run_phase5_provider_reconstruction_v3.py::_fit_one\`; \`phase5/freeze_phase5_reconstruction_v3b_selection.py::_rank_provider\`.

- **Phase3/4 M1-v2:** jointly fit one FCFS Gamma-like provider surrogate \(\theta_p=(\mu_p,\kappa_p,\mathrm{CV}_p)\) against the full publicly disclosed I1 surface using Optuna TPE, shortlist/confirmation/replay controls, and then freeze the provider surrogates before native graph propagation. Pilot M1 used the public I1 domain/closure conventions, not provider secret parameters or graph-WB fitting.
- **Registered Phase5 V2:** a different declared instantiation of the Phase3/4 M1-v2 family with 100 TPE trials, a predeclared one-round boundary-expansion rule and local confirm/replay. This registered stage must remain in provenance.
- **Executed Phase5 V3/V3b:** replace that provider search by *seven independent* TPE fits, 25 trials each, five startup trials and a separate 15-trajectory search seed bank per fit. Retain one winner per fit, re-score seven winners on a fresh common N100 local bank, and replay on a second independent N100 bank for diagnosis only. V3 first selected a behavioral-centroid representative; the later **V3b** freeze instead selects the one candidate with **lowest rescore I1 RMSE**. No candidate is chosen by graph white-box accuracy.
- **Graph prediction:** one Cartesian triple of frozen provider surrogates; the Phase5 mainline uses 100 graph trajectories per physical cell.

**Important:** these candidates are selected on *provider I1 fit*, not verified to recover hidden parameters. The October P2 truth audit found significantly better public I1 fits at the known generating parameters than at the selected V3b candidates. Do not call M1 a recovered actual provider model.

**Disposition:** label Phase3/4 and Phase5 V3b procedures separately, rather than one generic M1 algorithm.

## 4. Frozen pilot M2 and Phase5 V3b M2 differ even in nesting semantics

**Source:** \`phase4/config_phase4_m2_joint_ensemble_semantics_v1.json\`; \`phase4/M2_CHAPTER_CLOSE_2026-09-22.md\`; \`phase5/freeze_phase5_reconstruction_v3b_selection.py\`; \`phase5/run_phase5_graph_prediction_v3b_fullsupport.py::_m2_predictions\`.

- **Phase4 M2:** 3 **independently confirmed, diversity-selected** provider surrogate representatives per provider, based on the Phase4 M2-A4 search and local compatibility gate; Cartesian support of 27 joint models, each equally weighted. The frozen Phase4 contract explicitly declares \`M1_anchor_in_M2_ensemble: false\`. Accordingly M2 is **not** a literal average centered on M1, and M2-M1 difference cannot be attributed solely to averaging the exact M1 hypotheses.
- **Phase5 registered V2 M2:** LHS/GP search with a hard I1 compatibility criterion and instantiation failure semantics. Historical protocol, *not the executed final V3b selection*.
- **Executed Phase5 V3b M2:** ranks the seven V3 candidates per provider by common N100 public-I1 **RMSE** and retains ranks 1–3, *not* the Phase4 diversity/compatibility portfolio. Every provider's M1 model is now **included as rank 1** in its M2 provider portfolio. Cartesian support: 27 joint combinations, equal weights 1/27; 100 graph trajectories per joint member, total **2700** graph trajectories per cell. Its finite member min-max envelope is purely descriptive, not a confidence interval.
- **Critical caveat:** V3b has **no hard I1 fit-compatibility gate**. Calling the three selected models (or all seven V3 candidates used by M3) “I1-compatible” without a declared tolerance, calibration rule or validation is stronger than the operational definition. They are **candidate fits to I1**, with measurable residual losses.
- Phase6 uses another M2-family variant, again with 27 equally weighted joint models, but candidate selection follows a 256-trial, 64 Sobol +192 TPE, Top24 N100 rescore protocol with a loss determined by I1-strong or I2 variant.

**Disposition:** retain the equal-weight Cartesian formula but never describe all M2 runs as the *same frozen diverse compatible ensemble*. Explicitly document whether M1 is part of M2's support and whether model membership was compatibility-gated.

## 5. Pilot M3 and Phase5 V3b FULL343 differ in candidate bank and graph support

**Sources:** \`phase4/config_phase4_m3_v4_dominant_mass_graph_v1.json\`; \`phase4/m3_lambda_cv_v3.py\`; \`phase5/phase5_reconstruction_v3_selection.py\`; \`phase5/config_phase5_provider_reconstruction_v3b.json\`; \`phase5/config_phase5_graph_prediction_v3b_fullsupport.json\`; \`phase5/run_phase5_graph_prediction_v3b_fullsupport.py::_m3_predictions\`.

### Phase4 final pilot M3-v4
- The 48-provider-candidate support came from the exploratory LHS-derived bank, not the V3 seven-fits search.
- A public-I1-only blocked CV process selected **lambda 30** for Jeffreys-smoothed Bernoulli-KL Gibbs weights (the earlier v2 beta=5 stage is distinct development provenance).
- Product weights over provider candidates define an independent *inferred-model* measure on \(48^3\) Cartesian triples; a **dominant Top14** subset with cumulative mass about .999174 is retained, renormalized and simulated. Operating budgets B1400 and B2000 correspond to total graph trajectories per pilot query bank, reused across all query cells.
- The finite-support omitted-mass bound \(1-m\) compares the **truncated Gibbs model expectation** with the full **finite Gibbs model expectation**; it says nothing about error relative to the true graph.

### Phase5 V3/V3b and FULL343
- Candidate support changes to **7 independently searched fits/provider**, common N100 public-I1 rescore, with provider KL-Gibbs weights at lambda 30. For each provider,
  \[
  D_{pj} = K^{-1}\sum_{k=1}^{K} D_{\rm KL}(\mathrm{Ber}(\widetilde u_{pk})\Vert\mathrm{Ber}(\widetilde q_{pjk})),\qquad
  w_{pj} \propto \exp(-30D_{pj}),
  \]
  with Jeffreys smoothing \((Np+0.5)/(N+1)\) and the frozen number of public observations.
- Form **343 joint triples** with \(W_{abc}=w_{Aa}w_{Bb}w_{Cc}\), rank by product weight, and simulate *all 343* under a total graph budget of B1400. Initialize one trajectory/member then greedily allocate others by \(W_j^2/[N_j(N_j+1)]\).
- The **pre-graph-WB full-support revision** superseded the initial registered Top14 approximation because pre-execution retained mass was only ~0.552 for P1 (P3 ~0.962, P4 ~0.867). It did not change candidate weights or select using graph-WB accuracy. Thus this is a **documented method change before final graph outcome reading**, not evidence that the original planned algorithm was evaluated unchanged.
- Primary \(\widehat\sigma_G\) is \(\sum_{j=1}^{343}W_j\widehat\sigma_{G,j}\); Top1, Top3, Top14 are nested diagnostics from the **same** graph ledgers but with their own effective budgets. There is no model-support truncation for FULL343 **relative to the chosen 343-member distribution**. That is not zero error to reality.
- **M3_TOP1 is not definitionally M1**: M1 picks lowest provider I1 RMSE, whereas M3 TOP1 ranks highest product of *KL-Gibbs* weights. Candidate identities may happen to coincide in particular worlds, but equality cannot be assumed or used as causal evidence.
- The product over *provider-model weights* does **not** assume graph response-time independence after composition. Given one joint parameter triple, the native graph simulator still couples requests, queues, branch dependencies and arrival histories.

### Probability and precision boundaries
- Gibbs weights are **heuristic loss-derived plausibility weights**, not a calibrated posterior, an objectively identified prior over providers or a certificate of physical compatibility.
- Monte Carlo variance \(\sum_j W_j^2 p_j(1-p_j)/N_j\) and conservative bound \(\tfrac14\sum_j W_j^2/N_j\) concern **numerical error conditional on the selected weighted model distribution and independent per-member seed streams**. They exclude candidate-bank adequacy, provider-reconstruction bias, I1 observation noise and graph-to-reality fidelity.
- Pilot M3 B1400 graph trajectory cost is ~48.1% lower than Phase4 M2 B2700 **only if comparing graph-propagation trajectory counts**. Total cost includes provider candidate generation/rescoring and varies across method versions. Phase5's M1/M2/M3 graph budgets 100/2700/1400 are **not cost matched**.

**Disposition:** preserve Gibbs-weight and finite-support math with exact version tags; remove “probability of true model,” unqualified “posterior,” “confidence”, “guarantee,” or model-count-based superiority assertions.

## 6. Phase6 \`I1strong/I2a/I2b × M2\` is not merely an interface swap

**Sources:** \`phase6/PHASE6_I1_STRONG_MATCHED_CONTROL_PROTOCOL_2026-10-08.md\`; \`phase6/PHASE6_I2A_FULL_SPECTRUM_RECONSTRUCTION_PROTOCOL_2026-10-08.md\`; \`phase6/PHASE6_I2B_PUBLIC_REPRESENTATION_PROTOCOL_2026-10-09.md\`; \`phase6/run_phase6_i2bv4_six_way_matched_evaluation.py\`.

- Matched P4/G_SEQPAR runs fix the search architecture (64 initial Sobol, 192 TPE, common N25 search and N100 rescore banks, top24 shortlist then top3 provider support), 27-member Cartesian equal-weight graph propagation, and graph budget (2700 trajectories).
- They **change the disclosed representation *and* the corresponding reconstruction objective/loss**. I1strong minimizes complete I1-surface MSE; I2AFS minimizes an integrated discrepancy in I2a's fuller marginal distributions; I2b families use temporal-pair losses with distinct weighting strategies.
- Therefore an outcome difference identifies performance of an **interface-plus-inference-loss pairing under a budget-matched search/graph architecture**. It does not experimentally isolate the causal value of *information quantity alone*, nor conclude that richer information is generally useless.
- This is development evidence on a cell partly used to design I2b variants; do not label all six-way comparisons held-out confirmation.

## 7. Claim updates required in v11_45

| Old manuscript location | Action | Evidence / issue |
|---|---|---|
| §3.2 inverse model set | Define actual *finite generated candidate bank* and method-specific selected subset. Distinguish **explored set** from all hidden processes consistent with I1. | A013, A014, Phase4 and Phase5 source |
| §4 M0 | State same-rho product is predictive heuristic with conditional applicability; not SLA bound. | A020, Phase3 M0 contract/code |
| §4 M1 | Tag as Phase3/4 M1-v2; add Phase5 V3/V3b as a separate instantiation. | A021, V3b selection code |
| §4 M2 | Distinguish diversity-selected Phase4 M2 with M1 anchor excluded from RMSE-ranked Phase5 V3b M2 with M1 anchor included; no hard compatibility gate in V3b. | A022, Phase4 contract, V3b freeze |
| §4 M3 | Tag 48→14 pilot M3 separately from 7→343 Phase5 FULL343; disclose lambda provenance, weight interpretation and unmatched graph budgets. | A023–A025, pilot and FULL343 contracts |
| §5 / Appendix A/B | Report support-truncation and MC widths only as internal numerical/model-ensemble precision. Distinguish M3 Top1 from M1 and do not claim averaging superiority based on pilot. | A027–A028, A037, A041 |
| Discussion | Describe method development chronology, additional gates and failures; no general positive result from pilot or Phase6 interface ranking. | A033–A036, evidence registry E02–E12 |

## 8. Verification level and remaining narrow actions

**Established by static inspection:** the mathematical recipes, query and support conventions, method-version changes, stage order declarations, finite method-support semantics and baseline inclusion/exclusion rules above are explicitly present in source/contract code. Cross-referenced pilot, Phase5, Phase6 and P2 numerical scores were separately validated from saved tables in Step1.

**Not established merely by static inspection:** that each archived provider-selection table is identical to the expected ranking, every joint product and allocation reproduces the frozen weight tables, every raw trajectory was generated by the claimed code revision, or that matched method contrasts identify a single mechanism.

A targeted **read-only local model-support checker** (script \`verify_method_support_v0_1.py\`) can validate identities, weights, support sizes and allocation on existing V3b archives without any scientific simulation. Its outcome must be reviewed separately before marking the provenance fully reconciled.

**Final assessment:** The manuscript's method-family framework stands. The unsafe part is using one unqualified \`M1/M2/M3\` name or one common “I1-compatible” set across historically different operational definitions, followed by generality/certification claims not supported by the evidence.
