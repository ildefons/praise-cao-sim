# PRAISE/CAO Phase-5 prospective analysis addendum

**Status:** FROZEN BEFORE SCIENTIFIC EXECUTION  
**Date:** 2 October 2026  
**Role:** analysis-only addendum to the already frozen Phase-5 battery  
**Machine-readable companion:** `config_phase5_analysis_addendum_v1.json`

This addendum does **not** change any provider world, graph, workload, query, public-I1 card, method, reconstruction rule, support size, simulation budget, seed bank, Step-0 gate, or final white-box sample size. It only predeclares two analyses motivated by the closed pilot before any Phase-5 scientific result is opened.

## A1. Directional error and optimistic-bias audit

The pilot showed that optimism is not unique to M1. M1 has a much larger positive bias that grows from Easy to Mid to Stress, while M3 reduces but does not eliminate positive signed error relative to the finite white-box reference.

Phase 5 therefore treats error direction as a first-class confirmatory diagnostic rather than reporting only unsigned error.

For every method, report signed bias

[
\mathrm{Bias}=\frac{1}{n}\sum_q(\hat\sigma_q-\hat\sigma_q^{WB})
]

together with MAE/RMSE. Required directional summaries are:

- whole battery;
- provider world P;
- graph G;
- Easy/Mid/Stress;
- P x G;
- G x regime;
- P x regime;
- rho x regime.

For beta = 0.90, and secondarily beta = 0.80 and 0.95, report false accepts and false rejects separately on the same WB-certain subset already defined by the core protocol.

### White-box trajectory-cluster bootstrap for bias

Finite-N white-box fluctuation is separated from method error by a reference-only clustered bootstrap:

- final method predictions remain fixed;
- resampling unit is the complete final-WB trajectory index;
- all query/horizon outcomes generated from one physical WB trajectory stay together;
- when common random numbers reuse the same trajectory index across physical cells, that index is resampled jointly across those cells;
- 10,000 bootstrap replicates;
- analysis RNG seed 2026100201;
- report point bias and percentile 95% interval;
- report the same primary scopes listed above.

This interval isolates uncertainty from the finite final-WB reference only. It is not a joint confidence interval over method Monte Carlo error, model ambiguity, reconstruction uncertainty, or method construction.

No bias value or interval is a pass/fail gate and no directional result may trigger retuning or repair.

## A2. Prospective topology-sensitivity hypothesis

The closed ParAll pilot suggests a mechanism hypothesis: graph-level prediction may remain accurate even when some provider parameters are poorly reconstructed if the composed SLA quantity is relatively insensitive to those parameters.

In the pilot, provider C is the highest-utilization branch and M3-Top1 recovers its service-time scale and CV much more closely than those of A and B. Because ParAll latency is governed by a maximum, errors in faster branches may be partly masked. This is a hypothesis, not a pilot conclusion: total SLA cost is additive and queueing or graph-induced arrival changes can alter which provider or SLA component dominates.

The already frozen Phase-5 graphs test this without any design change:

- G_PAR: max-type exposure of A, B, C latency;
- G_SEQ: additive exposure of A, B, C latency;
- G_SEQPAR: A enters additively before max(B,C);
- G_PARSEQ: max(A, B+C).

The prospective mechanism expectation is:

> If masking of poorly reconstructed non-dominant providers materially explains the pilot, prediction error and/or optimistic bias should become more sensitive when graph structure makes those provider contributions additive or otherwise structurally exposed. This topology effect should be most visible in heterogeneous worlds P2/P4 and need not appear in the symmetric controls P1/P3.

This is an interpretive hypothesis, not a required ordering or success criterion. G_SEQ is not assumed to be worse in advance. Either persistence or failure of prediction is scientifically informative.

Required analysis:

1. compare MAE, signed bias, false accepts, and false rejects across G_PAR, G_SEQ, G_SEQPAR, and G_PARSEQ;
2. stratify the graph comparison by symmetric worlds P1/P3 versus heterogeneous worlds P2/P4;
3. relate graph-prediction error to provider-reconstruction error only after all primary predictions and final WB evidence are open;
4. do not use topology outcomes to change a reconstruction, weight, support, query, or budget.

## A3. Passive mechanism diagnostics

Two diagnostics may help interpret A2 and are strictly analysis-only.

### SLA-component violation flags

The top-level trajectory ledger already contains end-to-end latency L, cost C, and quality Q. For each frozen query/horizon, analysis code should derive whether a failed SLA condition is attributable to latency, cost, quality, or multiple simultaneous components. These flags are never method inputs.

### Parallel-join controlling child

Where the Phase-5 simulator can expose it from the same native execution trace without changing stochastic execution, emit a separate passive diagnostic artifact identifying which child completion controls each `parallel_all` join. Suggested fields are:

`physical_cell_id, method_id, trajectory, request_id, composition_node_id, controlling_child_id, child_completion_times`.

This artifact must not alter random draws, scheduling, completion semantics, method predictions, or budgets. It is never read before prediction freeze and is never available to M0/M1/M2/M3. If the implementation cannot expose it without a semantic change, record `NOT_AVAILABLE`; absence does not invalidate the primary battery.

## A4. Deferred diagnostics

The following pilot questions are intentionally deferred until after Phase-5 data collection and will be labelled post-hoc if performed:

- scoring the hidden true theta directly on the public I1 card and comparing its energy/weight with reconstructed candidates;
- testing whether retained-support envelopes or other M3 ambiguity summaries predict decision errors.

They are not part of the confirmatory Phase-5 analysis defined here.

## A5. Authority

The core Phase-5 protocol and its existing machine-readable contracts remain unchanged and authoritative for the scientific design. This addendum adds analysis commitments only. If there is any conflict, the core frozen design wins and the discrepancy must be documented rather than silently repaired.
