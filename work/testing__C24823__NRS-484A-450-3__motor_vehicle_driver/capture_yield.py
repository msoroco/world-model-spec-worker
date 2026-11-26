"""Capture 900 original 20 Hz yield-approach samples and four PNG frame streams."""
from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from yield_site import ASSIGNMENT as ASSIGNMENT_ID, select_stop_reference
from yield_source import CAMERAS, DIMENSIONS, sha


def _camera_image(reader, frame, dimensions):
    sample = reader(frame)
    if not isinstance(sample, dict) or sample.get("frame") != frame:
        raise ValueError("original camera frame identity mismatch")
    payload = sample.get("png_bytes")
    if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("original camera PNG missing")
    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        if image.format != "PNG" or image.size != tuple(dimensions):
            raise ValueError("original camera dimensions mismatch")
    return payload


def capture(world, ego, packet_path, packet_sha, case_id, output_dir, control,
            body_reader, brake, *, ticks=900, camera_readers, after_tick=None,
            control_readback=None, before_tick=None, traffic_readback=None):
    packet_path = Path(packet_path)
    if sha(packet_path) != packet_sha:
        raise ValueError("original yield site packet changed")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    select_stop_reference(packet_path)
    if packet.get("case_id") != case_id:
        raise ValueError("original yield case mismatch")
    if (type(ticks) is not int or ticks != 900 or not all(callable(fn) for fn in
            (control, body_reader, brake, control_readback, before_tick, traffic_readback)) or
            set(camera_readers) != set(CAMERAS)):
        raise ValueError("complete 900-tick original acquisition callbacks required")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-9:
        raise ValueError("original world must be synchronous at 20 Hz")
    if world.get_map().name != packet["map_name"] or not ego.type_id.startswith("vehicle."):
        raise ValueError("live original map or motor vehicle mismatch")
    output = Path(output_dir)
    trace = output / "original-yield-trace.jsonl"
    receipt = output / "original-yield-receipt.json"
    media = {name: output / ("original-" + name + ".png.zip") for name in CAMERAS}
    if any(path.exists() for path in (trace, receipt, *media.values())):
        raise ValueError("fresh original capture output required")
    output.mkdir(parents=True, exist_ok=True)
    archives = {name: ZipFile(path, "w", compression=ZIP_STORED) for name, path in media.items()}
    rows = []
    previous = None
    try:
        for index in range(ticks):
            control(ego, index)
            before_tick(index)
            tick_frame = world.tick()
            snap = world.get_snapshot()
            frame, time_s = snap.frame, float(snap.timestamp.elapsed_seconds)
            if (type(frame) is not int or frame != tick_frame or not math.isfinite(time_s) or
                    previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > .002)):
                raise ValueError("original 20 Hz frame order changed")
            transform = ego.get_transform()
            center = [float(transform.location.x), float(transform.location.y)]
            yaw = math.radians(float(transform.rotation.yaw))
            heading = [math.cos(yaw), math.sin(yaw)]
            waypoint = world.get_map().get_waypoint(transform.location, project_to_road=False)
            if waypoint is None:
                raise ValueError("original live circulation lane missing")
            lane_id = str(waypoint.road_id) + ":" + str(waypoint.lane_id)
            vertices = body_reader(ego)
            if not isinstance(vertices, list) or len(vertices) != 8 or any(
                    not isinstance(point, list) or len(point) != 3 or any(
                        type(value) not in (int, float) or not math.isfinite(value)
                        for value in point) for point in vertices):
                raise ValueError("eight finite original world-space body vertices required")
            velocity = ego.get_velocity()
            speed = math.sqrt(sum(float(getattr(velocity, axis)) ** 2 for axis in ("x", "y", "z")))
            source_control = control_readback(frame)
            if (not isinstance(source_control, dict) or
                    source_control.get("yield_sign_id") != packet["yield_sign_id"] or
                    source_control.get("control") != "yield_sign" or
                    not source_control.get("live_actor_id")):
                raise ValueError("original live yield-sign control readback differs")
            traffic = traffic_readback(frame)
            if (not isinstance(traffic, list) or len(traffic) != len(packet["approaching_traffic_points"]) or
                    any(not item.get("actor_id") or item.get("source_frame_id") != frame or
                        not item.get("position_xy_m") or not item.get("velocity_xy_mps")
                        for item in traffic)):
                raise ValueError("original approaching traffic actor readback differs")
            row = {"frame": frame, "time_s": time_s, "ego_actor_id": ego.id,
                   "ego_center_xy_m": center, "ego_lane_id": lane_id,
                   "ego_vertices": vertices, "ego_speed_mps": speed,
                   "yield_control_readback": source_control,
                   "approaching_traffic_readback": traffic, "camera_frames": {}}
            for name in CAMERAS:
                payload = _camera_image(camera_readers[name], frame, DIMENSIONS[name])
                member = f"{frame:08d}.png"
                archives[name].writestr(member, payload)
                row["camera_frames"][name] = {"member": member,
                    "sha256": hashlib.sha256(payload).hexdigest()}
            if after_tick is not None:
                after_tick(frame, time_s, row)
            rows.append(row)
            previous = (frame, time_s)
    except BaseException:
        try:
            brake(ego)
        except Exception:
            pass
        raise
    finally:
        for archive in archives.values():
            archive.close()
        if len(rows) != ticks:
            for path in media.values():
                path.unlink(missing_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    trace.write_bytes(payload)
    receipt.write_text(json.dumps({"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
        "diagnostic_fixture": False, "fps": 20, "frame_count": ticks,
        "site_sha256": packet_sha, "trace_sha256": hashlib.sha256(payload).hexdigest(),
        "ego_actor_id": ego.id, "camera_capture_complete": True,
        "camera_sources": {name: {"path": path.name, "sha256": sha(path),
            "frame_count": ticks, "dimensions": list(DIMENSIONS[name])}
            for name, path in media.items()}}, sort_keys=True) + "\n", encoding="utf-8")
    return {"trace": str(trace), "receipt": str(receipt),
            "trace_sha256": sha(trace), "receipt_sha256": sha(receipt)}
