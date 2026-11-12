"""Reproduce C10014 audit unit tests and selected synthetic rejection."""
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
    case_id = HERE.name + "__reference"
    selected = json.loads((HERE / "execution-manifest.json").read_text())["cases"][0]
    command = [str(PYTHON), "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-v"]
    tests = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    (HERE / "root-tests.log").write_text(tests.stdout + tests.stderr)
    if tests.returncode:
        raise RuntimeError("Assignment CPU tests failed: root-tests.log")
    negative = [str(PYTHON), str(HERE / "delivery_audit.py"),
        "--attempt", str(REPO / ".runtime-work/c10014-update021-reference-primary-compat"),
        "--saved", str(REPO / ".runtime-work/c10014-update021-reference-primary-saved/v0001"),
        "--owner-receipt", str(REPO / ".runtime-work/c10014-update021-reference-primary-compat/owner-release.json"),
        "--case", case_id,
        "--construction-sha256", selected["construction_sha256"]]
    rejected = subprocess.run(negative, cwd=REPO, text=True, capture_output=True)
    (HERE / "delivery-audit-negative.log").write_text(rejected.stdout + rejected.stderr)
    expected = "Missing sealed Native capture"
    if rejected.returncode == 0 or expected not in (rejected.stdout + rejected.stderr):
        raise RuntimeError("Synthetic selected attempt was not rejected as expected")
    proof = {
        "format": "c10014-delivery-audit-cpu-proof-v1",
        "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
        "tests_command": " ".join(command), "tests_exit_code": 0,
        "tests_log": "root-tests.log", "tests_log_sha256": sha(HERE / "root-tests.log"),
        "negative_command": " ".join(negative),
        "negative_exit_code": rejected.returncode,
        "negative_expected_error": expected,
        "negative_log": "delivery-audit-negative.log",
        "negative_log_sha256": sha(HERE / "delivery-audit-negative.log"),
        "original_native_accepted": False,
        "full_delivery_acceptance_proven": False,
    }
    (HERE / "delivery-audit-cpu-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    root = json.loads((HERE / "root-offline-proof.json").read_text())
    root["tests_exit_code"] = 0
    root["tests_log_sha256"] = sha(HERE / "root-tests.log")
    (HERE / "root-offline-proof.json").write_text(json.dumps(root, indent=2) + "\n")
    print(json.dumps({"tests": (tests.stdout + tests.stderr).count(" ... ok"),
                      "synthetic_rejected": True,
                      "audit_proof_sha256": sha(HERE / "delivery-audit-cpu-proof.json")}))


if __name__ == "__main__":
    main()
