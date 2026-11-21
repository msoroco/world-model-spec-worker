"""Numerical long-duration checks; generated samples are never Native proof."""
import unittest

from geometry import body, ego_y, other_x
from measure import measure_arrow_and_yield


def samples(yield_to_other=True):
    result = []
    for frame in range(840):
        other_body = body(other_x(frame), -1.75, 'east')
        within = any(-7 < vertex[0] < 7 for vertex in other_body) and frame < 169
        result.append({
            'native_frame': frame,
            'native_body_xy_m': body(1.75, ego_y(frame, yield_to_other), 'north'),
            'native_yaw_deg': 90.0, 'speed_mps': 0.0 if yield_to_other and 100 <= frame < 169 else 4.0,
            'governing_signal': {
                'native_actor_id': 22, 'native_state': 'Red' if frame < 100 else 'Green',
                'authored_aspect': 'green_straight_arrow', 'facing_ego_native_survey': True,
                'pixel_aspect_verified': frame >= 100},
            'other_vehicle': {
                'native_actor_id': 23, 'native_body_xy_m': other_body,
                'within_intersection_or_adjacent_crosswalk': within},
        })
    return result


class MeasureStraightArrow(unittest.TestCase):
    def test_42_second_yield_and_non_yield(self):
        safe = measure_arrow_and_yield(samples(True))
        unsafe = measure_arrow_and_yield(samples(False))
        self.assertEqual(safe['sole_arrow_pixel_verified_frames'], 740)
        self.assertTrue(safe['yielded_before_entry'])
        self.assertFalse(unsafe['yielded_before_entry'])
        self.assertTrue(safe['straight_heading_no_turn_observed'])
        self.assertFalse(safe['other_vehicle_lawful_entry_inferred'])

    def test_missing_pixel_aspect_fails_closed(self):
        source = samples(True)
        for row in source:
            row['governing_signal']['pixel_aspect_verified'] = False
        with self.assertRaisesRegex(ValueError, 'No verified sole'):
            measure_arrow_and_yield(source)


if __name__ == '__main__':
    unittest.main()
