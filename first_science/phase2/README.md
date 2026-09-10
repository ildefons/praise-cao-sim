# PRAISE first science - Phase 2 / I1

**Status: FROZEN for the first controlled I1-M0/I1-M1 comparison.**

Phase 2 owns construction of the provider information object `I1`. The accepted construction deliberately separates rho-conditioned region construction from sigma estimation at trajectory level.

## Frozen evidence partition

Two private provider-local corpora are used:

- `T_i^Gamma`: 100 trajectories, seeds `6000..6099`; used only to fit the joint model and construct `A_i(rho_region)`.
- `T_i^sigma`: 100 independent trajectories, seeds `6100..6199`; used only to estimate `sigma_i(A_i(rho_region),H;rho_query)` after the regions are fixed.

The seed banks are required to be disjoint. The materializer hash-verifies both corpora, verifies that the sigma acquisition manifest matches its frozen acquisition contract, and refuses identical provider-corpus hashes. Phase-1 white-box outputs are forbidden from I1 construction.

The public object is

`I1_i = ({A_i(rho_region)}, W_i, R_region, R_query, {sigma_i(A_i(rho_region),H;rho_query)})`

with the invariant

`A_i <- T_i^Gamma` and `sigma_i <- T_i^sigma`.

M0 and M1 receive exactly the same finished public cards. Neither method may read either private corpus.

## Frozen rho-conditioned local regions

The historical `results/i1_cards_v1/` branch used one fixed local region per provider and is retained only for provenance.

The accepted construction is

`T_i^Gamma -> joint log(L,C) GMM -> A_i(rho_region)`

followed independently by

`T_i^sigma -> sigma_i(A_i(rho_region),H;rho_query) -> public I1_i`.

For the current benchmark `Q=0.5` is degenerate. Each provider fits a full-covariance Gaussian mixture in `(log L, log C)`, selecting `K=1..4` by minimum BIC. From one deterministic `N=100000` sample of the fitted model, the code extracts the minimum-area origin-anchored rectangle `[0,l] x [0,c]` containing at least the requested probability content. Regions are constrained to be nested as `rho_region` increases. Non-degenerate Q is deliberately rejected in this version.

The finite region-content support is

`R_region={0.95,0.975,0.9833333333333333,0.99,0.995}`.

`rho_region=1` is not used because a Gaussian mixture has unbounded support and therefore no finite exact 100% probability-content rectangle.

The trajectory-compliance query threshold is a separate coordinate:

`sigma_i(A_i(rho_region),H;rho_query)=P(c_i(A_i(rho_region),H)>=rho_query)`.

The complete Cartesian `A_i(rho_region) x rho_query x H` surface is materialized. The first controlled comparison uses only

`rho_region=rho_query=rho_i=rho_G`.

## Frozen provenance

The formal freeze record is

`phase2_i1_rho_conditioned_freeze_manifest_v1.json`.

It records the evidence split, region construction, rho support, public I1 manifest hash, information firewall, and the rule that this construction must not be changed merely to improve M0 or M1 results.

Historical files remain versioned for provenance, but the authoritative public handoff is

`results/i1_cards_v2_rho_conditioned/public/`.

Phase 3 and M1 must consume that handoff read-only. They must never fit the GMM, read `T_i^Gamma`, read `T_i^sigma`, or reconstruct `A_i` from private evidence.

## Validation markers already required by the frozen contract

The accepted implementation is guarded by, among others:

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
PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS
REGION_EVIDENCE_HASH_VERIFICATION_PASS
SIGMA_EVIDENCE_HASH_VERIFICATION_PASS
TRAJECTORY_DISJOINT_REGION_SIGMA_EVIDENCE_PASS
PUBLIC_I1_RHO_REGION_CARTESIAN_SURFACE_PASS
SAME_CORRECTED_I1_FOR_M0_M1_PASS
```

Reopen Phase 2 only for a concrete scientific or implementation defect.
