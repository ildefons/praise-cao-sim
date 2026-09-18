# M2-B3: frozen A4 portfolio graph propagation

## Scientific question

M2-A4 established that the same public I1 card admits multiple independently
confirmed provider reconstructions. M2-B3 asks whether that local inverse
ambiguity propagates through the G0 composition into materially different
predicted graph survival/compliance surfaces.

This stage is prediction-only. It does not use graph reference outcomes to choose
or alter candidates.

## Frozen variants

The baseline is BASE_M1, using the confirmed M1 anchor for all three providers.

Nine one-at-a-time substitutions are then evaluated:

- ProviderA: ProviderA_GP_006, ProviderA_GP_035,
  ProviderA_TPE_base_trial079
- ProviderB: ProviderB_LHS_039, ProviderB_GP_031,
  ProviderB_TPE_base_trial068
- ProviderC: ProviderC_LHS_038, ProviderC_GP_014,
  ProviderC_TPE_base_trial037

Only one provider changes in each variant. The other two remain at their M1
anchors. No 3x3x3 factorial is run at this stage.

## Graph evidence

The full run uses graph seeds 28000..28099, 100 trajectories per variant, with
common random numbers across all ten variants. This is a fresh graph seed bank
relative to the earlier M1 and M2 graph stages.

The public-I1-induced graph admissibility boundary is identical for every
variant. Therefore M2-B3 isolates changes in predicted sigma_G that arise from
the reconstructed provider dynamics, not from changing A_G.

## Diagnostics

The runner reports:

1. whole-surface MAE/RMSE/mean delta/max absolute delta versus BASE_M1;
2. the same diagnostics separately by rho;
3. pairwise graph-surface spread among each provider's three A4 alternatives;
4. request-level latency/cost/quality summaries.

There is deliberately no binary materiality threshold.

## Execution

From first_science/phase4:

    python m2_b3_a4_portfolio_graph.py --prepare-only

Then run the isolated smoke test:

    python m2_b3_a4_portfolio_graph.py --smoke

The smoke test writes to results/m2_b3_a4_portfolio_graph_smoke_v1 and cannot
contaminate the full output.

If both pass:

    /usr/bin/time -v python m2_b3_a4_portfolio_graph.py \
      2>&1 | tee results/m2_b3_a4_portfolio_graph_v1/run.log

Completed per-variant ledgers are reused on restart, provided their exact graph
seed bank matches the requested run.

## Gate after M2-B3

First inspect spread versus BASE_M1 and within the three alternatives for each
provider. Only after those predictions are frozen should graph reference outcomes
be used for an accuracy comparison or a 3x3x3 factorial be considered.
