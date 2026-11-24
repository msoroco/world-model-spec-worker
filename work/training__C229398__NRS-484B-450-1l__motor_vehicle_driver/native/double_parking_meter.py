"""Source-only double-parking geometry and halt meter.

Consumes saved per-frame body footprints and a surveyed curb direction. It
reports observations, not a statutory verdict. No CARLA or derived channels
are accepted as input.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in value):
        raise ValueError("Invalid source point")
    return tuple(float(v) for v in value)


def _polygon(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Four original body footprint corners required")
    pts = [_point(p) for p in value]
    if len(set(pts)) != 4:
        raise ValueError("Degenerate source footprint")
    return pts


def _center(pts):
    return (sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4)


def _project(point, origin, axis):
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def _extent(pts, origin, axis):
    values = [_project(p, origin, axis) for p in pts]
    return min(values), max(values)


def _gap(a, b):
    return max(0.0, a[0] - b[1], b[0] - a[1])


def measure(map_path: Path, frame_path: Path, halt_motion_tolerance_m: float = 0.03):
    """Measure a 20 Hz source sequence; tolerance is an engineering diagnostic."""
    geometry = json.loads(map_path.read_text())
    if geometry.get("source_kind") != "surveyed_map_geometry":
        raise ValueError("Surveyed map geometry source required")
    origin = _point(geometry["curb_start_xy_m"])
    end = _point(geometry["curb_end_xy_m"])
    tangent = (end[0] - origin[0], end[1] - origin[1])
    length = math.hypot(*tangent)
    if length < 1:
        raise ValueError("Curb source segment too short")
    tangent = (tangent[0] / length, tangent[1] / length)
    normal = (-tangent[1], tangent[0])
    road_sign = geometry.get("road_interior_normal_sign")
    if road_sign not in (-1, 1):
        raise ValueError("Road-interior side must be surveyed")
    rows = [json.loads(line) for line in frame_path.read_text().splitlines() if line.strip()]
    if len(rows) < 600:
        raise ValueError("At least 30 seconds of 20 Hz original frames required")
    previous = None
    observed = []
    for i, row in enumerate(rows):
        if row.get("source_kind") != "original_actor_body_footprints" or row.get("frame") != i:
            raise ValueError("Original ordered body frame source required")
        timestamp = row.get("time_s")
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or abs(timestamp - i / 20) > 1e-6:
            raise ValueError("Source frame timing mismatch")
        bodies = row.get("actors")
        if not isinstance(bodies, dict) or set(bodies) != {"ego", "curbside"}:
            raise ValueError("Both original actor bodies required")
        footprints = {name: _polygon(bodies[name]["footprint_corners_xy_m"]) for name in bodies}
        centers = {name: _center(pts) for name, pts in footprints.items()}
        lateral = {name: _project(centers[name], origin, normal) * road_sign for name in bodies}
        longitudinal = {name: _extent(footprints[name], origin, tangent) for name in bodies}
        lateral_extents = {name: _extent(footprints[name], origin, normal) for name in bodies}
        longitudinal_overlap_m = max(0.0, min(longitudinal["ego"][1], longitudinal["curbside"][1]) - max(longitudinal["ego"][0], longitudinal["curbside"][0]))
        lateral_gap_m = _gap(lateral_extents["ego"], lateral_extents["curbside"])
        movement = {name: None if previous is None else math.dist(centers[name], previous[name]) for name in bodies}
        both_at_rest = previous is not None and all(movement[name] <= halt_motion_tolerance_m for name in bodies)
        observed.append({
            "frame": i,
            "time_s": timestamp,
            "ego_highway_side_of_curbside": lateral["ego"] > lateral["curbside"],
            "curbside_nearer_curb_m": abs(lateral["curbside"]),
            "longitudinal_overlap_m": longitudinal_overlap_m,
            "lateral_surface_gap_m": lateral_gap_m,
            "both_at_rest_diagnostic": both_at_rest,
            "concurrent_overlap_at_rest": both_at_rest and longitudinal_overlap_m > 0 and lateral["ego"] > lateral["curbside"],
        })
        previous = centers
    active = [row for row in observed if row["concurrent_overlap_at_rest"]]
    return {
        "format": "source-bound-double-parking-diagnostic",
        "source_kind": "original_footprint_and_surveyed_map_sources",
        "source_hashes": {str(map_path): _sha(map_path), str(frame_path): _sha(frame_path)},
        "frame_count": len(rows),
        "rate_hz": 20,
        "duration_s": len(rows) / 20,
        "concurrent_overlap_at_rest_frame_count": len(active),
        "longest_concurrent_run_frames": _longest(observed),
        "max_longitudinal_overlap_m": max(row["longitudinal_overlap_m"] for row in observed),
        "min_lateral_surface_gap_m": min(row["lateral_surface_gap_m"] for row in observed),
        "first_active_frame": active[0]["frame"] if active else None,
        "legal_exception_or_compliance_determined": False,
        "physical_realization_verified": False,
        "tolerance_note": "0.03 m/frame is an engineering stationarity diagnostic, not a legal cutoff",
    }


def _longest(rows):
    run = best = 0
    for row in rows:
        run = run + 1 if row["concurrent_overlap_at_rest"] else 0
        best = max(best, run)
    return best


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(args.map, args.frames)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
