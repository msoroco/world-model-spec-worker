"""Shape tests only; no result here is a Native physical proof."""
import json
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physical_fixture_audit import audit, check_result, sha
from test_lifecycle_audit import LifecycleAuditTests


class PhysicalFixtureAuditTests(unittest.TestCase):
    def make_chain(self, root, kind):
        """Invented source-shaped rows exercise code only, never a Native receipt."""
        attempt, owner, processing, construction = LifecycleAuditTests().shape(root)
        body = [[-2, -3], [-2, -1], [2, -1], [2, -3]]
        vertices = [[x, y, 0] for x, y in body]
        sources = {name: [] for name in ('trace.jsonl', 'capture/evidence.jsonl',
                   'video_frames.jsonl', 'native_samples.jsonl', 'body_history.jsonl')}
        for i in range(480):
            frame, time = i + 100, (i + 1) / 20
            marker = {'source_shaped_unit_test': True}
            sources['trace.jsonl'].append({**marker, 'frame': frame, 'time_s': time,
                'position': {'x': 0, 'y': -2}, 'speed_mps': 0,
                'speed_provenance': 'source_shaped_unit_test'})
            sources['capture/evidence.jsonl'].append({**marker,
                'original_frame': frame, 'recording_time_s': time,
                'ego': {'position_m': [0, -2, 0], 'speed_mps': 0,
                        'body_vertices_m': vertices}})
            sources['video_frames.jsonl'].append({**marker,
                'native_frame': frame, 'carla_frame': frame,
                'video_frame': i, 'time_s': time})
            sources['native_samples.jsonl'].append({**marker,
                'native_frame': frame, 'time_s': time,
                'native_center_xy_m': [0, -2], 'native_forward_xy': [1, 0],
                'native_road_id': 1, 'native_lane_id': -1,
                'native_body_xy_m': body, 'speed_mps': 0,
                'speed_provenance': 'source_shaped_unit_test'})
            sources['body_history.jsonl'].append({**marker, 'frame': frame,
                'time_s': time, 'body_vertices_m': vertices})
        for name, rows in sources.items():
            path = attempt / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        status = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]
        result_path = root / 'saved/v0001/analysis/result.json'
        result = json.loads(result_path.read_text())
        result.update({'accepted': False, 'legal_verdict_claimed': False,
            'maneuver_completed': status == 'met',
            'realized_observables': {'test_only_overlap_m': 5.2} if status == 'met' else {},
            'physical_checks': {'maneuver': {'status': status,
                'method': 'source-shaped unit test only',
                'sources': {'native_samples.jsonl': sha(attempt / 'native_samples.jsonl')}}}})
        result_path.write_text(json.dumps(result))
        seal_path = attempt / 'capture-seal.json'
        seal = json.loads(seal_path.read_text())
        seal['sources'] = {path.relative_to(attempt).as_posix(): sha(path)
                           for path in attempt.rglob('*') if path.is_file() and
                           path.name not in ('capture-seal.json', 'native-exit.json')}
        seal_path.write_text(json.dumps(seal))
        exit_path = attempt / 'native-exit.json'
        exit_record = json.loads(exit_path.read_text())
        exit_record['capture_seal_sha256'] = sha(seal_path)
        exit_path.write_text(json.dumps(exit_record))
        owner_record = json.loads(owner.read_text())
        owner_record['native_exit_sha256'] = sha(exit_path)
        owner.write_text(json.dumps(owner_record))
        receipt = json.loads(processing.read_text())
        receipt['original_source_hashes'] = seal['sources']
        receipt['result_sha256'] = sha(result_path)
        receipt['missing_evidence'] = kind == 'missing_evidence'
        processing.write_text(json.dumps(receipt))
        return attempt, owner, processing, construction

    def test_full_source_shaped_outcomes_and_production_rejection(self):
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                attempt, owner, processing, construction = self.make_chain(
                    Path(directory), kind)
                proof = audit(attempt, owner, processing, kind, 'case', construction,
                              test_shape=True)
                self.assertEqual(proof['kind'], kind)
                self.assertFalse(proof['physical_acceptance_claimed'])
                with self.assertRaisesRegex(ValueError, 'Synthetic or accepted'):
                    audit(attempt, owner, processing, kind, 'case', construction)

    def shaped_result(self, status, native=True):
        return {'case_id':'unit-case',
                'provenance_kind':'native' if native else 'synthetic_local_diagnostic',
                'diagnostic_fixture':not native,
                'accepted':False,'legal_verdict_claimed':False,
                'maneuver_completed':status=='met',
                'realized_observables':{'sampled_stopped_entrance_overlap':
                                        {'value':5.2,'reference':'native_samples.jsonl'}},
                'physical_checks':{'maneuver':{'status':status,
                    'method':'source-shaped unit test, not a Native observation',
                    'sources':{'native_samples.jsonl':'unit-source-hash'}}}}

    def test_three_expected_branches_and_mismatches(self):
        for kind,status in [('complete_motion','met'),
                            ('incomplete_motion','not_met'),
                            ('missing_evidence','unverified')]:
            with self.subTest(kind=kind):
                result=self.shaped_result(status)
                self.assertEqual(check_result(result,kind,'unit-case')['status'],status)
                with self.assertRaisesRegex(ValueError,'status'):
                    check_result(result,'complete_motion' if kind!='complete_motion'
                                 else 'incomplete_motion','unit-case')

    def test_synthetic_or_unsupported_completion_rejected(self):
        synthetic=self.shaped_result('met',native=False)
        with self.assertRaisesRegex(ValueError,'Synthetic'):
            check_result(synthetic,'complete_motion','unit-case')
        native=self.shaped_result('met')
        native['realized_observables']={}
        with self.assertRaisesRegex(ValueError,'realized Native'):
            check_result(native,'complete_motion','unit-case')
        native=self.shaped_result('not_met')
        native['maneuver_completed']=True
        with self.assertRaisesRegex(ValueError,'status'):
            check_result(native,'incomplete_motion','unit-case')


if __name__=='__main__':unittest.main()
