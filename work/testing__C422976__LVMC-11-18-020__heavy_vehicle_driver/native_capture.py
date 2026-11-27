"""Capture original School-Xing Native evidence with source and world readback."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import school_crossing as school


FRAME_COUNT = 900
RATE_HZ = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _save(output: Path, name: str, value) -> dict:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (output / name).write_bytes(data)
    return {"path": name, "sha256": _sha(data)}


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    body = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
    school.require(len(body) >= 4 and all(math.isfinite(x) for p in body for x in p),
                   "original heavy-vehicle body vertices missing")
    return body


def _front(actor, body):
    forward = actor.get_transform().get_forward_vector()
    projection = [p[0] * forward.x + p[1] * forward.y for p in body]
    greatest = max(projection)
    edge = [p for p, v in zip(body, projection) if greatest - v < .05]
    school.require(len(edge) >= 2, "original heavy-vehicle front edge missing")
    return [sum(p[i] for p in edge) / len(edge) for i in (0, 1)]


def capture(world, *, case_id: str, site_path: str | Path, site_sha256: str,
            output: str | Path, operator, frame_count: int = FRAME_COUNT,
            approach_start_m: float = 55.0) -> dict:
    """Require reviewed source packets and retain synchronized original rows."""
    school.require(type(frame_count) is int and 1 <= frame_count <= FRAME_COUNT,
                   "invalid capture frame count")
    school.require(math.isfinite(approach_start_m) and 45 <= approach_start_m <= 85,
                   "invalid reviewed heavy-vehicle approach start")
    case = next((c for c in school.CASES
                 if case_id == school.ASSIGNMENT + "__" + c.name), None)
    school.require(case is not None, "unknown exact school-crossing case")
    for name in ("map_bytes", "site_readback", "construct", "cameras", "control", "observe"):
        school.require(callable(getattr(operator, name, None)),
                       "Native operator callback missing: " + name)
    site_path = Path(site_path)
    site = school.load_site(site_path, site_sha256, case,
                            native_readback=operator.site_readback(world, case))
    school.require(_sha(operator.map_bytes(world)) == site["map_sha256"],
                   "loaded Native map differs from reviewed source")
    output = Path(output)
    school.require(not output.exists() or not any(output.iterdir()),
                   "attempt directory already populated")
    output.mkdir(parents=True, exist_ok=True)
    previous = copy.copy(world.get_settings())
    settings = copy.copy(previous)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    owned = []
    sensors = []
    try:
        world.apply_settings(settings)
        active = world.get_settings()
        school.require(active.synchronous_mode is True and
                       abs(active.fixed_delta_seconds - .05) < 1e-9,
                       "Native 20 Hz settings readback failed")
        built = operator.construct(world, site, case, approach_start_m)
        school.require(isinstance(built, dict) and isinstance(built.get("owned"), list),
                       "Native construction ownership missing")
        owned = built["owned"]
        vehicle, person = built.get("vehicle"), built.get("person")
        school.require(vehicle in owned and person in owned and vehicle is not person,
                       "original heavy vehicle or person not owned")
        school.require(getattr(vehicle, "is_alive", False) and
                       getattr(person, "is_alive", False),
                       "original participants are not alive")
        school.require(str(vehicle.id) == site["vehicle_id"] and
                       str(person.id) == site["person"]["id"],
                       "original participant IDs differ from reviewed site")
        school.require(getattr(vehicle, "type_id", "") == site["vehicle_blueprint"],
                       "heavy vehicle blueprint differs from reviewed class source")
        extent = vehicle.bounding_box.extent
        actual_dimensions = {"length": float(extent.x) * 2,
                             "width": float(extent.y) * 2,
                             "height": float(extent.z) * 2}
        school.require(all(abs(actual_dimensions[key] - site["vehicle_dimensions_m"][key]) <= .1
                           for key in actual_dimensions),
                       "heavy vehicle dimensions differ from reviewed class source")
        cameras, sensors = operator.cameras(world, vehicle, person, VIEWS)
        school.require(isinstance(cameras, dict) and set(cameras) == set(VIEWS) and
                       all(callable(cameras[v]) for v in VIEWS),
                       "four original RGB sources missing")
        rows, frame_map = [], []
        first_time = previous_frame = None
        attempt_sha = site["source_records"]["pedestrian_source"]["sha256"]
        for index in range(frame_count):
            operator.control(vehicle, person, site, case, index)
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            school.require(type(native_frame) is int and snapshot.frame == native_frame and
                           (previous_frame is None or native_frame == previous_frame + 1),
                           "original Native frame gap")
            if first_time is None:
                first_time = now
            school.require(abs(now - first_time - index / RATE_HZ) <= .005,
                           "original Native timestamp gap")
            previous_frame = native_frame
            observed = operator.observe(world, vehicle, person, site, case, native_frame)
            school.require(observed.get("source_frame_id") == native_frame and
                           str(observed.get("vehicle_id")) == str(vehicle.id) and
                           str(observed.get("person_id")) == str(person.id),
                           "original participant/frame join mismatch")
            school.require(observed.get("road_id") == site["road_id"] and
                           observed.get("lane_id") == site["lane_id"],
                           "original approach lane changed")
            school.require(observed.get("person_attempt_source_sha256") == attempt_sha and
                           type(observed.get("person_attempt_observed")) is bool,
                           "independent person attempt evidence missing")
            school.require(observed.get("person_side_relative_to_approach") == case.person_side,
                           "person side differs from reviewed approach")
            school.require(observed.get("sign_displayed") is case.sign_displayed,
                           "School-Xing display changed")
            body = _body(vehicle)
            transform = vehicle.get_transform()
            forward = transform.get_forward_vector()
            speed = float(vehicle.get_velocity().length())
            school.require(math.isfinite(speed) and speed >= 0,
                           "original heavy-vehicle speed invalid")
            person_transform = person.get_transform()
            location = person_transform.location
            person_forward = person_transform.get_forward_vector()
            person_speed = float(person.get_velocity().length())
            school.require(math.isfinite(person_speed) and person_speed >= 0,
                           "original person speed invalid")
            person_body = _body(person)
            for view in VIEWS:
                image = cameras[view](native_frame)
                school.require(type(image) is bytes and image,
                               "original RGB frame missing: " + view)
                directory = output / "cameras" / view
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{native_frame:06d}.png").write_bytes(image)
            row = {"source_frame_id": native_frame, "original_frame": native_frame,
                   "time_s": round(index / RATE_HZ, 5), "actor_id": str(vehicle.id),
                   "person_id": str(person.id), "driver_id": site["operator_id"],
                   "vehicle_blueprint": vehicle.type_id, "native_source": True,
                   "road_id": observed["road_id"], "lane_id": observed["lane_id"],
                   "vehicle_front_xy": _front(vehicle, body),
                   "body_vertices_m": body, "speed_mps": speed,
                   "x": float(transform.location.x), "y": float(transform.location.y),
                   "z": float(transform.location.z),
                   "heading_x": float(forward.x), "heading_y": float(forward.y),
                   "person_xy": [float(location.x), float(location.y)],
                   "person_z": float(location.z), "person_blueprint": person.type_id,
                   "person_body_vertices_m": person_body,
                   "person_speed_mps": person_speed,
                   "person_heading_x": float(person_forward.x),
                   "person_heading_y": float(person_forward.y),
                   "sign_displayed": observed["sign_displayed"],
                   "person_attempt_source_sha256": attempt_sha,
                   "person_attempt_observed": observed["person_attempt_observed"],
                   "person_side_relative_to_approach": observed["person_side_relative_to_approach"]}
            rows.append(row)
            frame_map.append({"frame_index": index, "native_frame": native_frame,
                              "time_s": row["time_s"]})
        school.require(_sha(operator.map_bytes(world)) == site["map_sha256"],
                       "Native map changed during capture")
        measurement = school.measure_original(rows, site, case)
        sources = {"site": _save(output, "site.json", site),
                   "history": _save(output, "history.json", rows),
                   "frame_map": _save(output, "frame-map.json", frame_map)}
        _save(output, "inventory.json", {"case_id": case_id,
              "source_kind": "original_native", "frame_count": frame_count,
              "camera_views": list(VIEWS), "reviewed_site_sha256": site_sha256,
              "sources": sources})
        return measurement
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
        school.require(restored.synchronous_mode == previous.synchronous_mode and
                       restored.fixed_delta_seconds == previous.fixed_delta_seconds,
                       "Native world settings restoration failed")
