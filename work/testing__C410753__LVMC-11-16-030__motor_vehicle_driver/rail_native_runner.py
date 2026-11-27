"""Fail-closed operator wiring for one reviewed railway grade-crossing case."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rail_construction import TARGETS, spawn_occluder
from rail_exception_construction import spawn_exception_actor
from rail_exception_reader import ReviewedRailExceptionReader
from rail_native_capture import capture
from rail_ray_reader import ReviewedRailRayReader
from rail_route_reader import ReviewedRailRouteReader
from rail_sight_measurement import read_reviewed_site


def _reviewed_source(root, ref, expected):
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("reviewed rail source reference missing")
    relative = Path(ref["path"])
    root = Path(root).resolve()
    source = (root / relative).resolve()
    if (relative.is_absolute() or ".." in relative.parts or
            not source.is_relative_to(root) or not source.is_file() or
            source.is_symlink() or
            hashlib.sha256(source.read_bytes()).hexdigest() != ref.get("sha256") or
            ref.get("sha256") != expected):
        raise ValueError("reviewed rail source missing or changed")
    return source


class RailRouteController:
    """Route following and speed are engineering inputs, never observed facts."""

    def __init__(self, route_reader, target_mph, control_factory):
        if not callable(control_factory):
            raise ValueError("Native rail vehicle control factory missing")
        self.points = route_reader.points
        self.target_mps = target_mph * .44704
        self.control_factory = control_factory

    def apply(self, ego):
        transform = ego.get_transform()
        location = transform.location
        yaw = math.radians(transform.rotation.yaw)
        nearest = min(range(len(self.points)), key=lambda index:
                      math.hypot(self.points[index][0] - location.x,
                                 self.points[index][1] - location.y))
        next_point = self.points[min(nearest + 1, len(self.points) - 1)]
        heading = math.atan2(next_point[1] - location.y,
                             next_point[0] - location.x)
        error = math.atan2(math.sin(heading - yaw), math.cos(heading - yaw))
        steer = max(-.7, min(.7, error / 1.05))
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        if not math.isfinite(speed):
            raise ValueError("original railway vehicle velocity invalid")
        gap = self.target_mps - speed
        throttle = min(.55, max(0.0, .22 + .18 * gap)) if gap >= -.1 else 0.0
        brake = min(.65, max(0.0, -.25 * gap)) if gap < -.1 else 0.0
        control = self.control_factory(throttle=throttle, brake=brake, steer=steer)
        ego.apply_control(control)
        return {"engineering_target_mps": self.target_mps,
                "original_speed_mps": speed, "throttle": throttle,
                "brake": brake, "steer": steer}


def run_case(*, case_key, packet, attempt_root, world, ego, location_factory,
             transform_factory, original_exception_reader, camera_adapter,
             control_factory, brake, frame_count=900):
    if case_key not in TARGETS:
        raise ValueError("unknown selected railway case")
    root = Path(attempt_root).resolve()
    road = world.get_map().to_opendrive()
    read_reviewed_site(root, packet, road)
    route = _reviewed_source(root, packet.get("route_source"),
                             packet.get("route_source_sha256"))
    rays = _reviewed_source(root, packet.get("rail_ray_geometry_source"),
                            packet.get("rail_ray_geometry_source_sha256"))
    exceptions = _reviewed_source(root, packet.get("rail_exception_review_source"),
                                  packet.get("rail_exception_review_sha256"))
    route_reader = ReviewedRailRouteReader(packet, route)
    ray_reader = ReviewedRailRayReader(packet, rays, world, location_factory)
    exception_reader = ReviewedRailExceptionReader(
        packet, exceptions, root, original_exception_reader)
    controller = RailRouteController(route_reader, TARGETS[case_key][0], control_factory)
    occluder = None
    exception_actor = None
    started = False
    try:
        occluder = spawn_occluder(world, transform_factory, root, packet,
                                  packet["road_sha256"], case_key)
        exception_actor = spawn_exception_actor(world, transform_factory, root, packet,
                                                packet["road_sha256"], case_key)
        camera_adapter.start()
        started = True
        return capture(
            case_id=packet["assignment_id"] + "__" + case_key,
            packet=packet, world=world, ego=ego,
            route_reader=route_reader, ray_reader=ray_reader,
            exception_reader=exception_reader,
            camera_reader=camera_adapter.read, brake=brake,
            attempt_root=root, before_tick=controller.apply,
            frame_count=frame_count)
    finally:
        try:
            if started:
                camera_adapter.stop()
        finally:
            try:
                if occluder is not None:
                    occluder.destroy()
            finally:
                if exception_actor is not None:
                    exception_actor.destroy()
