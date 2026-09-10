# PRAISE first science - Phase 2 / I1

Phase 2 owns the complete construction of the information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. Phase 3 starts only after the concrete public I1 cards are materialized and frozen.

The corrected development sequence is:

`Phase 1 frozen A_G battery -> Phase 2 I1 contract/acquisition/A_G->A_i instantiation/materialized cards -> Phase 3 (I1,M0) -> Phase 4 (I1,M1)`

## Phase-2 object

A concrete provider card is

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

Therefore `A_i` is part of `I1`. It is not chosen by M0 or M1. For the first benchmark, each frozen global admissibility region `A_G` is localized into provider-local `A_i` values by one method-independent benchmark rule using only the public composition structure. Those exact local regions are then materialized against the frozen provider corpus. M0 and M1 receive the resulting cards unchanged.

The full rho support `R` is also part of the card. Phase 2 does not choose a method-specific `rho_i`; a composition method may choose which already-exposed rho slice or slices it consumes.

## 2A - I1 representation contract - FROZEN

`config_phase2_i1_provider_card_v1.json` freezes:

- provider-local admissibility semantics;
- `H=0..240` in steps of 5;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`;
- Wilson 95% uncertainty;
- exact materialized `A_i` queries only;
- public/private information firewall.

## 2B - provider evidence acquisition - FROZEN

`config_phase2_i1_acquisition_v1.json` freezes the provider-side acquisition protocol. The real acquisition completed successfully with 100 trajectories and 119900 provider-request rows for each of ProviderA, ProviderB and ProviderC. The corpus and SHA-256 fingerprints are recorded in `phase2_i1_freeze_manifest_v1.json`.

This manifest is an evidence-corpus freeze checkpoint. It is not the final Phase-2 boundary anymore: Phase 2 now explicitly ends at the frozen materialized I1 card set.

## 2C - method-independent I1 query instantiation - FROZEN

`config_phase2_i1_query_instantiation_v1.json` and `phase2_i1_exact_query_declaration_v1.json` freeze the mapping from the already frozen Phase-1 v2 `A_G` battery to exact provider-local `A_i` regions.

For the public graph

`Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`,

the first benchmark localization uses:

- latency: every branch receives the complete residual latency because global latency uses a parallel maximum;
- cost: the residual additive global cost budget is split equally among the three providers;
- quality: every provider receives the global minimum quality threshold.

This step uses no I1 sigma values, no private provider parameters and no post-freeze white-box tuning. It also performs no rho allocation.

## 2D - final I1 card materialization - NEXT

`materialize_i1_cards.py` consumes:

1. the frozen I1 representation contract;
2. the frozen private provider corpus;
3. the frozen Phase-2 exact `A_i` declaration.

It deterministically produces the public I1 surfaces for all three benchmark `A_i` regions, all frozen horizons `H`, and the complete frozen rho support `R` for every provider.

After materialization, the card files and their hashes must be validated and frozen. Only then is Phase 2 complete.

The final invariant is:

`same materialized I1 cards -> M0 and M1`.

## Current Phase-2 files

- `config_phase2_i1_provider_card_v1.json`
- `config_phase2_i1_acquisition_v1.json`
- `config_phase2_i1_query_instantiation_v1.json`
- `phase2_i1_exact_query_declaration_v1.json`
- `i1_provider_card.py`
- `i1_provider_acquisition.py`
- `i1_query_instantiation.py`
- `materialize_i1_cards.py`
- `test_i1_provider_card.py`
- `test_i1_provider_acquisition.py`
- `test_i1_query_instantiation.py`
- `README_I1_PROVIDER_CARD.md`
- `phase2_i1_freeze_manifest_v1.json`

## Information / method boundary

Phase 2 may construct and freeze `I1`, including its `A_i` values and full `H x R` sigma surface. It may not choose an M0-specific or M1-specific rho slice or alter the cards based on method performance.

Phase 3 and Phase 4 may only consume the already frozen cards. They may not change `A_i`, rerun provider acquisition, or request a different I1 card set.

## Human-auditable implementation convention

Comments and docstrings may be improved without changing frozen numerical semantics or evidence. Scientific boundaries should remain visible as:

`frozen Phase-1 A_G -> method-independent Phase-2 A_i -> frozen provider evidence -> public I1 cards -> M0/M1`.

## Freeze rule

Do not modify Phase-2 scientific definitions, provider evidence, exact `A_i` declaration, rho support, horizon support or materialized card values to improve later M0/M1 results. Once the final card set is hash-frozen, Phase 2 becomes a read-only dependency.
