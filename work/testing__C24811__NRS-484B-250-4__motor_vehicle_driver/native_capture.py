"""Capture 900 synchronized Native frames and two original vehicle histories."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import native_signal as signal


def _save(root, name, value):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()
    (root / name).write_bytes(data)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    body = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
    signal.require(len(body) >= 4 and
                   all(math.isfinite(n) for point in body for n in point),
                   "original vehicle body vertices missing")
    return body


def _actor_row(actor, station, frame, time_s, site):
    transform = actor.get_transform()
    forward = transform.get_forward_vector()
    velocity = actor.get_velocity()
    speed = float(velocity.length())
    signal.require(math.isfinite(speed) and speed >= 0 and
                   isinstance(station, (int, float)) and math.isfinite(station),
                   "original vehicle speed/station invalid")
    return {"original_frame": frame, "source_frame_id": frame, "time_s": time_s,
            "actor_id": str(actor.id), "vehicle_blueprint": actor.type_id,
            "front_m": float(station), "speed_mps": speed,
            "x": float(transform.location.x), "y": float(transform.location.y),
            "z": float(transform.location.z),
            "heading_x": float(forward.x), "heading_y": float(forward.y),
            "body_vertices_m": _body(actor),
            **{name + "_source_sha256": site[name + "_source_sha256"]
               for name in signal.SOURCES}}


def capture(world, *, case, site, site_path, output, operator, brake_distance_m):
    signal.require(0 < brake_distance_m <= 25,
                   "invalid source-gated brake distance")
    for callback in ("map_bytes", "site_readback", "construct", "cameras",
                     "observe", "control"):
        signal.require(callable(getattr(operator, callback, None)),
                       "reviewed Native operator missing " + callback)
    signal.validate_site(site, site_path, case,
                         map_bytes=operator.map_bytes(world),
                         readback=operator.site_readback(world, site))
    root = Path(output)
    signal.require(not root.exists() or not any(root.iterdir()),
                   "attempt directory already populated")
    root.mkdir(parents=True, exist_ok=True)
    for name in signal.SOURCES:
        relative = Path(site["source_records"][name]["path"])
        source = Path(site_path).resolve().parent / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        signal.require(not target.exists(), "reviewed source output already exists")
        shutil.copyfile(source, target)
    prior = copy.copy(world.get_settings())
    settings = copy.copy(prior)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / signal.RATE_HZ
    actors, sensors = [], []
    try:
        world.apply_settings(settings)
        actual = world.get_settings()
        signal.require(actual.synchronous_mode is True and
                       abs(actual.fixed_delta_seconds - .05) <= 1e-9,
                       "Native synchronous 20 Hz readback failed")
        ego, other = operator.construct(world, site, case.name)
        actors = [ego, other]
        signal.require(all(getattr(actor, "is_alive", False) and
                           getattr(actor, "type_id", "").startswith("vehicle.")
                           for actor in actors) and ego.id != other.id,
                       "distinct live Native motor vehicles required")
        cameras, sensors = operator.cameras(world, ego, signal.VIEWS)
        signal.require(set(cameras) == set(signal.VIEWS) and
                       all(callable(cameras[view]) for view in signal.VIEWS),
                       "four original camera callbacks missing")
        ego_rows, other_rows, frame_map = [], [], []
        start_time = last_frame = None
        for index in range(signal.FULL_FRAMES):
            operator.control(ego, other, site, case.name, brake_distance_m)
            frame = world.tick()
            snapshot = world.get_snapshot()
            now = float(snapshot.timestamp.elapsed_seconds)
            signal.require(type(frame) is int and snapshot.frame == frame and
                           (last_frame is None or frame == last_frame + 1),
                           "Native original frame discontinuity")
            if start_time is None:
                start_time = now
            time_s = round(index / signal.RATE_HZ, 5)
            signal.require(abs(now - start_time - time_s) <= .005,
                           "Native 20 Hz timestamp discontinuity")
            last_frame = frame
            observed = operator.observe(world, ego, other, frame, site)
            signal.require(observed.get("source_frame_id") == frame and
                           str(observed.get("ego_actor_id")) == str(ego.id) and
                           str(observed.get("other_actor_id")) == str(other.id) and
                           observed.get("road_id") == site["road_id"] and
                           observed.get("lane_id") == site["lane_id"] and
                           observed.get("signal_id") == site["signal_id"],
                           "original Native actor/signal/lane readback mismatch")
            signal.require(type(observed.get("other_cleared_conflict_zone")) is bool and
                           type(observed.get("physical_occluder_present")) is bool and
                           observed["physical_occluder_present"],
                           "original conflict clearance or physical occluder readback missing")
            head_states = observed.get("governing_head_operating")
            signal.require(isinstance(head_states, dict) and
                           set(head_states) == set(site["governing_head_ids"]) and
                           all(type(value) is bool for value in head_states.values()) and
                           observed.get("signal_operating") is any(head_states.values()),
                           "complete governing signal head readback missing")
            erow = _actor_row(ego, observed["ego_front_station_m"], frame,
                              time_s, site)
            erow.update({"vehicle_id": site["ego_vehicle_id"],
                         "signal_id": site["signal_id"],
                         "approach_id": site["governed_approach"],
                         "signal_installed": observed["signal_installed"],
                         "signal_uncovered": observed["signal_uncovered"],
                         "signal_operating": observed["signal_operating"],
                         "governing_head_operating": head_states,
                         "all_heads_wholly_inoperative": not any(head_states.values())})
            orow = _actor_row(other, observed["other_front_station_m"], frame,
                              time_s, site)
            orow.update({"vehicle_id": site["other_vehicle_id"],
                         "signal_id": site["signal_id"],
                         "within_intersection": observed["other_within_intersection"],
                         "cleared_conflict_zone": observed["other_cleared_conflict_zone"]})
            ego_rows.append(erow)
            other_rows.append(orow)
            frame_map.append({"frame_index": index, "native_frame": frame,
                              "time_s": time_s})
            for view in signal.VIEWS:
                image = cameras[view](frame)
                signal.require(type(image) is bytes and image,
                               "original RGB frame missing: " + view)
                directory = root / "cameras" / view
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{frame:06d}.png").write_bytes(image)
        signal.require(hashlib.sha256(operator.map_bytes(world)).hexdigest() ==
                       site["map_sha256"], "Native map changed during capture")
        measured = signal.measure_original(site, site_path, case,
                                           ego_rows, other_rows)
        sources = {"site": _save(root, "site.json", site),
                   "ego_history": _save(root, "ego-history.json", ego_rows),
                   "other_history": _save(root, "other-history.json", other_rows),
                   "frame_map": _save(root, "frame-map.json", frame_map)}
        _save(root, "inventory.json", {
            "case_id": signal.ASSIGNMENT + "__" + case.name,
            "source_kind": "original_native", "frame_count": signal.FULL_FRAMES,
            "camera_views": list(signal.VIEWS),
            "reviewed_site_sha256": hashlib.sha256(Path(site_path).read_bytes()).hexdigest(),
            "sources": sources})
        return measured
    finally:
        for sensor in reversed(sensors):
            try:
                if hasattr(sensor, "stop"):
                    sensor.stop()
            finally:
                sensor.destroy()
        for actor in reversed(actors):
            if getattr(actor, "is_alive", False):
                actor.destroy()
        world.apply_settings(prior)
        restored = world.get_settings()
        signal.require(restored.synchronous_mode == prior.synchronous_mode and
                       restored.fixed_delta_seconds == prior.fixed_delta_seconds,
                       "Native settings restoration readback failed")
