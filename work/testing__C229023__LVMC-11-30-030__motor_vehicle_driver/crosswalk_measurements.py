"""Source-bound physical measurements for LVMC 11.30.030.

The module records position and motion. It never concludes that a driver had a
particular purpose, that an unmarked crossing legally exists, or that a pass
violated the ordinance.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C229023__LVMC-11-30-030__motor_vehicle_driver"
CASE_SUFFIXES = ("unmarked_wait", "unmarked_pass", "marked_wait", "marked_pass",
                 "unmarked_other_stop_wait", "unmarked_other_stop_pass")
EXPECTED_CONTEXT = {
    "unmarked_wait": ("unmarked", "permit_pedestrian"),
    "unmarked_pass": ("unmarked", "permit_pedestrian"),
    "marked_wait": ("marked", "permit_pedestrian"),
    "marked_pass": ("marked", "permit_pedestrian"),
    "unmarked_other_stop_wait": ("unmarked", "other"),
    "unmarked_other_stop_pass": ("unmarked", "other"),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError("finite two-dimensional point required")
    return value


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            at_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < at_x:
                inside = not inside
    return inside


def _projection(point, origin, axis):
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def _body_extents(vertices, origin, axis):
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("eight original world-space body vertices required")
    stations = []
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vertex):
            raise ValueError("finite three-dimensional body vertex required")
        stations.append(_projection(vertex[:2], origin, axis))
    if max(stations) - min(stations) <= 0:
        raise ValueError("body has no longitudinal extent")
    return min(stations), max(stations)


def measure(*, case_id, context_path, trace_path, receipt_path):
    """Reopen original bytes and report observed crosswalk approach/pass sequence."""
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in CASE_SUFFIXES}:
        raise ValueError("unknown exact case ID")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("case_id") != case_id or receipt.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("source receipt identity mismatch")
    if receipt.get("diagnostic_fixture"):
        raise ValueError("diagnostic fixture is not original delivery evidence")
    if _sha(context_path) != receipt.get("context_sha256") or _sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not context.get("map_sha256") or len(context["map_sha256"]) != 64:
        raise ValueError("context/map identity missing")
    if context.get("layout") != "intersection" or context.get("junction_kind") != "road_intersection":
        raise ValueError("actual road intersection context required")
    crossing = context.get("crosswalk")
    if not isinstance(crossing, dict) or crossing.get("kind") not in ("marked", "unmarked"):
        raise ValueError("crosswalk kind missing")
    polygon = crossing.get("polygon")
    if not isinstance(polygon, list) or len(polygon) < 4:
        raise ValueError("crosswalk polygon missing")
    polygon = [_point(p) for p in polygon]
    if crossing["kind"] == "unmarked":
        for key in ("opposite_sidewalk_lateral_lines", "curb_or_traveled_edge_sources"):
            if not crossing.get(key):
                raise ValueError("unmarked crosswalk geometry source missing: " + key)
    else:
        if not crossing.get("marking_source"):
            raise ValueError("marked crosswalk source missing")
    purpose = context.get("stopped_vehicle_purpose")
    if not isinstance(purpose, dict) or purpose.get("claim") not in ("permit_pedestrian", "other") or not purpose.get("source_ref"):
        raise ValueError("stopped vehicle purpose needs an independent source")
    expected_crossing, expected_purpose = EXPECTED_CONTEXT[case_id[len(ASSIGNMENT_ID) + 2:]]
    if crossing["kind"] != expected_crossing or purpose["claim"] != expected_purpose:
        raise ValueError("original crossing kind or stopped purpose differs from exact case")
    if not context.get("pedestrian_identity") or not context.get("lead_vehicle_identity") or not context.get("ego_vehicle_identity"):
        raise ValueError("all three actor identities required")
    road = context.get("road_axis")
    if not isinstance(road, dict):
        raise ValueError("road axis missing")
    origin = _point(road.get("origin"))
    axis = _point(road.get("forward"))
    norm = math.hypot(*axis)
    if abs(norm - 1.0) > 0.02:
        raise ValueError("road forward axis must be unit length")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) != receipt.get("frame_count") or len(rows) < 2 or receipt.get("fps") != 20:
        raise ValueError("20 Hz original frame count mismatch")
    observations = []
    prev = None
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        if isinstance(frame, bool) or not isinstance(frame, int) or isinstance(time_s, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError("original frame/time missing")
        if prev is not None and (frame != prev[0] + 1 or abs(time_s - prev[1] - .05) > .002):
            raise ValueError("original frame order or cadence mismatch")
        prev = frame, time_s
        ego = _point(row.get("ego_center"))
        lead = _point(row.get("lead_center"))
        pedestrian = _point(row.get("pedestrian_center"))
        ego_rear, ego_front = _body_extents(row.get("ego_vertices"), origin, axis)
        lead_rear, lead_front = _body_extents(row.get("lead_vertices"), origin, axis)
        for key in ("ego_speed_mps", "lead_speed_mps"):
            if isinstance(row.get(key), bool) or not isinstance(row.get(key), (int, float)) or not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError("original speed missing or invalid")
        observations.append({"frame": frame, "time_s": time_s,
                             "ego_station_m": _projection(ego, origin, axis),
                             "lead_station_m": _projection(lead, origin, axis),
                             "ego_rear_station_m": ego_rear, "ego_front_station_m": ego_front,
                             "lead_rear_station_m": lead_rear, "lead_front_station_m": lead_front,
                             "ego_speed_mps": row["ego_speed_mps"],
                             "lead_speed_mps": row["lead_speed_mps"],
                             "pedestrian_in_crosswalk": _inside(pedestrian, polygon)})
    # These are sampled engineering observations, not statutory thresholds.
    rear_approach_frames = [r["frame"] for r in observations if r["ego_front_station_m"] < r["lead_rear_station_m"]]
    stopped_frames = [r["frame"] for r in observations if r["lead_speed_mps"] <= .1]
    pass_frames = [r["frame"] for r in observations if r["ego_rear_station_m"] > r["lead_front_station_m"]]
    crossing_frames = [r["frame"] for r in observations if r["pedestrian_in_crosswalk"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": _sha(context_path), "trace_sha256": _sha(trace_path),
                                "receipt_sha256": _sha(receipt_path), "map_sha256": context["map_sha256"]},
            "crosswalk_kind": crossing["kind"], "stopped_vehicle_purpose_claim": purpose["claim"],
            "purpose_source_ref": purpose["source_ref"], "frame_count": len(observations),
            "rear_approach_frames": rear_approach_frames, "lead_stopped_frames": stopped_frames,
            "ego_ahead_frames": pass_frames, "pedestrian_crosswalk_frames": crossing_frames,
            "observations": observations, "legal_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(case_id=args.case, context_path=args.context,
                     trace_path=args.trace, receipt_path=args.receipt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
