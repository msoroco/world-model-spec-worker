"""Materialize six exact Native attempts from independently reviewed source bases.

Inputs live in a private .runtime-work directory. This tool verifies every
declared source hash and the runner's CPU precheck before exposing a case set.
It does not create a map, device authority, or physical evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from native_case_bundles import expand
from build_construction import build
from runner import check


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
PRIVATE = (WORKSPACE / ".runtime-work").resolve()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _private(path):
    path = Path(path).resolve()
    if not path.is_relative_to(PRIVATE):
        raise ValueError("source and output must be under .runtime-work")
    return path


def materialize(source, output):
    source, output = _private(source), _private(output)
    if not source.is_dir() or output.exists() or output == source:
        raise ValueError("existing private source and fresh output required")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("source and output must not nest")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base_paths = [source / name for name in ("no-device-base.json", "one-device-base.json")]
    if any(not path.is_file() or path.is_symlink() for path in base_paths):
        raise ValueError("two original source bases required")
    bases = [json.loads(path.read_text()) for path in base_paths]
    scenes = expand(plan, no_device_base=bases[0], one_device_base=bases[1])
    map_path = source / "candidate-corridor.xodr"
    if not map_path.is_file() or map_path.is_symlink():
        raise ValueError("original map source missing")
    assets = {"candidate-corridor.xodr": map_path}
    for scene in scenes.values():
        if scene.get("planned_frames") != 240 or scene.get("fixed_delta_seconds") != .05:
            raise ValueError("12-second 20 Hz reviewed scene required")
        if scene.get("map_source_sha256") != _sha(map_path):
            raise ValueError("original map source hash differs")
        for key in ("device_inventory_review", "camera_placement_review"):
            review = scene.get(key)
            name = review.get("source_path") if isinstance(review, dict) else None
            if (not isinstance(name, str) or not name or Path(name).is_absolute()
                    or ".." in Path(name).parts):
                raise ValueError("review source path missing")
            original = source / name
            path = original.resolve()
            if not path.is_relative_to(source) or not path.is_file() or original.is_symlink():
                raise ValueError("review source missing or escapes private source")
            if _sha(path) != review.get("source_sha256"):
                raise ValueError("review source hash differs")
            assets[name] = path
    output.mkdir(parents=True)
    try:
        for case_id, scene in scenes.items():
            target = output / case_id
            target.mkdir()
            for name, path in assets.items():
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
            config, measurement, construction = build(case_id)
            if config["selected_case_id"] != case_id or construction["case_id"] != case_id:
                raise ValueError("case-specific construction identity differs")
            for item in construction["files"]:
                name = item["path"]
                if Path(name).is_absolute() or ".." in Path(name).parts:
                    raise ValueError("construction file path escapes attempt")
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(item["content"])
            (target / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
            (target / "scene.json").write_text(json.dumps(scene, indent=2) + "\n")
            check(target)
    except BaseException:
        shutil.rmtree(output)
        raise
    return sorted(scenes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps({"materialized_cases": materialize(args.source, args.output),
                      "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
