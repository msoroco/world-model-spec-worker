"""Capture source-bound original two-vehicle roundabout motion at 20 Hz.

The caller owns the world, actors and sensors. These original geometry rows are
measurements, not a traffic-gap threshold or legal right-of-way determination.
"""

from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from native_roundabout import load_case
from roundabout_measurements import ASSIGNMENT_ID

CAMERAS = ("overview", "approach", "entry_conflict", "driver_reference")
CAMERA_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                     "entry_conflict": (1280, 720), "driver_reference": (1280, 720)}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _vertices(reader, actor):
    points = reader(actor)
    if not isinstance(points, list) or len(points) != 8:
        raise ValueError("eight original body vertices required")
    for point in points:
        if (not isinstance(point, list) or len(point) != 3 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in point)):
            raise ValueError("finite original body vertex required")
    return points


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
        image.load()
    return payload


def capture(world, ego, opponent, map_path, map_sha256, case_id, output_dir,
            ego_control, opponent_control, body_reader, brake,
            *, ticks=900, camera_readers=None, camera_dimensions=None):
    """Write complete trace and receipt only after all source frames pass."""
    packet = load_case(map_path, map_sha256, case_id)
    if (not isinstance(ticks, int) or ticks < 2 or
            not all(callable(fn) for fn in (ego_control, opponent_control,
                                            body_reader, brake))):
        raise ValueError("complete capture callbacks and tick count required")
    settings = world.get_settings()
    if (not settings.synchronous_mode or
            abs(settings.fixed_delta_seconds - .05) > 1e-9):
        raise ValueError("original world must be synchronous at 20 Hz")
    if world.get_map().name != packet["map_name"]:
        raise ValueError("original world map differs")
    if not isinstance(ego.id, int) or not isinstance(opponent.id, int) or ego.id == opponent.id:
        raise ValueError("distinct original actor identities required")
    output = Path(output_dir)
    trace = output / "original-trace.jsonl"
    receipt = output / "source-receipt.json"
    if trace.exists() or receipt.exists():
        raise ValueError("original roundabout output exists")
    dimensions = camera_dimensions or CAMERA_DIMENSIONS
    if camera_readers is not None and (set(camera_readers) != set(CAMERAS) or
                                       set(dimensions) != set(CAMERAS)):
        raise ValueError("four named original camera readers and dimensions required")
    media_paths = {name: output / ("original-" + name + ".png.zip")
                   for name in CAMERAS} if camera_readers is not None else {}
    if any(path.exists() for path in media_paths.values()):
        raise ValueError("original camera output exists")
    rows = []
    prior = None
    output.mkdir(parents=True, exist_ok=True)
    archives = {name: ZipFile(path, "w", compression=ZIP_STORED)
                for name, path in media_paths.items()}
    try:
        for index in range(ticks):
            ego_control(ego, index)
            opponent_control(opponent, index)
            tick_frame = world.tick()
            snapshot = world.get_snapshot()
            frame = snapshot.frame
            time_s = float(snapshot.timestamp.elapsed_seconds)
            if (type(frame) is not int or frame != tick_frame or
                    not math.isfinite(time_s) or
                    (prior is not None and
                     (frame != prior[0] + 1 or abs(time_s - prior[1] - .05) > .002))):
                raise ValueError("original 20 Hz frame/time discontinuity")
            speeds = []
            for actor in (ego, opponent):
                velocity = actor.get_velocity()
                speed = math.sqrt(sum(float(getattr(velocity, axis)) ** 2
                                      for axis in ("x", "y", "z")))
                if not math.isfinite(speed):
                    raise ValueError("nonfinite original vehicle speed")
                speeds.append(speed)
            row = {"frame": frame, "time_s": time_s,
                         "ego_actor_id": ego.id, "opponent_actor_id": opponent.id,
                         "ego_vertices": _vertices(body_reader, ego),
                         "opponent_vertices": _vertices(body_reader, opponent),
                         "ego_speed_mps": speeds[0],
                         "opponent_speed_mps": speeds[1]}
            if camera_readers is not None:
                row["camera_frames"] = {}
                for name in CAMERAS:
                    payload = _camera_image(camera_readers[name], frame, dimensions[name])
                    member = f"{frame:08d}.png"
                    archives[name].writestr(member, payload)
                    row["camera_frames"][name] = {"member": member,
                        "sha256": hashlib.sha256(payload).hexdigest()}
            rows.append(row)
            prior = frame, time_s
    except Exception:
        for actor in (ego, opponent):
            try:
                brake(actor)
            except Exception:
                pass
        raise
    finally:
        for archive in archives.values():
            archive.close()
        if len(rows) != ticks:
            for path in media_paths.values():
                path.unlink(missing_ok=True)
    trace_bytes = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    trace.write_bytes(trace_bytes)
    receipt.write_text(json.dumps({"assignment_id": ASSIGNMENT_ID,
        "case_id": case_id, "diagnostic_fixture": ticks != 900, "fps": 20,
        "frame_count": ticks, "map_sha256": map_sha256,
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "ego_actor_id": ego.id, "opponent_actor_id": opponent.id,
        "camera_capture_complete": camera_readers is not None,
        "camera_sources": {name: {"path": path.name, "sha256": _sha(path),
            "frame_count": ticks, "dimensions": list(dimensions[name])}
            for name, path in media_paths.items()}},
        sort_keys=True) + "\n", encoding="utf-8")
    return {"trace": str(trace), "receipt": str(receipt),
            "trace_sha256": _sha(trace), "receipt_sha256": _sha(receipt)}
