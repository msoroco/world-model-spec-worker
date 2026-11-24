import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from dual_green import EvidenceError
from native_other_controller import OtherUserController


class Actor:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.controls = []

    def get_location(self):
        return types.SimpleNamespace(x=self.x, y=self.y)

    def apply_control(self, command):
        self.controls.append(command)


class API:
    @staticmethod
    def VehicleControl(**values):
        return types.SimpleNamespace(**values)

    @staticmethod
    def WalkerControl(**values):
        return types.SimpleNamespace(**values)

    @staticmethod
    def Vector3D(x, y, z):
        return types.SimpleNamespace(x=x, y=y, z=z)


class OtherControllerTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c111125-other-controller-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        refs = []
        for name in ("map", "route", "signal", "crosswalk", "permission"):
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"source": name}) + "\n")
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.site = {
            "cell_id": "C111125", "actor": "motor_vehicle_driver",
            "original_sources": refs,
            "map_source_path": refs[0]["path"], "route_source_path": refs[1]["path"],
            "signal_survey_path": refs[2]["path"],
            "crosswalk_source_path": refs[3]["path"],
            "movement_permission_source_path": refs[4]["path"],
            "official_head_id": "5", "ego_approach_id": "east",
            "facing_relation": True, "arrow_direction": "left",
            "ego_movement": "straight", "straight_permission_review": "source_review_pending",
            "ego_route_xy": [[-10, 0], [0, 0], [10, 0]],
            "straight_tolerance_m": 0.2,
            "intersection_polygon_xy": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
            "adjacent_crosswalk_polygon_xy": [[-4, 3], [4, 3], [4, 5], [-4, 5]],
            "other_user_target_xy": [0, 4], "late_start_frame_index": 2,
        }
        self.other = Actor(0, 6)

    def controller(self, suffix):
        case = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__" + suffix
        return OtherUserController(case, self.site, self.root, API, self.other)

    def test_late_pedestrian_waits_then_moves_to_surveyed_crosswalk(self):
        controller = self.controller("dual_pedestrian_late")
        for index in (0, 1):
            self.assertTrue(controller(self.other, index)["engineering_stationary_request"])
            self.assertEqual(self.other.controls[-1].speed, 0)
        moving = controller(self.other, 2)
        self.assertFalse(moving["engineering_stationary_request"])
        self.assertGreater(self.other.controls[-1].speed, 0)
        self.assertLess(self.other.controls[-1].direction.y, 0)
        self.assertIsNone(moving["legal_use_verdict"])

    def test_vehicle_hold_and_wrong_order_rejected(self):
        controller = self.controller("dual_vehicle_present")
        self.assertTrue(controller(self.other, 0)["engineering_stationary_request"])
        self.assertTrue(self.other.controls[-1].hand_brake)
        with self.assertRaisesRegex(EvidenceError, "tick order"):
            controller(self.other, 0)

    def test_missing_late_target_rejected(self):
        del self.site["other_user_target_xy"]
        with self.assertRaisesRegex(EvidenceError, "surveyed target"):
            self.controller("dual_pedestrian_late")


if __name__ == "__main__":
    unittest.main()
