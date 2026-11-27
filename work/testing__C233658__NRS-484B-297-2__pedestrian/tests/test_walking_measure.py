import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from walking_measure import measure


class WalkingMeasurementTests(unittest.TestCase):
    def packet(self):
        return {"site": {"reviewed_public_highway": True, "reviewed_sidewalk_absent": True,
                         "reviewed_subsection_6_inapplicable": True,
                         "centerline_xy_m": [[-30.0, 0.0], [30.0, 0.0]]},
                "frames": [{"time_s": i / 20, "pedestrian_xyz_m": [20 - i, -4.5, 0],
                            "vehicle_xyz_m": [-30 + i, 0, 0],
                            "pedestrian_forward_xy": [-1, 0],
                            "vehicle_forward_xy": [1, 0]} for i in range(3)]}

    def test_original_side_facing_and_approach(self):
        value = measure(self.packet())
        self.assertEqual(value["pedestrian_side_history"], ["center_right"] * 3)
        self.assertTrue(value["all_frames_facing"])
        self.assertTrue(value["any_frame_vehicle_approaching"])
        self.assertTrue(value["site_qualifications_reviewed"])

    def test_missing_source_and_unreviewed_site_rejected(self):
        packet = self.packet()
        del packet["frames"][1]["vehicle_xyz_m"]
        with self.assertRaisesRegex(ValueError, "transform missing"):
            measure(packet)
        packet = self.packet()
        packet["site"]["reviewed_sidewalk_absent"] = False
        with self.assertRaisesRegex(ValueError, "qualifications unresolved"):
            measure(packet)


if __name__ == "__main__":
    unittest.main()
