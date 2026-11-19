# B0001 reference and condition sensitivity — frozen-decision diagnostic v1

**19 November 2026.** This is a **post-hoc diagnostic**, not another
selection-policy experiment. It consumes the original B0001 replay's nine
sets of 1,200 *final recommendations*, the independently audited 7×12 B0001
accuracy matrix, and the **existing** 10,000-draw joint white-box trajectory
bootstrap. The existing acquisition rules, episodes, final recommendations,
predictions, physical reference, and original replay statistics are unchanged.

## Summary for the manuscript

**The two positive B0001 aggregate comparisons are conditional and materially
dependent on one physical condition.** Rescoring the *fixed* final
recommendations against 10,000 correlated reference-bootstrap method means
does not reverse the signs of the Top2-minus-Balanced or KG-minus-Balanced
contrasts. In contrast, changing the target to the eleven cells excluding the
audited P1 × G_PAR anomaly reverses both differences.

The second operation changes the scientific estimand. It demonstrates
**domain-composition sensitivity**, not a failure of the original 12-condition
policy run and not an alternative primary result.

## Primary original-script results, kept separate

The original nine-policy replay's nominal 95% stratified **episode-bootstrap**
intervals (all on the fixed 12-condition B0001 matrix) are:

| Regret contrast (negative favors first policy) | Point estimate | 95% episode interval |
|---|---:|---|
| Original joint Top2 minus Balanced | -0.000985 | [-0.001801, -0.000174] |
| Original joint KG minus Balanced | -0.001379 | [-0.002212, -0.000547] |
| Original joint KG minus joint Top2 | -0.000394 | [-0.001065, +0.000251] |
| Two-stage KG uniform minus adaptive | -0.000189 | [-0.000859, +0.000424] |
| Two-stage Top2 uniform minus adaptive | +0.000087 | [-0.000757, +0.000934] |

The first two comparisons are favored on average within the fixed B0001
archive. The last three episode intervals contain zero. These episode
intervals are **not** reference-trajectory uncertainty intervals.

## Diagnostic A — fixed-decision reference uncertainty

Let `q_{p,a}` denote the fraction of policy `p`'s **already recorded**
terminal recommendations that select method `a`. For an alternative vector
of reference method losses `mu`, the rescored mean simple regret is

```text
R_p(mu) = sum_a q[p,a] * mu[a] - min_a mu[a].
```

For a contrast, the common best-method subtraction cancels:

```text
R_p(mu) - R_q(mu) = sum_a (q[p,a] - q[q,a]) * mu[a].
```

The archived 10,000 jointly resampled white-box reference **mean-MAE**
vectors are substituted in these formulas. No new bootstrap draws occur.
All 10,800 original terminal rows were reverified against the canonical
B0001 mean MAEs before scoring.

| Frozen-decision contrast | Original B0001 estimate | Existing trajectory-bootstrap 95% interval |
|---|---:|---|
| Top2 minus Balanced | -0.000985 | [-0.001153, -0.000829] |
| KG minus Balanced | -0.001379 | [-0.001549, -0.001218] |
| KG minus Top2 | -0.000394 | [-0.000445, -0.000331] |
| KG two-stage uniform minus adaptive | -0.000189 | [-0.000255, -0.000121] |
| Top2 two-stage uniform minus adaptive | +0.000087 | [+0.000020, +0.000145] |

These intervals quantify **reference uncertainty with terminal decisions
held fixed**. They are narrower than many episode-bootstrap intervals and
must **never** replace them or be labeled a full joint uncertainty analysis.
The policy acquisitions and recommendations would generally change if the
bootstrap cell losses were actually revealed during each episode. The
provided bootstrap file only supplies method-wide means, not all 84
per-replicate cell losses needed to do that full replay.

## Diagnostic B — influence of P1 × G_PAR

M3_FULL343 minus M1 MAE on the official twelve-cell target is
**+0.000715827**, favoring M1. P1 × G_PAR alone contributes
**+0.024688937** to this equal-cell *average* difference; the other eleven
cells together contribute **-0.023973109**. On the eleven-cell target without
P1 × G_PAR, M3 instead beats M1 by **0.026152483** MAE on average.

The P1 × G_PAR raw-ledger reference was independently reconstructed
735/735 and the 10,000 white-box bootstrap replicates favored M1 there
100% of the time. This is **not** an identified reference-ledger error.

The following values simply **rescore the same frozen terminal
recommendations** for a different, hypothetical eleven-cell target; they
do not rerun or retune a policy:

| Fixed-decision contrast | Official 12 cells | Excluding P1 × G_PAR |
|---|---:|---:|
| Top2 minus Balanced | -0.000985 | **+0.001162** |
| KG minus Balanced | -0.001379 | **+0.000555** |
| KG minus Top2 | -0.000394 | -0.000607 |
| KG two-stage uniform minus adaptive | -0.000189 | -0.000310 |
| Top2 two-stage uniform minus adaptive | +0.000087 | +0.000808 |

Of the twelve leave-one-condition-out rescoring diagnostics, **only**
excluding P1 × G_PAR reverses the identity of the lowest-mean-MAE method
(from M1 to M3_FULL343) and reverses the two original joint-action
comparisons against Balanced. All twelve diagnostic outcomes are in the
attached CSV.

## Interpretation and remaining boundary

1. The *primary* B0001 conditional-on-reference conclusions remain as
   reported by the exact original scripts; no outcome is overwritten.
2. Finite white-box trajectory noise around the existing B0001 reference
   does not, **when decisions are held fixed**, explain the large difference
   between the historical B1 and B0001 method rankings.
3. The choice of **target conditions** matters substantially. The purported
   general advantage of budget-aware acquisition cannot be claimed to be
   insensitive to the condition catalogue.
4. None of this supplies a full reference-aware sequential-policy bootstrap,
   independent provider-world replication, multiplicity-corrected inference,
   or a causal explanation of the P1 × G_PAR anomaly.

## Reproduce without altering the original policies

```bash
python first_science/b1/planb_validation/audit_b0001_policy_fixed_trace_sensitivity_v1.py \
  --matrix ~/praise/planb_b0001_seven_method_accuracy_v1/seven_method_matrix.csv \
  --reference-bootstrap ~/praise/planb_b0001_raw_audit_reference_uncertainty_v1/reference_bootstrap_10000_replicates.csv \
  --baseline-terminal /path/to/frozen/B0001/01_baseline/terminal_episodes.csv \
  --kg-terminal /path/to/frozen/B0001/02_kg/kg_terminal_episodes.csv \
  --controlled-terminal /path/to/frozen/B0001/03_controlled/controlled_terminal_episodes.csv \
  --out /path/to/new/diagnostic/output
```

The script is **read-only with respect to all frozen inputs and policies**;
it only writes separate diagnostic CSVs and a hash manifest to a new output
directory. It refuses input SHA mismatches and existing output directories.
It does not modify, call, or import the policy replay functions.
