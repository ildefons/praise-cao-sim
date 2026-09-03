# Phase-1 N=100 shortlist stability calibration

This stage was introduced after the first frozen N=10 matched battery replicated its latency/cost/mixed failure roles on fresh N=100 seeds but the mixed case moved above the frozen normalized SLA-compliance-area gate.

The first N=100 result is retained as a genuine protocol-v1 holdout failure. Its thresholds, rho, and gate are not repaired using those data.

## Frozen protocol

1. Use only the sealed N=10 SLA-native candidate metrics and existing role-ranking rule.
2. Freeze the five lowest-score matched physical-regime triplets.
3. Run all five physical settings on one new common seed bank, `4100..4199`, N=100 per setting.
4. Evaluate the three frozen admissibility regions of every battery without recalibrating A or rho.
5. A battery passes only if latency, cost, and mixed all replicate their intended request-failure role and each normalized SLA-compliance area remains inside `[0.50,0.75]`.
6. Select the first passing battery in the already-frozen N=10 ordering. N=100 numerical values do not reorder passing batteries.
7. If none pass, stop. Do not tune thresholds or extend the shortlist using these calibration data.
8. The selected three whiteboxes still require an untouched final N=100 confirmation using seeds `5000..5099`.

The N=100 shortlist stage is therefore a stability/calibration stage, not the final confirmation set.

## Commands

From `~/praise/praise-cao-sim/first_science/phase1`:

```bash
python test_n100_shortlist_calibration.py
python freeze_n10_matched_shortlist.py
```

Review the frozen shortlist before simulation. Then run:

```bash
python run_n100_shortlist_calibration.py
```

Do not use `--clean` on the first run. The runner refuses to mix with a non-empty existing output directory unless an explicit rerun is requested.

Key outputs:

- `shortlist_n10_matched_v1.json`
- `results/n100_shortlist_calibration_v1/n100_shortlist_case_summary.csv`
- `results/n100_shortlist_calibration_v1/n100_shortlist_battery_summary.csv`
- per-battery SLA diagnostics and plots
- `selected_whiteboxes_after_n100_calibration.json`

The selected manifest is not final confirmation evidence. It only freezes the three cases eligible for the untouched final seed bank.
