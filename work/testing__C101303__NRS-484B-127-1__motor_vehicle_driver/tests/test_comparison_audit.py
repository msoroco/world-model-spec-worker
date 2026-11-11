import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c101303_comparison_audit', FOLDER / 'comparison_audit.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class ComparisonAuditTest(unittest.TestCase):
    def test_all_primary_pairs_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for label in ('base', 'closer', 'faster_ego', 'slower_lead', 'lead_brakes',
                          'wet_surface', 'following_ends', 'queued_traffic'):
                source = FOLDER / ('diagnostic.json' if label == 'base' else
                                   f'cases/source_verified_{label}/diagnostic.json')
                content = json.loads(source.read_text())['files']['vehicle_history.jsonl']
                target = Path(tmp) / f'{label}.jsonl'
                target.write_text(content)
                paths[label] = target
            for comparison, variant in [('body_gap', 'closer'), ('ego_speed', 'faster_ego'),
                                        ('lead_speed', 'slower_lead'), ('lead_braking', 'lead_brakes'),
                                        ('wet_surface', 'wet_surface'), ('following_end', 'following_ends'),
                                        ('queued_traffic', 'queued_traffic')]:
                with self.subTest(comparison=comparison):
                    receipt = audit.audit_pair(FOLDER, comparison, paths['base'], paths[variant])
                    self.assertEqual(receipt['comparison_id'], comparison)
                    self.assertEqual(receipt['frames'], 9)
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
                source = FOLDER / ('diagnostic.json' if label == 'base' else
                                   f'cases/source_verified_{label}/diagnostic.json')
                target = Path(tmp) / f'{label}.jsonl'
                target.write_text(json.loads(source.read_text())['files']['vehicle_history.jsonl'])
                files.append(target)
            with self.assertRaisesRegex(ValueError, 'comparison construction changes undeclared'):
                audit.audit_pair(FOLDER, 'body_gap', *files, candidate='fallback2')


if __name__ == '__main__':
    unittest.main()
