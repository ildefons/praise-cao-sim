# KG acquisition-decomposition experiment v1

Development-only retrospective study of joint versus two-stage KG acquisition. The experiment does **not** modify the frozen B1 evidence or manuscript v0.60.

## Policies

- `joint_kg`: choose the maximum KG value over all currently unevaluated method–condition pairs.
- `method_first_adaptive`: select the method with highest mean KG over its available conditions; choose its maximum-KG condition.
- `condition_first_adaptive`: select the condition with highest mean KG over its available methods; choose its maximum-KG method.
- `method_first_uniform`: select the method by mean KG, then a uniform unused condition.
- `condition_first_uniform`: select the condition by mean KG, then a uniform unused method.

Each policy has its own observation history and posterior. First-stage means include only available, unobserved pairs. All policies share initial conditions, budgets, and posterior assumptions from the frozen B1 model.

## Run from Git (no ZIP or copied source files)

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/kg_decomposition_experiment_v1.py \
  --matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --out ~/praise/planb_b1_kg_decomposition_v1
```

Use an active Python environment with NumPy. The input matrix is verified against the SHA-256 freeze in `b1_kg_one_step_v1.py`. The output directory must not already exist to prevent overwriting evidence.

Optional synthetic smoke test (not scientific evidence):

```bash
python first_science/b1/planb_validation/kg_decomposition_experiment_v1.py \
  --smoke-synthetic --repeats 2 --bootstrap 100 \
  --out /tmp/kg_decomposition_synthetic_smoke
```

## Outputs

- `terminals.csv`: each policy's final method, correctness and terminal simple regret.
- `acquisition_diagnostics.csv`: chosen evaluations, one-step KG values, pairwise disagreements, and maximum-minus-mean dispersion bounds.
- `summary.csv`: regret, correctness, KG loss, disagreements and dispersion by policy/budget.
- `paired_vs_joint.csv`: paired within-archive regret differences versus joint KG, with stratified bootstrap intervals (scientific replay only).
- `manifest.json`: input hash, script hash, seed, parameters and output checksums.

The bootstrap is conditional on the one historical catalogue. It does not measure transfer to independent provider worlds. The paired contrasts match initial condition and replicate index; policies do not share a posterior after their evaluations diverge.

## Interpretation

Joint KG maximizes its own one-step score; a two-stage decomposition cannot exceed that one-step maximum. The code verifies that each adaptive decomposition's one-step KG gap is bounded by the maximum within-group (max-minus-mean) dispersion. Whether decompositions improve **terminal** decisions remains an empirical question; do not infer terminal superiority from one-step bounds.

Do not change frozen B1 records or use smoke-test numbers as scientific results.
