#!/usr/bin/env bash
# Compile and publish the current B1 Overleaf PDF and matching project ZIP.
# Run from any directory inside praise-cao-sim, on the report branch.
set -euo pipefail

branch="praise-identifiability-feasibility"
root="$(git rev-parse --show-toplevel)"
cd "$root"

if [[ "$(git branch --show-current)" != "$branch" ]]; then
  echo "ERROR: switch to $branch first." >&2
  exit 1
fi
for tool in latexmk xelatex zip unzip pdfinfo pdftotext python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: $tool is not installed." >&2
    echo "On Ubuntu, install the LaTeX prerequisites:" >&2
    echo "  sudo apt-get update" >&2
    echo "  sudo apt-get install -y texlive-xetex texlive-latex-extra texlive-pictures texlive-fonts-recommended texlive-plain-generic latexmk zip unzip poppler-utils fonts-dejavu-core" >&2
    exit 1
  fi
done

report="first_science/b1/report"
pdf="$report/B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf"
archive="$report/B1_OVERLEAF_PROJECT_V0_1.zip"

if [[ -n "$(git status --porcelain --untracked-files=no -- "$report/overleaf/main.tex" "$report/overleaf/README.md" "$report/overleaf/figures")" ]]; then
  echo "ERROR: uncommitted changes exist in the Overleaf source. Commit or stash them before rebuilding." >&2
  exit 1
fi

# In TeX, an unescaped percent sign comments out the rest of the line.
# Reject inline comments with trailing prose; comments ending the line are allowed.
python3 - "$report/overleaf/main.tex" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
    for pos, char in enumerate(line):
        if char != "%":
            continue
        backslashes = len(line[:pos]) - len(line[:pos].rstrip("\\\\"))
        if backslashes % 2 == 0 and line[:pos].strip() and line[pos + 1:].strip():
            raise SystemExit(
                f"ERROR: unescaped inline percent sign in {source}:{number}. "
                "Use \\\\% in ordinary LaTeX prose."
            )
print("LaTeX percent-sign preflight passed.")
PY

(
  cd "$report/overleaf"
  latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
  test -s main.pdf
  # Confirm that the final Section 4.1 paragraph survived TeX rendering.
  python3 - <<'PY'
import re
import subprocess
pdf_text = subprocess.check_output(["pdftotext", "-layout", "main.pdf", "-"], text=True)
normalized = re.sub(r"\s+", " ", pdf_text)
for phrase in ["80% of individual requests", "may be higher or lower"]:
    if phrase not in normalized:
        raise SystemExit(
            f"ERROR: compiled PDF does not contain expected Section 4.1 text: {phrase!r}"
        )
print("Section 4.1 PDF text verification passed.")
PY
  pdfinfo main.pdf | grep -E 'Pages:|Page size:'
  cp main.pdf ../B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf
  cp main.pdf B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf
  rm -f ../B1_OVERLEAF_PROJECT_V0_1.zip
  zip -q -9 -r ../B1_OVERLEAF_PROJECT_V0_1.zip main.tex README.md figures B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf
)

unzip -tqq "$archive"
test -s "$pdf"
unzip -p "$archive" B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf | cmp - "$pdf"
echo "Compiled: $pdf"
echo "Packaged: $archive"

git add -- "$pdf" "$archive"
if git diff --cached --quiet -- "$pdf" "$archive"; then
  echo "PDF and ZIP are already identical to the committed deliverables."
else
  git commit -m "Publish locally compiled B1 PDF and Overleaf ZIP" -- "$pdf" "$archive"
fi

git push origin "$branch"
echo "Published the PDF and ZIP to origin/$branch."
