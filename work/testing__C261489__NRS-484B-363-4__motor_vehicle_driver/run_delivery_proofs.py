"""Bind exact-case diagnostic delivery-auditor positive and missing-source proofs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c261489-owner-nov27b"
MANIFEST = HERE / "execution-manifest.json"
SCRIPT = HERE / "delivery_audit.py"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(text: str, path: Path) -> None:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    path.write_text("\n".join(lines) + "\n")


def command(case: str, attempt: Path, output: Path) -> list[str]:
    return [str(REPO / ".venv-cpu/bin/python"), str(SCRIPT), "--diagnostic",
            "--case", case, "--attempt", str(attempt), "--output", str(output)]


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        attempt = SCRATCH / ("compat-" + name + "-v3")
        output = SCRATCH / ("delivery-audit-" + name + "-v3.json")
        positive = command(case, attempt, output)
        run = subprocess.run(positive, env=env, cwd=REPO, text=True,
                             capture_output=True, timeout=600)
        if run.returncode:
            raise RuntimeError(name + " delivery proof: " + run.stderr[-2000:])
        result = json.loads(output.read_text())
        if result.get("case_id") != case or result.get("frame_count") != 9 or not result.get("diagnostic_fixture"):
            raise ValueError("diagnostic delivery result mismatched: " + name)
        log = HERE / ("cpu-delivery-" + name + ".log")
        clean_log("diagnostic source audit passed: " + case + "\n" + run.stdout, log)
        missing = SCRATCH / ("missing-delivery-source-" + name)
        negative = command(case, missing, SCRATCH / ("negative-delivery-" + name + ".json"))
        rejected = subprocess.run(negative, env=env, cwd=REPO, text=True,
                                  capture_output=True, timeout=60)
        phrase = "Missing required source: context.json"
        if rejected.returncode == 0 or phrase not in rejected.stderr:
            raise ValueError("missing-source delivery audit was not rejected: " + name)
        neglog = HERE / ("cpu-delivery-" + name + "-negative.log")
        clean_log(rejected.stdout + rejected.stderr, neglog)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(SCRIPT),
            "command": shlex.join(positive), "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": sha(log),
            "negative_command": shlex.join(negative),
            "negative_exit_code": rejected.returncode,
            "negative_expected_error": phrase,
            "negative_log": neglog.name, "negative_log_sha256": sha(neglog),
        }
        print(name, "diagnostic delivery audit positive/negative passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
