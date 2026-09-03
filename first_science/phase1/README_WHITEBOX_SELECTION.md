# Phase 1 N=10 white-box candidate selection — SLA semantics

The current Phase-1 selector uses the frozen SLA quantity

```text
sigma_G(A,H,rho*) = P(c_G(A,H) >= rho*)
rho* = 0.95
accounting window = cumulative [0,H] from prescribed t=0
```

The old first-passage AR generator and first-violation AUC scripts are retained only for provenance/reproducibility. They are **not** the current finalist-selection substrate.

## Why the AR generator changed

The original AR candidates were generated around first-passage critical values. After sigma was reopened and redefined as cumulative SLA-compliance probability, diagnostics showed that cost-dominant and mixed mechanisms existed in the sealed N=10 traces but were almost always far above the SLA-area gate. The old threshold geometry was therefore unsuitable for the new 5% violation-budget semantics.

The physical `25 x N=10` traces remain valid. No AICon/YAFS rerun is required.

## Current SLA-native AR generator

`config_phase1_sla_ar_generator_v1.json` freezes empirical request-level quantiles

```text
{0.90, 0.925, 0.95, 0.975, 0.99}
```

using `higher` empirical quantiles pooled across the ten sealed trajectories of each physical setting. `q_min=x=0.5` remains frozen.

For every physical setting, the generator creates three families:

```text
L quantile x loose C          latency-pressure axis
loose L x C quantile          cost-pressure axis
L quantile x C quantile       crossed L/C pressure
```

Loose latency is `simulation_stop_time + epsilon`, so no latency deadline can bind within the benchmark horizon. Loose cost is above every finite observed request cost. M0 and M1 are forbidden from AR generation.

The generator does not use the SLA-area midpoint or M0/M1 performance to tune A.

## Current N=10 workflow

From `first_science/phase1`:

```bash
python test_sla_native_admissibility_regions.py
python test_sla_revision_smoke.py
python test_presearch_contract.py
```

Generate the new AR candidate substrate from the sealed physical ledgers:

```bash
python generate_sla_native_admissibility_regions.py \
  --results results/scientific_discovery_v1_full_domain_ar
```

Expected marker:

```text
PHASE1_SLA_NATIVE_AR_GENERATOR_PASS
```

Then calculate the SLA-compliance metrics on those new A candidates:

```bash
python sla_native_candidate_metrics.py \
  --results results/scientific_discovery_v1_full_domain_ar
```

Expected marker:

```text
PHASE1_SLA_NATIVE_CANDIDATE_METRICS_PASS
```

Then select and plot the proposed latency/cost/mixed finalists:

```bash
python whitebox_candidate_selection.py \
  --results results/scientific_discovery_v1_full_domain_ar
```

Expected marker if all three roles are available:

```text
PHASE1_WHITEBOX_SLA_SELECTION_PROPOSAL_PASS
```

Key outputs are under:

```text
results/scientific_discovery_v1_full_domain_ar/whitebox_selection/
```

including:

```text
sla_native_admissibility_regions.csv
sla_candidate_metrics.csv
whitebox_candidate_ranking.csv
selected_whiteboxes_proposal.json
selected_candidate_request_decisions.csv
selected_candidate_trajectory_compliance_curves.csv
selected_candidate_sigma_curves.csv
selected_candidate_exact_sigma_steps.csv
n10_selected_sla_sigma_curves.png
```

The normalized SLA-compliance-area gate remains

```text
0.50 <= R_0.95(A) <= 0.75
```

and remains a gate only; there is no optimization toward its midpoint.

## Freeze and N=100 confirmation

Do not automatically copy the proposal into `selected_whiteboxes.json`. First inspect the three exact N=10 sigma curves and request-level L/C failure evidence. Once the exact physical setting(s), A values, rho=0.95, and cumulative [0,H] semantics are accepted, freeze them once.

Only then assign a new N=100 seed bank disjoint from development `1000..1009`, discovery `2000..2009`, and inspected exploratory `3000..3099`. N=100 confirms the frozen cases and must not recalibrate A or rho.
