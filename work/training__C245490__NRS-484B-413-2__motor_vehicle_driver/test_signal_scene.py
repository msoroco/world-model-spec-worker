"""CPU test for exact requested signal onset and lane-change schedule."""
import unittest

from signal_scene import CASE_SUFFIXES, DISTANCES_FT, controls, request, road_xml, verify_road


class SignalSceneTest(unittest.TestCase):
    def test_six_exact_boundaries(self):
        plans = [request(distance) for distance in DISTANCES_FT]
        self.assertEqual([p['area_class_requested'] for p in plans],
            ['business_or_residential'] * 3 + ['other'] * 3)
        self.assertEqual([p['frames'] for p in plans], [600] * 6)
        for distance, plan in zip(DISTANCES_FT, plans):
            onset = plan['signal_onset_odometer_m']
            self.assertFalse(controls(distance, onset - 0.01)['signal_requested'])
            self.assertTrue(controls(distance, onset)['signal_requested'])
            self.assertFalse(controls(distance, 119.99)['lane_change_requested'])
            self.assertTrue(controls(distance, 120.0)['lane_change_requested'])
            self.assertAlmostEqual((120.0 - onset) / .3048, distance)

    def test_district_and_other_area_not_mixed(self):
        self.assertLess(request(310)['signal_onset_odometer_m'],
                        request(90)['signal_onset_odometer_m'])
        with self.assertRaisesRegex(ValueError, 'Unselected'):
            request(200)
        with self.assertRaisesRegex(ValueError, 'odometer'):
            controls(100, float('nan'))

    def test_same_direction_two_lane_road(self):
        road = verify_road(road_xml())
        self.assertEqual(road['lane_ids'], ['-1', '-2'])
        self.assertGreater(road['length_m'], 120 + 95)
        with self.assertRaisesRegex(ValueError, 'change-lane'):
            verify_road(road_xml().replace('id="-2"', 'id="2"'))

    def test_same_cell_signal_variants(self):
        self.assertEqual(len(CASE_SUFFIXES), 12)
        for threshold in (100, 300):
            baseline = request(threshold)
            interrupted = request(f'{threshold}_interrupt')
            rainy = request(f'{threshold}_rain')
            right = request(f'{threshold}_right')
            self.assertEqual(baseline['signal_onset_odometer_m'],
                interrupted['signal_onset_odometer_m'])
            start = interrupted['signal_onset_odometer_m']
            self.assertFalse(controls(f'{threshold}_interrupt',
                start + 12 * .3048)['signal_requested'])
            self.assertTrue(controls(f'{threshold}_interrupt',
                start + 16 * .3048)['signal_requested'])
            self.assertEqual(rainy['weather_requested'], 'rain')
            self.assertEqual(right['signal_side'], 'right')


if __name__ == '__main__':
    unittest.main()
