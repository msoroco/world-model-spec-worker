"""Materialized Native runner for one reviewed C227824 pedestrian case.

``--check`` validates source bindings without importing CARLA or touching a
world. Acquisition requires an already materialized scene and map in the
private attempt directory.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from entry_measurement import _polygon
from native_attempt import _validate as validate_attempt
from native_cameras import placements
from native_signal import _review as review_devices
from native_world import _materialized, _sha, run_native
from walker_control import _xy


def check(attempt):
    root = Path(attempt).resolve()
    scene_path = root / "scene.json"
    if not scene_path.is_file():
        raise ValueError("materialized Native scene missing")
    scene = json.loads(scene_path.read_text())
    if not isinstance(scene, dict):
        raise ValueError("materialized Native scene must be an object")
    if (scene.get("law_id"), scene.get("cell_id"), scene.get("actor")) != (
            "NRS-484B-307-8b", "C227824", "pedestrian"):
        raise ValueError("materialized Native scene exact law, cell or actor differs")
    root = _materialized(scene, root)
    for name, key in (("config.json", "selected_case_id"),
                      ("construction.json", "case_id"),
                      ("measurement-contract.json", "case_id")):
        path = root / name
        if not path.is_file() or json.loads(path.read_text()).get(key) != scene.get("case_id"):
            raise ValueError("materialized case identity differs: " + name)
    construction = json.loads((root / "construction.json").read_text())
    files = construction.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("materialized construction source inventory missing")
    for item in files:
        name = item.get("path") if isinstance(item, dict) else None
        if (not isinstance(name, str) or not name or Path(name).is_absolute()
                or ".." in Path(name).parts):
            raise ValueError("materialized construction path invalid")
        path = root / name
        if not path.is_file() or path.is_symlink() or path.read_text() != item.get("content"):
            raise ValueError("materialized construction source differs: " + name)
    validate_attempt(scene, scene.get("planned_frames"))
    review_devices(scene)
    placements(scene)
    for review_name in ("device_inventory_review", "camera_placement_review"):
        review = scene[review_name]
        source_name = review.get("source_path")
        if not isinstance(source_name, str) or not source_name or Path(source_name).is_absolute():
            raise ValueError("review source path missing: " + review_name)
        source = root / source_name
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError("review source missing or escapes attempt: " + review_name)
        if _sha(source) != review["source_sha256"]:
            raise ValueError("review source hash differs: " + review_name)
    _polygon(scene.get("highway_polygon_xy_m"))
    _xy(scene.get("target_xy_m"))
    speed = scene.get("speed_mps")
    if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 3:
        raise ValueError("reviewed walker speed missing or invalid")
    point = scene.get("walker_spawn_xyz_m")
    if not isinstance(point, list) or len(point) != 3 or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in point):
        raise ValueError("reviewed walker spawn missing or invalid")
    identity = scene.get("walker_blueprint_id")
    if not isinstance(identity, str) or not identity.startswith("walker.pedestrian."):
        raise ValueError("reviewed walker blueprint missing")
    return scene


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=Path.cwd(), type=Path,
                        help="existing private materialized Native attempt (default: cwd)")
    parser.add_argument("--check", action="store_true", help="CPU source precheck only")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    scene = check(args.output_dir)
    result = ({"case_id": scene["case_id"], "cpu_precheck": "passed",
               "physical_acceptance_claimed": False} if args.check else
              run_native(scene, args.output_dir, host=args.host, port=args.port))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
