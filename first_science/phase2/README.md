# PRAISE first science — Phase 2 / Step 1

Phase 2 contains the information-and-composition part of the first PRAISE experiment.

Phase 1 is frozen and supplies the Step-0 white-box benchmark: the physical reference regime, the three matched admissibility regions, the authoritative top-level SLA-compliance curves, and their final untouched N=100 confirmation.

Phase 2 must not alter that benchmark. Its dependency is one-way:

`phase1 frozen Step-0 target -> phase2 I1 -> (I1,M0) and (I1,M1)`

## Current checkpoint

The minimal I1 interface and the first M0 analytic contract are now defined.

The first pilot does **not** create a generic provider-local L/C/Q grid. For each of the three meaningful frozen global Phase-1 ARs, M0 derives exactly one sufficient local boundary per provider from the declared graph algebra. Those exact I1 points are then supplied unchanged to M0 and M1.

Current files:

- `config_phase2_i1_provider_card_v1.json`: minimal I1 contract.
- `i1_provider_card.py`: provider-card builder and exact query API.
- `test_i1_provider_card.py`: simulator-independent I1 tests.
- `README_I1_PROVIDER_CARD.md`: I1 semantics and information firewall.
- `config_phase2_m0_v1.json`: first M0 method contract.
- `m0_contract_composition.py`: L/C/Q decomposition, SLA error-budget/counting logic and independent probability composition.
- `test_m0_contract_composition.py`: hand-checkable M0 contract tests.
- `README_M0.md`: M0 scientific interpretation and required real-anchor audits.

## Immediate next step

Read the full-precision three frozen global ARs from the Phase-1 final manifest, derive the nine exact ProviderA/B/C local boundaries, and audit that the real anchor satisfies the request-level boundary and horizon/request-set assumptions needed to interpret the M0 product as a formal SLA certificate. Only after that audit should the real I1 provider cards be generated.
