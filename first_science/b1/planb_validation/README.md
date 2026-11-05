# PRAISE Plan B — fixed-budget sequential validation

**Design freeze:** [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md)  
**Executable-policy freeze:** [B1_EXECUTABLE_POLICY_FREEZE_V1.md](B1_EXECUTABLE_POLICY_FREEZE_V1.md)  
**WB robustness result freeze:** [B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md)  
**Independent-world validation scope:** [B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md)  
**I1 acquisition timing recovery:** [B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md](B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md)  
**Independent-world and cost source audit:** [B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md](B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md)  
**Local read-only cost inventory:** [audit_independent_world_cost_v0_1.py](audit_independent_world_cost_v0_1.py)  
**Main script:** [b1_budget_comparison_v1.py](b1_budget_comparison_v1.py)  
**Synthetic-only tests:** [test_b1_budget_comparison_v1.py](test_b1_budget_comparison_v1.py)

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
