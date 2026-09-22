# M2 G2 Step-0 calibrated validation

**Status:** frozen contract implemented through Step-0 calibration.  
**M2 method status:** unchanged and frozen.  
**G2 prediction status:** forbidden until Step-0 calibration passes and freezes A_G2.

## Purpose

G1 remains a valid prospective stress test but its white-box sigma surface is
floor-degenerate for the intended dependable-service regime. G2 therefore
predeclares a Step-0 experimental-design calibration before comparing M0/M1/M2.

Step 0 may choose only the global admissibility-region battery. It may not read,
run, fit, select or reweight M0, M1 or M2.

## Frozen G2 public condition

Logical composition:

```
Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost
```

Provider-branch propagation delay is symmetric:

```
PR_A = PR_B = PR_C = 0.004 s
```

The uncalibrated base boundary is:

```
l_G2_base = 0.020003 + max(l_A,l_B,l_C)
c_G2_base = 0.03 + c_A + c_B + c_C
q_G2_base = min(q_A,q_B,q_C)
```

Candidate regions only relax this base:

```
l_candidate = s_L * l_G2_base,  s_L = 1.00..1.80 by 0.01
c_candidate = s_C * c_G2_base,  s_C = 1.00..1.50 by 0.01
q_candidate = q_G2_base
```

There are 81 x 51 = 4131 candidates per rho and five frozen rho slices.

## Frozen Step-0 gate

Calibration uses every frozen horizon from H=60 through H=240.

A candidate is feasible only if:

```
min sigma >= 0.90
0.93 <= mean sigma <= 0.98
0.90 <= sigma(H=240) <= 0.97
max(sigma)-min(sigma) >= 0.03
at least 25% of diagnostic points have sigma <= 0.98
```

Among feasible candidates, select minimum

```
sqrt((s_L-1)^2 + (s_C-1)^2)
```

with frozen tie breakers: mean sigma closest to 0.95, H240 sigma closest to
0.95, then smallest s_L and smallest s_C.

No prediction error and no M0/M1/M2 output participates.

## Stage 0: prepare-only

After pulling the branch:

```bash
python first_science/phase4/m2_g2_step0_calibration.py --prepare-only
```

Expected marker:

```
M2_G2_STEP0_PREPARE_PASS_NO_CALIBRATION_WHITEBOX
```

This generates no calibration white-box evidence.

## Stage 1: selection and freeze before confirmation

Selection uses hidden G2 WB seeds 32000..32099:

```bash
/usr/bin/time -v python first_science/phase4/m2_g2_step0_calibration.py \
  --selection-only 2>&1 | tee m2_g2_step0_selection.log
```

Expected successful marker:

```
M2_G2_STEP0_SELECTION_FROZEN_BEFORE_CONFIRMATION_PASS
```

Primary outputs:

```
results/m2_g2_step0_calibration_v1/
  m2_g2_public_condition_manifest_v1.json
  m2_g2_step0_base_regions.csv
  m2_g2_step0_selection_whitebox_ledger.csv
  m2_g2_step0_selection_candidate_diagnostics.csv
  m2_g2_step0_selected_regions_from_selection.csv
  m2_g2_step0_selected_selection_curves.csv
  m2_g2_step0_selection_freeze_manifest_v1.json
```

If any rho has no feasible candidate, stop. Do not alter the frozen contract
after seeing the selection evidence.

## Stage 2: independent confirmation and final Step-0 freeze

Only after the selection-freeze manifest exists:

```bash
/usr/bin/time -v python first_science/phase4/m2_g2_step0_calibration.py \
  --confirm-and-freeze 2>&1 | tee m2_g2_step0_confirmation.log
```

Confirmation uses independent WB seeds 32100..32199 and evaluates only the five
already-selected regions. It does not search or reselect.

Each region must pass the same feasibility gate. The selected region battery
must also be nested with rho: latency and cost boundaries nondecreasing, and
quality nondecreasing/equal under the current constant-Q pilot.

Successful marker:

```
M2_G2_STEP0_CALIBRATION_FROZEN_PASS
```

Additional outputs:

```
m2_g2_step0_confirmation_whitebox_ledger.csv
m2_g2_step0_selected_confirmation_curves.csv
m2_g2_step0_confirmation_summary.csv
m2_g2_step0_selected_regions_frozen.csv
m2_g2_step0_calibration_manifest_v1.json
```

If confirmation or nesting fails, the runner writes
`M2_G2_STEP0_CALIBRATION_FAIL`. Do not run G2 predictions. Any redesign must
use a separately named G2b contract.

## Next gate after a pass

Only after `m2_g2_step0_calibration_manifest_v1.json` reports the frozen pass
may we implement and run blind G2 M0/M1/M2 predictions on seeds 33000..33099.

The fresh final G2 WB evaluation seed bank 34000..34099 remains untouched until
all prediction artifacts are materialized and hash-frozen.
