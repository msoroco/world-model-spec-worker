"""Source-bound saved pedestrian bypass measurements for NRS 484B.297(6).

Reads original-shaped frame, body, obstruction and traffic histories. A fixture
may exercise the same computation, but is labelled diagnostic and never accepted
as physical or legal evidence. No CARLA connection is made here.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

REQUIRED = ("site-survey.json", "video_frames.jsonl", "pedestrian_history.jsonl",
            "obstruction_history.jsonl", "traffic_history.jsonl")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"empty saved source: {path.name}")
    return rows


def _point(value, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) < 2 or not all(_finite(v) for v in value[:2]):
        raise ValueError(f"missing finite {name}")
    return float(value[0]), float(value[1])


def _local(point, transform):
    x, y = _point(point, "world point")
    angle = math.radians(transform["yaw_degrees"])
    dx, dy = x - transform["x"], y - transform["y"]
    return (dx * math.cos(angle) + dy * math.sin(angle),
            -dx * math.sin(angle) + dy * math.cos(angle))


def _inside(point, bounds):
    x, y = point
    return bounds[0] <= x <= bounds[1] and bounds[2] <= y <= bounds[3]


def _polygon_bounds(vertices, transform, name):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError(f"missing observed {name} geometry")
    points = [_local(vertex, transform) for vertex in vertices]
    return [min(p[0] for p in points), max(p[0] for p in points),
            min(p[1] for p in points), max(p[1] for p in points)]


def _within_bounds(box, surface, tolerance=1e-6):
    return (box[0] >= surface[0] - tolerance and box[1] <= surface[1] + tolerance and
            box[2] >= surface[2] - tolerance and box[3] <= surface[3] + tolerance)


def _bounds(survey, name):
    value = survey.get("surface_bounds_local_m", {}).get(name)
    if not isinstance(value, list) or len(value) != 4 or not all(_finite(x) for x in value):
        raise ValueError(f"missing surveyed bounds: {name}")
    if value[0] >= value[1] or value[2] >= value[3]:
        raise ValueError(f"invalid surveyed bounds: {name}")
    return value


def measure_saved(root: Path, expected_case_id: str) -> dict:
    """Compute observable histories from digest-bound saved acquisition only."""
    root = Path(root)
    packet_path = root / "source-packet.json"
    packet = json.loads(packet_path.read_text())
    if packet.get("case_id") != expected_case_id:
        raise ValueError("saved source exact case mismatch")
    kind = packet.get("source_kind")
    if kind not in ("original_saved_acquisition", "synthetic_fixture"):
        raise ValueError("unknown saved acquisition provenance")
    bindings = packet.get("files")
    if not isinstance(bindings, dict) or set(bindings) != set(REQUIRED):
        raise ValueError("missing exact saved source binding")
    hashes = {}
    for name in REQUIRED:
        binding = bindings[name]
        if not isinstance(binding, dict) or binding.get("path") != name:
            raise ValueError(f"nonlocal or mismatched source binding: {name}")
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing required saved source: {name}")
        digest = _sha(path)
        if digest != binding.get("sha256"):
            raise ValueError(f"saved source digest mismatch: {name}")
        hashes[name] = digest
    survey = json.loads((root / "site-survey.json").read_text())
    if survey.get("cell_id") != "C104081" or survey.get("layout") != "hill_crest":
        raise ValueError("saved survey cell/layout mismatch")
    if kind == "original_saved_acquisition":
        if survey.get("source_kind") != "original_native_map_survey":
            raise ValueError("original saved acquisition lacks original Native survey")
        for name in ("sidewalk", "intervening_area", "designated_bicycle_lane", "immediately_adjacent_highway"):
            if survey.get("surfaces", {}).get(name, {}).get("surveyed") is not True:
                raise ValueError("original Native survey lacks observed surface: " + name)
    transform = survey.get("local_to_world", {})
    if not all(_finite(transform.get(k)) for k in ("x", "y", "yaw_degrees")):
        raise ValueError("survey lacks finite local-to-world transform")
    sidewalk = _bounds(survey, "sidewalk")
    area = _bounds(survey, "intervening_area")
    lane = _bounds(survey, "designated_bicycle_lane")
    highway = _bounds(survey, "immediately_adjacent_highway")
    if area[3] != sidewalk[2] or lane[3] != area[2] or highway[3] != sidewalk[2]:
        raise ValueError("surveyed surfaces are not contiguous")
    mapping = _rows(root / "video_frames.jsonl")
    pedestrian = _rows(root / "pedestrian_history.jsonl")
    obstructions = _rows(root / "obstruction_history.jsonl")
    traffic = _rows(root / "traffic_history.jsonl")
    if not (len(mapping) == len(pedestrian) == len(obstructions) == len(traffic)) or len(mapping) < 3:
        raise ValueError("saved history lengths or sample count mismatch")
    previous_frame = -1
    previous_time = -1.0
    centers = []
    lane_frames = []
    highway_frames = []
    sidewalk_frames = []
    obstruction_ends = set()
    obstruction_kinds = set()
    barrier_states = set()
    traffic_context = []
    obstruction_geometry = set()
    barrier_geometry = set()
    for index, (frame_map, walker, obstacle, vehicle) in enumerate(zip(mapping, pedestrian, obstructions, traffic)):
        frame = frame_map.get("carla_frame")
        time = frame_map.get("time_s")
        if type(frame) is not int or frame <= previous_frame or not _finite(time) or time <= previous_time:
            raise ValueError("original frame identity is nonmonotonic")
        if index and abs((time - previous_time) - 0.05) > 1e-3:
            raise ValueError("saved acquisition is not at pinned 20 Hz")
        if frame_map.get("video_frame") != index:
            raise ValueError("original video frame index mismatch")
        for row in (walker, obstacle, vehicle):
            if row.get("frame") != frame or not _finite(row.get("time_s")) or abs(row["time_s"] - time) > 1e-4:
                raise ValueError("saved histories do not join original frame/time")
        vertices = walker.get("body_vertices_world_m")
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ValueError("missing complete walker body vertices")
        points = [_local(vertex, transform) for vertex in vertices]
        center = ((min(p[0] for p in points) + max(p[0] for p in points)) / 2,
                  (min(p[1] for p in points) + max(p[1] for p in points)) / 2)
        if not _inside(center, sidewalk) and not _inside(center, highway):
            raise ValueError("pedestrian center leaves surveyed sidewalk/highway")
        centers.append(center)
        if _inside(center, lane): lane_frames.append(frame)
        if _inside(center, highway) and not _inside(center, sidewalk): highway_frames.append(frame)
        if _inside(center, sidewalk): sidewalk_frames.append(frame)
        if type(obstacle.get("intervening_barrier_present")) is not bool:
            raise ValueError("missing observed intervening barrier state")
        barrier_states.add(obstacle["intervening_barrier_present"])
        obstruction_box = _polygon_bounds(obstacle.get("sidewalk_obstruction_vertices_world_m"),
                                          transform, "sidewalk obstruction")
        if not _within_bounds(obstruction_box, sidewalk):
            raise ValueError("observed sidewalk obstruction leaves surveyed sidewalk")
        obstruction_geometry.add(tuple(round(v, 3) for v in obstruction_box))
        if obstacle["intervening_barrier_present"]:
            barrier_box = _polygon_bounds(obstacle.get("intervening_barrier_vertices_world_m"),
                                          transform, "intervening barrier")
            if not _within_bounds(barrier_box, area):
                raise ValueError("observed barrier leaves surveyed intervening area")
            barrier_geometry.add(tuple(round(v, 3) for v in barrier_box))
        elif obstacle.get("intervening_barrier_vertices_world_m"):
            raise ValueError("unreported observed intervening barrier geometry")
        end = obstacle.get("sidewalk_obstruction_end_local_m")
        if not _finite(end): raise ValueError("missing observed sidewalk obstruction extent")
        obstruction_ends.add(float(end))
        obstruction_kinds.add(obstacle.get("sidewalk_obstruction_kind"))
        if not _finite(vehicle.get("nearest_traffic_distance_m")) or vehicle["nearest_traffic_distance_m"] < 0:
            raise ValueError("missing finite traffic context")
        traffic_context.append(float(vehicle["nearest_traffic_distance_m"]))
        previous_frame, previous_time = frame, time
    if (len(barrier_states) != 1 or len(obstruction_ends) != 1 or
            len(obstruction_kinds) != 1 or len(obstruction_geometry) != 1 or
            len(barrier_geometry) > 1):
        raise ValueError("observed obstruction state changed during comparison")
    if obstruction_kinds.pop() not in ("impassable_section", "missing_section"):
        raise ValueError("unknown observed obstruction kind")
    kind_value = obstacle["sidewalk_obstruction_kind"]
    observed_end = next(iter(obstruction_ends))
    observed_box = next(iter(obstruction_geometry))
    if abs(observed_box[1] - observed_end) > 0.25:
        raise ValueError("observed sidewalk geometry disagrees with obstruction extent")
    if kind_value == "missing_section" and [round(observed_box[0], 3), round(observed_box[1], 3)] not in survey.get("observed_missing_sidewalk_intervals_local_m", []):
        raise ValueError("missing sidewalk section absent from source survey")
    if not sidewalk_frames or not highway_frames:
        raise ValueError("source lacks sidewalk-to-highway bypass")
    first_highway = highway_frames[0]
    last_highway = highway_frames[-1]
    if not any(f < first_highway for f in sidewalk_frames) or not any(f > last_highway for f in sidewalk_frames):
        raise ValueError("source lacks sidewalk origin or return")
    dx = centers[-1][0] - centers[0][0]
    if abs(dx) < 0.1: raise ValueError("saved route has no longitudinal travel")
    direction = 1 if dx > 0 else -1
    if direction != survey.get("original_sidewalk_direction"):
        raise ValueError("saved travel direction differs from original sidewalk direction")
    first_return = min(f for f in sidewalk_frames if f > last_highway)
    center_by_frame = {r["frame"]: p for r, p in zip(pedestrian, centers)}
    return {
        "format": "worker-saved-pedestrian-bypass-measurement", "case_id": expected_case_id,
        "provenance_kind": kind, "diagnostic_fixture": kind == "synthetic_fixture",
        "source_sha256": hashes, "source_packet_sha256": _sha(packet_path),
        "sample_count": len(mapping), "first_frame": mapping[0]["carla_frame"],
        "last_frame": mapping[-1]["carla_frame"], "observables": {
            "pedestrian_direction": direction, "designated_lane_used": bool(lane_frames),
            "designated_lane_frames": lane_frames, "highway_frames": highway_frames,
            "intervening_barrier_present": barrier_states.pop(),
            "sidewalk_obstruction_end_m": observed_end,
            "sidewalk_obstruction_bounds_local_m": list(observed_box),
            "intervening_barrier_bounds_local_m": list(next(iter(barrier_geometry))) if barrier_geometry else None,
            "sidewalk_obstruction_kind": kind_value,
            "first_sidewalk_return_frame": first_return,
            "return_center_local_m": list(center_by_frame[first_return]),
            "lateral_distance_to_sidewalk_edge_m": [sidewalk[2] - center_by_frame[f][1] for f in highway_frames],
            "nearest_traffic_distance_m": traffic_context,
        },
        "legal_judgment": "unresolved", "physical_acceptance": "not_assessed",
    }


def comparison_projection(root: Path, expected_case_id: str) -> dict:
    """Derive comparison fields from the measured saved histories and survey.

    The downstream comparison audit still rejects synthetic fixture provenance.
    A local operator must independently verify Native ownership of the sources.
    """
    root = Path(root)
    receipt = measure_saved(root, expected_case_id)
    packet = json.loads((root / "source-packet.json").read_text())
    survey = json.loads((root / "site-survey.json").read_text())
    context = packet.get("capture_context", {})
    if not isinstance(context, dict) or not isinstance(context.get("pedestrian_blueprint"), str) or not context["pedestrian_blueprint"]:
        raise ValueError("missing saved pedestrian blueprint")
    traffic_plan_hash = context.get("traffic_plan_sha256")
    if not isinstance(traffic_plan_hash, str) or len(traffic_plan_hash) != 64 or any(c not in "0123456789abcdef" for c in traffic_plan_hash):
        raise ValueError("missing bound traffic plan hash")
    camera_hash = context.get("camera_profile_sha256")
    if not isinstance(camera_hash, str) or len(camera_hash) != 64 or any(c not in "0123456789abcdef" for c in camera_hash):
        raise ValueError("missing bound camera profile hash")
    values = receipt["observables"]
    return {
        "source_kind": receipt["provenance_kind"], "case_id": expected_case_id,
        "cell_id": survey["cell_id"], "actor": "pedestrian", "map_id": survey.get("map_id"),
        "pedestrian_blueprint": context["pedestrian_blueprint"],
        "traffic_plan_sha256": traffic_plan_hash,
        "camera_profile_sha256": camera_hash, "duration_frames": receipt["sample_count"],
        "intervening_barrier_present": values["intervening_barrier_present"],
        "designated_lane_used": values["designated_lane_used"],
        "pedestrian_direction": values["pedestrian_direction"],
        "sidewalk_obstruction_end_m": values["sidewalk_obstruction_end_m"],
        "sidewalk_obstruction_kind": values["sidewalk_obstruction_kind"],
        "measurement_sources_sha256": receipt["source_sha256"],
        "source_packet_sha256": receipt["source_packet_sha256"],
        "physical_acceptance": "not_assessed", "legal_judgment": "unresolved",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--comparison-packet", action="store_true")
    args = parser.parse_args()
    result = (comparison_projection(args.attempt, args.case) if args.comparison_packet
              else measure_saved(args.attempt, args.case))
    output = Path(args.output)
    if output.exists():
        raise ValueError("preserve prior saved analysis; use a fresh output path")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case, "diagnostic_fixture": result["source_kind"] == "synthetic_fixture" if args.comparison_packet else result["diagnostic_fixture"]}))


if __name__ == "__main__":
    main()
