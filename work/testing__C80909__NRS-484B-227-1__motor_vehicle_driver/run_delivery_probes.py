"""Test the independent audit's diagnostic path and original-byte rejection."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    failures = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "cases" / suffix
        logs = {}
        for negative in (False, True):
            label = "negative" if negative else "positive"
            output = REPO / ".runtime-work/c80909-delivery-probes" / f"{suffix}-{label}"
            revision = 1
            while output.exists():
                output = REPO / ".runtime-work/c80909-delivery-probes" / f"{suffix}-{label}-{revision}"
                revision += 1
            command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / "delivery_probe.py"),
                       "--case", entry["case_id"], "--output", str(output)]
            if negative:
                command.append("--negative")
            proc = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            log = folder / f"delivery-{label}.log"
            log.write_text(proc.stdout)
            logs[label] = {"command": " ".join(command), "exit_code": proc.returncode,
                           "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
        if (logs["positive"]["exit_code"] != 0 or
                "diagnostic_audit_test_passed" not in (folder / "delivery-positive.log").read_text() or
                logs["negative"]["exit_code"] == 0 or
                "sealed original source changed: ego-body-history.jsonl" not in (folder / "delivery-negative.log").read_text()):
            failures.append(suffix)
            print(suffix, "delivery probe FAILED", flush=True)
            continue
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": logs["positive"]["command"], "test_exit_code": 0,
            "test_log": logs["positive"]["log"], "test_log_sha256": logs["positive"]["log_sha256"],
            "negative_command": logs["negative"]["command"],
            "negative_exit_code": logs["negative"]["exit_code"],
            "negative_expected_error": "sealed original source changed: ego-body-history.jsonl",
            "negative_log": logs["negative"]["log"],
            "negative_log_sha256": logs["negative"]["log_sha256"],
            "scope": "Synthetic diagnostic audit path with four real decoded camera fixtures; actual CARLA pixels, Native provenance and setup remain unverified"}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "diagnostic audit and changed-original rejection passed", flush=True)
    if failures:
        print("failed cases:", failures)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
