"""Bind positive and negative exact-case delivery preparation checks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / ".runtime-work" / "c111125_9b_owner_nov24d"
MANIFEST = FOLDER / "execution-manifest.json"
SCRIPT = FOLDER / "audit_delivery_prepared.py"


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def run(command: list[str], log: Path) -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH.resolve()),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str((SCRATCH / "output").resolve()))
    result = subprocess.run(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    clean = "\n".join(line.rstrip() for line in result.stdout.rstrip().splitlines()) + "\n"
    log.write_text(clean)
    return result.returncode


def main() -> None:
    data = json.loads(MANIFEST.read_text())
    for entry in data["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        attempt = SCRATCH / f"saved-attempt-post-{suffix}"
        command = [sys.executable, str(SCRIPT), "--case", case,
                   "--attempt", str(attempt), "--manifest", str(MANIFEST)]
        positive = FOLDER / f"audit-{suffix}-positive.log"
        negative = FOLDER / f"audit-{suffix}-negative.log"
        positive_code = run(command, positive)
        negative_command = command + ["--negative-missing-source"]
        negative_code = run(negative_command, negative)
        if positive_code or negative_code != 1 or "sealed original missing or changed" not in negative.read_text():
            raise RuntimeError(f"Delivery audit failed for {suffix}: {positive_code}/{negative_code}")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "command": " ".join(command), "negative_command": " ".join(negative_command),
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT.read_bytes()),
            "test_exit_code": positive_code, "test_log": positive.name,
            "test_log_sha256": sha(positive.read_bytes()),
            "negative_exit_code": negative_code,
            "negative_expected_error": "sealed original missing or changed",
            "negative_log": negative.name, "negative_log_sha256": sha(negative.read_bytes()),
            "scope": "CPU diagnostic preparation; physical and legal acceptance are pending",
        }
        print(suffix, "delivery audit", positive_code, negative_code, flush=True)
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
