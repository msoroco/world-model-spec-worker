"""Reproduce controlled-input checks and reject non-delivery CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    tests_command = [str(PYTHON), "-m", "unittest", "discover", "-s",
                     str(HERE / "tests"), "-p", "test_comparison*.py", "-v"]
    tests = subprocess.run(tests_command, cwd=REPO, text=True, capture_output=True)
    (HERE / "comparison-cpu-tests.log").write_text(tests.stdout + tests.stderr)
    if tests.returncode:
        raise RuntimeError("Controlled comparison CPU tests failed")
    source = HERE / "delivery-audit-cpu-proof.json"
    command = [str(PYTHON), str(HERE / "comparison_audit.py"),
               "--reference-audit", str(source), "--contrast-audit", str(source),
               "--output", str(REPO / ".runtime-work/c10014-invalid-comparison.json")]
    negative = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    (HERE / "comparison-audit-negative.log").write_text(
        negative.stdout + negative.stderr)
    expected = "Comparison needs independent original delivery acceptance"
    if negative.returncode == 0 or expected not in (negative.stdout + negative.stderr):
        raise RuntimeError("CPU proof was accepted as an original comparison")
    proof = {"format": "c10014-comparison-audit-cpu-proof-v1",
             "script": "comparison_audit.py",
             "script_sha256": sha(HERE / "comparison_audit.py"),
             "tests_command": " ".join(tests_command), "tests_exit_code": 0,
             "tests_log": "comparison-cpu-tests.log",
             "tests_log_sha256": sha(HERE / "comparison-cpu-tests.log"),
             "negative_command": " ".join(command),
             "negative_exit_code": negative.returncode,
             "negative_expected_error": expected,
             "negative_log": "comparison-audit-negative.log",
             "negative_log_sha256": sha(HERE / "comparison-audit-negative.log"),
             "original_comparison_accepted": False}
    (HERE / "comparison-audit-cpu-proof.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"tests": (tests.stdout + tests.stderr).count(" ... ok"),
                      "nonoriginal_receipt_rejected": True,
                      "proof_sha256": sha(HERE / "comparison-audit-cpu-proof.json")}))


if __name__ == "__main__":
    main()
