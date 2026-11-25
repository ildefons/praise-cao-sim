"""Reproduce v0.100 analytical tables from archived, frozen run evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
manifest = json.loads((DATA / "analytical_revision_manifest.json").read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
archive = DATA / "analytical_revision_inputs_v0.100.zip"
assert sha(archive) == manifest["input_archive_sha256"]
for name, digest in manifest["outputs_sha256"].items():
    assert sha(DATA / name) == digest, name
with tempfile.TemporaryDirectory(prefix="praise_analytical_") as tmp:
    root = Path(tmp) / "inputs"
    root.mkdir()
    out = Path(tmp) / "output"
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == set(manifest["input_sha256"])
        for name, digest in manifest["input_sha256"].items():
            raw = z.read(name)
            assert hashlib.sha256(raw).hexdigest() == digest, name
            (root / name).write_bytes(raw)
    assert sha(DATA / "combined_nine_policy_budget_summary.csv") == manifest["input_sha256"]["combined_nine_policy_budget_summary.csv"]
    subprocess.run([sys.executable, str(HERE / "audit_intervals.py"), str(root), str(out)], check=True)
    for name in manifest["outputs_sha256"]:
        pd.testing.assert_frame_equal(pd.read_csv(DATA / name), pd.read_csv(out / name), check_exact=False, rtol=1e-10, atol=1e-12)
        print("REPRODUCED", name)
print("PRAISE_ANALYTICAL_REVISION_PASS")
