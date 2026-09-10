# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. The public schema, provider-local `T_i -> A_i` rule, H/rho support, and materialization pipeline are frozen.

The active path is:

`frozen provider evidence T_i -> frozen A_i calibration -> full sigma_i(A_i,H;rho) surface -> hash-frozen public I1_i -> M0/M1`

There is no `A_G -> A_i` step and Phase 2 does not select a provider-specific `rho_i`.

## Provider evidence - FROZEN

`config_phase2_i1_acquisition_v1.json` defines the completed acquisition protocol. The private corpus contains 100 trajectories, seeds `6000..6099`, and 119900 provider-request rows per provider. `phase2_i1_freeze_manifest_v1.json` stores the frozen SHA-256 fingerprints.

## Public I1 object - FROZEN

For each provider:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

Frozen support:

- `H={0,5,...,240}`;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

The public card contains `A_i`, workload/context `W_i`, exact H/rho support, the sigma surface, and confidence metadata. Provider traces remain private.

## T_i -> A_i calibration - FROZEN

`i1_local_region.py` implements the frozen coordinate-wise anchor rule:

- `rho_anchor=0.95`;
- `H*=120 s`;
- `sigma_target=0.95`.

For latency, cost, and quality separately, select the observed threshold whose first `sigma_i(A_i^X,H;rho_anchor)` crossing below 0.95 occurs closest to 120 s. Combine the three thresholds into

`A_i={L_i<=l_i*, C_i<=c_i*, Q_i>=q_i*}`.

The resulting joint sigma is measured, not forced to 0.95. If quality is constant, its unique observed value is used directly.

`rho_anchor` is a Phase-2 calibration anchor, not a provider-specific `rho_i`. After `A_i` is fixed, the full frozen rho support is materialized.

## Public card materialization - FROZEN PIPELINE

`materialize_frozen_i1_cards.py` is the only materialization path. It:

1. verifies all three private provider-ledger SHA-256 hashes against `phase2_i1_freeze_manifest_v1.json`;
2. derives the three fixed `A_i` values using the rule above;
3. computes every H x rho I1 point from the same frozen corpus;
4. writes `card.json` and `sigma_surface.csv` for ProviderA/B/C;
5. reloads and validates each public card;
6. writes `i1_card_instances_manifest_v1.json` containing the public card hashes.

Generated cards live under `results/i1_cards_v1/public/` and are intentionally generated artifacts. The instance manifest, rather than a source-code boolean, records whether a concrete materialization exists.

M0 and M1 must consume exactly these same hash-frozen public cards. Phase 3 is forbidden from reading the private provider ledgers.

## Validation and materialization

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/test_materialize_frozen_i1_cards.py
python first_science/phase2/materialize_frozen_i1_cards.py
```

Expected materialization markers:

```text
PHASE2_I1_CARD_MATERIALIZATION_PASS
PRIVATE_EVIDENCE_HASH_VERIFICATION_PASS
THREE_PUBLIC_I1_CARDS_WRITTEN_PASS
PUBLIC_I1_CARD_HASH_FREEZE_PASS
SAME_I1_FOR_M0_M1_PASS
```

After this step, Phase 3 consumes only `results/i1_cards_v1/public/` and its instance manifest.
