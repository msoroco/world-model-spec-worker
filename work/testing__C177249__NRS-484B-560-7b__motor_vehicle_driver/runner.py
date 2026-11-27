"""Lazy, source-gated exact railway instruction Native dispatch."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import railway_7b as law

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C177249__NRS-484B-560-7b__motor_vehicle_driver"


def check():
    config = json.loads((HERE / "config.json").read_text())
    if hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact railway instruction case plan changed")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (ASSIGNMENT, law.LAW, law.CELL, law.ACTOR):
        raise ValueError("exact railway instruction identity differs")
    selected = config.get("selected_case_id")
    if selected not in {ASSIGNMENT + "__" + name for name in law.CASES}:
        raise ValueError("unselected railway instruction construction")
    return selected, config


def _operator(path, checksum):
    if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
        raise ValueError("reviewed railway operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_railway_instruction_operator", path)
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
    names = ("SCENARIO_RAIL_7B_SITE_PACKET", "SCENARIO_RAIL_7B_SITE_SHA256",
             "SCENARIO_RAIL_7B_OPERATOR_MODULE", "SCENARIO_RAIL_7B_OPERATOR_SHA256")
    values = [os.environ.get(name) for name in names]
    if not all(values):
        raise ValueError("source-hashed reviewed railway site and operator required")
    site_path, site_sha, operator_path, operator_sha = values
    site = law.load_packet(site_path, site_sha)
    name = selected.removeprefix(ASSIGNMENT + "__")
    law.validate_site(site, name)
    operator_module = _operator(Path(operator_path).resolve(), operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = operator_module.make_operator(world, site, selected)
    from native_capture import capture
    from native_output_bridge import publish
    capture(world, case_id=selected, site_path=site_path, site_sha256=site_sha,
            output=args.output_dir, operator=operator,
            approach_start_m=config.get("approach_start_m", 55.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)


if __name__ == "__main__":
    main()
