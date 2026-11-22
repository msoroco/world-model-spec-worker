import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit
from test_analysis import fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(path, occupied=False, traffic_case=False):
    rows = fixture(path, occupied, traffic_case)
    case = ('lawful_traffic_yield' if traffic_case else
            'crosswalk_occupied_yield' if occupied else 'crosswalk_clear_turn')
    case_id = ROOT.name + '__' + case
    (path / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': r['frame'], 'time_s': r['time_s'], 'position_m': [r['ego']['body_vertices_m'][0][0], 0, 0]}) + '\n'
        for r in rows))
    (path / 'road.xodr').write_text('fixture road\n')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (path / (name + '.mkv')).write_bytes(b'fixture video')
    acquisition = json.loads((path / 'acquisition.json').read_text())
    for name in ('trace.jsonl', 'road.xodr', 'overview.mkv', 'approach.mkv',
                 'reference_corner.mkv', 'driver_reference.mkv'):
        acquisition[name] = {'kind': 'original_native', 'sha256': sha(path / name)}
    (path / 'acquisition.json').write_text(json.dumps(acquisition))
    sources = {p.name: sha(p) for p in path.iterdir() if p.is_file()
               and p.name not in ('config.json', 'construction.json', 'scene.json')}
    (path / 'capture-seal.json').write_text(json.dumps({
        'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
        'restoration': {'restored': True}, 'sources': sources}))
    (path / 'native-exit.json').write_text(json.dumps({
        'event': 'native_exit', 'capture_seal_sha256': sha(path / 'capture-seal.json')}))
    (path / 'owner-release.json').write_text(json.dumps({
        'event': 'owner_released', 'operator_attested': True,
        'native_exit_sha256': sha(path / 'native-exit.json')}))
    (path / 'result.json').write_text(json.dumps({'case_id': case_id,
        'setup_confirmed': True, 'behavior_attempted': True,
        'maneuver_completed': True}))
    analysis = path / 'analysis'
    analysis.mkdir()
    (analysis / 'raw.mkv').write_bytes(b'fixture composed video')
    (path / 'processing.json').write_text(json.dumps({
        'format': 'worker-saved-processing', 'passed': True, 'recorded_only': True,
        'result': str(path / 'result.json'), 'result_sha256': sha(path / 'result.json'),
        'analysis_directory': str(analysis)}))
    (path / 'decode.json').write_text('{}')
    return case_id


class DeliveryAuditTests(unittest.TestCase):
    def test_source_bound_clear_and_occupied(self):
        for occupied, traffic_case in ((False, False), (True, False), (False, True)):
            with self.subTest(occupied=occupied, traffic_case=traffic_case), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                case_id = setup(path, occupied, traffic_case)
                def media(video, receipt, count, mapping_sha256):
                    self.assertEqual(video, path / 'analysis/raw.mkv')
                    self.assertEqual(receipt, path / 'decode.json')
                    self.assertEqual(count, 4)
                    self.assertEqual(mapping_sha256, sha(path / 'video_frames.jsonl'))
                report = audit(path, path / 'processing.json', path / 'decode.json',
                               case_id, media)
                self.assertTrue(report['passed'])
                self.assertEqual(report['frame_count'], 4)

    def test_stale_source_or_owner_release_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            case_id = setup(path, True)
            (path / 'pedestrian-entry.jsonl').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'sealed original missing or changed'):
                audit(path, path / 'processing.json', path / 'decode.json', case_id,
                      lambda *_args, **_kw: None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            case_id = setup(path)
            (path / 'owner-release.json').unlink()
            with self.assertRaisesRegex(ValueError, 'owner release missing'):
                audit(path, path / 'processing.json', path / 'decode.json', case_id,
                      lambda *_args, **_kw: None)

    def test_diagnostic_fixture_cannot_claim_native_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            case_id = setup(path)
            (path / 'fixture-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))
            with self.assertRaisesRegex(ValueError, 'diagnostic fixture cannot establish Native delivery'):
                audit(path, path / 'processing.json', path / 'decode.json', case_id,
                      lambda *_args, **_kw: None)
