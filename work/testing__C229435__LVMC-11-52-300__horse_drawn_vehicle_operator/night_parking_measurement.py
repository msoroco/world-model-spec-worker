"""Measure original parking episodes; leave statutory classification to review."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

FPS = 20
NIGHT_START = dt.time(1, 0)
NIGHT_END = dt.time(6, 0)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_sealed(path, expected_sha):
    if _sha(path) != expected_sha:
        raise ValueError("source SHA256 mismatch")
    return json.loads(Path(path).read_text())


def _local_midnight(day, tz):
    return dt.datetime.combine(day, dt.time(0), tzinfo=tz)


def night_overlap_seconds(start_utc, end_utc, zone):
    """Return measured intersection with each local 01:00–06:00 interval."""
    if start_utc.tzinfo is None or end_utc.tzinfo is None or end_utc <= start_utc:
        raise ValueError("ordered timezone-aware episode endpoints required")
    tz = ZoneInfo(zone)
    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    day = start_local.date() - dt.timedelta(days=1)
    last = end_local.date() + dt.timedelta(days=1)
    total = 0.0
    while day <= last:
        midnight = _local_midnight(day, tz)
        window_start = midnight.replace(hour=1).astimezone(dt.timezone.utc)
        window_end = midnight.replace(hour=6).astimezone(dt.timezone.utc)
        total += max(0.0, (min(end_utc, window_end) - max(start_utc, window_start)).total_seconds())
        day += dt.timedelta(days=1)
    return total


def measure(source_dir, contract):
    """Read hash-bound original frame/state and independent context sources."""
    source_dir = Path(source_dir)
    files = contract["sources"]
    context = _read_sealed(source_dir / files["context"]["path"], files["context"]["sha256"])
    classification = _read_sealed(source_dir / files["classification"]["path"], files["classification"]["sha256"])
    activity = _read_sealed(source_dir / files["activity"]["path"], files["activity"]["sha256"])
    trace_path = source_dir / files["trace"]["path"]
    if _sha(trace_path) != files["trace"]["sha256"]:
        raise ValueError("original trace SHA256 mismatch")
    frame_map_path = source_dir / files["frame_map"]["path"]
    if _sha(frame_map_path) != files["frame_map"]["sha256"]:
        raise ValueError("original frame map SHA256 mismatch")
    if context.get("iana_timezone") != "America/Los_Angeles" or not context.get("municipal_jurisdiction_source") or not context.get("street_source"):
        raise ValueError("qualifying street and civil timezone sources required")
    if (not all(type(classification.get(key)) is bool for key in
                ("transport_capable", "self_propelled", "vehicle_exclusions_checked")) or
            not classification.get("physical_source")):
        raise ValueError("physical vehicle classification source required")
    if not activity.get("responsible_person_source") or not activity.get("activity_source"):
        raise ValueError("parking activity and responsible person sources required")
    frames = []
    with trace_path.open() as handle:
        for line in handle:
            frames.append(json.loads(line))
    with frame_map_path.open() as handle:
        mapping = [json.loads(line) for line in handle]
    if len(frames) < 2:
        raise ValueError("original frame history too short")
    if len(frames) != len(mapping):
        raise ValueError("original trace/frame count mismatch")
    prior_number = None
    prior_time = None
    for index, frame in enumerate(frames):
        number = frame.get("frame")
        time = frame.get("utc_time")
        if type(number) is not int or not isinstance(time, str):
            raise ValueError("original frame/time identity required")
        instant = dt.datetime.fromisoformat(time.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("UTC frame time must be timezone aware")
        instant = instant.astimezone(dt.timezone.utc)
        mapped = mapping[index]
        if (mapped.get("carla_frame") != number or mapped.get("video_frame") != index or
                type(mapped.get("time_s")) not in (int, float) or
                not math.isclose(mapped["time_s"] - mapping[0]["time_s"], index / FPS, abs_tol=.001)):
            raise ValueError("original video/frame/time join mismatch")
        if prior_number is not None:
            if number != prior_number + 1 or not math.isclose((instant - prior_time).total_seconds(), 1 / FPS, abs_tol=.001):
                raise ValueError("original 20 Hz frame/time discontinuity")
        for actor in ("subject", "other_vehicle"):
            body = frame.get(actor, {}).get("body_vertices_xy_m")
            if not isinstance(body, list) or len(body) < 4 or any(len(point) != 2 for point in body):
                raise ValueError(f"missing original {actor} body")
            if not all(math.isfinite(float(value)) for point in body for value in point):
                raise ValueError(f"nonfinite original {actor} body")
        if type(frame.get("subject", {}).get("on_street")) is not bool or type(frame.get("subject", {}).get("parked")) is not bool:
            raise ValueError("original street/parking state required")
        speed = frame["subject"].get("speed_m_s")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original body speed must be finite and nonnegative")
        prior_number = number
        prior_time = instant
    parked = [index for index, frame in enumerate(frames) if frame["subject"]["on_street"] and frame["subject"]["parked"]]
    if len(parked) < 2 or parked != list(range(parked[0], parked[-1] + 1)):
        raise ValueError("incomplete continuously parked street episode")
    episode = frames[parked[0]:parked[-1] + 1]
    if any(frame["subject"]["speed_m_s"] > .15 for frame in episode):
        raise ValueError("original parked body must have stationary engineering speed")
    start = dt.datetime.fromisoformat(episode[0]["utc_time"].replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    end = dt.datetime.fromisoformat(episode[-1]["utc_time"].replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    initial_body = episode[0]["subject"]["body_vertices_xy_m"]
    if any(max(math.dist(a, b) for a, b in zip(initial_body, frame["subject"]["body_vertices_xy_m"])) > .2 for frame in episode):
        raise ValueError("original parked body displaced beyond engineering stationary tolerance")
    if not activity.get("episode_start_event_source") or not activity.get("episode_end_event_source"):
        raise ValueError("independent parking boundary events required")
    # Endpoint events must correspond to retained original samples, not a narrated target.
    if activity.get("start_frame") != episode[0]["frame"] or activity.get("end_frame") != episode[-1]["frame"]:
        raise ValueError("episode event/frame join mismatch")
    elapsed = (end - start).total_seconds()
    return {
        "first_frame": episode[0]["frame"],
        "last_frame": episode[-1]["frame"],
        "frame_count": len(frames),
        "parked_frame_count": len(episode),
        "elapsed_s": elapsed,
        "night_overlap_s": night_overlap_seconds(start, end, context["iana_timezone"]),
        "start_local": start.astimezone(ZoneInfo(context["iana_timezone"])).isoformat(),
        "end_local": end.astimezone(ZoneInfo(context["iana_timezone"])).isoformat(),
        "subject_body_start_xy_m": initial_body,
        "subject_body_end_xy_m": episode[-1]["subject"]["body_vertices_xy_m"],
        "other_vehicle_body_start_xy_m": episode[0]["other_vehicle"]["body_vertices_xy_m"],
        "other_vehicle_body_end_xy_m": episode[-1]["other_vehicle"]["body_vertices_xy_m"],
        "transport_capable": classification["transport_capable"],
        "self_propelled": classification["self_propelled"],
        "vehicle_exclusions_checked": classification["vehicle_exclusions_checked"],
        "activity": activity.get("activity"),
        "source_hashes": {key: item["sha256"] for key, item in files.items()},
        "legal_conclusion": None,
        "uncertainty": "Statutory endpoint counting, qualification and parking purpose require independent review.",
    }
