# Phase 2 direct-trace design harness

This file is the executable-development mirror of the current PRAISE/CAO design document. It exists to prevent implementation convenience, historical code, or later method needs from silently filling an unresolved scientific-design gap.

## Binding source principle

The retained Phase-2 evidence is the frozen ProviderA/B/C provider-local request-ledger corpus extracted from the frozen physical regime on seeds `6000..6099`.

The active construction direction is therefore

`frozen physical regime -> provider-local evidence T_i -> explicitly defined I1_i`.

The provider-local evidence is the source. It is not a cue to invent an intermediate local admissibility envelope.

## Hard invariants

Until the design document explicitly freezes a public I1 representation, Phase 2 must not:

- derive `A_i` from `A_G`;
- split a global latency/cost/quality budget into provider budgets;
- define `A_i` by quantiles or percentiles;
- define `A_i` by min/max support extrema merely as a substitute for the rejected percentile rule;
- search local `A_i` values to obtain an attractive local sigma shape;
- inspect M0 or M1 outcomes to shape I1;
- infer an unspecified scientific choice from historical Phase-1 or Phase-2 code;
- materialize or hash-freeze a final I1 object whose public schema has not first been frozen in the design document.

If implementation requires one of those choices and the design does not specify it, the required behavior is **STOP AND RECONCILE THE DESIGN DOCUMENT**.

## What remains valid

The following remain valid and read-only:

- the Phase-2 acquisition protocol;
- the private ProviderA/B/C ledgers and their recorded SHA-256 hashes;
- the provider-local evidence audit;
- the benchmark time origin and workload context;
- the Phase-1 v2 white-box benchmark, which is not an input to I1 construction;
- the generic Phase-3 M0 topology-aware LCQ composition kernel and its unit tests.

The old single-`A_i` sigma-surface card code remains historical implementation evidence only. It is not an active final-I1 contract while the public representation is being reconciled.

## Current hard stop

The exact public representation `I1_i = F(T_i)` is **not yet frozen**. "Use the traces directly" fixes the evidence path and forbids an added calibration/search layer; it does not by itself authorize exposing raw private traces or choosing a replacement envelope.

Numerical M0/M1 integration is therefore blocked until the design document explicitly states the public I1 object and the transformation from `T_i` to that object. The M0 structural algebra may remain frozen and tested in parallel, but it may not dictate the I1 representation.
