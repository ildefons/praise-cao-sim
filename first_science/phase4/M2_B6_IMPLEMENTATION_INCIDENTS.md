# M2-B6 implementation incidents

**Date:** 21 September 2026.

This note records implementation-only failures encountered after the B6 evaluation protocol and metrics were frozen. Neither incident changed B5 predictions, M2 members, ensemble weights, admissibility regions, evaluation metrics, or white-box data.

## Incident 1: exact rho-support equality

The first evaluation attempt stopped before opening the Phase-1 graph white-box ledger because serialized B5 rho values were compared to public-I1 rho values using exact Python list equality. The recurring rho value near 0.9833333333333333 can differ by a last-bit floating representation after CSV round-trip.

Fix: compare rho and horizon support using the already-declared absolute tolerance `1e-12` and zero relative tolerance.

Commit: `989b43c6b1a12acfc0d9ac0dada3618bc3ac2cbf`.

## Incident 2: exact floating-point join keys

After the prediction-freeze manifest existed, the second evaluation attempt opened the frozen Phase-1 graph white-box ledger and computed the white-box curves, but stopped before any B6 comparison metrics were materialized because the merge still used exact floating-point `rho_global` values as keys.

This failure occurred after white-box access. The already-created B6 prediction-freeze manifest therefore remains the authoritative pre-white-box freeze and must not be regenerated after this incident.

Fix: snap only serialized `rho_global` and `horizon` support coordinates to the exact frozen B5 support representatives after verifying a unique match within `atol=1e-12, rtol=0`. Join on those canonical support coordinates. Compare white-box and B5 `A_G` components separately with the same tolerance rather than using floating-point `A_G` values as exact merge keys.

No prediction values, white-box values, method definitions, weights, or evaluation metrics are modified by this normalization.

Commit: `3134e99e3da7bafaf56ee7583f0871716523f51b`.

## Continuation rule

Do not rerun `--prepare-only` after Incident 2. Pull the technical fix and rerun only the B6 evaluation command. The evaluator must validate the existing pre-white-box freeze hashes before proceeding.
