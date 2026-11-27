"""Exercise original-source joins with a plainly synthetic CPU fixture."""

import json
import tempfile
from pathlib import Path

from prove_due_care_meter import packet
from saved_due_care import ASSIGNMENT, join

ROOT = Path(__file__).resolve().parents[3]
CASE = ASSIGNMENT + "__selected_90e3f1aa__condition_a"


def write_rows(path, values):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values))


def fixture(root):
    survey = {"source_kind": "synthetic_native_sample", "road_boundary_source": "synthetic_path_survey",
              "pedestrian_classification_source": "synthetic_person_afoot",
              "control_relationship_source": "synthetic_driver_control",
              "pedestrian_crosses_vehicle_path": True}
    (root / "road_survey.json").write_text(json.dumps(survey) + "\n")
    trace, mapping = [], []
    for row in packet(True)["trace"]:
        i, native = row["frame"], row["native_frame"]
        trace.append({"source_kind": "synthetic_native_sample", "frame": i,
                      "native_frame": native, "video_frame": i, "time_s": row["time_s"],
                      "ego_x_m": row["vehicle_x_m"], "ego_y_m": row["vehicle_y_m"],
                      "ped_x_m": row["pedestrian_x_m"], "ped_y_m": row["pedestrian_y_m"],
                      "ego_speed_mps": row["vehicle_speed_mps"],
                      "ped_speed_mps": row["pedestrian_speed_mps"],
                      "vehicle_radius_m": row["vehicle_radius_m"],
                      "pedestrian_radius_m": row["pedestrian_radius_m"],
                      "ego_actor_id": 1, "pedestrian_actor_id": 2,
                      "vehicle_classification_source": "synthetic_motor_vehicle",
                      "pedestrian_classification_source": survey["pedestrian_classification_source"],
                      "control_relationship_source": survey["control_relationship_source"],
                      "path_survey_source": survey["road_boundary_source"],
                      "path_conflict_survey": True,
                      "contact_sensor_actor_id": 3, "contact_sensor_alive": True,
                      "requested_control": {"brake": row["requested_brake"]}})
        mapping.append({"video_frame": i, "native_frame": native,
                        "carla_frame": native, "time_s": row["time_s"]})
    write_rows(root / "pedestrian-due-care-trace.jsonl", trace)
    write_rows(root / "video_frames.jsonl", mapping)
    write_rows(root / "contact_events.jsonl", [{"native_frame": 1680, "other_actor_id": 2,
                                                "pedestrian_contact": True, "sensor_actor_id": 3}])
    return trace, mapping


def rejects(root, fragment):
    try:
        join(root, CASE, allow_fixture=True)
    except ValueError as error:
        assert fragment in str(error), str(error)
        return str(error)
    raise AssertionError("Bad source accepted: " + fragment)


def main():
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c230266-saved-") as temporary:
        root = Path(temporary)
        trace, mapping = fixture(root)
        source, measurement = join(root, CASE, allow_fixture=True)
        assert source["source_kind"] == "synthetic_native_sample"
        assert measurement["contact_frames"] == 1 and measurement["frames"] == 600
        assert measurement["actual_native_observed"] is False
        negative = {}
        events_path = root / "contact_events.jsonl"
        events = events_path.read_text()
        events_path.unlink()
        negative["missing_contact_stream"] = rejects(root, "Missing required source")
        events_path.write_text(events)
        mapping[180]["native_frame"] += 1
        write_rows(root / "video_frames.jsonl", mapping)
        negative["bad_frame_join"] = rejects(root, "video and time join differs")
        mapping[180]["native_frame"] -= 1
        write_rows(root / "video_frames.jsonl", mapping)
        trace[180]["contact_sensor_alive"] = False
        write_rows(root / "pedestrian-due-care-trace.jsonl", trace)
        negative["inactive_contact_sensor"] = rejects(root, "Active contact sensor")
        trace[180]["contact_sensor_alive"] = True
        write_rows(root / "pedestrian-due-care-trace.jsonl", trace)
        write_rows(events_path, [{"native_frame": 1680, "other_actor_id": 9,
                                 "pedestrian_contact": True, "sensor_actor_id": 3}])
        negative["false_pedestrian_contact"] = rejects(root, "Contact event actor")
    proof = {"format": "worker-pedestrian-saved-join-proof-v1",
             "positive": measurement, "negative_rejections": negative,
             "source_kind": "synthetic_native_sample", "original_native_observed": False,
             "legal_verdict": None}
    Path(__file__).with_name("saved-join-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive_frames": measurement["frames"],
                      "negative_rejections": len(negative), "actual_native_observed": False}))


if __name__ == "__main__":
    main()
