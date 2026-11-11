import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signal_advance_native_probe import (
    AdvanceIndicatorPolicy, prepare_probe, set_native_indicator)


class Waypoint:
    def __init__(self, x, *, lane=1):
        self.transform = NS(location=NS(x=x, y=0), rotation=NS(yaw=0))
        self.road_id = 8
        self.lane_id = lane
        self.is_junction = False

    def previous(self, distance):
        return [Waypoint(self.transform.location.x - distance, lane=2),
                Waypoint(self.transform.location.x - distance)]


class FakeActor:
    def __init__(self):
        self.state = 0
        self.calls = []

    def set_light_state(self, state):
        self.calls.append(state)
        self.state = state

    def get_light_state(self):
        return self.state


class SignalNativeProbeTests(unittest.TestCase):
    def setUp(self):
        self.outside = Waypoint(-35)
        self.selected = {'ego': {'outside': self.outside, 'approach_length_m': 35},
                         'oncoming': {'outside': Waypoint(35)}, 'left_route': [1]}

    def test_below_at_above_both_distances_use_same_inbound_lane(self):
        for target in (25.0, 30.48, 36.0, 86.0, 91.44, 97.0):
            with self.subTest(target=target):
                planned = prepare_probe(self.selected, target_signal_m=target)
                choice = planned['ego']['outside']
                self.assertEqual(choice.lane_id, self.outside.lane_id)
                self.assertEqual(choice.road_id, self.outside.road_id)
                self.assertEqual(planned['oncoming'], self.selected['oncoming'])
                self.assertIs(self.selected['ego']['outside'], self.outside)
                self.assertGreaterEqual(planned['signal_probe']['planned_total_approach_m'], target + 8)
                self.assertEqual(planned['signal_probe']['planned_indicator_onset_after_m'],
                                 planned['signal_probe']['planned_total_approach_m'] - target)
                self.assertFalse(planned['signal_probe']['legal_verdict_asserted'])

    def test_rejects_unavailable_lane_and_unlisted_probe(self):
        class WrongLane(Waypoint):
            def previous(self, distance):
                return [Waypoint(-distance, lane=2)]
        self.selected['ego']['outside'] = WrongLane(-35)
        with self.assertRaisesRegex(ValueError, 'Same-lane'):
            prepare_probe(self.selected, target_signal_m=91.44)
        with self.assertRaisesRegex(ValueError, 'declared'):
            prepare_probe(self.selected, target_signal_m=40)

    def test_indicator_latches_after_observed_warmup_and_calls_actor(self):
        policy = AdvanceIndicatorPolicy(onset_after_m=8)
        actor = FakeActor()
        carla = NS(VehicleLightState=NS(LeftBlinker=1, NONE=0))
        for x, expected in ((0, False), (3, False), (6, False), (9, True), (10, True)):
            command = policy.step(ego_position_xy_m=(x, 0), turn_state='approach')
            self.assertEqual(command, expected)
            self.assertEqual(set_native_indicator(actor, carla, command), expected)
        self.assertEqual(actor.calls, [0, 0, 0, 1, 1])
        self.assertEqual(policy.path_m, 10)
        self.assertTrue(policy.step(ego_position_xy_m=(10, 0), turn_state='turn'))

    def test_early_turn_jump_and_bad_readback_rejected(self):
        policy = AdvanceIndicatorPolicy(onset_after_m=8)
        policy.step(ego_position_xy_m=(0, 0), turn_state='approach')
        with self.assertRaisesRegex(ValueError, 'precedes'):
            policy.step(ego_position_xy_m=(1, 0), turn_state='turn')
        with self.assertRaisesRegex(ValueError, 'jump'):
            policy.step(ego_position_xy_m=(20, 0), turn_state='approach')
        actor = FakeActor()
        actor.get_light_state = lambda: 0
        carla = NS(VehicleLightState=NS(LeftBlinker=1, NONE=0))
        with self.assertRaisesRegex(ValueError, 'readback'):
            set_native_indicator(actor, carla, True)


if __name__ == '__main__':
    unittest.main()
