"""CPU checks for the proposed signal/yield action path; no Native claim."""
import unittest

from controller import choose_action
from geometry import ARROW_FRAME, OTHER_CLEAR_FRAME, check, ego_y, other_x


def arrow(frame):
    return {'frame': frame, 'faces_ego': True, 'aspects': ['green_straight_arrow']}


def other(frame, within=True):
    return {'frame': frame, 'actor_id': 'other_01', 'kind': 'motor_vehicle',
            'lawfully_within': True, 'within_intersection_or_adjacent_crosswalk': within}


class StraightArrowYield(unittest.TestCase):
    def test_conflict_hold_and_release(self):
        self.assertTrue(check()['passed'])
        at_arrow = choose_action(arrow(ARROW_FRAME), [other(ARROW_FRAME)], frame=ARROW_FRAME)
        self.assertEqual((at_arrow['target_speed_m_s'], at_arrow['brake'], at_arrow['turn_command']),
                         (0.0, 1.0, 0.0))
        self.assertEqual(ego_y(120, True), ego_y(ARROW_FRAME, True))
        self.assertGreater(ego_y(120, False), ego_y(ARROW_FRAME, False))
        after_clear = choose_action(arrow(OTHER_CLEAR_FRAME),
                                    [other(OTHER_CLEAR_FRAME, within=False)], frame=OTHER_CLEAR_FRAME)
        self.assertGreater(other_x(OTHER_CLEAR_FRAME), 7)
        self.assertEqual((after_clear['target_speed_m_s'], after_clear['brake']), (4.0, 0.0))

    def test_missing_or_mixed_signal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'same-frame governing signal'):
            choose_action(arrow(101), [], frame=100)
        with self.assertRaisesRegex(ValueError, 'Sole green'):
            choose_action({'frame': 100, 'faces_ego': True,
                           'aspects': ['green_straight_arrow', 'green_right_arrow']}, [], frame=100)
        with self.assertRaisesRegex(ValueError, 'right-of-way'):
            choose_action(arrow(100), [{'frame': 100, 'actor_id': 'other_01',
                                        'kind': 'motor_vehicle'}], frame=100)


if __name__ == '__main__':
    unittest.main()
