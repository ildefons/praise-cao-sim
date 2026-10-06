# Phase-5 provider reconstruction restart V3

**Freeze date:** 2026-10-06

## Status

V3 is a pre-graph-WB method-development restart motivated by the observed instability of the V2 local reconstruction procedure. The V2 primary M2 and the RMSE15 secondary variant remain immutable provenance. V3 is **not** claimed prospective relative to those local reconstruction outcomes.

No graph prediction, graph white-box result, or final-WB result has been used to define V3.

## Why restart

V2 used a small N=25 local bank both to search the provider parameter space and to decide which candidates were sufficiently close to the M1 reference. The RMSE15 variant showed that widening the tolerance increased the number of search-compatible candidates but did not make the selected diverse candidates stable under fresh N=100 confirmation.

The V3 design removes the hard local compatibility threshold and separates candidate generation from robust representative selection.

## Provider reconstruction

For every provider in every provider world, run seven independent TPE fits. Each fit has 25 trials, 5 startup trials, and its own fresh disjoint N=15 simulation bank. The best trial from each fit becomes one candidate reconstruction.

The seven candidates are then re-evaluated on one common fresh N=100 bank. For each candidate retain its complete predicted public-I1 sigma vector over H>0.

Let the seven vectors be s_1,...,s_7 and define the behavioral centroid

```
s_bar = (1/7) sum_i s_i.
```

Rank candidates by mean squared distance to s_bar. Ties are broken by lower N=100 RMSE to the public I1 surface and then candidate ID. This is a **behavioral** centroid rule. The arithmetic mean of the hidden parameter vectors is never used.

A second fresh N=100 bank replays all seven frozen candidates for diagnostics only. Replay cannot change candidate identities, ranks, or M3 weights.

## Method instantiation on the common seven-candidate bank

- **M1:** one provider model, the behavioral-central rank-1 candidate.
- **M2:** three provider models, behavioral-central ranks 1, 2, and 3, equally weighted. The world ensemble therefore contains 3^3 = 27 joint models.
- **M3:** all seven provider candidates, weighted by the frozen Jeffreys-KL Gibbs rule with lambda=30. The full joint support contains 7^3 = 343 models. Rank the joint models by product weight and retain ranks 1..14 for the existing B=1400 graph budget and nested Top1/Top3/Top14 readouts.
- **M0:** unchanged, but rerun in the V3 prediction namespace so that all methods participate in one common blind-prediction freeze.

There is no arbitrary RMSE pass/fail threshold in V3. A provider becomes NOT_INSTANTIABLE only if the reconstruction is technically incomplete or invalid, not because a candidate missed a numerical closeness margin.

## Reuse and firewall

V3 reuses the already frozen public I1 cards, Step-0 eligibility decisions, and the already frozen V2 provider-domain registry. Those domains are treated as fixed V3 inputs and may not adapt further.

All V3 provider-reconstruction simulation evidence uses new seed banks. V2 N=25/N=100 local simulation results are not V3 scientific evidence.

The final-WB bank remains embargoed. V3 may reuse the same still-unseen final-WB seed bank after a new V3 global prediction freeze.

## Engineering gate

Before any V3 scientific reconstruction, run the registered V3 reconstruction smoke. Smoke output is explicitly marked `scientific_evidence=false` and must never be read by scientific stages.
