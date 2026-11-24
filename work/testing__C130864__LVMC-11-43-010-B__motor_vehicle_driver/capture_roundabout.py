"""Capture source-bound original two-vehicle roundabout motion at 20 Hz.

The caller owns the world, actors and sensors. These original geometry rows are
measurements, not a traffic-gap threshold or legal right-of-way determination.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_roundabout import load_case
from roundabout_measurements import ASSIGNMENT_ID


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


def capture(world, ego, opponent, map_path, map_sha256, case_id, output_dir,
            ego_control, opponent_control, body_reader, brake,
            *, ticks=900):
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
    rows = []
    prior = None
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
            rows.append({"frame": frame, "time_s": time_s,
                         "ego_actor_id": ego.id, "opponent_actor_id": opponent.id,
                         "ego_vertices": _vertices(body_reader, ego),
                         "opponent_vertices": _vertices(body_reader, opponent),
                         "ego_speed_mps": speeds[0],
                         "opponent_speed_mps": speeds[1]})
            prior = frame, time_s
    except Exception:
        for actor in (ego, opponent):
            try:
                brake(actor)
            except Exception:
                pass
        raise
    output.mkdir(parents=True, exist_ok=True)
    trace_bytes = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
    trace.write_bytes(trace_bytes)
    receipt.write_text(json.dumps({"assignment_id": ASSIGNMENT_ID,
        "case_id": case_id, "diagnostic_fixture": ticks != 900, "fps": 20,
        "frame_count": ticks, "map_sha256": map_sha256,
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "ego_actor_id": ego.id, "opponent_actor_id": opponent.id},
        sort_keys=True) + "\n", encoding="utf-8")
    return {"trace": str(trace), "receipt": str(receipt),
            "trace_sha256": _sha(trace), "receipt_sha256": _sha(receipt)}
