"""Lazy CARLA taxi spawn and geometric right-turn route for C150530.

This module is a construction component. Capture, legal source provenance,
camera audit and physical completion require additional package work.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from candidate_opendrive import inspect as inspect_xodr
from stand_route import inspect as inspect_route


def route_points(layout: dict) -> list[tuple[float, float]]:
    inspect_route(layout)
    stand_x = layout["stand"]["center"][0]
    departure_x = layout["departure"]["point"][0]
    points = [(stand_x, -4.5), (departure_x, -1.75)]
    points.extend((x, -1.75) for x in (departure_x + 6, -30, -12, -4)
                  if departure_x + 1 < x < -4)
    points.append((-4, -1.75))
    for step in range(1, 13):
        angle = math.pi * step / 24
        points.append((-4 + 2.25 * math.sin(angle), -4 + 2.25 * math.cos(angle)))
    points.extend([(-1.75, -8), (-1.75, -20), (-1.75, -35)])
    if any(math.dist(a, b) < 1e-8 for a, b in zip(points, points[1:])):
        raise ValueError("route has duplicate consecutive waypoints")
    return points


def validate_native_map(world, map_bytes: bytes, case: str) -> str:
    inspect_xodr(map_bytes, case)
    actual = world.get_map().to_opendrive().encode("utf-8")
    actual_sha = hashlib.sha256(actual).hexdigest()
    expected_sha = hashlib.sha256(map_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("Native OpenDRIVE readback differs from exact candidate source")
    return actual_sha


def spawn_taxi(world, carla, layout: dict, map_bytes: bytes, blueprint_id: str):
    """Spawn one taxi at the candidate stand; caller owns actor destruction."""
    inspect_route(layout)
    validate_native_map(world, map_bytes, layout["case"])
    if not blueprint_id.startswith("vehicle."):
        raise ValueError("taxi requires a vehicle blueprint ID")
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None:
        raise ValueError("Native vehicle blueprint unavailable")
    if blueprint.has_attribute("role_name"):
        blueprint.set_attribute("role_name", "c150530_taxi")
    x, y = layout["stand"]["center"]
    actor = world.spawn_actor(blueprint, carla.Transform(
        carla.Location(x=x, y=y, z=0.35), carla.Rotation(yaw=0)))
    if actor is None:
        raise RuntimeError("Native taxi spawn failed")
    return actor


class RouteController:
    """Pure-pursuit-style engineering controller with explicit completion."""

    def __init__(self, layout: dict, target_speed_mps: float = 4.0):
        if not (0 < target_speed_mps <= 8):
            raise ValueError("invalid engineering target speed")
        self.points = route_points(layout)
        self.index = 0
        self.target_speed_mps = target_speed_mps

    def control(self, x: float, y: float, yaw_deg: float, speed_mps: float) -> dict:
        if not all(math.isfinite(v) for v in (x, y, yaw_deg, speed_mps)):
            raise ValueError("nonfinite Native motion sample")
        if speed_mps < 0:
            raise ValueError("negative speed")
        while self.index < len(self.points) - 1 and math.dist((x, y), self.points[self.index]) < 2.0:
            self.index += 1
        target = self.points[self.index]
        heading = math.degrees(math.atan2(target[1] - y, target[0] - x))
        error = ((heading - yaw_deg + 180) % 360) - 180
        steer = max(-1.0, min(1.0, error / 35.0))
        finished = self.index == len(self.points) - 1 and math.dist((x, y), target) < 2.0
        throttle = 0.0 if finished else max(0.0, min(0.4, (self.target_speed_mps - speed_mps) * 0.12))
        brake = 1.0 if finished else (0.3 if speed_mps > self.target_speed_mps + 1 else 0.0)
        return {"steer": steer, "throttle": throttle, "brake": brake,
                "target": target, "waypoint_index": self.index, "finished": finished}


def apply_step(actor, carla, controller: RouteController) -> dict:
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    command = controller.control(transform.location.x, transform.location.y,
                                 transform.rotation.yaw, speed)
    actor.apply_control(carla.VehicleControl(throttle=command["throttle"],
                                           brake=command["brake"], steer=command["steer"]))
    return command
