"""Exercise source-driven pass and post-clearance controller branches."""

import unittest

from controller import INNER_LEFT_RADIUS_M, OUTER_RIGHT_RADIUS_M, SourceState, request


class ControllerTests(unittest.TestCase):
    def state(self, cleared=False, slower=True):
        return SourceState(3.0, OUTER_RIGHT_RADIUS_M, 2.5,
                           8.0 if slower else None,
                           2.0 if slower else None, cleared)

    def test_lane_pair_and_pass_duration(self):
        self.assertEqual(request('probe_a', self.state()).target_radius_m, OUTER_RIGHT_RADIUS_M)
        self.assertEqual(request('probe_b', self.state()).target_radius_m, INNER_LEFT_RADIUS_M)
        during = request('necessary_pass', self.state())
        self.assertEqual((during.phase, during.pass_requested, during.target_radius_m),
                         ('pass_in_progress', True, INNER_LEFT_RADIUS_M))
        return_right = request('necessary_pass', self.state(cleared=True))
        linger = request('post_pass_linger', self.state(cleared=True))
        self.assertEqual((return_right.phase, return_right.target_radius_m),
                         ('return_after_pass', OUTER_RIGHT_RADIUS_M))
        self.assertEqual((linger.phase, linger.target_radius_m),
                         ('linger_after_pass', INNER_LEFT_RADIUS_M))
        self.assertFalse(return_right.pass_requested)
        self.assertFalse(linger.pass_requested)

    def test_missing_original_slower_vehicle_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original slower-vehicle source'):
            request('necessary_pass', self.state(slower=False))


if __name__ == '__main__':
    unittest.main()
