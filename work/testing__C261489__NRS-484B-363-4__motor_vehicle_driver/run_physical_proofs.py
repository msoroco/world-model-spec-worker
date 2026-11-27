"""Bind three source-based physical outcome probes and lifecycle CPU proof per case."""

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
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    focused = (HERE / "cpu-focused-tests.log").read_text()
    if ("test_exact_original_frames_four_cameras_and_world_restore" not in focused
            or "OK" not in focused):
        raise ValueError("Native capture restoration fixture proof missing")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        name = case[len(HERE.name) + 2:]
        fixtures = []
        for kind in KINDS:
            result = HERE / ("physical-" + name + "-" + kind + ".json")
            log = HERE / ("physical-" + name + "-" + kind + ".log")
            command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / "physical_completion.py"),
                       "--case", case, "--kind", kind, "--output", str(result)]
            completed = subprocess.run(command, cwd=REPO, env=env, text=True,
                                       capture_output=True, timeout=60)
            if completed.returncode:
                raise RuntimeError(name + " " + kind + ": " + completed.stderr[-1000:])
            value = json.loads(result.read_text())
            if value["physical_checks"]["maneuver"]["status"] != {
                    "complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]:
                raise ValueError("physical outcome classifier mismatch")
            log.write_text("synthetic diagnostic physical outcome passed: " + case + " " + kind + "\n")
            fixtures.append({"kind": kind, "command": shlex.join(command),
                             "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        receipt = SCRATCH / ("post-output-" + name + "-v3/v0001/processing.json")
        processing = json.loads(receipt.read_text())
        if (processing.get("case_id") != case or processing.get("recorded_only") is not True
                or processing.get("originals_preserved") is not True
                or "saved_processing_started" not in processing.get("events", [])):
            raise ValueError("recorded-only lifecycle fixture proof missing")
        lifecycle_log = HERE / ("physical-" + name + "-lifecycle.log")
        lifecycle_log.write_text("synthetic capture restoration test and exact recorded-only processing passed: "
                                 + case + "\n")
        proof = {"format": "worker-physical-preparation", "case_id": case,
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures,
                 "lifecycle": {"events": EVENTS, "exit_code": 0,
                               "command": "python -m unittest test_native_capture; runtime.py process-saved --case " + case,
                               "log": lifecycle_log.name, "log_sha256": sha(lifecycle_log),
                               "diagnostic_only": True}}
        path = HERE / ("physical-" + name + "-proof.json")
        path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        entry["physical_preparation"] = {"receipt": path.name, "sha256": sha(path)}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(name, "three physical outcome and lifecycle CPU probes passed", flush=True)


if __name__ == "__main__":
    main()
