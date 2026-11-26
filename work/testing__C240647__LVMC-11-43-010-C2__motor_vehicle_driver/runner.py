"""Exact source-gated Native right-turn roundabout entrypoint."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ROUTE = _module("c240647_route", HERE / "roundabout.py")

def check():
    config = json.loads((HERE / "config.json").read_text())
    if hashlib.sha256((HERE / "case-plan.json").read_bytes()).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact case plan changed")
    cases = json.loads((HERE / "case-plan.json").read_text())["cases"]
    selected = config.get("selected_case_id")
    case = next((row for row in cases if row["case_id"] == selected), None)
    if case is None or (config.get("assignment_id"),config.get("cell_id"),config.get("law_id"),config.get("actor")) != (
            "testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver","C240647","LVMC-11-43-010-C2","motor_vehicle_driver"):
        raise ValueError("selected exact right-lane case mismatch")
    return case

def execute(adapter, case, throttle=.35):
    if type(throttle) not in (int,float) or not .15 <= throttle <= .4:
        raise ValueError("bounded engineering throttle invalid")
    topology = ROUTE.verify_topology(adapter.readback_map(), case)
    points = topology["route"]
    actor = adapter.spawn_motor_vehicle(points[0])
    frames = []
    try:
        target = 1
        for index in range(900):
            state = adapter.actor_state(actor)
            x, y = float(state["x"]), float(state["y"])
            heading = math.atan2(float(state["heading_y"]), float(state["heading_x"]))
            while target < len(points)-1 and math.hypot(points[target]["x"]-x,points[target]["y"]-y) < 1.5:
                target += 1
            dx, dy = points[target]["x"]-x, points[target]["y"]-y
            target_angle = math.atan2(dy,dx)
            error = (target_angle-heading+math.pi)%(2*math.pi)-math.pi
            steer = max(-1.,min(1.,1.8*error))
            finished = target == len(points)-1 and math.hypot(dx,dy) < 1.5
            control = {"throttle":0 if finished else throttle,"brake":.4 if finished else 0.,"steer":steer}
            frame = adapter.step(actor,control)
            if frame.get("frame") != index:
                raise ValueError("Native source tick discontinuity")
            frames.append(frame)
        history = adapter.seal(case["case_id"],topology,frames)
        return ROUTE.verify_original_history(history,topology,case["case_id"])
    finally:
        adapter.destroy(actor)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port",type=int)
    parser.add_argument("--output-dir",type=Path)
    args = parser.parse_args()
    case = check()
    if args.check:
        print(case["case_id"])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    survey_path = os.environ.get("SCENARIO_ROUNDABOUT_SURVEY_PACKET")
    survey_sha = os.environ.get("SCENARIO_ROUNDABOUT_SURVEY_SHA256")
    operator_path = os.environ.get("SCENARIO_ROUNDABOUT_OPERATOR_MODULE")
    operator_sha = os.environ.get("SCENARIO_ROUNDABOUT_OPERATOR_SHA256")
    if not all((survey_path,survey_sha,operator_path,operator_sha)):
        raise ValueError("source-hashed reviewed roundabout and operator required")
    survey_raw = Path(survey_path).read_bytes()
    if hashlib.sha256(survey_raw).hexdigest() != survey_sha:
        raise ValueError("reviewed roundabout source hash mismatch")
    source_raw = Path(operator_path).read_bytes()
    if hashlib.sha256(source_raw).hexdigest() != operator_sha:
        raise ValueError("reviewed Native operator source hash mismatch")
    operator_module = _module("reviewed_roundabout_operator",Path(operator_path))
    if not callable(getattr(operator_module,"make_operator",None)):
        raise ValueError("reviewed Native operator factory missing")
    import carla
    client = carla.Client(args.host,args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = operator_module.make_operator(world,json.loads(survey_raw),case["case_id"])
    capture = _module("c240647_capture",HERE / "native_capture.py")
    bridge = _module("c240647_bridge",HERE / "native_output_bridge.py")
    measured = capture.capture(world,case=case,survey_path=survey_path,survey_sha256=survey_sha,
                               output=args.output_dir,operator=operator,
                               throttle=json.loads((HERE / "config.json").read_text()).get("route_throttle",.35))
    bridge.publish(args.output_dir,map_bytes=operator.map_bytes(world),restored=True)
    print(json.dumps(measured,sort_keys=True))

if __name__ == "__main__":
    main()
