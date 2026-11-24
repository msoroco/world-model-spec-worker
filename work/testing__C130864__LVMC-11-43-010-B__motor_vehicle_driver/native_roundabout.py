"""Lazy source-bound construction and timed roundabout entry controls.

Release ticks are engineering requests. The original capture must later prove
the actual gap, yielding, lane use, and physical completion.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from roundabout_measurements import ASSIGNMENT_ID, SUFFIXES, validate_map


def _route(points, name):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(f"{name} source route too short")
    for index, point in enumerate(points):
        if not all(isinstance(point.get(key), (int, float)) and math.isfinite(point[key])
                   for key in ("x", "y", "speed_mps")):
            raise ValueError(f"{name} route sample invalid")
        if not 0 < point["speed_mps"] <= 20 or not point.get("lane_id"):
            raise ValueError(f"{name} route speed/lane missing")
        if index:
            previous = points[index-1]
            step = math.hypot(point["x"]-previous["x"], point["y"]-previous["y"])
            if not .15 <= step <= 8:
                raise ValueError(f"{name} route samples disconnected")
    return points


def load_case(path: str | Path, expected_sha256: str, case_id: str) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original construction source hash mismatch")
    packet = json.loads(raw)
    if case_id not in {ASSIGNMENT_ID + "__" + name for name in SUFFIXES} or packet.get("case_id") != case_id:
        raise ValueError("exact roundabout case mismatch")
    validate_map(packet)
    if not packet.get("map_name") or not packet.get("route_source_sha256"):
        raise ValueError("live map and route source missing")
    ego = _route(packet.get("ego_route"), "ego")
    other = _route(packet.get("opponent_points"), "opponent")
    if ego[0]["lane_id"] != packet["ego_entry_lane"]["lane_id"] or ego[-1]["lane_id"] != packet["ego_entry_lane"]["connected_circulating_lane_id"]:
        raise ValueError("ego route lane connection mismatch")
    if any(p["lane_id"] != packet["opponent_route"]["circulating_lane_id"] for p in other):
        raise ValueError("opponent route circulating lane mismatch")
    if not all(packet.get(key, "").startswith("vehicle.") for key in ("ego_blueprint", "opponent_blueprint")):
        raise ValueError("two source-selected vehicle blueprints required")
    if not all(isinstance(packet.get(key), int) and 0 <= packet[key] < 900
               for key in ("ego_release_tick", "opponent_release_tick")):
        raise ValueError("source-selected release ticks required")
    if not packet.get("ego_spawn") or not packet.get("opponent_spawn"):
        raise ValueError("source-selected spawn transforms required")
    return packet


def spawn(world, packet, transform_factory):
    """Spawn two distinct actors after the reviewed map and route are loaded."""
    if world.get_map().name != packet["map_name"]:
        raise ValueError("wrong live roundabout map")
    library = world.get_blueprint_library()
    ego = world.try_spawn_actor(library.find(packet["ego_blueprint"]),
                                transform_factory(packet["ego_spawn"]))
    if ego is None:
        raise RuntimeError("ego spawn failed")
    try:
        other = world.try_spawn_actor(library.find(packet["opponent_blueprint"]),
                                      transform_factory(packet["opponent_spawn"]))
        if other is None or other.id == ego.id:
            raise RuntimeError("distinct opponent spawn failed")
        return ego, other
    except Exception:
        ego.destroy()
        raise


class TimedRoute:
    """Follow original route samples after a configured release tick."""
    def __init__(self, points, release_tick, control_factory):
        self.points = _route(points, "vehicle")
        if not isinstance(release_tick, int) or not 0 <= release_tick < 900:
            raise ValueError("invalid release tick")
        self.release_tick = release_tick
        self.factory = control_factory
        self.index = 1

    def __call__(self, actor, tick):
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("invalid Native tick")
        if tick < self.release_tick or self.index == len(self.points):
            actor.apply_control(self.factory(throttle=0.0, steer=0.0, brake=1.0))
            return
        pose = actor.get_transform()
        x, y = float(pose.location.x), float(pose.location.y)
        yaw = math.radians(float(pose.rotation.yaw))
        if not all(math.isfinite(v) for v in (x, y, yaw)):
            raise ValueError("nonfinite original vehicle pose")
        target = self.points[self.index]
        distance = math.hypot(target["x"]-x, target["y"]-y)
        if distance < .8:
            self.index += 1
            if self.index == len(self.points):
                actor.apply_control(self.factory(throttle=0.0, steer=0.0, brake=1.0))
                return
            target = self.points[self.index]
            distance = math.hypot(target["x"]-x, target["y"]-y)
        previous = self.points[self.index-1]
        dx, dy = target["x"]-previous["x"], target["y"]-previous["y"]
        cross_track = abs((x-previous["x"])*dy-(y-previous["y"])*dx)/math.hypot(dx,dy)
        if cross_track > 4:
            raise ValueError("original route tracking lost")
        heading = math.atan2(target["y"]-y, target["x"]-x)
        error = (heading-yaw+math.pi)%(2*math.pi)-math.pi
        steer = max(-1.0,min(1.0,math.atan(2.7*2*math.sin(error)/max(distance,.8))/.65))
        actor.apply_control(self.factory(throttle=.35, steer=steer, brake=0.0))
