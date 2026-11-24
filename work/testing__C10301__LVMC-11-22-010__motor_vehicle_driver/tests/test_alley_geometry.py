import copy
import importlib.util
import json
import unittest
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("alley_geometry", BASE / "alley_geometry.py")
geometry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.scene = json.loads((BASE / "alley-scene.json").read_text())

    def test_access_aisle_and_route_are_geometrically_distinct(self):
        report = geometry.validate(self.scene)
        self.assertTrue(report["route_clearance_verified_offline"])
        self.assertTrue(report["access_aisle_adjacent_to_parking"])
        self.assertEqual(report["route_length_m"], 110.0)
        self.assertFalse(report["native_realization_confirmed"])

    def test_rejects_route_too_short_for_full_capture(self):
        changed = copy.deepcopy(self.scene)
        changed["ego_route_xy_m"] = [[-18.0, 0.0], [18.0, 0.0]]
        with self.assertRaisesRegex(ValueError, "shorter than 45 seconds"):
            geometry.validate(changed)

    def test_rejects_access_aisle_replaced_by_travel_lane(self):
        changed = copy.deepcopy(self.scene)
        changed["surface_role"] = "ordinary_travel_lane"
        with self.assertRaisesRegex(ValueError, "ordinary travel lane"):
            geometry.validate(changed)

    def test_rejects_clearance_failure_and_missing_stripes(self):
        changed = copy.deepcopy(self.scene)
        changed["ego_route_xy_m"][2][1] = 2.8
        with self.assertRaisesRegex(ValueError, "does not clear"):
            geometry.validate(changed)
        changed = copy.deepcopy(self.scene)
        changed["contrasting_stripes_xy_m"] = changed["contrasting_stripes_xy_m"][:1]
        with self.assertRaisesRegex(ValueError, "multiple contrasting stripes"):
            geometry.validate(changed)

    def test_rejects_detached_parking(self):
        changed = copy.deepcopy(self.scene)
        changed["designated_parking_xy_m"][1] = 6.0
        with self.assertRaisesRegex(ValueError, "beside alley and designated parking"):
            geometry.validate(changed)


if __name__ == "__main__":
    unittest.main()
