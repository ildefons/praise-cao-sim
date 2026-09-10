# Phase 2 - I1 provider admissibility-probability surface

Phase 2 constructs and freezes the first provider information technology. Phase 1 remains the immutable Step-0 white-box benchmark.

## Public I1 object

For one provider-local admissibility region

`A_i = {L_i <= l_i, C_i <= c_i, Q_i >= q_i}`

and declared workload/context `W_i`, a public card is

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

The frozen first-experiment axes remain:

- `H = 0..240` in steps of 5;
- `R = {0.95, 0.975, 0.9833333333333333, 0.99, 1.0}`.

The card may also expose the Wilson 95% interval, successful-trajectory count and acquisition-trajectory count at each surface point.

## Corrected A_i ownership

`A_i` is part of the finished I1 card. It is therefore fixed in Phase 2, before M0 or M1 runs.

The current direct construction is:

`frozen physical regime -> fresh full Phase-2 trajectories -> provider-local subtraces/ledgers -> provider-local A_i -> empirical sigma_i -> finished I1_i`.

The local `A_i` for ProviderA is chosen only from ProviderA evidence; likewise for ProviderB and ProviderC. The same rule form must be used for all three providers.

There is no `A_G -> A_i` step. Global admissibility-region values, global white-box sigma outcomes, M0 and M1 are forbidden inputs when choosing `A_i`.

## Provider-local semantics

The local accounting mirrors the frozen Phase-1 admissibility semantics:

- cumulative `[0,H]` from common `t=0`;
- `L_i` is provider arrival to provider completion, including queue wait and service;
- an in-time request is decided at provider completion;
- a local latency miss is decided at its local latency deadline;
- cost and quality are not evaluated after a timeout;
- unresolved requests at `H` are excluded;
- zero decided requests implies compliance fraction 1;
- `sigma_i(H;rho)` may be non-monotone in `H` when `rho<1`;
- at fixed `A_i,H`, `sigma_i(H;rho)` is non-increasing in rho.

`C_i` is native provider execution cost and `Q_i` is native provider-observed quality.

## Frozen provider evidence

The provider evidence was acquired once in the frozen physical regime using the independent seed bank `6000..6099` (`N=100`). Each seed executes the complete native graph so the provider arrival/queue context is real. The full native trajectory is transient; only the provider-local ledgers persist.

The retained local ledger columns are

`trajectory, request_id, emission, completion, L, C, Q`

where `emission` means provider-local arrival.

The existing evidence-corpus hashes in `phase2_i1_freeze_manifest_v1.json` remain valid. The old v1 statement that a consuming method supplies `A_i` is superseded by `config_phase2_i1_direct_trace_v2.json`.

## Current direct-I1 status

`config_phase2_i1_direct_trace_v2.json` freezes the corrected ownership and information firewall, while leaving only the small provider-local `A_i` selection rule open.

`inspect_provider_local_evidence.py` verifies the exact frozen provider-corpus hashes and prints descriptive L/C/Q summaries. It does not choose `A_i`.

After one provider-local `A_i` rule is frozen, the existing generic functions in `i1_provider_card.py` can compute the full empirical `H x R` sigma surface directly from each provider ledger. No simulator rerun is required.

## Information firewall

A public I1 card must not expose raw provider traces, private request ledgers, acquisition seeds, hidden generator parameters, provider instruction means, hidden physical parameters, simulator state, or top-level Phase-1 white-box curves/outcomes.

M0 and M1 receive exactly the same finished I1 cards and may not alter or rematerialize `A_i`.

## Validation

From `~/praise/praise-cao-sim`:

```bash
python first_science/phase2/test_i1_provider_card.py
python first_science/phase2/test_i1_provider_acquisition.py
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/inspect_provider_local_evidence.py
```

The first three are contract/unit tests. The final command is a read-only audit of the already acquired private provider evidence.
