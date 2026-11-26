"""Lazy, source-gated Native speed acquisition entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C150979__LVMC-11-16-060__motor_vehicle_driver"
CASES = ("same25_below", "same25_at", "same25_above", "different35")


def check():
    config = json.loads((HERE / "config.json").read_text())
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact speed case plan source changed")
    selected = config["selected_case_id"]
    if selected not in {ASSIGNMENT + "__" + key for key in CASES}:
        raise ValueError("selected speed case absent from frozen scope")
    if (config["assignment_id"] != ASSIGNMENT or config["cell_id"] != "C150979" or
            config["law_id"] != "LVMC-11-16-060"):
        raise ValueError("exact speed bundle scope mismatch")
    return selected


def _operator(path, expected_sha256):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed Native operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_speed_operator", path)
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
    selected = check()
    if args.check:
        print(selected)
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    site_path = os.environ.get("SCENARIO_SPEED_SITE_PACKET")
    site_sha = os.environ.get("SCENARIO_SPEED_SITE_SHA256")
    operator_path = os.environ.get("SCENARIO_SPEED_OPERATOR_MODULE")
    operator_sha = os.environ.get("SCENARIO_SPEED_OPERATOR_SHA256")
    if not all((site_path, site_sha, operator_path, operator_sha)):
        raise ValueError("source-hashed reviewed speed site and operator required")
    site_path = Path(site_path).resolve()
    raw = site_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != site_sha:
        raise ValueError("reviewed speed site source hash mismatch")
    module = _operator(Path(operator_path).resolve(), operator_sha)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, json.loads(raw), selected)
    from native_capture import capture
    from native_output_bridge import publish
    config = json.loads((HERE / "config.json").read_text())
    measured = capture(world, case_id=selected, site_path=site_path,
                       site_sha256=site_sha, output=args.output_dir,
                       operator=operator,
                       throttle_scale=config.get("throttle_scale", 1.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)
    print(json.dumps(measured, sort_keys=True))


if __name__ == "__main__":
    main()
