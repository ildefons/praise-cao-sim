# Pilot evidence-strengthening audit v1

**Classification:** post-hoc read-only analysis of already-frozen pilot evidence.  
**New provider simulation:** none.  
**New graph simulation:** none.  
**New white-box simulation:** none.

This audit packages three items from the evidence-strengthening plan: hidden-parameter comparison, signed prediction bias by regime, and a white-box-reference-noise-adjusted discrepancy diagnostic. The existing Top1/Top3/Top14 validation remains the authoritative support-size analysis.

## 1. Hidden theta comparison

The hidden pilot provider parameters, expressed in the surrogate coordinates, are:

- ProviderA: mu=0.12 s, kappa=3, CV=0.3
- ProviderB: mu=0.15 s, kappa=3, CV=0.3
- ProviderC: mu=0.18 s, kappa=3, CV=0.3

Neither M1 nor M3-Top1 generally recovers these hidden coordinates. The most extreme M1 mismatch is ProviderC: mu=0.002682 s (0.0149x truth), kappa=87.307 (29.10x truth), CV=0.994 (3.31x truth). Top1 is much closer to truth for ProviderC mu and CV, but its kappa=0.552 is still only 0.184x the hidden value. For ProviderA, Top1 is not closer in every coordinate: mu=0.02208 s (0.184x truth) and CV=1.514 (5.05x truth), while kappa=4.936 (1.65x truth).

This supports the descriptive statement that graph-predictive accuracy does not require recovery of the hidden provider parameters in this pilot. It does **not** establish a formal parameter-identifiability theorem.

The existing public-I1 replay audit also prevents a simpler explanation based on uniformly better local fit. For ProviderA, M1 has lower local Bernoulli-KL than Top1 (0.2001 vs 0.2592); Top1 is better for ProviderB (0.1105 vs 0.1401) and ProviderC (0.08795 vs 0.2732). Thus M1-vs-Top1 remains a compound contrast in candidate generation/search and scoring, not an isolated test of one factor.

## 2. Signed bias by Easy/Mid/Stress

Using H=60..240 and mapping the historical pilot regime labels G0/G1/G2 to Easy/Mid/Stress:

| Method | Easy bias | Mid bias | Stress bias |
|---|---:|---:|---:|
| M1 | +0.0410 | +0.1505 | +0.3640 |
| M2 | +0.0105 | +0.0308 | +0.1009 |
| M3-Top1 | +0.0230 | +0.0314 | +0.0205 |
| M3-Top3 | +0.0242 | +0.0356 | +0.0263 |
| M3-Top14 | +0.0236 | +0.0350 | +0.0261 |

The main mechanism visible in signed error is therefore not merely decreasing MAE. M1 becomes strongly optimistic as the query becomes harder; M2 attenuates but does not remove that trend; all three M3 support readouts keep the positive bias small and comparatively stable. M0 remains strongly conservative where operationally applicable and is not applicable throughout Stress.

## 3. WB-reference-noise-adjusted discrepancy

For each point, the final WB estimator uses N=200 trajectories. Treating sigma_WB as a Bernoulli proportion, the unbiased plug-in estimate of the variance of the sample mean is

`v_WB = sigma_WB*(1-sigma_WB)/(N-1)`.

For a fixed prediction, observed squared discrepancy contains WB sampling variance. We therefore report

`MSE_WB-adjusted = max(0, MSE_observed - mean(v_WB))`

and its square root. This is a **reference-noise adjustment only**. It does not remove Monte Carlo noise in the method prediction and is not an estimator of a theorem-level truth error.

Whole-battery H=60..240 results:

| Method | raw RMSE | WB-noise-adjusted RMSE |
|---|---:|---:|
| M1 | 0.2307 | 0.2293 |
| M2 | 0.0941 | 0.0905 |
| M3-Top1 | 0.0341 | 0.0223 |
| M3-Top3 | 0.0357 | 0.0247 |
| M3-Top14 | 0.0358 | 0.0248 |

For Stress, the corresponding M3 adjusted RMSE values are 0.0107 (Top1), 0.0186 (Top3), and 0.0198 (Top14). Estimated WB sampling variance accounts for about 91%, 77%, and 75% of the respective raw MSEs in that regime. This makes the tiny observed differences among M3 support sizes even less suitable for ranking.

The already-frozen trajectory-cluster bootstrap gives the complementary comparative result for M2 versus M3-Top14 B=1400. The whole-battery delta MAE (M2 minus M3) has 95% bootstrap interval [0.0266, 0.0433]. The Easy interval [-0.0100, 0.0117] crosses zero, while Mid [0.0121, 0.0463] and Stress [0.0569, 0.0798] remain positive. Thus the evidence supports a robust M3 improvement over M2 in Mid/Stress, not a universal advantage in Easy.

## 4. Manuscript-use interpretation

The strongest concise synthesis from the frozen pilot is:

> The inverse problem is parameter-non-identifying but can still be prediction-sufficient: markedly different public-I1-compatible latent reconstructions can yield accurate graph-level SLA predictions. In the pilot, prediction saturates at very small M3 support, while faithful representation of the reconstructed Gibbs distribution requires more support. Signed-error analysis further shows that the main failure of the single M1 reconstruction is increasing optimism as the SLA query tightens.

Keep the scope explicit: this is one provider world, one physical graph, and the frozen Easy/Mid/Stress query battery. The prospective Phase-5 battery is what tests whether these regularities generalize.
