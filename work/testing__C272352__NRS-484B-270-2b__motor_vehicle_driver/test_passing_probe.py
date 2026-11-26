import unittest

from passing_probe import THREE_FEET_M, measure_pass, rectangle_gap


class PassingProbeTests(unittest.TestCase):
    def site(self):
        return dict(highway_source="map/highway.json", lane_count_same_direction=1,
                    centerline_y=4.0, right_side_y=1.0, vehicle_id="ego",
                    bicycle_id="bike", bicycle_kind="bicycle")

    def frames(self, gap=1.0, early_return=False):
        bike = (10.0, 12.0, 0.0, 0.5)
        boxes = [(0.0, 4.0, 0.0, 0.5),
                 (9.0, 11.0, 0.5 + gap, 2.5 + gap),
                 (13.0, 15.0, 0.0 if early_return else 1.5, 2.0)]
        return [dict(original_frame=i, time_s=i * 0.05, vehicle_box=box,
                     bicycle_box=bike, vehicle_speed_mps=5.0,
                     bicycle_speed_mps=2.0, vehicle_source="motion/ego.json",
                     bicycle_source="motion/bike.json", lane_source="map/lane.json")
                for i, box in enumerate(boxes)]

    def test_body_gap_floor_and_return_order(self):
        m = measure_pass(self.site(), self.frames())
        self.assertTrue(m["three_foot_floor_observed"])
        self.assertTrue(m["longitudinal_clear_before_return"])
        self.assertEqual(m["incorporated_exceptions"], "unresolved")
        self.assertFalse(measure_pass(self.site(), self.frames(0.8))["three_foot_floor_observed"])

    def test_early_return_observed(self):
        frames = self.frames(early_return=True)
        frames[2]["vehicle_box"] = (11.0, 13.0, 0.0, 2.0)
        frames.append({**frames[-1], "original_frame": 3, "time_s": .15,
                       "vehicle_box": (13.0, 15.0, 0.0, 2.0)})
        m = measure_pass(self.site(), frames)
        self.assertFalse(m["longitudinal_clear_before_return"])

    def test_exact_floor_geometry(self):
        self.assertAlmostEqual(rectangle_gap((0, 1, 0, 1), (0, 1, 1 + THREE_FEET_M, 2)), THREE_FEET_M)

    def test_reject_wrong_lane_and_missing_sources(self):
        site = self.site()
        site["lane_count_same_direction"] = 2
        with self.assertRaisesRegex(ValueError, "single"):
            measure_pass(site, self.frames())
        frames = self.frames()
        frames[1]["bicycle_source"] = ""
        with self.assertRaisesRegex(ValueError, "unbound"):
            measure_pass(self.site(), frames)

    def test_reject_no_pass(self):
        frames = self.frames()
        for f in frames:
            f["vehicle_box"] = (0, 4, 1.5, 3.5)
        with self.assertRaisesRegex(ValueError, "no longitudinal"):
            measure_pass(self.site(), frames)

    def test_reject_overlap_without_completed_pass(self):
        frames = self.frames()
        frames[2]["vehicle_box"] = (9.0, 11.0, 1.5, 3.5)
        with self.assertRaisesRegex(ValueError, "did not finish"):
            measure_pass(self.site(), frames)


if __name__ == "__main__":
    unittest.main()
