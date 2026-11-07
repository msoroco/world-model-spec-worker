import json
from pathlib import Path
import tempfile
import unittest

from engineering import candidate, evaluate_fallbacks
from geometry import check as check_geometry
from exception import measure, signal_state
from statutory_context import assess as assess_statutory_context
from runner import check as check_runner

HERE = Path(__file__).resolve().parent.parent


class PriorEntryOffline(unittest.TestCase):
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
        program = plan['engineering']['entry_program']
        states = [signal_state(i, program) for i in range(240)]
        self.assertEqual(states[0], ('walk', True))
        self.assertEqual(next(i for i, state in enumerate(states) if state[0] == 'dont_walk_steady'), 80)
        self.assertEqual(states[18][0], 'dont_walk_flashing' if config['case_suffix'] == 'exception_1_1' else 'walk')

    def test_missing_case_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing required source: exception-samples.jsonl'):
                measure(Path(folder) / 'exception-samples.jsonl', Path(folder) / 'exception-context.json')
            with self.assertRaisesRegex(ValueError, 'Missing required source: exception-samples.jsonl'):
                evaluate_fallbacks(Path(folder) / 'exception-samples.jsonl',
                                   Path(folder) / 'exception-context.json')

    def test_statutory_context_requires_source_facts(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source-measurement.json'
            source.write_text(json.dumps({'format': 'c10316-prior-entry-source-observation-v1',
                                          'source_sha256': {}, 'legal_verdict_claimed': False}))
            assessment = assess_statutory_context(HERE / 'statutory-context-contract.json', source)
            self.assertEqual(len(assessment['branches']), 12)
            self.assertTrue(all(row['missing_source_facts'] for row in assessment['branches']))
            self.assertFalse(assessment['physical_context_observed'])
            self.assertFalse(assessment['legal_applicability_determined'])


if __name__ == '__main__':
    unittest.main()
