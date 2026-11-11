"""Preserve source-bound approach and turn context for the 250(2) exception.

Angular observations are engineering measurements. They do not decide whether
the statutory opposite-direction left-turn exception applies.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


SOURCES = ("turn_route_context.json", "road_geometry.json", "crossing_history.jsonl", "video_frames.jsonl")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _angle(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def _bearing(a, b):
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (*a, *b)):
        raise ValueError("Finite route points required")
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < 0.1:
        raise ValueError("Distinct route points required")
    return math.degrees(math.atan2(dy, dx))


def _route(value):
    if not isinstance(value, list) or len(value) < 4 or any(
            not isinstance(p, list) or len(p) != 2 for p in value):
        raise ValueError("Source-bound approach, entry and exit route required")
    first, last = _bearing(value[0], value[1]), _bearing(value[-2], value[-1])
    return {"approach_bearing_deg": first, "exit_bearing_deg": last,
            "route_deflection_deg": _angle(first, last)}


def analyze(root):
    root = Path(root)
    paths = {name: root / name for name in SOURCES}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Missing turn-context source: " + name)
    hashes = {name: _sha(path) for name, path in paths.items()}
    result_path = root / "result.json"
    if result_path.is_file():
        recorded = json.loads(result_path.read_text()).get("source_evidence_hashes", {})
        for name in SOURCES:
            if recorded.get(name) != hashes[name]:
                raise ValueError("Turn-context source differs from saved result: " + name)
    route_context = json.loads(paths["turn_route_context.json"].read_text())
    geometry = json.loads(paths["road_geometry.json"].read_text())
    if route_context.get("intersection_id") != geometry.get("intersection_id"):
        raise ValueError("Turn route context differs from sourced intersection")
    routes = route_context.get("routes", {})
    if not isinstance(routes, dict) or set(routes) != {"ego", "other"}:
        raise ValueError("Both source-bound routes required")
    route_measurements = {who: _route(routes[who]) for who in ("ego", "other")}
    rows = [json.loads(line) for line in paths["crossing_history.jsonl"].read_text().splitlines() if line.strip()]
    frames = [json.loads(line) for line in paths["video_frames.jsonl"].read_text().splitlines() if line.strip()]
    if len(rows) < 2 or len(rows) != len(frames):
        raise ValueError("Original crossing/frame history required")
    first = {}
    for i, (row, frame) in enumerate(zip(rows, frames)):
        if frame.get("carla_frame") != row.get("frame") or frame.get("video_frame") != i or abs(
                frame.get("time_s", float("inf")) - row.get("time_s", float("-inf"))) > 1e-4:
            raise ValueError("Turn-context original frame join failed")
        for who in ("ego", "other"):
            actor = row.get(who, {})
            heading = actor.get("heading_deg")
            if heading is not None and (type(heading) not in (int, float) or not math.isfinite(heading)):
                raise ValueError("Invalid original actor heading: " + who)
            if who not in first:
                first[who] = {"frame": row["frame"], "time_s": row["time_s"],
                              "heading_deg": heading, "native_road_id": actor.get("native_road_id"),
                              "native_lane_id": actor.get("native_lane_id")}
    for who in ("ego", "other"):
        expected = geometry.get(who + "_approach_heading_deg")
        if type(expected) not in (int, float) or not math.isfinite(expected):
            raise ValueError("Sourced approach heading required: " + who)
        if abs(_angle(expected, route_measurements[who]["approach_bearing_deg"])) > 15:
            raise ValueError("Reviewed route conflicts with sourced approach heading: " + who)
        if first[who]["heading_deg"] is not None and abs(_angle(expected, first[who]["heading_deg"])) > 30:
            raise ValueError("Original heading conflicts with sourced approach: " + who)
    difference = _angle(route_measurements["ego"]["approach_bearing_deg"],
                        route_measurements["other"]["approach_bearing_deg"])
    return {"format": "worker-c125751-turn-context-v1",
            "intersection_id": route_context.get("intersection_id"),
            "source_hashes": hashes,
            "approach_difference_deg": difference,
            "routes": route_measurements, "first_original_headings": first,
            "original_heading_complete": all(first[who]["heading_deg"] is not None for who in first),
            "opposite_direction_judgment": "unresolved; map and trajectory review required",
            "left_turn_intention_judgment": "unresolved; route deflection alone is insufficient",
            "statutory_exception_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt), indent=2, allow_nan=False))
