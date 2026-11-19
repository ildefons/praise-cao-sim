# PRAISE systems paper — LaTeX working directory

**Status:** manuscript draft v0.68, 19 November 2026. **Review-first**, not ready for submission.
**Canonical source:** `main.tex` in this directory. Edits and iterations are committed to the `praise-identifiability-feasibility` branch.  
**Compilation:** Standard **pdfLaTeX**, no XeLaTeX/LuaLaTeX/fontspec, no shell escape, no bibliography generator. The historical and fresh-reference scientific figures are converted locally from their separately archived frozen SVGs by build.sh. Citations use a standard in-file bibliography. The architecture is drawn using LaTeX boxes and text so no image conversion is needed.

## Pull and compile

The manuscript now uses the **historical and fresh-reference thirteen-budget, nine-policy SVGs as the two principal Results figures**, both with identical 0--0.025 regret axes. The fresh-reference archive is the independently regenerated white-box reference for the same provider worlds and graphs (repository identifier `B0001`). These are frozen from the same original evaluation policies, whose original five-budget output is preserved. The manuscript clips only the archived figures' top title strips so their original internal dataset labels do not appear in the reader-facing plots; all curves, axes and uncertainty bars are untouched. Standard `pdflatex` cannot read SVG directly, so `build.sh` converts both frozen SVGs to local PDFs *without regenerating or changing the results*. It detects Inkscape, `rsvg-convert`, or Python `cairosvg`; no XeLaTeX, fontspec or shell escape is required.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
cd first_science/b1/planb_validation/paper_systems
bash build.sh
```

Output: `main.pdf` in this directory. If no SVG converter is installed, `bash build.sh` explains which lightweight option can be installed (for Ubuntu: `sudo apt-get install librsvg2-bin`). The two converted PDFs in `figures/` are **local build artifacts**; do not commit them.

If figures were already converted and you only wish to recompile the TeX source, two ordinary `pdflatex` invocations are sufficient.

The manuscript now includes a formal citation to the GitHub-hosted B1 consolidated technical report and its complete numerical appendix. This is clearly labeled an internal repository technical report, not a peer-reviewed publication. GitHub links are branch-specific and should be replaced with immutable commit links or a DOI when the paper is submission-ready.

## Review protocol

- The manuscript is framed around **budget-aware allocation of validation evidence for decisions among computing-continuum methods**. Composed-service predictor selection is the evaluated case study, not the whole problem definition.
- The structural motivation is explicit throughout v0.68: the Introduction defines diversity dimensions as validation-condition coordinates and distinguishes those varied in the case study from those held fixed or excluded. Section 3.3 explicitly continues this discussion, then connects multidimensional budget-aware acquisitions to the per-method additive Gaussian model and its world--graph instance. This is a transparent approximation, not a claim that service hierarchies mathematically imply additive error or that the replay isolates the benefit of factor sharing.
- Current review structure: Section 2 presents the general validation framework; Section 3 specifies the protocol (3.2), the per-method additive Bayesian performance model (3.3), posterior updating (3.4), and validation allocation strategies (3.5); Section 4 introduces the composed-service case study; Section 5 gives the historical and fresh-reference thirteen-budget validation results with the same y-axis for both plots; Section 6 distinguishes a bounded positive answer to RQ1 from exploratory, unresolved superiority questions in RQ2/RQ3; later sections qualify novelty, limitations and scope. Joint-action KG remains distinct from the matched two-stage condition-choice experiment.
- When proposing edits, refer to section numbers or quote a phrase. The v0.68 Discussion and Conclusion explicitly explain posterior information sharing as an a priori mechanism supporting executable joint-action KG, while distinguishing this implementation from a claim of new KG theory or proven surrogate superiority.
- Manuscript is **venue-neutral** until the actual workshop/conference format is chosen. Page length and references must be adapted to that venue's template once identified.
- Working author list and affiliations appear in the manuscript; verify the final metadata before submission.
- No new simulations were run to write this draft; all reported values are reused from the verified evidence documents.

## Evidence and provenance

- [A1 implementation and seven-method public-I1 source trace](../B1_A1_I_M_SOURCE_TRACE_2026-11-06_V0_2.md).
- [A1 architecture and real episode](../B1_A1_SYSTEM_ARCHITECTURE_DRAFT_2026-11-06_V0_1.md).
- [A2 closest-systems audit](../B1_A2_CLOSEST_SYSTEMS_COMPARISON_2026-11-06_V0_2.md).
- [Original B1 main result](../B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md) and [complete numerical appendix](../B1_CONSOLIDATED_NUMERIC_APPENDIX_V0_1.md).
- [Controlled two-stage condition-selection study](../B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md).
- [Fresh-reference (B0001) complete exact-original-policy replay and figures](../results/b0001_original_policies_v1/README.md).
- [Fresh-reference (B0001) read-only fixed-decision reference and condition-sensitivity audit](../results/b0001_fixed_decision_sensitivity_v1/README.md).
- [Both thirteen-budget curves, original-policy extension data and provenance](../results/b1_nine_policy_13_budget_extension_v1/README.md).
- [Exact eight-budget extension commands and the shared-axis plotting command](../B1_ORIGINAL_NINE_POLICY_13_BUDGET_REPLAY_RUNBOOK_V1.md).
- [Complete verified B=15 episode](../results/worked_example_v1/worked_episode.md).

## Proposed version discipline

Use `main.tex` as the evolving manuscript rather than creating one file per edit. Record major scientific/scoping decisions in versioned standalone evidence notes, preserve the original frozen data and scripts, and increment the manuscript's visible version tag in the title/date for substantive revisions. Git history captures every textual iteration.
