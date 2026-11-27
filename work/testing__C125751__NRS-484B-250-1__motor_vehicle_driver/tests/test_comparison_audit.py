import sys
import unittest
import subprocess
import tempfile
import json
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit_pair, audit_saved_pair
from case_protocol import ASSIGNMENT
from test_analysis import write_attempt


def report(case, order, signal):
    return {'case_id': case, 'map_sha256': 'map', 'review_sha256': 'review',
            'crossing_id': 'cross', 'ego_route_sha256': 'ego', 'other_route_sha256': 'other',
            'camera_plan_sha256': 'cameras', 'duration_frames': 900,
            'ego_blueprint': 'vehicle.a', 'other_blueprint': 'vehicle.b',
            'ego_entry_frame': 12, 'other_entry_frame': 5 if order else 20,
            'signal_states_observed': [signal], 'physical_review_pending': True}


class ComparisonAuditTest(unittest.TestCase):
    def test_saved_original_comparison_rejects_synthetic_lifecycle(self):
        repo = Path(__file__).resolve().parents[3]
        scratch = repo / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            left, right = Path(temporary)/'left', Path(temporary)/'right'
            left.mkdir(); right.mkdir()
            write_attempt(left); write_attempt(right)
            history_path = right/'signal-history.json'
            history = json.loads(history_path.read_text())
            history['frames'][0]['ego_light_readback'] = 'Red'
            history_path.write_text(json.dumps(history))
            seal_path = right/'signal-packet.json'
            seal = json.loads(seal_path.read_text())
            seal['case_id'] = 'case-2'
            seal['payload_sha256'] = hashlib.sha256(history_path.read_bytes()).hexdigest()
            seal_path.write_text(json.dumps(seal))
            inventory_path = right/'acquisition.json'
            inventory = json.loads(inventory_path.read_text())
            for name in ('signal-history.json', 'signal-packet.json'):
                inventory[name]['sha256'] = hashlib.sha256((right/name).read_bytes()).hexdigest()
            inventory_path.write_text(json.dumps(inventory))
            for attempt, suffix in ((left, 'precedence'), (right, 'signal_red')):
                config = json.loads((attempt/'config.json').read_text())
                config['selected_case_id'] = ASSIGNMENT + '__' + suffix
                (attempt/'config.json').write_text(json.dumps(config))
                (attempt/'capture-seal.json').write_text(json.dumps({
                    'provenance_kind': 'synthetic_fixture',
                    'diagnostic_fixture': True, 'sources': {}}))
            with self.assertRaisesRegex(ValueError, 'original Native lifecycle unverified'):
                audit_saved_pair(left, right, variable='signal_state')

    def test_cli_rejects_uncontrolled_change(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
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

    def test_accepted_response_is_measured_and_isolated(self):
        waiting = report(ASSIGNMENT + '__precedence', True, 'Green')
        advancing = report(ASSIGNMENT + '__advance', True, 'Green')
        waiting['other_clear_frame'] = advancing['other_clear_frame'] = 10
        advancing['ego_entry_frame'] = 7
        for item in (waiting, advancing):
            item['signal_initial_state'] = 'Green'
            item['signal_transition_frames'] = [{'frame': 0, 'state': 'Green'}]
        observed = audit_pair(waiting, advancing, variable='crossing_response')
        self.assertTrue(observed['measured_crossing_response']
                        ['advance_entered_before_other_cleared'])
        changed = dict(advancing, signal_states_observed=['Red'])
        with self.assertRaisesRegex(ValueError, 'signal state changed'):
            audit_pair(waiting, changed, variable='crossing_response')
        changed = dict(advancing, ego_entry_frame=12)
        with self.assertRaisesRegex(ValueError, 'advance case did not enter'):
            audit_pair(waiting, changed, variable='crossing_response')
        changed = dict(advancing, other_clear_frame=11)
        with self.assertRaisesRegex(ValueError, 'other vehicle entry or clearance changed'):
            audit_pair(waiting, changed, variable='crossing_response')
        changed = dict(advancing, map_sha256='different')
        with self.assertRaisesRegex(ValueError, 'fixed condition differs'):
            audit_pair(waiting, changed, variable='crossing_response')
        changed = dict(advancing, other_entry_frame=20)
        with self.assertRaisesRegex(ValueError, 'other-first crossing chronology'):
            audit_pair(waiting, changed, variable='crossing_response')

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
