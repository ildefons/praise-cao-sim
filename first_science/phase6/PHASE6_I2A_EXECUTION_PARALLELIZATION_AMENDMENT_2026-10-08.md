# Phase-6 execution-only parallelization amendment

**Date:** 2026-10-08

The initial Phase-6 I2a provider-audit runner was started sequentially. Before
the first provider completed, two candidate scores were printed for
P1/ProviderA:

- FIT1 mean_W1 = 0.005383
- FIT2 mean_W1 = 0.016517

Execution was stopped to avoid unnecessary wall time.

After those two partial outputs had been observed, the runner was changed only
for execution engineering:

1. add `--workers` with default 4 and parallelize independent
   (provider-world, provider) audits with `ProcessPoolExecutor`;
2. add deterministic per-candidate checkpoints so an interrupted provider can
   resume without recomputing completed candidates;
3. reuse an already frozen completed provider audit on restart.

No scientific element changed. In particular, this amendment does **not**
change:

- I2a definition or public representation;
- provider evidence;
- frozen candidate family or parameters;
- candidate simulation seeds;
- N=100 candidate budget;
- region or horizon support;
- Wasserstein-1 discrepancy;
- aggregation rule;
- ranking or tie break;
- graph firewall;
- any M2/M3 rule.

The two observed partial scores therefore had no influence on the scientific
protocol. They motivated only parallel execution and resumability.
