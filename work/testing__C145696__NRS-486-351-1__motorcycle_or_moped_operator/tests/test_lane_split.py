import importlib.util
import pathlib
import hashlib
import os
import tempfile
import unittest


MODULE = pathlib.Path(__file__).resolve().parents[1] / "lane_split.py"
spec = importlib.util.spec_from_file_location("lane_split", MODULE)
lane_split = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane_split)


class LaneSplitTests(unittest.TestCase):
    def setUp(self):
        self.survey = {
            "lanes": {"left": {"road_id": 4, "lane_id": -1, "travel_direction": "east", "adjacent_right_lane_id": -2, "lane_type": "Driving", "spawn_transform": "L"},
                      "right": {"road_id": 4, "lane_id": -2, "travel_direction": "east", "adjacent_left_lane_id": -1, "lane_type": "Driving", "spawn_transform": "R"}},
            "split_route": {"entry_lane_id": -1, "exit_lane_id": -2, "verified_drivable": True, "measured_clear_width_m": 2.4, "waypoints": ["A", "B"]},
            "left_lane_route": {"waypoints": ["A", "C"]}, "ego_body_width_m": 0.8, "ego_spawn_transform": "E"}
        self.case = {"left_motion": "stationary", "right_motion": "moving", "maneuver": "between", "vehicle_class": "motorcycle", "target_speed_mps": 4}

    def test_source_gated_construction_and_route(self):
        request = lane_split.construction(self.survey, self.case)
        self.assertEqual([x["lane_id"] for x in request["spawns"]], [-1, -2, -1])
        self.assertEqual(request["route"], ["A", "B"])
        self.assertEqual(request["controller"]["type"], "waypoint_follow")

    def test_rejects_unverified_adjacent_geometry(self):
        self.survey["lanes"]["left"]["adjacent_right_lane_id"] = -3
        with self.assertRaisesRegex(ValueError, "not adjacent"):
            lane_split.construction(self.survey, self.case)

    def test_rejects_unusable_passage(self):
        self.survey["split_route"]["measured_clear_width_m"] = 0.7
        with self.assertRaisesRegex(ValueError, "passage width"):
            lane_split.construction(self.survey, self.case)

    def actor(self, ident, lane, lateral):
        return {"actor_id": ident, "lane_id": lane, "s_m": 12.0, "lateral_m": lateral,
                "half_length_m": 1.0, "half_width_m": 0.2, "speed_mps": 3.0}

    def test_original_measurement_and_actor_seal(self):
        actors = {"ego": self.actor(1, -1, 1.5), "left_occupant": self.actor(2, -1, 0),
                  "right_occupant": self.actor(3, -2, 3)}
        frames = [{"frame": n, "time_s": n / 20, "actors": actors} for n in (100, 101)]
        expected = {role: {"actor_id": actor["actor_id"], "lane_id": actor["lane_id"]} for role, actor in actors.items()}
        result = lane_split.measure_original(frames, expected)
        self.assertEqual(result["candidate_between_frames"], [100, 101])
        frames[1] = {"frame": 102, "time_s": 5.1, "actors": actors}
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            lane_split.measure_original(frames, expected)
        frames[1] = {"frame": 101, "time_s": 5.05, "actors": {**actors, "right_occupant": self.actor(8, -2, 3)}}
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            lane_split.measure_original(frames, expected)

    def test_comparison_rejects_fixed_condition_drift(self):
        row = {"assignment_id": "a", "case_id": "x", "construction_sha256": "seal", "original_frame_count": 900,
               "map_sha256": "map", "road_id": 4, "left_lane_id": -1, "right_lane_id": -2,
               "ego_class": "motorcycle", "camera_plan_sha256": "camera", "duration_frames": 900,
               "left_motion": "stationary", "source_decode_sha256": "decode"}
        other = {**row, "case_id": "y", "left_motion": "moving"}
        self.assertEqual(lane_split.audit_comparison(row, other, "left_motion")["comparison_difference"], "left_motion")
        other["map_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "map_sha256"):
            lane_split.audit_comparison(row, other, "left_motion")
        other["map_sha256"] = "map"
        other["source_decode_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "decoded source"):
            lane_split.audit_comparison(row, other, "left_motion")

    def test_native_spawn_readback_and_cleanup(self):
        class Backend:
            def __init__(self):
                self.spawned = []
                self.destroyed = []
                self.route = None

            def spawn(self, request):
                actor = {"actor_id": len(self.spawned) + 1, "role": request["role"], "lane_id": request["lane_id"]}
                self.spawned.append(actor)
                return actor

            def read_actor(self, actor):
                return actor

            def drive_route(self, actor, route, controller):
                self.route = route

            def destroy(self, actor):
                self.destroyed.append(actor["actor_id"])

        backend = Backend()
        result = lane_split.execute_native(backend, self.survey, self.case)
        self.assertEqual(result["route_waypoints"], ["A", "B"])
        self.assertEqual(backend.route, ["A", "B"])
        self.assertEqual(backend.destroyed, [3, 2, 1])

    def test_saved_source_audit_rejects_tamper_and_missing_review(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_TEST_TEMP_ROOT"]) as temporary:
            root = pathlib.Path(temporary)
            sources = {}
            for name in ("native_result", "frame_map", "original_actor_history"):
                data = (name + " original").encode()
                (root / name).write_bytes(data)
                sources[name] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            cameras = {name: {"decoded_frames": 2, "source_sha256": "source", "decoder_receipt_sha256": "decode"}
                       for name in ("front", "rear", "left", "right")}
            receipt = {"case_id": "exact", "original_frame_count": 2, "frame_map_count": 2,
                       "participant_actor_ids": {"ego": 1, "left": 2, "right": 3},
                       "police_context_source": "operator-register", "operator_identity_source": "operator-register",
                       "sources": sources, "camera_decode": cameras,
                       "actual_pixel_review": {"status": "reviewed"}, "physical_completion": {"status": "reviewed"}}
            self.assertEqual(lane_split.audit_saved(root, receipt, "exact", 2)["audited_original_frames"], 2)
            (root / "frame_map").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "stale source"):
                lane_split.audit_saved(root, receipt, "exact", 2)
            sources["frame_map"]["sha256"] = hashlib.sha256((root / "frame_map").read_bytes()).hexdigest()
            receipt["actual_pixel_review"]["status"] = "pending"
            with self.assertRaisesRegex(ValueError, "actual pixels"):
                lane_split.audit_saved(root, receipt, "exact", 2)


if __name__ == "__main__":
    unittest.main()
