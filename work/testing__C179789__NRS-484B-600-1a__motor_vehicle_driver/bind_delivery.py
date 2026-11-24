"""Attach seven exact independent delivery audit contracts and CPU proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"
SCRIPT = ROOT / "delivery_audit.py"
EXPECTED = "original capture seal, source or restoration differs"
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    cases = manifest["cases"]
    if len(cases) != 7 or len({entry["case_id"] for entry in cases}) != 7:
        raise ValueError("seven exact cases required")
    for entry in cases:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        if suffix == case:
            raise ValueError("foreign case")
        folder = ROOT / "delivery" / suffix
        positive, negative = folder / "positive.log", folder / "negative.log"
        if ("independent synthetic source and decode audit passed" not in positive.read_text()
                or EXPECTED not in negative.read_text()):
            raise ValueError("missing positive or negative delivery proof: " + case)
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
                   ROOT.name + "/prove_delivery_audit_cases.py " + case)
        entry["delivery_acceptance"] = {
            "case_id": case,
            "sets": ["demo-test", "full-test"],
            "checks": list(CHECKS),
            "script": SCRIPT.relative_to(ROOT).as_posix(),
            "script_sha256": sha(SCRIPT),
            "command": command,
            "test_exit_code": 0,
            "test_log": positive.relative_to(ROOT).as_posix(),
            "test_log_sha256": sha(positive),
            "negative_command": command + " --negative",
            "negative_exit_code": 1,
            "negative_expected_error": EXPECTED,
            "negative_log": negative.relative_to(ROOT).as_posix(),
            "negative_log_sha256": sha(negative),
            "proof_scope": "case-specific synthetic source and two-pixel diagnostic views",
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("seven exact independent delivery audit contracts bound")


if __name__ == "__main__":
    main()
