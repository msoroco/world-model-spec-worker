"""Saved-only original-footprint entry timing for the exact median-opening site.

This measures entry brackets. It does not decide "approximately," priority,
official-device status, or the subsection 4/opposite-direction exceptions.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _inside(p, polygon):
    x, y = p
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            at_x = (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]
            if at_x > x:
                hit = not hit
    return hit


def _intersect(a, b, c, d):
    return _cross(a,b,c)*_cross(a,b,d) < 0 and _cross(c,d,a)*_cross(c,d,b) < 0


def _overlap(body, junction):
    if any(_inside(p, junction) for p in body) or any(_inside(p, body) for p in junction):
        return True
    return any(_intersect(a,b,c,d) for a,b in zip(body,body[1:]+body[:1])
               for c,d in zip(junction,junction[1:]+junction[:1]))


def _points(value, name):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(f"{name} polygon missing")
    points = [tuple(map(float, p)) for p in value]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
        raise ValueError(f"{name} polygon invalid")
    return points


def measure(packet_path: str | Path, packet_sha256: str, *, case_id: str,
            expected_frames: int = 900) -> dict:
    """Hash-check an original trace and retain consecutive sample brackets."""
    raw = Path(packet_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != packet_sha256:
        raise ValueError("original trace source hash mismatch")
    packet = json.loads(raw)
    if packet.get("case_id") != case_id:
        raise ValueError("exact case identity mismatch")
    if not all(packet.get(k) for k in ("map_source_sha256", "intersection_source_sha256",
                                       "highway_source_sha256", "device_source_sha256")):
        raise ValueError("site and control sources missing")
    if packet.get("ego_road_id") == packet.get("other_road_id"):
        raise ValueError("different source highways required")
    junction = _points(packet.get("intersection_polygon_xy_m"), "intersection")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != expected_frames:
        raise ValueError("complete original frame history required")
    entries = {}
    previous = None
    previous_overlap = {"ego": False, "other": False}
    for row in frames:
        frame, time_s = row["frame"], row["time_s"]
        if type(frame) is not int or not isinstance(time_s, (int,float)) or not math.isfinite(time_s):
            raise ValueError("invalid original frame or time")
        if previous is not None and (frame != previous["frame"] + 1 or
                not .049 <= time_s-previous["time_s"] <= .051):
            raise ValueError("original 20 Hz frame discontinuity")
        for who in ("ego", "other"):
            actor = row[who]
            if actor.get("id") != packet.get(who + "_actor_id") or actor.get("road_id") != packet.get(who + "_road_id"):
                raise ValueError("original actor/highway identity mismatch")
            body = _points(actor.get("body_corners_xy_m"), who)
            now = _overlap(body, junction)
            if now and not previous_overlap[who] and who not in entries:
                if previous is None:
                    raise ValueError("actor starts inside intersection; entry unbracketed")
                entries[who] = {"previous_frame": previous["frame"],
                                "entry_frame": frame,
                                "time_bracket_s": [previous["time_s"], time_s]}
            previous_overlap[who] = now
        previous = row
    if set(entries) != {"ego", "other"}:
        raise ValueError("both original intersection entries required")
    difference = entries["ego"]["time_bracket_s"][1] - entries["other"]["time_bracket_s"][1]
    return {"case_id": case_id, "original_trace_sha256": packet_sha256,
            "intersection_entry_time_difference_s": difference,
            "entry_brackets": entries, "measurement_method": "first original footprint-intersection transition upper timestamp; no interpolation",
            "approximately_same_time": "undetermined", "right_of_way": "undetermined",
            "official_device_exception": "undetermined", "opposite_direction_left_turn_exception": "undetermined",
            "subsection_4_exception": "undetermined"}
