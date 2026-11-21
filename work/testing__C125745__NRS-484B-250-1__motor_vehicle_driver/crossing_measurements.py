"""Measure other-first entry at a stop-sign-controlled median opening.

This preserves Native junction/highway identity, sign-governed approach and
source frames. Entry order is observed even when the official-device exclusion
may make NRS 484B.250(1) inapplicable; no legal verdict is produced.
"""

import hashlib
import json
import math
import shutil
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite Native observation")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _inside(actor, polygon):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete actor body")
    body = MultiPoint([(_number(v[0]), _number(v[1])) for v in vertices]).convex_hull
    return body.intersects(polygon)


def analyze(root: Path) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "ego_highway_id", "other_highway_id",
                "ego_road_id", "other_road_id", "native_stop_sign_id", "sign_governance_source",
                "stop_sign_video_source", "intersection_polygon_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced crossing context: " + key)
    if context["ego_highway_id"] == context["other_highway_id"]:
        raise ValueError("Approaches must be from different highways")
    if context.get("stop_sign_erected") is not True or context.get("stop_sign_governed_road_id") != context["ego_road_id"]:
        raise ValueError("Properly erected governing stop sign not sourced")
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing sourced intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    rows, frames = _rows(root / "crossing_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete crossing/frame history")
    prior = (-1, -math.inf)
    first_entry = {"ego": None, "other": None}
    left_censored = {"ego": False, "other": False}
    prior_inside = {"ego": False, "other": False}
    samples = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original frame/time")
        prior = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_stop_sign_id") != context["native_stop_sign_id"]:
            raise ValueError("Identified governing stop sign not observed")
        sample = {"frame": fid, "time_s": time}
        for who in ("ego", "other"):
            actor = row.get(who)
            if not isinstance(actor, dict) or actor.get("intersection_id") != context["intersection_id"] or actor.get("road_id") != context[who + "_road_id"]:
                raise ValueError("Actor not on sourced junction approach")
            inside = _inside(actor, polygon)
            if index == 0 and inside:
                left_censored[who] = True
            distance = _number(actor.get("distance_to_intersection_m"))
            speed = _number(actor.get("speed_mps"))
            if distance < 0 or speed < 0:
                raise ValueError("Invalid approach distance or speed")
            if inside and not prior_inside[who] and first_entry[who] is None and not left_censored[who]:
                first_entry[who] = {"frame": fid, "time_s": time}
            prior_inside[who] = inside
            sample[who] = {"body_in_intersection": inside, "distance_to_intersection_m": distance,
                           "speed_mps": speed}
        samples.append(sample)
    if first_entry["ego"] is None and not left_censored["ego"]:
        raise ValueError("Ego body entry must be observed or left-censored")
    if first_entry["other"] is None and not left_censored["other"]:
        raise ValueError("Other body entry must be observed or left-censored")
    ego_approaching_at_other_entry = None
    if first_entry["other"] is not None:
        other_frame = first_entry["other"]["frame"]
        other_index = next(i for i, sample in enumerate(samples) if sample["frame"] == other_frame)
        ego_approaching_at_other_entry = (not samples[other_index]["ego"]["body_in_intersection"]
            and samples[other_index]["ego"]["distance_to_intersection_m"] > 0
            and other_index + 1 < len(samples)
            and samples[other_index + 1]["ego"]["distance_to_intersection_m"] < samples[other_index]["ego"]["distance_to_intersection_m"])
    ego_speeds_while_other_inside = [sample["ego"]["speed_mps"] for sample in samples
                                     if sample["other"]["body_in_intersection"] and not sample["ego"]["body_in_intersection"]]
    return {"format": "worker-stop-sign-other-first-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "highway_ids": [context["ego_highway_id"], context["other_highway_id"]],
            "first_body_entry": first_entry,
            "entry_left_censored": left_censored,
            "other_entered_before_ego_observed": (first_entry["other"]["time_s"] < first_entry["ego"]["time_s"]
                                                   if all(first_entry.values()) else None),
            "ego_approaching_at_other_entry_observed": ego_approaching_at_other_entry,
            "minimum_ego_speed_while_other_inside_mps": min(ego_speeds_while_other_inside) if ego_speeds_while_other_inside else None,
            "samples": samples,
            "statutory_roadway_crossing_judgment": "unresolved",
            "official_device_exclusion_judgment": "unresolved; Native stop-sign trigger and images need authority review",
            "right_of_way_judgment": "unresolved"}


def capture_sample(snapshot, world_map, ego, other, sign, crossing_polygon,
                   junction_id, approach_road_ids=None):
    """Build one retained Native row; the caller writes it with the same-frame video map.

    This records full body vertices and live road identities. Distances are
    geometric diagnostics to the reviewed crossing, not legal thresholds.
    """
    polygon = Polygon(crossing_polygon)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid source crossing polygon")
    frame = snapshot.frame
    time_s = snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or frame < 0:
        raise ValueError("Native frame required")
    _number(time_s)
    if ego.id == other.id:
        raise ValueError("Distinct Native vehicles required")
    if approach_road_ids is not None and (
            not isinstance(approach_road_ids, dict) or
            set(approach_road_ids) != {"ego", "other"} or
            any(type(v) is not int for v in approach_road_ids.values()) or
            approach_road_ids["ego"] == approach_road_ids["other"]):
        raise ValueError("Distinct sourced approach road IDs required")
    row = {"frame": frame, "time_s": time_s, "native_stop_sign_id": sign.id}
    for role, actor in (("ego", ego), ("other", other)):
        transform = actor.get_transform()
        waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
        if waypoint is None:
            raise ValueError("Native vehicle left mapped road: " + role)
        if approach_road_ids is not None and not waypoint.is_junction and waypoint.road_id != approach_road_ids[role]:
            raise ValueError("Native approach road differs from sourced road: " + role)
        vertices = actor.bounding_box.get_world_vertices(transform)
        points = [[_number(vertex.x), _number(vertex.y)] for vertex in vertices]
        if len(points) < 4 or MultiPoint(points).convex_hull.area <= 0:
            raise ValueError("Complete Native body required: " + role)
        velocity = actor.get_velocity()
        speed = math.sqrt(sum(_number(value) ** 2 for value in
                              (velocity.x, velocity.y, velocity.z)))
        distance = MultiPoint(points).convex_hull.distance(polygon)
        row[role] = {"actor_id": actor.id, "intersection_id": junction_id,
                     "road_id": approach_road_ids[role] if approach_road_ids is not None else waypoint.road_id,
                     "native_road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
                     "body_vertices_xy_m": points,
                     "distance_to_intersection_m": distance, "speed_mps": speed}
    return row


def finalize_saved(attempt, output):
    """Create channels and a Native result from immutable saved source copies.

    This does not classify official-device authority or legal right of way.
    The finalizer refuses missing originals and stale frame/time joins.
    """
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Fresh saved-processing version required")
    from worker_exchange.native_output import physical_result, write_result
    required = ("config.json", "trace.jsonl", "capture/evidence.jsonl", *REQUIRED,
                "overview.mkv", "approach.mkv", "reference_corner.mkv",
                "driver_reference.mkv")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = "testing__C125745__NRS-484B-250-1__motor_vehicle_driver__stop_sign_other_first"
    if (config.get("selected_case_id") != case_id or
            config.get("law_id") != "NRS-484B-250-1" or
            config.get("cell_id") != "C125745" or
            not config.get("recording_description", {}).get("channels")):
        raise ValueError("Wrong exact C125745(1) capture identity")
    report = analyze(attempt)
    rows, frames, trace = (_rows(attempt / name) for name in
                           ("crossing_history.jsonl", "video_frames.jsonl", "trace.jsonl"))
    if len(rows) != len(frames) or len(trace) != len(frames) or any(
            original.get("frame") != frame.get("carla_frame") or
            original.get("time_s") != frame.get("time_s")
            for original, frame in zip(trace, frames)):
        raise ValueError("Original trace/video frame join failed")
    def center(actor):
        vertices = actor["body_vertices_xy_m"]
        return [sum(_number(p[axis]) for p in vertices) / len(vertices)
                for axis in (0, 1)]
    observations = {
        "ego_speed": ("m/s", lambda row, sample: sample["ego"]["speed_mps"]),
        "other_speed": ("m/s", lambda row, sample: sample["other"]["speed_mps"]),
        "ego_approach_distance": ("m", lambda row, sample: sample["ego"]["distance_to_intersection_m"]),
        "other_approach_distance": ("m", lambda row, sample: sample["other"]["distance_to_intersection_m"]),
        "ego_body_inside": ("boolean", lambda row, sample: sample["ego"]["body_in_intersection"]),
        "other_body_inside": ("boolean", lambda row, sample: sample["other"]["body_in_intersection"]),
        "stop_sign_id": ("Native actor ID", lambda row, sample: row["native_stop_sign_id"]),
        "ego_position": ("m", lambda row, sample: center(row["ego"])),
        "other_position": ("m", lambda row, sample: center(row["other"])),
    }
    expected = {item["name"] for item in config["recording_description"]["channels"]}
    if expected != set(observations):
        raise ValueError("Recording channels differ from saved finalizer")
    evidence_root = attempt / "evidence"
    evidence_root.mkdir()
    for name in ("config.json", "trace.jsonl", *REQUIRED):
        target = evidence_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(attempt / name, target)
    shutil.copytree(attempt / "capture", evidence_root / "capture", dirs_exist_ok=True)
    channels = attempt / "channels"
    channels.mkdir()
    recording_evidence = []
    for name, (unit, method) in observations.items():
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for row, sample in zip(rows, report["samples"]):
                stream.write(json.dumps({"time_s": row["time_s"],
                    "original_frame": row["frame"], "value": method(row, sample)},
                    allow_nan=False) + "\n")
        recording_evidence.append({"name": name, "unit": unit, "reference": reference})
    context_reference = "channels/junction_context.json"
    (attempt / context_reference).write_text(json.dumps({"junction_context":
        json.loads((attempt / "junction_context.json").read_text())},
        allow_nan=False, sort_keys=True) + "\n")
    recording_evidence.append({"name": "junction_context", "unit": "structured record",
                               "reference": context_reference})
    checksums = {"evidence/" + path.relative_to(evidence_root).as_posix():
                 hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in evidence_root.rglob("*") if path.is_file()}
    (attempt / "evidence-checksums.json").write_text(json.dumps(checksums, sort_keys=True) + "\n")
    target = report["other_entered_before_ego_observed"]
    result = {
        "case_id": case_id,
        "measured_values": {"first_body_entry": report["first_body_entry"],
                            "entry_left_censored": report["entry_left_censored"],
                            "ego_approaching_at_other_entry_observed":
                                report["ego_approaching_at_other_entry_observed"]},
        "target_checks": [{"target": "other_enters_before_ego", "requested": True,
            "measured": target, "method": "source-hashed complete-body entry and original frame join",
            "tolerance": 0, "matched": target is True,
            "physical_cause_confirmed": False, "cause_evidence": list(report["sources"])}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "Saved source assessment pending",
        "physical_failure_flags": ["Native sign, crossing and legal judgments require original review"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
                             ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": recording_evidence,
        "source_evidence_hashes": report["sources"],
        "capture_evidence_sha256": hashlib.sha256((attempt / "capture/evidence.jsonl").read_bytes()).hexdigest(),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {"format": "worker-analysis-report", "case_id": case_id,
                "source_report": report, "source_hashes": report["sources"],
                "physical_checks": result["physical_checks"],
                "realized_observables": result["realized_observables"],
                "provenance_kind": result["provenance_kind"],
                "diagnostic_fixture": result["diagnostic_fixture"],
                "legal_verdict_asserted": False, "analysis_complete": True}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize_saved(args.attempt, args.output)


if __name__ == "__main__":
    main()
