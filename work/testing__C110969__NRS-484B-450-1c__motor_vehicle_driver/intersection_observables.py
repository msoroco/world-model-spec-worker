"""Source-bound observations for NRS 484B.450(1)(c), not a legal evaluator.

The intersection polygon must come from a separately reviewed Native map packet.
Samples are original body footprints and motion records, not expected case labels.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SourceError(message)


def load_source(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256,
             f"source seal differs: {path}")
    value = json.loads(raw)
    _require(isinstance(value, dict), f"source must be an object: {path}")
    return value


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p) -> bool:
    return abs(_cross(a, b, p)) <= 1e-9 and min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9


def _segments_intersect(a, b, c, d) -> bool:
    if _on_segment(a, b, c) or _on_segment(a, b, d) or _on_segment(c, d, a) or _on_segment(c, d, b):
        return True
    return (_cross(a, b, c) > 0) != (_cross(a, b, d) > 0) and (_cross(c, d, a) > 0) != (_cross(c, d, b) > 0)


def _inside(point, polygon) -> bool:
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(a, b, point):
            return True
    crossings = 0
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            at_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            crossings += at_x > x
    return bool(crossings % 2)


def footprint_intersects_boundary(footprint, boundary) -> bool:
    """Count an overlapping body, including an edge touch, as boundary contact."""
    _require(len(footprint) >= 3 and len(boundary) >= 3, "missing body or intersection polygon")
    for polygon in (footprint, boundary):
        _require(all(len(p) == 2 and all(isinstance(v, (int, float)) for v in p) for p in polygon),
                 "invalid polygon coordinates")
    if any(_inside(p, boundary) for p in footprint) or any(_inside(p, footprint) for p in boundary):
        return True
    return any(_segments_intersect(a, b, c, d)
               for a, b in zip(footprint, footprint[1:] + footprint[:1])
               for c, d in zip(boundary, boundary[1:] + boundary[:1]))


def measure(boundary_packet: dict, samples_packet: dict, activity_packet: dict) -> dict:
    """Describe source-backed contact and halt intervals without legal labels."""
    for key in ("map_id", "highway_status", "boundary_method", "intersection_polygon", "source_refs"):
        _require(boundary_packet.get(key), f"missing reviewed intersection boundary: {key}")
    _require("joining_roadways" in boundary_packet,
             "missing reviewed intersection boundary: joining_roadways")
    _require(boundary_packet["highway_status"] == "reviewed_highway" and
             boundary_packet["joining_roadways"] is True,
             "intersection highway/joining-roadway basis unreviewed")
    boundary = boundary_packet["intersection_polygon"]
    _require(samples_packet.get("map_id") == boundary_packet["map_id"], "map identity differs")
    samples = samples_packet.get("samples", [])
    _require(len(samples) >= 2, "insufficient original motion samples")
    _require(activity_packet.get("source_refs") and activity_packet.get("activity_source"),
             "missing independent activity source")
    intervals = []
    last_frame = -1
    for sample in samples:
        frame = sample.get("frame")
        _require(isinstance(frame, int) and frame > last_frame, "nonmonotonic original frame")
        last_frame = frame
        _require(sample.get("body_footprint") and isinstance(sample.get("speed_mps"), (float, int)),
                 "missing original body or speed")
        intervals.append({"frame": frame,
                          "within_or_touching_boundary": footprint_intersects_boundary(
                              sample["body_footprint"], boundary),
                          "speed_mps": sample["speed_mps"]})
    _require(samples_packet.get("fps") == 20, "original 20 Hz frame basis missing")
    return {"map_id": boundary_packet["map_id"], "boundary_method": boundary_packet["boundary_method"],
            "frames": intervals, "activity_observation": activity_packet.get("activity_observation"),
            "traffic_conflict_observation": activity_packet.get("traffic_conflict_observation"),
            "law_direction_observation": activity_packet.get("law_direction_observation"),
            "officer_direction_observation": activity_packet.get("officer_direction_observation"),
            "device_direction_observation": activity_packet.get("device_direction_observation"),
            "source_refs": boundary_packet["source_refs"] + samples_packet.get("source_refs", []) + activity_packet["source_refs"],
            "legal_conclusion": None}
