"""Original 20 Hz railway instruction capture with live readback and cleanup."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import railway_7b as law

FRAME_COUNT = 900
RATE_HZ = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "testing__C177249__NRS-484B-560-7b__motor_vehicle_driver"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _save(root, name, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    (root / name).write_bytes(data)
    return {"path": name, "sha256": _sha(data)}


def capture(world, *, case_id, site_path, site_sha256, output, operator,
            frame_count=FRAME_COUNT, approach_start_m=55.0):
    if type(frame_count) is not int or not 1 <= frame_count <= FRAME_COUNT:
        raise ValueError("invalid original frame count")
    if type(approach_start_m) not in (int, float) or not 45 <= approach_start_m <= 85:
        raise ValueError("invalid source-reviewed approach start")
    name = case_id.removeprefix(ASSIGNMENT + "__")
    if case_id != ASSIGNMENT + "__" + name:
        raise ValueError("exact railway instruction identity mismatch")
    site = law.load_packet(site_path, site_sha256)
    law.validate_site(site, name)
    callbacks = ("map_bytes", "site_readback", "construct", "cameras", "control", "observe")
    if any(not callable(getattr(operator, key, None)) for key in callbacks):
        raise ValueError("reviewed Native operator callbacks incomplete")
    map_bytes = operator.map_bytes(world)
    if type(map_bytes) is not bytes or _sha(map_bytes) != site.get("map_sha256"):
        raise ValueError("live Native map differs from source-reviewed crossing")
    readback = operator.site_readback(world, site, name)
    for key in ("rail_geometry_sha256", "road_geometry_sha256", "device_placement_sha256"):
        if readback.get(key) != site.get("native_readback", {}).get(key):
            raise ValueError("live Native crossing or device readback differs: " + key)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("original Native attempt already populated")
    output.mkdir(parents=True, exist_ok=True)
    previous = copy.copy(world.get_settings())
    settings = copy.copy(previous)
    settings.synchronous_mode = True
    settings.no_rendering_mode = False
    settings.fixed_delta_seconds = 1.0 / RATE_HZ
    owned, sensors = [], []
    try:
        world.apply_settings(settings)
        active = world.get_settings()
        if active.synchronous_mode is not True or active.no_rendering_mode is not False or abs(active.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("rendered 20 Hz Native readback differs")
        built = operator.construct(world, site, name, approach_start_m)
        if not isinstance(built, dict) or not isinstance(built.get("owned"), list):
            raise ValueError("source-reviewed crossing construction/ownership missing")
        owned = built["owned"]
        vehicle = built.get("vehicle")
        if vehicle not in owned or vehicle.type_id != site["vehicle"]["blueprint_id"]:
            raise ValueError("actual motor vehicle construction differs")
        device = built.get("device")
        if device is None or not operator.device_matches(device, site):
            raise ValueError("actual official device construction/readback missing")
        if name.startswith("officer_"):
            officer = built.get("officer")
            if officer not in owned or not operator.officer_matches(officer, site):
                raise ValueError("actual police officer construction/readback missing")
        cameras, sensors = operator.cameras(world, vehicle, device, built.get("officer"), site, VIEWS)
        if not isinstance(cameras, dict) or set(cameras) != set(VIEWS) or any(not callable(cameras[v]) for v in VIEWS):
            raise ValueError("four synchronized RGB sources missing")
        rows, frame_map = [], []
        first_time = previous_frame = None
        for index in range(frame_count):
            operator.control(vehicle, device, built.get("officer"), site, name, index)
            frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            if type(frame) is not int or snapshot.frame != frame or (previous_frame is not None and frame != previous_frame + 1):
                raise ValueError("original Native frame gap")
            if first_time is None:
                first_time = now
            if abs(now - first_time - index / RATE_HZ) > .005:
                raise ValueError("original Native timestamp gap")
            previous_frame = frame
            observed = operator.observe(world, vehicle, device, built.get("officer"), site, name, frame)
            if observed.get("source_frame") != frame or observed.get("site_sha256") != site_sha256:
                raise ValueError("original instruction frame/site join differs")
            if observed.get("vehicle_actor_id") != vehicle.id:
                raise ValueError("actual motor vehicle identity differs")
            if observed.get("device_actor_or_map_id") != site["device"]["actor_or_map_id"]:
                raise ValueError("actual device identity differs")
            for view in VIEWS:
                image = cameras[view](frame)
                if type(image) is not bytes or not image:
                    raise ValueError("original RGB frame missing: " + view)
                directory = output / "cameras" / view
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{frame:06d}.png").write_bytes(image)
            motion = vehicle.get_velocity()
            velocity = [float(motion.x), float(motion.y), float(motion.z)]
            if any(not math.isfinite(value) for value in velocity):
                raise ValueError("actual velocity invalid")
            speed = math.dist(velocity, [0., 0., 0.])
            transform = vehicle.get_transform()
            position = transform.location
            heading = transform.get_forward_vector()
            vertices = vehicle.bounding_box.get_world_vertices(transform)
            body = [[float(p.x), float(p.y), float(p.z)] for p in vertices]
            if len(body) < 8 or any(not math.isfinite(v) for p in body for v in p):
                raise ValueError("actual vehicle body geometry missing")
            row = {"source_frame": frame, "source_frame_id": frame,
                   "time_s": round(index / RATE_HZ, 5), "source_site_sha256": site_sha256,
                   "device_indication": observed.get("device_indication"),
                   "officer_direction": observed.get("officer_direction"),
                   "front_body_gap_to_entry_m": observed.get("front_body_gap_to_entry_m"),
                   "rear_body_gap_to_exit_m": observed.get("rear_body_gap_to_exit_m"),
                   "speed_mps": speed, "velocity_mps": velocity,
                   "brake_applied": observed.get("brake_applied"),
                   "vehicle_actor_id": vehicle.id, "vehicle_blueprint_id": vehicle.type_id,
                   "vehicle_position_m": [float(position.x), float(position.y), float(position.z)],
                   "heading_xy": [float(heading.x), float(heading.y)],
                   "body_vertices_m": body,
                   **{key: observed.get(key) for key in (
                       "device_indication_source_ref", "device_instruction_source_ref",
                       "governed_movement_source_ref", "body_source_ref", "control_source_ref",
                       "crossing_geometry_source_ref", "officer_direction_source_ref")}}
            law.measure(site, [row])
            rows.append(row)
            frame_map.append({"frame_index": index, "native_frame": frame, "time_s": row["time_s"]})
        if _sha(operator.map_bytes(world)) != site["map_sha256"]:
            raise ValueError("Native crossing map changed during capture")
        measured = law.measure(site, rows)
        sources = {"site": _save(output, "site.json", site),
                   "history": _save(output, "history.json", rows),
                   "frame_map": _save(output, "frame-map.json", frame_map)}
        _save(output, "inventory.json", {"case_id": case_id,
              "source_kind": "original_native", "frame_count": frame_count,
              "camera_views": list(VIEWS), "reviewed_site_sha256": site_sha256,
              "sources": sources})
        return measured
    finally:
        for sensor in reversed(sensors):
            try:
                if hasattr(sensor, "stop"):
                    sensor.stop()
            finally:
                sensor.destroy()
        for actor in reversed(owned):
            if getattr(actor, "is_alive", False):
                actor.destroy()
        world.apply_settings(previous)
        restored = world.get_settings()
        if restored.synchronous_mode != previous.synchronous_mode or restored.fixed_delta_seconds != previous.fixed_delta_seconds:
            raise ValueError("Native world restoration failed")
