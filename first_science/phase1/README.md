# PRAISE first science - Phase 1

**Status: FROZEN for the first controlled I1-M0/I1-M1 comparison.**

## Purpose

Phase 1 supplies the technology-neutral white-box reference for the composed system. AICon/YAFS execution of the physical graph is the sole white-box truth generator. Phase-1 outcomes may be used only for benchmark construction/confirmation and later external evaluation; they are forbidden from Phase-2 I1 construction and from M0/M1 reconstruction.

## Authoritative current sigma semantics

The current Phase-1 v2 benchmark uses trajectory-level cumulative request compliance, not first-passage/no-violation survival.

For admissibility region `A`, horizon `H`, and required cumulative-compliance fraction `rho`, define `c_G(A,H)` as the fraction of requests **decided by H** that satisfy `A`. A request is decided at completion if it completes within its latency deadline, otherwise at the latency deadline. Requests not yet decided by H are excluded from the denominator. Before any request is decided, the compliance fraction is `1.0`.

The authoritative query is

`sigma_G(A,H;rho) = P(c_G(A,H) >= rho)`.

A trajectory can fall below `rho` and later recover when additional compliant requests are decided. Therefore `sigma_G(A,H;rho)` is allowed to be non-monotone in `H`.

The implementation is in `sla_compliance_analysis.py`. The older `T_violation`/first-event survival analysis is retained only as historical v1/development provenance and must not be used to interpret the current Phase-1 v2, Phase-2, or Phase-3 experiment.

## Frozen physical graph and provider semantics

Reference graph:

`Fpre -> ParAll(A,B,C) -> Fpost`

`Fpre` and `Fpost` are deterministic. A/B/C use the same native service-module family with controlled provider offsets. Stochasticity enters through native per-invocation instruction demand. `L` and `C` are generated natively by AICon/YAFS rather than directly sampled. In the current benchmark `Q=0.5` is degenerate.

The matched physical regime used by the frozen v2 AR battery is:

- `physical_setting_id = D300000000_d0.200`;
- `center_instruction_mean = 300000000`;
- `dispersion = 0.2`;
- root workload period `0.2 s`;
- horizon domain `[0,240] s` with reporting step `5 s`.

## Frozen Phase-1 v2 admissibility-region battery

The authoritative manifest is:

`phase1_v2_ar_freeze_manifest_v1.json`

It freezes three diagnostic global regions in the same matched physical regime:

| Role | Case | L max | C max | Q min |
| --- | --- | ---: | ---: | ---: |
| latency | `V2_LATENCY` | 0.68855284199994315 | 2.60390295517990822 | 0.5 |
| cost | `V2_COST` | 0.74739413900001495 | 2.13979268099999986 | 0.5 |
| mixed | `V2_MIXED` | 0.74739413900001495 | 2.17409932499999980 | 0.5 |

The v2 selection used the cumulative-compliance query at nominal/stress rho values and was frozen before M0/M1 evaluation. The final confirmation uses an untouched paired `N=100` bank, seeds `7000..7099`, with no recalibration of the selected regions.

## Current firewall

- Phase 1 must not be reopened merely to improve M0 or M1 performance.
- Phase 2 may not use Phase-1 white-box outcomes to construct I1.
- M0 and M1 may consult Phase-1 white-box truth only after their outputs have been formed, for external evaluation.
- Historical first-violation utilities and earlier finalist/calibration artifacts remain provenance only.

See also `SIGMA_SEMANTICS_AUDIT.md` and the frozen v2 manifest for the exact current accounting contract.
