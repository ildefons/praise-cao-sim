# Phase 2 - I1 provider admissibility-probability surface

Phase 2 constructs and freezes the first provider information technology. Phase 1 remains the immutable white-box benchmark.

## Public I1 object

For one fixed provider-local admissibility region

`A_i={L_i<=l_i, C_i<=c_i, Q_i>=q_i}`

and workload/context `W_i`, the public card is

`I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho)=P(c_i(A_i,H)>=rho)`.

The frozen axes are `H={0,5,...,240}` and `R={0.95,0.975,0.9833333333333333,0.99,1.0}`. Wilson confidence intervals and trajectory counts may accompany each point.

## A_i ownership and construction

`A_i` is part of the finished I1 card and is fixed by Phase 2 before M0 or M1 runs. The construction is

`T_i -> frozen coordinate calibration -> A_i -> full H x R sigma surface -> public I1_i`.

For each provider and each coordinate separately, the frozen anchor calibration uses

- `rho_anchor=0.95`;
- `H*=120 s`;
- `sigma_target=0.95`.

The selected coordinate threshold is the observed candidate whose first local sigma crossing below 0.95 occurs closest to 120 s. The three coordinate thresholds form the joint rectangle. Its joint sigma at 120 s is measured rather than forced to 0.95. Constant quality uses its unique observed value.

There is no `A_G -> A_i` step, no request-level p95/p99 construction, and no M0/M1 feedback into `A_i`.

## Provider-local semantics

The local accounting mirrors the frozen cumulative-admissibility semantics:

- cumulative `[0,H]` from `t=0`;
- `L_i` is provider arrival to provider completion including queue wait and service;
- local latency misses are decided at the local latency deadline;
- cost and quality are not evaluated after a timeout;
- unresolved requests at H are excluded;
- zero decided requests implies compliance fraction 1;
- sigma may be non-monotone in H for rho<1;
- sigma is non-increasing in rho at fixed A_i,H.

## Frozen provider evidence

The provider evidence was acquired once using seeds `6000..6099`, N=100. Only provider-local ledgers persist. Their SHA-256 values are frozen in `phase2_i1_freeze_manifest_v1.json`.

Private ledger columns are

`trajectory, request_id, emission, completion, L, C, Q`.

## Hash-frozen public instance handoff

`materialize_frozen_i1_cards.py` is the only production path from the frozen private evidence to concrete public I1 instances. Before materialization it verifies the evidence hashes. It then writes, for each provider,

- `card.json`;
- `sigma_surface.csv`.

It also writes `i1_card_instances_manifest_v1.json` with the SHA-256 fingerprints of those public files. M0 and M1 must consume the same files unchanged.

Phase 3 is explicitly forbidden from reading the private provider ledgers or recalculating `A_i`. It loads and verifies the public card hashes before evaluating M0.

## Validation

From the repository root:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase2/test_i1_provider_card.py
python first_science/phase2/test_i1_provider_acquisition.py
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/test_materialize_frozen_i1_cards.py
python first_science/phase2/materialize_frozen_i1_cards.py
```

The generated public card root is

`first_science/phase2/results/i1_cards_v1/public/`.
