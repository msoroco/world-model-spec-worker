"""Source-bound sidewalk footprint and halt-history measurement.

A convex local sidewalk polygon is supplied by an acquired map packet, not inferred
from a semantic label. This module measures geometry and timing only. Whether the
surface is legally a sidewalk and whether any exception applies remain review items.
"""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

FRAME_RATE = 20
FRAME_COUNT = 600
EPS = 1e-9


def _poly(raw, label):
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError(label + " polygon required")
    try:
        pts = [(float(p[0]), float(p[1])) for p in raw]
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError(label + " polygon invalid") from exc
    if not all(isfinite(x) and isfinite(y) for x, y in pts):
        raise ValueError(label + " polygon nonfinite")
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
               pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2
    if abs(area) < EPS:
        raise ValueError(label + " polygon degenerate")
    if area < 0:
        pts.reverse()
    for i in range(len(pts)):
        ax, ay = pts[i]; bx, by = pts[(i + 1) % len(pts)]; cx, cy = pts[(i + 2) % len(pts)]
        if (bx - ax) * (cy - by) - (by - ay) * (cx - bx) < -EPS:
            raise ValueError(label + " polygon must be convex")
    return pts


def _area(pts):
    if len(pts) < 3:
        return 0.0
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
                   pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


def _clip(subject, boundary):
    out = subject
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        old = out
        out = []
        if not old:
            break
        for j, q in enumerate(old):
            p = old[j - 1]
            sp, sq = side(p), side(q)
            if sq >= -EPS:
                if sp < -EPS:
                    t = sp / (sp - sq)
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                out.append(q)
            elif sp >= -EPS:
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def measure_frame(vehicle, sidewalk):
    v, s = _poly(vehicle, "vehicle"), _poly(sidewalk, "sidewalk")
    overlap = _area(_clip(v, s))
    vehicle_area = _area(v)
    return {
        "vehicle_footprint_area_m2": vehicle_area,
        "sidewalk_overlap_area_m2": overlap,
        "vehicle_overlap_fraction": overlap / vehicle_area,
        "overlap_positive": overlap > EPS,
        "entire_vehicle_on_sidewalk": abs(overlap - vehicle_area) <= EPS,
    }


def _read_bound(path, expected_sha):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("source hash mismatch")
    return json.loads(data)


def measure_sources(map_path, map_sha256, trace_path, trace_sha256):
    map_packet = _read_bound(map_path, map_sha256)
    trace = _read_bound(trace_path, trace_sha256)
    required_map = ("map_acquisition", "highway_boundary_source", "property_boundary_source",
                    "intended_pedestrian_use_source", "sidewalk_polygon_m")
    if any(not map_packet.get(k) for k in required_map):
        raise ValueError("sidewalk map and context source provenance required")
    if len(trace) != FRAME_COUNT:
        raise ValueError("trace must contain 600 frames")
    stopped = overlap = stopped_overlap = whole = 0
    first_stop = last_stop = None
    for i, row in enumerate(trace):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("20 Hz source frame join failed")
        if not row.get("actor_pose_source") or not row.get("velocity_source"):
            raise ValueError("raw actor pose and velocity source required")
        try:
            speed = float(row["speed_mps"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("raw speed required") from exc
        if not isfinite(speed) or speed < 0:
            raise ValueError("raw speed invalid")
        m = measure_frame(row.get("vehicle_footprint_m"), map_packet["sidewalk_polygon_m"])
        # 0.05 m/s is an engineering stop-state threshold, not statutory meaning.
        at_rest = speed <= 0.05
        stopped += at_rest
        overlap += m["overlap_positive"]
        stopped_overlap += at_rest and m["overlap_positive"]
        whole += at_rest and m["entire_vehicle_on_sidewalk"]
        if at_rest:
            first_stop = i if first_stop is None else first_stop
            last_stop = i
    return {
        "frames": FRAME_COUNT, "frame_rate_hz": FRAME_RATE,
        "first_rest_frame": first_stop, "last_rest_frame": last_stop,
        "rest_frames": stopped, "overlap_frames": overlap,
        "rest_and_overlap_frames": stopped_overlap,
        "entire_footprint_rest_frames": whole,
        "map_sha256": map_sha256, "trace_sha256": trace_sha256,
        "exception_sources": {
            "traffic_conflict": None, "other_law": None,
            "officer_direction": None, "official_device": None,
            "subsection_3_actor": None,
        },
        "sidewalk_legal_status": None,
        "legal_conclusion": None,
    }
