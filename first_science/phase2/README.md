# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. The current rho-conditioned candidate deliberately separates region construction from sigma estimation at trajectory level.

## Frozen evidence partition

Two private provider-local corpora are used:

- `T_i^Gamma`: the existing 100-trajectory corpus acquired with seeds `6000..6099`. It is used only to fit the joint model and construct `A_i(rho_region)`.
- `T_i^sigma`: a new independent 100-trajectory corpus acquired with seeds `6100..6199`. It is used only to estimate `sigma_i(A_i(rho_region),H;rho_query)` after the regions are fixed.

The seed banks are required to be disjoint. The rho-conditioned materializer hash-verifies both corpora, verifies that the sigma acquisition manifest exactly matches its frozen acquisition contract, and refuses identical provider-corpus hashes. Phase-1 white-box outputs are forbidden from I1 construction.

The resulting public object is therefore

`I1_i = ({A_i(rho_region)}, W_i, R_region, R_query, {sigma_i(A_i(rho_region),H;rho_query)})`

with the important provenance invariant

`A_i <- T_i^Gamma` and `sigma_i <- T_i^sigma`, with `T_i^Gamma` trajectory-disjoint from `T_i^sigma`.

M0 and M1 receive exactly the same finished public cards. Neither method may read either private corpus.

## Rho-conditioned local regions

The historical materialization `results/i1_cards_v1/` used one fixed local region per provider, selected by the earlier `H*=120`, `rho_anchor=.95`, `sigma_target=.95` first-crossing calibration. That branch is retained for provenance.

The corrected candidate path is

`T_i^Gamma -> joint log(L,C) GMM -> A_i(rho_region)`

followed independently by

`T_i^sigma -> sigma_i(A_i(rho_region),H;rho_query) -> public I1_i`.

For the current benchmark, `Q=0.5` is degenerate. Each provider fits a full-covariance Gaussian mixture in `(log L, log C)`. The number of components is selected by minimum BIC over `K=1..4`. From one deterministic `N=100000` sample of the fitted joint model, the code extracts the minimum-area origin-anchored rectangle `[0,l] x [0,c]` containing at least the requested model probability content. Regions are constrained to be nested as `rho_region` increases. Non-degenerate Q is deliberately rejected in this version rather than generalized without a frozen rule.

The finite region-content support is

`R_region={0.95,0.975,0.9833333333333333,0.99,0.995}`.

`rho_region=1` is not used because a Gaussian mixture has unbounded support and therefore no finite exact 100% probability-content rectangle.

The trajectory-compliance query threshold is a separate coordinate:

`sigma_i(A_i(rho_region),H;rho_query)=P(c_i(A_i(rho_region),H)>=rho_query)`.

The complete Cartesian `A_i(rho_region) x rho_query x H` surface is materialized. The official M0 comparison first uses only the diagonal

`rho_region=rho_query=rho_i=rho_G`.

## Versioned implementations

Historical fixed-region branch, retained for provenance:

- `config_phase2_i1_provider_card_v2.json`
- `i1_local_region.py`
- `materialize_frozen_i1_cards.py`
- generated `results/i1_cards_v1/`

Rho-conditioned independent-evidence candidate:

- region acquisition: `config_phase2_i1_acquisition_v1.json`
- sigma acquisition: `config_phase2_i1_sigma_acquisition_v1.json`
- card contract: `config_phase2_i1_provider_card_v3_rho_conditioned.json`
- region construction: `i1_rho_conditioned_region.py`
- materialization: `materialize_rho_conditioned_i1_cards.py`
- generated public cards: `results/i1_cards_v2_rho_conditioned/public/`

The generic `i1_provider_card.py` is reused. Fitted GMM parameters, BIC diagnostics, synthetic model samples, both private ledgers, and all acquisition seeds remain private.

## Validation and execution

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

git pull origin first-science-phase1

# Structural/model guards
python -c "import sklearn; print(sklearn.__version__)"
python first_science/phase2/test_i1_rho_conditioned_region.py
python first_science/phase2/test_materialize_rho_conditioned_i1_cards.py

# One-time independent T_i^sigma acquisition.
# Do NOT rerun the existing T_i^Gamma corpus.
python first_science/phase2/i1_provider_acquisition.py \
  --config first_science/phase2/config_phase2_i1_sigma_acquisition_v1.json \
  --output first_science/phase2/results/i1_sigma_acquisition_v1

# Materialize corrected public I1 cards. This now refuses to run without both
# disjoint, hash-verified evidence corpora.
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
TRAJECTORY_DISJOINT_REGION_SIGMA_CONTRACT_PASS
REGION_CORPUS_FOR_SIGMA_ESTIMATION_BLOCKED_PASS

PHASE2_I1_ACQUISITION_RUN_PASS

PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS
REGION_EVIDENCE_HASH_VERIFICATION_PASS
SIGMA_EVIDENCE_HASH_VERIFICATION_PASS
TRAJECTORY_DISJOINT_REGION_SIGMA_EVIDENCE_PASS
JOINT_LOG_GMM_REGION_EXTRACTION_PASS
PUBLIC_I1_RHO_REGION_CARTESIAN_SURFACE_PASS
SAME_CORRECTED_I1_FOR_M0_M1_PASS
```

After this materialization, Phase 3 must consume only `results/i1_cards_v2_rho_conditioned/public/`. It must never fit the GMM, read `T_i^Gamma`, read `T_i^sigma`, or reconstruct `A_i`.

Do not start the I1-M1 numerical fit until the newly materialized independent-evidence I1 cards and the resulting Phase-3 M0 two-axis output have been inspected.
