import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_oneway", ROOT / "native_oneway.py")
NATIVE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NATIVE
SPEC.loader.exec_module(NATIVE)


class NativeConstructionTests(unittest.TestCase):
    def test_approach_hold_and_departure_controls(self):
        self.assertEqual(NATIVE.phase_for("park", False, 0, 400), "approach")
        self.assertEqual(NATIVE.phase_for("stand", True, 0, 400), "hold")
        self.assertEqual(NATIVE.phase_for("stand", True, 160, 400), "depart")
        self.assertEqual(NATIVE.control(0, 0, "hold", "park")["hand_brake"], True)
        self.assertEqual(NATIVE.control(0, 0, "hold", "stand")["hand_brake"], False)
        self.assertGreater(NATIVE.control(0, 5, "approach", "park")["brake"], 0)

    def test_original_four_camera_capture_profile(self):
        self.assertEqual(NATIVE.CAMERAS, (("overview", 1920, 1080),
            ("approach", 1280, 720), ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720)))

    def test_loaded_marked_lane_readback_rejects_wrong_lane(self):
        class Map:
            def get_waypoint(self, location):
                return types.SimpleNamespace(road_id=7,
                    lane_id=-1 if location.x == 1 else -2)
        carla = types.SimpleNamespace(Location=lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z))
        records = {"roadway": {"marked_lanes": [
            {"lane_id": -1, "sample_xy": [1, 2]},
            {"lane_id": -2, "sample_xy": [2, 2]}]}}
        self.assertEqual(NATIVE.validate_loaded_road(Map(), carla, records, {"road_id": 7}), [-2, -1])
        records["roadway"]["marked_lanes"][1]["lane_id"] = -3
        with self.assertRaisesRegex(ValueError, "lane identity"):
            NATIVE.validate_loaded_road(Map(), carla, records, {"road_id": 7})


if __name__ == "__main__":
    unittest.main()
