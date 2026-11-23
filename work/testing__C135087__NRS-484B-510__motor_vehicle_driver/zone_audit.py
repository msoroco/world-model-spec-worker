"""Source-bound audit of an original 20 Hz Native restricted-zone history."""

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_original_frames(frames_path: Path, context_path: Path, seal_path: Path,
                          case_id: str, expected_frames: int = 900) -> dict:
    """Reject absent/stale original sources; return measurements, never a verdict."""
    frames_path, context_path, seal_path = map(Path, (frames_path, context_path, seal_path))
    for path in (frames_path, context_path, seal_path):
        if not path.is_file():
            raise ValueError(f"missing original source: {path.name}")
    seal = json.loads(seal_path.read_text())
    context = json.loads(context_path.read_text())
    if seal.get("case_id") != case_id or context.get("case_id") != case_id:
        raise ValueError("case identity mismatch")
    if seal.get("frames_sha256") != _sha(frames_path) or seal.get("context_sha256") != _sha(context_path):
        raise ValueError("original source hash mismatch")
    for key in ("zone_start_m", "zone_end_m", "restricted_purpose", "restricted_source",
                "effective_conditions", "subject_vehicle_class_source", "driver_identity_source",
                "entrant_parking_purpose_source", "prohibited_stopping_exclusions_review"):
        if not context.get(key):
            raise ValueError(f"missing source-backed context: {key}")
    lo, hi = float(context["zone_start_m"]), float(context["zone_end_m"])
    if not lo < hi:
        raise ValueError("invalid zone boundaries")
    frames = [json.loads(line) for line in frames_path.read_text().splitlines() if line]
    if len(frames) != expected_frames:
        raise ValueError("incomplete original frame history")
    required = ("frame", "time_s", "subject_station_m", "subject_speed_mps",
                "entrant_station_m", "entrant_speed_mps", "entrant_waiting",
                "passenger_exchange_active", "passenger_station_m", "passenger_boarding_state",
                "entrant_access_blocked",
                "entrant_parking_task_active")
    for index, frame in enumerate(frames):
        if any(key not in frame for key in required):
            raise ValueError("missing original-frame observation")
        if frame["frame"] != index:
            raise ValueError("noncontiguous original frames")
        t = float(frame["time_s"])
        if not math.isfinite(t) or abs(t - index / 20.0) > 0.002:
            raise ValueError("original frame time mismatch")
        for key in ("subject_station_m", "subject_speed_mps", "entrant_station_m", "entrant_speed_mps", "passenger_station_m"):
            if not math.isfinite(float(frame[key])):
                raise ValueError("nonfinite original-frame measurement")
    inside = [f for f in frames if lo <= f["subject_station_m"] <= hi and f["subject_speed_mps"] < 0.1]
    exchange = [f for f in frames if f["passenger_exchange_active"]]
    states = {f["passenger_boarding_state"] for f in frames}
    if not {"approaching", "boarding", "aboard"}.issubset(states):
        raise ValueError("actual passenger exchange state transition absent")
    approaching = [f for f in frames if f["entrant_parking_task_active"] and f["entrant_station_m"] < lo]
    waiting = [f for f in frames if f["entrant_waiting"]]
    blocked = [f for f in frames if f["entrant_access_blocked"]]
    if not inside or not exchange or not approaching:
        raise ValueError("required zone, exchange or restricted-purpose approach absent")
    return {
        "case_id": case_id,
        "frames_sha256": _sha(frames_path),
        "context_sha256": _sha(context_path),
        "frame_count": len(frames),
        "fixed_context": {key: context[key] for key in (
            "zone_start_m", "zone_end_m", "restricted_purpose", "restricted_source",
            "effective_conditions", "subject_vehicle_class_source", "driver_identity_source",
            "entrant_parking_purpose_source", "prohibited_stopping_exclusions_review")},
        "subject_stationary_in_zone_frames": len(inside),
        "passenger_exchange_frames": len(exchange),
        "passenger_boarding_states": sorted(states),
        "entrant_approach_frames": len(approaching),
        "entrant_waiting_frames": len(waiting),
        "entrant_access_blocked_frames": len(blocked),
        "first_waiting_time_s": waiting[0]["time_s"] if waiting else None,
        "first_access_blocked_time_s": blocked[0]["time_s"] if blocked else None,
        "legal_interference": "unresolved_judgment",
        "legal_about_to_enter": "unresolved_judgment",
        "legal_temporary": "unresolved_judgment",
    }


def compare_cases(left: dict, right: dict) -> dict:
    """Verify source-backed fixed setup and report observed differences only."""
    if left.get("case_id") == right.get("case_id") or not left.get("case_id") or not right.get("case_id"):
        raise ValueError("distinct exact case identities required")
    if left.get("frame_count") != 900 or right.get("frame_count") != 900:
        raise ValueError("complete original histories required")
    if not left.get("frames_sha256") or not right.get("frames_sha256"):
        raise ValueError("sealed original source references required")
    if not left.get("fixed_context") or left["fixed_context"] != right.get("fixed_context"):
        raise ValueError("fixed zone, purpose or participant source differs")
    return {
        "case_ids": [left["case_id"], right["case_id"]],
        "fixed_context_source_matched": True,
        "observed_difference": {
            key: [left[key], right[key]] for key in (
                "entrant_waiting_frames", "entrant_access_blocked_frames",
                "passenger_exchange_frames", "subject_stationary_in_zone_frames")
        },
        "legal_comparison": "unresolved_judgment",
    }
