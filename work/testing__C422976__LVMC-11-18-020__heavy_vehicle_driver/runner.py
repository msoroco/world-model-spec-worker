"""Lazy exact School-Xing CARLA entrypoint; source packet required before driving."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import school_crossing as school


HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    plan = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact School-Xing plan changed")
    if (config.get("assignment_id") != school.ASSIGNMENT or
            config.get("cell_id") != "C422976" or
            config.get("catalog_control") != "school_crosswalk" or
            config.get("law_id") != school.LAW or
            config.get("actor") != "heavy_vehicle_driver"):
        raise ValueError("exact School-Xing bundle scope mismatch")
    selected = config.get("selected_case_id")
    if selected not in {school.ASSIGNMENT + "__" + c.name for c in school.CASES}:
        raise ValueError("selected case outside frozen school-crossing branch")
    return selected, config


def load_operator(path, expected_sha):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("reviewed operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_school_crossing_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed operator factory missing")
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    selected, config = check()
    if args.check:
        print(selected)
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    names = ("SCENARIO_SCHOOL_SITE_PACKET", "SCENARIO_SCHOOL_SITE_SHA256",
             "SCENARIO_SCHOOL_OPERATOR_MODULE", "SCENARIO_SCHOOL_OPERATOR_SHA256")
    values = [os.environ.get(name) for name in names]
    if not all(values):
        raise ValueError("source-hashed reviewed School-Xing site and operator required")
    site_path, site_sha, operator_path, operator_sha = values
    site_path = Path(site_path).resolve()
    if hashlib.sha256(site_path.read_bytes()).hexdigest() != site_sha:
        raise ValueError("reviewed School-Xing site source hash mismatch")
    module = load_operator(Path(operator_path).resolve(), operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, json.loads(site_path.read_text()), selected)
    from native_capture import capture
    from native_output_bridge import publish
    capture(world, case_id=selected, site_path=site_path, site_sha256=site_sha,
            output=args.output_dir, operator=operator,
            approach_start_m=config.get("approach_start_m", 55.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)


if __name__ == "__main__":
    main()
