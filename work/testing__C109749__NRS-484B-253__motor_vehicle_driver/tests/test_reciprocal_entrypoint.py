"""Exact reciprocal CLI selects the seven-actor original capture path."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from reciprocal_entrypoint import run_native
from saved_left_turn import ASSIGNMENT_ID
from test_carla_scene_factory import API, World, packet


class ReciprocalEntrypointTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'c109749-reciprocal-entrypoint-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.packet = packet(self.world)
        self.packet['later_opposing_route'] = list(self.packet['opposing_route'])
        self.config = {'law_id': 'NRS-484B-253', 'cell_id': 'C109749',
                       'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                       'duration_s': 45,
                       'cameras': ['overview', 'approach', 'reference_corner',
                                   'driver_reference'],
                       'selected_case_id': ASSIGNMENT_ID + '__reciprocal_yield',
                       'controller': {'wait_for_initial_opponent': True,
                                      'signal_left': True,
                                      'wait_for_later_opponent': True,
                                      'target_speed_mps': 5.0}}
        self.config_path = self.root / 'config.json'
        self.map_path = self.root / 'map.json'
        self.output = self.root / 'attempt'

    def invoke(self):
        self.config_path.write_text(json.dumps(self.config) + '\n')
        self.map_path.write_text(json.dumps(self.packet) + '\n')
        client = SimpleNamespace(get_world=lambda: self.world)
        with mock.patch('reciprocal_live.run', return_value={'physical_acceptance': 'unverified'}) as run:
            result = run_native(self.config_path, self.map_path, self.output,
                                api=API, client=client)
        return result, run

    def test_both_reciprocal_cases_select_live_three_actor_runner(self):
        for suffix, wait in (('reciprocal_yield', True), ('reciprocal_no_yield', False)):
            self.config['selected_case_id'] = ASSIGNMENT_ID + '__' + suffix
            self.config['controller']['wait_for_later_opponent'] = wait
            result, runner = self.invoke()
            self.assertEqual(result['physical_acceptance'], 'unverified')
            self.assertEqual(runner.call_count, 1)
            self.assertTrue(callable(runner.call_args.kwargs['scene_factory']))
            self.assertEqual(runner.call_args.kwargs['output'], self.output)

    def test_rejects_nonreciprocal_or_diagnostic_before_client(self):
        self.config['selected_case_id'] = ASSIGNMENT_ID + '__inside_yield'
        self.config['controller']['wait_for_later_opponent'] = None
        with self.assertRaisesRegex(ValueError, 'separate later opponent'):
            self.invoke()
        self.config['selected_case_id'] = ASSIGNMENT_ID + '__reciprocal_yield'
        self.config['controller']['wait_for_later_opponent'] = True
        self.packet['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'reviewed original'):
            self.invoke()

    def test_rejects_nonempty_attempt(self):
        self.output.mkdir()
        (self.output / 'prior.txt').write_text('prior\n')
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            self.invoke()


if __name__ == '__main__':
    unittest.main()
