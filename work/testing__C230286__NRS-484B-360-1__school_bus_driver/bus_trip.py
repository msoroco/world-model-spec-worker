"""School-bus pupil-trip speed construction and original-frame measurement."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C230286__NRS-484B-360-1__school_bus_driver"
MPH_PER_MPS = 2.2369362920544
LIMIT_MPH = 55.0


def build_profile(target_mph: float, duration_s: float, acceleration_mps2: float = 1.5) -> list[dict]:
    """Build 20 Hz target motion without claiming realized bus speed."""
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (target_mph, duration_s, acceleration_mps2)):
        raise ValueError("finite profile parameters required")
    if target_mph < 0 or duration_s < 1 or acceleration_mps2 <= 0:
        raise ValueError("nonnegative target and positive duration/acceleration required")
    steps = round(duration_s * 20)
    if abs(steps / 20 - duration_s) > 1e-8:
        raise ValueError("duration must align to 20 Hz")
    target_mps = target_mph / MPH_PER_MPS
    speed = 0.0
    profile = []
    for i in range(steps + 1):
        profile.append({"time_s": i / 20, "commanded_speed_mps": speed,
                        "commanded_speed_mph": speed * MPH_PER_MPS})
        speed = min(target_mps, speed + acceleration_mps2 / 20)
    return profile


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    if not packet.get("bus_actor_id") or not packet.get("driver_actor_id"):
        raise ValueError("school bus and driver identity required")
    classification = packet.get("school_bus_classification")
    if not isinstance(classification, dict) or not classification.get("qualifying_definition_branch") or not classification.get("source"):
        raise ValueError("source-backed school-bus definition branch required")
    if classification.get("all_exclusions_reviewed") is not True:
        raise ValueError("all school-bus exclusions require review")
    if packet.get("transport_direction") not in ("to_school", "from_school"):
        raise ValueError("school transportation direction required")
    if not packet.get("transport_source") or not packet.get("sidewalk_source"):
        raise ValueError("transport and sidewalk context sources required")
    if not isinstance(packet.get("pupil_count"), int) or isinstance(packet["pupil_count"], bool) or packet["pupil_count"] < 0:
        raise ValueError("separate pupil count required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original 20 Hz frames required")
    observations = []
    previous = None
    for i, frame in enumerate(frames):
        t, speed = frame.get("time_s"), frame.get("speed_mps")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (t, speed)) or speed < 0:
            raise ValueError("finite nonnegative original speed and time required")
        if previous is not None and not 0 < t - previous <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        previous = t
        if not isinstance(frame.get("transporting_pupils_to_or_from_school"), bool):
            raise ValueError("original transport-phase readback required")
        observations.append({"frame_index": i, "time_s": t, "speed_mps": speed,
                             "speed_mph": speed * MPH_PER_MPS,
                             "transporting_pupils_to_or_from_school": frame["transporting_pupils_to_or_from_school"]})
    active = [o for o in observations if o["transporting_pupils_to_or_from_school"]]
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "bus_actor_id": packet["bus_actor_id"], "driver_actor_id": packet["driver_actor_id"],
            "school_bus_classification": classification,
            "transport_direction": packet["transport_direction"], "transport_source": packet["transport_source"],
            "pupil_count": packet["pupil_count"], "sidewalk_source": packet["sidewalk_source"],
            "active_transport_frame_count": len(active),
            "maximum_active_transport_speed_mph": max((o["speed_mph"] for o in active), default=None),
            "active_transport_speed_above_55_mph_observed": any(o["speed_mph"] > LIMIT_MPH for o in active),
            "observations": observations,
            "review_limit": "Observed speed and transportation phase require independent source validation; profile targets do not establish realized motion or school-bus legal classification."}
