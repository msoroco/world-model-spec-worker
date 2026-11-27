"""Lazy Native roundabout traversal with original actor/map readback.

The local operator supplies CARLA ownership, world restoration, four synchronized
cameras and Native sealing. This module never imports CARLA during CPU checks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

from direction import ASSIGNMENT, CASE_DIRECTIONS, load_source, measure_history

HERE = Path(__file__).resolve().parent


def _steer(state, waypoint):
    dx = waypoint["x"] - state["x"]
    dy = waypoint["y"] - state["y"]
    heading = math.atan2(state["heading_y"], state["heading_x"])
    angle = (math.atan2(dy, dx)-heading+math.pi)%(2*math.pi)-math.pi
    return max(-1.0,min(1.0,1.8*angle))


def _route_distance(state,route):
    distances=[]
    for a,b in zip(route,route[1:]):
        vx,vy=b["x"]-a["x"],b["y"]-a["y"]
        length=vx*vx+vy*vy
        fraction=max(0.0,min(1.0,((state["x"]-a["x"])*vx+(state["y"]-a["y"])*vy)/length))
        distances.append(math.hypot(state["x"]-a["x"]-fraction*vx,
                                    state["y"]-a["y"]-fraction*vy))
    return min(distances)


def execute(adapter, packet, case_id, *, throttle=.32, ticks=900):
    """Route on the original map, then classify the observed signed ring arc."""
    if case_id not in CASE_DIRECTIONS or ticks != 900:
        raise ValueError("exact 900-tick direction case required")
    if type(throttle) not in (int,float) or not .15 <= throttle <= .40:
        raise ValueError("bounded controller throttle required")
    readback = adapter.readback_map()
    if (readback.get("map_name") != packet["map_name"] or
            readback.get("opendrive_sha256") != packet["opendrive_sha256"]):
        raise ValueError("live map differs from reviewed source")
    name = "counterclockwise" if CASE_DIRECTIONS[case_id] == 1 else "clockwise"
    route = packet["connected_routes"][name]
    actor = adapter.spawn_motor_vehicle(route[0])
    rows=[]
    previous_frame=None
    try:
        target=1
        for index in range(ticks):
            state=adapter.actor_state(actor)
            if not all(type(state.get(k)) in (int,float) and math.isfinite(state[k])
                       for k in ("x","y","heading_x","heading_y")):
                raise ValueError("original actor pose absent")
            if _route_distance(state,route)>4.0:
                raise ValueError("original route tracking exceeds 4 m corridor")
            while target < len(route)-1 and math.hypot(state["x"]-route[target]["x"],
                    state["y"]-route[target]["y"]) < 1.5:
                target += 1
            control={"throttle":float(throttle) if target < len(route)-1 else 0.0,
                     "brake":0.0 if target < len(route)-1 else .5,
                     "steer":_steer(state,route[target])}
            sample=adapter.step(actor,control)
            if (type(sample.get("frame")) is not int or
                    (previous_frame is not None and sample["frame"] != previous_frame+1) or
                    sample.get("actor_id") != actor.id):
                raise ValueError("Native original frame/actor discontinuity")
            rows.append(sample)
            previous_frame=sample["frame"]
        history=adapter.seal(case_id,packet,rows)
        return measure_history(packet,history,case_id)
    finally:
        adapter.destroy(actor)


def check(directory=HERE):
    root=Path(directory)
    config=json.loads((root/"config.json").read_text())
    case_id=config["selected_case_id"]
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("cell_id") != "C238432" or
            config.get("law_id") != "LVMC-11-43-010-A" or
            case_id not in CASE_DIRECTIONS or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45):
        raise ValueError("exact roundabout direction configuration differs")
    return case_id


def _source_module(path, expected_hash):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("reviewed Native operator hash mismatch")
    spec=importlib.util.spec_from_file_location("reviewed_roundabout_direction_operator",path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module,"make_operator",None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=2000)
    args=parser.parse_args(argv)
    case_id=check()
    if args.check:
        print(json.dumps({"case_id":case_id,"static_construction_valid":True,
                          "native_started":False}))
        return 0
    if not args.output_dir:
        raise ValueError("Native output directory required")
    keys=("SCENARIO_ROUNDABOUT_DIRECTION_SURVEY",
          "SCENARIO_ROUNDABOUT_DIRECTION_SURVEY_SHA256",
          "SCENARIO_ROUNDABOUT_DIRECTION_OPERATOR",
          "SCENARIO_ROUNDABOUT_DIRECTION_OPERATOR_SHA256")
    if not all(os.environ.get(key) for key in keys):
        raise ValueError("source-hashed reviewed roundabout survey and operator required")
    packet=load_source(os.environ[keys[0]],os.environ[keys[1]],case_id)
    operator_module=_source_module(os.environ[keys[2]],os.environ[keys[3]])
    import carla
    client=carla.Client(args.host,args.port)
    client.set_timeout(30)
    world=client.get_world()
    adapter=operator_module.make_operator(world,packet,case_id,args.output_dir)
    try:
        measured=execute(adapter,packet,case_id,
                         throttle=json.loads((HERE/"config.json").read_text()).get("route_throttle",.32))
        print(json.dumps(measured,sort_keys=True))
    finally:
        adapter.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
