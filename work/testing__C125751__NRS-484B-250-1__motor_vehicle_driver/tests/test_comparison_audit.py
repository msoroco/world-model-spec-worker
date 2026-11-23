import sys
import unittest
import subprocess
import tempfile
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit_pair


def report(case, order, signal):
    return {'case_id': case, 'map_sha256': 'map', 'review_sha256': 'review',
            'crossing_id': 'cross', 'ego_route_sha256': 'ego', 'other_route_sha256': 'other',
            'camera_plan_sha256': 'cameras', 'duration_frames': 900,
            'ego_blueprint': 'vehicle.a', 'other_blueprint': 'vehicle.b',
            'ego_entry_frame': 12, 'other_entry_frame': 5 if order else 20,
            'signal_states_observed': [signal], 'physical_review_pending': True}


class ComparisonAuditTest(unittest.TestCase):
    def test_cli_rejects_uncontrolled_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'left.json').write_text(json.dumps(report('a', True, 'Green')))
            (root/'right.json').write_text(json.dumps(report('b', False, 'Green')))
            cmd = [sys.executable, str(Path(__file__).resolve().parents[1]/'comparison_audit.py'),
                   '--left', str(root/'left.json'), '--right', str(root/'right.json'),
                   '--variable', 'entry_order', '--output', str(root/'pair.json')]
            good = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads((root/'pair.json').read_text())['case_ids'], ['a', 'b'])
            changed = report('b', False, 'Green'); changed['map_sha256'] = 'wrong'
            (root/'right.json').write_text(json.dumps(changed))
            bad = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)

    def test_entry_order_and_signal_isolation(self):
        self.assertEqual(audit_pair(report('a', True, 'Green'), report('b', False, 'Green'),
                                    variable='entry_order')['comparison_variable'], 'entry_order')
        self.assertEqual(audit_pair(report('a', True, 'Green'), report('b', True, 'Red'),
                                    variable='signal_state')['comparison_variable'], 'signal_state')

    def test_rejects_missing_fixed_condition_or_unchanged_variable(self):
        a, b = report('a', True, 'Green'), report('b', False, 'Green')
        b['camera_plan_sha256'] = None
        with self.assertRaises(ValueError):
            audit_pair(a, b, variable='entry_order')
        b = report('b', True, 'Green')
        with self.assertRaises(ValueError):
            audit_pair(a, b, variable='entry_order')
        b = report('b', False, 'Red')
        with self.assertRaises(ValueError):
            audit_pair(a, b, variable='signal_state')


if __name__ == '__main__':
    unittest.main()
