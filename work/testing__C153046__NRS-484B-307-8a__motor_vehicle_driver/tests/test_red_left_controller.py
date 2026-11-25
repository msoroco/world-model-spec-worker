import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'red_left_controller.py'
spec = importlib.util.spec_from_file_location('red_left_controller_c153046', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def variables(**changes):
    base = {'signal_request': 'steady_red_alone',
            'stop_request': 'complete_stop', 'approach_position': 'extreme_left',
            'receiving_direction': 'one_way_left',
            'conflict_response_request': 'no_conflict'}
    base.update(changes)
    return base


def site(**changes):
    base = {'source_packet_sha256': 'packet', 'signal_actor_id': 'signal-9',
            'left_lane_id': 'left', 'inner_lane_id': 'inner',
            'receiving_direction': 'one_way_left'}
    base.update(changes)
    return base


def observation(frame=100, distance=1.5, speed=4.0, lane='left',
                participants=None, **changes):
    row = {'origin': 'native_world_snapshot', 'source_packet_sha256': 'packet',
           'signal_actor_id': 'signal-9', 'signal_state': 'steady_red_alone',
           'frame': frame, 'time_s': frame / 20,
           'ego_lane_id': lane, 'body_front_to_stop_m': distance,
           'speed_m_s': speed, 'directed_participants': participants or []}
    row.update(changes)
    return row


def participant(kind, occupied):
    return {'kind': kind, 'conflict_zone_occupied': occupied,
            'native_actor_id': kind + '-7', 'source_citation': 'native snapshot'}


class ControllerTests(unittest.TestCase):
    def test_earlier_hold_fallback_changes_only_trigger(self):
        primary = mod.RedLeftController('clear', variables(), site(), 1.0)
        fallback = mod.RedLeftController('clear', variables(), site(), 2.0)
        row = observation(distance=1.5, speed=1.0)
        self.assertEqual(primary.step(row)['action'], 'approach_stop_reference')
        self.assertEqual(fallback.step(row)['action'], 'hold_before_reference')
        with self.assertRaisesRegex(ValueError, 'outside tested range'):
            mod.RedLeftController('clear', variables(), site(), 4.0)

    def test_complete_stop_then_conflict_yield_then_turn(self):
        c = mod.RedLeftController('pedestrian_yield',
                                  variables(conflict_response_request='pedestrian_yield'), site())
        busy = [participant('pedestrian', True)]
        self.assertEqual(c.step(observation(100, 2.0, 4.0, participants=busy))['action'],
                         'approach_stop_reference')
        self.assertEqual(c.step(observation(101, 0.5, 1.0, participants=busy))['action'],
                         'hold_before_reference')
        stopped = c.step(observation(102, 0.5, 0.0, participants=busy))
        self.assertTrue(stopped['stop_observed'])
        self.assertEqual(c.step(observation(103, 0.5, 0.0, participants=busy))['action'],
                         'hold_for_directed_conflict')
        self.assertEqual(c.step(observation(104, 0.5, 0.0,
                                            participants=[participant('pedestrian', False)]))['action'],
                         'turn_left_request')

    def test_intentional_rolling_and_advance_remain_requests(self):
        c = mod.RedLeftController('rolling', variables(stop_request='rolling'), site())
        result = c.step(observation(distance=0.2, speed=0.8))
        self.assertEqual(result['action'], 'turn_left_request')
        self.assertFalse(result['stop_observed'])
        self.assertFalse(result['physical_acceptance_claimed'])
        c = mod.RedLeftController('traffic_advance',
                                  variables(conflict_response_request='traffic_advance'), site())
        result = c.step(observation(distance=0.2, speed=0.0,
                                    participants=[participant('traffic', True)]))
        self.assertEqual(result['action'], 'hold_before_reference')
        self.assertEqual(c.step(observation(101, distance=0.2, speed=0.0,
                                            participants=[participant('traffic', True)]))['action'],
                         'turn_left_request')

    def test_exact_site_lane_signal_and_time_are_required(self):
        with self.assertRaisesRegex(ValueError, 'receiving road'):
            mod.RedLeftController('two_way', variables(receiving_direction='two_way'), site())
        c = mod.RedLeftController('inner', variables(approach_position='inner_lane'), site())
        with self.assertRaisesRegex(ValueError, 'approach lane'):
            c.step(observation())
        self.assertEqual(c.step(observation(lane='inner'))['action'], 'approach_stop_reference')
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            c.step(observation(102, lane='inner'))
        c = mod.RedLeftController('clear', variables(), site())
        with self.assertRaisesRegex(ValueError, 'signal actor'):
            c.step(observation(signal_actor_id='other'))

    def test_missing_directed_conflict_source_rejected(self):
        c = mod.RedLeftController('ped',
                                  variables(conflict_response_request='pedestrian_yield'), site())
        with self.assertRaisesRegex(ValueError, 'participant absent'):
            c.step(observation())
        c = mod.RedLeftController('ped',
                                  variables(conflict_response_request='pedestrian_yield'), site())
        with self.assertRaisesRegex(ValueError, 'participant source missing'):
            c.step(observation(participants=[{'kind': 'pedestrian',
                                              'conflict_zone_occupied': True}]))


if __name__ == '__main__':
    unittest.main()
