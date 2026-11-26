"""Measure source-bound roadway occupancy at a provided overhead crossing.

The output is a measurement, never an automatic legal judgment. In particular
Section 11.30.070 designation and actual right-of-way require separate review.
"""
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    context_path = folder / "crossing-context.json"
    trace_path = folder / "post-tick.jsonl"
    context = json.loads(context_path.read_text())
    if context.get("trace_sha256") != digest(trace_path):
        raise ValueError("original trace hash differs")
    if context.get("frozen_cell") != {"layout": "pedestrian_overpass", "maneuver": "straight", "control": "other_vehicle"}:
        raise ValueError("frozen cell differs")
    if context.get("source_kind") not in ("synthetic_scene_request", "native_post_tick"):
        raise ValueError("source kind missing")
    grade = context.get("grade_separation")
    if not isinstance(grade, dict) or grade.get("road_id") != 2 or grade.get("provided") is not True or grade.get("elevation_m", 0) < 4.5 or grade.get("span_x_m") != [-10, 10]:
        raise ValueError("provided overhead pedestrian crossing survey required")
    if context.get("marked_crosswalk_intervals_y_m") is None or context.get("intersection_intervals_y_m") is None:
        raise ValueError("roadway marking and intersection survey required")
    if context.get("designated_place_prohibition") not in (True, False, None):
        raise ValueError("designated-place review invalid")
    if context.get("pedestrian_id") is None or not context.get("vehicle_ids"):
        raise ValueError("participant inventory required")
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError("600 original 20 Hz frames required")
    pedestrian_id = context["pedestrian_id"]
    inventory = set(context["vehicle_ids"])
    first_entry = None
    last_exit = None
    vehicles_at_entry = set()
    vehicle_trajectories = {v: [] for v in inventory}
    min_vehicle_gap_m = math.inf
    previous_frame = None
    previous_time = None
    for i, row in enumerate(rows):
        frame, time = row.get("native_frame"), row.get("time_s")
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError("original frame or time invalid")
        if previous_frame is not None and (frame != previous_frame + 1 or abs(time - previous_time - .05) > .002):
            raise ValueError("original frame/time continuity differs")
        if row.get("pedestrian_id") != pedestrian_id:
            raise ValueError("pedestrian identity differs")
        body = row.get("pedestrian_footprint_xy_m")
        if not isinstance(body, list) or len(body) != 4 or any(
            not isinstance(v, list) or len(v) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
            for v in body):
            raise ValueError("original pedestrian footprint missing")
        vehicles = row.get("vehicles")
        if not isinstance(vehicles, list) or {v.get("id") for v in vehicles} != inventory:
            raise ValueError("complete vehicle inventory missing")
        for v in vehicles:
            if type(v.get("x_m")) not in (int, float) or type(v.get("y_m")) not in (int, float) or type(v.get("speed_mps")) not in (int, float):
                raise ValueError("vehicle original pose/speed missing")
            if not all(math.isfinite(v[k]) for k in ("x_m", "y_m", "speed_mps")) or v["speed_mps"] < 0:
                raise ValueError("vehicle original pose/speed invalid")
            vehicle_trajectories[v["id"]].append((frame, v["y_m"]))
            min_vehicle_gap_m = min(min_vehicle_gap_m, abs(v["y_m"] - sum(p[1] for p in body)/4))
        occupies_road = max(v[0] for v in body) > -3.5 and min(v[0] for v in body) < 3.5
        if occupies_road:
            if first_entry is None:
                first_entry = row
                vehicles_at_entry = {v["id"] for v in vehicles if abs(v["x_m"]) <= 3.5}
            last_exit = row
        previous_frame, previous_time = frame, time
    if first_entry is None or last_exit is None:
        raise ValueError("roadway occupancy absent")
    ys = [v[1] for v in first_entry["pedestrian_footprint_xy_m"]]
    lo, hi = min(ys), max(ys)
    crossing_y = sum(ys) / len(ys)
    vehicle_crossing_frames = {
        vehicle_id: next((frame for frame, y in samples if abs(y - crossing_y) <= .5), None)
        for vehicle_id, samples in vehicle_trajectories.items()}
    def overlap(interval):
        return not (hi < interval[0] or lo > interval[1])
    provided_at_point = abs(crossing_y - grade["crossing_y_m"]) <= 1.8
    if not provided_at_point:
        raise ValueError("roadway entry is not at provided overhead crossing point")
    marked = any(overlap(v) for v in context["marked_crosswalk_intervals_y_m"])
    intersection = any(overlap(v) for v in context["intersection_intervals_y_m"])
    precedence = {str(v): ("vehicle_first" if vehicle_crossing_frames.get(v) is not None and
                            vehicle_crossing_frames[v] < first_entry["native_frame"]
                            else "pedestrian_first_or_vehicle_unobserved") for v in sorted(vehicles_at_entry)}
    return {
        "format": "c190398-overhead-crossing-source-meter-v1",
        "sources": {"crossing-context.json": digest(context_path), "post-tick.jsonl": digest(trace_path)},
        "source_kind": context["source_kind"], "frames": 600, "rate_hz": 20,
        "roadway_entry_frame": first_entry["native_frame"], "roadway_last_occupancy_frame": last_exit["native_frame"],
        "crossing_y_m": crossing_y, "overhead_crossing_at_entry": provided_at_point,
        "grade_separation": grade,
        "marked_crosswalk_overlap_at_entry": marked, "intersection_at_entry": intersection,
        "outside_both_crosswalk_categories_at_entry": not marked and not intersection,
        "vehicles_on_roadway_at_entry": sorted(vehicles_at_entry),
        "vehicle_conflict_frames": vehicle_crossing_frames, "precedence_at_entry": precedence,
        "minimum_centerline_vehicle_gap_m": min_vehicle_gap_m,
        "designated_place_prohibition": context["designated_place_prohibition"],
        "native_pixels_verified": False, "vehicle_yield_legally_judged": False,
        "law_applicability_conclusion": None,
    }
