# PRAISE CAO Simulator

Simulation environment for studying composition of Composable Autonomic
Offerings (CAOs) under performance, sustainability and cost constraints.

The simulator builds on AICon/YAFS and extends it only where required for
the PRAISE composition experiments.

Initial planned extensions:

- stochastic per-request computational demand;
- recursive parallel composition (`ParAll`);
- synchronized multi-message activation (`JoinAll`);
- request lineage for nested compositions;
- sustainability, energy and cost metrics.

## Baseline

Simulation substrate:

- AICon: https://github.com/ildefons/aicon
- YAFS / SimPy discrete-event simulation