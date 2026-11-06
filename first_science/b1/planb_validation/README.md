# PRAISE Plan B — fixed-budget sequential validation

**Literature-method compatibility (KG, BayesGap, UGapE, TTTS, elimination, linear design):** [B1_LITERATURE_METHOD_COMPATIBILITY_AUDIT_V0_1.md](B1_LITERATURE_METHOD_COMPATIBILITY_AUDIT_V0_1.md)  
**Fixed-budget best-arm / active-model-selection literature:** [B1_FIXED_BUDGET_BAI_LITERATURE_POSITIONING_2026-11-05.md](B1_FIXED_BUDGET_BAI_LITERATURE_POSITIONING_2026-11-05.md)  
**Consolidated scientific evidence report:** [B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md](B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md)  
**Complete four-policy numerical appendix:** [B1_CONSOLIDATED_NUMERIC_APPENDIX_V0_1.md](B1_CONSOLIDATED_NUMERIC_APPENDIX_V0_1.md)  
**Knowledge Gradient benchmark freeze:** [B1_KG_ONE_STEP_SPECIFICATION_V1.md](B1_KG_ONE_STEP_SPECIFICATION_V1.md)  
**KG implementation / synthetic tests:** [b1_kg_one_step_v1.py](b1_kg_one_step_v1.py), [test_b1_kg_one_step_v1.py](test_b1_kg_one_step_v1.py)  
**All five regret–budget curves with 95% bootstrap error bars:** [figure and provenance](figures/README.md); [vector plot](figures/b1_five_policy_regret_vs_budget_ci_v1.svg); [verified plotting data](figures/b1_five_policy_regret_with_bootstrap_ci_v1.csv); [read-only plotting script](plot_b1_regret_five_policies_v1.py)  
**Seven-policy reconstruction plot (read-only, pending local run):** [plot_b1_regret_seven_policies_v1.py](plot_b1_regret_seven_policies_v1.py). Adds KG-uniform and Top2-uniform reconstructed variants to the preserved original five policies. **Not** a verified exact replication of the 6 November ablation; see documented arm-selection differences below.  
**Audited retrospective KG result:** [B1_KG_SUPPLEMENTARY_DEVELOPMENT_RESULT_V1.md](B1_KG_SUPPLEMENTARY_DEVELOPMENT_RESULT_V1.md)  
**B1 baseline-preservation decision:** [B1_BASELINE_PRESERVATION_AND_AGENDA_BOUNDARY_2026-11-05.md](B1_BASELINE_PRESERVATION_AND_AGENDA_BOUNDARY_2026-11-05.md)  
**Design freeze:** [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md)  
**Executable-policy freeze:** [B1_EXECUTABLE_POLICY_FREEZE_V1.md](B1_EXECUTABLE_POLICY_FREEZE_V1.md)  
**WB robustness result freeze:** [B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md)  
**Independent-world validation scope:** [B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md)  
**I1 acquisition timing recovery:** [B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md](B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md)  
**Independent-world and cost source audit:** [B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md](B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md)  
**Local read-only cost inventory:** [audit_independent_world_cost_v0_1.py](audit_independent_world_cost_v0_1.py)  
**Main script:** [b1_budget_comparison_v1.py](b1_budget_comparison_v1.py)  
**Synthetic-only tests:** [test_b1_budget_comparison_v1.py](test_b1_budget_comparison_v1.py)

**Completed controlled condition-selection results (6 November 2026):** [scientific report, paired contrasts and both archived figures](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md). **Main figure:** [seven-policy matched plot](results/controlled_condition_ablation_v1/b1_controlled_seven_policy_regret_vs_budget_ci_v1.svg); **context figure:** [nine policies including the original KG/Top2 references](results/controlled_condition_ablation_v1/b1_nine_policy_with_historical_refs_ci_v1.svg). In the separately defined two-stage families, adaptive vs uniform reduces across-budget mean regret by **26.5% for KG** and **22.8% for Top2**. Paired uniform-minus-adaptive differences: KG +0.002121 [0.001281, 0.002960], Top2 +0.001980 [0.001202, 0.002819] (95% within-archive stratified bootstrap). At B=10, KG's observed difference reverses, with an interval including zero. These are policy-specific retrospective comparisons, **not** an exact isolation of condition sampling in the original joint-acquisition policies. All original frozen outputs remain preserved.  

## Controlled two-stage KG/Top2 condition-selection ablation (v1)

**Code:** [b1_condition_selection_controlled_v1.py](b1_condition_selection_controlled_v1.py) and [plot_b1_condition_selection_controlled_v1.py](plot_b1_condition_selection_controlled_v1.py).

**New policy definitions, not the original single-stage KG/Top2 implementations.** Both variants within each family use the exact same predictor selection function given the current observed history. For KG, the arm is chosen by the mean one-step KG score over its remaining conditions. For Top2, the frozen 50%-coverage schedule is retained: the coverage-phase arm is one with the fewest observations, then the decision-phase arm is the top-two candidate with the highest mean variance reduction over its remaining conditions. During coverage, adaptive conditions use the original balanced provider/graph score for the chosen arm. For subsequent Top2 allocation and all KG allocations, adaptive conditions maximize the original condition-specific acquisition criterion. Uniform conditions are drawn uniformly without replacement among the selected arm's unevaluated conditions. Both variants retain the original seven initial evaluations, posterior model and posterior-mean final choice.

**Interpretation:** the arm-choice function is identical within a family, but histories can diverge following different condition choices, so later selected arms need not be identical. This is a controlled **whole-policy** condition-choice comparison, not a forced identical-arm-path direct-effect analysis. The original five-policy results and plots remain intact. The 6 November retrospective earlier reconstruction is a different exploratory variant and must not be silently pooled with these results.

Run the controlled experiment locally using the hashed frozen matrix (4 policies × 5 budgets × 240 episodes = **4,800 episodes; 110,400 logged evaluations**) and 2,000 stratified bootstrap resamples:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python first_science/b1/planb_validation/b1_condition_selection_controlled_v1.py \
  --matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --out ~/praise/planb_b1_controlled_condition_ablation_v1
```

After **B1_CONTROLLED_TWO_STAGE_CONDITION_ABLATION_PASS**, generate both figures:

```bash
python first_science/b1/planb_validation/plot_b1_condition_selection_controlled_v1.py \
  --original-summary ~/praise/planb_b1_fixed_budget_v1/budget_summary.csv \
  --kg-summary ~/praise/planb_b1_kg_reproduced_20261106/kg_budget_summary.csv \
  --controlled-summary ~/praise/planb_b1_controlled_condition_ablation_v1/controlled_budget_summary.csv \
  --out ~/praise/planb_b1_controlled_condition_figures_v1
```

The main seven-policy plot contains the **three other original benchmarks** (Random, Balanced, Informed), plus the four new matched KG/Top2 variants. The nine-policy reference plot additionally shows the **two original joint-action KG/Top2 policies** as separate dotted reference curves, not as members of the matched ablation. Each curve has the same bootstrap interval design: 240 episodes per policy/budget, 2,000 stratified percentile draws. Original reference summaries remain hash-checked and untouched.

**Status (6 November 2026):** local execution completed; summaries, paired contrasts, SVG figures and provenance manifests committed at `results/controlled_condition_ablation_v1/`. [Reviewed scientific interpretation](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md). This remains retrospective evidence on a historical fixed 7×12 matrix, not independent-world confirmation; episode-level and action-history CSVs remain outside Git and are recorded by hashes in the committed manifest.

---

## November 6 uniform-condition reconstruction (exploratory; original five policies unchanged)

The repository contains [b1_uniform_condition_replay_v1.py](b1_uniform_condition_replay_v1.py), a separately versioned retrospective replay using the frozen 7×12 matrix and fixed Gaussian posterior. Its two policies sample an unobserved condition uniformly *after* choosing an arm. This is **not** the recovered original November 6 experiment: KG selects its arm by the maximum available condition-wise KG acquisition score; Top2's initial coverage phase balances arm counts, not the original provider–graph coverage score. Accordingly, differences from the original adaptive KG/Top2 baselines combine changes in arm and condition policies and **must not be interpreted as an isolated causal effect of condition adaptivity**.

The 6 November local replay was reported to pass with 2,400 episodes and 55,200 action records. Across five budgets, reconstructed uniform-minus-adaptive mean regret was +0.000942 for KG (95% paired bootstrap interval [0.000187, 0.001737]) and +0.002773 for Top2 ([0.001910, 0.003626]). These are **reconstruction** results, conditional on the historical archive, not independent-world or confirmatory evidence. These summary values are transcribed from the local replay output; the full episode files are not committed.

With existing local sources, render all seven policies with **the same 240 episodes/policy/budget and 2,000-replicate stratified percentile-bootstrap interval procedure**:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python first_science/b1/planb_validation/plot_b1_regret_seven_policies_v1.py \
  --original-summary ~/praise/planb_b1_fixed_budget_v1/budget_summary.csv \
  --kg-summary ~/praise/planb_b1_kg_reproduced_20261106/kg_budget_summary.csv \
  --uniform-summary ~/praise/planb_b1_uniform_reproduced_20261106/uniform_budget_summary.csv \
  --out ~/praise/planb_b1_seven_policy_reconstruction_figures_v1
```

The plotting script hash-checks the two frozen summaries, verifies all 35 policy/budget rows, refuses overwrites, reads existing bootstrap intervals without recomputing them and emits PNG, SVG, CSV and a provenance manifest. It does not change the five-policy figure or frozen result files. The revised **controlled ablation protocol remains open** until arm-choice behavior can be held fixed or an explicit estimand for the joint two-stage policy is frozen.

---

## First: audit and complete the 7×12 matrix

Run in the existing PRAISE Python environment, on branch `praise-identifiability-feasibility`:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python -m unittest discover -s first_science/b1/planb_validation -p 'test_b1_budget_comparison_v1.py' -v

python first_science/b1/planb_validation/b1_budget_comparison_v1.py \
  --repo . --mode inspect

python first_science/b1/planb_validation/verify_seven_method_matrix_v1.py \
  --repo . --out ~/praise/planb_b1_fixed_budget_v1
```

The verifier checks exactly **84 frozen atomic results**, source manifests and file hashes, and published aggregate MAE values. It writes `seven_method_matrix.csv` and `matrix_provenance.json` **outside the repository**. If anything is missing or inconsistent, it fails instead of silently substituting a five-method or rounded-table experiment. A missing `b1_pilot_m3_retrospective_v1/evaluation/metrics_retrospective.csv` is a missing archival source; do not rerun simulator code just to satisfy this gate.

## Second: five predetermined budget comparisons

Only after the seven-method matrix verifies:

```bash
python first_science/b1/planb_validation/b1_budget_comparison_v1.py \
  --repo . --mode all \
  --repeats-per-cell 20 --bootstrap 2000 \
  --out ~/praise/planb_b1_fixed_budget_v1
```

This runs independent, budget-conditioned episodes for **B = 10, 15, 20, 30, 40** and all four policies: uniform random after common initialization, balanced coverage, previous informed allocation, and the simple budget-aware coverage/top-two policy. With 12 starting cells and 20 independent repetitions per starting cell, there are **240 episodes per policy per budget**.

The final decision is scored with **terminal simple regret** (primary), reference-best selection probability, and regret distribution. Separate per-budget comparisons and a prespecified across-budget contrast against balanced allocation are saved. No simulation is launched, and frozen evidence is not modified.

Outputs in the requested directory:
- `seven_method_matrix.csv`: 84 archived cell MAEs
- `matrix_provenance.json`: verified frozen sources (matrix stage)
- `terminal_episodes.csv`: one terminal decision per independent episode
- `episode_action_history.csv`: full revealed-action sequence, retained for later continuation experiments
- `budget_summary.csv`: regret, accuracy, tail and bootstrap intervals for every B and policy
- `paired_regret_contrasts.csv`: paired bootstrap difference summaries
- `run_manifest.json`: code/protocol settings, input file hashes and output file hashes

## Third: white-box reference uncertainty (no policy changes)

**Frozen protocol:** [B1_WB_REFERENCE_ROBUSTNESS_PROTOCOL_V1.md](B1_WB_REFERENCE_ROBUSTNESS_PROTOCOL_V1.md)  
**Script:** [b1_wb_reference_robustness_v1.py](b1_wb_reference_robustness_v1.py)  
**Tests:** [test_b1_wb_reference_robustness_v1.py](test_b1_wb_reference_robustness_v1.py)

Do not rerun or change B1 v1 policy settings. With the existing completed seven-method replay outputs:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python -m unittest discover -s first_science/b1/planb_validation -p 'test_b1_wb_reference_robustness_v1.py' -v

python first_science/b1/planb_validation/b1_wb_reference_robustness_v1.py \
  --repo . \
  --b1-outputs ~/praise/planb_b1_fixed_budget_v1 \
  --out ~/praise/planb_b1_wb_robustness_v1 \
  --reference-reps 300 \
  --split-pairs 4 \
  --split-repeats 2
```

The audit expects the binary outcomes and metadata created by the existing Phase-5 reference bootstrap at:
`first_science/phase5/results/06_evaluation_v3b_fullsupport/bootstrap_reference/` (files `wb_primary_trajectory_outcomes.npz` and `wb_primary_outcome_columns.csv`). If this cache is missing, **append `--reconstruct-outcomes`** to derive those files from the frozen white-box ledgers **outside the repository**, without simulation or overwriting existing results.

The script validates all seven original pointwise prediction files using frozen SHA-256 manifests; independently reconstructs 84 cell MAEs; and resamples entire WB trajectories, never individual correlated query rows. In the split stress test it reruns the **unchanged** B1 policies, giving half the WB trajectories to the allocation decisions and scoring on the disjoint half.

Outputs appear only under the chosen `--out` directory: `WB_REFERENCE_ROBUSTNESS_REPORT.md`, `reference_winner_frequency.csv`, `reference_sensitivity_by_budget.csv`, `disjoint_half_paired_regret.csv`, and a hashed `audit_manifest.json`.

**Interpretation:** this tests finite-white-box-reference uncertainty *within the same 12 historical cases*. It is neither a new provider-world experiment nor a new claim about algorithm novelty. A positive screening outcome justifies planning independent-world validation; **no new simulations** are authorized by this stage.

---

## Fourth: source and local cost-feasibility inventory (no fresh simulations)

**Source findings:** [B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md](B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md). New world generation is **not authorized** by this audit; the original four worlds were fixed design points.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python -m unittest discover -s first_science/b1/planb_validation \
  -p 'test_audit_independent_world_cost_v0_1.py' -v

python first_science/b1/planb_validation/audit_independent_world_cost_v0_1.py \
  --repo . \
  --out ~/praise/planb_b1_world_cost_feasibility_v0_1
```

Review `WORLD_COST_FEASIBILITY_AUDIT.md`, `historical_stage_cost_summary.csv`, `historical_manifest_costs.csv` and `audit_manifest.json`. The source-contract trajectory floor is 129,600 graph trajectories for a complete 7×12 battery including WB. Local stage manifests provide elapsed time only where explicitly recorded; missing original-style/fixed-CV method-specific times are **unknown**, not zero. Do not interpret summed parallel stage durations as full-project makespan.

---

**Second-pass measured graph-stage recovery:** [B1_GRAPH_STAGE_TIMING_RECOVERY_REVIEW_2026-11-05.md](B1_GRAPH_STAGE_TIMING_RECOVERY_REVIEW_2026-11-05.md). The archived logs contain `time.perf_counter()` elapsed readings for **all 24 fixed-CV Top14/Top1 graph execution stages**, totaling **596.3 minutes (9.9383 h)**. This is **not** the fixed-CV full-command wall time: merging and postprocessing are excluded. The initial v1 log extractor found zero *shell* `real` markers but kept these stage timings in `log_timing_evidence.csv`.  

## Fifth: recover historical Top14/Top1 graph timings (no simulations)

**Recovered original-style terminal measurements:** [B1_ORIGINAL_GRAPH_TIMING_RECOVERY_2026-11-05.md](B1_ORIGINAL_GRAPH_TIMING_RECOVERY_2026-11-05.md). The original-style Top14+Top1 combined graph battery required **14h57m39.671s measured across three invocations** (two cells separately, then a replay reusing them); this is not a CPU-hour value. Fixed-CV combined wall time has **not yet been measured**.

Use only the read-only log extractor:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python -m unittest discover -s first_science/b1/planb_validation \
  -p 'test_recover_graph_timing_from_logs_v1.py' -v
python first_science/b1/planb_validation/recover_graph_timing_from_logs_v1.py \
  --repo . --out ~/praise/planb_b1_archival_graph_timing_v1
```

It searches existing *project-local* log files and reads original/fixed-CV prediction manifests, without executing any scientific simulation. For a historical log stored elsewhere, append `--log /absolute/path/to/log`. It records exact measured shell-time markers separately from progress reports and completion-time gaps. The output `ARCHIVAL_TIMING_RECOVERY.md` summarizes what the logs actually support; `log_timing_evidence.csv` contains exact source lines and `manifest_completion_gaps_NOT_RUNTIME.csv` contains explicitly **non-measured** completion gaps. If a fixed-CV log contains no timestamp or `time` output, it cannot establish fixed-CV elapsed hours on its own. Do not use filesystem modification times as measurements.

---

## Sixth: prospective provider-world and Step-0 design (DRAFT ONLY)

**Scientific review draft:** [B1_PROSPECTIVE_WORLD_STEP0_DESIGN_V0_1.md](B1_PROSPECTIVE_WORLD_STEP0_DESIGN_V0_1.md)  
**Proposed ranges and recruitment contract:** [B1_WORLD_GENERATOR_DRAFT_V0_1.json](B1_WORLD_GENERATOR_DRAFT_V0_1.json)  
**Dry-run generator:** [preview_new_worlds_v0_1.py](preview_new_worlds_v0_1.py).

This sampler changes **nothing** in frozen B1 v1. It only materializes a deterministic, isolated preview of *unassessed* physical Gamma provider-world candidates under three role strata and a four-graph-eligibility policy. It does not call Phase-5 I1, Step-0, reconstruction, graph simulation, WB or any acquisition policy. Its output contains **private** generating parameters, never to be exposed to the controller.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python -m unittest discover -s first_science/b1/planb_validation \
  -p 'test_preview_new_worlds_v0_1.py' -v

python first_science/b1/planb_validation/preview_new_worlds_v0_1.py \
  --repo . \
  --out ~/praise/planb_b1_newworld_preview_v0_1
```

The script refuses to overwrite an existing output directory. Review `PREVIEW_ONLY.md`, `PRIVATE_world_candidates.csv`, and `dry_run_manifest.json`. The preview contains 3 proposed batteries × 3 roles × up to 4 attempts = 36 *NOT_RUN* candidates; these are **not** 36 accepted worlds or a confirmatory sample size. Before *any* new simulations, the independently versioned Phase-5 new-world adapter, Step-0 eligibility and attrition rules, and confirmatory sample-size/cost plan must be reviewed and frozen.

---

## Interpretation

The fixed 12-cell PRAISE archive has only three distinct provider worlds. Replaying randomized allocation many times is essential for estimating sequence variability, but does **not** create new independent worlds. This is a **retrospective methodology development test**, not a prospective generalization result. Evaluation-count budgets do **not** imply equal runtime cost among algorithms. We deliberately do not tune policy switching fractions to the current archive's observed performance.

---

## Earlier B1.2 diagnostic (exploratory)

# PRAISE Plan B — Gate B1.2 early-budget diagnostic

This read-only diagnostic reconstructs the Gate 1 policies' selected `(algorithm, world, graph)` actions and tests whether their early validation accuracy is associated with world/graph coverage. It uses the existing five-method replay results; it **does not run simulations or change frozen evidence**.

## Prerequisites
- The original Gate 1 script already extracted to `~/praise/planb_gate1/planb_gate1.py`.
- The prior five-method replay outputs in `~/praise/planb_gate1_local_outputs`.
- Python with NumPy and pandas (Matplotlib and tabulate optional).

## Run

From your PRAISE checkout on branch `praise-identifiability-feasibility`:

```bash
git pull --ff-only origin praise-identifiability-feasibility
python first_science/b1/planb_validation/diagnose_early_v1.py \
  --gate ~/praise/planb_gate1/planb_gate1.py \
  --results ~/praise/planb_gate1_local_outputs \
  --out ~/praise/planb_gate1_early_diagnostic \
  --budgets 8,14,17
```

The diagnostic verifies each reconstructed recommendation against the archived replay trace. Any mismatch aborts before reporting coverage. It writes `B1_2_DIAGNOSTIC.md`, a plot (if Matplotlib is installed), and detailed CSV tables in the specified output directory.

## Limits

This is a retrospective, five-method, fixed-domain diagnostic. The 180 replay trials are not independent provider worlds. Reference MAEs are historical and not calculated with disjoint white-box trajectory halves; observed associations between action choices and selection accuracy are not causal evidence. Do not treat this as a full validation of a new acquisition policy.
