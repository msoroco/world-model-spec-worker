"""Saved-only measurements in a surveyed Native road frame for C329610.

Inputs must contain observed Native body samples and map-derived directions.
This does not assign intent, physical success in CARLA, or a legal outcome.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Invalid surveyed Native vector: " + name)
    pair = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in pair) or abs(math.hypot(*pair)-1) > .01:
        raise ValueError("Invalid surveyed Native vector: " + name)
    return pair


def _point(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Invalid surveyed Native point: " + name)
    pair = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in pair):
        raise ValueError("Invalid surveyed Native point: " + name)
    return pair


def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1]


def _relative(a, origin):
    return (a[0]-origin[0], a[1]-origin[1])


def measure(samples_path: Path, geometry_path: Path) -> dict:
    if not samples_path.is_file():
        raise ValueError(f"Missing required source: {samples_path.name}")
    if not geometry_path.is_file():
        raise ValueError(f"Missing required source: {geometry_path.name}")
    geometry = json.loads(geometry_path.read_text())
    for key in ("native_map_sha256", "road_directions_native", "approach_centerline_point_native_m",
                "approach_right_normal_native", "right_half_width_m", "intersection_entry_point_native_m",
                "approach_forward_native", "destination_exit_point_native_m", "destination_forward_native"):
        if key not in geometry:
            raise ValueError("Missing surveyed Native geometry: " + key)
    directions = geometry["road_directions_native"]
    if not isinstance(directions, dict) or set(directions) != {
            "approach_forward", "approach_opposing", "destination_forward", "destination_opposing"}:
        raise ValueError("Native two-way highway evidence missing")
    forward = _vector(geometry["approach_forward_native"], "approach_forward_native")
    destination = _vector(geometry["destination_forward_native"], "destination_forward_native")
    if _dot(forward, destination) > .1 or _dot(forward, destination) < -.1:
        raise ValueError("Surveyed turn is not approximately orthogonal")
    if any(_dot(_vector(directions[a], a), _vector(directions[b], b)) > -.98 for a,b in
           (("approach_forward", "approach_opposing"), ("destination_forward", "destination_opposing"))):
        raise ValueError("Native two-way highway evidence missing")
    if _dot(_vector(directions["approach_forward"], "approach_forward"), forward) < .98 or \
       _dot(_vector(directions["destination_forward"], "destination_forward"), destination) < .98:
        raise ValueError("Native direction survey differs from turn path")
    map_hash = geometry["native_map_sha256"]
    if not isinstance(map_hash, str) or len(map_hash) != 64 or any(c not in "0123456789abcdef" for c in map_hash):
        raise ValueError("Native map hash missing")
    centerline = _point(geometry["approach_centerline_point_native_m"], "approach_centerline")
    right = _vector(geometry["approach_right_normal_native"], "approach_right_normal")
    if abs(_dot(forward, right)) > .01:
        raise ValueError("Approach forward/right axes are not orthogonal")
    width = float(geometry["right_half_width_m"])
    if not math.isfinite(width) or width <= 2:
        raise ValueError("Invalid Native right-half width")
    entry = _point(geometry["intersection_entry_point_native_m"], "entry")
    exit_point = _point(geometry["destination_exit_point_native_m"], "exit")
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("Too few Native motion samples")
    previous = -math.inf
    approach = []
    entry_bracket = None
    for row in rows:
        t = float(row["time_s"])
        if not math.isfinite(t) or t <= previous:
            raise ValueError("Native sample times are not strictly increasing")
        previous = t
        _point(row["native_center_xy_m"], "body center")
        vertices = row["native_body_xy_m"]
        if not isinstance(vertices, list) or len(vertices) != 4:
            raise ValueError("Native body sample incomplete")
        for vertex in vertices:
            _point(vertex, "body vertex")
        _vector(row["native_forward_xy"], "actor forward")
        leading_station = max(_dot(_relative(v, entry), forward) for v in vertices)
        if entry_bracket is None and leading_station >= 0:
            entry_bracket = [approach[-1]["time_s"] if approach else None, t]
        if leading_station < 0:
            approach.append(row)
    if not approach or entry_bracket is None:
        raise ValueError("No observed approach and intersection entry bracket")
    offsets = [_dot(_relative(row["native_center_xy_m"], centerline), right) for row in approach]
    within_right_half = all(0 < _dot(_relative(vertex, centerline), right) < width
                            for row in approach for vertex in row["native_body_xy_m"])
    completed = any(all(_dot(_relative(v, exit_point), destination) > 0 for v in row["native_body_xy_m"])
                    and _dot(row["native_forward_xy"], destination) >= math.cos(math.radians(20))
                    for row in rows)
    return {
        "format": "c329610-saved-geometry-measurement-v2",
        "provenance_kind": "native_samples_required",
        "native_map_sha256": map_hash,
        "approach_window_s": [approach[0]["time_s"], approach[-1]["time_s"]],
        "intersection_entry_time_bracket_s": entry_bracket,
        "center_to_centerline_right_offset_m": {"min": min(offsets), "max": max(offsets), "mean": sum(offsets)/len(offsets)},
        "full_body_within_right_half_on_sampled_approach": within_right_half,
        "destination_exit_observed": completed,
        "sample_count": len(rows),
        "approach_sample_count": len(approach),
        "sources": {samples_path.name: _sha(samples_path), geometry_path.name: _sha(geometry_path)},
        "limitations": ["Native sampled geometry only", "No continuous intersample claim", "No statutory nearest-centerline cutoff", "No legal verdict or intent inference"]
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = measure(args.samples, args.geometry)
    if args.output.exists():
        raise ValueError("Retain prior report; choose a new output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
