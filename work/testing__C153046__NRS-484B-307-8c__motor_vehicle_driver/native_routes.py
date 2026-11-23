"""Apply source-cited participant waypoint requests before each Native tick."""
from __future__ import annotations

import math
from pathlib import Path

from native_setup import validate_plan


def _location(actor):
    point = actor.get_transform().location
    values = (float(point.x), float(point.y), float(point.z))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Native route actor has nonfinite location")
    return values


class Routes:
    def __init__(self, packet_path: Path, suffix: str, actors,
                 vehicle_control, walker_control, vector_factory):
        scene, plan = validate_plan(packet_path, suffix)
        self.source_packet_sha256 = scene["source_packet_sha256"]
        self.entries = []
        for kind, specs, instances in (("pedestrian", plan["pedestrians"], actors.pedestrians),
                                       ("traffic", plan["other_traffic"], actors.traffic)):
            if len(specs) != len(instances):
                raise ValueError("Native route actor count differs from reviewed plan")
            for spec, actor in zip(specs, instances):
                speed = spec.get("route_speed_mps")
                if type(speed) not in (int, float) or not math.isfinite(speed) or speed <= 0:
                    raise ValueError("source-cited participant route speed missing")
                self.entries.append({"kind": kind, "actor": actor,
                                     "points": spec["route_points_xyz_m"],
                                     "speed": float(speed), "next": 0})
        self.vehicle_control = vehicle_control
        self.walker_control = walker_control
        self.vector_factory = vector_factory

    def before_tick(self, index: int):
        if type(index) is not int or index < 0:
            raise ValueError("Native frame index missing")
        for entry in self.entries:
            actor = entry["actor"]
            position = _location(actor)
            points = entry["points"]
            while entry["next"] < len(points):
                target = points[entry["next"]]
                delta = tuple(target[i] - position[i] for i in range(3))
                distance = math.hypot(delta[0], delta[1])
                if distance >= .5:
                    break
                entry["next"] += 1
            if entry["next"] == len(points):
                control = (self.walker_control(speed=0.0) if entry["kind"] == "pedestrian"
                           else self.vehicle_control(throttle=0.0, brake=1.0, steer=0.0))
            elif entry["kind"] == "pedestrian":
                control = self.walker_control(
                    direction=self.vector_factory(delta[0] / distance, delta[1] / distance, 0.0),
                    speed=entry["speed"])
            else:
                yaw = math.radians(float(actor.get_transform().rotation.yaw))
                error = math.atan2(math.sin(math.atan2(delta[1], delta[0]) - yaw),
                                   math.cos(math.atan2(delta[1], delta[0]) - yaw))
                steer = max(-1.0, min(1.0, error / .6))
                velocity = actor.get_velocity()
                speed = math.sqrt(sum(float(getattr(velocity, axis)) ** 2 for axis in "xyz"))
                control = self.vehicle_control(throttle=.35 if speed < entry["speed"] else 0.0,
                                               brake=.3 if speed > entry["speed"] + .5 else 0.0,
                                               steer=steer)
            actor.apply_control(control)
