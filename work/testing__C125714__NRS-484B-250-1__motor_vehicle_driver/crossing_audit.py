"""Saved-trace measurements for the assigned median-opening crossing.

This module reports physical predicates and source gaps, never a legal verdict.
The trace format is deliberately small so the original capture can export it.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path


REQUIRED_CONTEXT = ("map_source", "ego_highway", "other_highway", "public_access_source",
                    "device_inventory_source", "driver_scope_source")


def _inside(point, rect):
    if len(point) != 2 or len(rect) != 4 or rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise ValueError("invalid point or crossing rectangle")
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


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
        now_inside = _inside(sample["center_xy"], rect)
        if now_inside and not previous_inside and entry is None:
            if previous_frame < 0:
                raise ValueError("first sample already in crossing; entry unobserved")
            entry = frame
        if not now_inside and previous_inside and entry is not None and exit_frame is None:
            exit_frame = frame
        previous_frame, previous_inside = frame, now_inside
    return entry, exit_frame


def measure(trace):
    context = trace["context"]
    for name in REQUIRED_CONTEXT:
        if not context.get(name):
            raise ValueError(f"missing source-bound context: {name}")
    if context["ego_highway"] == context["other_highway"]:
        raise ValueError("different highway not established")
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
    ego_entry, ego_exit = _first_entry(trace["ego_samples"], rect)
    other_entry, other_exit = _first_entry(trace["other_samples"], rect)
    if ego_entry is None or other_entry is None:
        raise ValueError("both original entries must be observed at the same crossing")
    if context.get("approach_relation") not in ("crossing", "opposite"):
        raise ValueError("approach relation not established")
    if context.get("left_turn_intent") not in (True, False) or context.get("left_turn_realized") not in (True, False):
        raise ValueError("left-turn intent and realization must be separately observed")
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
    return {"left": left, "right": right, "declared_differences": sorted(fields)}


def load_and_measure(path: str | Path, expected_sha256: str):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("saved trace source hash mismatch")
    return measure(json.loads(data))
