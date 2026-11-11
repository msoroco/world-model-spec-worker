"""Saved-source stop and entry-order facts for the subsection-4 comparison.

Zero recorded speed, a position near a selected reference, and another vehicle's
entry order are observations. None alone establishes a statutory stop or yield.
"""
import hashlib
import json
import math
from pathlib import Path

SOURCES = ("stop_context.json", "stop_history.jsonl", "video_frames.jsonl")


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError("Missing finite " + label)
    return value


def _distance(point, segment):
    a, b = (_point(v, "stop reference endpoint") for v in segment)
    dx, dy = b[0]-a[0], b[1]-a[1]
    if dx*dx+dy*dy <= 0:
        raise ValueError("Degenerate stop reference segment")
    projection = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(point[0]-a[0]-projection*dx, point[1]-a[1]-projection*dy)


def analyze(root: Path, entries: dict) -> dict:
    root = Path(root)
    hashes = {}
    for name in SOURCES:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required stop source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "stop_context.json").read_text())
    if context.get("intersection_id") != entries.get("intersection_id"):
        raise ValueError("Stop and entry intersection identities differ")
    references = context.get("selected_references")
    if not isinstance(references, dict) or set(references) != {"ego", "other"}:
        raise ValueError("Source-selected stop reference required for each approach")
    for party, reference in references.items():
        if not isinstance(reference, dict) or reference.get("kind") not in (
                "marked_stop_line", "near_side_crosswalk", "nearest_view_point"):
            raise ValueError("Source-selected stop reference required: " + party)
        if not reference.get("geometry_source") or not reference.get("reference_review_source"):
            raise ValueError("Stop reference lacks geometry/review provenance: " + party)
        segment = reference.get("segment_xy_m")
        if not isinstance(segment, list) or len(segment) != 2:
            raise ValueError("Stop reference segment required: " + party)
        _distance(_point(segment[0], "stop reference endpoint"), segment)
    history = [json.loads(s) for s in (root / "stop_history.jsonl").read_text().splitlines() if s.strip()]
    mapping = [json.loads(s) for s in (root / "video_frames.jsonl").read_text().splitlines() if s.strip()]
    if len(history) < 2 or len(history) != len(mapping):
        raise ValueError("Incomplete stop/frame history")
    entry = entries.get("first_body_entry", {})
    if set(entry) != {"ego", "other"} or any(not isinstance(entry[p], dict) for p in ("ego", "other")):
        raise ValueError("Both measured original body entries required")
    first_zero = {"ego": None, "other": None}
    entry_seen = {"ego": False, "other": False}
    ego_at_entry = None
    other_inside_at_ego_entry = None
    last_frame, last_time = -1, -math.inf
    for i, (row, video) in enumerate(zip(history, mapping)):
        frame, time_s = row.get("frame"), row.get("time_s")
        if (type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s)
                or frame <= last_frame or time_s <= last_time):
            raise ValueError("Nonmonotone original stop frame/time")
        last_frame, last_time = frame, time_s
        if (video.get("video_frame") != i or video.get("carla_frame") != frame
                or video.get("time_s") != time_s):
            raise ValueError("Original stop/video frame join failed")
        for party in ("ego", "other"):
            state = row.get(party)
            if not isinstance(state, dict):
                raise ValueError("Missing original stop state: " + party)
            speed = state.get("speed_mps")
            if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
                raise ValueError("Invalid observed participant speed")
            _point(state.get("front_xy_m"), party + " front position")
            if type(state.get("body_inside_crossing")) is not bool:
                raise ValueError("Missing original body occupancy")
            if frame < entry[party]["frame"] and speed == 0 and first_zero[party] is None:
                first_zero[party] = {"frame": frame, "time_s": time_s,
                                     "front_distance_to_reference_m": _distance(
                                         state["front_xy_m"], references[party]["segment_xy_m"])}
            if frame == entry[party]["frame"]:
                if time_s != entry[party]["time_s"]:
                    raise ValueError(party + " stop/entry timestamp mismatch")
                entry_seen[party] = True
        if frame == entry["ego"]["frame"]:
            ego_at_entry = {"frame": frame, "time_s": time_s,
                            "front_distance_to_reference_m": _distance(
                                row["ego"]["front_xy_m"], references["ego"]["segment_xy_m"])}
            other_inside_at_ego_entry = row["other"]["body_inside_crossing"]
    if ego_at_entry is None or not all(entry_seen.values()):
        raise ValueError("Measured body entry absent from original stop history")
    return {"format": "worker-original-stop-order-measurements", "sources": hashes,
            "intersection_id": context["intersection_id"],
            "selected_references": {party: {"kind": ref["kind"],
                "geometry_source": ref["geometry_source"],
                "reference_review_source": ref["reference_review_source"]}
                for party, ref in references.items()},
            "first_recorded_zero_speed_before_entry": first_zero,
            "ego_at_entry": ego_at_entry,
            "other_first_body_entry_before_ego": entry["other"]["frame"] < entry["ego"]["frame"],
            "other_body_inside_at_ego_entry": other_inside_at_ego_entry,
            "statutory_stop_judgment": "unresolved",
            "statutory_yield_judgment": "unresolved"}
