"""Source-bound mountain-road reversal and two-direction 500-foot sight audit.

The operational 1.4 m lane-observer and nine-body-point convention is an
engineering measurement. It does not decide statutory driver visibility.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C129731__NRS-484B-407__motor_vehicle_driver"
LIMIT_M = 152.4
STATIONS_M = (10.0, 50.0, 100.0, 150.0, 152.4)
DIRECTIONS = ("ahead_opposing", "behind_same_direction")
SOURCES = ("frame_map", "ego_motion", "sight_rays", "road_geometry")


def _source(root: Path, entry: dict):
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("source path escapes original attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original sight source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("original sight source hash mismatch")
    return json.loads(raw)


def measure(root: Path, inventory: dict, case_id: str) -> dict:
    root = Path(root)
    if not case_id.startswith(ASSIGNMENT + "__") or inventory.get("case_id") != case_id:
        raise ValueError("exact reversal case mismatch")
    if inventory.get("source_kind") != "original_native":
        raise ValueError("original Native source required")
    sources = inventory.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        raise ValueError("complete sight source inventory required")
    packets = {name: _source(root, sources[name]) for name in SOURCES}
    geometry = packets["road_geometry"]
    if (geometry.get("source_kind") != "original_native_geometry" or
            geometry.get("highway_source") is None or
            geometry.get("location_kind") not in
            ("curve", "approach_to_crest", "near_crest")):
        raise ValueError("original highway curve or crest geometry missing")
    frames = packets["frame_map"].get("frames")
    if not isinstance(frames, list) or len(frames) < 900:
        raise ValueError("original 900-frame history missing")
    first = frames[0].get("frame")
    if type(first) is not int or [r.get("frame") for r in frames] != list(range(first, first + len(frames))):
        raise ValueError("original frame sequence not consecutive")
    times = [r.get("time_s") for r in frames]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or any(
            abs(b - a - .05) > .005 for a, b in zip(times, times[1:])):
        raise ValueError("original frame clock not 20 Hz")
    ego = packets["ego_motion"]
    if ego.get("case_id") != case_id or ego.get("source_kind") != "original_native":
        raise ValueError("original ego motion identity mismatch")
    motion = ego.get("samples")
    if not isinstance(motion, list) or len(motion) != len(frames):
        raise ValueError("original ego motion incomplete")
    for row, frame in zip(motion, frames):
        if row.get("frame") != frame["frame"] or row.get("time_s") != frame["time_s"]:
            raise ValueError("ego frame/time join mismatch")
        if (type(row.get("yaw_deg")) not in (int, float) or
                not math.isfinite(row["yaw_deg"]) or type(row.get("turn_active")) is not bool):
            raise ValueError("original heading or turn phase missing")
    active = [r for r in motion if r["turn_active"]]
    if len(active) < 2:
        raise ValueError("original reversal phase missing")
    heading_change = abs((active[-1]["yaw_deg"] - active[0]["yaw_deg"] + 180) % 360 - 180)
    if heading_change < 150:
        raise ValueError("measured vehicle did not reverse direction")
    rays = packets["sight_rays"]
    if rays.get("case_id") != case_id or rays.get("source_kind") != "original_native":
        raise ValueError("original ray source identity mismatch")
    rows = rays.get("samples")
    if not isinstance(rows, list):
        raise ValueError("original ray history absent")
    expected = {(frame["frame"], direction, station)
                for frame in active for direction in DIRECTIONS for station in STATIONS_M}
    turn_times = {frame["frame"]: frame["time_s"] for frame in active}
    seen = set()
    blocked = {direction: 0 for direction in DIRECTIONS}
    for row in rows:
        key = (row.get("frame"), row.get("direction"), row.get("station_distance_m"))
        if key not in expected or key in seen:
            raise ValueError("ray frame/direction/station outside original turn")
        if row.get("time_s") != turn_times[row["frame"]]:
            raise ValueError("sight ray original frame/time join mismatch")
        seen.add(key)
        points = row.get("body_point_clear")
        if (type(row.get("observer_height_m")) not in (int, float) or
                abs(row["observer_height_m"] - 1.4) > .001 or
                not isinstance(points, list) or len(points) != 9 or
                any(type(value) is not bool for value in points) or
                row.get("target_vehicle_id") != geometry.get("ego_vehicle_id") or
                not row.get("observer_lane_source")):
            raise ValueError("original nine-point sight ray provenance incomplete")
        if not any(points):
            if not row.get("terrain_hit_id"):
                raise ValueError("blocked sight ray lacks actual terrain occluder")
            blocked[row["direction"]] += 1
    if seen != expected:
        raise ValueError("both approach directions lack complete 500-foot sight coverage")
    return {"format": "c129731-original-two-direction-sight-v1",
            "case_id": case_id, "source_sha256": {name: sources[name]["sha256"] for name in SOURCES},
            "original_frames": len(frames), "turn_frames": len(active),
            "location_kind": geometry["location_kind"],
            "measured_heading_change_deg": heading_change,
            "observer_height_m": 1.4, "station_distances_m": list(STATIONS_M),
            "statutory_distance_m": LIMIT_M, "blocked_ray_counts": blocked,
            "rays_checked": len(expected),
            "driver_visibility_judgment": "unresolved"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite original sight measurement")
    inventory = json.loads((args.attempt / "inventory.json").read_text())
    result = measure(args.attempt, inventory, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
