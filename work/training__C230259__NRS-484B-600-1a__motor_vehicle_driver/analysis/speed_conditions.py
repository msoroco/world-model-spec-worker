"""Source-shaped speed/conditions measurement for NRS 484B.600(1)(a).

This module measures physical quantities only. It never decides whether a
speed is reasonable or proper, and synthetic samples prove only the CPU path.
"""
from math import isfinite, sqrt

CAMERAS = ("front", "rear", "left", "right")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("missing or nonfinite " + name)
    return float(value)


def measure(frames, *, source_kind, rate_hz=20, minimum_seconds=30):
    """Check frame joins and retain measured speed with contemporaneous context.

    `frames` comes from original Native state plus four camera frame maps. The
    fixture label `synthetic_native_sample` cannot be promoted as Native proof.
    """
    if source_kind not in ("original_native", "synthetic_native_sample"):
        raise ValueError("undeclared source kind")
    if rate_hz != 20 or minimum_seconds < 30:
        raise ValueError("capture contract requires 20 Hz and at least 30 seconds")
    if len(frames) < rate_hz * minimum_seconds:
        raise ValueError("capture shorter than minimum frame count")
    speeds = []
    participant_counts = []
    first_time = None
    previous_time = None
    for index, frame in enumerate(frames):
        frame_id = frame.get("frame_id")
        if not isinstance(frame_id, int) or frame_id != index:
            raise ValueError("nonconsecutive Native frame map")
        time = _finite(frame.get("sim_time_s"), "sim_time_s")
        if first_time is None:
            first_time = time
        if previous_time is not None and abs((time - previous_time) - 1 / rate_hz) > 1e-5:
            raise ValueError("Native frame timing gap")
        previous_time = time
        camera_frames = frame.get("camera_frames")
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
            raise ValueError("missing four source-camera frame joins")
        if any(camera_frames[name] != frame_id for name in CAMERAS):
            raise ValueError("source-camera frame mismatch")
        velocity = frame.get("ego_velocity_mps")
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("missing original ego velocity vector")
        speed = sqrt(sum(_finite(part, "ego velocity component") ** 2 for part in velocity))
        participants = frame.get("participants")
        if not isinstance(participants, list) or not participants:
            raise ValueError("missing contemporaneous traffic")
        if len({item.get("id") for item in participants if isinstance(item, dict)}) != len(participants):
            raise ValueError("duplicate or malformed traffic identity")
        for participant in participants:
            if not isinstance(participant, dict) or not participant.get("id"):
                raise ValueError("missing traffic identity")
            vector = participant.get("velocity_mps")
            if not isinstance(vector, list) or len(vector) != 3:
                raise ValueError("missing traffic velocity vector")
            for component in vector:
                _finite(component, "traffic velocity component")
        width = _finite(frame.get("lane_width_m"), "lane_width_m")
        if width <= 0:
            raise ValueError("nonpositive roadway width")
        surface = frame.get("surface")
        weather = frame.get("weather")
        if not isinstance(surface, dict) or not surface.get("kind"):
            raise ValueError("missing road surface context")
        if not isinstance(weather, dict) or not {"precipitation", "visibility_m"} <= set(weather):
            raise ValueError("missing weather or visibility context")
        _finite(weather["precipitation"], "precipitation")
        _finite(weather["visibility_m"], "visibility_m")
        speeds.append(speed)
        participant_counts.append(len(participants))
    duration = previous_time - first_time + 1 / rate_hz
    if duration + 1e-5 < minimum_seconds:
        raise ValueError("capture shorter than minimum duration")
    return {
        "format": "speed-conditions-measurement-v1",
        "source_kind": source_kind,
        "frame_count": len(frames),
        "duration_s": round(duration, 5),
        "ego_speed_mps": {"minimum": min(speeds), "maximum": max(speeds),
                          "mean": sum(speeds) / len(speeds)},
        "traffic_count": {"minimum": min(participant_counts), "maximum": max(participant_counts)},
        "condition_join_complete": True,
        "legal_judgment": "unresolved",
    }
