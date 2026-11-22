"""Build and offline-check one route-clearance fallback for each physical risk."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def revise(scene, suffix):
    route = scene["route_xy_m"]
    if suffix == "closed_divider":
        route[-1][1] = -3.25  # Increase planned front clearance by 0.25 m.
        knob = "final stop 0.25 m farther from closed divider"
    elif suffix == "right_roadway_no_turn":
        for point in route:
            point[1] = -6.0  # Move straight path away from median.
        knob = "straight path shifted 0.25 m away from median"
    elif suffix == "wrong_roadway":
        for point in route[-3:]:
            point[1] = 2.4  # Distinct non-right lane center candidate.
        knob = "non-right destination path shifted 0.15 m toward lane interior"
    elif suffix == "opening_multiple":
        route[4][0] = 1.3
        knob = "reverse staging waypoint shifted 0.2 m toward opening center"
    else:
        route[3][0] = 0.5 if suffix == "opening_single" else -0.25
        knob = "opening transition waypoint shifted toward opening center"
    return scene, knob


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        case_folder = HERE / "cases" / suffix
        original = json.loads((HERE / entry["construction"]).read_text())
        alternate = json.loads(json.dumps(original))
        scene_file = next(item for item in alternate["files"] if item["path"] == "scene.json")
        scene, knob = revise(json.loads(scene_file["content"]), suffix)
        scene_file["content"] = json.dumps(scene, indent=2, sort_keys=True) + "\n"
        alternate_path = case_folder / "fallback1-construction.json"
        write(alternate_path, alternate)
        fallback = {"id": "fallback1", "construction": str(alternate_path.relative_to(HERE)),
                    "construction_sha256": sha(alternate_path),
                    "trigger": {"source": "ego-body-history.jsonl", "metric": "measured full-body clearance or maneuver completion",
                                "failure_condition": "original motion does not meet primary physical target or body clearance"},
                    "changed_knobs": [knob]}
        entry["candidates"] = [fallback]
    write(manifest_path, manifest)
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        candidate = entry["candidates"][0]
        output = REPO / ".runtime-work" / "c126120-fallback-offline" / suffix
        index = 1
        while output.exists():
            output = REPO / ".runtime-work" / "c126120-fallback-offline" / f"{suffix}-{index}"
            index += 1
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "offline",
                   "--manifest", str(manifest_path), "--case", entry["case_id"],
                   "--candidate", "fallback1", "--output", str(output)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run(command, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / "cases" / suffix / "fallback1-offline-check.log"
        log.write_text(process.stdout)
        if process.returncode:
            raise RuntimeError(f"{suffix} fallback offline failed: {process.stdout[-1200:]}")
        candidate["offline"] = {"command": " ".join(command), "exit_code": 0,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
        print(suffix, "fallback1 offline passed")
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
