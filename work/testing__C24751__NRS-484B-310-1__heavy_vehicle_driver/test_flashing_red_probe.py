import unittest

from flashing_red_probe import Site, measure, occluded, stop_reference


class FlashingRedProbeTests(unittest.TestCase):
    def site(self, crosswalk=20.0, limit=19.0):
        return Site("northbound", "signal-A", "northbound", crosswalk, limit,
                    22.0, ((8.0, 1.0), (10.0, 1.0), (10.0, 3.0), (8.0, 3.0)),
                    12.0, 2.5, 3.5)

    def frames(self, stop_front=18.5):
        return [dict(original_frame=i, time_s=i * 0.05, front_m=x,
                     speed_mps=v, red_lit=lit, signal_id="signal-A",
                     approach_id="northbound", source_ref="native/signal-and-motion.json")
                for i, x, v, lit in ((0, 17.0, 2.0, True),
                                     (1, stop_front, 0.0, False),
                                     (2, stop_front, 0.0, True))]

    def test_alternative_stop_references(self):
        self.assertEqual(stop_reference(self.site()), ("crosswalk", 20.0))
        self.assertEqual(stop_reference(self.site(None)), ("limit_line", 19.0))
        self.assertEqual(stop_reference(self.site(None, None)), ("intersection", 22.0))

    def test_real_occluder_segment(self):
        corners = self.site().occluder_corners_m
        self.assertTrue(occluded((0, 0), (16, 4), corners))
        self.assertFalse(occluded((0, -2), (16, -2), corners))

    def test_source_bound_stop_and_roll_through(self):
        result = measure(self.site(), self.frames())
        self.assertTrue(result["stopped_before_reference"])
        self.assertEqual(result["post_stop_rules"], "unresolved")
        self.assertFalse(measure(self.site(), self.frames(21.0))["stopped_before_reference"])

    def test_reject_nonflashing_signal_and_wrong_approach(self):
        frames = self.frames()
        for frame in frames:
            frame["red_lit"] = True
        with self.assertRaisesRegex(ValueError, "intermittent"):
            measure(self.site(), frames)
        with self.assertRaisesRegex(ValueError, "govern"):
            stop_reference(Site("northbound", "signal-A", "southbound", 20, 19, 22,
                                self.site().occluder_corners_m, 12, 2.5, 3.5))

    def test_reject_missing_source_and_lane_fit(self):
        frames = self.frames()
        del frames[0]["source_ref"]
        with self.assertRaisesRegex(ValueError, "missing original"):
            measure(self.site(), frames)
        with self.assertRaisesRegex(ValueError, "cannot fit"):
            stop_reference(Site("northbound", "signal-A", "northbound", 20, 19, 22,
                                self.site().occluder_corners_m, 12, 4, 3.5))


if __name__ == "__main__":
    unittest.main()
