"""Exercise exact boarding/alighting door actuation and traffic schedules."""

import json
import unittest
from pathlib import Path

from controller import CASES, request, verify_schedule
from door_actuation import apply_door_command
from runner import check


ROOT = Path(__file__).resolve().parents[1]


class DoorInterferenceConstructionTest(unittest.TestCase):
    def test_all_exact_cases(self):
        config = json.loads((ROOT / 'config.json').read_text())
        suffix = config['schedule']
        specification = CASES[suffix]
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(config['occupancy_delta_requested'], specification['occupancy_delta'])
        self.assertEqual(request(suffix, 200)['transfer_request'], specification['transfer'])
        self.assertEqual(sum(request(suffix, i)['passing_vehicle_request'] != 'none' for i in range(600)), 101)

    def test_controlled_traffic_arrival(self):
        self.assertEqual(verify_schedule()['deliberate_difference'], 'passing traffic arrival window')
        for transfer in ('board', 'alight'):
            near = [request(transfer + '_overlap', i) for i in range(600)]
            later = [request(transfer + '_clear', i) for i in range(600)]
            self.assertEqual([row['traffic_side_door_request'] for row in near],
                             [row['traffic_side_door_request'] for row in later])
            self.assertEqual([row['transfer_request'] for row in near],
                             [row['transfer_request'] for row in later])
            self.assertNotEqual([row['passing_vehicle_request'] for row in near],
                                [row['passing_vehicle_request'] for row in later])

    def test_actuator_transitions(self):
        class Vehicle:
            def __init__(self):
                self.calls = []
            def open_door(self, door):
                self.calls.append(('open', door))
            def close_door(self, door):
                self.calls.append(('closed', door))
        for suffix in CASES:
            car = Vehicle()
            for i in range(600):
                apply_door_command(car, 'FL', suffix, i)
            self.assertEqual(car.calls, [('closed', 'FL'), ('open', 'FL'), ('closed', 'FL')])

    def test_command_cannot_claim_observation(self):
        config = json.loads((ROOT / 'config.json').read_text())
        config['door_state_observed_by_command'] = True
        with self.assertRaisesRegex(ValueError, 'Command cannot establish'):
            check(config)


if __name__ == '__main__':
    unittest.main()
