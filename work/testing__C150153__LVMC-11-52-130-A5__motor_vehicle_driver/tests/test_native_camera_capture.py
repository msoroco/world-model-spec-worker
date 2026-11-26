"""Diagnostic camera bytes test Native synchronization and cleanup protocol."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from independent_delivery_audit import CAMERAS
from native_camera_capture import capture
from parking import CASES
from test_independent_delivery_audit import sha
from test_native_case_runner import CombinedAdapter
from test_reviewed_site import ReviewedSiteTests


class CameraAdapter(CombinedAdapter):
    def start_cameras(self, attempt, plan_sha, names):
        self.attempt = Path(attempt)
        self.names = tuple(names)
        self.index = 0
        self.aborted = False

    def record_camera_frame(self, row):
        index = self.index
        self.index += 1
        return {name: index for name in self.names}

    def finish_cameras(self):
        result = {}
        for name in self.names:
            path = self.attempt / (name + '.mkv')
            path.write_text('synthetic non-video camera bytes\n')
            result[name] = path
        return result

    def abort_cameras(self):
        self.aborted = True

    def original_comparison_context(self):
        return {'format': 'sidewalk-elevator-original-comparison-context',
                'case_id': HERE.name + '__' + self.capture.case.id,
                'site_packet_sha256': self.capture.site['site_sha256'],
                'history_sha256': sha(self.attempt / 'history.jsonl'),
                'ego_blueprint_sha256': self.capture.site['ego_blueprint_sha256'],
                'route_sha256': self.capture.site['one_way_direction_sha256'],
                'weather_sha256': 'synthetic-weather-source',
                'curb_gap_target_m': 0.3,
                'exception_source_sha256': (self.capture.site.get({
                    'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                    'police_direction': 'police_direction_source_sha256',
                    'traffic_device_direction': 'traffic_device_source_sha256',
                }.get(self.capture.case.exception)) if self.capture.case.exception != 'none' else None)}


class NativeCameraCaptureTests(unittest.TestCase):
    def test_all_exact_cases_join_four_views_and_reject_bad_frame_map(self):
        scratch = Path('.runtime-work/c150153-native-camera-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            with self.subTest(case=case.id), TemporaryDirectory(dir=scratch) as temp:
                packet, sources, source_packet = ReviewedSiteTests().make_packet(Path(temp))
                site = dict(source_packet['site'], site_sha256=sha(packet))
                adapter = CameraAdapter(site, case)
                attempt = Path(temp) / 'attempt'
                proof = capture(adapter, packet, sources, HERE.name + '__' + case.id,
                                4.0, attempt)
                self.assertEqual(proof['frame_count'], 900)
                self.assertEqual(set(proof['camera_sha256']), set(CAMERAS))
                self.assertFalse(proof['full_video_decode'])
                mapping = [json.loads(line) for line in (attempt / 'camera-frame-map.jsonl').read_text().splitlines()]
                self.assertEqual(len(mapping), 900)
                self.assertEqual(mapping[0]['original_frame'], 4000)
                self.assertEqual(mapping[-1]['camera_frames']['overview'], 899)
                self.assertFalse(adapter.aborted)
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    capture(adapter, packet, sources, HERE.name + '__' + case.id,
                            4.0, attempt)

    def test_bad_camera_index_aborts_and_releases(self):
        scratch = Path('.runtime-work/c150153-native-camera-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet, sources, source_packet = ReviewedSiteTests().make_packet(Path(temp))
            site = dict(source_packet['site'], site_sha256=sha(packet))
            class WrongIndex(CameraAdapter):
                def record_camera_frame(self, row):
                    values = super().record_camera_frame(row)
                    values['overview'] += 1
                    return values
            adapter = WrongIndex(site, CASES[0])
            with self.assertRaisesRegex(ValueError, 'frame index join differs'):
                capture(adapter, packet, sources, HERE.name + '__' + CASES[0].id,
                        4.0, Path(temp) / 'bad-attempt')
            self.assertTrue(adapter.aborted)
            self.assertFalse((Path(temp) / 'bad-attempt/history.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
