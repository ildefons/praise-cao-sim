# Phase-5 V2 engineering-smoke completion and sequencing deviation

Date: 2026-10-06

## Status

This note records a protocol-order deviation. It does not modify any frozen
scientific threshold, seed bank, query, provider reconstruction, or method
outcome.

The Phase-5 V2 execution contract registered a mandatory non-scientific
engineering smoke before scientific execution. The original smoke runner
successfully exercised the four graph ASTs and several runtime invariants, but
did not fully exercise every registered minimum smoke clause before the I1,
Step-0, M1, and M2 scientific stages were executed.

The missing engineering checks are therefore completed now, after those
scientific reconstruction stages, with throwaway non-scientific artifacts only.

## Remediation rule

The completion smoke:

- reads and writes only under `first_science/phase5/smoke/`;
- does not read or write `results/`;
- uses no graph white-box evidence;
- does not change or repair I1, Step-0, M1, or M2;
- does not tune any scientific threshold or selection rule;
- records the sequencing deviation explicitly rather than claiming that the
  registered ordering was satisfied retrospectively.

If the completion smoke exposes a scientific implementation mismatch, no
scientific result will be silently repaired. The mismatch must be assessed
separately and any required replay must preserve the frozen scientific
contract.

## Completion checks

The supplement `run_phase5_mandatory_smoke_completion_v2.py` verifies:

1. the prior all-four-AST native smoke exists and is non-scientific;
2. an actual checkpoint/resume path;
3. manifest and SHA-256 production;
4. M3 Top1/Top3/Top14 nested readouts from one common member bank;
5. the LHS-MSE Top1 diagnostic selection path;
6. the global prediction-freeze hard block on incomplete coverage and success
   on complete coverage;
7. the exact B=1400 integer minimax allocation family and the frozen
   rank-1 N>=100 invariant;
8. passive diagnostic handling does not mutate the frozen base-smoke artifact.

## Scientific interpretation

Passing this completion smoke closes the engineering coverage gap but does not
erase the ordering deviation. The deviation remains part of Phase-5
provenance. All already observed scientific outcomes remain frozen unless a
separate contract-level implementation mismatch is demonstrated.
