# Pilot-to-retrospective M3 deviation audit (2026-10-20)

**Status:** source-level forensic comparison of the frozen PRAISE contracts and uploaded retrospective evidence. No simulator-parity run has yet been performed in this environment.

## Key answer

The October retrospective reproduces the central pilot M3 **estimator**, but not the original pilot's complete **experimental pipeline**. Even restricting to G_PAR, the operating worlds, candidate domains, provider I1 observations, graph runtime path, seeds and graph-level query regions differ. The correct causal explanation for the larger MAE is therefore not identified.

## Verified provenance matrix

| Layer | Phase-4 G0 pilot | October B1 G_PAR retrospective | Classification |
|:--|:--|:--|:--|
| Providers | D300e6, delta=.2; mean services .12/.15/.18s; utilizations .60/.75/.90 | P1 .825/.825/.825, P3 .90/.90/.90, P4 .81/.90/.99 | **Different truth** |
| Graph | Source -> Fpre -> ParAll(A,B,C) -> Fpost | G_PAR is same logical AST | Same logical structure |
| Simulator | Phase-3 m1_graph_simulator_v2, native G0 code path | Phase-5 phase5_graph_simulator_v2, AST compiler | **Different code path, parity untested** |
| Surrogate IPT | 1e6 numerical gauge, fixed Fpre/Fpost 1e9 | 1e9 gauge for providers and fixed stages | **Different gauge, parity untested** |
| Public I1 cards | Original Phase-2 card and random acquisition | New cards for P1/P3/P4 | **Different public observations** |
| Candidate coordinates | Nonadaptive LHS 48/provider, seed 20260917+provider_index*100003 | Same imported LHS routine and seed rule | Same unit-cube design |
| Parameter domains | Original declared M1 bounds, expanded Provider C | Frozen Phase-5 M1 world-specific domain registry | **Different mapped candidates** |
| Local candidate simulation | Shared native local-score routine, 100 trajectories, seeds 35000..35099 | Same routine and count, seeds 52300..52399 | Different MC bank |
| Gibbs energy | Jeffreys-smoothed Bernoulli KL on complete public I1 surface, H>0 | Same formula | Same mathematical rule |
| Lambda | 30, selected by 5-fold public-I1 CV on original pilot | Fixed transferred value 30 | **New-world CV not repeated** |
| Joint weighting | Product of provider-normalized Gibbs weights | Same | Same mathematical rule |
| TopK | Minimum prefix attaining >= .999 retained mass, obtained K14 | Top14 fixed independently of retained mass | **Selection policy changed** |
| Monte Carlo allocation | Greedy minimax integer variance bound, B1400 | Same formula, B1400 | Matched |
| Graph seeds | From 3,600,000 in rank-indexed blocks | From 8,100,000 in rank-indexed blocks | Different MC stream |
| SLA query regions | 15 calibrated regions for pilot G0 | 15 new calibrated regions per eligible world and graph | **Different evaluation targets** |
| Graph sigma readout | build_empirical_graph_sigma_curve | Imports the same function | Same scoring semantics |
| WB | N200 | N1000 | Different finite-reference noise |

## Quantitative checks from the uploaded evidence

The LHS *normalized* coordinates are identical across P1/P3/P4 for each corresponding provider and candidate index. The actual physical candidate parameters change because the domain changes.

The pilot's adaptive 99.9%-mass rule gave K14 with retained mass 0.999174. Reapplying the rule to the new complete weighted banks would require **K19 in P1, K22 in P3 and K15 in P4**. Fixed K14 retains 0.996404, 0.996771 and 0.998925, respectively. Since these omitted-mass bounds are below 0.0036 (relative to exact inferred-bank expectation), truncation alone cannot explain the observed deviations of approximately 0.1 to 0.2 from the white-box graph curves. Monte Carlo uncertainty is separate.

Pilot G0 original Top14 B1400 MAE: 0.03037.
New original-style Top14 B1400 on G_PAR alone: P1 0.24468, P3 0.25108, P4 0.10975.
New original-style Top14 B1400 over 12 cases: 0.154155.

## Reproduction ladder

**First, no expensive simulation:** audit original versus new numeric inputs, source and candidate domain mapping. Core KL and allocation formulas checked in source; individual archived solver trajectories have not been regenerated.

**Second, run the small simulator-parity diagnostic** audit_pilot_graph_parity_v1.py. With identical fixed surrogates, workload and seed, it compares native request ledgers from old G0 and new G_PAR at IPT=1e6, then compares Phase-5 provider IPT gauges 1e6 and 1e9. Differences would require investigating native graph execution before attributing deterioration solely to new provider worlds.

**Third, only if needed**, establish a carefully controlled bridge on the *original provider world* using original public I1 cards, candidate domain, 15 original SLA queries and frozen native models. At each step hold everything else fixed. It would be a retrospective diagnosis, not a new holdout. Do not commit any new claims until this bridge is verified.

Do not restart a 12-cell graph battery or reuse hidden truth in an operational estimator; retain the original PPG firewall and frozen archives.

## Authoritative sources

- Phase4 candidate design: first_science/phase4/m2_a2_nonadaptive_coverage.py
- Phase4 local: first_science/phase4/m3_local_weighting.py, m3_lambda_cv_v3.py
- Phase4 graph: first_science/phase4/m3_v4_dominant_mass_graph.py
- Phase4 protocols: config_phase4_m3_v4_dominant_mass_graph_v1.json, config_phase4_sigma_regime_battery_step0_v2.json
- New reconstruction/graph: first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py
- New domains: first_science/phase5/run_phase5_m2_reconstruction_v2.py
- Native graph paths: first_science/phase3/m1_graph_simulator_v2.py and first_science/phase5/phase5_graph_simulator_v2.py
- New worlds/regions: first_science/phase5/config_phase5_recoverability_battery_v2.json
