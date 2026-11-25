# PRAISE sequential validation paper — v0.100

Working manuscript, 25 November 2026. The shared Overleaf project remains the collaborative editing source; this directory snapshots its v0.100 manuscript and reproducible evidence. No acquisitions or simulations were rerun for this statistical revision.

## Build

From this directory, with Python (NumPy, pandas, SciPy, Matplotlib) and pdfLaTeX available:

```bash
python verify_analytical_revision.py
bash build.sh
```

Expected markers: `PRAISE_ANALYTICAL_REVISION_PASS` and `PRAISE_PAPER_BUILD_PASS`. `build.sh` generates the two analytical figures and compiles `main.pdf` twice. Generated PDFs and LaTeX auxiliary files remain untracked as before. The old bootstrap plot scripts and summary tables remain in the repository as historical evidence; they are no longer used by the current paper build.

## Revision scope

- `main.tex`: the current shared Overleaf manuscript; Appendix B and C are separate inputs. All 234 mean-regret curve points remain unchanged.
- `data/analytical_curve_intervals.csv`: all 234 pointwise intervals, including untruncated and plotting bounds.
- `data/analytical_main_contrasts.csv`: aggregate policy contrasts with the stated Bonferroni adjustment, including exploratory early-budget contrasts.
- `data/analytical_covariance_contrasts.csv`: paired covariance-model contrasts for Appendix B.
- `audit_intervals.py`: read-only computation of the three tables; `verify_analytical_revision.py` checks the frozen archive and reruns the calculation in a temporary directory.
- `data/analytical_revision_inputs_v0.100.zip`: exact input ledgers, original manifests, and S1/S2 evidence; `data/analytical_revision_manifest.json`: input/output hashes, software versions and verification scope.
- `plot_analytical_figures.py`: reads the revised intervals, reconciles all means against the original summary, and renders Figures 3 and 4 with the manuscript filenames and axis limits.

## Inference and limitations

Intervals are approximate Student-t intervals using fixed, equally weighted starting-condition strata and Welch–Satterthwaite degrees of freedom. For nested policies, average across budget checkpoints within each run before computing variance; for budget-specific Top2 runs and distinct policies, combine independent variance contributions. The covariance-model comparisons use matched-run differences. Plotting lower bounds are truncated at zero. The original bootstrap analyses for reference sensitivity, prior sensitivity and budget thresholds are retained. Zero observed variance does not imply absence of variability under unseen seeds.

The Top2 analytical intervals use the baseline prior-sensitivity replay. All 234 reported mean regrets and correct-selection rates reproduce, and the 2,400 available original historical two-stage Top2 rows agree individually. Remaining individual-run parity with original Top2 archives is still outstanding; the manuscript explicitly identifies the replay source. The intervals describe policy randomization conditional on the two fixed matrices, not transfer to other environments or reference uncertainty.

Earlier v0.98 manuscript and original bootstrap evidence remain accessible through Git history and the original exports. Do not overwrite the original summaries with the analytical tables.
