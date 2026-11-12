"""Retain controlled-pair CPU tests and selected diagnostic rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    tests = [str(PYTHON), "-m", "unittest", "discover", "-s",
             str(HERE / "tests"), "-p", "test_comparison_audit.py", "-v"]
    tested = subprocess.run(tests, cwd=ROOT, capture_output=True, text=True)
    test_log = HERE / "update021-comparison-cpu-tests.log"
    test_log.write_text(tested.stdout + tested.stderr)
    if tested.returncode:
        raise RuntimeError("Selected crosswalk comparison CPU tests failed")
    reference = (ROOT / ".runtime-work" /
                 "c10316-current-reference-primary-compat/compatibility.json")
    contrast = (ROOT / ".runtime-work" /
                "c10316-current-contrast-primary-compat/compatibility.json")
    output = HERE / "update021-unaccepted-comparison.json"
    command = [str(PYTHON), str(HERE / "comparison_audit.py"),
               "--reference-audit", str(reference),
               "--contrast-audit", str(contrast),
               "--output", str(output)]
    rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    negative_log = HERE / "update021-comparison-selected-negative.log"
    negative_log.write_text(rejected.stdout + rejected.stderr)
    expected = "Comparison requires independent original delivery acceptance"
    if rejected.returncode == 0 or expected not in rejected.stdout + rejected.stderr or output.exists():
        raise RuntimeError("Synthetic compatibility receipt passed original comparison")
    proof = {"format": "c10316-comparison-audit-cpu-proof-v1",
             "auditor_sha256": sha(HERE / "comparison_audit.py"),
             "tests_command": " ".join(tests), "tests_exit_code": 0,
             "tests_log": test_log.name, "tests_log_sha256": sha(test_log),
             "selected_negative_command": " ".join(command),
             "selected_negative_exit_code": rejected.returncode,
             "selected_negative_expected_error": expected,
             "selected_negative_log": negative_log.name,
             "selected_negative_log_sha256": sha(negative_log),
             "controlled_source_shaped_pairs": 4,
             "original_comparison_acceptance_proven": False,
             "legal_verdict_claimed": False}
    path = HERE / "update021-comparison-cpu-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"tests": 3, "selected_synthetic_rejected": True,
                      "original_comparison_acceptance_proven": False,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
