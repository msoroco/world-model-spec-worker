"""Source-bound CPU checks for the two selected opposite-direction passes."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]


class SelectedOppositePassTests(unittest.TestCase):
    def run_script(self, relative, *args):
        result = subprocess.run([sys.executable, '-B', str(PACKAGE / relative), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        return json.loads(result.stdout)

    def test_source_body_geometry_and_missing_inputs(self):
        report = self.run_script('native/prove_opposing_pass_measure.py')
        self.assertTrue(report['passed'])
        self.assertEqual(report['missing_source_negatives'], 6)
        right = report['cases']['witness_1']['measurement']
        left = report['cases']['witness_2']['measurement']
        self.assertEqual(right['meeting_frames'], left['meeting_frames'])
        self.assertEqual(right['ego_left_half_during_meeting_frames'], 0)
        self.assertEqual(left['ego_left_half_during_meeting_frames'], left['meeting_frames'])
        self.assertFalse(right['as_nearly_as_possible_judged'])

    def test_selected_comparison_isolation(self):
        report = self.run_script('comparison_audit.py', '--self-test')
        self.assertTrue(report['passed'])
        self.assertEqual(report['frames'], 600)
        failure = subprocess.run([sys.executable, '-B', str(PACKAGE / 'comparison_audit.py'),
                                  '--self-test', '--negative'], capture_output=True, text=True)
        self.assertNotEqual(failure.returncode, 0)
        self.assertIn('Oncoming vehicle changed outside comparison variable', failure.stderr)

    def test_independent_delivery_rejects_diagnostic(self):
        for suffix in ('witness_1', 'witness_2'):
            case = PACKAGE.name + '__' + suffix
            positive = self.run_script('delivery_audit.py', '--case', case, '--self-test')
            self.assertTrue(positive['cpu_predicates_passed'])
            failure = subprocess.run([sys.executable, '-B', str(PACKAGE / 'delivery_audit.py'),
                                      '--case', case, '--self-test', '--negative'],
                                     capture_output=True, text=True)
            self.assertNotEqual(failure.returncode, 0)
            self.assertIn('Missing original source: exact original Native result', failure.stderr)


if __name__ == '__main__':
    unittest.main()
