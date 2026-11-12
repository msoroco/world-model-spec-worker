"""Retain CPU verifier tests and rejection of the selected synthetic attempt."""
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
    test_command = [str(PYTHON), "-m", "unittest", "discover", "-s",
                    str(HERE / "tests"), "-p", "test_lifecycle_audit.py", "-v"]
    tested = subprocess.run(test_command, cwd=REPO, capture_output=True, text=True)
    (HERE / "update019-lifecycle-cpu-tests.log").write_text(tested.stdout + tested.stderr)
    if tested.returncode:
        raise RuntimeError("Lifecycle CPU tests failed")
    attempt = REPO / ".runtime-work/c10316-current-reference-primary-compat"
    saved = REPO / ".runtime-work/c10316-current-reference-primary-saved/v0001"
    command = [str(PYTHON), str(HERE / "lifecycle_audit.py"),
               "--attempt", str(attempt),
               "--owner-receipt", str(attempt / "owner-release.json"),
               "--processing", str(saved / "processing.json"),
               "--case", HERE.name + "__reference",
               "--construction-sha256", json.loads(
                   (HERE / "execution-manifest.json").read_text())["cases"][0]["construction_sha256"]]
    rejected = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    (HERE / "update019-lifecycle-audit-negative.log").write_text(rejected.stdout + rejected.stderr)
    expected = "Original Native capture seal or exit missing"
    if rejected.returncode == 0 or expected not in rejected.stdout + rejected.stderr:
        raise RuntimeError("Selected synthetic attempt passed Native lifecycle audit")
    proof = {"format":"c10316-lifecycle-audit-cpu-proof-v1",
             "script":"lifecycle_audit.py","script_sha256":sha(HERE / "lifecycle_audit.py"),
             "tests_command":" ".join(test_command),"tests_exit_code":0,
             "tests_log":"update019-lifecycle-cpu-tests.log",
             "tests_log_sha256":sha(HERE / "update019-lifecycle-cpu-tests.log"),
             "negative_command":" ".join(command),
             "negative_exit_code":rejected.returncode,
             "negative_expected_error":expected,
             "negative_log":"update019-lifecycle-audit-negative.log",
             "negative_log_sha256":sha(HERE / "update019-lifecycle-audit-negative.log"),
             "original_native_lifecycle_proven":False,
             "physical_preparation_proven":False}
    (HERE / "update019-lifecycle-audit-cpu-proof.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"tests":2,"synthetic_rejected":True,
                      "proof_sha256":sha(HERE / "update019-lifecycle-audit-cpu-proof.json")}))


if __name__ == "__main__":
    main()
