# Phase 1 N=10 white-box candidate selection

This post-process converts the completed N=10 white-box discovery atlas into a small reviewable finalist proposal for fresh N=100 confirmation. It is simulator-independent and uses only white-box outputs. I1, M0 and M1 are forbidden from this selection.

## Revised nondegeneracy criterion

The former `sigma(H=120) ~= 0.95` finalist target is superseded. `H=120` remains a reporting checkpoint only.

For each exact admissibility region `A=(l_max,c_max,q_min)`, compute the normalized restricted survival area

```text
R(A) = integral_0^Hmax sigma_A(H) dH / Hmax
```

exactly from first-violation times. With censoring at `Hmax`, the empirical estimator is the mean capped first-violation time divided by the horizon width. The stored 5 s reporting grid does not define the area.

The numerical nondegeneracy interval is **configuration data**, not a hard-coded selection target. The current versioned default is:

```text
0.50 <= R_hat_10(A) <= 0.75
```

The interval is a **gate only**. The selector does not optimize toward `0.625` or any other midpoint. A future justified change to the band is a versioned configuration edit; no algorithm rewrite should be needed.

## Selection roles

After the common area gate, candidates are classified/ranked as:

- `latency`: latency-first violations clearly dominate cost-first violations;
- `cost`: cost-first violations clearly dominate latency-first violations;
- `mixed`: both latency-first and cost-first violations have material support and limited imbalance.

Role evidence is primary. Exact-event temporal richness (unique first-violation times, plateau fraction and maximum empirical jump) is secondary ranking information. There is no longer a role-independent hard gate requiring four failures, four unique times or four stored sigma levels.

When all three roles are available in one physical setting, the selector prefers a matched physical regime. Otherwise it returns the best distinct role candidates and leaves the final scientific review explicit.

## Run on the existing discovery results

The existing `25 x N=10` physical trajectories remain valid. No AICon/YAFS rerun is required solely because the selection criterion changed.

From `first_science/phase1`:

```bash
python test_exact_auc_candidate_metrics.py
python test_whitebox_candidate_selection.py
python test_scientific_discovery_configuration.py
```

Then compute exact metrics for **all distinct A regions** in the already augmented discovery result set:

```bash
python exact_auc_candidate_metrics.py \
  --results results/scientific_discovery_v1_full_domain_ar
```

The implementation deduplicates numerically identical `A` regions and precomputes threshold-event times per trajectory, avoiding a slow request-by-request rescan for every region.

Then select the proposal:

```bash
python whitebox_candidate_selection.py \
  --results results/scientific_discovery_v1_full_domain_ar
```

Expected markers:

```text
PHASE1_EXACT_AUC_CANDIDATE_METRICS_PASS
PHASE1_WHITEBOX_AUC_SELECTION_PROPOSAL_PASS
```

Outputs:

```text
results/scientific_discovery_v1_full_domain_ar/whitebox_selection/auc_candidate_metrics.csv
results/scientific_discovery_v1_full_domain_ar/whitebox_selection/whitebox_candidate_ranking.csv
results/scientific_discovery_v1_full_domain_ar/whitebox_selection/selected_whiteboxes_proposal.json
```

If a role is absent, diagnose it without changing the band:

```bash
python diagnose_whitebox_selection.py
```

## Freeze and confirmation gate

The proposal is not automatically copied into `selected_whiteboxes.json`. Review the exact physical parameters, `A`, N=10 area and failure-mechanism evidence once.

Only accepted cases are frozen for confirmation. Final N=100 confirmation must:

- use a **new** seed bank disjoint from development seeds `1000..1009`, discovery seeds `2000..2009`, and the already inspected exploratory N=100 seeds `3000..3099`;
- rerun the exact frozen physical case(s);
- evaluate the exact frozen `A=(l_max,c_max,q_min)`;
- recompute exact `R_hat_100(A)`, sigma curves and first-violation causes;
- never recalibrate `A` on the N=100 traces.
