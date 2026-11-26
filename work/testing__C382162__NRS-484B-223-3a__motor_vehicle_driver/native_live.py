"""Own one source-gated Native vehicle, four cameras and world lease.

This module remains importable without CARLA; the injected operator supplies
map readback, exact spawn and route control after source verification.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from center_lane_site import verify_reviewed_site
from native_capture import VIEWS, camera_reader, capture_original


def _body(vehicle):
    vertices = vehicle.bounding_box.get_world_vertices(vehicle.get_transform())
    points = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
    if len(points) != 8 or not all(math.isfinite(n) for point in points for n in point):
        raise ValueError("original motor-vehicle body vertices missing")
    return points


def capture(world, *, attempt_root, case_id, site, purpose_binding, operator,
            count=900, dimensions=None):
    root = Path(attempt_root).resolve()
    map_bytes = world.get_map().to_opendrive().encode()
    kind = case_id.rsplit("__", 1)[-1]
    verify_reviewed_site(root, site, kind, map_bytes.decode())
    required = ("site_readback", "spawn_vehicle", "cameras", "control", "observe")
    if any(not callable(getattr(operator, name, None)) for name in required):
        raise ValueError("reviewed Native operator callback missing")
    readback = operator.site_readback(world, site)
    for name in ("lanes", "junction", "route", "highway_road_id"):
        if readback.get(name) != site.get(name):
            raise ValueError("Native lane/junction route readback differs: " + name)
    original_settings = copy.copy(world.get_settings())
    original_weather = world.get_weather()
    settings = copy.copy(original_settings)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    vehicle, sensors, callbacks = None, [], None
    first_time = last_frame = None
    try:
        world.apply_settings(settings)
        actual = world.get_settings()
        if actual.synchronous_mode is not True or abs(actual.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native 20 Hz settings readback failed")
        vehicle = operator.spawn_vehicle(world, site, case_id)
        if (vehicle is None or not getattr(vehicle, "is_alive", False) or
                not str(getattr(vehicle, "type_id", "")).startswith("vehicle.") or
                type(getattr(vehicle, "id", None)) is not int):
            raise ValueError("original motor vehicle spawn failed")
        callbacks, sensors = operator.cameras(world, vehicle, VIEWS)
        if (not isinstance(callbacks, dict) or set(callbacks) != set(VIEWS) or
                any(not callable(callbacks[name]) for name in VIEWS) or
                len(sensors) != 4):
            raise ValueError("four original synchronized cameras missing")

        def observe(index):
            nonlocal first_time, last_frame
            operator.control(vehicle, site, case_id, index)
            frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            if (type(frame) is not int or snapshot.frame != frame or
                    (last_frame is not None and frame != last_frame + 1) or
                    not math.isfinite(now)):
                raise ValueError("original Native frame/time identity drift")
            last_frame = frame
            if first_time is None:
                first_time = now
            elapsed = now - first_time
            if abs(elapsed - index / 20) > .005:
                raise ValueError("original Native 20 Hz timestamp drift")
            state = operator.observe(world, vehicle, site, frame)
            if (state.get("source_frame_id") != frame or
                    state.get("actor_id") != vehicle.id or
                    state.get("driver_id") != site.get("driver_id")):
                raise ValueError("original actor/driver readback mismatch")
            images = {view: callbacks[view](frame) for view in VIEWS}
            transform = vehicle.get_transform()
            forward = transform.get_forward_vector()
            speed = float(vehicle.get_velocity().length())
            if not all(math.isfinite(value) for value in (
                    transform.location.x, transform.location.y, transform.location.z,
                    forward.x, forward.y, speed)):
                raise ValueError("original Native actor kinematics invalid")
            return {"original_frame": frame, "time_s": round(elapsed, 5),
                    "road_id": state.get("road_id"), "lane_id": state.get("lane_id"),
                    "maneuver": state.get("maneuver"), "driver_id": state["driver_id"],
                    "source_ref": "native/live-readback", "actor_id": vehicle.id,
                    "body_vertices_m": _body(vehicle),
                    "vehicle_blueprint": vehicle.type_id,
                    "x": float(transform.location.x), "y": float(transform.location.y),
                    "z": float(transform.location.z), "heading_x": float(forward.x),
                    "heading_y": float(forward.y), "speed_mps": speed,
                    "camera_images": images}

        result = capture_original(root, case_id, site, purpose_binding, map_bytes.decode(),
                                  camera_reader(root, observe, dimensions), count=count)
        if hashlib.sha256(world.get_map().to_opendrive().encode()).digest() != hashlib.sha256(map_bytes).digest():
            raise ValueError("Native map changed during acquisition")
        return result
    finally:
        first_error = None
        for sensor in reversed(sensors):
            try:
                sensor.stop()
            except Exception as error:
                first_error = first_error or error
            try:
                sensor.destroy()
            except Exception as error:
                first_error = first_error or error
        if vehicle is not None and getattr(vehicle, "is_alive", False):
            try:
                vehicle.destroy()
            except Exception as error:
                first_error = first_error or error
        try:
            world.set_weather(original_weather)
        finally:
            world.apply_settings(original_settings)
        restored = world.get_settings()
        if (restored.synchronous_mode != original_settings.synchronous_mode or
                restored.fixed_delta_seconds != original_settings.fixed_delta_seconds):
            raise ValueError("original Native world restoration failed")
        if first_error is not None:
            raise first_error
