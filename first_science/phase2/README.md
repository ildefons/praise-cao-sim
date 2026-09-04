# PRAISE first science — Phase 2 / I1

Phase 2 freezes the first information technology `I1`. Phase 1 remains the immutable Step-0 white-box benchmark.

The development sequence is now:

`Phase 1 frozen white-box target -> Phase 2 I1 -> Phase 3 (I1,M0) -> Phase 4 (I1,M1)`

## Phase-2 objective

Freeze one provider information technology that can later be consumed unchanged by different composition methods:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

I1 does not choose the provider-local admissibility region `A_i`. A consuming method declares exact `A_i` query points before seeing I1 sigma values; the public card is then deterministically materialized from a frozen private provider-acquisition corpus. This avoids an arbitrary provider-local L/C/Q grid and keeps metric-budget allocation inside `M` rather than `I`.

## Phase-2 checkpoints

### 2A — I1 contract

Frozen in `config_phase2_i1_provider_card_v1.json`:

- provider-local SLA semantics;
- `H=0..240` in steps of 5;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`;
- Wilson 95% uncertainty;
- exact materialized queries only;
- public/private information firewall;
- same materialized cards for M0 and M1.

### 2B — I1 acquisition protocol

Frozen in `config_phase2_i1_acquisition_v1.json`:

- final Phase-1 matched physical regime, used privately for provider acquisition;
- fresh acquisition seeds `6000..6099`, `N=100`;
- same workload context as Phase 1;
- provider arrival/completion/L/C/Q ledger semantics;
- transient full-graph traces, persistent provider-local ledgers only;
- one immutable corpus reused for every later A_i/H/rho query.

### 2C — Freeze acquired provider corpus

Run the frozen acquisition protocol and retain its provider-ledger checksums/manifest. Once this succeeds, I1 is frozen. Later phases can materialize exact public card instances, but cannot change the evidence or I1 definition.

## Current Phase-2 files

- `config_phase2_i1_provider_card_v1.json`
- `config_phase2_i1_acquisition_v1.json`
- `i1_provider_card.py`
- `i1_provider_acquisition.py`
- `materialize_i1_cards.py`
- `test_i1_provider_card.py`
- `test_i1_provider_acquisition.py`
- `README_I1_PROVIDER_CARD.md`

Any M0 code already prototyped is logically Phase 3 and is not part of the Phase-2 scientific freeze.
