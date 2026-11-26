"""Synthetic sealed-media protocols never establish Native delivery."""
import hashlib
import json
from pathlib import Path
from subprocess import CompletedProcess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from independent_delivery_audit import CAMERAS, _decode, audit
from native_case_runner import run_case
from parking import CASES
from test_native_case_runner import CombinedAdapter
from test_reviewed_site import ReviewedSiteTests


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self, root, case_name='west_inside'):
        root = Path(root)
        packet_path, sources, packet = ReviewedSiteTests().make_packet(root)
        source_site = dict(packet['site'])
        source_site['site_sha256'] = sha(packet_path)
        case = next(item for item in CASES if item.id == case_name)
        attempt = root / 'attempt'
        attempt.mkdir()
        run_case(CombinedAdapter(source_site, case), packet_path, sources,
                 HERE.name + '__' + case_name, 4.0, attempt / 'history.jsonl')
        rows = [json.loads(line) for line in (attempt / 'history.jsonl').read_text().splitlines()]
        mapping = [{'original_frame': row['original_frame'], 'time_s': row['time_s'],
                    'camera_frames': {name: index for name in CAMERAS}}
                   for index, row in enumerate(rows)]
        (attempt / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in mapping))
        for name in CAMERAS:
            (attempt / (name + '.mkv')).write_text('synthetic camera placeholder\n')
        context = {'format': 'sidewalk-elevator-original-comparison-context',
                   'case_id': HERE.name + '__' + case_name,
                   'site_packet_sha256': sha(packet_path),
                   'history_sha256': sha(attempt / 'history.jsonl'),
                   'ego_blueprint_sha256': source_site['ego_blueprint_sha256'],
                   'weather_sha256': 'synthetic-weather-source',
                   'route_sha256': source_site['one_way_direction_sha256'],
                   'curb_gap_target_m': 0.3,
                   'exception_source_sha256': (source_site.get({
                       'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                       'police_direction': 'police_direction_source_sha256',
                       'traffic_device_direction': 'traffic_device_source_sha256',
                   }.get(case.exception)) if case.exception != 'none' else None)}
        (attempt / 'comparison-context.json').write_text(json.dumps(context) + '\n')
        names = ('history.jsonl', 'camera-frame-map.jsonl', 'comparison-context.json',
                 *(name + '.mkv' for name in CAMERAS))
        seal = {'format': 'sidewalk-elevator-native-seal',
                'case_id': HERE.name + '__' + case_name, 'site_packet_sha256': sha(packet_path),
                'frames': 900, 'capture_rate_hz': 20, 'owner_released': True,
                'restoration_verified': True, 'native_process_exit_code': 0,
                'encoder_exit_codes': {name: 0 for name in CAMERAS},
                'provenance_kind': 'synthetic_fixture',
                'sources': {name: sha(attempt / name) for name in names}}
        (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
        return attempt, packet_path, sources, seal

    def test_sealed_frame_join_and_changed_original_rejection(self):
        scratch = Path('.runtime-work/c150153-delivery-audit-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, packet, sources, seal = self.fixture(temp)
            result = audit(attempt, packet, sources, diagnostic_fixture=True,
                           decoder=lambda path, name: 900)
            self.assertEqual(result['frame_count'], 900)
            self.assertEqual(result['camera_count'], 4)
            self.assertFalse(result['physical_acceptance_claimed'])
            with self.assertRaisesRegex(ValueError, 'original Native capture'):
                audit(attempt, packet, sources)
            failed = dict(seal, native_process_exit_code=1)
            (attempt / 'capture-seal.json').write_text(json.dumps(failed) + '\n')
            with self.assertRaisesRegex(ValueError, 'owner release incomplete'):
                audit(attempt, packet, sources, diagnostic_fixture=True,
                      decoder=lambda path, name: 900)
            (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            (attempt / 'overview.mkv').write_text('changed video\n')
            with self.assertRaisesRegex(ValueError, 'sealed original source missing or changed'):
                audit(attempt, packet, sources, diagnostic_fixture=True,
                      decoder=lambda path, name: 900)
            (attempt / 'overview.mkv').write_text('synthetic camera placeholder\n')
            rows = [json.loads(line) for line in (attempt / 'camera-frame-map.jsonl').read_text().splitlines()]
            rows[400]['camera_frames']['overview'] = 999
            (attempt / 'camera-frame-map.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
            seal['sources']['camera-frame-map.jsonl'] = sha(attempt / 'camera-frame-map.jsonl')
            (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            with self.assertRaisesRegex(ValueError, 'frame/time join differs'):
                audit(attempt, packet, sources, diagnostic_fixture=True,
                      decoder=lambda path, name: 900)

    def test_real_decoder_requires_exact_profile_and_full_decode(self):
        path = Path('overview.mkv')
        def probe(rate='20/1', width=1920):
            return CompletedProcess([], 0, json.dumps({'streams': [{
                'nb_read_frames': '900', 'r_frame_rate': rate,
                'width': width, 'height': 1080}]}), '')
        with patch('independent_delivery_audit.subprocess.run',
                   side_effect=[probe(), CompletedProcess([], 0, '', '')]) as run:
            self.assertEqual(_decode(path, 'overview'), 900)
            self.assertIn('-xerror', run.call_args.args[0])
        for wrong in (probe(rate='10/1'), probe(width=1280)):
            with patch('independent_delivery_audit.subprocess.run', return_value=wrong):
                with self.assertRaisesRegex(ValueError, 'profile differs'):
                    _decode(path, 'overview')
        with patch('independent_delivery_audit.subprocess.run',
                   side_effect=[probe(), CompletedProcess([], 1, '', 'decode error')]):
            with self.assertRaisesRegex(ValueError, 'full decode failed'):
                _decode(path, 'overview')


if __name__ == '__main__':
    unittest.main()
