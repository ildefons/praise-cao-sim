# M2-A4 GP level-set diverse portfolio

M2-A4 replaces ad hoc repeated point-searching with a standard black-box level-set workflow. The scientific target is the public-I1-compatible parameter set, not a single optimum.

## Frozen design

For each provider, work in normalized `(log mu, log kappa, CV)` coordinates on `[0,1]^3`. Warm-start an ARD Matérn-5/2 Gaussian process with all existing TPE and M2-A2 LHS evaluations that used the original M1 search bank `22000..22024`. The provider-specific compatibility ceiling is the already-frozen M2-A2 ceiling, derived from the pre-A2 TPE best and the `1.25 x` rule. New LHS/GP discoveries may not move this ceiling.

At each of 48 sequential evaluations per provider, fit the GP and evaluate the point maximizing the straddle acquisition

`a(x) = 1.96 s(x) - |m(x) - epsilon_i|`

over a frozen scrambled-Sobol candidate pool of 16,384 points. This is a level-set search: it targets uncertainty around the compatible/incompatible boundary rather than repeatedly exploiting the current best point.

After all 48 evaluations, pool all actually evaluated TPE, LHS and GP points below the frozen ceiling. Build a provisional five-member portfolio per provider: first choose the lowest-loss point, then greedily add the point maximizing minimum Euclidean distance to the already selected set. GP-predicted but unevaluated points cannot enter the portfolio.

Confirm those five candidates per provider on `23000..23099`. Compatibility uses the pre-existing M2-A confirmation reference: confirmation MSE must remain within `1.25 x` the provider's previous best confirmed MSE. Take the first three passing members in the frozen provisional order. Replay those final three on `24000..24099` for diagnostics only; replay cannot change the portfolio.

No graph simulation, graph prediction, graph white-box data, private Phase-2 provider traces, hidden Phase-1 parameters, Optuna rerun, or PPG GP mechanism is used in M2-A4.

## Commands

From `first_science/phase4`, first validate dependencies and freeze the deterministic Sobol design without simulation:

```bash
mkdir -p results/m2_a4_gp_levelset_v1
python m2_a4_gp_levelset_search.py --prepare-only
```

Then run the 48-per-provider GP level-set search:

```bash
/usr/bin/time -v python m2_a4_gp_levelset_search.py \
  2>&1 | tee results/m2_a4_gp_levelset_v1/run.log
```

The search checkpoints `m2_a4_gp_acquisitions.csv` after every new evaluation and can be resumed by rerunning the same command.

Only after `M2_A4_GP_LEVELSET_SEARCH_COMPLETE`, confirm and freeze the portfolio:

```bash
mkdir -p results/m2_a4_portfolio_confirmation_v1
/usr/bin/time -v python m2_a4_confirm_portfolio.py \
  2>&1 | tee results/m2_a4_portfolio_confirmation_v1/run.log
```

Hold M2-B2 and any new graph-composition experiment until the final M2-A4 portfolio passes and is frozen.
