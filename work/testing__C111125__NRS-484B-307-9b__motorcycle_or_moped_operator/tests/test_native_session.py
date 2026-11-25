import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_session

CASE = ROOT.name + '__two_cycles_clear'


def make_site(root):
    refs = {}
    for key in ('map_ref', 'route_ref', 'signal_ref', 'stop_ref', 'crosswalk_ref'):
        path = root / (key + '.json')
        path.write_text(json.dumps({'source': key}) + '\n')
        refs[key] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    site = {'diagnostic_fixture': False, 'case_id': CASE,
            'cell_id': 'C111125', 'actor': 'motorcycle_or_moped_operator',
            'maneuver': 'straight', 'control': 'traffic_light',
            'original_sources': refs, 'map_ref': 'map_ref', 'route_ref': 'route_ref',
            'signal_ref': 'signal_ref', 'stop_ref': 'stop_ref',
            'crosswalk_ref': 'crosswalk_ref', 'ego_approach_id': 'west',
            'official_head_id': 'head-17', 'facing_relation': True,
            'route_xy': [[-20, 0], [-5, 0], [5, 0], [20, 0]],
            'straight_tolerance_m': 0.5, 'stop_reference_kind': 'marked_stop_line',
            'stop_reference_station_m': -5, 'intersection_entry_station_m': 0,
            'ego_blueprint_id': 'vehicle.motorcycle',
            'ego_classification_source': 'reviewed-source'}
    packet = root / 'site.json'
    packet.write_text(json.dumps(site) + '\n')
    return packet, site


class NativeSessionTests(unittest.TestCase):
    def test_original_source_copy_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet, site = make_site(root)
            attempt = root / 'materialized'
            attempt.mkdir()
            (attempt / 'config.json').write_text('{}\n')
            ego = Mock()
            session = types.SimpleNamespace(world=object(), carla=object(),
                                             blueprint_library=object(), event_adapter=object(), camera_adapter=object())
            def fake_capture(_site, _root, _adapter, output, **kwargs):
                rows = [{'frame': i, 'official_head_id': 'head-17', 'actor_id': 'ego-1'}
                        for i in range(900)]
                data = json.dumps(rows) + '\n'
                Path(output).write_text(data)
                return {'frame_count': 900, 'actor_id': 'ego-1',
                        'event_ref': {'path': 'original-events.json',
                                      'sha256': hashlib.sha256(data.encode()).hexdigest()}}
            def fake_finish():
                (attempt / 'media-manifest.json').write_text(json.dumps({
                    'camera_views': {name: {'source': {'path': name + '.mkv', 'sha256': '0'*64},
                                            'first_original_frame': 0, 'last_original_frame': 899,
                                            'width': 16, 'height': 16}
                                     for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}}))
                return {'path': 'media-manifest.json', 'sha256': 'a' * 64}
            with patch.object(native_session, 'construct_native', return_value={'ego': ego}) as construct, \
                    patch.object(native_session, 'capture_original', side_effect=fake_capture) as capture, \
                    patch.object(native_session, 'FourViewRecorder') as recorder, \
                    patch.object(native_session, 'audit_manifest') as audit:
                recorder.return_value.finish.side_effect = fake_finish
                audit.return_value = {'camera_views': {name: {'decoded_frames': 900, 'fps': 20}
                                  for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}}
                receipt = native_session.capture_events(session, packet, CASE, attempt)
            construct.assert_called_once()
            self.assertEqual(capture.call_args.args[1], attempt)
            ego.destroy.assert_called_once()
            self.assertEqual((attempt / 'native-site.json').read_bytes(), packet.read_bytes())
            for ref in site['original_sources'].values():
                self.assertEqual((attempt / ref['path']).read_bytes(), (root / ref['path']).read_bytes())
            self.assertEqual(receipt['camera_media_status'], 'four_original_views_recorded_unreviewed')
            self.assertEqual(receipt['media_manifest_ref']['path'], 'media-manifest.json')
            self.assertEqual(receipt['saved_manifest_ref']['path'], 'saved-manifest.json')
            audit.assert_called_once()
            self.assertEqual(receipt['site_packet_sha256'], hashlib.sha256(packet.read_bytes()).hexdigest())

    def test_capture_failure_still_destroys_ego(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet, _ = make_site(root)
            attempt = root / 'materialized'
            attempt.mkdir()
            ego = Mock()
            session = types.SimpleNamespace(world=object(), carla=object(),
                                             blueprint_library=object(), event_adapter=object(), camera_adapter=object())
            with patch.object(native_session, 'construct_native', return_value={'ego': ego}), \
                    patch.object(native_session, 'capture_original', side_effect=ValueError('frame gap')), \
                    patch.object(native_session, 'FourViewRecorder'):
                with self.assertRaisesRegex(ValueError, 'frame gap'):
                    native_session.capture_events(session, packet, CASE, attempt)
            ego.destroy.assert_called_once()
            self.assertFalse((attempt / 'event-receipt.json').exists())

    def test_missing_or_reused_source_refused_before_spawn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet, site = make_site(root)
            attempt = root / 'materialized'
            attempt.mkdir()
            session = types.SimpleNamespace(world=object(), carla=object(),
                                             blueprint_library=object(), event_adapter=object(), camera_adapter=object())
            (root / site['original_sources']['map_ref']['path']).unlink()
            with patch.object(native_session, 'construct_native') as construct:
                with self.assertRaisesRegex(ValueError, 'missing or escaping source'):
                    native_session.capture_events(session, packet, CASE, attempt)
            construct.assert_not_called()
            make_site(root)
            (attempt / 'original-events.json').write_text('existing\n')
            with patch.object(native_session, 'construct_native') as construct:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    native_session.capture_events(session, packet, CASE, attempt)
            construct.assert_not_called()


if __name__ == '__main__':
    unittest.main()
