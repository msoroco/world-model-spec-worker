"""Run saved-only processing and missing-original-source rejection per exact case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
COMPAT = REPO / ".runtime-work/c177249-compat-all-v2"
SCRATCH = REPO / ".runtime-work/c177249-saved-all-v2"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, result):
    target = HERE / name
    temporary = SCRATCH / (name + ".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2).rstrip() + "\n")
    os.replace(temporary, target)
    return target


def call(command):
    done = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "TMPDIR": str(REPO / ".runtime-work"),
                               "MPLCONFIGDIR": str(REPO / ".runtime-work/mpl")})
    if done.returncode:
        raise ValueError("saved-only command failed: " + done.stderr[-1500:])
    return json.loads(done.stdout)


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id.removeprefix(HERE.name + "__")
        attempt = COMPAT / (name + "-primary")
        selection = attempt / "candidate-selection.json"
        if selection.exists():
            selection.unlink()
        output = SCRATCH / ("positive-" + name)
        command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        result = call(command)
        if not result.get("passed") or result.get("missing_evidence") or not result.get("originals_preserved") or not result.get("timestamp_joins", {}).get("passed"):
            raise ValueError("positive saved-only proof incomplete: " + name)
        positive_log = save("cpu-saved-" + name + ".log", result)
        missing_attempt = SCRATCH / ("missing-attempt-" + name)
        shutil.copytree(attempt, missing_attempt)
        (missing_attempt / "history.json").unlink()
        missing_output = SCRATCH / ("missing-output-" + name)
        negative = command.copy()
        negative[negative.index("--attempt") + 1] = str(missing_attempt)
        negative[negative.index("--output") + 1] = str(missing_output)
        failure = call(negative)
        if not failure.get("missing_evidence") or "history.json" not in (missing_output / "v0001/feedback.json").read_text():
            raise ValueError("missing original history not classified: " + name)
        negative_log = save("cpu-saved-" + name + "-missing.log", failure)
        entry["post_capture"] = {"command": " ".join(command),
                                 "feedback_command": " ".join(negative),
                                 "test_log": positive_log.name,
                                 "test_log_sha256": sha(positive_log),
                                 "test_exit_code": 0,
                                 "feedback_log": negative_log.name,
                                 "feedback_log_sha256": sha(negative_log),
                                 "feedback_test_exit_code": 0,
                                 "recorded_only": True,
                                 "diagnostic_fixture": True,
                                 "physical_acceptance_claimed": False}
        print(name, "saved positive and negative passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    run()
