import json
from pathlib import Path
import tempfile
import unittest

from engineering import candidate
from geometry import check as check_geometry
from measure_countdown import measure
from runner import check as check_runner
from signal_clock import frame_state

HERE = Path(__file__).resolve().parent.parent


class CountdownOffline(unittest.TestCase):
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

    def test_ordered_frame_schedules(self):
        config = json.loads((HERE / 'config.json').read_text())
        zero = candidate(config['case_suffix'], config['candidate_id'])['engineering']['countdown_zero_s']
        states = [frame_state(i, zero) for i in range(240)]
        self.assertEqual(states[0]['displayed_countdown_s'], int(zero))
        self.assertEqual(next(i for i, state in enumerate(states) if state['displayed_countdown_s'] == 0), int(zero*20))
        self.assertEqual([state['display_illuminated'] for state in states[:20]],
                         [True]*5+[False]*5+[True]*5+[False]*5)

    def test_missing_case_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing required source: countdown_samples.jsonl'):
                measure(Path(folder) / 'countdown_samples.jsonl', Path(folder) / 'countdown-context.json')


if __name__ == '__main__':
    unittest.main()
