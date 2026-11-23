"""Source-bound checks for an NRS 484B.403(3) U-turn capture.

This module consumes original Native map/actor samples. It does not decide
whether a district is legally a business district or issue a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import argparse
from pathlib import Path


class SourceError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def _angle_difference(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _inside_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """Ray-crossing test for the recorded intersection polygon in map XY."""
    inside = False
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[i - 1]
        if (ay > y) != (by > y):
            x_cross = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < x_cross:
                inside = not inside
    return inside


def analyze_native(path: Path, *, expected_case: str, expected_sha256: str) -> dict:
    """Check recorded route/participant sources and return measurements.

    The input is a compact, hash-sealed projection of original Native packets.
    ``district_basis`` must cite an independently reviewed source; this check
    intentionally leaves district classification unresolved.
    """
    _require(sha256(path) == expected_sha256, "Native source hash mismatch")
    packet = json.loads(path.read_text(encoding="utf-8"))
    _require(packet.get("case_id") == expected_case, "case identity mismatch")
    _require(packet.get("actor") == "motor_vehicle_driver", "actor identity mismatch")
    _require(packet.get("map_sha256") and packet.get("route_sha256"), "map/route source binding missing")
    _require(packet.get("district_basis", {}).get("source_sha256"), "district source binding missing")
    boundary = packet.get("intersection_boundary", {})
    polygon = boundary.get("polygon_xy_m", [])
    _require(boundary.get("source_sha256") and len(polygon) >= 3, "intersection boundary source missing")
    _require(all(len(point) == 2 and all(math.isfinite(float(v)) for v in point)
                 for point in polygon), "invalid intersection polygon")
    samples = packet.get("frames", [])
    _require(len(samples) >= 3, "insufficient original frames")
    first = samples[0]["frame"]
    prev_time = -math.inf
    for i, sample in enumerate(samples):
        _require(sample["frame"] == first + i, "noncontiguous original frame map")
        t = sample["time_s"]
        _require(isinstance(t, (int, float)) and math.isfinite(t) and t > prev_time, "invalid original time sequence")
        prev_time = t
        ego = sample.get("ego", {})
        other = sample.get("other_vehicle", {})
        _require(ego.get("id") == packet.get("ego_id"), "ego source identity mismatch")
        _require(other.get("id") == packet.get("other_id"), "other vehicle source identity mismatch")
        _require(ego.get("road_id") is not None and ego.get("lane_id") is not None, "ego map lane missing")
        _require(other.get("road_id") is not None and other.get("lane_id") is not None, "other vehicle map lane missing")
        _require(all(math.isfinite(float(ego[k])) for k in ("x", "y", "yaw_deg")), "invalid ego pose")
        _require(all(math.isfinite(float(other[k])) for k in ("x", "y")), "invalid other vehicle pose")
        corners = ego.get("body_corners_xy_m", [])
        _require(len(corners) >= 4, "ego body footprint missing")
        _require(all(len(point) == 2 and all(math.isfinite(float(v)) for v in point)
                     for point in corners), "invalid ego body footprint")
    start, end = samples[0]["ego"], samples[-1]["ego"]
    _require(start["road_id"] == end["road_id"], "U-turn road continuity missing")
    _require(start["lane_id"] != end["lane_id"], "opposite destination lane missing")
    _require(_angle_difference(start["yaw_deg"], end["yaw_deg"]) >= 135.0, "full reversal not observed")
    junction_frames = [s["frame"] for s in samples if s["ego"].get("junction_id") is not None]
    whole_body_inside_frames = [s["frame"] for s in samples if all(
        _inside_polygon(x, y, polygon) for x, y in s["ego"]["body_corners_xy_m"])]
    distances = [math.hypot(s["ego"]["x"] - s["other_vehicle"]["x"],
                            s["ego"]["y"] - s["other_vehicle"]["y"]) for s in samples]
    return {
        "case_id": expected_case,
        "source_sha256": expected_sha256,
        "frame_count": len(samples),
        "start_frame": first,
        "end_frame": samples[-1]["frame"],
        "reversal_deg": _angle_difference(start["yaw_deg"], end["yaw_deg"]),
        "junction_frames": junction_frames,
        "junction_occupied_during_reversal": bool(junction_frames),
        "whole_body_inside_intersection_frames": whole_body_inside_frames,
        "intersection_boundary_source_sha256": boundary["source_sha256"],
        "minimum_other_vehicle_center_distance_m": min(distances),
        "district_source_sha256": packet["district_basis"]["source_sha256"],
        "district_classification": "unresolved_review",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit sealed original Native U-turn packets")
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_native(args.native, expected_case=args.case, expected_sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
