"""Lazy 20 Hz original capture for the reviewed LVMC grade crossing.

The operator supplies live CARLA objects and reviewed site sources. All labels
below come from readers at the original world frame; targets never enter the
measurement. Capture writes separate original frame, ray and camera sources.
"""
from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path

from rail_sight_measurement import measure, read_reviewed_site

CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
FRAME_FIELDS = ("original_frame", "time_s", "route_station_m", "speed_mps",
                "body_on_crossing", "flagman_on_duty", "signal_installed",
                "signal_clearly_visible", "signal_immediate_train_approach")
RAY_FIELDS = ("crossing", "rail_minus_400ft", "rail_plus_400ft")


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def _write_source(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _encoded(value)
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def _bind_packet(root, packet):
    """Seal the exact reviewed input packet alongside the original attempt."""
    relative = "reviewed-rail-packet.json"
    path = root / relative
    raw = _encoded(packet)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError("reviewed rail packet changed")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def capture(*, case_id, packet, world, ego, route_reader, ray_reader,
            exception_reader, camera_reader, brake, attempt_root,
            before_tick=None, frame_count=900):
    """Capture source-bound frames; fail closed on source or profile gaps.

    route_reader(frame, snapshot, ego) returns station in metres and body
    crossing occupancy from reviewed geometry. ray_reader returns three
    original sight readbacks. exception_reader returns duty/installed/visible/
    indication booleans. camera_reader returns four (frame, PNG bytes) pairs.
    A test may shorten frame_count; the production call must keep 900.
    """
    root = Path(attempt_root).resolve()
    if type(frame_count) is not int or not 3 <= frame_count <= 900:
        raise ValueError("invalid original rail frame count")
    if not root.is_dir() or (root / "native-rail-receipt.json").exists():
        raise ValueError("new reviewed rail attempt directory required")
    road = world.get_map().to_opendrive()
    read_reviewed_site(root, packet, road)
    packet_ref = _bind_packet(root, packet)
    frames = []
    camera_map = []
    try:
        for index in range(frame_count):
            if before_tick is not None:
                before_tick(ego)
            original_frame = world.tick()
            snapshot = world.get_snapshot()
            if (type(original_frame) is not int or
                    snapshot.frame != original_frame or
                    (frames and original_frame != frames[-1]["original_frame"] + 1)):
                raise ValueError("original rail frame join differs")
            time_s = snapshot.timestamp.elapsed_seconds
            if (type(time_s) not in (int, float) or not math.isfinite(time_s) or
                    (frames and not .045 <= time_s - frames[-1]["time_s"] <= .055)):
                raise ValueError("original rail 20 Hz time differs")
            velocity = ego.get_velocity()
            speed_mps = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            location = ego.get_transform().location
            position_xy_m = [location.x, location.y]
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in position_xy_m):
                raise ValueError("original rail ego position invalid")
            route_station_m, body_on_crossing = route_reader(original_frame, snapshot, ego)
            rays = ray_reader(original_frame, snapshot, ego)
            exceptions = exception_reader(original_frame, snapshot, ego)
            if (type(route_station_m) not in (int, float) or
                    not math.isfinite(route_station_m) or
                    type(body_on_crossing) is not bool or
                    not isinstance(rays, dict) or
                    not set(RAY_FIELDS).issubset(rays) or
                    not set(rays).issubset(set(RAY_FIELDS) | {"source_trace"}) or
                    any(type(rays[key]) is not bool for key in RAY_FIELDS) or
                    not isinstance(exceptions, dict) or
                    not set(FRAME_FIELDS[5:]).issubset(exceptions) or
                    not set(exceptions).issubset(set(FRAME_FIELDS[5:]) | {"source_trace"}) or
                    any(type(exceptions[key]) is not bool for key in FRAME_FIELDS[5:])):
                raise ValueError("original rail route, sight or exception readback invalid")
            frame = {"original_frame": original_frame, "time_s": time_s,
                     "route_station_m": route_station_m, "speed_mps": speed_mps,
                     "position_xy_m": position_xy_m,
                     "body_on_crossing": body_on_crossing,
                     **{key: exceptions[key] for key in FRAME_FIELDS[5:]}}
            if "source_trace" in exceptions:
                frame["exception_source_trace"] = exceptions["source_trace"]
            frame_ref = _write_source(root, f"original-frames/{original_frame:08d}.json", frame)
            ray_ref = _write_source(root, f"original-rays/{original_frame:08d}.json",
                                    {"frame": original_frame, **rays})
            images = camera_reader(original_frame, snapshot)
            if not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("all four original rail cameras required")
            camera_row = {"original_frame": original_frame, "sources": {}}
            for name, size in CAMERAS.items():
                item = images[name]
                if not isinstance(item, tuple) or len(item) != 2 or item[0] != original_frame:
                    raise ValueError("original rail camera frame join differs")
                raw = item[1]
                if not isinstance(raw, bytes):
                    raise ValueError("original rail camera PNG missing")
                from PIL import Image
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG" or image.size != size:
                        raise ValueError("original rail camera profile differs")
                    image.load()
                relative = f"original-cameras/{name}/{original_frame:08d}.png"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
                camera_row["sources"][name] = {
                    "path": relative, "sha256": hashlib.sha256(raw).hexdigest()}
            camera_map.append(camera_row)
            frames.append({**frame,
                           "sight_crossing_clear": rays["crossing"],
                           "sight_rail_negative_400ft_clear": rays["rail_minus_400ft"],
                           "sight_rail_positive_400ft_clear": rays["rail_plus_400ft"],
                           "frame_source_path": frame_ref["path"],
                           "frame_source_sha256": frame_ref["sha256"],
                           "sight_source_path": ray_ref["path"],
                           "sight_source_sha256": ray_ref["sha256"]})
        if frame_count != 900:
            return {"test_capture_only": True, "frame_count": frame_count,
                    "camera_count": len(camera_map)}
        measurement = measure(root, packet, road, frames)
        frame_ref = _write_source(root, "native-rail-frames.json", frames)
        camera_ref = _write_source(root, "native-rail-camera-map.json", camera_map)
        receipt = {"case_id": case_id, "capture_kind": "original_native",
                   "fps": 20, "duration_s": 45, "frame_count": 900,
                   "packet": packet_ref, "frames": frame_ref, "camera_map": camera_ref,
                   "measurement": measurement, "legal_conclusion": None}
        _write_source(root, "native-rail-receipt.json", receipt)
        return receipt
    finally:
        brake(ego)
