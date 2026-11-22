import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit
from test_following import fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(path):
    rows = fixture(path)
    case_id = ROOT.name + '__following_base_probe'
    for row in rows:
        row['traffic_actor_ids'] = []
    (path/'following-history.jsonl').write_text(''.join(
        json.dumps(row)+'\n' for row in rows))
    context = json.loads((path/'following-context.json').read_text())
    context['case_id'] = case_id
    (path/'following-context.json').write_text(json.dumps(context))
    (path/'trace.jsonl').write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s']})+'\n' for row in rows))
    (path/'video_frames.jsonl').write_text(''.join(json.dumps({
        'carla_frame': row['frame'], 'time_s': row['time_s'],
        'video_frame': i})+'\n' for i, row in enumerate(rows)))
    (path/'road.xodr').write_text('synthetic road\n')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (path/(name+'.mkv')).write_bytes(b'synthetic camera bytes')
    acquisition = {name: {'kind': 'original_native', 'sha256': sha(path/name)}
        for name in ('following-history.jsonl', 'following-context.json',
                     'trace.jsonl', 'video_frames.jsonl', 'road.xodr',
                     'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                     'driver_reference.mkv')}
    (path/'acquisition.json').write_text(json.dumps(acquisition))
    sources = {name: sha(path/name) for name in acquisition}
    sources['acquisition.json'] = sha(path/'acquisition.json')
    (path/'capture-seal.json').write_text(json.dumps({
        'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
        'restoration': {'restored': True}, 'sources': sources}))
    (path/'native-exit.json').write_text(json.dumps({
        'event': 'native_exit', 'capture_seal_sha256': sha(path/'capture-seal.json')}))
    (path/'owner-release.json').write_text(json.dumps({
        'event': 'owner_released', 'operator_attested': True,
        'native_exit_sha256': sha(path/'native-exit.json')}))
    (path/'result.json').write_text(json.dumps({'case_id': case_id,
        'setup_confirmed': True, 'behavior_attempted': True,
        'maneuver_completed': True}))
    (path/'config.json').write_text(json.dumps({'selected_case_id': case_id,
        'law_id': 'NRS-484B-127-1', 'cell_id': 'C101303',
        'actor': 'motor_vehicle_driver', 'cameras': [], 'duration_s': 24}))
    analysis = path/'analysis'
    analysis.mkdir()
    (analysis/'raw.mkv').write_bytes(b'synthetic composed bytes')
    (path/'processing.json').write_text(json.dumps({
        'format': 'worker-saved-processing', 'passed': True,
        'recorded_only': True, 'result': str(path/'result.json'),
        'result_sha256': sha(path/'result.json'),
        'analysis_directory': str(analysis)}))
    (path/'decode.json').write_text('{}')
    return case_id


class DeliveryAuditTests(unittest.TestCase):
    def checked(self, path, case_id):
        def media(video, receipt, count, mapping_sha256):
            self.assertEqual(video, path/'analysis/raw.mkv')
            self.assertEqual(receipt, path/'decode.json')
            self.assertEqual(count, 4)
            self.assertEqual(mapping_sha256, sha(path/'video_frames.jsonl'))
        return audit(path, path/'processing.json', path/'decode.json', case_id,
                     media_verify=media, measure_fn=lambda *_args: {
                         'scope': 'synthetic_cpu_test_only'})

    def test_positive_source_and_frame_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            case_id = setup(path)
            report = self.checked(path, case_id)
            self.assertTrue(report['passed'])
            self.assertEqual(report['frame_count'], 4)
            self.assertIsNone(report['legal_verdict'])

    def test_rejects_changed_source_owner_and_frame_join(self):
        for mutation, expected in (
            (lambda p: (p/'following-history.jsonl').write_text('changed\n'),
             'sealed original missing or changed'),
            (lambda p: (p/'owner-release.json').unlink(), 'owner release missing'),
            (lambda p: (p/'video_frames.jsonl').write_text('[]\n'),
             'sealed original missing or changed')):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                path = Path(temp)
                case_id = setup(path)
                mutation(path)
                with self.assertRaisesRegex(ValueError, expected):
                    self.checked(path, case_id)

    def test_rejects_diagnostic_fixture_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            case_id = setup(path)
            (path/'fixture-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))
            with self.assertRaisesRegex(ValueError, 'diagnostic fixture'):
                self.checked(path, case_id)

    def test_rejects_sealed_context_for_another_exact_case(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            case_id = setup(path)
            context = json.loads((path/'following-context.json').read_text())
            context['case_id'] = ROOT.name+'__wet_probe'
            (path/'following-context.json').write_text(json.dumps(context))
            acquisition = json.loads((path/'acquisition.json').read_text())
            acquisition['following-context.json']['sha256'] = sha(path/'following-context.json')
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            seal = json.loads((path/'capture-seal.json').read_text())
            seal['sources']['following-context.json'] = sha(path/'following-context.json')
            seal['sources']['acquisition.json'] = sha(path/'acquisition.json')
            (path/'capture-seal.json').write_text(json.dumps(seal))
            native = json.loads((path/'native-exit.json').read_text())
            native['capture_seal_sha256'] = sha(path/'capture-seal.json')
            (path/'native-exit.json').write_text(json.dumps(native))
            owner = json.loads((path/'owner-release.json').read_text())
            owner['native_exit_sha256'] = sha(path/'native-exit.json')
            (path/'owner-release.json').write_text(json.dumps(owner))
            with self.assertRaisesRegex(ValueError, 'hill route geometry missing'):
                self.checked(path, case_id)
