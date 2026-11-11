import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opposing_left_control import turn_release_step
from test_opposing_left_source import Actor


class TurnControlTests(unittest.TestCase):
    def test_waits_for_original_body_entry_and_full_clearance(self):
        zone = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
        actor = Actor(12, 9, 0, -1, 0)
        state = turn_release_step(actor, zone, opposite_seen_in_zone=False,
                                  turning_released=False)
        self.assertFalse(state['turning_released'])
        actor.x = 0
        state = turn_release_step(actor, zone, opposite_seen_in_zone=state['opposite_seen_in_zone'],
                                  turning_released=state['turning_released'])
        self.assertTrue(state['opposite_body_overlaps_zone'])
        self.assertFalse(state['turning_released'])
        actor.x = -4
        state = turn_release_step(actor, zone, opposite_seen_in_zone=state['opposite_seen_in_zone'],
                                  turning_released=state['turning_released'])
        self.assertTrue(state['turning_released'])
        self.assertEqual(state['turning_speed_mps'], 4.0)
        actor.x = 0
        self.assertTrue(turn_release_step(actor, zone, opposite_seen_in_zone=True,
                                          turning_released=True)['turning_released'])

    def test_invalid_zone_rejected(self):
        with self.assertRaisesRegex(ValueError, 'polygon invalid'):
            turn_release_step(Actor(12, 0, 0, 1, 0), [[0, 0]],
                              opposite_seen_in_zone=False, turning_released=False)
