"""Lazy, source-gated Native near-side crosswalk entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C331230__NRS-484A-450-2__motor_vehicle_driver"


def check():
    config = json.loads((HERE / "config.json").read_text())
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact near-side crosswalk plan changed")
    selected = config["selected_case_id"]
    names = ("marked_crosswalk_halt", "marked_crosswalk_rolling",
             "unmarked_crosswalk_halt", "unmarked_crosswalk_rolling")
    if selected not in {ASSIGNMENT + "__" + name for name in names}:
        raise ValueError("selected case outside exact frozen scope")
    if config["assignment_id"] != ASSIGNMENT or config["cell_id"] != "C331230" or \
            config["law_id"] != "NRS-484A-450-2":
        raise ValueError("exact near-side crosswalk bundle scope mismatch")
    return selected, config


def load_operator(path, expected_sha256):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("reviewed Native operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_crosswalk_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
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
    site_path = os.environ.get("SCENARIO_CROSSWALK_SITE_PACKET")
    site_sha = os.environ.get("SCENARIO_CROSSWALK_SITE_SHA256")
    operator_path = os.environ.get("SCENARIO_CROSSWALK_OPERATOR_MODULE")
    operator_sha = os.environ.get("SCENARIO_CROSSWALK_OPERATOR_SHA256")
    if not all((site_path, site_sha, operator_path, operator_sha)):
        raise ValueError("source-hashed reviewed crosswalk site and operator required")
    site_path = Path(site_path).resolve()
    if hashlib.sha256(site_path.read_bytes()).hexdigest() != site_sha:
        raise ValueError("reviewed crosswalk site source hash mismatch")
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
            brake_distance_m=config.get("brake_distance_m", 12.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)


if __name__ == "__main__":
    main()
