"""Bind positive and negative CPU evidence for original delivery acceptance."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    script = ROOT / "independent/delivery_audit.py"
    proof = ROOT / "independent/prove_delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        folder = ROOT / "cases" / case.split("__")[-1]
        positive = folder / "delivery-positive.log"
        negative = folder / "delivery-negative.log"
        command = [sys.executable, str(proof), case]
        passed = subprocess.run(command, text=True, capture_output=True)
        failed = subprocess.run(command + ["--negative"], text=True, capture_output=True)
        positive.write_text((passed.stdout + passed.stderr).rstrip() + "\n")
        negative.write_text((failed.stdout + failed.stderr).rstrip() + "\n")
        expected = "original pixel review source changed"
        if passed.returncode != 0 or failed.returncode == 0 or expected not in negative.read_text():
            raise ValueError("delivery proof did not pass/reject: " + case)
        base = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ASSIGNMENT +
                "/independent/prove_delivery_audit.py " + case)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"], "checks": CHECKS,
            "script": str(script.relative_to(ROOT)), "script_sha256": sha(script),
            "command": base, "test_exit_code": passed.returncode,
            "test_log": str(positive.relative_to(ROOT)), "test_log_sha256": sha(positive),
            "negative_command": base + " --negative", "negative_exit_code": failed.returncode,
            "negative_expected_error": expected,
            "negative_log": str(negative.relative_to(ROOT)), "negative_log_sha256": sha(negative),
        }
        saved = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
                 "--manifest work/" + ASSIGNMENT + "/execution-manifest.json --case " + case +
                 " --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" --library \"$LIBRARY\" "
                 "--validator \"$VALIDATOR\" --owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"")
        entry["post_capture"] = {"recorded_only": True, "command": saved,
                                 "feedback_command": saved,
                                 "proof_scope": "diagnostic CPU fixture; original capture requires independent review"}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("six exact delivery acceptance audits bound")


if __name__ == "__main__":
    build()
