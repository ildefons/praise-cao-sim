# PRAISE Plan B — fixed-budget sequential validation

**Design freeze:** [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md)  
**Executable-policy freeze:** [B1_EXECUTABLE_POLICY_FREEZE_V1.md](B1_EXECUTABLE_POLICY_FREEZE_V1.md)  
**Main script:** [b1_budget_comparison_v1.py](b1_budget_comparison_v1.py)  
**Synthetic-only tests:** [test_b1_budget_comparison_v1.py](test_b1_budget_comparison_v1.py)

## First: audit and complete the 7×12 matrix

Run in the existing PRAISE Python environment, on branch \`praise-identifiability-feasibility\`:

\`\`\`bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python -m unittest discover -s first_science/b1/planb_validation -p 'test_b1_budget_comparison_v1.py' -v

python first_science/b1/planb_validation/b1_budget_comparison_v1.py \
  --repo . --mode inspect

python first_science/b1/planb_validation/verify_seven_method_matrix_v1.py \
  --repo . --out ~/praise/planb_b1_fixed_budget_v1
\`\`\`

The verifier checks exactly **84 frozen atomic results**, source manifests and file hashes, and published aggregate MAE values. It writes \`seven_method_matrix.csv\` and \`matrix_provenance.json\` **outside the repository**. If anything is missing or inconsistent, it fails instead of silently substituting a five-method or rounded-table experiment. A missing \`b1_pilot_m3_retrospective_v1/evaluation/metrics_retrospective.csv\` is a missing archival source; do not rerun simulator code just to satisfy this gate.

## Second: five predetermined budget comparisons

Only after the seven-method matrix verifies:

\`\`\`bash
python first_science/b1/planb_validation/b1_budget_comparison_v1.py \
  --repo . --mode all \
  --repeats-per-cell 20 --bootstrap 2000 \
  --out ~/praise/planb_b1_fixed_budget_v1
\`\`\`

This runs independent, budget-conditioned episodes for **B = 10, 15, 20, 30, 40** and all four policies: uniform random after common initialization, balanced coverage, previous informed allocation, and the simple budget-aware coverage/top-two policy. With 12 starting cells and 20 independent repetitions per starting cell, there are **240 episodes per policy per budget**.

The final decision is scored with **terminal simple regret** (primary), reference-best selection probability, and regret distribution. Separate per-budget comparisons and a prespecified across-budget contrast against balanced allocation are saved. No simulation is launched, and frozen evidence is not modified.

Outputs in the requested directory:
- \`seven_method_matrix.csv\`: 84 archived cell MAEs
- \`matrix_provenance.json\`: verified frozen sources (matrix stage)
- \`terminal_episodes.csv\`: one terminal decision per independent episode
- \`episode_action_history.csv\`: full revealed-action sequence, retained for later continuation experiments
- \`budget_summary.csv\`: regret, accuracy, tail and bootstrap intervals for every B and policy
- \`paired_regret_contrasts.csv\`: paired bootstrap difference summaries
- \`run_manifest.json\`: code/protocol settings, input file hashes and output file hashes

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
