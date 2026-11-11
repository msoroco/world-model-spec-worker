"""Source-bound NRS 484B.710 branch measurements, without legal judgment.

The companion fire_distance module measures complete Native ground footprints.
This module joins those measurements to retained per-frame participant state.
Alarm purpose, authorized status and official business are separately sourced
context; lamps and siren alone cannot establish those facts.
"""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


_distance_path = Path(__file__).with_name("fire_distance.py")
_spec = importlib.util.spec_from_file_location("fire_distance", _distance_path)
_distance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_distance)


def _read_jsonl(path, label):
    raw = Path(path).read_bytes()
    if not raw:
        raise ValueError(f"Empty retained {label} source")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid retained {label} JSONL") from error
    return rows, sha256(raw).hexdigest()


def measure_branch(participant_source, state_source, expected_frames, branch, context):
    """Return measured boundary observations for one declared alternative.

    State records must carry original Native frame/time and boolean fields:
    apparatus_moving, ego_moving, ego_following, ego_parked, warning_lamp,
    siren. Siren may be null when Native has no readback; alarm purpose remains
    a separately sourced premise rather than being inferred from device state.
    """
    if branch not in {"traveling_follow", "stopped_drive_to", "stopped_park"}:
        raise ValueError("Unknown fire apparatus branch")
    required_context = ("alarm_response_source", "apparatus_answered_alarm",
                        "subject_authorized_emergency", "subject_official_business")
    if not isinstance(context, dict) or any(key not in context for key in required_context):
        raise ValueError("Missing sourced alarm or exception context")
    if not context["alarm_response_source"]:
        raise ValueError("Alarm-response context lacks a source")
    if any(type(context[key]) is not bool for key in required_context[1:]):
        raise ValueError("Alarm and exception context must be explicit booleans")
    measured = _distance.measure_native_source(participant_source, expected_frames)
    states, state_hash = _read_jsonl(state_source, "participant state")
    if len(states) != expected_frames:
        raise ValueError("Incomplete retained participant state history")
    required_state = ("apparatus_moving", "ego_moving", "ego_following",
                      "ego_parked", "warning_lamp")
    observations = []
    previous_centre_distance = None
    for distance, state in zip(measured["measurements"], states):
        if (type(state.get("frame")) is not int or
                type(state.get("time_s")) not in (int, float) or
                state["frame"] != distance["frame"] or
                state["time_s"] != distance["time_s"]):
            raise ValueError("Native state and footprint frame/time join failed")
        if any(type(state.get(key)) is not bool for key in required_state):
            raise ValueError("Missing measured Native participant state")
        if "siren" not in state or (state["siren"] is not None and type(state["siren"]) is not bool):
            raise ValueError("Siren state must be a Native readback or explicit unknown")
        if branch == "traveling_follow":
            active = state["apparatus_moving"] and state["ego_following"] and state["ego_moving"]
        elif branch == "stopped_drive_to":
            # A stationary apparatus and a moving ego alone do not establish
            # driving *to* it. Require measured closing in consecutive frames.
            active = (not state["apparatus_moving"] and state["ego_moving"]
                      and not state["ego_parked"] and previous_centre_distance is not None
                      and distance["centre_distance_ft"] < previous_centre_distance - 1e-6)
        else:
            active = not state["apparatus_moving"] and state["ego_parked"] and not state["ego_moving"]
        observations.append({
            "frame": distance["frame"], "time_s": distance["time_s"],
            "branch_active": active,
            "nearest_footprint_gap_ft": distance["nearest_footprint_gap_ft"],
            "centre_distance_ft": distance["centre_distance_ft"],
            "warning_lamp": state["warning_lamp"], "siren": state["siren"],
        })
        previous_centre_distance = distance["centre_distance_ft"]
    active = [row for row in observations if row["branch_active"]]
    if not active:
        raise ValueError("Declared branch has no measured active frames")
    gaps = [row["nearest_footprint_gap_ft"] for row in active]
    boundary_key = ("nearest_footprint_gap_ft" if branch == "traveling_follow"
                    else "centre_distance_ft")
    # Floating point coordinate conversion may move a mathematically exact
    # 500 ft fixture by a few ulps. This is a numerical bin only, not a legal
    # definition of "within" or a physical measurement acceptance tolerance.
    numerical_tolerance_ft = 1e-6
    return {
        "branch": branch, "boundary_ft": _distance.BOUNDARY_FEET,
        "boundary_measurement": boundary_key,
        "participant_source_sha256": measured["source_sha256"],
        "state_source_sha256": state_hash,
        "frame_count": expected_frames, "active_frame_count": len(active),
        "min_gap_ft": min(gaps), "max_gap_ft": max(gaps),
        "min_boundary_distance_ft": min(row[boundary_key] for row in active),
        "max_boundary_distance_ft": max(row[boundary_key] for row in active),
        "numerical_tolerance_ft": numerical_tolerance_ft,
        "below_500_frames": [row["frame"] for row in active if row[boundary_key] < 500 - numerical_tolerance_ft],
        "at_500_frames": [row["frame"] for row in active if abs(row[boundary_key] - 500) <= numerical_tolerance_ft],
        "above_500_frames": [row["frame"] for row in active if row[boundary_key] > 500 + numerical_tolerance_ft],
        "at_500_requires_tolerance_review": True,
        "exception_context": {
            "authorized_emergency": context["subject_authorized_emergency"],
            "official_business": context["subject_official_business"],
            "source": context["alarm_response_source"],
        },
        "apparatus_answered_alarm": context["apparatus_answered_alarm"],
        "observations": observations,
    }
