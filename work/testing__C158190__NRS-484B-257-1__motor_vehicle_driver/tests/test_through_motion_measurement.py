import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from through_motion_measurement import compare_original, inspect_original
from yield_view_measurement import ASSIGNMENT


class OriginalMotionTests(unittest.TestCase):
    def packet(self, response="slow", phase="close"):
        digest = "a" * 64
        site = {"control": "yield_sign", "stop_line_present": False,
                "near_crosswalk_present": False, "police_control_active": False,
                "traffic_signal_control_active": False,
                "source_kind": "original_native_readback", "source_recording_id": "source-fixture",
                "yield_sign_source_sha256": digest, "marking_survey_sha256": digest,
                "through_highway_survey_sha256": digest, "view_ray_source_sha256": digest,
                "map_source_sha256": digest, "intersection_id": "intersection-fixture",
                "ego_route_source_sha256": digest, "camera_plan_sha256": digest,
                "duration_frames": 5, "planned_ego_response": response,
                "planned_through_traffic_phase": phase,
                "approach_view_stations": [
                    {"station_id": "far", "distance_to_intersection_m": 10,
                     "view_of_through_traffic": True},
                    {"station_id": "near", "distance_to_intersection_m": 2,
                     "view_of_through_traffic": True}]}
        frames = []
        for index in range(5):
            within = index in (2, 3)
            frames.append({"time_s": index * 0.05, "ego_speed_mps": 4 - index,
                           "distance_to_intersection_m": 5 - index,
                           "ego_within_intersection": within,
                           "through_vehicle_ids": ["through-1"],
                           "through_vehicles": [{"id": "through-1", "through_highway": True,
                                                 "distance_to_conflict_m": 8 - index,
                                                 "speed_mps": 5.0}]})
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "site": site, "frames": frames}

    def write(self, directory, name, packet):
        path = Path(directory) / name
        path.write_text(json.dumps(packet), encoding="utf-8")
        return path

    def test_complete_crossing_and_trajectory(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            result = inspect_original(self.write(directory, "one.json", self.packet()))
        self.assertEqual(result["crossing_frame_indices"], [2, 3])
        self.assertEqual(result["through_vehicle_motion"][0]["observed_frame_count"], 2)

    def test_missing_original_survey_rejected(self):
        packet = self.packet()
        del packet["site"]["yield_sign_source_sha256"]
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            with self.assertRaisesRegex(ValueError, "yield_sign_source_sha256"):
                inspect_original(self.write(directory, "one.json", packet))

    def test_missing_crossing_motion_rejected(self):
        packet = self.packet()
        del packet["frames"][2]["through_vehicles"]
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            with self.assertRaisesRegex(ValueError, "motion required"):
                inspect_original(self.write(directory, "one.json", packet))

    def test_empty_crossing_traffic_rejected(self):
        packet = self.packet()
        for frame in packet["frames"][2:4]:
            frame["through_vehicles"] = []
            frame["through_vehicle_ids"] = []
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            with self.assertRaisesRegex(ValueError, "motion required"):
                inspect_original(self.write(directory, "empty.json", packet))

    def test_controlled_response_and_negative_fixed_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            left = self.write(directory, "left.json", self.packet())
            right_packet = self.packet(response="stop")
            right = self.write(directory, "right.json", right_packet)
            self.assertEqual(compare_original(left, right, "ego_response")["variable"], "ego_response")
            right_packet["site"]["camera_plan_sha256"] = "b" * 64
            self.write(directory, "right.json", right_packet)
            with self.assertRaisesRegex(ValueError, "camera_plan_sha256"):
                compare_original(left, right, "ego_response")

    def test_undeclared_intervention_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            left = self.write(directory, "left.json", self.packet())
            right = self.write(directory, "right.json", self.packet(response="stop", phase="late"))
            with self.assertRaisesRegex(ValueError, "uncontrolled"):
                compare_original(left, right, "ego_response")


if __name__ == "__main__":
    unittest.main()
