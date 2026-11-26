"""Run pinned exact offline checks for six emergency-unit cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from emergency_construction import CASES
from build_constructions import FALLBACKS
from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c405341/offline"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def proof():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    entries = []
    for case in CASES:
        name = case.suffix
        construction = HERE / ("construction-" + name + ".json")
        entry = {"case_id": AID + "__" + name, "kind": "delivery",
            "construction": construction.name, "construction_sha256": sha(construction),
            "fixture_recipe": "work/" + AID + "/diagnostics/" + name + "-recipe.json",
            "measurement_contract": "diagnostics/" + name + "-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "source_gate": "reviewed Native authority, qualifying emergency lighting, unit and ego routes and four camera poses required",
            "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "acquisition": {channel: {"entrypoint": "runner.py", "method": "capture_original",
                "evidence": "Post-tick unit pose, light, cue, ego control and four joined camera frame IDs."}
                for channel in ("sealed_native_original_frames", "unit_motion",
                                "qualifying_flashing_lights", "driver_view_movement_cue",
                                "ego_approach", "ego_response", "officer_direction", "video_four_views")},
            "candidate_risk": {"status": "physical" if name in FALLBACKS else "none",
                "reason": FALLBACKS[name][2] if name in FALLBACKS else
                          "No candidate-specific physical risk after source-gated Native review"},
            "candidates": []}
        if name in FALLBACKS:
            fallback = HERE / ("construction-" + name + "-fallback1.json")
            key, value, trigger = FALLBACKS[name]
            entry["candidates"] = [{"id": "fallback1", "construction": fallback.name,
                "construction_sha256": sha(fallback),
                "trigger": {"source": "sealed original Native motion, cue and driver-view pixel history",
                            "metric": key, "failure_condition": trigger},
                "changed_knobs": [key + " = " + str(value)]}]
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "source_gated_draft",
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries, "comparisons": []}
    write(manifest_path, manifest)
    environment = dict(os.environ,
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c405341/output-root"),
        TMPDIR=str(ROOT / ".runtime-work/c405341/tmp"), PYTHONDONTWRITEBYTECODE="1")
    for entry in entries:
        name = entry["case_id"].removeprefix(AID + "__")
        for candidate in ([None, "fallback1"] if entry["candidates"] else [None]):
            label = name + ("-fallback1" if candidate else "")
            destination = SCRATCH / label
            if destination.exists():
                shutil.rmtree(destination)
            command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                       "--manifest", str(manifest_path), "--case", entry["case_id"],
                       "--output", str(destination), "--python", sys.executable]
            if candidate:
                command += ["--candidate", candidate]
            process = subprocess.run(command, cwd=ROOT, env=environment,
                                     capture_output=True, text=True, timeout=300)
            log_path = HERE / ("cpu-offline-" + label + ".log")
            details = (destination / "offline.log").read_text(encoding="utf-8") if (destination / "offline.log").exists() else ""
            log_path.write_text((details + process.stdout + process.stderr).rstrip() + "\n", encoding="utf-8")
            if process.returncode:
                raise RuntimeError("exact offline failed: " + label + " (see " + str(log_path) + ")")
            proof = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                "/execution-manifest.json --case " + entry["case_id"] +
                (" --candidate fallback1" if candidate else "") +
                " --output $OUTPUT --python $CPU_PYTHON", "exit_code": 0,
                "construction_sha256": entry["candidates"][0]["construction_sha256"] if candidate else entry["construction_sha256"],
                "log": log_path.name, "log_sha256": sha(log_path)}
            if candidate:
                entry["candidates"][0]["offline"] = proof
            else:
                entry["offline"] = proof
            print(label + ": offline passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    proof()
