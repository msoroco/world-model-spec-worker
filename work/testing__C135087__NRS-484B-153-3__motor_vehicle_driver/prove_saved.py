"""Test current selected saved-only path, positive and missing-door feedback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
SCRATCH = REPO / ".runtime-work/c135087-owner-nov26"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command):
    done = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError("saved-only failed: " + " ".join(command) + "\n" + done.stderr[-3000:])
    return json.loads(done.stdout)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        kind = entry["case_id"].removeprefix(HERE.name + "__")
        attempt = SCRATCH / ("compat-current-" + kind + "-primary")
        selection = attempt / "candidate-selection.json"
        if selection.exists():
            selection.unlink()
        output = SCRATCH / ("saved-final-current-" + kind)
        cmd = [PYTHON, str(REPO / "runtime.py"), "process-saved", "--manifest", str(MANIFEST),
               "--case", entry["case_id"], "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        positive = call(cmd)
        if not positive["passed"] or positive["missing_evidence"] or not positive["originals_preserved"] or not positive["timestamp_joins"]["passed"]:
            raise ValueError("positive saved-only result incomplete: " + kind)
        log = HERE / ("cpu-saved-" + kind + ".log")
        log.write_text(json.dumps(positive, sort_keys=True, indent=2) + "\n")
        missing = SCRATCH / ("saved-final-missing-attempt-" + kind)
        shutil.copytree(attempt, missing)
        (missing / "door.json").unlink()
        negative = SCRATCH / ("saved-final-missing-" + kind)
        ncmd = cmd.copy()
        ncmd[ncmd.index("--attempt") + 1] = str(missing)
        ncmd[ncmd.index("--output") + 1] = str(negative)
        failure = call(ncmd)
        if not failure["missing_evidence"] or "door.json" not in (negative / "v0001/feedback.json").read_text():
            raise ValueError("missing door source not classified: " + kind)
        neglog = HERE / ("cpu-saved-" + kind + "-missing.log")
        neglog.write_text(json.dumps(failure, sort_keys=True, indent=2) + "\n")
        entry["post_capture"] = {"command": " ".join(cmd), "feedback_command": " ".join(ncmd),
                                 "test_log": log.name, "test_log_sha256": sha(log), "test_exit_code": 0,
                                 "feedback_log": neglog.name, "feedback_log_sha256": sha(neglog),
                                 "feedback_test_exit_code": 0, "recorded_only": True,
                                 "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        print("saved-only positive+negative", kind, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    prove()
