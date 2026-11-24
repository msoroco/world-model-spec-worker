import hashlib
import json
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from dual_green import EvidenceError
from native_straight_controller import StraightController, for_exact_case


def obj(**values):
    return types.SimpleNamespace(**values)


class Actor:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.controls = []
    def get_location(self):
        return obj(x=self.x, y=self.y)
    def get_velocity(self):
        return obj(x=0.0, y=0.0)
    def get_transform(self):
        return obj(get_forward_vector=lambda: obj(x=1.0, y=0.0))
    def apply_control(self, command):
        self.controls.append(command)


class API:
    @staticmethod
    def VehicleControl(**values):
        return obj(**values)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c111125-straight-controller-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        refs = []
        for name in ("map", "route", "signal", "crosswalk", "permission"):
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"source": name}) + "\n")
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.site = {
            "cell_id": "C111125", "actor": "motor_vehicle_driver", "original_sources": refs,
            "map_source_path": refs[0]["path"], "route_source_path": refs[1]["path"],
            "signal_survey_path": refs[2]["path"], "crosswalk_source_path": refs[3]["path"],
            "movement_permission_source_path": refs[4]["path"],
            "official_head_id": "5", "ego_approach_id": "east", "facing_relation": True,
            "arrow_direction": "left", "ego_movement": "straight",
            "straight_permission_review": "source_review_pending",
            "ego_route_xy": [[-10, 0], [0, 0], [10, 0]], "straight_tolerance_m": 0.2,
            "intersection_polygon_xy": [[-2,-2], [2,-2], [2,2], [-2,2]],
            "adjacent_crosswalk_polygon_xy": [[-4,3], [4,3], [4,5], [-4,5]],
        }
        self.ego = Actor(-10, 0)

    def controller(self, other=None):
        return StraightController(self.site, self.root, API, self.ego, other)

    def test_clear_route_commands_motion_then_endpoint_brake(self):
        control = self.controller()
        first = control(self.ego, 0)
        self.assertFalse(first["engineering_stop_requested"])
        self.assertGreater(self.ego.controls[-1].throttle, 0)
        self.ego.x = 10
        last = control(self.ego, 1)
        self.assertTrue(last["route_completed_request"])
        self.assertGreaterEqual(self.ego.controls[-1].brake, 0.7)
        self.assertIsNone(last["legal_yield_verdict"])

    def test_other_user_in_conflict_region_requests_stop(self):
        other = Actor(0, 4)
        control = self.controller(other)
        self.assertTrue(control(self.ego, 0)["conflict_region_occupied"])
        self.assertGreaterEqual(self.ego.controls[-1].brake, 0.7)
        other.y = 8
        self.assertFalse(control(self.ego, 1)["engineering_stop_requested"])

    def test_rejects_route_departure_and_tick_replay(self):
        control = self.controller()
        control(self.ego, 0)
        with self.assertRaisesRegex(EvidenceError, "tick order"):
            control(self.ego, 0)
        self.ego.y = 4
        with self.assertRaisesRegex(EvidenceError, "corridor"):
            control(self.ego, 1)

    def test_rejects_mutated_survey_source(self):
        (self.root / "route.json").write_text("changed\n")
        with self.assertRaisesRegex(EvidenceError, "hash mismatch"):
            self.controller()

    def test_exact_case_binding_checks_actor_count_and_kind(self):
        prefix = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
        self.assertIsInstance(for_exact_case(prefix + "dual_clear", self.site,
                                             self.root, API, [self.ego]), StraightController)
        self.site["other_user_kind"] = "pedestrian"
        with self.assertRaisesRegex(EvidenceError, "actor count"):
            for_exact_case(prefix + "dual_pedestrian_present", self.site,
                           self.root, API, [self.ego])
        with self.assertRaisesRegex(EvidenceError, "other-user kind"):
            for_exact_case(prefix + "dual_vehicle_present", self.site,
                           self.root, API, [self.ego, Actor(0, 4)])
        with self.assertRaisesRegex(EvidenceError, "unplanned"):
            for_exact_case(prefix + "unknown", self.site, self.root, API, [self.ego])


if __name__ == "__main__":
    unittest.main()
