# PRAISE first science - Phase 2 / I1

Phase 2 owns the complete construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. Phase 3 numerical evaluation starts only after the concrete public I1 cards are materialized, inspected and hash-frozen.

The current sequence is:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local subtraces/ledgers -> frozen provider-local A_i rule -> empirical sigma_i(A_i,H;rho) -> frozen I1 cards -> Phase 3 M0 -> Phase 4 M1`

There is no `A_G -> A_i` step in I1 construction.

## Phase-2 object

A concrete provider card is

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

`A_i` is part of `I1`. It is constructed and frozen in Phase 2 from provider `i`'s own acquisition evidence only. `A_G` is not an input. M0 and M1 may not choose or alter `A_i`.

The full rho support `R` is part of the card. Phase 2 does not choose a method-specific rho slice.

## 2A - provider evidence acquisition - FROZEN AND RETAINED

`config_phase2_i1_acquisition_v1.json` defines the acquisition protocol. The completed acquisition remains valid:

- frozen physical regime `D300000000_d0.200`;
- independent seeds `6000..6099`;
- 100 full native trajectories;
- each full trajectory reduced to the ProviderA/B/C local request ledgers;
- 119900 provider-request rows per provider;
- provider-corpus SHA-256 fingerprints recorded in `phase2_i1_freeze_manifest_v1.json`.

The old `phase2_i1_freeze_manifest_v1.json` remains the frozen evidence-corpus checkpoint. Its historical statement that a consuming method declares `A_i` is superseded by the direct-I1 v2 contract. The underlying provider evidence and hashes are unchanged.

## 2B - corrected direct I1 construction contract - FROZEN

`config_phase2_i1_direct_trace_v2.json` records the corrected information boundary:

- provider `i`'s `A_i` comes only from provider `i`'s local acquisition ledger;
- no `A_G` values enter `A_i` construction;
- no global latency/cost budget is split into local budgets;
- no Phase-1 global sigma outcome is used;
- no M0/M1 result is used;
- the same rule form is used for all three providers;
- the frozen `H={0,5,...,240}` and `R={0.95,0.975,0.9833333333333333,0.99,1.0}` support is retained.

## 2C - provider-local A_i rule - FROZEN

`config_phase2_i1_local_region_rule_v1.json` freezes one deliberately simple provider-description rule:

`A_i = {L_i <= p99(L_i), C_i <= p99(C_i), Q_i >= min(Q_i)}`

where both p99 values use the empirical `higher` order statistic. The same rule is applied independently to ProviderA, ProviderB and ProviderC.

This is not a reuse of the Phase-1 global AR gate. No requirement is imposed that every provider-local card reproduce the global `R_0.95/R_0.99` selection regime. The providers are allowed to expose different local sigma shapes.

## 2D - final direct I1 card materialization - CURRENT NEXT STEP

`config_phase2_i1_provider_card_v2.json` freezes the corrected direct-I1 card ownership while retaining the existing H/rho/accounting/confidence semantics.

`materialize_direct_i1_cards.py` applies the frozen local rule to the already frozen ProviderA/B/C ledgers and then computes

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`

for the complete frozen `H x R` support. It writes one public card and one public sigma surface per provider plus a card-set manifest. No simulator rerun is required.

The generated manifest is intentionally marked as materialized but not yet repository-frozen. After human inspection, the exact card hashes are copied into a repository freeze manifest. Only then is Phase 2 fully closed.

The final invariant is:

`same finished I1 cards -> M0 and M1`.

## Superseded A_G -> A_i path

The earlier benchmark-localization path is not part of the current design. The old query-instantiation declaration, equal global cost split, global latency residual localization, and diagnostics built on those provisional cards must not be used for the final I1 cards.

## Information / method boundary

Phase 2 may use the private provider-local evidence to construct and freeze `I1`. After the final cards are frozen, Phase 3 and Phase 4 receive only the public cards plus their method-allowed public inputs. They may not access the private provider ledgers, alter `A_i`, or rematerialize I1 after seeing method results.

## Validation sequence

Starting from the repository root:

```bash
python first_science/phase2/test_materialize_direct_i1_cards.py
python first_science/phase2/materialize_direct_i1_cards.py
```

Expected test markers:

```text
PHASE2_DIRECT_I1_MATERIALIZATION_TESTS_PASS
P99_LOCAL_REGION_RULE_PASS
DIRECT_I1_CARD_SUPPORT_PASS
```

Expected materialization final marker:

```text
PHASE2_DIRECT_I1_MATERIALIZATION_PASS
repository_freeze_performed=false
```

## Freeze rule

The provider acquisition evidence, H/R support, accounting semantics and provider-local p99/p99/minQ rule are now read-only. The remaining Phase-2 action is deterministic final card materialization, inspection and hash-freezing.
