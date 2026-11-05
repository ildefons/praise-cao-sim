# PRAISE Plan B — sequential validation

**B1 experimental protocol (frozen v1):** [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md). The six agreed principles govern the next budget-conditioned comparison. The B1.2 diagnostic below predates this freeze and is development evidence, not the frozen budget-aware evaluation.

---

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
