"""Saved-trace measurements for the assigned median-opening crossing.

This module reports physical predicates and source gaps, never a legal verdict.
The trace format is deliberately small so the original capture can export it.
"""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path


REQUIRED_CONTEXT = ("map_source", "ego_highway", "other_highway", "public_access_source",
                    "device_inventory_source", "driver_scope_source")


def _inside(point, rect):
    if len(point) != 2 or len(rect) != 4 or rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise ValueError("invalid point or crossing rectangle")
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _body_overlaps(vertices, rect):
    if len(rect) != 4 or rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise ValueError("invalid crossing rectangle")
    if not isinstance(vertices, list) or len(vertices) != 4:
        raise ValueError("original body footprint missing")
    if any(not isinstance(p, list) or len(p) != 2 for p in vertices):
        raise ValueError("invalid original body vertex")
    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xs + ys):
        raise ValueError("non-numeric original body vertex")
    turns = []
    for index in range(4):
        a, b, c = (vertices[(index + j) % 4] for j in range(3))
        turns.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
    if not all(t > 0 for t in turns) and not all(t < 0 for t in turns):
        raise ValueError("original body vertices are not ordered convex corners")
    region = [[rect[0], rect[1]], [rect[2], rect[1]],
              [rect[2], rect[3]], [rect[0], rect[3]]]
    for polygon in (vertices, region):
        for index, point in enumerate(polygon):
            following = polygon[(index + 1) % 4]
            axis = (point[1] - following[1], following[0] - point[0])
            if axis == (0, 0):
                raise ValueError("degenerate original body or crossing edge")
            body_projection = [axis[0]*p[0] + axis[1]*p[1] for p in vertices]
            region_projection = [axis[0]*p[0] + axis[1]*p[1] for p in region]
            if max(body_projection) < min(region_projection) or max(region_projection) < min(body_projection):
                return False
    return True


def _first_entry(samples, rect):
    if len(samples) < 2:
        raise ValueError("at least two original samples required")
    previous_frame = -1
    previous_inside = False
    entry = None
    exit_frame = None
    for sample in samples:
        frame = sample["frame"]
        if not isinstance(frame, int) or frame <= previous_frame:
            raise ValueError("nonmonotone or missing original frame")
        if previous_frame >= 0 and frame != previous_frame + 1:
            raise ValueError("gap in original frame history")
        now_inside = _body_overlaps(sample["body_vertices_xy_m"], rect)
        if now_inside and not previous_inside and entry is None:
            if previous_frame < 0:
                raise ValueError("first sample already in crossing; entry unobserved")
            entry = frame
        if not now_inside and previous_inside and entry is not None and exit_frame is None:
            exit_frame = frame
        previous_frame, previous_inside = frame, now_inside
    return entry, exit_frame


def _observed_left_turn(samples):
    """Use original body centers to distinguish an actual turn from stated intent."""
    centers = [(sum(p[0] for p in sample["body_vertices_xy_m"])/4,
                sum(p[1] for p in sample["body_vertices_xy_m"])/4)
               for sample in samples]
    moves = [(b[0]-a[0], b[1]-a[1]) for a, b in zip(centers, centers[1:])
             if math.dist(a, b) > 0.1]
    if len(moves) < 2:
        raise ValueError("original other-body motion insufficient for turn measurement")
    first, last = moves[0], moves[-1]
    cross = first[0]*last[1] - first[1]*last[0]
    length = math.hypot(*first)*math.hypot(*last)
    return cross/length > 0.8


def measure(trace):
    context = trace["context"]
    for name in REQUIRED_CONTEXT:
        if not context.get(name):
            raise ValueError(f"missing source-bound context: {name}")
    relation = context.get("approach_relation")
    if relation == "crossing" and context["ego_highway"] == context["other_highway"]:
        raise ValueError("different highway not established")
    if relation == "opposite" and context["ego_highway"] != context["other_highway"]:
        raise ValueError("opposite approaches require one highway identity")
    if context.get("public_access") is not True or context.get("human_driver") is not True:
        raise ValueError("public highway or conventional driver scope not established")
    devices = context.get("devices")
    if not isinstance(devices, list) or any(
            item not in ("traffic_light", "stop_sign", "yield_sign") for item in devices):
        raise ValueError("official device inventory must be explicit")
    crossing = trace["crossing"]
    if not crossing.get("crossing_id") or not crossing.get("roadway_id"):
        raise ValueError("crossing and separate roadway identities required")
    rect = crossing["bounds_xy_m"]
    ego_frames = [sample["frame"] for sample in trace["ego_samples"]]
    other_frames = [sample["frame"] for sample in trace["other_samples"]]
    if ego_frames != other_frames:
        raise ValueError("ego and other original frame windows do not match")
    ego_entry, ego_exit = _first_entry(trace["ego_samples"], rect)
    other_entry, other_exit = _first_entry(trace["other_samples"], rect)
    if ego_entry is None or other_entry is None:
        raise ValueError("both original entries must be observed at the same crossing")
    if relation not in ("crossing", "opposite"):
        raise ValueError("approach relation not established")
    if context.get("left_turn_intent") not in (True, False) or context.get("left_turn_realized") not in (True, False):
        raise ValueError("left-turn intent and realization must be separately observed")
    observed_left_turn = _observed_left_turn(trace["other_samples"]) if relation == "opposite" else False
    if relation == "opposite" and observed_left_turn != context["left_turn_realized"]:
        raise ValueError("declared left-turn realization differs from original body motion")
    device_exclusion = bool(devices)
    opposite_left_exclusion = (context["approach_relation"] == "opposite" and
                               (context["left_turn_intent"] or context["left_turn_realized"]))
    return {
        "crossing_id": crossing["crossing_id"], "roadway_id": crossing["roadway_id"],
        "ego_entry_frame": ego_entry, "other_entry_frame": other_entry,
        "ego_exit_frame": ego_exit, "other_exit_frame": other_exit,
        "other_entered_before_ego": other_entry < ego_entry,
        "other_cleared_before_ego_entry": other_exit is not None and other_exit < ego_entry,
        "official_device_exclusion": device_exclusion,
        "opposite_left_exclusion": opposite_left_exclusion,
        "observed_left_turn": observed_left_turn,
        "subsection_4_qualification": "unresolved_source_review",
        "legal_judgment": "unresolved",
    }


def audit_comparison(left_trace, right_trace, varying_fields):
    """Reject undeclared changes and missing source context in a pair."""
    left, right = measure(left_trace), measure(right_trace)
    fields = set(varying_fields)
    if not fields:
        raise ValueError("comparison variable required")
    for name in REQUIRED_CONTEXT:
        if name not in fields and left_trace["context"][name] != right_trace["context"][name]:
            raise ValueError(f"fixed context changed: {name}")
    for name in ("crossing_id", "roadway_id"):
        if name not in fields and left[name] != right[name]:
            raise ValueError(f"fixed crossing changed: {name}")
    for name in ("devices", "approach_relation", "left_turn_intent", "left_turn_realized"):
        if name not in fields and left_trace["context"][name] != right_trace["context"][name]:
            raise ValueError(f"undeclared difference: {name}")
    observables = {
        "entry_order": (left["other_entered_before_ego"], right["other_entered_before_ego"]),
        "clearance": (left["other_cleared_before_ego_entry"], right["other_cleared_before_ego_entry"]),
    }
    for name in ("devices", "approach_relation", "left_turn_intent", "left_turn_realized"):
        observables[name] = (left_trace["context"][name], right_trace["context"][name])
    for name in fields:
        if name not in observables:
            raise ValueError(f"unsupported declared comparison variable: {name}")
        if observables[name][0] == observables[name][1]:
            raise ValueError(f"declared comparison variable did not differ: {name}")
    return {"left": left, "right": right, "declared_differences": sorted(fields)}


def load_and_measure(path: str | Path, expected_sha256: str):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("saved trace source hash mismatch")
    return measure(json.loads(data))
