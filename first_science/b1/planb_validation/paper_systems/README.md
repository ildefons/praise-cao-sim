# PRAISE systems paper — LaTeX working directory

**Status:** manuscript draft v0.1, 6 November 2026. **Review-first**, not ready for submission.  
**Canonical source:** `main.tex` in this directory. Edits and iterations are committed to the `praise-identifiability-feasibility` branch.  
**Compilation:** Standard **pdfLaTeX**, no XeLaTeX/LuaLaTeX/fontspec, no shell escape, no bibliography generator, no external figures required for this draft. Citations use a standard in-file bibliography. The architecture is drawn using LaTeX boxes and text so no image conversion is needed.

## Pull and compile

From your local repository:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

cd first_science/b1/planb_validation/paper_systems
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

Open `main.pdf` locally. If `latexmk` is already installed, this equivalent one-line build is also supported:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

No packages should require special engines. If the installed TeX distribution lacks a standard package, report the precise error and we can simplify the source further. Do not commit generated `main.pdf`, `.aux`, `.log`, or `.out` build artifacts.

## Review protocol

- The initial paper is intended as an **applied computing-continuum systems methodology** manuscript: a full research narrative, not just a skeleton.
- First priorities for editorial iteration: system decision and scope, Figure 1's legibility, differentiated contribution relative to closest systems, and the organization of the two independent B1 retrospective experiment families.
- When proposing edits, refer to section numbers or quote a phrase. The next revision will update `main.tex` in GitHub and provide a new exact pull-and-compile command.
- Manuscript is **venue-neutral** until the actual workshop/conference format is chosen. Page length and references must be adapted to that venue's template once identified.
- Author list and affiliations are intentionally left anonymous in this working version; final metadata should be agreed before submission.
- No new simulations were run to write this draft; all reported values are reused from the verified evidence documents.

## Evidence and provenance

- [A1 implementation and seven-method public-I1 source trace](../B1_A1_I_M_SOURCE_TRACE_2026-11-06_V0_2.md).
- [A1 architecture and real episode](../B1_A1_SYSTEM_ARCHITECTURE_DRAFT_2026-11-06_V0_1.md).
- [A2 closest-systems audit](../B1_A2_CLOSEST_SYSTEMS_COMPARISON_2026-11-06_V0_2.md).
- [Original B1 main result](../B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md) and [complete numerical appendix](../B1_CONSOLIDATED_NUMERIC_APPENDIX_V0_1.md).
- [Controlled two-stage condition-selection study](../B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md).
- [Complete verified B=15 episode](../results/worked_example_v1/worked_episode.md).

## Proposed version discipline

Use `main.tex` as the evolving manuscript rather than creating one file per edit. Record major scientific/scoping decisions in versioned standalone evidence notes, preserve the original frozen data and scripts, and increment the manuscript's visible version tag in the title/date for substantive revisions. Git history captures every textual iteration.
