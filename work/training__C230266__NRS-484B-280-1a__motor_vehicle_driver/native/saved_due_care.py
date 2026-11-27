"""Join immutable Native encounter sources and compute diagnostics, not a legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from due_care_meter import FRAMES, digest, measure

ASSIGNMENT = "training__C230266__NRS-484B-280-1a__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_90e3f1aa__condition_a",
         ASSIGNMENT + "__selected_90e3f1aa__condition_b"}
SOURCES = ("pedestrian-due-care-trace.jsonl", "video_frames.jsonl",
           "contact_events.jsonl", "road_survey.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def join(attempt, case_id, *, allow_fixture=False):
    root = Path(attempt)
    if case_id not in CASES:
        raise ValueError("Exact selected case differs")
    source_paths = {name: root / name for name in SOURCES}
    for name, path in source_paths.items():
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
    source_hashes = {name: sha(path) for name, path in source_paths.items()}
    trace, frame_map, events = (rows(source_paths[name]) for name in SOURCES[:3])
    survey = json.loads(source_paths[SOURCES[3]].read_text())
    if len(trace) != FRAMES or len(frame_map) != FRAMES:
        raise ValueError("Full 600-frame trace and frame map required")
    expected_kind = "synthetic_native_sample" if allow_fixture else "original_native_observation"
    if survey.get("source_kind") != ("synthetic_native_sample" if allow_fixture else "original_native_road_survey"):
        raise ValueError("Road survey provenance differs")
    if not survey.get("road_boundary_source") or not survey.get("pedestrian_classification_source") or \
            not survey.get("control_relationship_source") or \
            type(survey.get("pedestrian_crosses_vehicle_path")) is not bool:
        raise ValueError("Independent pedestrian path survey missing")
    event_frames = {}
    for event in events:
        native = event.get("native_frame")
        if type(native) is not int or type(event.get("other_actor_id")) is not int or \
                type(event.get("pedestrian_contact")) is not bool or \
                type(event.get("sensor_actor_id")) is not int:
            raise ValueError("Malformed original contact event")
        event_frames.setdefault(native, []).append(event)
    joined = []
    vehicle_ids, pedestrian_ids, sensor_ids = set(), set(), set()
    for i, (row, mapping) in enumerate(zip(trace, frame_map)):
        native = row.get("native_frame")
        if row.get("source_kind") != expected_kind or row.get("frame") != i or \
                row.get("video_frame") != i or mapping.get("video_frame") != i or \
                mapping.get("native_frame") != native or mapping.get("carla_frame") != native or \
                row.get("time_s") != mapping.get("time_s"):
            raise ValueError("Original Native, video and time join differs")
        if type(native) is not int or (i and native <= trace[i - 1]["native_frame"]):
            raise ValueError("Original Native frame sequence differs")
        if row.get("contact_sensor_alive") is not True or \
                type(row.get("contact_sensor_actor_id")) is not int:
            raise ValueError("Active contact sensor provenance missing")
        if row.get("path_conflict_survey") is not survey["pedestrian_crosses_vehicle_path"] or \
                row.get("path_survey_source") != survey["road_boundary_source"] or \
                row.get("pedestrian_classification_source") != survey["pedestrian_classification_source"] or \
                row.get("control_relationship_source") != survey["control_relationship_source"]:
            raise ValueError("Original pedestrian path or actor survey differs")
        control = row.get("requested_control")
        if not isinstance(control, dict) or type(control.get("brake")) not in (int, float):
            raise ValueError("Requested driver control source missing")
        vehicle_ids.add(row.get("ego_actor_id"))
        pedestrian_ids.add(row.get("pedestrian_actor_id"))
        sensor_ids.add(row["contact_sensor_actor_id"])
        present = event_frames.pop(native, [])
        if any(event["sensor_actor_id"] != row["contact_sensor_actor_id"] or
               (event["pedestrian_contact"] != (event["other_actor_id"] == row["pedestrian_actor_id"]))
               for event in present):
            raise ValueError("Contact event actor or sensor join differs")
        joined.append({"frame": i, "native_frame": native, "video_frame": i,
                       "time_s": row["time_s"],
                       "vehicle_x_m": row["ego_x_m"], "vehicle_y_m": row["ego_y_m"],
                       "pedestrian_x_m": row["ped_x_m"], "pedestrian_y_m": row["ped_y_m"],
                       "vehicle_speed_mps": row["ego_speed_mps"],
                       "pedestrian_speed_mps": row["ped_speed_mps"],
                       "vehicle_radius_m": row["vehicle_radius_m"],
                       "pedestrian_radius_m": row["pedestrian_radius_m"],
                       "contact_sensor": any(e["pedestrian_contact"] for e in present),
                       "contact_source": source_hashes["contact_events.jsonl"] + ":" + str(row["contact_sensor_actor_id"]),
                       "path_conflict_survey": row["path_conflict_survey"],
                       "requested_brake": control["brake"]})
    if event_frames:
        raise ValueError("Contact event outside original frame map")
    if len(vehicle_ids) != 1 or len(pedestrian_ids) != 1 or len(sensor_ids) != 1 or \
            None in vehicle_ids or None in pedestrian_ids or vehicle_ids == pedestrian_ids:
        raise ValueError("Distinct fixed original actors and contact sensor required")
    packet = {"format": "worker-pedestrian-due-care-source-v1",
              "law_id": "NRS-484B-280-1a", "cell_id": "C230266",
              "source_kind": expected_kind, "actor": "motor_vehicle_driver",
              "vehicle_id": str(next(iter(vehicle_ids))),
              "pedestrian_id": str(next(iter(pedestrian_ids))),
              "vehicle_classification_source": trace[0].get("vehicle_classification_source"),
              "pedestrian_classification_source": survey["pedestrian_classification_source"],
              "path_survey_source": survey["road_boundary_source"],
              "source_hashes": source_hashes, "trace": joined,
              "trace_sha256": digest(joined)}
    return packet, measure(packet)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    packet, measurement = join(args.attempt, args.case, allow_fixture=args.allow_fixture)
    Path(args.output).write_text(json.dumps({"packet": packet, "measurement": measurement},
                                            sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"frames": measurement["frames"], "contact_frames": measurement["contact_frames"],
                      "actual_native_observed": measurement["actual_native_observed"]}))


if __name__ == "__main__":
    main()
