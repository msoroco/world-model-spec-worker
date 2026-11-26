import copy
import unittest

from conditions_source_v2 import VIEWS, measure


def fixture():
    return [{"video_frame": i, "native_frame": 1000 + i, "time_s": i / 20,
             "camera_frames": {name: 1000 + i for name in VIEWS},
             "ego_velocity_xyz_mps": [12.0, 0.0, 0.0],
             "traffic": [{"native_actor_id": 47, "velocity_xyz_mps": [8.0, 0.0, 0.0],
                          "class_source": "original Native blueprint"}],
             "road": {"native_map_sha256": "a" * 64, "surface_source": "Native map and readback",
                      "lane_width_m": 3.5, "curvature_inv_m": 0.0, "surface_wetness": 0.0},
             "weather": {"precipitation": 0.0, "fog_density": 0.0,
                         "sun_altitude_angle": 45.0},
             "visibility_source": "Native weather and four views"} for i in range(600)]


class SourceJoin(unittest.TestCase):
    def test_full_frame_measurement_has_no_verdict(self):
        result = measure(fixture(), source_kind="synthetic_cpu_fixture")
        self.assertEqual(result["frame_count"], 600)
        self.assertEqual(len(result["frame_measurements"]), 600)
        self.assertEqual(result["ego_speed_mps"]["mean"], 12.0)
        self.assertEqual(result["legal_judgment"], "unresolved")
        self.assertFalse(result["physical_acceptance"])

    def test_missing_named_sources_rejected(self):
        for key, subkey in (("camera_frames", "overview"), ("road", "surface_source"),
                            ("weather", "precipitation"), ("traffic", None),
                            ("ego_velocity_xyz_mps", None)):
            with self.subTest(key=key):
                rows = fixture()
                if subkey is None:
                    rows[50].pop(key)
                else:
                    rows[50][key].pop(subkey)
                with self.assertRaises(ValueError):
                    measure(rows, source_kind="synthetic_cpu_fixture")

    def test_timing_and_identity_rejected(self):
        rows = fixture()
        rows[75]["time_s"] += .05
        with self.assertRaisesRegex(ValueError, "time join"):
            measure(rows, source_kind="synthetic_cpu_fixture")
        rows = fixture()
        rows[75]["traffic"].append(copy.deepcopy(rows[75]["traffic"][0]))
        with self.assertRaisesRegex(ValueError, "Distinct Native"):
            measure(rows, source_kind="synthetic_cpu_fixture")


if __name__ == "__main__":
    unittest.main()
