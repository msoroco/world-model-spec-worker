"""Recorded-only NRS 484B.297(6) measurements from original Native sources.

Geometry and timing are engineering observations, never legal due-care,
impassability, side-as-possible or practicability determinations.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from native_scene import CAMERAS, FRAMES, OBSTRUCTION_X, RATE_HZ, SIDEWALK


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()
            if line.strip()]


def original_measurement(attempt):
    attempt = Path(attempt)
    scene = json.loads(required(attempt, "sidewalk_context.json").read_text())
    if (scene.get("source_kind") != "original_native_map_readback" or
            set(scene.get("lanes", {})) != {"roadway", "shoulder", "sidewalk"} or
            len(scene.get("obstruction_actors", [])) != 10 or
            scene.get("legal_highway_status_review_pending") is not True):
        raise ValueError("Original Native sidewalk/obstruction source incomplete")
    people = _rows(attempt, "pedestrian-original.jsonl")
    mapping = _rows(attempt, "video_frames.jsonl")
    cameras = _rows(attempt, "camera-sources.jsonl")
    if not len(people) == len(mapping) == FRAMES:
        raise ValueError("Complete original pedestrian/frame map required")
    if len(cameras) != FRAMES * len(CAMERAS):
        raise ValueError("Four synchronized original source-camera streams required")
    expected_cameras = {name: (width, height) for name, width, height, *_ in CAMERAS}
    camera_seen = set()
    prior = None
    path_m = 0.0
    road_frames = []
    full_return = []
    forward_frames = 0
    for index, (person, frame) in enumerate(zip(people, mapping)):
        center = person.get("center_xy_m")
        feet = person.get("footprint_xy_m")
        if (person.get("video_frame") != index or frame.get("video_frame") != index or
                person.get("native_frame") != frame.get("native_frame") or
                person.get("time_s") != frame.get("time_s") or
                person.get("original_native_observed") is not True or
                not isinstance(center, list) or len(center) != 2 or
                not isinstance(feet, list) or len(feet) != 4 or
                any(not isinstance(point, list) or len(point) != 2 for point in feet)):
            raise ValueError("Original Native pedestrian/frame join differs")
        values = [*center, *(v for point in feet for v in point)]
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in values):
            raise ValueError("Nonfinite original pedestrian body")
        if prior is not None:
            step = math.dist(center, prior)
            if step > .6:
                raise ValueError("Original pedestrian frame discontinuity")
            path_m += step
            forward_frames += center[0] > prior[0]
        prior = center
        if min(point[1] for point in feet) > SIDEWALK[1]:
            road_frames.append(index)
        if min(point[0] for point in feet) > OBSTRUCTION_X[1] and all(
                SIDEWALK[0] <= point[1] <= SIDEWALK[1] for point in feet):
            full_return.append(index)
    for row in cameras:
        name, index = row.get("camera"), row.get("video_frame")
        if name not in expected_cameras or type(index) is not int or not 0 <= index < FRAMES:
            raise ValueError("Original source-camera identity differs")
        key = name, index
        if key in camera_seen:
            raise ValueError("Duplicate source-camera frame")
        camera_seen.add(key)
        width, height = expected_cameras[name]
        if (row.get("native_frame") != mapping[index]["native_frame"] or
                row.get("time_s") != mapping[index]["time_s"] or
                row.get("width") != width or row.get("height") != height or
                row.get("source_path") != name + ".mkv" or
                row.get("source_rgb_sha256") !=
                mapping[index].get("source_rgb_sha256", {}).get(name)):
            raise ValueError("Original source-camera/frame map join differs")
    if camera_seen != {(name, index) for name in expected_cameras
                       for index in range(FRAMES)}:
        raise ValueError("Missing original source-camera frame")
    if not road_frames or not full_return or not road_frames[0] < full_return[0]:
        raise ValueError("No original road entry and full sidewalk return")
    return {"source_kind": "original_native_measurement",
            "frames": FRAMES, "rate_hz": RATE_HZ,
            "first_road_footprint_frame": road_frames[0],
            "last_road_footprint_frame": road_frames[-1],
            "first_full_sidewalk_return_frame": full_return[0],
            "road_footprint_frames": len(road_frames),
            "forward_motion_frames": forward_frames,
            "sampled_path_length_m": path_m,
            "nearest_road_edge_center_distance_m":
                min(abs(people[index]["center_xy_m"][1] - SIDEWALK[1])
                    for index in road_frames),
            "obstruction_actor_count": len(scene["obstruction_actors"]),
            "bike_lane_designation": scene["bike_lane_designation"],
            "actual_obstruction_pixels_review_pending": True,
            "due_care_review_pending": True,
            "as_far_as_possible_review_pending": True,
            "first_practicable_return_review_pending": True,
            "legal_verdict_claimed": False}


def measure_activation(measured):
    return {"pedestrian_road_entry_frame": measured["first_road_footprint_frame"],
            "obstruction_actor_count": measured["obstruction_actor_count"],
            "physical_obstruction_review_pending": True}


def measure_subject(measured):
    return {"source_kind": measured["source_kind"],
            "sampled_frames": measured["frames"]}


def measure_near_side(measured):
    return {"nearest_road_edge_center_distance_m":
            measured["nearest_road_edge_center_distance_m"],
            "as_far_as_possible_review_pending": True}


def measure_direction(measured):
    return {"forward_motion_frames": measured["forward_motion_frames"],
            "traffic_direction_original_review_pending": True}


def measure_bicycle_lane(measured):
    return {"native_map_bicycle_lane_designation": measured["bike_lane_designation"],
            "intervening_area_impassability_review_pending": True}


def measure_return(measured):
    return {"first_full_sidewalk_return_frame":
            measured["first_full_sidewalk_return_frame"],
            "first_practicable_return_review_pending": True}


def measure_scope(measured):
    return {"road_footprint_frames": measured["road_footprint_frames"],
            "sampled_path_length_m": measured["sampled_path_length_m"]}


def derive_channels(attempt, config):
    attempt = Path(attempt)
    people = _rows(attempt, "pedestrian-original.jsonl")
    mapping = _rows(attempt, "video_frames.jsonl")
    scene = json.loads(required(attempt, "sidewalk_context.json").read_text())
    declared = {item["name"] for item in config["recording_description"]["channels"]}
    channels = {name: [] for name in declared}
    path_m = 0.0
    previous = None
    for person, frame in zip(people, mapping):
        center = person["center_xy_m"]
        if previous is None:
            heading = [1.0, 0.0]
        else:
            dx, dy = center[0] - previous[0], center[1] - previous[1]
            distance = math.hypot(dx, dy)
            path_m += distance
            heading = [dx / distance, dy / distance] if distance else [1.0, 0.0]
        previous = center
        values = {
            "ru.subject": person["walker_id"],
            "ru.pedestrian": {"native_actor_id": person["walker_id"]},
            "st.sidewalk": {"native_lane_readback": scene["lanes"]["sidewalk"],
                            "independent_surface_review_pending": True},
            "st.obstruction": {"native_actor_ids": [item["native_actor_id"]
                                                 for item in scene["obstruction_actors"]],
                               "physical_impassability_review_pending": True},
            "st.highway": {"native_roadway_readback": scene["lanes"]["roadway"],
                           "public_status_review_pending": True},
            "st.road_edge": {"sidewalk_side_y_m": SIDEWALK[1],
                             "source": "sidewalk_context.json"},
            "st.intersection": {"junction_source": "road.xodr",
                                "physical_surface_review_pending": True},
            "rel.occupies": {"original_footprint_xy_m": person["footprint_xy_m"],
                             "surface_review_pending": True},
            "kin.position": center,
            "kin.heading": heading,
            "kin.path_length": path_m,
            "kin.time": frame["time_s"],
        }
        if set(values) != declared:
            raise ValueError("declared original channels differ from saved finalizer")
        for name, value in values.items():
            channels[name].append({"time_s": frame["time_s"], "value": value})
    directory = attempt / "channels"
    directory.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (directory / (name + ".jsonl")).write_text(
            "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result, provenance_record
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Fresh saved-only stage required")
    config = json.loads(required(attempt, "config.json").read_text())
    measured = original_measurement(attempt)
    derive_channels(attempt, config)
    inputs = ("pedestrian-original.jsonl", "video_frames.jsonl",
              "camera-sources.jsonl", "sidewalk_context.json")
    hashes = {name: sha(required(attempt, name)) for name in inputs}
    methods = ("measure_activation", "measure_subject", "measure_near_side",
               "measure_direction", "measure_bicycle_lane", "measure_return",
               "measure_scope")
    observations = {name: {"method": name, "value": globals()[name](measured),
                           "sources": hashes} for name in methods}
    report = {"format": "worker-analysis-report-v1", "case_id": config["case_id"],
              "measurements": observations, "legal_verdict_claimed": False}
    result = {"case_id": config["case_id"], "measured_values": measured,
              "target_checks": [{"target": "original blocked sidewalk bypass and return",
                  "requested": True, "measured": True,
                  "method": "original Native body/map/frame join",
                  "tolerance": 0, "matched": True,
                  "physical_cause_confirmed": False,
                  "cause_evidence": list(hashes)}],
              "setup_confirmed": False, "behavior_attempted": True,
              "maneuver_completed": False,
              "termination_reason": "independent physical and practicability review pending",
              "physical_failure_flags": ["original physical review pending"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name, *_ in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": ([{"name": name, "unit": "source",
                                       "reference": name} for name in inputs] +
                                     [{"name": item["name"], "unit": item["unit"],
                                       "reference": item["source"]}
                                      for item in config["recording_description"]["channels"]] +
                                     [{"name": "sidewalk_context", "unit": "source",
                                       "reference": "sidewalk_context.json"}]),
              "realized_observables": {},
              **provenance_record(attempt), "accepted": False,
              "legal_verdict_claimed": False}
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2,
                                                     allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
