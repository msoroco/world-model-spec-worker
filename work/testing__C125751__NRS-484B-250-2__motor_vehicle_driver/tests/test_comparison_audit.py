import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from comparison_audit import CASES, FIXED, audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, case, states):
    root.mkdir()
    for name in FIXED:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixed source\n')
    rows = [dict(frame=frame, time_s=(frame - 1) / 20, native_signal_id=55,
                 state=states[0], other_native_signal_id=56, other_state=states[1])
            for frame in (1, 2)]
    (root / 'signal_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (root / 'config.json').write_text(json.dumps({'selected_case_id': case,
        'site': {'crossing_id': 7}, 'target_signal_state': states[0]}))
    entry = {role: {'frame': 2, 'native_state': state}
             for role, state in zip(('ego', 'other'), states)}
    (root / 'analysis-report.json').write_text(json.dumps({'measurements':
        {'signal_at_entry': {'value': {'at_body_entry': entry}}}}))
    result = {'case_id': case, 'source_evidence_hashes':
              {name: sha(root / name) for name in (*FIXED, 'signal_history.jsonl')},
              'capture_evidence_sha256': sha(root / 'capture/evidence.jsonl'),
              'target_checks': [{'target': 'ego_native_signal_state_at_body_entry', 'matched': True}],
              'measured_values': {'ego_signal_state_at_entry': states[0]}}
    (root / 'result.json').write_text(json.dumps(result))


class ComparisonAuditTests(unittest.TestCase):
    def test_fixed_pair_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = Path(temp) / 'left', Path(temp) / 'right'
            fixture(left, CASES[0], ('Green', 'Red'))
            fixture(right, CASES[1], ('Off', 'Off'))
            self.assertTrue(audit(left, right)['passed'])
            (right / 'stop_history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Result source hash differs'):
                audit(left, right)

    def test_changed_fixed_geometry_even_with_updated_result_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = Path(temp) / 'left', Path(temp) / 'right'
            fixture(left, CASES[0], ('Green', 'Red'))
            fixture(right, CASES[1], ('Off', 'Off'))
            (right / 'road_geometry.json').write_text('changed source\n')
            result = json.loads((right / 'result.json').read_text())
            result['source_evidence_hashes']['road_geometry.json'] = sha(right / 'road_geometry.json')
            (right / 'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'Fixed comparison source differs'):
                audit(left, right)

    def test_undeclared_signal_identity_change(self):
        with tempfile.TemporaryDirectory() as temp:
            left, right = Path(temp) / 'left', Path(temp) / 'right'
            fixture(left, CASES[0], ('Green', 'Red'))
            fixture(right, CASES[1], ('Off', 'Off'))
            rows = [json.loads(line) for line in (right / 'signal_history.jsonl').read_text().splitlines()]
            rows[1]['other_native_signal_id'] = 99
            (right / 'signal_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            result = json.loads((right / 'result.json').read_text())
            result['source_evidence_hashes']['signal_history.jsonl'] = sha(right / 'signal_history.jsonl')
            (right / 'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'Signal identity or timing differs'):
                audit(left, right)
