import copy
import importlib.util
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('comparison_audit', ROOT / 'comparison_audit.py')
comparison_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison_audit)
from test_following import fixture


def reports(plan, comparison_id):
    comparison = next(c for c in plan['comparisons'] if c['comparison_id'] == comparison_id)
    result = {}
    for cid in comparison['case_ids']:
        setup = next(c['world_setup'] for c in plan['cases'] if c['case_id'] == cid)
        result[cid] = {'format': 'worker-following-measurements', 'case_id': cid,
                       'legal_reasonableness_verdict': 'unresolved',
                       'sources': {'following-history.jsonl': 'a'*64,
                                   'following-context.json': 'b'*64},
                       'steady_window_s': [14, 20], 'steady_frame_count': 120,
                       'raw_history': [{'frame': 280}], 'lane_change_first_frame': 420,
                       'mean_along_route_body_gap_m': setup['target_body_gap_m'],
                       'mean_ego_speed_mps': setup['ego_target_speed_mps'],
                       'mean_surrounding_vehicle_count': setup['surrounding_vehicle_count'],
                       'mean_native_precipitation_strength': setup['precipitation_percent']}
    return result


class ComparisonAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT/'case-plan.json').read_text())

    def test_each_declared_pair_and_observed_difference(self):
        for pair in self.plan['comparisons']:
            with self.subTest(pair=pair['comparison_id']):
                result = comparison_audit.audit(self.plan, pair['comparison_id'],
                                                reports(self.plan, pair['comparison_id']))
                self.assertEqual(result['legal_reasonableness_verdict'], 'unresolved')

    def test_rejects_missing_evidence_or_changed_fixed_condition(self):
        name = 'body_gap_request'
        values = reports(self.plan, name)
        second = self.plan['comparisons'][0]['case_ids'][1]
        values[second]['sources'].pop('following-history.jsonl')
        with self.assertRaisesRegex(ValueError, 'sources missing'):
            comparison_audit.audit(self.plan, name, values)
        plan = copy.deepcopy(self.plan)
        plan['cases'][1]['world_setup']['duration_s'] = 30
        with self.assertRaisesRegex(ValueError, 'fixed conditions differ'):
            comparison_audit.audit(plan, name, reports(self.plan, name))

    def test_rejects_unobserved_difference(self):
        name = 'body_gap_request'
        values = reports(self.plan, name)
        first, second = self.plan['comparisons'][0]['case_ids']
        values[second]['mean_along_route_body_gap_m'] = values[first]['mean_along_route_body_gap_m']
        with self.assertRaisesRegex(ValueError, 'not observed'):
            comparison_audit.audit(self.plan, name, values)

    def test_attempt_audit_recomputes_original_sources(self):
        name = 'body_gap_request'
        first, second = self.plan['comparisons'][0]['case_ids']
        with tempfile.TemporaryDirectory() as temp:
            paths = {first: Path(temp)/'base', second: Path(temp)/'closer'}
            for case_id, path in paths.items():
                path.mkdir()
                rows = fixture(path)
                if case_id == second:
                    for row in rows:
                        row['leader']['body_vertices_m'] = [[v[0]-7, v[1], v[2]]
                                                            for v in row['leader']['body_vertices_m']]
                    (path/'following-history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                context = json.loads((path/'following-context.json').read_text())
                context['case_id'] = case_id
                (path/'following-context.json').write_text(json.dumps(context))
                acquisition = json.loads((path/'acquisition.json').read_text())
                for source in ('following-history.jsonl', 'following-context.json'):
                    acquisition[source]['sha256'] = hashlib.sha256((path/source).read_bytes()).hexdigest()
                (path/'acquisition.json').write_text(json.dumps(acquisition))
            result = comparison_audit.audit_attempts(ROOT/'case-plan.json', name, paths,
                                                      diagnostic=True)
            self.assertLess(result['observed_values'][1], result['observed_values'][0])
            (paths[second]/'following-history.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError, 'stale original Native source'):
                comparison_audit.audit_attempts(ROOT/'case-plan.json', name, paths,
                                                diagnostic=True)


if __name__ == '__main__':
    unittest.main()
