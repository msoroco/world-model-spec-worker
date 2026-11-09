"""Build eight exact paragraph (c)(2) inline candidates for pinned CPU preflight."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


TEST = '''import unittest
from pathlib import Path
from check import check
from fixture_raw import build as fixture
from saved import prepare, measure
from route_fallbacks import route

class PrivateWayC2(unittest.TestCase):
    def test_copied_statute_and_spur(self):
        result=check(Path.cwd())
        self.assertEqual(result['private_way_requested'],
                         result['case_id'].endswith('__exception_3_1'))
        self.assertTrue(result['requested_c1_over_200ft'])
        self.assertFalse(result['actual_private_way_passed_observed'])
        self.assertFalse(result['delivery_ready'])

    def test_pass_or_stop_request(self):
        result=check(Path.cwd())
        if result['candidate_id']=='fallback3':
            self.assertEqual(result['requested_right_ahead_frames'],0)
            self.assertEqual(result['requested_spur_zone_frames'],0)
        else:
            self.assertGreater(result['requested_right_ahead_frames'],0)
            self.assertGreater(result['requested_spur_zone_frames'],0)

    def test_synthetic_raw_to_saved_crossing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            fixture(Path.cwd(),root/'raw')
            receipt=prepare(Path.cwd(),root/'raw',root/'saved',True)
            measured=measure(Path.cwd(),root/'saved')
            routing=route(Path.cwd(),root/'saved')
            self.assertEqual(receipt['source_kind'],'synthetic_cpu')
            self.assertFalse(measured['physical_private_way_crossing_verified'])
            self.assertFalse(measured['delivery_ready'])
            self.assertEqual(set(routing['triggers']),{'fallback1','fallback2','fallback3'})
            self.assertIsNone(routing['selected_fallback'])
'''


def build():
    cases = []
    for witness in ('exception_3_1', 'exception_3_2'):
        choices = []
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bundle = HERE/'offline/bundles'/witness/candidate
            names = ('assignment-source.json', 'case-plan.json', 'unmarked-pass.xodr',
                     'config.json', 'requested-tracks.jsonl', 'build.py', 'check.py',
                     'capture.py', 'measurement-contract.json', 'saved.py',
                     'fixture_raw.py', 'route_fallbacks.py')
            files = [{'path': name, 'content': (bundle/name).read_text()} for name in names]
            files.append({'path': 'tests/test_exact.py', 'content': TEST})
            construction = {
                'case_id': CASE.name+'__'+witness, 'cell_id': 'C146314',
                'law_id': 'NRS-484B-210-1', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'capture.py', 'files': files,
                'status': 'unselected_cpu_diagnostic',
                'recording_description': 'Private-way spur present or absent at x=50 m; actual Native spur/crossing and c1 distance unobserved.'}
            path = HERE/'runtime-drafts'/witness/candidate/'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2, allow_nan=False)+'\n')
            choices.append({'id': candidate,
                            'construction': str(path.relative_to(HERE)),
                            'construction_sha256': sha(path)})
        cases.append({'case_id': CASE.name+'__'+witness,
                      'construction': choices[0]['construction'],
                      'construction_sha256': choices[0]['construction_sha256'],
                      'candidates': choices[1:],
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Original Native private-way junction, crossing, right pass and c1 distance are unverified.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': cases, 'original_native_observed': False,
                'delivery_ready': False}
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    m = build()
    print(json.dumps({'cases': len(m['cases']),
                      'constructions': sum(1+len(x['candidates']) for x in m['cases'])}))
