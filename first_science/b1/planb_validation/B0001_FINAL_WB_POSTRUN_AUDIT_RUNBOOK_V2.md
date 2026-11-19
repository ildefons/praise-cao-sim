# B0001 N=1000 final white-box reference: independent mechanical audit

The 12-cell reference runner has reported completion, but **evaluation stays
blocked until this separate post-run audit passes**. The seven predictor
families (84 method/condition pairings) are immutable. Do not retune or repair
them after viewing the white-box reference.

## Pull and audit

In your local `~/praise/praise-cao-sim` checkout:

```bash
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/audit_b0001_final_wb_seven_arm_v2.py \
  --authorization ~/praise/planb_b0001_final_wb_authorization_seven_arm_v1 \
  --reference ~/praise/planb_b0001_final_wb_seven_arm_v1 \
  --graph ~/praise/planb_b0001_graph_isolated_v1 \
  --staging ~/praise/planb_b0001_public_inputs_v1 \
  --audit ~/praise/planb_b0001_postrun_audit_v1 \
  --seven-arm ~/praise/planb_b0001_seven_arm_blind_freeze_v1 \
  --four-arm ~/praise/planb_b0001_four_arm_graph_science_v1 \
  --out ~/praise/planb_b0001_final_reference_audit_v2
```

Expected terminal success marker:

`B0001_SEVEN_ARM_FINAL_REFERENCE_MECHANICAL_AUDIT_V2_PASS`

The output is a **new file**, not a replacement for any frozen input:

`~/praise/planb_b0001_final_reference_audit_v2/b0001_final_reference_seven_arm_postrun_audit_v2.json`

The audit fails closed if any source is absent, if file hashes differ, if the
global reference differs from the copy archived independently on November 19,
or if any of the seed/query/curve/Wilson checks fail. It refuses to overwrite
an existing audit JSON. The script performs **no simulations and no model
evaluation**; it does rehash frozen predictor files. No existing reference,
predictor, authorization, policy, or manifest file is changed.

The external global-reference freeze is anchored to SHA-256
`37a0bb58a31593ed62e72b88e3f693ee5e20d2e421d6e3d9e7a601627f8101ff`,
calculated from the separately uploaded `b0001_final_wb_global_freeze.json`.

## Audit scope and limits

Checks: all 12 reference manifests and their ledger/curve SHA-256 hashes;
exact 1,000 seeds per cell; 15 queries x 49 horizons per cell; binary-success
rates and Wilson 95% confidence intervals; the original physical generator
source hash and selected private contract hashes; all seven pre-WB predictor
freezes; and a pinned externally archived hash of the global reference freeze.

This is **mechanical integrity verification**, not independent recalculation
of trajectory-level compliance from raw requests, not a repeat simulation,
and not yet a scientific performance analysis. A successful result authorizes
the next, separately frozen seven-method evaluation protocol; it does not
declare the seven-method study complete.

Please share the final terminal output and the single audit JSON. Do not
re-run the 12,000 trajectories or modify frozen predictions.
