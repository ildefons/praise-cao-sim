# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1` from the frozen private provider evidence. The private acquisition corpus, workload, H grid, cumulative accounting semantics, and Phase-1 white-box benchmark remain unchanged.

## Current correction under validation: rho-conditioned local regions

The historical materialization `results/i1_cards_v1/` used one fixed local region per provider, selected by the earlier `H*=120`, `rho_anchor=.95`, `sigma_target=.95` first-crossing calibration. That branch is retained for provenance, but it is no longer the intended scientific construction if the rho-conditioned candidate below validates.

The candidate path is

`T_i -> joint log(L,C) GMM -> A_i(rho_region) -> sigma_i(A_i(rho_region),H;rho_query) -> public I1_i`.

The central map is

`Gamma(T_i,rho_region)=A_i(rho_region)`.

For the current benchmark, `Q=0.5` is degenerate. Each provider therefore fits a full-covariance Gaussian mixture in `(log L, log C)`. The number of components is selected by minimum BIC over `K=1..4`. From one deterministic `N=100000` sample of the fitted joint model, the code extracts the minimum-area origin-anchored rectangle `[0,l] x [0,c]` containing at least the requested model probability content. Regions are constrained to be nested as `rho_region` increases. Non-degenerate Q is deliberately rejected in this version rather than generalized without a frozen rule.

The finite region-content support is

`R_region={0.95,0.975,0.9833333333333333,0.99,0.995}`.

`rho_region=1` is not used because a Gaussian mixture has unbounded support and therefore no finite exact 100% probability-content rectangle.

The trajectory-compliance query threshold remains a separate coordinate in the public card:

`sigma_i(A_i(rho_region),H;rho_query)=P(c_i(A_i(rho_region),H)>=rho_query)`.

For now the same support is exposed for `rho_query`. The complete Cartesian `A_i(rho_region) x rho_query x H` surface is materialized so later methods never need private traces. The official M0 comparison first uses only the diagonal

`rho_region=rho_query=rho_i=rho_G`.

## Provider evidence - unchanged and hash frozen

`config_phase2_i1_acquisition_v1.json` defines the completed acquisition protocol. The private corpus contains 100 trajectories, seeds `6000..6099`, and 119900 provider-request rows per provider. `phase2_i1_freeze_manifest_v1.json` stores the frozen SHA-256 fingerprints.

The new materializer verifies these same hashes before doing any GMM fitting. No new provider simulation is required, and Phase-1 white-box outputs are forbidden from the I1 construction.

## Versioned implementations

Historical fixed-region branch, retained for provenance:

- `config_phase2_i1_provider_card_v2.json`
- `i1_local_region.py`
- `materialize_frozen_i1_cards.py`
- generated `results/i1_cards_v1/`

Rho-conditioned candidate branch:

- `config_phase2_i1_provider_card_v3_rho_conditioned.json`
- `i1_rho_conditioned_region.py`
- `materialize_rho_conditioned_i1_cards.py`
- generated `results/i1_cards_v2_rho_conditioned/`

The generic `i1_provider_card.py` is reused. It already supports multiple exact local regions and computes the H x rho query surface from the frozen provider ledgers using the established cumulative request-decision semantics.

Fitted GMM parameters, BIC diagnostics and the synthetic model sample stay private. The public handoff contains only the rho-conditioned regions, their support, workload/context, exact sigma surfaces and confidence metadata. The resulting public cards are hash recorded in `i1_rho_conditioned_manifest_v1.json` and are intended to be supplied unchanged to M0 and M1.

## Validation and materialization

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

git pull origin first-science-phase1

python -c "import sklearn; print(sklearn.__version__)"
python first_science/phase2/test_i1_rho_conditioned_region.py
python first_science/phase2/test_materialize_rho_conditioned_i1_cards.py
python first_science/phase2/materialize_rho_conditioned_i1_cards.py
```

Expected markers include:

```text
PHASE2_RHO_CONDITIONED_REGION_TESTS_PASS
JOINT_LOG_LC_GMM_BIC_PASS
MINIMUM_AREA_JOINT_MASS_BOX_PASS
NESTED_A_I_OF_RHO_PASS
FINITE_GMM_RHO_ONE_BLOCKED_PASS
NONDEGENERATE_Q_NOT_SILENTLY_GENERALIZED_PASS

PHASE2_RHO_CONDITIONED_I1_CONTRACT_TESTS_PASS
OLD_H120_SINGLE_A_I_CALIBRATION_BLOCKED_PASS
MULTI_A_I_PUBLIC_CARD_MATERIALIZATION_PASS

PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS
PRIVATE_EVIDENCE_HASH_VERIFICATION_PASS
JOINT_LOG_GMM_REGION_EXTRACTION_PASS
PUBLIC_I1_RHO_REGION_CARTESIAN_SURFACE_PASS
SAME_CORRECTED_I1_FOR_M0_M1_PASS
```

After validation, Phase 3 must consume only `results/i1_cards_v2_rho_conditioned/public/`; it must never refit the GMM or read the private provider ledgers.
