# Controlled KG tie audit (development)

This is the first diagnostic milestone before considering a two-step Knowledge Gradient extension. It does **not** update the paper or frozen B1 baselines.

## Rationale

The original five-policy replay used policy-specific random streams for ties. Most method-first/condition-first disagreements with joint KG had no meaningful one-step KG loss. We therefore separate policy differences from arbitrary tie resolution before interpreting differences in terminal regret.

## Run from the Git branch

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/kg_controlled_ties_v1.py \
  --matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --out ~/praise/planb_b1_kg_controlled_ties_v1
```

The input matrix SHA-256 is verified by the existing frozen KG loader. This writes only to a new output directory and refuses to overwrite a prior run.

## Design

Three adaptive policies are compared: joint KG, method-first mean-then-max KG and condition-first mean-then-max KG. Each retains an independent posterior and identical seven-observation initial condition.

Two tie-resolution controls:

- `lexicographic`: deterministic, no random draw, **one episode per starting condition**. Descriptive only: repeats would be identical.
- `shared_hash`: stable policy-independent hash-based priorities for identical named choices at a given budget, starting condition, replicate and step. Twenty replicates per start (default). This removes policy-ID-specific random stream variation, but does not force different first-stage aggregation rules to select the same tied action.

Both use tolerance `1e-12` when identifying maxima. The audit reports ties among available KG action scores, selected-versus-joint KG gap, disagreement, reference-best selection, and terminal simple regret.

Generated files: `summary.csv`, `acquisitions.csv`, `terminals.csv`, and `manifest.json`.

Interpretation cautions: these remain repeated replays of a **single fixed** 7×12 outcome catalogue. The shared-hash design controls RNG assignment but is not a causal guarantee that tie effects are eliminated. Compare both controls and avoid making independent-world inference.

## Next gate

If nontrivial one-step ambiguity remains after this audit, sample posterior states with multiple equal-KG available actions for a targeted two-step KG quadrature study. Reserve new provider-world and graph validation for after algorithm choice.
