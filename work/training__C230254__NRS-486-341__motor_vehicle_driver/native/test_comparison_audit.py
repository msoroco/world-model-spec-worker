import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from acquire_lane_use import append_source, sample
from comparison_audit import compare
from test_acquire_lane_use import actor, road


def make_case(root, suffix, setting, ego_y):
    root.mkdir()
    citation = root / "road-authority.json"
    citation.write_text('{"source":"operator_survey_pending_review"}\n')
    digest = hashlib.sha256(citation.read_bytes()).hexdigest()
    survey = {"source_kind": "original_native_context_survey", "map_name": "Town01",
              "citations": [{"path": citation.name, "sha256": digest}]}
    for key in ("highway_public_maintenance_source",
                "highway_public_vehicular_access_source",
                "protected_vehicle_seat_source", "protected_vehicle_wheels_source",
                "protected_vehicle_exclusions_source",
                "subject_motor_vehicle_class_source"):
        survey[key] = citation.name
    (root / "lane-use-context.json").write_text(json.dumps(survey) + "\n")
    cfg = {"case_id": "training__C230254__NRS-486-341__motor_vehicle_driver__" + suffix,
           "law_id": "NRS-486-341", "cell_id": "C230254",
           "actor": "motor_vehicle_driver", "map_name": "Town01",
           "protected_blueprint": "vehicle.kawasaki.ninja", "subject_blueprint": "vehicle.tesla.model3",
           "rate_hz": 20, "duration_s": 30,
           "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
           "protected_controller": "constant_lane_progress",
           "subject_controller": "constant_lane_progress_with_lateral_target",
           "requested_setting": setting}
    (root / "config.json").write_text(json.dumps(cfg) + "\n")
    refs = {"actor_trace": "trace.jsonl", "actor_bounds": "lane-use-source.jsonl",
            "lane_map": "lane-use-source.jsonl"}
    with (root / "video_frames.jsonl").open("w") as frame_map:
        for index in range(2):
            native_frame = index + 25
            row = sample(road(), actor(1, index, ego_y), actor(2, index, 0, width=1),
                         frame=index, native_frame=native_frame, time_s=index / 20,
                         source_refs=refs)
            append_source(root / "lane-use-source.jsonl", row)
            frame_map.write(json.dumps({"video_frame": index, "native_frame": native_frame,
                                        "time_s": index / 20,
                                        "camera_native_frames": {name: native_frame for name in
                                                                 cfg["cameras"]}}) + "\n")


class ComparisonTest(unittest.TestCase):
    def test_positive_and_fixed_condition_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            make_case(first, "full_lane_available", "full_lane_available", 4)
            make_case(second, "blocked_by_ego", "blocked_by_ego", 1)
            report = compare(first, second)
            self.assertTrue(report["passed"])
            self.assertFalse(report["legal_verdict_claimed"])
            cfg = json.loads((second / "config.json").read_text())
            cfg["protected_controller"] = "changed"
            (second / "config.json").write_text(json.dumps(cfg) + "\n")
            with self.assertRaisesRegex(ValueError, "Fixed comparison condition differs"):
                compare(first, second)

    def test_missing_original_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            make_case(first, "full_lane_available", "full_lane_available", 4)
            make_case(second, "blocked_by_ego", "blocked_by_ego", 1)
            (second / "lane-use-source.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                compare(first, second)


if __name__ == "__main__":
    unittest.main()
