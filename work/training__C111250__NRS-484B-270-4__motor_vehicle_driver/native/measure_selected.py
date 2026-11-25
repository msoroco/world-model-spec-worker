"""Measure original Native bicycle-facility occupancy without a legal verdict."""
import hashlib
import json
import math
from pathlib import Path

from facility import body_overlap


SOURCES = ("facility-context.json", "subsection3-context.json", "body-history.jsonl",
           "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(attempt, allow_diagnostic=False):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError("Missing required original source: " + name)
    facility = json.loads((attempt / "facility-context.json").read_text())
    circumstance = json.loads((attempt / "subsection3-context.json").read_text())
    source_kind = facility.get("source_kind")
    if source_kind != circumstance.get("source_kind") or source_kind not in (
            "original_native_capture", "synthetic_cpu_diagnostic") or (
            source_kind == "synthetic_cpu_diagnostic" and not allow_diagnostic):
        raise ValueError("Original Native context required")
    if facility.get("facility_x_m") != [3.5, 5.5] or \
       facility.get("intersection_y_m") != [-7.0, 7.0] or \
       len(facility.get("native_lane_survey", [])) != 6 or \
       not facility.get("native_map_sha256"):
        raise ValueError("Original Native facility geometry/readback differs")
    if circumstance.get("exception_clause_requested") != \
            "NRS 484B.270(3)(c), to avoid conflict with other traffic" or \
       not isinstance(circumstance.get("conflict_actor_id"), int) or \
       len(circumstance.get("conflict_actor_body_xy_m", [])) != 4:
        raise ValueError("Original subsection 3 conflict-actor source missing")
    bodies = rows(attempt / "body-history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    frames = rows(attempt / "video_frames.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    if not all(len(seq) == 600 for seq in (bodies, trace, frames, evidence)):
        raise ValueError("Original 600-frame source interval incomplete")
    previous_frame = -1; previous_time = -1.0
    inside = []; overlap = []
    for index, (body, pose, mapped, packet) in enumerate(zip(bodies, trace, frames, evidence)):
        frame = mapped.get("native_frame"); time_s = mapped.get("time_s")
        if type(frame) is not int or frame <= previous_frame or \
           type(time_s) not in (int, float) or not math.isfinite(time_s) or \
           time_s <= previous_time or mapped.get("video_frame") != index or \
           mapped.get("carla_frame") != frame:
            raise ValueError("Original frame map monotonicity/identity differs")
        if body.get("native_frame") != frame or pose.get("frame") != frame or \
           abs(body.get("time_s", -100) - time_s) > 1e-4 or \
           abs(pose.get("time_s", -100) - time_s) > 1e-4 or \
           packet.get("original_frame") != frame:
            raise ValueError("Original body, trace and capture frame join differs")
        if body.get("source_kind") != source_kind:
            raise ValueError("Original Native body source required")
        if not isinstance(body.get("speed_mps"), (int, float)) or \
           not math.isfinite(body["speed_mps"]):
            raise ValueError("Original Native velocity missing")
        metric = body_overlap(body)
        if metric["inside_intersection"]:
            inside.append(frame)
        if metric["cycle_intersection_body_overlap_m2"] > 0:
            overlap.append(frame)
        previous_frame, previous_time = frame, time_s
    if not inside:
        raise ValueError("Original body never entered intersection")
    return {"format": "c111250-selected-source-measurement-v1",
            "frames": 600, "first_native_frame": frames[0]["native_frame"],
            "last_native_frame": frames[-1]["native_frame"],
            "intersection_body_frames": len(inside),
            "cycle_lane_intersection_overlap_frames": len(overlap),
            "first_cycle_lane_intersection_overlap_frame": overlap[0] if overlap else None,
            "source_sha256": {name: sha(attempt / name) for name in SOURCES},
            "source_kind": source_kind,
            "native_lane_survey": facility["native_lane_survey"],
            "official_designation_proven": bool(facility.get("official_designation_proven")),
            "subsection3_exception_legally_resolved": bool(circumstance.get("exception_legally_resolved")),
            "facility_user_yield_observed": bool(circumstance.get("yield_to_facility_users_observed")),
            "legal_verdict_claimed": False}
