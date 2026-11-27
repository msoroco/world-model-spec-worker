"""Exercise recorded-only processing on fresh exact-case diagnostic acquisitions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c261489-owner-nov27b"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    configured = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not configured or not Path(configured).resolve().is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("Export scratch output root under .runtime-work before runtime import")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.package_compatibility import materialize_case
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        fixture = SCRATCH / ("post-fixture-" + name + "-v3")
        attempt = SCRATCH / ("post-attempt-" + name + "-v3")
        output = SCRATCH / ("post-output-" + name + "-v3")
        if fixture.exists() or attempt.exists() or output.exists():
            raise ValueError("Fresh diagnostic processing destinations required: " + name)
        materialize(REPO, REPO / entry["fixture_recipe"], fixture)
        materialize_case(MANIFEST, case, attempt, fixture)
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "process-saved", "--manifest", str(MANIFEST), "--case", case,
                   "--attempt", str(attempt), "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             capture_output=True, timeout=600)
        if run.returncode:
            raise RuntimeError(name + " saved processing failed: " + run.stderr[-1800:])
        receipt = json.loads((output / "v0001/processing.json").read_text())
        if (receipt.get("case_id") != case or receipt.get("passed") is not True
                or receipt.get("recorded_only") is not True or receipt.get("originals_preserved") is not True
                or receipt.get("physical_acceptance_claimed") is not False):
            raise ValueError("recorded-only proof did not preserve original sources: " + name)
        log = HERE / ("cpu-process-saved-" + name + ".log")
        log.write_text("recorded-only diagnostic processing passed: " + case + "\n")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$SCRATCH_ROOT .venv-cpu/bin/python runtime.py process-saved --manifest work/"
                       + HERE.name + "/execution-manifest.json --case " + case
                       + " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": "cat $OUTPUT/v0001/feedback.json # " + case,
            "test_log": log.name, "test_log_sha256": sha(log), "test_exit_code": 0,
            "diagnostic_only": True,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(name, "recorded-only diagnostic processing passed", flush=True)


if __name__ == "__main__":
    main()
