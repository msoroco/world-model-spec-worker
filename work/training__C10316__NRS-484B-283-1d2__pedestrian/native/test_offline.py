import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from engineering import candidate
from geometry import check as check_geometry
from measure_countdown import measure
from runner import check as check_runner
from signal_clock import frame_state
from signal_head import command_and_sample, resolve, sample

HERE = Path(__file__).resolve().parent.parent


class FakeHead:
    type_id = 'traffic.traffic_light'
    id = 77

    def __init__(self, opendrive_id='203'):
        self.opendrive_id = opendrive_id
        self.state = 'Off'
        self.frozen = False

    def get_opendrive_id(self):
        return self.opendrive_id

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def freeze(self, value):
        self.frozen = value


class CountdownOffline(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((HERE / 'config.json').read_text())
        result = check_runner(config)
        self.assertEqual(result['frames'], 600)
        self.assertEqual(len(result['cameras']), 4)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_display_verified'])

    def test_authored_crosswalk_covers_road(self):
        measured = check_geometry(HERE / 'road.xodr')
        self.assertEqual((measured['near_edge_x_m'], measured['far_edge_x_m']), (-3.5, 3.5))
        self.assertEqual(measured['road_width_m'], 7)
        self.assertFalse(measured['legal_highway_status_verified'])

    def test_ordered_frame_schedules(self):
        config = json.loads((HERE / 'config.json').read_text())
        zero = candidate(config['case_suffix'], config['candidate_id'])['engineering']['countdown_zero_s']
        states = [frame_state(i, zero) for i in range(600)]
        self.assertEqual(states[0]['displayed_countdown_s'], int(zero))
        self.assertEqual(next(i for i, state in enumerate(states) if state['displayed_countdown_s'] == 0), int(zero*20))
        self.assertEqual([state['display_illuminated'] for state in states[:20]],
                         [True]*5+[False]*5+[True]*5+[False]*5)

    def test_missing_case_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing required source: countdown_samples.jsonl'):
                measure(Path(folder) / 'countdown_samples.jsonl', Path(folder) / 'countdown-context.json')

    def test_authored_head_state_readback(self):
        head = FakeHead()
        self.assertIs(resolve([head, FakeHead('999')]), head)
        states = SimpleNamespace(TrafficLightState=SimpleNamespace(Red='Red', Off='Off'))
        for indication, lit, expected in (('dont_walk_flashing', True, 'Red'),
                                          ('dont_walk_flashing', False, 'Off'),
                                          ('dont_walk_steady', True, 'Red')):
            receipt = command_and_sample(head, states, indication, lit)
            self.assertEqual(receipt['native_state'], expected)
            self.assertEqual(receipt['source'], 'native_actor_readback')
            self.assertTrue(head.frozen)
        head.state = 'Green'
        with self.assertRaisesRegex(ValueError, 'state differs'):
            sample(head, 'dont_walk_steady', True)

    def test_missing_or_ambiguous_head_rejected(self):
        for actors in ([], [FakeHead('999')], [FakeHead(), FakeHead()]):
            with self.assertRaisesRegex(ValueError, 'Exactly one'):
                resolve(actors)


if __name__ == '__main__':
    unittest.main()
