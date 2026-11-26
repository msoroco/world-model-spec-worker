"""Bind source-preserving saved-only positive and missing-source feedback proofs."""

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
VALIDATOR = str(REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command):
    run = subprocess.run(command, cwd=REPO, env=os.environ,
                         capture_output=True, text=True, timeout=600)
    if run.returncode:
        raise RuntimeError((run.stdout + run.stderr)[-3000:])
    return json.loads(run.stdout)


def main():
    os.environ["TMPDIR"] = os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        tokens = shlex.split(entry["compatibility"]["command"])
        attempt = Path(tokens[tokens.index("--output") + 1])
        selection = attempt / "candidate-selection.json"
        if selection.exists():
            selection.unlink()
        output = SCRATCH / ("saved-" + tag + "-" + str(time.time_ns()))
        command = [PYTHON, str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"),
                   "--validator", VALIDATOR]
        positive = call(command)
        if (positive.get("passed") is not True or positive.get("missing_evidence") or
                positive.get("originals_preserved") is not True or
                positive.get("timestamp_joins", {}).get("passed") is not True):
            raise ValueError("source-preserving saved proof incomplete: " + tag)
        positive_log = HERE / ("proof-saved-" + tag + ".log")
        positive_log.write_text(json.dumps(positive, sort_keys=True, indent=2) + "\n")
        missing = SCRATCH / ("saved-missing-attempt-" + tag + "-" + str(time.time_ns()))
        shutil.copytree(attempt, missing)
        (missing / "original-crosswalk-history.json").unlink()
        negative_output = SCRATCH / ("saved-negative-" + tag + "-" + str(time.time_ns()))
        negative_command = command.copy()
        negative_command[negative_command.index("--attempt") + 1] = str(missing)
        negative_command[negative_command.index("--output") + 1] = str(negative_output)
        negative = call(negative_command)
        if (not negative.get("missing_evidence") or
                "original-crosswalk-history.json" not in
                (negative_output / "v0001/feedback.json").read_text()):
            raise ValueError("missing original crosswalk source not classified: " + tag)
        negative_log = HERE / ("proof-saved-" + tag + "-missing.log")
        negative_log.write_text(json.dumps(negative, sort_keys=True, indent=2) + "\n")
        entry["post_capture"] = {
            "command": " ".join(command),
            "feedback_command": " ".join(negative_command),
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "test_exit_code": 0, "feedback_log": negative_log.name,
            "feedback_log_sha256": sha(negative_log), "feedback_test_exit_code": 0,
            "recorded_only": True, "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}
        MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        print(tag, "saved-only positive/negative passed", flush=True)


if __name__ == "__main__":
    main()
