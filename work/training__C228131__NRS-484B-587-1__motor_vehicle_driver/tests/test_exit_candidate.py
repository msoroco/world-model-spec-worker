import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native'))
from exit_candidate import CAMERAS, FRAMES, measure, target
from exit_geometry import check as geometry_check
from exit_finalize import AUTHORITY, observation


def make_sources(mode):
    road = b'<OpenDRIVE>exit candidate only</OpenDRIVE>\n'
    context = {'source_kind': 'synthetic_cpu',
               'road_source_sha256': hashlib.sha256(road).hexdigest(),
               'controlled_access_highway': True, 'device_official': True,
               'device_erected': True, 'device_indicates_exit': True,
               'highway_edge_y_m': -3.5,
               'indicated_exit_x_interval_m': [-1, 1]}
    for name in ('controlled_access_designation_sha256',
                 'official_device_authority_sha256', 'device_content_sha256',
                 'device_erection_sha256', 'exit_extent_source_sha256'):
        context[name] = hashlib.sha256(name.encode()).hexdigest()
    poses, frames = [], []
    for index in range(FRAMES):
        native = index + 100
        request = target(mode, index)
        cameras = {name: native for name in CAMERAS}
        poses.append({'video_frame': index, 'native_frame': native,
                      'time_s': index / 20, 'vehicle_id': 77,
                      'center_xy_m': [request['x_m'], request['y_m']],
                      'footprint_half_width_m': 1,
                      'camera_native_frames': cameras})
        frames.append({'video_frame': index, 'native_frame': native,
                       'time_s': index / 20, 'camera_native_frames': cameras})
    encode = lambda values: ''.join(json.dumps(row) + '\n' for row in values).encode()
    return encode(poses), encode(frames), json.dumps(context).encode(), road


class ExitCandidate(unittest.TestCase):
    def test_mirrored_indicated_and_outside_exit(self):
        geometry = geometry_check()
        self.assertTrue(geometry['exit_paving_crosses_edge'])
        self.assertFalse(geometry['native_lane_connectivity_verified'])
        for mode, expected in (('indicated_exit', True), ('outside_exit', False)):
            with self.subTest(mode=mode):
                sources = make_sources(mode)
                receipt = measure(*sources)
                self.assertEqual(receipt['frame_count'], 600)
                self.assertEqual(receipt['four_camera_joins'], 2400)
                self.assertEqual(len(receipt['exit_events']), 1)
                self.assertEqual(receipt['exit_events'][0]['within_indicated_exit'], expected)
                self.assertFalse(receipt['physical_completion_verified'])
                self.assertIsNone(receipt['legal_result'])

    def test_missing_original_source_and_frame_join_rejected(self):
        pose, frame, context, road = make_sources('indicated_exit')
        damaged = json.loads(context)
        damaged.pop('exit_extent_source_sha256')
        with self.assertRaisesRegex(ValueError, 'exit_extent_source_sha256 missing'):
            measure(pose, frame, json.dumps(damaged).encode(), road)
        with self.assertRaisesRegex(ValueError, 'road source hash differs'):
            measure(pose, frame, context, b'other road')
        changed = [json.loads(line) for line in frame.splitlines()]
        changed[300]['camera_native_frames']['driver_reference'] = -1
        altered = ''.join(json.dumps(row) + '\n' for row in changed).encode()
        with self.assertRaisesRegex(ValueError, 'camera joins missing'):
            measure(pose, altered, context, road)

    def test_reverse_direction_and_multiple_exits_rejected(self):
        pose, frame, context, road = make_sources('indicated_exit')
        values = [json.loads(line) for line in pose.splitlines()]
        for value in values:
            value['center_xy_m'][1] = -9 - value['center_xy_m'][1]
        reversed_pose = ''.join(json.dumps(row) + '\n' for row in values).encode()
        with self.assertRaisesRegex(ValueError, 'Exactly one measured exit event'):
            measure(reversed_pose, frame, context, road)
        values = [json.loads(line) for line in pose.splitlines()]
        for value in values[400:]:
            value['center_xy_m'][1] = 0 if value['video_frame'] < 500 else -9
        repeated = ''.join(json.dumps(row) + '\n' for row in values).encode()
        with self.assertRaisesRegex(ValueError, 'Exactly one measured exit event'):
            measure(repeated, frame, context, road)

    def test_separately_reviewed_exit_source_joins(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work' / 'c228131-exit-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        for mode, indicated in (('indicated_exit', True), ('outside_exit', False)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=scratch) as temp:
                root = Path(temp)
                poses, frames, _, road = make_sources(mode)
                data = {'actor-poses.jsonl': poses, 'video_frames.jsonl': frames,
                        'road.xodr': road}
                data.update({name: name.encode() for name in AUTHORITY})
                for name, raw in data.items():
                    (root / name).write_bytes(raw)
                for name in CAMERAS:
                    (root / (name + '.mkv')).write_bytes(b'diagnostic placeholder')
                (root / 'fixture-provenance.json').write_text('{}\n')
                digest = lambda name: hashlib.sha256(data[name]).hexdigest()
                access = {'review_status': 'synthetic_diagnostic', 'reviewer': 'diagnostic-access',
                          'source': 'diagnostic-access-source', 'road_sha256': digest('road.xodr'),
                          'pose_sha256': digest('actor-poses.jsonl'),
                          'source_sha256': {'access-authority.txt': digest('access-authority.txt')},
                          'controlled_access_highway': True, 'highway_edge_y_m': -3.5}
                device = {'review_status': 'synthetic_diagnostic', 'reviewer': 'diagnostic-device',
                          'source': 'diagnostic-device-source', 'road_sha256': digest('road.xodr'),
                          'frame_map_sha256': digest('video_frames.jsonl'),
                          'source_sha256': {name: digest(name) for name in AUTHORITY[1:]},
                          'device_official': True, 'device_erected': True,
                          'device_indicates_exit': True, 'indicated_exit_x_interval_m': [-1, 1]}
                (root / 'access-review.json').write_text(json.dumps(access) + '\n')
                (root / 'device-review.json').write_text(json.dumps(device) + '\n')
                facts = observation(root)
                self.assertEqual(facts['exit_events'][0]['within_indicated_exit'], indicated)
                self.assertFalse(facts['video_decode_verified'])
                self.assertFalse(facts['original_device_pixels_verified'])
                (root / 'exit-extent.txt').write_text('altered source\n')
                with self.assertRaisesRegex(ValueError, 'Exit authority source differs'):
                    observation(root)
                (root / 'exit-extent.txt').write_bytes(data['exit-extent.txt'])
                (root / 'device-review.json').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing original exit source'):
                    observation(root)


if __name__ == '__main__':
    unittest.main()
