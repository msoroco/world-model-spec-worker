"""Lazy Native roundabout construction using an injected CARLA adapter.

The adapter owns world snapshot/restore, synchronized four-view capture and
Native sealing. This runner never imports CARLA during CPU preparation.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path


MODULE = Path(__file__).with_name("roundabout.py")
SPEC = importlib.util.spec_from_file_location("roundabout_route", MODULE)
ROUTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTE)


def _steer(position: dict, heading: tuple[float, float], target: dict) -> float:
    direction = ROUTE._unit(ROUTE._vector(position, target))
    angle = math.atan2(ROUTE._cross(heading, direction), ROUTE._dot(heading, direction))
    return max(-1.0, min(1.0, 1.8 * angle))


def execute(adapter, case_id: str, lane_role: str) -> dict:
    """Spawn one motor vehicle, track the mapped route and seal 900 Native ticks.

    Adapter.readback_map must sample the active map and its OpenDRIVE hash.
    Adapter.step applies controls and returns the original tick's actor sample.
    Adapter.seal retains original packets, frame map and camera captures. The
    returned summary is a measurement, never a physical or legal acceptance.
    """
    source = adapter.readback_map()
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
            control = {"throttle": 0.35 if target < len(route)-1 else 0.0,
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
