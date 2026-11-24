"""Source-bound perpendicular projection of a parked vehicle assembly.

The legal fifteen-foot distance is converted exactly to 4.572 metres.
The source packet must include the complete physical outline of the
vehicle, load and any attached trailer, plus an original curb segment.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C150088__LVMC-11-52-060__motor_vehicle_driver"
LIMIT_M = 15 * 0.3048


def _point(value, name):
    if not isinstance(value, list) or len(value) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value
    ):
        raise ValueError(f"finite original {name} point required")
    return value


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    a = _point(packet.get("curb_segment_start_m"), "curb start")
    b = _point(packet.get("curb_segment_end_m"), "curb end")
    street = _point(packet.get("street_side_reference_m"), "street reference")
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        raise ValueError("curb segment too short")
    normal = (-dy / length, dx / length)
    sign = 1 if (street[0] - a[0]) * normal[0] + (street[1] - a[1]) * normal[1] > 0 else -1
    if abs((street[0] - a[0]) * normal[0] + (street[1] - a[1]) * normal[1]) < 0.1:
        raise ValueError("street-side reference is ambiguous")
    parts = packet.get("physical_parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("complete physical parts required")
    categories = [p.get("category") for p in parts]
    if "vehicle" not in categories:
        raise ValueError("vehicle outline required")
    if packet.get("load_present") != ("load" in categories):
        raise ValueError("load presence and outline disagree")
    if packet.get("trailer_attached") != ("trailer" in categories):
        raise ValueError("trailer attachment and outline disagree")
    observations = []
    for part in parts:
        if part.get("category") not in ("vehicle", "load", "trailer") or not part.get("source_actor_id"):
            raise ValueError("physical part category and original identity required")
        vertices = part.get("outline_vertices_m")
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise ValueError("complete part outline requires three vertices")
        distances = []
        for vertex in vertices:
            x, y = _point(vertex, "outline")
            distances.append(sign * ((x - a[0]) * normal[0] + (y - a[1]) * normal[1]))
        observations.append({"category": part["category"], "source_actor_id": part["source_actor_id"],
                             "maximum_street_projection_m": max(distances)})
    maximum = max(p["maximum_street_projection_m"] for p in observations)
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "method": "maximum_signed_perpendicular_vertex_distance_from_original_curb_line",
            "parts": observations, "maximum_street_projection_m": maximum,
            "fifteen_feet_m": LIMIT_M, "exceeds_fifteen_feet": maximum > LIMIT_M,
            "qualification": "Requires reviewed curb geometry, street-side reference and complete physical outlines from original source."}
