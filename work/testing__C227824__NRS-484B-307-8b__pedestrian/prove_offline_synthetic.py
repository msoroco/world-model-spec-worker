"""Exercise all six exact bundles through runtime offline with synthetic reviews.

This is a software diagnostic. It supplies no official signal, legal highway
boundary, real CARLA actor, recording, or physical acceptance evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_construction import ROOT, build
from native_case_bundles import expand
from saved_entry import CAMERAS


REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c227824-offline-synthetic"


def _text(value):
    return json.dumps(value, indent=2) + "\n"


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    map_bytes = (ROOT / "candidate-corridor.xodr").read_bytes()
    reviews = {
        "no-device-review.json": _text({"diagnostic_fixture": True, "device_ids": []}),
        "one-device-review.json": _text({"diagnostic_fixture": True, "device_ids": [8]}),
        "camera-review.json": _text({"diagnostic_fixture": True, "four_views": list(CAMERAS)}),
    }
    base = {
        "map_source_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "fixed_delta_seconds": .05, "planned_frames": 240,
        "target_xy_m": [15, 6.5], "speed_mps": 1,
        "walker_spawn_xyz_m": [15, -6.5, 1],
        "walker_blueprint_id": "walker.pedestrian.0001",
        "highway_polygon_xy_m": [[0, -5.5], [30, -5.5], [30, 5.5], [0, 5.5]],
        "route_id": "synthetic-pedestrian-route", "facing_head_id": 5,
        "governing_pedestrian_device_ids": [],
        "camera_placements": {name: {"location_xyz_m": [10, -10, 4],
                                     "target_xyz_m": [15, 0, 1]}
                              for name in CAMERAS},
        "camera_placement_review": {
            "complete": True, "source_path": "camera-review.json",
            "source_sha256": hashlib.sha256(reviews["camera-review.json"].encode()).hexdigest()},
        "device_inventory_review": {
            "complete": True, "source_path": "no-device-review.json",
            "source_sha256": hashlib.sha256(reviews["no-device-review.json"].encode()).hexdigest()},
        "diagnostic_fixture": True,
    }
    one = json.loads(_text(base))
    one["governing_pedestrian_device_ids"] = [8]
    one["device_inventory_review"] = {
        "complete": True, "source_path": "one-device-review.json",
        "source_sha256": hashlib.sha256(reviews["one-device-review.json"].encode()).hexdigest()}
    plan = json.loads((ROOT / "case-plan.json").read_text())
    scenes = expand(plan, no_device_base=base, one_device_base=one)
    rows = []
    for case_id, scene in scenes.items():
        suffix = case_id[len(ROOT.name) + 2:]
        target = PRIVATE / suffix
        target.mkdir(exist_ok=True)
        _, _, construction = build(case_id)
        construction["files"].extend([
            {"path": "scene.json", "content": _text(scene)},
            {"path": "candidate-corridor.xodr", "content": map_bytes.decode()},
            *({"path": name, "content": content} for name, content in reviews.items()),
        ])
        source = target / "construction.json"
        source.write_text(_text(construction))
        manifest = target / "manifest.json"
        manifest.write_text(_text({"cases": [{"case_id": case_id,
                                               "construction": "construction.json",
                                               "construction_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}))
        output = target / "attempt"
        if output.exists():
            import shutil
            shutil.rmtree(output)
        command = [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest",
                   str(manifest), "--case", case_id, "--output", str(output)]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["TMPDIR"] = str(PRIVATE)
        run = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(case_id + ": " + run.stdout + run.stderr)
        rows.append({"case_id": case_id, "offline_exit_code": run.returncode,
                     "diagnostic_fixture": True})
    first = rows[0]["case_id"]
    first_suffix = first[len(ROOT.name) + 2:]
    first_target = PRIVATE / first_suffix
    corrupted = first_target / "manifest-corrupt.json"
    corrupted.write_text(_text({"cases": [{"case_id": first,
                                           "construction": "construction.json",
                                           "construction_sha256": "0" * 64}]}))
    negative = subprocess.run(
        [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest",
         str(corrupted), "--case", first, "--output",
         str(first_target / "attempt-corrupt")],
        cwd=REPO, env=env, capture_output=True, text=True)
    if negative.returncode == 0 or "Candidate construction changed" not in negative.stderr:
        raise RuntimeError("stale exact construction was not rejected")
    print(_text({"format": "c227824-synthetic-offline-summary", "cases": rows,
                 "stale_construction_rejected": True,
                 "physical_acceptance_claimed": False}).rstrip())


if __name__ == "__main__":
    main()
