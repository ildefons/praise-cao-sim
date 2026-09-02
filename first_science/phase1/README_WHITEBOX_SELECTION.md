# Phase 1 N=10 white-box candidate selection

This post-process converts the existing N=10 white-box atlas into a small reviewable finalist proposal for N=100 confirmation. It is simulator-independent and uses only white-box outputs. I1, M0 and M1 are forbidden from this selection.

## Selection roles

The default battery contains three complementary roles:

- `latency`: latency-first violations dominate cost-first violations;
- `cost`: cost-first violations dominate latency-first violations;
- `mixed`: both latency-first and cost-first violations are observed.

For every role, selection first requires the requested cause structure and then ranks candidates transparently by:

1. distance of `sigma(H*=120)` from target `0.95` (with N=10, the useful bracket is normally `0.9/1.0`);
2. larger number of distinct exact first-violation times;
3. shorter longest plateau fraction;
4. stronger role-specific cause evidence;
5. more observed failures by simulator stop;
6. lower split-half curve supremum disagreement as a final N=10 tie-breaker.

The stored 5-unit survival grid is used only for descriptive curve summaries. Exact event-time diagnostics continue to come from `sigma_curve_diagnostics.py`; the selector does not smooth or redefine sigma.

## Run

From `first_science/phase1` after the N=10 atlas, plots and diagnostics already exist:

```bash
python test_whitebox_candidate_selection.py
python whitebox_candidate_selection.py
```

Expected markers:

```text
PHASE1_WHITEBOX_SELECTION_TESTS_PASS
PHASE1_WHITEBOX_SELECTION_PROPOSAL_PASS
```

Outputs:

```text
results/development_atlas/whitebox_selection/whitebox_candidate_ranking.csv
results/development_atlas/whitebox_selection/selected_whiteboxes_proposal.json
```

The command also prints the proposed latency/cost/mixed white boxes with full-precision physical parameters, A thresholds and discovery diagnostics.

## Freeze gate

`selected_whiteboxes_proposal.json` is **not** automatically copied into the canonical `selected_whiteboxes.json`. Review the proposal once. Only accepted cases are copied exactly into `selected_whiteboxes.json` and its status changed to `FROZEN_FOR_CONFIRMATION`.

After that freeze, N=100 confirmation must:

- use fresh seeds disjoint from the N=10 discovery seeds;
- rerun the exact frozen `(Dbar, delta)` physical cases;
- evaluate the exact frozen `A=(l_max,c_max,q_min)`;
- never recalibrate A on the N=100 traces.
