"""CPU geometry checks for the two exact C82860 crossing requests."""

import copy
import unittest

from road_request import check, request


class RoadRequestTest(unittest.TestCase):
    def test_two_roadways_and_distinct_full_uturn_crossings(self):
        opening = request("authorized_opening")
        barrier = request("barrier_crossing")
        self.assertTrue(check(opening, barrier)["passed"])
        for item in (opening, barrier):
            path = item["route_waypoints_xy_m"]
            self.assertEqual(path[0], [-25, -6.75])
            self.assertEqual(path[-1][1], 6.75)
            self.assertEqual(path[2][0], path[3][0])
            self.assertEqual(path[3][0], path[4][0])
            self.assertEqual(path[3][1], 0)
            self.assertEqual((item["rate_hz"], item["frames"]), (20, 600))
            self.assertEqual(len(item["cameras"]), 4)
            self.assertIsNone(item["legal_verdict"])
        self.assertLess(abs(opening["requested_crossing_x_m"]), 3)
        self.assertGreater(barrier["requested_crossing_x_m"], 3)
        self.assertLess(barrier["requested_crossing_x_m"], 20)

    def test_request_identity_and_comparison_isolation_rejected(self):
        opening = request("authorized_opening")
        barrier = request("barrier_crossing")
        changed = copy.deepcopy(barrier)
        changed["cameras"][0]["width"] = 640
        with self.assertRaisesRegex(ValueError, "exact U-turn request differs"):
            check(opening, changed)
        changed = copy.deepcopy(barrier)
        changed["source_map"] = "<OpenDRIVE/>"
        with self.assertRaisesRegex(ValueError, "exact U-turn request differs"):
            check(opening, changed)


if __name__ == "__main__":
    unittest.main()
