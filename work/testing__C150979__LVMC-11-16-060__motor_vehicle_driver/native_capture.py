"""Source-sealed original Native speed and posting capture.

The local operator supplies original map, sign and actor readback. A reviewed
site packet selects the route and its posting context; commands are never used
as measured speed or proof of legal posting authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import speed_delivery as speed


HERE = Path(__file__).resolve().parent
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900
RATE_HZ = 20


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _save(root, name, payload):
    path = root / (name + ".json")
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(data)
    return {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}


def capture(world, *, case_id, site_path, site_sha256, output, operator,
            ego_blueprint="vehicle.tesla.model3", throttle_scale=1.0):
    """Capture 900 original 20 Hz frames with four synchronous camera sources.

    Operator methods: map_bytes(world), sign_readback(world), cameras(world,
    actor, views), observe(world, actor, native_frame, site). The latter returns
    measured route station, map identity, actor identity and sign readback.
    """
    _require(case_id.startswith(speed.ASSIGNMENT + "__"), "exact case identity mismatch")
    case_key = case_id.removeprefix(speed.ASSIGNMENT + "__")
    _require(case_key in speed.TARGETS, "unknown speed case")
    _require(throttle_scale > 0 and throttle_scale <= 1.0, "invalid controller scale")
    raw = Path(site_path).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == site_sha256, "reviewed site seal mismatch")
    site = json.loads(raw)
    _require(site.get("source_kind") == "reviewed_original_native_speed_site", "reviewed site source missing")
    _require(site.get("assignment_id") == speed.ASSIGNMENT, "site assignment mismatch")
    _require(site.get("case_ids") == [speed.ASSIGNMENT + "__" + key for key in
             ("same25_below", "same25_at", "same25_above", "different35")],
             "reviewed case inventory mismatch")
    _require(site.get("controller_sha256") == speed.sha256(HERE / "speed_delivery.py"),
             "reviewed controller source changed")
    for name in ("map_bytes", "sign_readback", "cameras", "observe"):
        _require(callable(getattr(operator, name, None)), "Native operator callback missing: " + name)
    map_bytes = operator.map_bytes(world)
    _require(type(map_bytes) is bytes and hashlib.sha256(map_bytes).hexdigest() == site.get("map_sha256"),
             "loaded map differs from reviewed site")
    speed.validate_site(site, case_key, site["map_sha256"])
    _require(operator.sign_readback(world) == site["signs"], "Native sign inventory differs from reviewed site")
    output = Path(output)
    _require(not output.exists() or not any(output.iterdir()), "attempt directory already populated")
    output.mkdir(parents=True, exist_ok=True)
    prior = copy.copy(world.get_settings())
    settings = copy.copy(prior)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    actor = None
    sensors = []
    try:
        world.apply_settings(settings)
        actual = world.get_settings()
        _require(actual.synchronous_mode is True and abs(actual.fixed_delta_seconds - .05) < 1e-9,
                 "Native 20 Hz settings readback failed")
        construction = speed.construct(world, site, case_key, site["map_sha256"], ego_blueprint)
        actor = construction["actor"]
        _require(getattr(actor, "is_alive", False), "Native ego actor not alive")
        _require(getattr(actor, "type_id", None) == ego_blueprint,
                 "spawned Native blueprint differs from reviewed configuration")
        actor_id = str(actor.id)
        callbacks, sensors = operator.cameras(world, actor, VIEWS)
        _require(isinstance(callbacks, dict) and set(callbacks) == set(VIEWS) and
                 all(callable(callbacks[name]) for name in VIEWS), "four synchronous cameras missing")
        frames = []
        frame_map = []
        first_time = None
        last_native_frame = None
        for index in range(FRAME_COUNT):
            control = speed.control_tick(actor, construction["target_mps"] * throttle_scale)
            native_frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            _require(type(native_frame) is int and snapshot.frame == native_frame,
                     "Native tick/snapshot mismatch")
            _require(last_native_frame is None or native_frame == last_native_frame + 1,
                     "Native frame discontinuity")
            if first_time is None:
                first_time = now
            _require(math.isfinite(now) and abs(now - first_time - index / RATE_HZ) <= .005,
                     "Native timestamp discontinuity")
            last_native_frame = native_frame
            observed = operator.observe(world, actor, native_frame, site)
            _require(isinstance(observed, dict) and observed.get("source_frame_id") == native_frame,
                     "original frame readback missing")
            _require(str(observed.get("actor_id")) == actor_id and observed.get("ego_alive") is True,
                     "original ego identity/alive mismatch")
            _require(observed.get("road_id") == site["route"]["road_id"] and
                     observed.get("lane_id") == site["route"]["lane_id"],
                     "original route lane changed")
            for field in ("route_station_m", "speed_mps", "x", "y", "z", "heading_x", "heading_y"):
                value = observed.get(field)
                _require(type(value) in (int, float) and math.isfinite(value),
                         "original observation missing: " + field)
            _require(observed["speed_mps"] >= 0, "original speed negative")
            body = observed.get("body_vertices_m")
            _require(isinstance(body, list) and len(body) >= 4 and all(
                     isinstance(point, list) and len(point) == 3 and all(
                         type(v) in (int, float) and math.isfinite(v) for v in point)
                     for point in body), "original body vertices missing")
            for view in VIEWS:
                image = callbacks[view](native_frame)
                _require(type(image) is bytes and image, "original camera frame missing: " + view)
                camera_dir = output / "cameras" / view
                camera_dir.mkdir(parents=True, exist_ok=True)
                (camera_dir / f"{native_frame:06d}.png").write_bytes(image)
            frame = {"frame_index": index, "time_s": round(index / RATE_HZ, 5),
                     "source_frame_id": native_frame, "actor_id": actor_id,
                     "vehicle_blueprint": ego_blueprint,
                     "ego_alive": True, "driver_role": "motor_vehicle_driver",
                     "map_sha256": site["map_sha256"], "road_id": observed["road_id"],
                     "lane_id": observed["lane_id"], "route_station_m": observed["route_station_m"],
                     "speed_mps": observed["speed_mps"], "x": observed["x"],
                     "y": observed["y"], "z": observed["z"], "body_vertices_m": body,
                     "heading_x": observed["heading_x"], "heading_y": observed["heading_y"],
                     "requested_mps": control["requested_mps"]}
            if "sign_id" in observed:
                frame["sign_id"] = observed["sign_id"]
                frame["sign_value_mph"] = observed.get("sign_value_mph")
            frames.append(frame)
            frame_map.append({"frame_index": index, "native_frame": native_frame,
                              "time_s": frame["time_s"]})
        _require(hashlib.sha256(operator.map_bytes(world)).hexdigest() == site["map_sha256"],
                 "Native map changed during capture")
        measured = speed.measure(site, case_key, site["map_sha256"], frames)
        sources = {"site": _save(output, "site", site), "history": _save(output, "history", frames),
                   "frame_map": _save(output, "frame-map", frame_map)}
        _save(output, "inventory", {"case_id": case_id, "source_kind": "original_native",
               "frame_count": FRAME_COUNT, "camera_views": list(VIEWS),
               "reviewed_site_sha256": site_sha256, "sources": sources})
        return measured
    finally:
        for sensor in reversed(sensors):
            try:
                if hasattr(sensor, "stop"):
                    sensor.stop()
            finally:
                sensor.destroy()
        if actor is not None and getattr(actor, "is_alive", False):
            actor.destroy()
        world.apply_settings(prior)
        restored = world.get_settings()
        _require(restored.synchronous_mode == prior.synchronous_mode and
                 restored.fixed_delta_seconds == prior.fixed_delta_seconds,
                 "Native settings restoration readback failed")
