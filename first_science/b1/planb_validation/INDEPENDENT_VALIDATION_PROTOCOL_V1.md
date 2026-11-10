# Independent validation: prospective systems study — preflight v1

**Status:** Research protocol and code-discovery preflight, not a completed new-world experiment.
This does not alter B1 historical evidence or manuscript v0.60.

## Scientific objective

Test whether the **frozen validation policies** select a low-error composed-service
predictor in previously unseen provider configurations and, if feasible, composition
graphs. Historical B1 replays reuse 84 archived outcomes and cannot establish
generalization between independent provider systems.

**Primary endpoint:** terminal simple regret (difference between the selected
predictor's true domain-average MAE and the best of seven reference predictors)
on a *separately generated* validation problem. Report reference-best selection
as a secondary endpoint, and world-level paired variation across policies.

## Experimental units and transfer tests

1. **Provider shift (primary).** Retain the four original graph families; create
   independent provider-world instances from new seeds. An experimental *problem*
   consists of a predeclared catalogue of provider worlds crossed with these
   graphs. Compute seven predictor MAEs under comparable public-I1 and WB contracts.
   Do not reuse the historical P1/P3/P4 reference worlds or prediction outcomes.
2. **Graph shift (secondary, only if feasible).** Add genuinely new composition
   structures *after* checking simulator and predictor support. Do not treat graph
   relabelings or mere order permutations as new structures. Document graph
   semantics, feasibility and evaluation comparability before including them.
3. **Future operational exercise.** Optionally let selected actions trigger
   predictor and WB evaluation on demand, rather than reveal entries in a new
   frozen archive. Prefer this if runtime allows; new-world retrospective replay
   remains useful independent evidence, but not a live execution demonstration.

The primary evaluation should preserve a comparable, fixed *within-problem*
condition catalogue (e.g. new provider worlds crossed with four graphs), with
the one-hot design adapted **only in a precommitted way** to its fixed dimensions.
Never use existing P1/P3/P4 identifiers to denote historical worlds while
claiming new-world transfer. The model may encode three new provider identities
locally in each new problem; this is *within-problem adaptation*, not an ability
to predict an unseen provider's loss with no samples. Extending the number of
worlds or graphs requires a predeclared encoding, prior and common evaluation
budgets, and changes the comparison problem.

The reference result for each pair must come from the same query/horizon
definition and independent WB reference procedure. The historical archive
aggregates 555 query/horizon points per method-condition pair; match this
contract if scientifically appropriate, rather than silently changing
evaluation reliability.

## Protect the inference

- Separate **development** and **confirmatory** independent-world cohorts.
  Policies, priors, budgets, initialization, tie-handling and primary contrasts
  are frozen before confirmatory outcomes are examined.
- Primary comparator: one-step joint KG versus Balanced and Top2 (plus the
  existing Random and Informed controls); retain the original acquisition
  policies instead of adding algorithm variants post hoc.
- Treat the *independently generated world configuration or full problem* as
  the sampling unit, not replay seed, MAE query point or KG decision.
- If world draws are grouped in sets to define a problem, account for that
  grouping in paired uncertainty estimates. Replicated replays within the
  same problem only measure policy randomization effects.
- A common public I1 interface and independent WB reference are essential.
  Never expose private provider parameters, unrevealed losses or reference-best
  identities to an acquisition policy.

## Cost model and run-time planning

Record wall-clock cost and, where feasible, CPU peak memory and reusable setup
for: provider-world generation; public I1 card construction; reconstruction
per method; graph prediction per method-condition; reference WB estimation;
and score aggregation. Distinguish one-time preparation from marginal cost of
evaluating an additional method-condition pair. Avoid assuming each MAE value
has identical cost.

Before selecting the cohort count, time a small *nonconfirmatory* pilot on
independent worlds. This pilot may reveal unsupported graph structures,
excessive M3 costs, or infeasible WB reference runs. Record pilot-world seeds
and exclude these from the confirmatory cohort.

## Git-delivered preflight: first run

From the branch:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/independent_validation_preflight_v1.py \
  --repo ~/praise/praise-cao-sim \
  --out ~/praise/planb_b1_independent_preflight_v1
```

This deliberately does **not** run any simulator. It inventories local
Python entry points and their command-line options, grouped by likely stage,
without importing them. Files:

- `pipeline_inventory.csv`: candidate script paths, function names,
  discovered flags, import names, classification, source hashes.
- `stage_summary.json`: strongest candidates per pipeline stage.
- `manifest.json`: provenance and hashes.

**Review the inventory** to find the real new-provider generator, public-I1
evidence pipeline, each predictor family, and WB reference entry point. The
current conversation has not established a safe verified end-to-end CLI for
these stages; do not invent one.

## Optional: time reviewed commands

After verifying individual command lines and ensuring they use **new scratch
output locations only**, provide a JSON plan, for example:

```json
{
  "commands": [
    {
      "name": "provider_generation_pilot",
      "cwd": ".",
      "argv": ["python", "VERIFIED_PROVIDER_SCRIPT.py", "--help"],
      "timeout_seconds": 60
    }
  ]
}
```

This example is intentionally a placeholder: replace it with a verified
repository command. No simulation is implied by running `--help`.
The preflight accepts a reviewed plan through `--benchmark-plan PATH`;
it records wall times, stdout/stderr and exit codes and stops on failure.
It **never automatically executes** a discovered candidate.

## Next gate

Inspect the inventory and select the actual simulator/validator entry points.
Then make an executable, versioned small-pilot plan with new worlds (and
new graphs only if supported). Use measured costs to set feasible cohort size.
Only then freeze and execute the independent confirmatory validation. The
theoretical KG investigations are separate and should not consume this budget.
