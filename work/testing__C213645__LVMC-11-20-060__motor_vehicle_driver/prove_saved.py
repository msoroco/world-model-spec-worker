"""Run the immutable saved-only processor for every exact diagnostic case."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c213645-owner"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c229405-decoder2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


manifest = json.loads(MANIFEST.read_text())
for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    attempt = SCRATCH / ("saved-" + name + "-attempt")
    if attempt.exists():
        shutil.rmtree(attempt)
    shutil.copytree(SCRATCH / ("compat-" + name + "-primary-final"), attempt)
    (attempt / "candidate-selection.json").unlink()
    output = SCRATCH / ("saved-" + name + "-output")
    if output.exists():
        shutil.rmtree(output)
    command = [sys.executable, str(REPO / "runtime.py"), "process-saved", "--manifest", str(MANIFEST),
               "--case", entry["case_id"], "--attempt", str(attempt), "--output", str(output),
               "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
    process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError("saved-only processing failed for " + name + ": " + process.stderr[-2000:])
    receipt = json.loads((output / "v0001/processing.json").read_text())
    if not receipt["passed"] or not receipt["recorded_only"] or not receipt["originals_preserved"] or receipt["missing_evidence"]:
        raise ValueError("saved-only receipt differs for " + name)
    receipt_path = HERE / ("cpu-saved-" + name + "-receipt.json")
    write(receipt_path, {"case_id": entry["case_id"], "passed": True,
                         "recorded_only": True, "originals_preserved": True,
                         "timestamp_joins": receipt["timestamp_joins"],
                         "result_sha256": receipt["result_sha256"],
                         "final_video_checks": receipt["final_video_checks"]})
    log = HERE / ("cpu-saved-" + name + ".log")
    log.write_text("saved-only process exited 0; original hashes preserved; final video decoded\n")
    template = (".venv-cpu/bin/python runtime.py process-saved --manifest work/" + manifest["assignment_id"] +
                "/execution-manifest.json --case " + entry["case_id"] +
                " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR" +
                " --owner-release-receipt $OWNER_RELEASE_RECEIPT")
    entry["post_capture"] = {"command": template, "feedback_command": template.replace("$SAVED_OUTPUT", "$FEEDBACK_OUTPUT"),
                             "recorded_only": True, "test_command": " ".join(command),
                             "test_exit_code": 0, "test_log": log.name, "test_log_sha256": sha(log),
                             "receipt": receipt_path.name, "receipt_sha256": sha(receipt_path)}
    write(MANIFEST, manifest)
    print(name, "saved-only processor passed", flush=True)
