"""CPU checks of requested construction, without claiming original motion."""
import math
import unittest
import xml.etree.ElementTree as ET

from scene import FRAMES, HZ, PASS_TARGETS_M, check, open_drive, target
from runner import CAMERAS, survey_check


class SceneTests(unittest.TestCase):
    def test_nine_exact_plans_and_timebase(self):
        proof = check()
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(proof["rate_hz"], 20)
        self.assertEqual(len(PASS_TARGETS_M), 9)
        self.assertEqual((FRAMES, HZ), (600, 20))
        self.assertEqual([row[0] for row in CAMERAS],
                         ["overview", "approach", "reference_corner", "driver_reference"])

    def test_opposing_lane_and_marking_difference(self):
        for marking in (False, True):
            root = ET.fromstring(open_drive(marking))
            lanes = root.findall("road/lanes/laneSection/left/lane") + root.findall("road/lanes/laneSection/right/lane")
            self.assertEqual([lane.attrib["id"] for lane in lanes], ["1", "-1"])
            self.assertEqual([lane.find("roadMark").attrib["type"] for lane in lanes],
                             ["solid" if marking else "broken"] * 2)

    def test_body_gap_and_return_ordering(self):
        for suffix, requested in PASS_TARGETS_M.items():
            rows = [target(suffix, frame) for frame in range(FRAMES)]
            overlap = [row for row in rows if abs(row.ego_x_m - row.scooter_x_m) <= 2.95]
            self.assertTrue(overlap)
            gaps = [row.ego_y_m - row.scooter_y_m - .9 - .35 for row in overlap]
            if suffix != "ordering_1":
                self.assertTrue(all(math.isclose(gap, requested, abs_tol=1e-9) for gap in gaps))
            return_frame = next(i for i in range(1, FRAMES) if rows[i].ego_y_m < rows[i - 1].ego_y_m - 1e-8)
            if suffix == "ordering_1":
                self.assertLess(return_frame, overlap[-1].frame)
            else:
                self.assertGreater(return_frame, overlap[-1].frame)
            self.assertEqual(rows[0].scooter_x_m, -10)
            self.assertEqual(rows[-1].scooter_y_m, -2.3)

    def test_missing_and_wrong_scooter_source_rejected(self):
        source = {key: "reviewed original source" for key in (
            "source_path", "device_blueprint_source", "device_subtype_source",
            "scooter_classification_source", "scooter_handlebars_source",
            "scooter_electric_motor_source", "scooter_riding_design_source",
            "scooter_mass_source", "scooter_motor_max_speed_source",
            "rider_identity_source")}
        source.update(device_blueprint="vehicle.surveyed_scooter", device_subtype="electric_scooter",
                      scooter_rider_excluded_mass_lb=30, scooter_motor_only_max_mph=15)
        self.assertEqual(survey_check(source)["device_subtype"], "electric_scooter")
        for mutation in ({"rider_identity_source": None}, {"device_subtype": "bicycle"},
                         {"device_blueprint": "vehicle.bh.crossbike"},
                         {"scooter_rider_excluded_mass_lb": 101},
                         {"scooter_motor_only_max_mph": 21}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                survey_check({**source, **mutation})


if __name__ == "__main__":
    unittest.main()
