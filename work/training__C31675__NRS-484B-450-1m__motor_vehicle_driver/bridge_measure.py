"""Source-hashed bridge/vehicle geometry measurement from saved observations.

The bridge polygon must be established from original map and physical review.
This module measures spatial relation and stationary candidates, not legality.
"""
from __future__ import annotations

import hashlib
import json
import math


def _polygon(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("convex source polygon required")
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in point
        ):
            raise ValueError("invalid source polygon point")
        points.append((float(point[0]), float(point[1])))
    turns = []
    for i in range(len(points)):
        a, b, c = points[i], points[(i + 1) % len(points)], points[(i + 2) % len(points)]
        turns.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
    if min(turns) <= 0:
        raise ValueError("counterclockwise strictly convex source polygon required")
    return points


def _inside(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    return all((polygon[(i+1)%len(polygon)][0]-polygon[i][0])*(point[1]-polygon[i][1])
               -(polygon[(i+1)%len(polygon)][1]-polygon[i][1])*(point[0]-polygon[i][0]) >= -1e-9
               for i in range(len(polygon)))


def _separated(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> bool:
    # Convex separating axis test; catches crossings even when no corner is inside.
    for polygon in (a, b):
        for i, p in enumerate(polygon):
            q = polygon[(i+1) % len(polygon)]
            nx, ny = -(q[1]-p[1]), q[0]-p[0]
            ap = [nx*x+ny*y for x, y in a]
            bp = [nx*x+ny*y for x, y in b]
            if max(ap) < min(bp)-1e-9 or max(bp) < min(ap)-1e-9:
                return True
    return False


def measure(trace: bytes, bridge: bytes, *, trace_sha256: str, bridge_sha256: str) -> dict:
    actual_trace = hashlib.sha256(trace).hexdigest()
    actual_bridge = hashlib.sha256(bridge).hexdigest()
    if actual_trace != trace_sha256 or actual_bridge != bridge_sha256:
        raise ValueError("saved source hash mismatch")
    bridge_source = json.loads(bridge)
    deck = _polygon(bridge_source.get("deck_polygon_xy_m"))
    if bridge_source.get("structure_type") != "bridge":
        raise ValueError("source is not a bridge deck")
    rows = [json.loads(line) for line in trace.splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError("insufficient saved samples")
    measurements = []
    for i, row in enumerate(rows):
        if row.get("frame") != i:
            raise ValueError("missing or reordered saved frame")
        t = row.get("time_s")
        if type(t) not in (int, float) or not math.isfinite(t):
            raise ValueError("invalid saved time")
        if i and abs((t - rows[i-1]["time_s"])-0.05) > 1e-4:
            raise ValueError("saved 20 Hz time discontinuity")
        speed = row.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("missing observed speed")
        body = _polygon(row.get("body_footprint_xy_m"))
        relation = ("full" if all(_inside(p, deck) for p in body) else
                    "none" if _separated(body, deck) else "partial")
        measurements.append({"frame": i, "time_s": t, "speed_mps": speed,
                             "bridge_relation": relation,
                             "stationary_candidate": speed <= 0.1})
    return {"format": "c31675-bridge-measurement-v1", "trace_sha256": actual_trace,
            "bridge_sha256": actual_bridge, "rows": measurements,
            "stationary_candidate_speed_ceiling_mps": 0.1,
            "legal_result": None,
            "limitations": ["0.1 m/s is an engineering candidate filter, not a legal cutoff",
                            "original structure, motion, cause and exception require independent review"]}
