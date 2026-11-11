import importlib.util
import copy
import json
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c101303_comparison_audit', FOLDER / 'comparison_audit.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def full_source(label, target, *, frame_offset=0, time_offset=0.0):
    source = FOLDER / ('diagnostic.json' if label == 'base' else
                       f'cases/source_verified_{label}/diagnostic.json')
    original = [json.loads(line) for line in
                json.loads(source.read_text())['files']['vehicle_history.jsonl'].splitlines() if line]
    rows = []
    for index in range(900):
        row = copy.deepcopy(original[min(index, len(original)-1)])
        row['frame'] = original[0]['frame'] + frame_offset + index
        row['time_s'] = round(time_offset + (index + 1) / 20, 6)
        rows.append(row)
    target.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    return target


class ComparisonAuditTest(unittest.TestCase):
    def test_all_primary_pairs_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for label in ('base', 'closer', 'faster_ego', 'slower_lead', 'lead_brakes',
                          'wet_surface', 'following_ends', 'queued_traffic'):
                paths[label] = full_source(label, Path(tmp) / f'{label}.jsonl',
                                           frame_offset=100 if label != 'base' else 0,
                                           time_offset=10.0 if label != 'base' else 0.0)
            for comparison, variant in [('body_gap', 'closer'), ('ego_speed', 'faster_ego'),
                                        ('lead_speed', 'slower_lead'), ('lead_braking', 'lead_brakes'),
                                        ('wet_surface', 'wet_surface'), ('following_end', 'following_ends'),
                                        ('queued_traffic', 'queued_traffic')]:
                with self.subTest(comparison=comparison):
                    receipt = audit.audit_pair(FOLDER, comparison, paths['base'], paths[variant])
                    self.assertEqual(receipt['comparison_id'], comparison)
                    self.assertEqual(receipt['frames'], 900)
            with self.assertRaisesRegex(ValueError, 'missing original vehicle_history'):
                audit.audit_pair(FOLDER, 'body_gap', paths['base'], Path(tmp) / 'missing.jsonl')
            altered = Path(tmp) / 'altered.jsonl'
            rows = [json.loads(line) for line in paths['closer'].read_text().splitlines()]
            for row in rows:
                row.pop('surface_condition')
            altered.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'missing condition or traffic'):
                audit.audit_pair(FOLDER, 'body_gap', paths['base'], altered)

    def test_fallback_comparison_isolation_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for label in ('base', 'closer'):
                files.append(full_source(label, Path(tmp) / f'{label}.jsonl'))
            with self.assertRaisesRegex(ValueError, 'comparison construction changes undeclared'):
                audit.audit_pair(FOLDER, 'body_gap', *files, candidate='fallback1')
            isolated = audit.audit_pair(FOLDER, 'body_gap', *files,
                                        right_candidate='fallback1')
            self.assertEqual(isolated['left_candidate'], 'primary')
            self.assertEqual(isolated['right_candidate'], 'fallback1')

    def test_missing_frame_and_relative_time_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            left = full_source('base', Path(tmp) / 'base.jsonl')
            right = full_source('closer', Path(tmp) / 'closer.jsonl',
                                frame_offset=100, time_offset=10.0)
            rows = [json.loads(line) for line in right.read_text().splitlines()]
            rows[300]['frame'] += 1
            right.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'unaligned or repeated source frames'):
                audit.audit_pair(FOLDER, 'body_gap', left, right)
            rows[300]['frame'] -= 1
            for row in rows[300:]:
                row['time_s'] += 0.02
            right.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source cadence differs|relative time join differs'):
                audit.audit_pair(FOLDER, 'body_gap', left, right)


if __name__ == '__main__':
    unittest.main()
