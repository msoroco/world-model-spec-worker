import unittest

from turn_signal_probe import FEET_TO_METERS, measure, required_distance_m


class TurnSignalProbeTests(unittest.TestCase):
    def context(self, district="business", weather="rain"):
        return dict(district=district, district_source="map/district.json",
                    weather=weather, weather_source="native/weather.json",
                    maneuver="right_turn", route_source="map/route.json", vehicle_id="ego")

    def frames(self, first_signal=0, spacing=10.0):
        return [dict(original_frame=i, time_s=i * 0.05, xy=(i * spacing, 0.0),
                     signal="right" if i >= first_signal else "off",
                     course_changed=i == 5, motion_source="native/motion.json",
                     signal_source="native/indicator.json", vehicle_id="ego")
                for i in range(6)]

    def test_exact_statutory_distances(self):
        self.assertEqual(required_distance_m("residential"), 100 * FEET_TO_METERS)
        self.assertEqual(required_distance_m("other"), 300 * FEET_TO_METERS)

    def test_continuous_business_signal(self):
        result = measure(self.context(), self.frames())
        self.assertTrue(result["distance_floor_observed"])
        self.assertEqual(result["continuous_start_original_frame"], 0)
        self.assertEqual(result["weather"], "rain")

    def test_short_and_interrupted_signal(self):
        self.assertFalse(measure(self.context(), self.frames(3))["distance_floor_observed"])
        frames = self.frames()
        frames[3]["signal"] = "off"
        self.assertFalse(measure(self.context(), frames)["distance_floor_observed"])

    def test_other_area_300_feet_and_weather_independence(self):
        frames = self.frames(spacing=20.0)
        self.assertTrue(measure(self.context("other", "clear"), frames)["distance_floor_observed"])
        self.assertTrue(measure(self.context("other", "snow"), frames)["distance_floor_observed"])

    def test_reject_missing_sources_and_course_onset(self):
        frames = self.frames()
        frames[2]["signal_source"] = ""
        with self.assertRaisesRegex(ValueError, "missing original"):
            measure(self.context(), frames)
        frames = self.frames()
        frames[4]["course_changed"] = True
        with self.assertRaisesRegex(ValueError, "exact course-change"):
            measure(self.context(), frames)

    def test_reject_missing_original_frame_or_time_join(self):
        frames = self.frames()
        frames[3]["original_frame"] = 4
        with self.assertRaisesRegex(ValueError, "20 Hz frame/time join"):
            measure(self.context(), frames)
        frames = self.frames()
        frames[3]["time_s"] += 0.02
        with self.assertRaisesRegex(ValueError, "20 Hz frame/time join"):
            measure(self.context(), frames)


if __name__ == "__main__":
    unittest.main()
