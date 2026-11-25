"""Prove canonical saved-only processing of six exact CPU diagnostic bundles."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"
RUNTIME = REPO / "runtime.py"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c111610-saved-runtime")
    environment["TMPDIR"] = str(REPO / ".runtime-work")
    return subprocess.run(command, cwd=REPO, env=environment, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        tag = str(time.time_ns())
        fixture = REPO / ".runtime-work" / ("c111610-saved-fixture-" + suffix + "-" + tag)
        attempt = REPO / ".runtime-work" / ("c111610-saved-attempt-" + suffix + "-" + tag)
        output = REPO / ".runtime-work" / ("c111610-saved-output-" + suffix + "-" + tag)
        recipe = REPO / entry["fixture_recipe"]
        for command in ([str(PYTHON), str(RUNTIME), "fixture", "--recipe", str(recipe), "--output", str(fixture)],
                        [str(PYTHON), str(RUNTIME), "materialize", "--manifest", str(MANIFEST),
                         "--case", entry["case_id"], "--output", str(attempt)]):
            result = call(command)
            if result.returncode:
                raise RuntimeError(suffix + ": " + result.stdout[-1500:])
        for source in fixture.iterdir():
            destination = attempt / source.name
            if destination.exists():
                raise ValueError("diagnostic fixture shadows exact construction: " + source.name)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copyfile(source, destination)
        command = [str(PYTHON), str(RUNTIME), "process-saved", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--attempt", str(attempt),
                   "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        result = call(command)
        log = HERE / ("saved-" + suffix + ".log")
        log.write_text(result.stdout.rstrip("\n") + "\n")
        if result.returncode:
            raise RuntimeError(suffix + ": " + result.stdout[-1500:])
        entry["post_capture"] = {"recorded_only": True, "command": " ".join(command),
            "feedback_command": " ".join(command), "test_exit_code": 0,
            "test_log": log.name, "test_log_sha256": sha(log),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "saved-only=0", flush=True)


if __name__ == "__main__":
    main()
