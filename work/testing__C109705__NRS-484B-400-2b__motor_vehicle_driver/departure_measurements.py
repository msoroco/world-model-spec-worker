"""Measure a complete body's left-turn exit right of the destination centerline.

Source files are retained original-frame inputs. This is a geometric observation,
not a legal conclusion or a substitute for camera review of map references.
"""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import LineString, MultiPoint, Point, Polygon

REQUIRED = ("road_context.json", "turn_history.jsonl", "video_frames.jsonl")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _points(values, label, minimum):
    if not isinstance(values, list) or len(values) < minimum:
        raise ValueError("Missing " + label)
    result = []
    for value in values:
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("Invalid " + label)
        result.append((_finite(value[0], label + " x"), _finite(value[1], label + " y")))
    return result


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    ctx = json.loads((root / "road_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "approach_road_id", "outgoing_road_id",
                "opposing_lane_source", "destination_centerline_source", "destination_right_half_source",
                "junction_source", "left_turn_route_source"):
        if ctx.get(key) is None:
            raise ValueError("Missing sourced road context: " + key)
    if ctx.get("both_highways_two_directional") is not True or ctx.get("intended_turn") != "left":
        raise ValueError("Two-directional left-turn activation not sourced")
    centerline = LineString(_points(ctx.get("destination_centerline_xy_m"), "destination centerline", 2))
    right_half = Polygon(_points(ctx.get("destination_right_half_polygon_xy_m"), "destination right half", 3))
    junction = Polygon(_points(ctx.get("junction_polygon_xy_m"), "junction", 3))
    if centerline.length <= 0 or not right_half.is_valid or right_half.area <= 0 or not junction.is_valid or junction.area <= 0:
        raise ValueError("Invalid road reference geometry")
    rows, frames = _rows(root / "turn_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete turn/frame history")
    samples = []
    previous = (-1, -math.inf)
    entered = False
    exited = False
    for i, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = fid, time
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        body = MultiPoint(_points(row.get("ego_body_vertices_xy_m"), "ego body", 4)).convex_hull
        if body.area <= 0:
            raise ValueError("Degenerate vehicle body")
        intersects = body.intersects(junction)
        if intersects:
            entered = True
        if entered and not intersects and not exited:
            if row.get("road_id") != ctx["outgoing_road_id"]:
                raise ValueError("Exit is not on sourced destination road")
            exited = True
            samples.append({"frame": fid, "time_s": time, "road_id": row["road_id"],
                            "complete_body_right_of_destination_centerline": right_half.covers(body) and not body.intersects(centerline),
                            "body_in_destination_right_half": right_half.covers(body),
                            "body_intersects_centerline": body.intersects(centerline),
                            "body_centroid_distance_to_centerline_m": centerline.distance(body.centroid),
                            "minimum_vertex_distance_to_centerline_m": min(centerline.distance(Point(p)) for p in _points(row["ego_body_vertices_xy_m"], "ego body", 4))})
    if not entered or not exited:
        raise ValueError("No observed intersection entry then complete-body exit")
    return {"format": "worker-left-turn-destination-exit-observations", "sources": hashes,
            "native_road_context": ctx, "exit_sample": samples[0],
            "legal_conclusion": "unresolved pending source geometry and physical review"}


def measure_two_way_turn_entry(observations: dict) -> dict:
    context = observations["native_road_context"]
    return {"both_highways_two_directional": context["both_highways_two_directional"],
            "intended_turn": context["intended_turn"],
            "intersection_id": context["intersection_id"],
            "observed_complete_body_exit_frame": observations["exit_sample"]["frame"],
            "source_status": "synthetic diagnostic; Native physical status unverified"}


def measure_destination_exit(observations: dict) -> dict:
    sample = observations["exit_sample"]
    return {"frame": sample["frame"], "time_s": sample["time_s"],
            "destination_road_id": sample["road_id"],
            "body_in_destination_right_half": sample["body_in_destination_right_half"],
            "body_intersects_centerline": sample["body_intersects_centerline"],
            "complete_body_right_of_destination_centerline":
                sample["complete_body_right_of_destination_centerline"]}


def measure_centerline_branch_exit(observations: dict) -> dict:
    context, sample = observations["native_road_context"], observations["exit_sample"]
    return {"centerline_kind": context["site_source_review"]["centerline_kind"],
            "body_centroid_distance_to_centerline_m":
                sample["body_centroid_distance_to_centerline_m"],
            "minimum_vertex_distance_to_centerline_m":
                sample["minimum_vertex_distance_to_centerline_m"],
            "legal_nearest_judgment": "unresolved; no statutory numeric cutoff"}


def finalize(attempt: Path, output: Path) -> dict:
    """Rebuild the destination exit channel from retained original sources only."""
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Use fresh saved analysis output and retain original evidence")
    required = ("config.json", "site_packet.json", "road_context.json", "road_geometry.json",
                "turn_history.jsonl", "body_history.jsonl", "video_frames.jsonl",
                "trace.jsonl", "capture/evidence.jsonl",
                "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    packet = json.loads((attempt / "site_packet.json").read_text())
    case = config.get("selected_case_id")
    prefix = "testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__source_verified_"
    if not isinstance(case, str) or not case.startswith(prefix) or case not in config.get("supported_case_ids", []):
        raise ValueError("Exact saved C109705(2b) case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-400-2b", "C109705", "motor_vehicle_driver"):
        raise ValueError("Exact saved law, cell or actor differs")
    expected_kind = "imaginary" if "imaginary_" in case else "marked"
    if packet.get("centerline_kind") != expected_kind:
        raise ValueError("Selected case destination centerline kind differs")
    observations = analyze(attempt)
    context, sample = observations["native_road_context"], observations["exit_sample"]
    if context.get("site_source_review", {}).get("centerline_kind") != expected_kind:
        raise ValueError("Saved road context centerline review differs")
    if any(context.get(key) != packet.get(key) for key in (
            "native_map_id", "intersection_id", "approach_road_id", "outgoing_road_id",
            "destination_centerline_xy_m", "destination_right_half_polygon_xy_m",
            "junction_polygon_xy_m")):
        raise ValueError("Saved road context differs from selected source packet")
    if not sample["complete_body_right_of_destination_centerline"]:
        raise ValueError("Complete exit body crosses destination centerline or right-half boundary")
    frames, trace = _rows(attempt / "video_frames.jsonl"), _rows(attempt / "trace.jsonl")
    if len(trace) != len(frames) or any(
            row.get("frame") != frame.get("carla_frame") or row.get("time_s") != frame.get("time_s")
            for row, frame in zip(trace, frames)):
        raise ValueError("Original trace/frame join differs")
    body_rows, turn_rows = _rows(attempt / "body_history.jsonl"), _rows(attempt / "turn_history.jsonl")
    if len(body_rows) != len(frames) or any(
            row.get("frame") != frame.get("carla_frame") or row.get("time_s") != frame.get("time_s") or
            row.get("road_id") != turn.get("road_id") or
            len(row.get("body_vertices_m", [])) < 4 or
            [v[:2] for v in row["body_vertices_m"]] != turn.get("ego_body_vertices_xy_m")
            for row, turn, frame in zip(body_rows, turn_rows, frames)):
        raise ValueError("Original full-body/frame join differs")
    geometry = json.loads((attempt / "road_geometry.json").read_text())
    if (geometry.get("departure_road_id") != context["outgoing_road_id"] or
            geometry.get("approach_road_id") != context["approach_road_id"] or
            geometry.get("intersection_xy_m") != context["junction_polygon_xy_m"] or
            geometry.get("connector_road_id") != packet.get("connector_road_id") or
            geometry.get("departure_direction_xy") != packet.get("departure_direction_xy") or
            geometry.get("two_way") is not True):
        raise ValueError("Saved connector road geometry differs from source context")
    sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest() for name in required}
    measured = {"destination_centerline_kind": expected_kind,
                "exit_frame": sample["frame"], "exit_time_s": sample["time_s"],
                "complete_body_right_of_destination_centerline": True,
                "body_centroid_distance_to_centerline_m": sample["body_centroid_distance_to_centerline_m"],
                "minimum_vertex_distance_to_centerline_m": sample["minimum_vertex_distance_to_centerline_m"],
                "legal_conclusion": "unresolved"}
    for key, method, inputs, value in (
            ("two_way_turn_entry", "measure_two_way_turn_entry",
             ("road_context.json", "turn_history.jsonl", "video_frames.jsonl"),
             measure_two_way_turn_entry(observations)),
            ("complete_destination_exit", "measure_destination_exit",
             ("road_context.json", "turn_history.jsonl", "video_frames.jsonl"),
             measure_destination_exit(observations)),
            ("centerline_branch_exit", "measure_centerline_branch_exit",
             ("road_context.json", "turn_history.jsonl", "video_frames.jsonl"),
             measure_centerline_branch_exit(observations))):
        measured[key] = {"method": method, "value": value,
                         "sources": {name: sources[name] for name in inputs}}
    channels = attempt / "channels"
    channels.mkdir()
    (channels / "destination_exit_context.json").write_text(json.dumps({
        "case_id": case, "measured_values": measured, "source_evidence_hashes": sources,
        "destination_exit_context": {"road_context": context,
                                     "road_geometry": geometry,
                                     "departure_sample": sample},
        "legal_conclusion": "unresolved"}, indent=2, allow_nan=False) + "\n")
    (channels / "destination_exit.jsonl").write_text(json.dumps({
        "time_s": sample["time_s"], "value": sample}, allow_nan=False) + "\n")
    description = config.get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("Saved recording description missing")
    result = {"case_id": case, "measured_values": measured,
              "target_checks": [{"target": "complete_body_right_of_destination_centerline",
                                 "requested": True, "measured": True,
                                 "method": "original frame joined full-body polygon against sourced destination line and right half",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": ["road_context.json", "turn_history.jsonl", "video_frames.jsonl"]}],
              "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original-source analysis; physical and legal review pending",
              "physical_failure_flags": ["actual Native motion and camera visibility not independently accepted"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description,
              "recording_evidence": [{"name": "destination_exit_context", "unit": "structured record",
                                      "reference": "channels/destination_exit_context.json"},
                                     {"name": "destination_exit", "unit": "structured record",
                                      "reference": "channels/destination_exit.jsonl"}],
              "source_evidence_hashes": sources,
              "capture_evidence_sha256": sources["capture/evidence.jsonl"],
              "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {"format": "worker-c109705-destination-saved-analysis", "case_id": case,
              "measurements": measured, "sources": sources,
              "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"case_id": finalize(args.attempt, args.output)["case_id"],
                      "physical_acceptance_claimed": False}))
