import unittest
import json
import os
import tempfile
from pathlib import Path

from branch_variants import BRANCHES, FEET_20_M, FEET_75_M, check, design_gap_m, side_of_lane
from expanded_layout import check as check_layout, open_drive
from expanded_controller import approach_command, completion_observation
import expanded_runner
import xml.etree.ElementTree as ET


class BranchVariantTests(unittest.TestCase):
    def test_both_highway_sides_and_bands(self):
        self.assertFalse(check()["physical_execution_claimed"])
        self.assertEqual(side_of_lane(-1), "south")
        self.assertEqual(side_of_lane(1), "north")
        self.assertGreater(design_gap_m(BRANCHES["controlled_1"]), FEET_20_M)
        self.assertLess(design_gap_m(BRANCHES["controlled_2"]), FEET_20_M)
        self.assertGreater(design_gap_m(BRANCHES["opposite_far"]), FEET_75_M)
        self.assertLess(design_gap_m(BRANCHES["opposite_near"]), FEET_75_M)

    def test_activities_and_exceptions_are_separate_targets(self):
        self.assertEqual({BRANCHES[k].activity for k in ("controlled_2", "stopped", "standing")},
                         {"parked", "stopped", "standing"})
        self.assertEqual({BRANCHES[k].exception for k in
                          ("traffic_conflict", "law_direction", "police_direction", "device_direction")},
                         {"traffic_conflict", "law", "police_officer", "official_device"})
        self.assertEqual(BRANCHES["traffic_conflict"].context_actor, "traffic_vehicle")
        self.assertEqual(BRANCHES["police_direction"].context_actor, "police_officer")
        self.assertEqual(BRANCHES["device_direction"].context_actor, "official_device")

    def test_opposing_road_lanes_are_constructed(self):
        self.assertTrue(check_layout()["two_opposing_lanes"])
        root = ET.fromstring(open_drive())
        section = root.find("road/lanes/laneSection")
        self.assertEqual(section.find("left/lane").get("id"), "1")
        self.assertEqual(section.find("right/lane").get("id"), "-1")

    def test_opposing_approaches_and_rest_readback(self):
        same = approach_command("controlled_2", -40, 0)
        opposite = approach_command("opposite_near", 50, 0)
        self.assertGreater(same["target_velocity_x_mps"], 0)
        self.assertLess(opposite["target_velocity_x_mps"], 0)
        self.assertEqual(approach_command("opposite_near", -10, 0)["phase"], "rest_target")
        rows = [{"center_xy_m": [-10, 2], "speed_mps": 0.0} for _ in range(40)]
        self.assertEqual(completion_observation(rows, "opposite_near")["observed_rest_frames"], 40)
        rows[-1]["center_xy_m"][1] = -2
        with self.assertRaisesRegex(ValueError, "wrong highway side"):
            completion_observation(rows, "opposite_near")

    def test_expanded_runner_accepts_each_exact_branch_config(self):
        old = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as folder:
                os.chdir(folder)
                for suffix, branch in BRANCHES.items():
                    Path("config.json").write_text(json.dumps({
                        "cell_id": "C229410", "law_id": "NRS-484B-450-1j",
                        "case_suffix": suffix, "initial_activity": branch.activity,
                        "exception_context": branch.exception,
                        "rate_hz": 20, "duration_s": 30}))
                    self.assertTrue(expanded_runner.check()["geometry"]["two_opposing_lanes"])
                Path("config.json").write_text(json.dumps({
                    "cell_id": "C229410", "law_id": "NRS-484B-450-1j",
                    "case_suffix": "police_direction", "initial_activity": "parked",
                    "exception_context": "police_officer", "rate_hz": 20, "duration_s": 30}))
                with self.assertRaisesRegex(ValueError, "activity or exception"):
                    expanded_runner.check()
        finally:
            os.chdir(old)
