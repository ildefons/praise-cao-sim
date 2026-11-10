# Isolated fresh-world Step-0 feasibility pilot (v1)

Status: *engineering pilot only*. No acquisition policy is run and no B1
confirmatory evidence is produced. The original Phase-5 scientific functions,
Step-0 query rules, evidence counts and graph semantics are unchanged.

## Design

The original `run_phase5_i1_v2.run_world` and
`run_phase5_step0_v2._run_calibration_cell/_run_confirmation_cell` are
called with a **private, isolated copy of their Phase-5 JSON contracts**.
The scripts' historical files are never edited.

The initial pilot is restricted to `B0001_P1_A01` / `G_PAR`.
This is the first candidate of the first proposed battery, not a
post-selected world. The adapter maps it to the `P1` world slot in the
**isolated** contract copy only.

The pilot runs:
1. Fresh I1 acquisition: 100 region and 100 sigma provider-local trajectories,
   with fresh public cards stored under the isolated workspace
2. Official Step-0 calibration: 200 new graph white-box trajectories
3. Official Step-0 confirmation: 200 independent new graph trajectories
   if calibration passes; if calibration fails, Step-0 confirmation records
   the gate failure without simulation

Seed banks are four disjoint, SHA-derived subranges above 130 million.
Original Phase-5 scientific bank seeds and private historical world
parameters are not reused. Candidate generating parameters remain in
`isolated_contracts` and must not be passed to acquisition policies.

The pilot output root **must be outside the Git checkout** and must not
exist before a new run.

## Verify without running simulations

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/isolated_step0_pilot_v1.py \
  --verify \
  --preview ~/praise/planb_b1_newworld_preview_v0_1/PRIVATE_world_candidates.json
```

The check creates disposable contracts in a temporary directory, verifies
that the original historical source configs are unchanged, that the new
physical parameters are in the isolated world, and that 100/100/200/200
fresh seed blocks are disjoint. It does **not** import the simulation runner.
Expected marker: `ISOLATED_STEP0_ADAPTER_VERIFY_PASS`.

## Execute only the one-world/one-graph pilot

```bash
python first_science/b1/planb_validation/isolated_step0_pilot_v1.py \
  --run \
  --preview ~/praise/planb_b1_newworld_preview_v0_1/PRIVATE_world_candidates.json \
  --out ~/praise/planb_b1_isolated_step0_pilot_v1
```

This launches real simulations and can be costly. The user has authorized
this specific isolated pilot; the prior world-generator draft's
`execution_authorized: false` remains unchanged because it was a
simulation-free *preview*, not an execution protocol.

Output includes:
- `pilot_provenance_PRIVATE.json`: candidate ID, original contract hashes,
  seed derivation, source provenance; do not pass to selector
- `isolated_contracts/`: new-world contracts, I1 public cards and private
  I1 evidence; keep private
- `step0/P1__G_PAR/`: native Step-0 output and calibration/confirmation manifests
- `stage_i1.json`, `stage_step0_calibration.json`,
  `stage_step0_confirmation.json`: measured wall-clock seconds and stage status
- `pilot_summary.json`: eligibility and per-stage measured costs, suitable
  for discussing the next gate

If a scientific stage fails, the wrapper records its exception with stage
time and traceback. Do not delete or edit pilot evidence merely because of a
gate failure. Treat an actual Step-0 rejection as a valid eligibility
observation, not an implementation problem.

## Limitations and next decision

This is a single engineering pilot, NOT a complete 7-method validation
battery and NOT a new-graph test. A successful Step-0 for one new world/graph
does not establish 12-cell battery feasibility or selection quality.
Pilot world selection was specified before eligibility results.

If Step-0 runs, inspect the stage wall times and candidate eligibility.
Use those measurements to decide whether to continue with the other
three graphs and remaining world roles; retain predefined attempt limits,
report failures and preserve outcome firewalls.

Do not run historical Phase-5 CLI on the new-world config or write its
results under `first_science/phase5/results`.
