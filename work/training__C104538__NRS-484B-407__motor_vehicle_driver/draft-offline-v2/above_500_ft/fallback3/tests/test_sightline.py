import math
import unittest
from geometry import (FT_M, OBSERVER_DISTANCES_FT, check, open_drive,
                      obstruction_radius_for_limit)
from sightline import measure_case, sight_ray


class C104538SightlineTest(unittest.TestCase):
    def test_authored_curve_and_crest(self):
        result = check()
        self.assertTrue(result['passed'])
        self.assertFalse(result['native_loaded'])
        self.assertIn('<arc curvature=', open_drive())

    def test_both_approach_directions_at_all_three_distances(self):
        for suffix, distance in OBSERVER_DISTANCES_FT.items():
            with self.subTest(suffix=suffix):
                result = measure_case(suffix)
                self.assertEqual(len(result['rays_at_500_ft']), 2)
                self.assertTrue(all(ray['observer_distance_ft'] == 500
                                    for ray in result['rays_at_500_ft']))
                self.assertAlmostEqual(result['measured_authored_reference_limit_ft'],distance)
                self.assertEqual(result['rays_at_500_ft'][0]['reference_ray_blocked'],
                                 result['rays_at_500_ft'][1]['reference_ray_blocked'])
                self.assertFalse(result['native_verified'])
                self.assertFalse(result['legal_verdict_claimed'])

    def test_500_foot_reference_boundary(self):
        below = measure_case('below_500_ft')['rays_at_500_ft'][0]
        boundary = measure_case('at_500_ft')['rays_at_500_ft'][0]
        above = measure_case('above_500_ft')['rays_at_500_ft'][0]
        self.assertLess(below['signed_radial_clearance_m'], 0)
        self.assertAlmostEqual(boundary['signed_radial_clearance_m'], 0, places=8)
        self.assertGreater(above['signed_radial_clearance_m'], 0)
        self.assertTrue(below['reference_ray_blocked'])
        self.assertFalse(boundary['reference_ray_blocked'])
        self.assertFalse(above['reference_ray_blocked'])
        self.assertAlmostEqual(boundary['observer_distance_ft'] * FT_M, 152.4)

    def test_rejects_wrong_case_and_bad_ray(self):
        with self.assertRaisesRegex(ValueError, 'Unknown C104538 case'):
            measure_case('invented')
        for distance, direction in ((500, 0), (math.nan, 1), (-1, 1)):
            with self.subTest(distance=distance, direction=direction):
                with self.assertRaises(ValueError):
                    sight_ray(distance, direction, obstruction_radius_for_limit(500))


if __name__ == '__main__':
    unittest.main()
