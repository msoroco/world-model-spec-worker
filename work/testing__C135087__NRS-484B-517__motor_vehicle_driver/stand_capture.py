"""Original-frame CARLA source capture for the C135087 taxicab stand branch.

The observer must read loading, entrant and access state from the live scene.
Authored case modes are never copied into observations. Camera files must be
captured separately and remain subject to the pinned full media decoder.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from stand import SourceError, audit_saved_attempt


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
OBSERVED = ("passenger_loading_active", "entrant_waiting",
            "entrant_about_to_enter", "access_obstructed")


def _speed(actor):
    v = actor.get_velocity()
    values = (float(v.x), float(v.y), float(v.z))
    if not all(math.isfinite(x) for x in values):
        raise SourceError("nonfinite live actor velocity")
    return math.sqrt(sum(x * x for x in values))


def _pose(actor):
    transform = actor.get_transform()
    location = transform.location
    position = {key: float(getattr(location, key)) for key in ("x", "y", "z")}
    heading = float(transform.rotation.yaw)
    if not all(math.isfinite(value) for value in (*position.values(), heading)):
        raise SourceError("nonfinite live subject pose")
    return position, heading


def _write(root, name, value):
    path = root / name
    if path.exists():
        raise SourceError("refusing to overwrite original source: " + name)
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    path.write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}


def capture(world, actors, observer, case_id, map_name, output,
            frame_count=900, step=None, camera_finalize=None):
    """Tick a synchronous world and seal actor rows with existing camera files.

    `actors` maps subject/entrant/passenger to live CARLA actors. `observer`
    receives the snapshot and actors and returns four readback booleans. A
    controller may be supplied as `step(world, actors, index)` before each tick.
    """
    if type(frame_count) is not int or frame_count != 900:
        raise SourceError("full capture requires 900 original frames")
    if set(actors) != {"subject", "entrant", "passenger"}:
        raise SourceError("all three live participants required")
    ids = [actor.id for actor in actors.values()]
    if any(type(i) not in (int, str) or not i for i in ids) or len(set(ids)) != 3:
        raise SourceError("live participant identities are absent or duplicate")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-9:
        raise SourceError("live world must use synchronous 20 Hz")
    if world.get_map().name != map_name:
        raise SourceError("live map name differs from reviewed site")
    root = Path(output)
    if not root.is_dir():
        raise SourceError("capture output directory with four cameras required")
    if camera_finalize is None:
        for name in CAMERAS:
            camera = root / (name + ".mkv")
            if camera.is_symlink() or not camera.is_file() or not camera.stat().st_size:
                raise SourceError("missing original camera source: " + name)
    rows, frame_map = [], []
    previous = None
    for index in range(frame_count):
        if step is not None:
            step(world, actors, index)
        tick_frame = world.tick()
        snapshot = world.get_snapshot()
        frame, time_s = snapshot.frame, float(snapshot.timestamp.elapsed_seconds)
        if type(frame) is not int or frame != tick_frame or not math.isfinite(time_s):
            raise SourceError("original tick/snapshot frame or clock differs")
        if previous is not None and (frame != previous[0] + 1 or
                                     not .049 <= time_s - previous[1] <= .051):
            raise SourceError("original snapshot is not contiguous 20 Hz")
        previous = frame, time_s
        readback = observer(snapshot, actors)
        if not isinstance(readback, dict) or set(readback) != set(OBSERVED) or any(
                type(readback[key]) is not bool for key in OBSERVED):
            raise SourceError("live loading/entrant/access readback is incomplete")
        row = {"frame": frame, "time_s": time_s, "case_id": case_id,
               "map_name": map_name, "subject_id": actors["subject"].id,
               "entrant_id": actors["entrant"].id,
               "passenger_id": actors["passenger"].id,
               "subject_speed_mps": _speed(actors["subject"]),
               "entrant_speed_mps": _speed(actors["entrant"]), **readback}
        row["position"], row["heading_deg"] = _pose(actors["subject"])
        rows.append(row)
        frame_map.append({"frame": frame, "time_s": time_s})
    if camera_finalize is not None:
        camera_finalize()
    camera_refs = {}
    for name in CAMERAS:
        camera = root / (name + ".mkv")
        if camera.is_symlink() or not camera.is_file() or not camera.stat().st_size:
            raise SourceError("missing original camera source: " + name)
        camera_refs[name] = {"path": camera.name,
                             "sha256": hashlib.sha256(camera.read_bytes()).hexdigest(),
                             "frame_count": frame_count, "fps": 20}
    attempt = {"source_format": "native_original", "frame_count": frame_count,
               "fps": 20, "case_id": case_id, "map_name": map_name,
               "subject_id": actors["subject"].id,
               "entrant_id": actors["entrant"].id,
               "passenger_id": actors["passenger"].id,
               "first_frame": rows[0]["frame"],
               "actor_rows": _write(root, "actor-rows.json", rows),
               "frame_map": _write(root, "frame-map.json", frame_map),
               "cameras": camera_refs}
    audit_saved_attempt(attempt, root)
    _write(root, "attempt-source.json", attempt)
    trace_path = root / "trace.jsonl"
    if trace_path.exists():
        if trace_path.is_symlink() or not trace_path.is_file():
            raise SourceError("original pipeline trace is not a regular file")
        try:
            trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        except (UnicodeError, ValueError) as error:
            raise SourceError("original pipeline trace is unreadable") from error
        if len(trace) != frame_count:
            raise SourceError("original pipeline trace frame count differs")
        for source, row in zip(trace, rows):
            if (source.get("frame") != row["frame"] or
                    abs(float(source.get("time_s", float("nan"))) - row["time_s"]) > 1e-4 or
                    source.get("position_m") != [row["position"][key] for key in ("x", "y", "z")]):
                raise SourceError("original pipeline trace differs from actor capture")
    else:
        trace_path.write_text("".join(json.dumps({
            "frame": row["frame"], "time_s": row["time_s"],
            "position": row["position"], "heading_deg": row["heading_deg"],
            "position_m": [row["position"][key] for key in ("x", "y", "z")],
            "speed_mps": row["subject_speed_mps"],
            "speed_mph": row["subject_speed_mps"] / .44704}) + "\n" for row in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
        for i, row in enumerate(rows)))
    return attempt
