import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('evidence_audit', HERE / 'evidence_audit.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class EvidenceAuditTests(unittest.TestCase):
    def test_frozen_inventory(self):
        rows = audit_module.audit(ROOT)
        self.assertEqual(len(rows), 8)
        self.assertEqual(len({row['recording_id'] for row in rows}), 8)

    def test_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            source = root / 'inputs' / audit_module.ASSIGNMENT_ID
            source.mkdir(parents=True)
            (source / 'assignment.json').write_bytes((ROOT / 'inputs' / audit_module.ASSIGNMENT_ID / 'assignment.json').read_bytes())
            inventory = json.loads((ROOT / 'inputs' / audit_module.ASSIGNMENT_ID / 'evidence.json').read_text())
            inventory['recordings'] = inventory['recordings'][:1]
            (source / 'evidence.json').write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                audit_module.audit(root)


if __name__ == '__main__':
    unittest.main()

class JudgmentPlanTests(unittest.TestCase):
    def test_source_bound_targets_respect_strict_ranges(self):
        plan = json.loads((HERE / 'judgment-probe-plan.json').read_text())
        self.assertEqual(plan['assignment_id'], audit_module.ASSIGNMENT_ID)
        self.assertEqual(len(plan['ranges']), 22)
        for row in plan['ranges']:
            source = ROOT / row['source_ref']['path']
            self.assertEqual(audit_module.digest(source), row['source_ref']['sha256'])
            low, high = row['source_minimum'], row['source_maximum']
            values = row['planning_targets']
            if values['below'] is not None:
                self.assertLess(values['below'], low)
            if values['inside'] is not None:
                self.assertLess(low, values['inside'])
                self.assertLess(values['inside'], high)
            if values['above'] is not None:
                self.assertGreater(values['above'], high)
            self.assertTrue(row['endpoint_limits'] or all(v is not None for v in values.values()))

    def test_every_feasible_bracket_maps_to_a_requested_exact_case(self):
        import sys
        sys.path.insert(0, str(HERE))
        from range_case_author import observed_target, in_zone
        plan = json.loads((HERE/'judgment-probe-plan.json').read_text())
        cases = {case['case_id']: case for case in
                 json.loads((HERE/'case-plan.json').read_text())['cases']}
        for row in plan['ranges']:
            for zone, target in row['planning_targets'].items():
                ids = row['planned_case_ids'].get(zone, [])
                if target is None:
                    self.assertEqual(ids, [])
                    continue
                self.assertEqual(len(ids), 1)
                case = cases[ids[0]]
                self.assertTrue(in_zone(observed_target(case['world_setup'],
                    row['variable']), row, zone))
                self.assertIn(row['judgment_key'], case['judgment_refs'])
                self.assertTrue(any(item['range_index'] == row['range_index']
                    and item['zone'] == zone for item in case['sweep_measurements']))
