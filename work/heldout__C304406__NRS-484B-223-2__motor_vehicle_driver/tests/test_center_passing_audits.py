import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_center_passing_delivery import audit as audit_passing
from audit_center_passing_comparison import audit as compare
from audit_center_passing_near_delivery import audit as audit_near
from audit_center_passing_near_comparison import audit as compare_near
from three_lane_passing_near_finalizer import analyze as analyze_near, build_result as build_near_result
from three_lane_finalizer import analyze as analyze_lanes, build_result as build_lane_result
from three_lane_passing_finalizer import analyze as analyze_passing, build_result as build_passing_result

HERE = Path(__file__).resolve().parents[1]


class PassingAuditsTests(unittest.TestCase):
    def case(self, root, kind):
        attempt = root / kind
        attempt.mkdir()
        spec = json.loads((HERE / (kind + '-diagnostic.json')).read_text())
        for name in ('passing_frames.jsonl', 'three_lane_frames.jsonl',
                     'three_lane_context.json', 'three_lane_map_readback.json',
                     'trace.jsonl', 'video_frames.jsonl'):
            if name in spec['files']:
                (attempt / name).write_text(spec['files'][name])
        construction_name = {'center-default':'construction-center-default.json',
            'center-passing-clear':'construction-center-passing-clear.json',
            'center-passing-near-traffic':'construction-center-passing-near-traffic.json'}[kind]
        construction = json.loads((HERE / construction_name).read_text())
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        passing = kind == 'center-passing-clear'
        near = kind == 'center-passing-near-traffic'
        report = analyze_near(attempt) if near else (analyze_passing(attempt) if passing else analyze_lanes(attempt))
        result = build_near_result(attempt, report) if near else (build_passing_result(attempt, report) if passing else build_lane_result(attempt, report))
        saved = root / (kind + '-saved') / 'analysis'
        saved.mkdir(parents=True)
        (saved / 'analysis-report.json').write_text(json.dumps(report) + '\n')
        (saved / 'result.json').write_text(json.dumps(result) + '\n')
        receipt = saved.parent / 'processing.json'
        receipt.write_text(json.dumps({'case_id': report['case_id'], 'passed': True,
            'recorded_only': True, 'originals_preserved': True, 'missing_evidence': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}) + '\n')
        return attempt, receipt

    def test_source_binding_and_controlled_target_difference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            center, c_receipt = self.case(root, 'center-default')
            passing, p_receipt = self.case(root, 'center-passing-clear')
            self.assertTrue(audit_passing(passing, p_receipt)['source_binding_passed'])
            proof = compare(center, c_receipt, passing, p_receipt)
            self.assertTrue(proof['fixed_conditions_passed'])
            self.assertTrue(proof['target_source_added'])
            with (passing / 'passing_frames.jsonl').open('a') as source:
                source.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'original source differs'):
                audit_passing(passing, p_receipt)
            with self.assertRaisesRegex(ValueError, 'original source differs'):
                compare(center, c_receipt, passing, p_receipt)

    def test_near_traffic_source_and_fixed_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clear, c_receipt = self.case(root, 'center-passing-clear')
            near, n_receipt = self.case(root, 'center-passing-near-traffic')
            self.assertTrue(audit_near(near, n_receipt)['source_binding_passed'])
            proof = compare_near(clear, c_receipt, near, n_receipt)
            self.assertTrue(proof['added_center_actor_each_frame'])
            with (near / 'passing_frames.jsonl').open('a') as source:
                source.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'original source differs'):
                audit_near(near, n_receipt)


if __name__ == '__main__':
    unittest.main()
