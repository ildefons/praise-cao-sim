# Pilot M3 selection-policy transfer (v1)

**Status: executable source prepared. No numerical result or causal conclusion is claimed before local execution.**

## Question

Does transferring the original pilot's *selection and reconstruction procedure*, rather than the fixed values returned by that procedure in September, recover good end-to-end SLA predictions across the 12 eligible Phase-II configurations?

This is a **retrospective exploratory experiment**. The existing Phase-II reference has already been studied, so even good results here are not independent confirmation.

## Frozen transfer rules

1. Build each candidate domain from the new provider's public I1 and workload information, using the original Phase-3 formula (m1_joint_lift_v2.build_search_bounds). ProviderA/B use the original base M1 contract and ProviderC the pilot's declared expanded-ProviderC contract. No hidden parameters or previously reconstructed Phase-II M1 domains.
2. Generate 48 candidate triples per provider using the original nonadaptive LHS routine and seed 20260917 + provider_index*100003.
3. Score each candidate using the complete public I1 surface and 100 native local trajectories, with common pilot seeds 35000..35099, Jeffreys smoothing and the original native Gamma surrogate.
4. Choose lambda **separately for each provider world**, using the original five-fold blocked public-I1 cross-validation, grid and tie-breaking rule. Lambda30 in the configuration is only the temporary initial value needed by the reused candidate-scoring engine; it does **not** determine final weights.
5. Rank all 48^3 weighted joint candidate combinations and keep the **smallest prefix achieving at least 99.9% of the inferred weight**, instead of forcing 14 members.
6. Allocate B=1400 graph trajectories among selected models by the original integer minimax variance-bound rule. Simulate Top1 separately at the same B1400.
7. Use the existing Phase-II eligible 12-cell battery (P1/P3/P4 and four graphs), SLA definitions and white-box reference. Freeze all 12 predictions before opening the reference in the evaluation stage.

**Feasibility condition:** if the adaptive mass rule selects K>1400 joint models, it is impossible to allocate at least one trajectory to every model within B1400. The runner records support_feasibility.json and stops. Do not silently force K14 or increase the budget.

**Scope of fidelity:** the domain construction *formula* transfers, not the pilot's numerical bounds. The expanded-ProviderC domain policy is copied from the pilot as declared; we do not repeat the earlier M1 boundary-escalation study. New worlds, calibrated SLA regions, graph seeds and white-box sample sizes differ, so this is a procedural transfer, not a bit-for-bit repeat of the full pilot.

## Source and output isolation

- run_pilot_m3_policy_transfer_v1.py: public-only policy controller (domains, CV, mass-based support, stage dispatch).
- _pilot_m3_policy_transfer_core_v1.py: isolated fork of the retrospective engine for local/graph simulations, supporting variable K; the original retrospective runner is unchanged.
- config_pilot_m3_policy_transfer_v1.json: frozen selection and evaluation contract.
- Output: first_science/phase5/results/b1_pilot_m3_policy_transfer_v1 (distinct from all archived pilot/Phase-II/retrospective results).

The reused local simulator initially writes provisional lambda30 weights after scoring a provider. Once the three providers' candidate curves are ready, the policy controller runs the original public-I1 CV procedure and replaces these provisional weights with **final CV-selected provider weights**. Only these final frozen weights enter the joint support and graph prediction. Provisional weights are not results.

## Mandatory first step: reproduce the ORIGINAL pilot only

Before any P1/P3/P4 candidate benchmark or battery run, the transfer controller now requires a signed local pilot-reproduction gate. This reproduces the September pilot on its own public cards, candidate domains, original G0 parallel graph, original 15 SLA cases and original graph seeds. No new provider worlds are used in these steps.

From the existing praise-cao environment:

    cd ~/praise/praise-cao-sim
    git pull --ff-only origin praise-identifiability-feasibility
    python -m py_compile first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py
    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage preflight
    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage deterministic

The deterministic check reconstructs **all 144 original pilot candidate proposals**, re-runs the **original five-fold public-I1 CV**, and verifies that lambda=30, the ordered Top14 weight support, and the integer B1400 allocations agree with the frozen pilot.

Next reproduce the original **100-trajectory local scoring** of the same 144 provider models, comparing each complete public-I1 probability curve with its original archive. This is a larger experiment (14,400 provider-local trajectories) and is checkpointed per candidate. Begin with a bounded sample of three original candidates, then run the full local replay:

    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage local-replay --max-candidates 3
    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage local-replay

**Optional four-worker acceleration for the remaining candidates.** The independent
`run_pilot_m3_local_replay_parallel_v1.py` is a scheduling adapter that keeps the
original reproduction-gate source untouched, so existing original-format SHA-checked
candidate checkpoints remain reusable. It uses the original simulator, seed bank,
archived comparison keys, numerical tolerance and final canonical serial verifier.
First replay four additional candidates (first seven total), then the rest:

    python -m py_compile first_science/b1/retrospective_m3/run_pilot_m3_local_replay_parallel_v1.py
    time python first_science/b1/retrospective_m3/run_pilot_m3_local_replay_parallel_v1.py --workers 4 --max-candidates 7
    time python first_science/b1/retrospective_m3/run_pilot_m3_local_replay_parallel_v1.py --workers 4

Do not run serial and parallel local replay simultaneously. If any cached checkpoint
or freshly replayed candidate differs from the archive, the adapter fails rather
than overwriting it. The canonical `LOCAL_REPLAY_PASS` is written only after
all 144 candidates are verified. Parallelism does not alter the scientific budget.

Then independently regenerate the 555 original pilot graph predictions from its archived B1400 graph ledgers and run the small matched-native-G0 smoke:

    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage archived-scoring
    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage graph-smoke

The full B1400 replay is a distinct, **potentially expensive** reproducibility test. It uses the **new Phase-II G_PAR simulator**, configured with the original pilot provider candidates, original G0 seeds, original canonical IPT=1e6 and original SLA definitions. Every freshly simulated request ledger is compared with the archived pilot G0 ledger, using resumable per-seed checkpoints. First test a bounded sample:

    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage full-graph --max-trajectories 10

If the subset passes, **optional four-worker acceleration** uses the original
native simulator and archive comparison, with identical per-seed checkpoint
format and no change to the original gate source. First test eight NEW
trajectories after the ten already checked, then complete all 1,400:

    python -m py_compile first_science/b1/retrospective_m3/run_pilot_m3_full_graph_parallel_v1.py
    time python first_science/b1/retrospective_m3/run_pilot_m3_full_graph_parallel_v1.py --workers 4 --max-trajectories 18
    time python first_science/b1/retrospective_m3/run_pilot_m3_full_graph_parallel_v1.py --workers 4
    python first_science/b1/retrospective_m3/run_pilot_m3_reproduction_gate_v1.py --stage seal

Do not run original serial full-graph and parallel native replay at the same
time, and do not seal until the parallel script prints
`FULL_GRAPH_PASS` and `PILOT_FULL_GRAPH_PARALLEL_CHECKPOINTS_VERIFIED`.
For a fully serial alternative, run the original `--stage full-graph` without
a trajectory limit, followed by `--stage seal`.

Only a successful seal prints `B1_PILOT_M3_REPRODUCTION_GATE_PASS` and creates the local `first_science/b1/local_audit/pilot_m3_reproduction_gate_v1/gate.json`. That artifact checks the frozen transfer code and contracts. All subsequent battery execution stages fail closed if the gate is missing or stale. The gate checks original candidate generation, **actual local stochastic simulation**, CV, support, graph scoring and full native reproduction in the newer graph simulator. It is a verification of fidelity to the original pilot, **not** evidence of generalization.

## Execute locally

Run in the existing praise-cao environment:

    cd ~/praise/praise-cao-sim
    git pull --ff-only origin praise-identifiability-feasibility
    python -m py_compile first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py first_science/b1/retrospective_m3/_pilot_m3_policy_transfer_core_v1.py
    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage preflight

First benchmark a few *real* local simulations and reuse their checkpoints:

    time python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage benchmark --world P1 --benchmark-candidates 3 --workers 3

Then complete P1 reconstruction, lambda CV and adaptive support selection:

    time python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage prepare --world P1 --workers 3

**Checkpoint:** inspect candidate_support/P1/cv_selection.json and candidate_support/P1/support_feasibility.json under the new output root. If the prefix is feasible, benchmark and run the first graph:

    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage graph-benchmark --cell P1__G_PAR --workers 3
    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage predict --cell P1__G_PAR --workers 3

To complete the battery, after reviewing the P1 diagnostics:

    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage prepare --workers 3
    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage predict --workers 3
    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage freeze
    python first_science/b1/retrospective_m3/run_pilot_m3_policy_transfer_v1.py --stage evaluate

Do not use evaluate until all 12 cell predictions are frozen, and stop if any world is infeasible under B1400. There is no automatic fallback method.

## Overnight unchanged-procedure battery scheduler

The full pilot reproduction has passed, and P1 has already completed all
144 provider candidates. Under its cross-validated lambda=3, P1's minimal
99.9%-mass support has K=14267 > B=1400. Preserve this as an **infeasible
original-policy transfer**, not a reason to change its selection rule.

The separate \`run_pilot_m3_battery_overnight_v1.py\` is a resumable
**scheduling-only wrapper** for the already frozen controller. It does not
change the LHS domain rule, provider-local bank, CV, Gibbs weights,
99.9%-mass support selection, B1400 allocation, simulation code, or
white-box access restrictions. It:

1. Validates the sealed original pilot reproduction and all 12 public-only
   battery inputs.
2. Preserves P1's infeasibility and independently prepares P3 then P4.
3. Accepts a world-level prepare failure **only** when the canonical
   feasibility checkpoint proves that K>B and the controller prints its
   exact expected failure.
4. Benchmarks and predicts each of the four graph cells for each feasible
   world; per-cell prediction manifests are immutable and reusable.
5. Saves a separate execution audit summary to
   \`first_science/b1/local_audit/pilot_m3_battery_overnight_v1/overnight_status.json\`.

Run \`--workers 4\` for the full unattended workflow, or add
\`--prepare-only\` to stop after P3/P4 provider reconstruction.

The wrapper intentionally does **not** read the existing Phase-II white-box
reference, calculate accuracy, or claim a complete 12-cell evaluation.
The existing \`freeze\` and \`evaluate\` stages of the frozen controller are
valid only when all 12 eligible cells have successfully produced predictions,
which is impossible for P1 at K=14267 with B=1400. Record such cases as
**not estimable under the frozen budget**, never as accuracy failures or
successful predictions. Partial accuracy evaluation, if desired, must be
designed and labeled separately after the public-only predictions have
been completely frozen.

## What to report

At the first checkpoint: preflight output, cv_selection.json, cv_summary.csv, support_feasibility.json and (if feasible) adaptive_support.csv and support_manifest.json for P1.

At the full evaluation: global_prediction_freeze.json, per-cell metrics, and the Phase-II FULL343 comparator evaluated against exactly the same white-box reference, including world-by-graph breakdown and costs.

Public-I1 CV loss and graph-level MAE measure different targets. An improved CV score does not itself demonstrate improved composed SLA predictions. All comparisons here are post-result development analyses; a new untouched battery is required for confirmatory claims.
