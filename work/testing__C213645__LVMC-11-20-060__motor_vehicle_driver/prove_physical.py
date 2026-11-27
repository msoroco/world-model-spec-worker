"""Exercise complete, incomplete and source-gap physical outcomes per case."""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


manifest = json.loads(MANIFEST.read_text())
for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    base = SCRATCH / ("compat-" + name + "-primary-final")
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        attempt = SCRATCH / ("physical-" + name + "-" + kind)
        if attempt.exists():
            shutil.rmtree(attempt)
        attempt.mkdir()
        for filename in ("config.json", "construction.json", "trace.jsonl", "video_frames.jsonl",
                         "fixture-provenance.json"):
            shutil.copy2(base / filename, attempt / filename)
        shutil.copytree(base / "original-attempt", attempt / "original-attempt")
        activity_path = attempt / "original-attempt/activity.json"
        inventory_path = attempt / "original-attempt/inventory.json"
        activity = json.loads(activity_path.read_text())
        if kind == "incomplete_motion":
            for sample in activity["samples"][3:]:
                sample["ego"]["xy_m"] = [2, 0]
                sample["ego"]["speed_mps"] = 0.0
        if kind == "missing_evidence":
            activity["observation_status"] = "missing"
            activity["source_gap"] = "original continuous ego body motion unavailable for physical assessment"
        write(activity_path, activity)
        inventory = json.loads(inventory_path.read_text())
        inventory["sources"]["activity"]["sha256"] = sha(activity_path)
        write(inventory_path, inventory)
        command = [sys.executable, str(HERE / "analysis.py"), "--attempt", str(attempt),
                   "--output", str(attempt / "analysis-report.json")]
        env = dict(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
        env["PYTHONPATH"] = str(REPO / "runtime/scenario_pipeline") + os.pathsep + str(REPO / "runtime/python")
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        log = HERE / ("cpu-physical-" + name + "-" + kind + ".log")
        log.write_text((result.stdout + result.stderr).rstrip() + "\n" if result.stdout or result.stderr
                       else "analysis exited 0; saved source measured\n")
        if result.returncode:
            raise RuntimeError("physical analysis failed: " + str(log))
        saved = json.loads((attempt / "result.json").read_text())
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if saved["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical outcome differs: " + name + " " + kind)
        result_path = HERE / ("cpu-physical-" + name + "-" + kind + ".json")
        write(result_path, saved)
        fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                         "log": log.name, "log_sha256": sha(log),
                         "result": result_path.name, "result_sha256": sha(result_path)})
    lifecycle_log = HERE / ("cpu-lifecycle-" + name + ".log")
    command = [sys.executable, str(HERE / "prove_lifecycle.py"), "--case", entry["case_id"]]
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    lifecycle_log.write_text((result.stdout + result.stderr).rstrip() + "\n")
    if result.returncode:
        raise RuntimeError("lifecycle proof failed: " + str(lifecycle_log))
    receipt = {"construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
               "lifecycle": {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                                        "native_exit", "owner_released", "saved_processing_started"],
                             "command": " ".join(command), "exit_code": 0,
                             "log": lifecycle_log.name, "log_sha256": sha(lifecycle_log)}}
    receipt_path = HERE / ("cpu-physical-" + name + "-receipt.json")
    write(receipt_path, receipt)
    entry["physical_preparation"] = {"receipt": receipt_path.name, "sha256": sha(receipt_path)}
    write(MANIFEST, manifest)
    print(name, "three physical outcomes and lifecycle passed", flush=True)
