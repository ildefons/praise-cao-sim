# WP3a implementation and execution gate — 27 November 2026

Protocol: WP3A_CMMS_EXPERIMENTAL_PROTOCOL_2026_11_27_V1.md (commit 4352b3a). No scientific design change. No real CMMS acquisition trajectories executed.

## Implementation

- wp3a_policy_core.py: dimension-generic history-only selection, coefficient/covariance Gaussian maps, all nine frozen B1 rules; bounded mask cache; stable candidate ordering and 1e-12 score tie tolerance.
- wp3a_cmms_replay.py: source digest/schema/replication checks, primary and balanced reference construction, fixed seed/budget design, per-case lossless compressed histories and terminal rows, independent path/scoring reconstruction, WP2 check, resumable immutable case outputs. Base compares coefficient/covariance moments at every terminal; structural stage additionally replays both KG variants with covariance-space additive model before accepting reused additive paths.
- wp3a_cmms_analysis.py: predeclared conditional Student-t/Welch-Satterthwaite intervals, independent-policy bootstrap, 8-comparison familywise baseline intervals, prior and replication sensitivity, matched-stream structural contrasts. Separate baseline-only review stage, which cannot alter subsequent protocol.
- test_wp3a_cmms.py: synthetic posterior, policy, seed, information-boundary, exhaustion, full-coverage and inference tests; explicit comparison to original PRAISE selectors in 7x12 using same histories and random streams.

Exact committed core blob 517f6e1d34da02d788e1585b91ea599cfe25f298 was reproduced in a local test container, git blob hash checked, then tested on synthetic data: coefficient/covariance moments and WP2 affine relation over 70 masks; all nine policy paths (three replicates each) agree between coefficient/covariance implementations; nested prefixes and full catalogue correct-selection boundary pass. Independently rechecked actual supplied ZIP/CSV digests and complete source data contract: PASS, no acquisitions. These are bounded checks; the complete committed unittest suite, packaged CLI preflight and full driver/analysis integration still require execution on the laptop. Do not start real replay if either test/preflight fails.

## 1. Tests and preflight only

From the repository root, in the existing praise-cao environment:

    git pull --ff-only origin praise-identifiability-feasibility
    export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
    python first_science/b1/planb_validation/test_wp3a_cmms.py -v

Requires NumPy, pandas and SciPy. Set SOURCE to the actual local copy of the exact user-supplied cmms-benchmark-7D80 ZIP (filename may differ; hash must match). For example:

    SOURCE="/actual/path/to/cmms-benchmark-7D80(1).zip"
    RUNNER=first_science/b1/planb_validation/wp3a_cmms_replay.py
    OUT="$HOME/praise/wp3a_cmms_2026_11_27_v1"
    python "$RUNNER" --source "$SOURCE" --preflight-only

Expected: all unit tests OK and WP3A_PREFLIGHT_PASS no acquisitions or outputs written. Send test and preflight output for review before real replay. Keep the same environment variables and source for every stage (recorded in manifest).

## 2. Baseline only (after test/preflight review)

    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage base
    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage review-base

This is exactly 46,800 scored terminal decisions, 18,000 distinct trajectories and 1,242,000 acquired action entries. No simulator/hardware execution. Output base/ contains terminals.csv and paths.npz plus immutable manifest, reference/ contains both reference tables and manifest. Each action ID = method_index*20+condition_index; paths padded with -1, metadata columns policy_index/start_index/replicate/terminal_budget. Base review outputs base_review/aggregate_summary.csv, aggregate_contrasts.csv, policy_budget_summary.csv, budget_contrasts.csv and manifest. Verify and review, but do not change priors or experiment based on these results.

## 3. Complete frozen protocol (after baseline technical review)

    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage priors
    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage balanced
    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage structure
    python "$RUNNER" --source "$SOURCE" --out "$OUT" --stage analyse

Alternatively --stage all executes all prescribed stages and verifies existing cases. A single prespecified nonbase prior may be selected with --stage priors --prior NAME to split execution. Completed cases are reused only if provenance, design, environment and output hashes match. Incomplete temporary directories remain untouched; final case directory never overwritten. Any code/contract/environment changes require a new versioned output root; report any numerical tie diagnosis before proceeding. No performance-based gate or tuning. Output all sensitivity/structural and statistical tables to analysis/ for final scientific review. Total prescribed scored terminals 733,200 (excluding synthetic tests and additive identity reproduction).

No manuscript change authorized. WP1, WP2 and WP5a frozen.
