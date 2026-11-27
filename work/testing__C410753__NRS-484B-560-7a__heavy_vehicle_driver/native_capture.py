"""Source-gated original Native capture for heavy-vehicle railway crossing.

The reviewed site/operator must realize the obstacle or road profile in CARLA.
All callbacks are checked against live actor/map readback before sealing. This
module does not claim physical success from a requested construction.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import railway_7a as law

FRAME_COUNT = 900
RATE_HZ = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "testing__C410753__NRS-484B-560-7a__heavy_vehicle_driver"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _save(output, name, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    (output / name).write_bytes(data)
    return {"path": name, "sha256": _sha(data)}


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    body = [[float(p.x), float(p.y), float(p.z)] for p in points]
    if len(body) < 8 or not all(math.isfinite(x) for p in body for x in p):
        raise ValueError("actual heavy/coupled-unit body vertices missing")
    return body


def capture(world, *, case_id, site_path, site_sha256, output, operator,
            frame_count=FRAME_COUNT, approach_start_m=55.0):
    if type(frame_count) is not int or not 1 <= frame_count <= FRAME_COUNT:
        raise ValueError("invalid original Native frame count")
    if type(approach_start_m) not in (int, float) or not 45. <= approach_start_m <= 85.:
        raise ValueError("invalid source-reviewed approach start")
    name = case_id.removeprefix(ASSIGNMENT + "__")
    if case_id != ASSIGNMENT + "__" + name:
        raise ValueError("exact railway case identity mismatch")
    site = law.load_source(site_path, site_sha256)
    law.validate_site(site, name)
    callbacks = ("map_bytes", "site_readback", "construct", "cameras", "control", "observe")
    if any(not callable(getattr(operator, n, None)) for n in callbacks):
        raise ValueError("reviewed railway operator callbacks incomplete")
    map_bytes = operator.map_bytes(world)
    if type(map_bytes) is not bytes or _sha(map_bytes) != site.get("map_sha256"):
        raise ValueError("live Native map differs from reviewed railway map")
    readback = operator.site_readback(world, site, name)
    for key in ("rail_geometry_source_sha256", "crossing_profile_source_sha256",
                "downstream_space_source_sha256", "undercarriage_source_sha256"):
        if not readback.get(key) or readback[key] != site.get("native_readback", {}).get(key):
            raise ValueError("source packet/Native railway readback differs: " + key)
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
            raise ValueError("rendered 20 Hz Native world readback differs")
        built = operator.construct(world, site, name, approach_start_m)
        if not isinstance(built, dict) or not isinstance(built.get("owned"), list):
            raise ValueError("railway Native construction/ownership missing")
        owned = built["owned"]
        vehicle = built.get("vehicle")
        coupled = built.get("coupled_units")
        if vehicle not in owned or not isinstance(coupled, list) or len(coupled) != len(site["vehicle"]["coupled_units"]):
            raise ValueError("actual heavy/coupled vehicle construction missing")
        if any(unit not in owned for unit in coupled):
            raise ValueError("coupled unit is not owned")
        if vehicle.type_id != site["vehicle"]["blueprint_id"]:
            raise ValueError("actual heavy vehicle blueprint differs")
        extent = vehicle.bounding_box.extent
        dimensions = [float(extent.x) * 2, float(extent.y) * 2, float(extent.z) * 2]
        if any(abs(x - y) > .1 for x, y in zip(dimensions, site["vehicle"]["dimensions_m"])):
            raise ValueError("actual heavy vehicle body dimensions differ")
        for actor, spec in zip(coupled, site["vehicle"]["coupled_units"]):
            unit_extent = actor.bounding_box.extent
            unit_dimensions = [float(unit_extent.x) * 2, float(unit_extent.y) * 2,
                               float(unit_extent.z) * 2]
            if (str(actor.id) != str(spec["actor_id"]) or
                    actor.type_id != spec["blueprint_id"] or
                    any(abs(x - y) > .1 for x, y in zip(unit_dimensions, spec["dimensions_m"]))):
                raise ValueError("actual coupled actor identity, blueprint or dimensions differ")
        if name.startswith("space_"):
            obstruction = built.get("downstream_obstruction")
            if obstruction not in owned or not getattr(obstruction, "is_alive", False):
                raise ValueError("actual opposite-side obstruction actor missing")
        cameras, sensors = operator.cameras(world, vehicle, coupled, site, VIEWS)
        if not isinstance(cameras, dict) or set(cameras) != set(VIEWS) or any(not callable(cameras[v]) for v in VIEWS):
            raise ValueError("four synchronized original RGB sources missing")
        rows, frame_map = [], []
        first_time = prior_frame = None
        for index in range(frame_count):
            operator.control(vehicle, coupled, site, name, index)
            frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            if type(frame) is not int or snapshot.frame != frame or (prior_frame is not None and frame != prior_frame + 1):
                raise ValueError("original Native frame gap")
            if first_time is None:
                first_time = now
            if abs(now - first_time - index / RATE_HZ) > .005:
                raise ValueError("original Native timestamp gap")
            prior_frame = frame
            observed = operator.observe(world, vehicle, coupled, site, name, frame)
            if observed.get("source_frame") != frame or observed.get("site_sha256") != site_sha256:
                raise ValueError("original railway observation frame/site join differs")
            if observed.get("vehicle_actor_id") != vehicle.id or observed.get("crossing_profile_sha256") != site["native_readback"]["crossing_profile_source_sha256"]:
                raise ValueError("actual heavy vehicle or road profile differs")
            if name.startswith("space_") and not observed.get("downstream_obstacle_source_ref"):
                raise ValueError("actual downstream obstacle source missing")
            if name.startswith("clearance_") and not observed.get("undercarriage_surface_source_ref"):
                raise ValueError("actual undercarriage surface source missing")
            units = [vehicle, *coupled]
            actual_units = []
            for unit in units:
                location = unit.get_transform().location
                direction = unit.get_transform().get_forward_vector()
                motion = unit.get_velocity()
                actual_units.append({"actor_id": str(unit.id), "blueprint_id": unit.type_id,
                                     "body_source_ref": "original_native_bbox_world_vertices",
                                     "body_vertices_m": _body(unit),
                                     "position_m": [float(location.x), float(location.y), float(location.z)],
                                     "heading_xy": [float(direction.x), float(direction.y)],
                                     "velocity_mps": [float(motion.x), float(motion.y), float(motion.z)]})
            for view in VIEWS:
                image = cameras[view](frame)
                if type(image) is not bytes or not image:
                    raise ValueError("original RGB frame missing: " + view)
                directory = output / "cameras" / view
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{frame:06d}.png").write_bytes(image)
            speed = float(vehicle.get_velocity().length())
            if not math.isfinite(speed) or speed < 0:
                raise ValueError("original heavy-vehicle speed invalid")
            position = vehicle.get_transform().location
            forward = vehicle.get_transform().get_forward_vector()
            row = {"source_frame": frame, "source_frame_id": frame,
                   "time_s": round(index / RATE_HZ, 5),
                   "source_site_sha256": site_sha256,
                   "vehicle_units": actual_units, "speed_mps": speed,
                   "downstream_body_gap_m": observed.get("downstream_body_gap_m"),
                   "undercarriage_contact": observed.get("undercarriage_contact"),
                   "contact_source_ref": observed.get("contact_source_ref"),
                   "control_source_ref": observed.get("control_source_ref"),
                   "traffic_conflict_source_ref": observed.get("traffic_conflict_source_ref"),
                   "traffic_conflict": observed.get("traffic_conflict"),
                   "brake_applied": observed.get("brake_applied"),
                   "downstream_obstacle_source_ref": observed.get("downstream_obstacle_source_ref"),
                   "undercarriage_surface_source_ref": observed.get("undercarriage_surface_source_ref"),
                   "vehicle_position_m": [float(position.x), float(position.y), float(position.z)],
                   "heading_xy": [float(forward.x), float(forward.y)]}
            law.measure_frames(site, [row])
            rows.append(row)
            frame_map.append({"frame_index": index, "native_frame": frame,
                              "time_s": row["time_s"]})
        if _sha(operator.map_bytes(world)) != site["map_sha256"]:
            raise ValueError("Native railway map changed during capture")
        measured = law.measure_frames(site, rows)
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
