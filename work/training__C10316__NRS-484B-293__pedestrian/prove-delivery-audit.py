"""Retain CPU delivery boundary tests and selected synthetic rejection."""
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
             str(HERE / "tests"), "-p", "test_delivery_audit.py", "-v"]
    tested = subprocess.run(tests, cwd=ROOT, capture_output=True, text=True)
    test_log = HERE / "update020-delivery-cpu-tests.log"
    test_log.write_text(tested.stdout + tested.stderr)
    if tested.returncode:
        raise RuntimeError("C10316 independent delivery CPU tests failed")
    attempt = ROOT / ".runtime-work/c10316-current-reference-primary-compat"
    saved = ROOT / ".runtime-work/c10316-current-reference-primary-saved/v0001"
    selected = json.loads((HERE / "execution-manifest.json").read_text())
    construction = next(case["construction_sha256"] for case in
                        selected["cases"] if case["case_id"].endswith("__reference"))
    command = [str(PYTHON), str(HERE / "delivery_audit.py"),
               "--attempt", str(attempt), "--saved", str(saved),
               "--owner-receipt", str(attempt / "owner-release.json"),
               "--case", HERE.name + "__reference",
               "--construction-sha256", construction,
               "--pixel-review", str(attempt / "pixel-review.json"),
               "--crossing-review", str(attempt / "crossing-review.json"),
               "--primary-video", str(attempt / "primary.mkv"),
               "--core-trace", str(attempt / "core.json"),
               "--decode-dir", str(attempt / "decode"),
               "--output", str(attempt / "delivery-audit.json")]
    rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    negative_log = HERE / "update020-delivery-selected-negative.log"
    negative_log.write_text(rejected.stdout + rejected.stderr)
    expected = "Original Native capture seal or exit missing"
    if rejected.returncode == 0 or expected not in rejected.stdout + rejected.stderr:
        raise RuntimeError("Selected synthetic attempt passed original delivery audit")
    proof = {"format": "c10316-delivery-audit-cpu-proof-v1",
             "auditor_sha256": sha(HERE / "delivery_audit.py"),
             "tests_command": " ".join(tests), "tests_exit_code": 0,
             "tests_log": test_log.name, "tests_log_sha256": sha(test_log),
             "selected_negative_command": " ".join(command),
             "selected_negative_exit_code": rejected.returncode,
             "selected_negative_expected_error": expected,
             "selected_negative_log": negative_log.name,
             "selected_negative_log_sha256": sha(negative_log),
             "source_shaped_unit_test_only": True,
             "original_delivery_acceptance_proven": False,
             "legal_verdict_claimed": False}
    path = HERE / "update020-delivery-cpu-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"tests": 2, "selected_synthetic_rejected": True,
                      "original_delivery_acceptance_proven": False,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
