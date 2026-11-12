import unittest

from aggressive_sequence import MILE_M, measure_sequence


def sample(distance_m):
    return [{"frame": i, "time_s": i * .05, "driver_id": "ego-driver",
             "x_m": i * distance_m / 6, "y_m": 0} for i in range(7)]


def episodes():
    return [{"start_frame": start, "end_frame": end, "target_vehicle_id": 9,
             "before_gap_m": -2, "after_gap_m": 2,
             "rightward_separation_m": 1, "off_pavement_frames": [end]}
            for start, end in ((1, 2), (4, 5))]


class SequenceTests(unittest.TestCase):
    def test_event_envelope_below_at_and_above_one_mile(self):
        for distance, expected in ((MILE_M - .01, True), (MILE_M, True),
                                   (MILE_M + .01, False)):
            result = measure_sequence(sample(distance), episodes(), [0], [6])
            self.assertEqual(result["within_one_mile_envelope"], expected)
            self.assertTrue(result["two_distinct_right_passing_episodes_measured"])
            self.assertFalse(result["offense_decided"])

    def test_rejects_discontinuous_or_unsupported_events(self):
        rows = sample(100)
        rows[3]["frame"] = 8
        with self.assertRaisesRegex(ValueError, "discontinuous"):
            measure_sequence(rows, episodes(), [0], [6])
        with self.assertRaisesRegex(ValueError, "Off-pavement"):
            measure_sequence(sample(100), [dict(episodes()[0], off_pavement_frames=[])], [0], [6])
        overlapping = episodes()
        overlapping[1]["start_frame"] = 2
        with self.assertRaisesRegex(ValueError, "overlap"):
            measure_sequence(sample(100), overlapping, [0], [6])
        wrong_target = episodes()
        wrong_target[1]["target_vehicle_id"] = 10
        with self.assertRaisesRegex(ValueError, "Fixed overtaken vehicle"):
            measure_sequence(sample(100), wrong_target, [0], [6])
        with self.assertRaisesRegex(ValueError, "Off-pavement source frames"):
            measure_sequence(sample(100), [dict(episodes()[0], off_pavement_frames=[999])], [0], [6])


if __name__ == "__main__":
    unittest.main()
