# PRAISE first science - Phase 2 / I1

Phase 2 owns the complete construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. Phase 3 starts only after the concrete public I1 cards are materialized, inspected and frozen.

The current sequence is:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local subtraces/ledgers -> provider-local A_i -> empirical sigma_i(A_i,H;rho) -> frozen I1 cards -> Phase 3 M0 -> Phase 4 M1`

There is no `A_G -> A_i` step in I1 construction.

## Phase-2 object

A concrete provider card is

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

`A_i` is part of `I1`. It is selected and frozen in Phase 2 from provider `i`'s own acquisition evidence only. `A_G` is not an input to that selection. M0 and M1 may not choose or alter `A_i`.

The full rho support `R` is part of the card. Phase 2 does not choose a method-specific rho slice.

## 2A - provider evidence acquisition - FROZEN AND RETAINED

`config_phase2_i1_acquisition_v1.json` defines the acquisition protocol. The already completed acquisition remains valid:

- frozen physical regime `D300000000_d0.200`;
- independent seeds `6000..6099`;
- 100 full native trajectories;
- each full trajectory reduced to the ProviderA/B/C local request ledgers;
- 119900 provider-request rows per provider;
- provider-corpus SHA-256 fingerprints recorded in `phase2_i1_freeze_manifest_v1.json`.

The old `phase2_i1_freeze_manifest_v1.json` remains useful as the frozen evidence-corpus checkpoint. Its historical statement that a consuming method declares `A_i` is superseded by the direct-I1 v2 contract. The underlying provider evidence and hashes are unchanged.

## 2B - corrected direct I1 construction contract - CURRENT

`config_phase2_i1_direct_trace_v2.json` records the corrected information boundary:

- provider `i`'s `A_i` comes only from provider `i`'s local acquisition ledger;
- no `A_G` values enter `A_i` construction;
- no global latency/cost budget is split into local budgets;
- no Phase-1 global sigma outcome is used;
- no M0/M1 result is used;
- the same selection-rule form must be used for all three providers;
- the already frozen `H={0,5,...,240}` and `R={0.95,0.975,0.9833333333333333,0.99,1.0}` support is retained.

`inspect_provider_local_evidence.py` is the read-only audit of the actual frozen provider ledgers before the final local `A_i` rule is chosen. It verifies the stored SHA-256 hashes and prints provider-local L/C/Q evidence summaries. The printed quantiles are descriptive only; they are not an `A_i` selection rule.

## 2C - provider-local A_i selection - NEXT

Freeze one small rule that maps

`provider i local evidence -> A_i={L_i<=l_i, C_i<=c_i, Q_i>=q_i}`

using that provider's evidence only. The rule must have the same form for ProviderA/B/C and must not inspect `A_G`, global white-box sigma outcomes, M0 or M1.

Once that rule is frozen, apply it to the existing 6000..6099 ledgers and write one fixed `A_i` per provider.

## 2D - final direct I1 card materialization - AFTER 2C

For each provider, compute directly from the same frozen provider evidence

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`

for the complete frozen `H x R` support, then write, inspect, hash and freeze the public card. No provider simulator rerun is required.

The final invariant is:

`same finished I1 cards -> M0 and M1`.

## Superseded A_G -> A_i path

The earlier benchmark-localization path is not part of the current design. In particular, the old query-instantiation declaration, equal global cost split, global latency residual localization, and diagnostics built on those materialized cards must not be used for the final I1 cards. They are historical development artifacts only.

## Information / method boundary

Phase 2 may use the private provider-local evidence to construct and freeze `I1`. After the final cards are frozen, Phase 3 and Phase 4 receive only the public cards plus their method-allowed public inputs. They may not access the private provider ledgers, alter `A_i`, or rematerialize I1 after seeing method results.

## Freeze rule

The acquisition evidence, H/R support and accounting semantics remain read-only. The only currently open Phase-2 scientific choice is the simple provider-local `A_i` selection rule. Once that rule and the resulting cards are frozen, Phase 2 becomes a read-only dependency.
