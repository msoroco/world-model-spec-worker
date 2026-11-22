"""Original-frame physical checks for C126120 divided-highway U-turns.

An authored opening, a map lane, or a reverse command does not prove that a
public authority established a crossover or that the full vehicle stayed in it.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import Polygon, box


def _region(rect):
    if (not isinstance(rect, list) or len(rect) != 4 or
            not all(isinstance(v, (int, float)) and math.isfinite(v) for v in rect) or
            rect[0] >= rect[2] or rect[1] >= rect[3]):
        raise ValueError("invalid roadway or median rectangle")
    return box(*rect)


def _body(vertices):
    if not isinstance(vertices, list) or len(vertices) != 4:
        raise ValueError("missing original four-corner body")
    polygon = Polygon(vertices)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("invalid original body polygon")
    return polygon


def measure(trace):
    context = trace["context"]
    for name in ("map_source_sha256", "authority_review_source_sha256",
                 "opening_id", "source_right_roadway_id", "destination_right_roadway_id"):
        if not context.get(name):
            raise ValueError("missing source-bound divided-highway context: " + name)
    if context["source_right_roadway_id"] == context["destination_right_roadway_id"]:
        raise ValueError("destination roadway identity does not change")
    opening = _region(context["opening_bounds_xy_m"])
    barriers = [_region(rect) for rect in context["closed_divider_bounds_xy_m"]]
    if not barriers:
        raise ValueError("closed divider physical geometry is absent")
    if any(opening.intersects(barrier) for barrier in barriers):
        raise ValueError("opening overlaps closed divider geometry")
    source = _region(context["source_right_roadway_bounds_xy_m"])
    destination = _region(context["destination_right_roadway_bounds_xy_m"])
    rows = trace["samples"]
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("insufficient original body history")
    previous = None
    previous_time = None
    bodies = []
    headings = []
    opening_frames = []
    closed_frames = []
    reverse_frames = []
    forward_frames = []
    previous_center = None
    for row in rows:
        frame, time_s = row["frame"], row["time_s"]
        if (type(frame) is not int or not isinstance(time_s, (int,float)) or
                not math.isfinite(time_s) or
                (previous is not None and (frame != previous+1 or time_s <= previous_time))):
            raise ValueError("original frame/time history is not consecutive")
        body = _body(row["body_vertices_xy_m"])
        heading = row["heading_deg"]
        velocity = row["velocity_xy_mps"]
        if (not isinstance(heading, (int,float)) or not math.isfinite(heading) or
                not isinstance(velocity, list) or len(velocity) != 2 or
                not all(isinstance(v, (int,float)) and math.isfinite(v) for v in velocity)):
            raise ValueError("original heading or velocity missing")
        if body.intersects(opening): opening_frames.append(frame)
        if any(body.intersects(barrier) for barrier in barriers): closed_frames.append(frame)
        signed = velocity[0]*math.cos(math.radians(heading)) + velocity[1]*math.sin(math.radians(heading))
        center = (body.centroid.x, body.centroid.y)
        observed_step = None if previous_center is None else (
            (center[0]-previous_center[0])*math.cos(math.radians(heading)) +
            (center[1]-previous_center[1])*math.sin(math.radians(heading)))
        if signed < -.2 and observed_step is not None and observed_step < -.01:
            reverse_frames.append(frame)
        if signed > .2 and observed_step is not None and observed_step > .01:
            forward_frames.append(frame)
        bodies.append(body); headings.append(heading)
        previous, previous_time = frame, time_s
        previous_center = center
    if not source.covers(bodies[0]):
        raise ValueError("original start body is not in source right-hand roadway")
    change = sum((b-a+180)%360-180 for a,b in zip(headings,headings[1:]))
    departure = destination.covers(bodies[-1])
    return {"opening_id": context["opening_id"],
            "opening_contact_frames": opening_frames,
            "closed_divider_contact_frames": closed_frames,
            "net_heading_change_deg": change,
            "u_turn_orientation_observed": 150 <= abs(change) <= 210,
            "destination_right_roadway_departure_observed": departure,
            "reverse_motion_frames": reverse_frames,
            "multiple_movement_observed": bool(reverse_frames and
                                               any(f < reverse_frames[0] for f in forward_frames) and
                                               any(f > reverse_frames[-1] for f in forward_frames)),
            "engineering_crossing_observed": bool(opening_frames) and not closed_frames and departure,
            "authority_establishment_judgment": "unresolved_source_review",
            "legal_judgment": "unresolved"}


def load_and_measure(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("saved original trace hash mismatch")
    return measure(json.loads(raw))


def compare(left, right, varying):
    a, b = measure(left), measure(right)
    if left["context"]["map_source_sha256"] != right["context"]["map_source_sha256"]:
        raise ValueError("fixed OpenDRIVE source changed")
    if left["context"]["opening_id"] != right["context"]["opening_id"] and "opening_id" not in varying:
        raise ValueError("fixed opening changed")
    allowed = {"multiple_movement_observed", "engineering_crossing_observed",
               "destination_right_roadway_departure_observed", "opening_id"}
    if not varying or any(item not in allowed for item in varying):
        raise ValueError("unsupported comparison difference")
    for key in varying:
        value_a = left["context"][key] if key == "opening_id" else a[key]
        value_b = right["context"][key] if key == "opening_id" else b[key]
        if value_a == value_b:
            raise ValueError("declared comparison difference not realized: " + key)
    return {"left": a, "right": b, "declared_differences": sorted(varying),
            "legal_verdict_claimed": False}
