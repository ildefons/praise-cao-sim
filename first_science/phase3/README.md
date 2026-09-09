# Phase 3A — structural M0 query-decomposition contract

Phase 3A defines the structural part of `(I1,M0)` before any comparison with white-box top-level sigma outcomes.

## Scientific question

For a frozen exogenous global admissibility query

`Q_G = (A_G, H, rho_G)`

and the public composition graph

`Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`,

derive provider-local query boundaries

`Q_i = (A_i, H, rho_i)`

using only public composition semantics and the frozen Phase-1 v2 global admissibility regions.

Phase 3A does **not** query I1 sigma values and does **not** estimate `sigma_G`.
Those belong to Phase 3B.

## Allowed information

- exact frozen Phase-1 v2 `A_G` thresholds and `rho_G`;
- public graph/topology/runtime constants needed for deterministic boundary algebra;
- provider identifiers and the known `ParAll` composition structure.

## Forbidden information

- Phase-2 private provider acquisition ledgers;
- provider hidden generator parameters or distributions;
- public I1 sigma values while defining the structural mapping;
- Phase-1 top-level white-box sigma/confirmation outcomes while defining or tuning M0;
- any M1 reconstruction results.

## Frozen-reference mapping under test

For three required providers:

- latency: `L_G = L_fixed + max_i(L_branch_i + L_i)`, so each provider receives the full residual latency budget;
- cost: `C_G = C_fixed + sum_i C_i`, so the transparent reference policy splits the residual cost budget equally;
- quality: `Q_G = min_i Q_i`, so every provider inherits the global minimum quality threshold;
- cumulative tolerance: with `epsilon_G = 1-rho_G`, use equal allocation `epsilon_i = epsilon_G/3` and `rho_i = 1-epsilon_i`.

For `rho_G=0.95`, this gives

`rho_i = 0.9833333333333333`,

which was already frozen in the Phase-2 I1 rho grid before M0/M1 evaluation.

## Proof obligations and current boundary

Phase 3A distinguishes three obligations:

1. **Request-level boundary implication.** Under the declared public boundary algebra, all local requests satisfying their `A_i` imply the composed request satisfies `A_G`.
2. **Cumulative counting implication.** On the same aligned ordered set of logical root requests, local violation budgets whose sum is at most the global budget imply the global cumulative admissibility target.
3. **Runtime horizon alignment.** The real benchmark uses decision-time accounting at horizon `H`. Provider-local and top-level decided-request subsets need not automatically be identical at the same `H`. This must be audited separately before the aligned counting statement is promoted to a formal certificate for the real benchmark.

The initial implementation in this directory freezes neither that runtime alignment claim nor the final M0 probability product. It first makes the structural mapping machine-checkable and human-auditable.
