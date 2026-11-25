import unittest

from facility import body_overlap
from route_v2 import body_at, check, route_x


class RouteV2Test(unittest.TestCase):
    def test_crossing_and_sustained_routes(self):
        proof = check()
        self.assertTrue(proof["passed"])
        self.assertLess(proof["crossing_overlap_stations"], proof["sustained_overlap_stations"])
        self.assertGreater(body_overlap(body_at("outside_cycle_lane", -4.0))["cycle_intersection_body_overlap_m2"], 0)
        self.assertEqual(body_overlap(body_at("outside_cycle_lane", 4.0))["cycle_intersection_body_overlap_m2"], 0)

    def test_invalid_station_and_case_fail_closed(self):
        with self.assertRaises(ValueError):
            route_x("other", 0.0)
        with self.assertRaises(ValueError):
            route_x("outside_cycle_lane", float("nan"))


if __name__ == "__main__":
    unittest.main()
