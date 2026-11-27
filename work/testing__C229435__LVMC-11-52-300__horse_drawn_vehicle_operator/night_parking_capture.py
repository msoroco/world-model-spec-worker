"""Original 20 Hz Native tick capture for both parking-cell vehicles."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo


def utc_start(civil_date, local_time, zone="America/Los_Angeles"):
    value = dt.datetime.fromisoformat(civil_date + "T" + local_time)
    if value.tzinfo is not None:
        raise ValueError("reviewed civil date/time must be local naive fields")
    return value.replace(tzinfo=ZoneInfo(zone)).astimezone(dt.timezone.utc)


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    body = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if len(body) < 4 or any(not math.isfinite(value) for point in body for value in point):
        raise ValueError("original complete Native body unavailable")
    return body


def _state(actor, *, parked=None, on_street=None):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    result = {
        "body_vertices_xy_m": _body(actor),
        "center_xy_m": [float(transform.location.x), float(transform.location.y)],
        "speed_m_s": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
    }
    if parked is not None:
        result.update(parked=bool(parked), on_street=bool(on_street))
    return result


def capture_ticks(world, subject, other, pipeline, cameras, frame_map, output,
                  *, frame_count, civil_start_utc, subject_on_street, subject_parked,
                  diagnostic=False):
    """Retain every world tick, original body and exact video frame identity.

    `subject_on_street` must inspect the current world body against the reviewed
    street polygon. `diagnostic` permits a small fake CPU fixture only.
    """
    output = Path(output).resolve()
    if ".runtime-work" not in output.parts or not output.is_dir():
        raise ValueError("original acquisition must stay under .runtime-work")
    if type(frame_count) is not int or frame_count < 2:
        raise ValueError("full episode needs at least two 20 Hz ticks")
    if not diagnostic and frame_count < 35981:
        raise ValueError("full nighttime duration construction is incomplete")
    if civil_start_utc.tzinfo is None:
        raise ValueError("reviewed civil UTC start required")
    first_time = None
    prior_frame = None
    previous_sim_time = None
    with (output / "night-parking-trace.jsonl").open("x", buffering=1) as details, \
         (output / "trace.jsonl").open("x", buffering=1) as generic:
        for index in range(frame_count):
            native_frame = world.tick()
            snap = world.get_snapshot()
            if type(native_frame) is not int or snap.frame != native_frame or (prior_frame is not None and native_frame != prior_frame + 1):
                raise ValueError("Native world tick identity discontinuity")
            native_time = float(snap.timestamp.elapsed_seconds)
            if not math.isfinite(native_time) or (previous_sim_time is not None and not math.isclose(native_time - previous_sim_time, .05, abs_tol=.001)):
                raise ValueError("Native world did not advance at 20 Hz")
            if first_time is None:
                first_time = native_time
            previous_sim_time = native_time
            prior_frame = native_frame
            subject_state = _state(subject, parked=subject_parked(index, subject),
                                   on_street=subject_on_street(subject))
            other_state = _state(other)
            civil_time = civil_start_utc + dt.timedelta(seconds=index / 20)
            detail = {"frame": native_frame, "utc_time": civil_time.isoformat(),
                      "subject": subject_state, "other_vehicle": other_state}
            details.write(json.dumps(detail, allow_nan=False) + "\n")
            position = subject.get_transform().location
            generic.write(json.dumps({"frame": native_frame, "time_s": native_time - first_time,
                                      "position": {"x": float(position.x), "y": float(position.y), "z": float(position.z)},
                                      "heading_deg": float(subject.get_transform().rotation.yaw),
                                      "speed_mps": subject_state["speed_m_s"]}, allow_nan=False) + "\n")
            frame_map.append(native_frame, native_time - first_time)
            pipeline.capture(native_frame, native_time)
            cameras.append(native_frame)
    return {"frames": frame_count, "first_native_frame": prior_frame - frame_count + 1,
            "last_native_frame": prior_frame, "civil_start_utc": civil_start_utc.isoformat(),
            "civil_end_utc": (civil_start_utc + dt.timedelta(seconds=(frame_count - 1) / 20)).isoformat(),
            "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}
