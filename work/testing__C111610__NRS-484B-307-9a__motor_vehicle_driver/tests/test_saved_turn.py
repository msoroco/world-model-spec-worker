import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('saved_turn_c111610', ROOT / 'saved_turn.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)


class SavedTurnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        original = {
            'map': {'intersection_id': 'junction-1', 'lane_ids': [1, 2, 3]},
            'ego_signal': {'head_id': 'ego-head', 'governed_lane_ids': [1]},
            'opposing_signal': {'head_id': 'opp-head'},
            'crosswalk': {'crosswalk_id': 'cw-1', 'adjacent_to_turn': True,
                          'polygon_xy': [[0, 0], [2, 0], [2, 2], [0, 2]]},
            'pedestrian_permission': {'crosswalk_id': 'cw-1', 'source_id': 'ped-head',
                                      'lawfulness_basis': 'walk_device'},
            'other_traffic': {'actor_id': 92, 'intersection_id': 'junction-1', 'route_lane_id': 3},
        }
        refs = {name: self.save_json(name, value) for name, value in original.items()}
        site = {'cell_id': 'C111610', 'actor': 'motor_vehicle_driver', 'intersection_id': 'junction-1',
                'ego_approach_lane_id': 1, 'arrow_destination_lane_id': 2,
                'straight_destination_lane_id': 3, 'ego_head_id': 'ego-head',
                'opposing_head_id': 'opp-head', 'adjacent_crosswalk_id': 'cw-1',
                'arrow_direction': 'left', 'pedestrian_actor_id': 91,
                'other_traffic_actor_id': 92, 'original_sources': refs}
        rows = []
        for i in range(3):
            rows.append({'frame': i, 'ego_head_id': 'ego-head', 'opposing_head_id': 'opp-head',
                         'ego_red': True, 'opposing_red': True, 'ego_arrow_direction': 'left',
                         'pedestrian_actor_id': 91, 'pedestrian_permission_source_id': 'ped-head',
                         'other_traffic_actor_id': 92, 'other_traffic_lawful_context': True,
                         'other_traffic_in_intersection': False, 'pedestrian_lawful_context': True,
                         'pedestrian_xy': [1, 1] if i == 0 else [5, 5],
                         'ego_route_lane_id': 2, 'ego_in_intersection': i == 2,
                         'ego_speed_mps': 2.0})
        cameras = {}
        for camera in ('front', 'left', 'right', 'rear'):
            frames = []
            for i in range(3):
                image = Image.new('RGB', (4, 3), color=(i * 60, 10, 20))
                buf = io.BytesIO()
                image.save(buf, format='PNG')
                frames.append({'frame': i, 'source': self.save_bytes(camera + str(i) + '.png', buf.getvalue())})
            cameras[camera] = frames
        self.manifest = {'case_suffix': 'yield_pedestrian', 'fps': 20, 'duration_frames': 3,
                         'site': self.save_json('site', site), 'telemetry': self.save_json('telemetry', rows),
                         'camera_profile': self.save_json('camera_profile',
                             {'fps': 20, 'duration_frames': 3,
                              'cameras': ['front', 'left', 'right', 'rear']}),
                         'cameras': cameras}

    def save_bytes(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def save_json(self, name, value):
        return self.save_bytes(name + '.json', json.dumps(value, sort_keys=True).encode())

    def audit(self):
        return saved.audit_saved_attempt(self.root, self.save_json('manifest', self.manifest), expected_frames=3)

    def test_full_source_decode_and_measurement(self):
        result = self.audit()
        self.assertEqual(result['first_ego_entry_frame'], 2)
        self.assertEqual(result['original_frames'], 3)
        self.assertEqual({k: v['frames'] for k, v in result['decoded_cameras'].items()},
                         dict.fromkeys(('front', 'left', 'right', 'rear'), 3))
        self.assertFalse(result['physical_acceptance'])
        self.assertTrue(result['comparison_row']['held_until_clear'])
        self.assertEqual(result['comparison_row']['original_signal_frames'], 3)

    def test_production_600_frame_contract(self):
        rows = json.loads((self.root / 'telemetry.json').read_text())
        for frame in range(3, 600):
            row = dict(rows[-1])
            row['frame'] = frame
            rows.append(row)
        self.manifest['telemetry'] = self.save_json('telemetry', rows)
        self.manifest['duration_frames'] = 600
        self.manifest['camera_profile'] = self.save_json('camera_profile',
            {'fps': 20, 'duration_frames': 600,
             'cameras': ['front', 'left', 'right', 'rear']})
        for camera, frames in self.manifest['cameras'].items():
            source_raw = (self.root / frames[-1]['source']['path']).read_bytes()
            for frame in range(3, 600):
                frames.append({'frame': frame,
                               'source': self.save_bytes(camera + str(frame) + '.png', source_raw)})
        result = saved.audit_saved_attempt(self.root, self.save_json('full_manifest', self.manifest))
        self.assertEqual(result['original_frames'], 600)
        self.assertEqual(sum(v['frames'] for v in result['decoded_cameras'].values()), 2400)

    def test_missing_changed_or_broken_camera_rejected(self):
        self.manifest['cameras']['rear'].pop()
        with self.assertRaisesRegex(saved.SavedSourceError, 'camera frame count mismatch'):
            self.audit()
        self.manifest['cameras']['rear'].append(self.manifest['cameras']['front'][2])
        self.manifest['cameras']['front'][1]['source']['sha256'] = '0' * 64
        with self.assertRaisesRegex(saved.SavedSourceError, 'source hash mismatch'):
            self.audit()
        self.manifest['cameras']['front'][1]['source'] = self.save_bytes('broken.png', b'broken')
        with self.assertRaisesRegex(saved.SavedSourceError, 'camera image decode failed'):
            self.audit()

    def test_missing_original_signal_or_wrong_timing_rejected(self):
        with self.assertRaisesRegex(saved.SavedSourceError, 'timing mismatch'):
            saved.audit_saved_attempt(self.root, self.save_json('short_manifest', self.manifest))
        self.manifest['duration_frames'] = 2
        with self.assertRaisesRegex(saved.SavedSourceError, 'timing mismatch'):
            self.audit()
        self.manifest['duration_frames'] = 3
        rows = json.loads((self.root / 'telemetry.json').read_text())
        rows[2]['opposing_red'] = False
        self.manifest['telemetry'] = self.save_json('telemetry', rows)
        with self.assertRaisesRegex(saved.SavedSourceError, 'opposing steady red'):
            self.audit()

    def test_frame_identity_and_escape_rejected(self):
        self.manifest['cameras']['left'][1]['frame'] = 2
        with self.assertRaisesRegex(saved.SavedSourceError, 'camera frame sequence mismatch'):
            self.audit()
        self.manifest['cameras']['left'][1]['frame'] = 1
        self.manifest['cameras']['left'][1]['source']['path'] = '../outside.png'
        with self.assertRaisesRegex(saved.SavedSourceError, 'source escapes attempt root'):
            self.audit()


if __name__ == '__main__':
    unittest.main()
