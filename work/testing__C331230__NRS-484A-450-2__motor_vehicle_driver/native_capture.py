"""Original Native near-side crosswalk capture with reviewed site readback."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import near_crosswalk as near

ASSIGNMENT = "testing__C331230__NRS-484A-450-2__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900
RATE_HZ = 20


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(output, name, payload):
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path = output / name
    path.write_bytes(data)
    return {"path": name, "sha256": sha(data)}


def reviewed_site(site, site_path, site_sha256, operator, world, case):
    raw = Path(site_path).read_bytes()
    require(sha(raw) == site_sha256, "reviewed crosswalk site seal mismatch")
    require(site.get("source_kind") == "reviewed_original_native_crosswalk_site" and
            site.get("assignment_id") == ASSIGNMENT, "reviewed site identity mismatch")
    require(site.get("case_ids") == [ASSIGNMENT + "__" + item.name for item in near.CASES],
            "exact crosswalk case inventory changed")
    records = site.get("source_records")
    require(isinstance(records, dict) and set(near.SOURCES) <= set(records),
            "independent reviewed source records missing")
    for name in near.SOURCES:
        entry = records[name]
        expected = site.get(name + "_source_sha256")
        require(isinstance(entry, dict) and entry.get("sha256") == expected and
                isinstance(expected, str) and len(expected) == 64,
                "reviewed source hash missing: " + name)
        relative = Path(entry["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,
                "reviewed source path escapes site directory: " + name)
        path = (Path(site_path).parent / relative).resolve()
        require(path.is_file() and sha(path.read_bytes()) == expected,
                "reviewed source bytes changed: " + name)
    for callback in ("map_bytes", "site_readback", "cameras", "observe", "control"):
        require(callable(getattr(operator, callback, None)),
                "Native operator callback missing: " + callback)
    require(sha(operator.map_bytes(world)) == site.get("map_sha256"),
            "loaded Native map differs from reviewed crosswalk site")
    readback = operator.site_readback(world, site)
    for key in ("stop_sign_id", "stop_sign_orientation_xy", "stop_sign_governs",
                "intersection_rect_m", "near_crosswalk_rect_m", "marked",
                "opposing_sidewalk_left_xy", "opposing_sidewalk_right_xy"):
        require(readback.get(key) == site.get(key),
                "Native sign/crosswalk geometry differs from reviewed site: " + key)
    near.validate_scene(site, case)


def _front(actor, body):
    forward = actor.get_transform().get_forward_vector()
    projections = [point[0] * forward.x + point[1] * forward.y for point in body]
    greatest = max(projections)
    front_vertices = [point for point, projection in zip(body, projections)
                      if greatest - projection < .05]
    require(len(front_vertices) >= 2, "Native front body edge missing")
    return [sum(point[axis] for point in front_vertices) / len(front_vertices)
            for axis in (0, 1)]


def _body(actor):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    body = [[float(vertex.x), float(vertex.y), float(vertex.z)]
            for vertex in vertices]
    require(len(body) >= 4 and all(math.isfinite(v) for point in body for v in point),
            "original Native vehicle body vertices missing")
    return body


def capture(world, *, case_id, site_path, site_sha256, output, operator,
            brake_distance_m=12.0):
    require(case_id.startswith(ASSIGNMENT + "__"), "exact case identity mismatch")
    case = next((item for item in near.CASES if ASSIGNMENT + "__" + item.name == case_id), None)
    require(case is not None, "unknown near-side crosswalk case")
    require(0 < brake_distance_m <= 25, "invalid route-controller brake distance")
    site = json.loads(Path(site_path).read_text())
    reviewed_site(site, site_path, site_sha256, operator, world, case)
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "attempt directory already populated")
    output.mkdir(parents=True, exist_ok=True)
    prior = copy.copy(world.get_settings())
    settings = copy.copy(prior)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    vehicle = None
    sensors = []
    try:
        world.apply_settings(settings)
        actual = world.get_settings()
        require(actual.synchronous_mode is True and abs(actual.fixed_delta_seconds - .05) < 1e-9,
                "Native 20 Hz settings readback failed")
        built = near.construct(operator, site, case)
        vehicle = built["owned"][0]
        require(getattr(vehicle, "is_alive", False), "Native ego vehicle not alive")
        require(getattr(vehicle, "type_id", "").startswith("vehicle."),
                "Native ego motor vehicle blueprint missing")
        callbacks, sensors = operator.cameras(world, vehicle, VIEWS)
        require(isinstance(callbacks, dict) and set(callbacks) == set(VIEWS) and
                all(callable(callbacks[view]) for view in VIEWS),
                "four original synchronous camera sources missing")
        frames, frame_map = [], []
        start_time = last_frame = None
        for index in range(FRAME_COUNT):
            operator.control(vehicle, site, case, brake_distance_m)
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            require(type(native_frame) is int and snapshot.frame == native_frame and
                    (last_frame is None or native_frame == last_frame + 1),
                    "Native frame identity discontinuity")
            if start_time is None:
                start_time = now
            require(math.isfinite(now) and abs(now - start_time - index / RATE_HZ) <= .005,
                    "Native 20 Hz timestamp discontinuity")
            last_frame = native_frame
            observed = operator.observe(world, vehicle, native_frame, site)
            require(observed.get("source_frame_id") == native_frame and
                    str(observed.get("actor_id")) == str(vehicle.id) and
                    observed.get("ego_alive") is True,
                    "original actor identity/readback mismatch")
            require(observed.get("road_id") == site.get("road_id") and
                    observed.get("lane_id") == site.get("lane_id"),
                    "original governed approach lane changed")
            speed = float(vehicle.get_velocity().length())
            require(math.isfinite(speed) and speed >= 0, "original vehicle speed invalid")
            transform = vehicle.get_transform()
            forward = transform.get_forward_vector()
            body = _body(vehicle)
            front = _front(vehicle, body)
            for view in VIEWS:
                image = callbacks[view](native_frame)
                require(type(image) is bytes and image, "original RGB frame missing: " + view)
                camera_dir = output / "cameras" / view
                camera_dir.mkdir(parents=True, exist_ok=True)
                (camera_dir / f"{native_frame:06d}.png").write_bytes(image)
            row = {"original_frame": native_frame, "source_frame_id": native_frame,
                   "time_s": round(index / RATE_HZ, 5),
                   "actor_id": str(vehicle.id), "driver_id": site["driver_id"],
                   "vehicle_id": site["vehicle_id"], "vehicle_blueprint": vehicle.type_id,
                   "road_id": observed["road_id"], "lane_id": observed["lane_id"],
                   "marked": case.marked, "stop_sign_governs": True,
                   "vehicle_front_xy": front, "speed_mps": speed,
                   "x": float(transform.location.x), "y": float(transform.location.y),
                   "z": float(transform.location.z), "heading_x": float(forward.x),
                   "heading_y": float(forward.y), "body_vertices_m": body}
            row.update({name + "_source_sha256": site[name + "_source_sha256"]
                        for name in near.SOURCES})
            frames.append(row)
            frame_map.append({"frame_index": index, "native_frame": native_frame,
                              "time_s": row["time_s"]})
        require(sha(operator.map_bytes(world)) == site["map_sha256"],
                "Native map changed during capture")
        measurement = near.measure_original(frames, site, case)
        sources = {"site": save(output, "site.json", site),
                   "history": save(output, "history.json", frames),
                   "frame_map": save(output, "frame-map.json", frame_map)}
        save(output, "inventory.json", {"case_id": case_id,
             "source_kind": "original_native", "frame_count": FRAME_COUNT,
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
        if vehicle is not None and getattr(vehicle, "is_alive", False):
            vehicle.destroy()
        world.apply_settings(prior)
        restored = world.get_settings()
        require(restored.synchronous_mode == prior.synchronous_mode and
                restored.fixed_delta_seconds == prior.fixed_delta_seconds,
                "Native settings restoration readback failed")
