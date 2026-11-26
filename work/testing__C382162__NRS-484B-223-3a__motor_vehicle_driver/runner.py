"""Exact center-lane Native dispatch; imports CARLA only after source gates."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

from native_capture import ASSIGNMENT, KINDS

HERE = Path(__file__).resolve().parent


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(path, expected):
    path = Path(path).resolve()
    if not path.is_file() or _sha(path) != expected:
        raise ValueError("reviewed source bytes differ")
    return path


def stage(site_path, site_sha, intent_path, intent_sha, output):
    """Copy exact reviewed bytes into a fresh attempt before Native motion."""
    site_path = _source(site_path, site_sha)
    intent_path = _source(intent_path, intent_sha)
    site = json.loads(site_path.read_text())
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Native attempt directory already populated")
    output.mkdir(parents=True, exist_ok=True)
    for binding in (site.get("native_map_source"), site.get("highway_review_source")):
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
            raise ValueError("reviewed map/highway source binding missing")
        relative = Path(binding["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("reviewed source path escapes site directory")
        source = _source(site_path.parent / relative, binding["sha256"])
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    purpose = json.loads(intent_path.read_text())
    target = output / "pre-entry-intent.json"
    shutil.copyfile(intent_path, target)
    binding = {"path": target.name, "sha256": _sha(target)}
    if purpose.get("source_ref") != target.name:
        raise ValueError("pre-entry intent source reference differs from staged packet")
    (output / "reviewed-site.json").write_bytes(site_path.read_bytes())
    return site, binding


def load_operator(path, expected):
    path = _source(path, expected)
    spec = importlib.util.spec_from_file_location("reviewed_center_lane_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def check():
    config = json.loads((HERE / "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-223-3a" or
            config.get("cell_id") != "C382162" or
            config.get("selected_case_id") not in {ASSIGNMENT + "__" + kind for kind in KINDS}):
        raise ValueError("exact center-lane case bundle scope mismatch")
    if config.get("plan_sha256") != _sha(HERE / "case-plan.json"):
        raise ValueError("exact center-lane case plan changed")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = check()
    if args.check:
        print(config["selected_case_id"])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and fresh output directory required")
    keys = ("SCENARIO_CENTER_LANE_SITE_PACKET", "SCENARIO_CENTER_LANE_SITE_SHA256",
            "SCENARIO_CENTER_LANE_PURPOSE_PACKET", "SCENARIO_CENTER_LANE_PURPOSE_SHA256",
            "SCENARIO_CENTER_LANE_OPERATOR_MODULE", "SCENARIO_CENTER_LANE_OPERATOR_SHA256")
    if any(not os.environ.get(name) for name in keys):
        raise ValueError("source-hashed reviewed center-lane site, intent and operator required")
    site, purpose = stage(os.environ[keys[0]], os.environ[keys[1]],
                          os.environ[keys[2]], os.environ[keys[3]], args.output_dir)
    module = load_operator(os.environ[keys[4]], os.environ[keys[5]])
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, site, config["selected_case_id"])
    operator.target_speed_mps = float(config.get("controller_target_speed_mps", 5))
    from native_live import capture

    capture(world, attempt_root=args.output_dir, case_id=config["selected_case_id"],
            site=site, purpose_binding=purpose, operator=operator)
    from native_output_bridge import publish

    publish(args.output_dir, map_bytes=world.get_map().to_opendrive().encode(), restored=True)


if __name__ == "__main__":
    main()
