"""Source-bound canonical dispatch and statutory comparison regression checks."""
import importlib.util
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c109137_runner', ROOT / 'runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class CanonicalCaseTests(unittest.TestCase):
    def test_every_exact_case_and_candidate_dispatches(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        for entry in manifest['cases']:
            for candidate in ['primary'] + [item['id'] for item in entry['candidates']]:
                command = RUNNER.command(entry['case_id'], candidate,
                                         RUNNER.REPO / '.runtime-work' / 'c109137' / 'test-dispatch')
                self.assertIn(entry['case_id'], command)
                self.assertIn(candidate, command)
                self.assertEqual(command[1], str(RUNNER.REPO / 'runtime.py'))
        self.assertEqual(len(manifest['cases']), 4)

    def test_unknown_case_and_output_are_rejected(self):
        case = json.loads((ROOT / 'execution-manifest.json').read_text())['cases'][0]['case_id']
        with self.assertRaisesRegex(ValueError, 'Unknown exact case'):
            RUNNER.command(case + '__wrong', 'primary', RUNNER.REPO / '.runtime-work' / 'c109137')
        with self.assertRaisesRegex(ValueError, 'Unknown exact case candidate'):
            RUNNER.command(case, 'fallback3', RUNNER.REPO / '.runtime-work' / 'c109137')
        with self.assertRaisesRegex(ValueError, 'Output must be under'):
            RUNNER.command(case, 'primary', RUNNER.REPO / 'work' / ROOT.name / 'tmp')

    def test_statutory_source_and_controlled_differences(self):
        statutory = runpy.run_path(str(ROOT / 'statutory_source_audit.py'))
        self.assertEqual(statutory['audit']()['case_count'], 4)
        with self.assertRaisesRegex(ValueError, 'Original zone'):
            statutory['audit'](True)
        comparisons = runpy.run_path(str(ROOT / 'comparison_audit.py'))
        for name, candidates in [('signal_request_pair', ('primary', 'fallback1', 'fallback2')),
                                 ('following_response_pair', ('primary', 'fallback2'))]:
            for candidate in candidates:
                self.assertTrue(comparisons['audit'](name, candidate)['passed'])
                with self.assertRaisesRegex(ValueError, 'fixed source changed'):
                    comparisons['audit'](name, candidate, True)


if __name__ == '__main__':
    unittest.main()
