import unittest

from aggressive_sequence import MILE_M, measure_sequence
from two_pass_construction import PHASES, phase_at, transition_guard, validate_schedule


def sample(distance_m):
    return [{"frame": i, "time_s": i * .05, "driver_id": "ego-driver",
             "x_m": i * distance_m / 6, "y_m": 0} for i in range(7)]


def episodes():
    return [{"start_frame": start, "end_frame": end, "target_vehicle_id": 9,
             "before_gap_m": -2, "after_gap_m": 2,
             "rightward_separation_m": 1, "off_pavement_frames": [end]}
            for start, end in ((1, 2), (4, 5))]


class SequenceTests(unittest.TestCase):
    def test_two_pass_requests_have_reentry_and_original_geometry_guards(self):
        self.assertTrue(validate_schedule())
        self.assertEqual(phase_at(300).name, 'first_right_pass_request')
        self.assertEqual(phase_at(480).name, 'first_reentry')
        self.assertEqual(phase_at(540).name, 'lead_reclaim_request')
        self.assertEqual(phase_at(620).name, 'second_reentry')
        self.assertEqual(phase_at(750).name, 'second_right_pass_request')
        self.assertEqual(PHASES[1].ego_target, 'right_of_paved_edge')
        self.assertEqual(PHASES[3].ego_speed_mps, 6)
        self.assertGreater(PHASES[3].lead_speed_mps, PHASES[3].ego_speed_mps)
        nominal_to_second_pass_s = sum((p.end_m-p.start_m)/p.ego_speed_mps for p in PHASES[:-1])
        self.assertLess(nominal_to_second_pass_s, 60)
        first_gain_m = (PHASES[1].ego_speed_mps-PHASES[1].lead_speed_mps) * (PHASES[1].end_m-PHASES[1].start_m)/PHASES[1].ego_speed_mps
        reclaim_gain_m = (PHASES[3].lead_speed_mps-PHASES[3].ego_speed_mps) * (PHASES[3].end_m-PHASES[3].start_m)/PHASES[3].ego_speed_mps
        second_gain_m = (PHASES[5].ego_speed_mps-PHASES[5].lead_speed_mps) * (PHASES[5].end_m-PHASES[5].start_m)/PHASES[5].ego_speed_mps
        self.assertGreater(-15 + first_gain_m, 5)
        self.assertLess(-15 + first_gain_m - reclaim_gain_m, -5)
        self.assertGreater(-15 + first_gain_m - reclaim_gain_m + second_gain_m, 5)
        for previous, current, gap, edge in (
            ('approach', 'first_right_pass_request', -12, -1),
            ('first_right_pass_request', 'first_reentry', 12, 2),
            ('first_reentry', 'lead_reclaim_request', 10, -1),
            ('lead_reclaim_request', 'second_reentry', -12, 2),
            ('second_reentry', 'second_right_pass_request', -12, -1),
        ):
            self.assertTrue(transition_guard(previous, current, gap, edge))
        for previous, current, gap, edge in (
            ('approach', 'first_right_pass_request', 2, -1),
            ('first_right_pass_request', 'first_reentry', -2, 2),
            ('first_reentry', 'lead_reclaim_request', 10, 2),
            ('lead_reclaim_request', 'second_reentry', 8, 2),
            ('second_reentry', 'second_right_pass_request', -12, 2),
        ):
            with self.assertRaises(ValueError):
                transition_guard(previous, current, gap, edge)

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
