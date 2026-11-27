"""Synthetic CPU contract tests; never evidence of an original recording."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from reviewed_scene import ASSIGNMENT, VARIANTS, execute_native, plan
from right_side_measurement import measure_packet
from finalize_original import finalize
from analysis import build_report


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def open_map(self, *args):
        self.calls.append(("open_map", args))

    def spawn_obstruction(self, **kwargs):
        self.calls.append(("spawn_obstruction", kwargs))
        return "physical_prop_stub"

    def spawn_vehicle(self, **kwargs):
        self.calls.append(("spawn_vehicle", kwargs))
        return kwargs["role"]

    def attach_camera(self, **kwargs):
        self.calls.append(("attach_camera", kwargs))
        return kwargs["name"]

    def tick_and_capture(self, **kwargs):
        self.calls.append(("tick_and_capture", kwargs["frame"]))


class ReviewedSceneTest(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c323986-6271a/output"))
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        xodr = '<OpenDRIVE><road id="1"><lanes><laneSection><left><lane id="1" type="driving"/></left><right><lane id="-1" type="driving"/></right></laneSection></lanes></road></OpenDRIVE>'
        (self.root / "map.xodr").write_text(xodr)
        map_ref = self.ref("map.xodr")
        camera = {name: {"width": width, "height": height, "fov_deg": 90,
                 "pose": {"x": 0, "y": 0, "z": 2, "pitch": 0, "yaw": 0, "roll": 0}}
                  for name, width, height in [("overview", 1920, 1080), ("approach", 1280, 720),
                                              ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]}
        physical = {"map_ref": map_ref, "paved_right_edge_m": 4.7, "highway_right_edge_m": 5.2,
                    "obstruction_right_edge_m": 4.4, "obstruction_left_edge_m": 4.0,
                    "ego_center_path_m": 0.0, "ego_right_path_m": 1.1,
                    "ego_half_width_m": 0.9, "obstruction_blueprint_id": "static.prop.streetbarrier",
                    "follower_start_station_m": 20,
                    "ego_start_station_m": 45, "ego_speed_mps": 5,
                    "follower_speed_mps": 8, "obstruction_station_m": 85}
        variants = {suffix: dict(physical) for suffix in VARIANTS}
        variants["slow_center_narrow"]["paved_right_edge_m"] = 3.5
        variants["slow_center_obstruction_near"]["obstruction_station_m"] = 60
        for index, speed in enumerate((4.0, 5.0, 6.0)):
            variants[f"impediment-{index:04d}"]["ego_speed_mps"] = speed
        for index, edge in enumerate((3.5, 4.1, 4.7)):
            variants[f"paved_width-{index:04d}"]["paved_right_edge_m"] = edge
        for index, offset in enumerate((0.0, 0.55, 1.1)):
            variants[f"right_position-{index:04d}"]["ego_right_path_m"] = offset
        site = {"reviewed_original_site": True, "diagnostic_fixture": False,
                "cpu_test_synthetic_only": True, "map_ref": map_ref, "road_id": "1",
                "highway": True, "one_lane_each_direction": True,
                "opposite_direction_verified": True, "travel_lane_id": "-1",
                "opposite_lane_id": "1", "variants": variants,
                "camera_profiles": camera}
        (self.root / "site.json").write_text(json.dumps(site))
        self.site_ref = self.ref("site.json")

    def tearDown(self):
        self.temp.cleanup()

    def ref(self, name):
        return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def test_all_exact_cases_have_two_way_geometry_and_physical_prop(self):
        for suffix in VARIANTS:
            scene = plan(self.root, self.site_ref, ASSIGNMENT + "__" + suffix)
            self.assertNotEqual(scene["travel_lane_id"], scene["opposite_lane_id"])
            self.assertEqual(scene["frames"], 900)
            fake = FakeAdapter()
            execute_native({**scene, "frames": 3}, fake)
            self.assertEqual(len([c for c in fake.calls if c[0] == "spawn_obstruction"]), 1)
            self.assertEqual(len([c for c in fake.calls if c[0] == "attach_camera"]), 4)
            self.assertEqual(len([c for c in fake.calls if c[0] == "tick_and_capture"]), 3)
        no_follow = plan(self.root, self.site_ref, ASSIGNMENT + "__slow_center_no_follower")
        self.assertEqual(no_follow["actors"][1]["lane_id"], no_follow["opposite_lane_id"])
        self.assertEqual([plan(self.root, self.site_ref, ASSIGNMENT + f"__impediment-{i:04d}")["actors"][0]["target_speed_mps"]
                          for i in range(3)], [4.0, 5.0, 6.0])
        self.assertEqual([plan(self.root, self.site_ref, ASSIGNMENT + f"__paved_width-{i:04d}")["paved_right_edge_m"]
                          for i in range(3)], [3.5, 4.1, 4.7])
        self.assertEqual([plan(self.root, self.site_ref, ASSIGNMENT + f"__right_position-{i:04d}")["actors"][0]["lateral_offset_m"]
                          for i in range(3)], [0.0, 0.55, 1.1])

    def test_missing_or_stale_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash changed"):
            plan(self.root, {**self.site_ref, "sha256": "0" * 64}, ASSIGNMENT + "__slow_center_wide")
        site = json.loads((self.root / "site.json").read_text())
        site["opposite_direction_verified"] = False
        (self.root / "site.json").write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, "one lane each direction"):
            plan(self.root, self.ref("site.json"), ASSIGNMENT + "__slow_center_wide")

    def test_unreviewed_comparison_change_rejected(self):
        site = json.loads((self.root / "site.json").read_text())
        site["variants"]["slow_right_wide"]["follower_speed_mps"] = 12
        (self.root / "site.json").write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, "changed held physical facts"):
            plan(self.root, self.ref("site.json"), ASSIGNMENT + "__slow_right_wide")

    def test_original_measurement_preserves_obstruction_and_follower_questions(self):
        row = {"ego_actor_id": 10, "follower_actor_id": 11, "ego_lane_id": "-1",
               "follower_lane_id": "-1", "opposite_lane_id": "1", "one_lane_each_direction_readback": True,
               "follower_immediately_behind_readback": True, "paved_right_edge_m": 4.7,
               "highway_right_edge_m": 5.2, "obstruction_left_edge_m": 4.0,
               "obstruction_right_edge_m": 4.4, "ego_body_left_edge_m": -0.9,
               "ego_body_right_edge_m": 0.9, "ego_speed_mps": 5.0,
               "follower_speed_mps": 8.0, "follower_along_route_body_gap_m": 20.0,
               "obstruction_station_m": 85.0, "ego_station_m": 45.0,
               "follower_station_m": 20.0}
        packet = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__slow_center_wide",
                  "original_trace_id": "synthetic-unit-test", "original_frame_map_sha256": "a" * 64,
                  "frames": [{**row, "frame": i, "time_s": i / 20} for i in range(3)]}
        measured = measure_packet(packet, {"path": "synthetic-unit-test", "sha256": "b" * 64})
        self.assertEqual(measured["observations"][0]["relative_closing_speed_mps"], 3)
        self.assertEqual(len(measured["unresolved_judgments"]), 4)
        packet["frames"][1]["follower_actor_id"] = 10
        with self.assertRaisesRegex(ValueError, "own follower"):
            measure_packet(packet, {"path": "synthetic-unit-test", "sha256": "b" * 64})

    def test_saved_original_join_and_negative_source(self):
        case_id = ASSIGNMENT + "__slow_center_wide"
        row = {"ego_actor_id": 10, "follower_actor_id": 11, "ego_lane_id": "-1",
               "follower_lane_id": "-1", "opposite_lane_id": "1", "one_lane_each_direction_readback": True,
               "paved_right_edge_m": 4.7, "highway_right_edge_m": 5.2,
               "obstruction_left_edge_m": 4.0, "obstruction_right_edge_m": 4.4,
               "ego_body_left_edge_m": -0.9, "ego_body_right_edge_m": 0.9,
               "ego_speed_mps": 5.0, "follower_speed_mps": 8.0,
               "follower_along_route_body_gap_m": 20.0,
               "obstruction_station_m": 85.0, "ego_station_m": 45.0,
               "follower_station_m": 20.0}
        frames = [{"frame": i, "time_s": i / 20,
                   "camera_frames": {name: i + 100 for name in
                       ("overview", "approach", "reference_corner", "driver_reference")}}
                  for i in range(9)]
        frame_map = {"case_id": case_id, "source_kind": "original_native_frame_map", "frames": frames}
        map_path = self.root / "original-frame-map.json"
        map_path.write_text(json.dumps(frame_map))
        relation = {"case_id": case_id, "source_kind": "original_native_relation",
                    "relation_basis_source": "synthetic CPU test",
                    "samples": [{"frame": i, "time_s": i / 20,
                                 "follower_actor_id": 11, "immediately_behind": True}
                                for i in range(9)]}
        motion = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                  "original_trace_id": "synthetic-unit-test",
                  "original_frame_map_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
                  "frames": [{**row, "frame": i, "time_s": i / 20} for i in range(9)]}
        (self.root / "original-relation.json").write_text(json.dumps(relation))
        (self.root / "original-motion.json").write_text(json.dumps(motion))
        (self.root / "fixture-provenance.json").write_text(json.dumps({
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}))
        (self.root / "original-site.json").write_text(json.dumps({
            "case_id": case_id, "site_ref_sha256": self.site_ref["sha256"],
            "cpu_test_synthetic_only": True}))
        result = finalize(self.root, case_id)
        self.assertEqual(result["original_frame_count"], 9)
        self.assertEqual(result["observations"][5]["relative_closing_speed_mps"], 3)
        report = build_report(self.root, case_id)
        self.assertEqual(report["measurements"]["following_motion_measurement"]["value"]["immediate_follower_frames"], 9)
        self.assertTrue(report["diagnostic_fixture"])
        (self.root / "original-relation.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            finalize(self.root, case_id)


if __name__ == "__main__":
    unittest.main()
