"""Run independent delivery audit on every diagnostic case and missing source."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c394507-nov26"
MANIFEST = HERE / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
ERROR = "Missing required source: original-crosswalk-history.json"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    value = value.rstrip()
    return value + "\n" if value else ""


def main():
    os.environ["TMPDIR"] = os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        tokens = shlex.split(entry["compatibility"]["command"])
        attempt = Path(tokens[tokens.index("--output") + 1])
        result = SCRATCH / ("delivery-audit-" + tag + "-" + str(time.time_ns()) + ".json")
        command = [PYTHON, str(HERE / "delivery_audit.py"),
                   "--case-id", entry["case_id"], "--attempt", str(attempt),
                   "--plan", str(HERE / "case-plan.json"), "--output", str(result)]
        positive = subprocess.run(command, cwd=REPO, env=os.environ,
                                  capture_output=True, text=True, timeout=300)
        if positive.returncode:
            raise RuntimeError(tag + " positive audit: " +
                               (positive.stdout + positive.stderr)[-1600:])
        data = json.loads(result.read_text())
        if (data.get("source_video_join") is not True or
                len(data.get("four_view_full_decode", {})) != 4 or
                data.get("physical_acceptance_claimed") is not False):
            raise ValueError("incomplete independent diagnostic audit: " + tag)
        positive_log = HERE / ("proof-delivery-" + tag + ".log")
        positive_log.write_text(clean(positive.stdout + positive.stderr))
        missing = SCRATCH / ("delivery-missing-" + tag + "-" + str(time.time_ns()))
        shutil.copytree(attempt, missing)
        (missing / "original-crosswalk-history.json").unlink()
        negative_command = command.copy()
        negative_command[negative_command.index("--attempt") + 1] = str(missing)
        negative_command[negative_command.index("--output") + 1] = str(
            SCRATCH / ("delivery-negative-" + tag + "-" + str(time.time_ns()) + ".json"))
        negative = subprocess.run(negative_command, cwd=REPO, env=os.environ,
                                  capture_output=True, text=True, timeout=300)
        negative_log = HERE / ("proof-delivery-" + tag + "-negative.log")
        negative_log.write_text(clean(negative.stdout + negative.stderr))
        if negative.returncode == 0 or ERROR not in negative_log.read_text():
            raise ValueError("missing original crosswalk source accepted: " + tag)
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative.returncode,
            "negative_expected_error": ERROR,
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        print(tag, "delivery audit positive/negative passed", flush=True)


if __name__ == "__main__":
    main()
