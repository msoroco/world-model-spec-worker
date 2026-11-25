"""CPU negative checks for diagnostic source substitution into Native gates."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from runner import _require_reviewed_source_record
from stand_converter_source import audit
from stand_source_sweep import extract


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    scratch = REPO / ".runtime-work"
    with tempfile.TemporaryDirectory(prefix="c135087-source-gate-", dir=scratch) as temporary:
        attempt_dir = Path(temporary) / "attempt"
        env = os.environ.copy()
        env["TMPDIR"] = str(scratch)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run([sys.executable, str(REPO / "runtime.py"), "fixture", "--recipe",
                        str(HERE / "diagnostics/loading_open_waiting-recipe.json"),
                        "--output", str(attempt_dir)], cwd=REPO, env=env,
                       stdout=subprocess.DEVNULL, check=True)
        _checks(attempt_dir)


def _checks(attempt_dir):
    attempt = json.loads((attempt_dir / "attempt-source.json").read_text())
    site = attempt_dir / "site-original.json"
    site_ref = {"path": str(site), "sha256": hashlib.sha256(site.read_bytes()).hexdigest()}
    checks = [
        ("site", lambda: _require_reviewed_source_record(site_ref, "site"),
         "diagnostic site record"),
        ("converter", lambda: audit(attempt_dir, attempt),
         "physical original-run declaration"),
        ("sweep", lambda: extract(attempt_dir, "0" * 64, "0" * 64),
         "original Native acquisition"),
    ]
    for label, check, expected in checks:
        try:
            check()
        except Exception as error:
            if expected not in str(error):
                raise
            print(label + ": synthetic diagnostic rejected: " + str(error))
        else:
            raise AssertionError(label + " accepted synthetic diagnostic")


if __name__ == "__main__":
    main()
