# PRAISE first science — Phase 2 / Step 1

Phase 2 starts the information-and-composition part of the first PRAISE experiment.

Phase 1 is frozen and supplies the Step-0 white-box benchmark: the physical reference regime, the three matched admissibility regions, the authoritative top-level SLA-compliance curves, and their final untouched N=100 confirmation.

Phase 2 must not alter that benchmark. Its dependency is one-way:

`phase1 frozen Step-0 target -> phase2 I1 -> (I1,M0) and (I1,M1)`

The first task is to freeze and instantiate the minimal provider information representation `I1`. The exact same I1 cards must later be consumed by both M0 and M1 so that representation and composition effects remain separable.

Current files:

- `config_phase2_i1_provider_card_v1.json`: minimal I1 contract.
- `i1_provider_card.py`: provider-card builder and exact query API.
- `test_i1_provider_card.py`: simulator-independent contract tests.
- `README_I1_PROVIDER_CARD.md`: scientific semantics and information firewall.

The next open item is the provider-local admissibility-region grid. It must be designed from provider-local information only, frozen before real I1 acquisition, and not tuned against Phase-1 top-level white-box curves or M0/M1 outcomes.
