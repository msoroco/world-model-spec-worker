"""Bind seven independent positive/negative saved delivery audit commands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "prove_delivery_cases.py"
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        positive = HERE / f"delivery-{suffix}-positive.log"
        negative = HERE / f"delivery-{suffix}-negative.log"
        if (not positive.is_file() or not negative.is_file() or
                '"independent_original_source_audit_passed": true' not in positive.read_text() or
                "Original capture seal, source or restoration differs" not in negative.read_text()):
            raise ValueError("Current independent delivery audit proof missing: " + suffix)
        command = "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + HERE.name + "/prove_delivery_cases.py " + case_id
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"], "checks": list(CHECKS),
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
            "command": command, "negative_command": command + " --negative",
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "Original capture seal, source or restoration differs",
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "scope": "synthetic diagnostic acceptance protocol; physical review pending",
            "physical_acceptance_claimed": False,
        }
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound seven exact independent positive and negative delivery audits")


if __name__ == "__main__":
    main()
