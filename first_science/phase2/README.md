# PRAISE first science — Phase 2 / I1 — FROZEN

Phase 2 freezes the first information technology `I1`. Phase 1 remains the immutable Step-0 white-box benchmark.

The development sequence is:

`Phase 1 frozen white-box target -> Phase 2 I1 [FROZEN] -> Phase 3 (I1,M0) -> Phase 4 (I1,M1)`

## Frozen Phase-2 object

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

I1 does not choose the provider-local admissibility region `A_i`. A consuming method declares exact `A_i` query points before seeing I1 sigma values; the public card is then deterministically materialized from the frozen private provider-acquisition corpus. This avoids an arbitrary provider-local L/C/Q grid and keeps metric-budget allocation inside `M` rather than `I`.

## 2A — I1 contract — FROZEN

`config_phase2_i1_provider_card_v1.json` freezes:

- provider-local SLA semantics;
- `H=0..240` in steps of 5;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`;
- Wilson 95% uncertainty;
- exact materialized queries only;
- public/private information firewall;
- same materialized cards for M0 and M1.

## 2B — I1 acquisition protocol — FROZEN

`config_phase2_i1_acquisition_v1.json` freezes:

- the final Phase-1 matched physical regime as the private provider-acquisition world;
- fresh acquisition trajectories, disjoint from the frozen Phase-1 final evaluation trajectories;
- `N=100` provider-acquisition trajectories;
- the same workload context as Phase 1;
- provider arrival/completion/L/C/Q ledger semantics;
- transient full-graph traces and persistent provider-local ledgers only;
- one immutable corpus reused for later exact `A_i/H/rho` card queries.

## 2C — acquired provider corpus — FROZEN

The real acquisition completed successfully with:

- ProviderA: 100 trajectories, 119900 provider-request rows;
- ProviderB: 100 trajectories, 119900 provider-request rows;
- ProviderC: 100 trajectories, 119900 provider-request rows.

The implementation tests passed:

- `PHASE2_I1_PROVIDER_CARD_TESTS_PASS`
- `PHASE2_I1_PROVIDER_ACQUISITION_TESTS_PASS`

The validated public provenance checkpoint is recorded in `phase2_i1_freeze_manifest_v1.json`, including the three provider-corpus SHA-256 fingerprints. Private raw provider ledgers remain local evidence and are not part of the public I1 card.

## Frozen Phase-2 files

- `config_phase2_i1_provider_card_v1.json`
- `config_phase2_i1_acquisition_v1.json`
- `i1_provider_card.py`
- `i1_provider_acquisition.py`
- `materialize_i1_cards.py`
- `test_i1_provider_card.py`
- `test_i1_provider_acquisition.py`
- `README_I1_PROVIDER_CARD.md`
- `phase2_i1_freeze_manifest_v1.json`

## Freeze rule

Do not modify Phase-2 scientific definitions, acquisition evidence, rho support, horizon support, or card semantics to improve later M0/M1 results.

Later phases may only:

1. declare exact provider-local `A_i` query points without inspecting I1 outcomes;
2. invoke the frozen materializer on the frozen provider corpus;
3. consume the resulting identical public I1 cards.

Any M0 code already prototyped in this directory is pre-freeze scaffolding and is logically Phase 3; scientific development of M0 starts in `phase3/`.
