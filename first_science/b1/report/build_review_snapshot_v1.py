#!/usr/bin/env python3
"""Build a standalone B1 Overleaf ZIP, preserving reviewed text through 8.1."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REPORT = Path(__file__).resolve().parent
ORIGINAL = REPORT / "overleaf" / "main.tex"
FIGURE = REPORT / "overleaf" / "figures" / "phase5_aggregate.tex"
CUT = r"\subsection*{8.2 Pilot--battery divergence tracing}"
PDF_NAME = "B1_REVIEW_THROUGH_8_1.pdf"
ZIP_NAME = "B1_REVIEW_THROUGH_8_1_OVERLEAF.zip"


def make_snapshot(full: str) -> str:
    if full.count(CUT) != 1:
        raise ValueError("Exactly one Section 8.2 boundary required")
    before, suffix = full.split(CUT, 1)
    # Ship the review snapshot with portable fonts and pdfLaTeX, so the
    # recipient can import it in Overleaf without choosing a compiler.
    xelatex_preamble = (
        r"\usepackage{fontspec}" + "\n"
        + r"\setmainfont{DejaVu Serif}" + "\n"
        + r"\setsansfont{DejaVu Sans}"
    )
    pdftex_preamble = (
        r"\usepackage[T1]{fontenc}" + "\n"
        + r"\usepackage[utf8]{inputenc}" + "\n"
        + r"\usepackage{lmodern}"
    )
    # Older canonical reports used XeLaTeX fonts; the current canonical
    # report already uses portable pdfLaTeX fonts. Accept either source
    # preamble, but require exactly one recognized choice, and always
    # publish an Overleaf project that uses default pdfLaTeX.
    fontspec_count = before.count(xelatex_preamble)
    pdftex_count = before.count(pdftex_preamble)
    if fontspec_count == 1 and pdftex_count == 0:
        before = before.replace(xelatex_preamble, pdftex_preamble, 1)
    elif fontspec_count == 0 and pdftex_count == 1:
        pass  # Current canonical source needs no conversion.
    else:
        raise ValueError(
            "Expected exactly one supported font preamble "
            "(original fontspec or portable pdfLaTeX)"
        )
    if "fontspec" in before or "setmainfont" in before or "setsansfont" in before:
        raise ValueError("Non-default compiler dependency remains")
    if not before.startswith(r"\documentclass") or r"\end{document}" in before:
        raise ValueError("Invalid source document boundaries")
    if "8.1 Original-style M3 transfer" not in before:
        raise ValueError("Missing reviewed Section 8.1")
    if r"\label{tab:retrospective-m3-overall}" not in before:
        raise ValueError("Missing reviewed Table 6")
    tail = CUT + suffix
    headings = re.findall(r"(?m)^\\(section|subsection)\*\{([^}\n]+)\}", tail)
    if not headings or headings[0][1] != "8.2 Pilot--battery divergence tracing":
        raise ValueError("Unexpected Section 8.2 placeholder")
    placeholders = [r"\clearpage", "% Only section titles beyond 8.1, no unreviewed text.", ""]
    titles = []
    for kind, title in headings:
        if kind == "subsection" and not title.startswith("8."):
            continue
        titles.append(title)
        placeholders.append(rf"\{kind}*{{{title}}}")
        if kind == "section":
            placeholders.append(rf"\addcontentsline{{toc}}{{section}}{{{title}}}")
        if title.startswith("Appendix C."):
            # Earlier reviewed sections link to this appendix label.
            placeholders.append(r"\phantomsection\label{app:experiment-stages}")
        placeholders.append("")
    # Four pending subsections plus Sections 9–11 and Appendices A–D.
    expected = [
        "8.2 Pilot--battery divergence tracing",
        "8.3 Post-result I1/I2 pipeline development (historical Phase-6)",
        "8.4 Distinct P2 public-induced-region comparison",
        "8.5 Privileged search-deficit diagnosis",
        "9. Uncertainty mathematics and cross-experiment interpretation",
        "10. Threats to validity and reproducibility",
        "11. Conclusions and falsifiable next questions",
        "Appendix A. Mathematical and numerical interpretation",
        "Appendix B. Archived source and audit provenance",
        "Appendix C. Experimental chronology and method versions",
        "Appendix D. Provisional literature references",
    ]
    if titles != expected:
        raise ValueError(f"Unexpected placeholder headings: {titles!r}")
    result = before.rstrip() + "\n\n" + "\n".join(placeholders) + "\n\\end{document}\n"
    if result.count(r"\end{document}") != 1 or "phase6_aggregate.tex" in result:
        raise ValueError("Unreviewed material was not removed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=REPORT / "review_snapshot")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = ORIGINAL.read_bytes()
    tex = make_snapshot(source.decode("utf-8"))

    with tempfile.TemporaryDirectory(prefix="b1_review8_1_") as directory:
        project = Path(directory)
        (project / "figures").mkdir()
        (project / "main.tex").write_text(tex, encoding="utf-8")
        shutil.copy2(FIGURE, project / "figures" / FIGURE.name)
        readme = (
            "# B1 internal report: reviewed-through-8.1 snapshot\n\n"
            "Sections 1 through 8.1 are preserved from the canonical working report. "
            "Sections after 8.1 and Appendices A-D contain titles only. "
            "This project is for internal review, not public release.\n\n"
            "Import the entire ZIP into Overleaf. Select main.tex as the main "
            "file. Overleaf default pdfLaTeX works without compiler settings. "
            "The compiled PDF is included.\n\n"
            f"Canonical source SHA256: {hashlib.sha256(source).hexdigest()}\n"
        )
        (project / "README.md").write_text(readme, encoding="utf-8")
        result = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
             "-file-line-error", "main.tex"],
            cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if result.returncode:
            print(result.stdout[-7000:])
            raise SystemExit("Snapshot pdfLaTeX compilation failed")
        pdf = project / "main.pdf"
        if not pdf.exists() or pdf.stat().st_size < 1000:
            raise SystemExit("Missing compiled PDF")
        extracted = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            capture_output=True, text=True, check=True
        ).stdout
        # Narrow PDF table cells wrap unpredictably. Check stable unique
        # content and numbers, not phrases split by pdftotext column layout.
        for phrase in ["0.154155", "0.162280", "Appendix C",
                       "Pilot", "FULL343"]:
            if phrase not in extracted:
                raise SystemExit("PDF validation missing " + phrase)
        standalone = output / PDF_NAME
        package = output / ZIP_NAME
        shutil.copy2(pdf, standalone)
        shutil.copy2(pdf, project / PDF_NAME)
        with ZipFile(package, "w", ZIP_DEFLATED, compresslevel=9) as zipfile:
            for name in ["main.tex", "README.md", "figures/phase5_aggregate.tex", PDF_NAME]:
                zipfile.write(project / name, arcname=name)
        with ZipFile(package) as zipfile:
            if zipfile.testzip() is not None:
                raise SystemExit("ZIP integrity check failed")
            if zipfile.read(PDF_NAME) != standalone.read_bytes():
                raise SystemExit("Bundled PDF differs from compiled output")
            if zipfile.read("main.tex").decode("utf-8") != tex:
                raise SystemExit("Bundled LaTeX differs from reviewed snapshot")
        print("B1_REVIEW_THROUGH_8_1_OVERLEAF_PASS")
        print("PDF:", standalone)
        print("ZIP:", package)
        print("Snapshot ZIP bytes:", package.stat().st_size)


if __name__ == "__main__":
    main()
