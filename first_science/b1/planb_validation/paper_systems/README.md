# PRAISE systems paper — LaTeX working directory

**Status:** manuscript draft v0.76, 19 November 2026. **Review-first**, not ready for submission.
**Canonical source:** `main.tex` in this directory. Edits and iterations are committed to the `praise-identifiability-feasibility` branch.  
**Compilation:** Standard **pdfLaTeX**, no XeLaTeX/LuaLaTeX/fontspec, no shell escape, no bibliography generator. The historical figure is converted from its archived SVG, while the zoomed fresh-reference figure is rendered locally from the frozen summary CSV by build.sh. Citations use a standard in-file bibliography. The architecture is drawn using LaTeX boxes and text so no image conversion is needed.

## Pull and compile

The two principal Results figures show the same nine policies and thirteen budgets. Figure 3 retains the historical 0--0.025 regret axis; Figure 4 uses a 0--0.012 vertical range to resolve the smaller fresh-reference regrets. All fresh-reference 95% interval bounds are below 0.012. The independent-reference archive covers the same provider worlds and graphs (repository identifier `B0001`). The original **shared-axis SVGs remain frozen and unchanged**. During `bash build.sh`, the historical SVG is converted to PDF and `plot_fresh_reference_zoom_v1.py` reconstructs only the paper's zoomed Figure 4 from the archived summary CSV. Policy labels, markers, colors, curves and uncertainty values are reused; no outcomes are recomputed. The build requires the existing Python plotting dependencies (`matplotlib`, `numpy`, `pandas`) and an SVG converter (Inkscape, `rsvg-convert`, or Python `cairosvg`) for Figure 3.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
cd first_science/b1/planb_validation/paper_systems
bash build.sh
```

Output: `main.pdf` in this directory. If no SVG converter is installed, `bash build.sh` explains which lightweight option can be installed (for Ubuntu: `sudo apt-get install librsvg2-bin`). The generated figure PDFs and zoomed SVG in `figures/` are **local build artifacts**; do not commit them.

If figures were already converted and you only wish to recompile the TeX source, two ordinary `pdflatex` invocations are sufficient.

The manuscript now includes a formal citation to the GitHub-hosted B1 consolidated technical report and its complete numerical appendix. This is clearly labeled an internal repository technical report, not a peer-reviewed publication. GitHub links are branch-specific and should be replaced with immutable commit links or a DOI when the paper is submission-ready.

## Review protocol

- The manuscript is framed around **budget-aware allocation of validation evidence for decisions among computing-continuum methods**. Composed-service predictor selection is the evaluated case study, not the whole problem definition.
- The structural methodology is explicit throughout v0.76: the Introduction identifies diversity dimensions as validation-condition coordinates; Section 3.3 formulates a structure-informed prior covariance and presents crossed world--graph additive effects as the evaluated instance; Section 3.4 relates posterior condition covariance to acquisition statistics. These are modeling hypotheses informed by continuum structure, not physically guaranteed loss correlations. The policy replay does not isolate the empirical gain from factor sharing.
- Current review structure: Section 2 presents the general validation framework; Section 3 specifies the protocol (3.2), the structure-informed prior and its additive case-study implementation (3.3), posterior updating (3.4), and validation allocation strategies (3.5); Section 4 introduces the composed-service case study; Section 5 gives the historical and fresh-reference thirteen-budget validation results with the same y-axis for both plots; Section 6 discusses the positive RQ1 finding, the comparative RQ2/RQ3 results and future research; Section 7 positions the contribution against related work; Section 8 concludes. Joint-action KG remains distinct from the matched two-stage condition-choice experiment.
- When proposing edits, refer to section numbers or quote a phrase. The v0.76 Discussion and Conclusion distinguish the general structure-to-belief-to-decision methodology from its evaluated additive surrogate and existing KG theory.
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
