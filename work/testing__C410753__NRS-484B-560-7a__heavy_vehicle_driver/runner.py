"""Lazy Native dispatch for exact NRS 484B.560(7)(a) heavy-vehicle cases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import railway_7a as law

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C410753__NRS-484B-560-7a__heavy_vehicle_driver"


def check():
    config = json.loads((HERE / "config.json").read_text())
    if hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact railway case plan changed")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (ASSIGNMENT, law.LAW, law.CELL, law.ACTOR):
        raise ValueError("exact railway construction identity differs")
    selected = config.get("selected_case_id")
    if selected not in {ASSIGNMENT + "__" + name for name in law.CASE_AXES}:
        raise ValueError("unselected railway construction")
    return selected, config


def load_operator(path, expected_sha):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("reviewed railway operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_railway_7a_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed railway operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed railway operator factory missing")
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
    names = ("SCENARIO_RAIL_7A_SITE_PACKET", "SCENARIO_RAIL_7A_SITE_SHA256",
             "SCENARIO_RAIL_7A_OPERATOR_MODULE", "SCENARIO_RAIL_7A_OPERATOR_SHA256")
    values = [os.environ.get(n) for n in names]
    if not all(values):
        raise ValueError("source-hashed reviewed railway site and operator required")
    site_path, site_sha, operator_path, operator_sha = values
    site = law.load_source(site_path, site_sha)
    case_name = selected.removeprefix(ASSIGNMENT + "__")
    law.validate_site(site, case_name)
    module = load_operator(Path(operator_path).resolve(), operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, site, selected)
    from native_capture import capture
    from native_output_bridge import publish
    capture(world, case_id=selected, site_path=site_path, site_sha256=site_sha,
            output=args.output_dir, operator=operator,
            approach_start_m=config.get("approach_start_m", 55.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)


if __name__ == "__main__":
    main()
