"""Lazy Native roundabout construction using an injected CARLA adapter.

The adapter owns world snapshot/restore, synchronized four-view capture and
Native sealing. This runner never imports CARLA during CPU preparation.
"""

from __future__ import annotations

import importlib.util
import argparse
import hashlib
import json
import math
import os
from pathlib import Path


MODULE = Path(__file__).with_name("roundabout.py")
SPEC = importlib.util.spec_from_file_location("roundabout_route", MODULE)
ROUTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTE)


def _steer(position: dict, heading: tuple[float, float], target: dict) -> float:
    direction = ROUTE._unit(ROUTE._vector(position, target))
    angle = math.atan2(ROUTE._cross(heading, direction), ROUTE._dot(heading, direction))
    return max(-1.0, min(1.0, 1.8 * angle))


def execute(adapter, case_id: str, lane_role: str, throttle: float = 0.35) -> dict:
    """Spawn one motor vehicle, track the mapped route and seal 900 Native ticks.

    Adapter.readback_map must sample the active map and its OpenDRIVE hash.
    Adapter.step applies controls and returns the original tick's actor sample.
    Adapter.seal retains original packets, frame map and camera captures. The
    returned summary is a measurement, never a physical or legal acceptance.
    """
    source = adapter.readback_map()
    if type(throttle) not in (int, float) or not 0.15 <= throttle <= 0.40:
        raise ROUTE.SourceError("bounded route tracking throttle invalid")
    topology = ROUTE.verify_topology(source, lane_role)
    route = topology["route"]
    actor = adapter.spawn_motor_vehicle(route[0])
    frames = []
    try:
        target = 1
        for index in range(900):
            state = adapter.actor_state(actor)
            position = {"x": float(state["x"]), "y": float(state["y"])}
            while target < len(route)-1 and math.hypot(*ROUTE._vector(position, route[target])) < 1.5:
                target += 1
            heading = ROUTE._unit((float(state["heading_x"]), float(state["heading_y"])))
            control = {"throttle": throttle if target < len(route)-1 else 0.0,
                       "brake": 0.0 if target < len(route)-1 else 0.4,
                       "steer": _steer(position, heading, route[target])}
            frame = adapter.step(actor, control)
            if frame.get("frame") != index:
                raise ROUTE.SourceError("Native tick sequence discontinuity")
            frames.append(frame)
        history = adapter.seal(case_id, topology, frames)
        return ROUTE.verify_original_history(history, topology, case_id)
    finally:
        adapter.destroy(actor)


HERE = Path(__file__).resolve().parent


def check() -> str:
    config = json.loads((HERE / "config.json").read_text())
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact U-turn case plan source changed")
    plan = json.loads(plan_bytes)
    case_id = config["selected_case_id"]
    if case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected U-turn case absent from plan")
    if (config["assignment_id"] != "testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver"
            or config["cell_id"] != "C133321" or config["law_id"] != "LVMC-11-43-010-C1"):
        raise ValueError("exact U-turn bundle scope mismatch")
    return case_id


def _reviewed_operator(path, expected_sha256):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed Native operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_roundabout_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print(case_id)
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    survey = os.environ.get("SCENARIO_ROUNDABOUT_SURVEY_PACKET")
    survey_sha = os.environ.get("SCENARIO_ROUNDABOUT_SURVEY_SHA256")
    operator_path = os.environ.get("SCENARIO_ROUNDABOUT_OPERATOR_MODULE")
    operator_sha = os.environ.get("SCENARIO_ROUNDABOUT_OPERATOR_SHA256")
    if not all((survey, survey_sha, operator_path, operator_sha)):
        raise ValueError("source-hashed reviewed roundabout and operator required")
    survey_path = Path(survey).resolve()
    raw = survey_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != survey_sha:
        raise ValueError("reviewed roundabout source hash mismatch")
    operator_module = _reviewed_operator(Path(operator_path).resolve(), operator_sha)
    if not callable(getattr(operator_module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = operator_module.make_operator(world, json.loads(raw), case_id)
    from native_capture import capture
    from native_output_bridge import publish
    measured = capture(world, case_id=case_id, survey_path=survey_path,
                       survey_sha256=survey_sha, output=args.output_dir,
                       operator=operator,
                       throttle=json.loads((HERE / "config.json").read_text()).get("route_throttle", 0.35))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)
    print(json.dumps(measured, sort_keys=True))


if __name__ == "__main__":
    main()
