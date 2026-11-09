# PRAISE systems paper — LaTeX working directory

**Status:** manuscript draft v0.4, 9 November 2026. **Review-first**, not ready for submission.  
**Canonical source:** `main.tex` in this directory. Edits and iterations are committed to the `praise-identifiability-feasibility` branch.  
**Compilation:** Standard **pdfLaTeX**, no XeLaTeX/LuaLaTeX/fontspec, no shell escape, no bibliography generator, the primary scientific figure is converted locally from a committed frozen SVG by build.sh. Citations use a standard in-file bibliography. The architecture is drawn using LaTeX boxes and text so no image conversion is needed.

## Pull and compile (v0.2)

The manuscript includes the **existing frozen seven-policy SVG** as its primary results figure. Standard `pdflatex` cannot read SVG directly, so the repository build script converts that exact archived SVG to a local PDF *without regenerating or changing the results*. It detects Inkscape, `rsvg-convert`, or Python `cairosvg`; no XeLaTeX, fontspec or shell escape is required.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
cd first_science/b1/planb_validation/paper_systems
bash build.sh
```

Output: `main.pdf` in this directory. If no SVG converter is installed, `bash build.sh` explains which lightweight option can be installed (for Ubuntu: `sudo apt-get install librsvg2-bin`). The converted `figures/controlled_seven_policy_regret.pdf` is a **local build artifact**; do not commit it. All substantive manuscript editing goes through GitHub.

If figures were already converted and you only wish to recompile the TeX source, two ordinary `pdflatex` invocations are sufficient.

The manuscript now includes a formal citation to the GitHub-hosted B1 consolidated technical report and its complete numerical appendix. This is clearly labeled an internal repository technical report, not a peer-reviewed publication. GitHub links are branch-specific and should be replaced with immutable commit links or a DOI when the paper is submission-ready.

## Review protocol

- The manuscript is framed around **budget-aware allocation of validation evidence for decisions among computing-continuum methods**. Composed-service predictor selection is the evaluated case study, not the whole problem definition.
- First priorities for editorial iteration: revised general-to-specific title, abstract and introduction; whether the case-study instantiation follows naturally; Figure 1's scope; and the distinct original versus two-stage comparison families.
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
