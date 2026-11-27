"""Run the pinned offline construction proof for all selected 1b cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c183357-1b/offline"
CHANNELS = ("sealed_native_original_frames", "unit_motion", "qualifying_flashing_lights",
            "front_visible_red_lamp", "siren_equipment", "target_authorization",
            "subject_driver", "relative_approach", "ego_response", "officer_direction",
            "edge_distance", "body_yaw_to_edge", "intersection_overlap",
            "shoulder_region", "ego_body_geometry", "shoulder_sign", "video_four_views")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def proof():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    entries = []
    for case in plan["cases"]:
        suffix = case["variant"]
        construction = HERE / "cases" / suffix / "construction.json"
        entry = {"case_id": case["case_id"], "kind": "delivery",
            "construction": str(construction.relative_to(HERE)),
            "construction_sha256": sha(construction),
            "fixture_recipe": "work/" + AID + "/diagnostics/" + suffix + "-recipe.json",
            "measurement_contract": "diagnostics/" + suffix + "-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "source_gate": "reviewed Native highway, curb, paved shoulder, intersection, lawfully placed sign, qualifying unit, officer context and four camera poses required",
            "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "acquisition": {channel: {"entrypoint": "runner.py", "method": "capture_original",
                "evidence": "Per-tick body/curb/shoulder/intersection geometry, unit pose, sign and four joined camera frame IDs."}
                for channel in CHANNELS},
            "candidate_risk": {"status": "physical", "reason":
                "Native route, curb/shoulder positioning or front-visible lamp may fail on a reviewed site"},
            "candidates": []}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "source_gated_draft",
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries, "comparisons": []}
    manifest_path = HERE / "execution-manifest.json"
    write(manifest_path, manifest)
    environment = dict(os.environ,
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c183357-1b/output-root"),
        TMPDIR=str(ROOT / ".runtime-work/c183357-1b/tmp"), PYTHONDONTWRITEBYTECODE="1")
    (ROOT / ".runtime-work/c183357-1b/tmp").mkdir(parents=True, exist_ok=True)
    for entry in entries:
        suffix = entry["case_id"].removeprefix(AID + "__")
        destination = SCRATCH / suffix
        if destination.exists():
            shutil.rmtree(destination)
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(manifest_path), "--case", entry["case_id"],
                   "--output", str(destination), "--python", sys.executable]
        process = subprocess.run(command, cwd=ROOT, env=environment,
                                 capture_output=True, text=True, timeout=300)
        log_path = HERE / ("cpu-offline-" + suffix + ".log")
        details = (destination / "offline.log").read_text(encoding="utf-8") if (destination / "offline.log").exists() else ""
        log_path.write_text((details + process.stdout + process.stderr).rstrip() + "\n", encoding="utf-8")
        if process.returncode:
            raise RuntimeError("exact offline failed: " + suffix + " (see " + str(log_path) + ")")
        entry["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
            "/execution-manifest.json --case " + entry["case_id"] +
            " --output $OUTPUT --python $CPU_PYTHON", "exit_code": 0,
            "construction_sha256": entry["construction_sha256"],
            "log": log_path.name, "log_sha256": sha(log_path)}
        print(suffix + ": offline passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    proof()
