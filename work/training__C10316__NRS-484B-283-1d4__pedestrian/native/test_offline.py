import json
from pathlib import Path
import tempfile
import unittest

from engineering import candidate
from geometry import check as check_geometry
from steady import measure, signal_state
from runner import check as check_runner

HERE = Path(__file__).resolve().parent.parent


class SteadyOffline(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((HERE / 'config.json').read_text())
        result = check_runner(config)
        self.assertEqual(result['frames'], 240)
        self.assertEqual(len(result['cameras']), 4)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_display_verified'])

    def test_authored_crosswalk_covers_road(self):
        measured = check_geometry(HERE / 'road.xodr')
        self.assertEqual((measured['near_edge_x_m'], measured['far_edge_x_m']), (-3.5, 3.5))
        self.assertEqual(measured['road_width_m'], 7)
        self.assertFalse(measured['legal_highway_status_verified'])

    def test_full_phase_schedule_and_controlled_entry(self):
        config = json.loads((HERE / 'config.json').read_text())
        plan = candidate(config['case_suffix'], config['candidate_id'])
        start = plan['engineering']['steady_start_s']
        states = [signal_state(i, start) for i in range(240)]
        self.assertEqual(states[0], ('walk', True))
        self.assertEqual(next(i for i, state in enumerate(states) if state[0] == 'dont_walk_steady'), int(start*20))
        self.assertEqual(states[18][0], 'walk' if config['case_suffix'] == 'witness_1' else 'dont_walk_steady')

    def test_missing_case_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing required source: steady-samples.jsonl'):
                measure(Path(folder) / 'steady-samples.jsonl', Path(folder) / 'steady-context.json')


if __name__ == '__main__':
    unittest.main()
