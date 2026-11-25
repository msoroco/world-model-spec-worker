"""Synthetic source fixture for Native plan and pure controller CPU checks."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from cycle_lane_native import control, prepare
from cycle_lane_intersection import ASSIGNMENT
import test_cycle_lane_original as fixture_module


class NativePlanTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.OriginalAuditTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def call_prepare(self, route="test_route", site_hash=None):
        root = self.fixture.root
        return prepare(ASSIGNMENT + "__cycle_lane_through_intersection",
                       root / "site.json", site_hash or self.fixture.site["sha256"],
                       root / "exception.json", self.fixture.exception["sha256"],
                       root / "vehicle.json", self.fixture.vehicle["sha256"], route)

    def test_source_gated_route_and_capture_profile(self):
        result = self.call_prepare()
        self.assertEqual(result["capture_profile"]["views"],
                         ["overview", "approach", "reference_corner", "driver_reference"])
        self.assertTrue(result["route"])

    def test_wrong_source_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed source hash"):
            self.call_prepare(site_hash="0" * 64)

    def test_wrong_case_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "requested cycle-lane intersection overlap"):
            self.call_prepare(route="ordinary_route")

    def test_controller_straight_and_stop(self):
        forward = control((0, 0), 0.0, 1.0, [[0, 0], [5, 0], [10, 0]])
        self.assertGreater(forward["throttle"], 0)
        self.assertAlmostEqual(forward["steer"], 0)
        end = control((9.8, 0), 0.0, 2.0, [[0, 0], [5, 0], [10, 0]])
        self.assertTrue(end["route_complete"])
        self.assertEqual(end["brake"], 1.0)

    def test_controller_tracks_lateral_target(self):
        turning = control((0, 0), 0.0, 2.0, [[0, 0], [5, 2], [10, 4]])
        self.assertGreater(turning["steer"], 0)
