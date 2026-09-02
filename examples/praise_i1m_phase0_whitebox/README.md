# PRAISE I1-M0/M1 — Implementation Phase 0

**Purpose:** validate the white-box provider observation/survival kernel before reference-regime search or any I1/M0/M1 implementation.

Expected baselines:
- AICon/YAFS: `6eabfa7` (`Fix QoS execution semantics and seeded uniform distribution`)
- PRAISE-CAO: `fbf722e` (`Validate PRAISE dependency scope and native request semantics`)

## Scope

One deterministic periodic source sends requests to one stochastic native AICon/YAFS provider. The provider produces outcomes causally through the simulator:

- `L = time_out - time_reception = wait + service` (local provider latency; network excluded),
- `C = COST(node) * service`,
- `Q = x`, with `D_exec = x * D_nominal` in the AICon core.

The native demand generator is gamma with a smoke-test mean/CV. These are **diagnostic defaults**, not the final scientific reference regime.

Phase 0 does **not** construct I1 cards, M0, M1, A/B/C providers, Fpre/Fpost, or run reference-regime optimization.

## Files

- `main.py`: native AICon/YAFS experiment, event-ledger extraction and fast self-checks.
- `survival.py`: simulator-independent first-violation/censoring semantics.
- `test_survival.py`: hand-checkable unit tests of survival semantics.
- `config_phase0.json`: smoke-test defaults.
- `logging.ini`: local logging configuration.
- `results/`: generated output; do not commit.

## First-violation semantics

For `A={L<=l, C<=c, Q>=q}`:

- latency fails at `arrival + l` if completion has not occurred by the deadline;
- cost and quality fail at request completion;
- an unfinished request whose latency deadline has not passed at simulation stop is right-censored;
- horizons greater than the trajectory stop time are rejected;
- `sigma(H)` uses the strict convention `P(T_violation > H)`.

The ledger explicitly retains requests still queued at simulator stop by inspecting the provider's YAFS input store, because those requests do not yet have a `COMP_M` metric row.

## Local smoke test

From the example directory, with your AICon fork on `PYTHONPATH`:

```bash
export PYTHONPATH="$HOME/praise/aicon/src/yafs/src:$PYTHONPATH"
python test_survival.py
python main.py --clean
```

Expected PASS markers:

```text
PHASE0_SURVIVAL_UNIT_TESTS_PASS
PHASE0_REPRODUCIBILITY_PASS
PHASE0_NETWORK_FIREWALL_PASS
PHASE0_QUEUE_CAPTURE_PASS ...
PHASE0_NATIVE_SMOKE_PASS
```

## Longer local test after smoke passes

A first longer engineering run (still **not** reference calibration):

```bash
python main.py --clean --n-trajectories 100 --stop-time 200
```

Do not interpret the included `A_test` or gamma/workload values scientifically. Their only purpose is to exercise the machinery.
