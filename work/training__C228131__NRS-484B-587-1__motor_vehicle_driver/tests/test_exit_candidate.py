import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native'))
from exit_candidate import CAMERAS, FRAMES, measure, target
from exit_geometry import check as geometry_check


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


if __name__ == '__main__':
    unittest.main()
