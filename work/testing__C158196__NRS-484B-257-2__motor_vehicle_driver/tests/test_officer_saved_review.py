import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_officer_saved_review',
                                              ROOT / 'officer_saved_review.py')
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class OfficerSavedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.cameras = {}
        for name in REVIEW.CAMERAS:
            path = root / (name + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=gray:s=16x16:r=20', '-frames:v', '3',
                            '-c:v', 'ffv1', str(path)], check=True,
                           capture_output=True)
            self.cameras[name] = path
        self.original_approach = self.cameras['approach'].read_bytes()
        self.capture_path = root / 'capture.json'
        self.review_path = root / 'review.json'
        self.capture = {
            'format': 'worker-subsection-2-officer-native-capture',
            'case_id': PREFIX + 'officer_controls_go', 'frame_count': 3,
            'rows': [{'frame_index': i, 'carla_frame': 100 + i,
                      'officer_program': {'officer_actor_id': 3,
                                          'programmed_direction': 'go'},
                      'camera_raw_sources': {
                          name: {'carla_frame': 100 + i,
                                 'raw_source': str(path) + '#frame-' + str(i)}
                          for name, path in self.cameras.items()}}
                     for i in range(3)]}
        self.write_capture()
        self.review = {
            'format': 'worker-subsection-2-officer-original-frame-review',
            'case_id': self.capture['case_id'],
            'capture_sha256': sha(self.capture_path), 'reviewer': 'fixture-reviewer',
            'camera_sha256': {name: sha(path) for name, path in self.cameras.items()},
            'frames': [self.observation(i) for i in range(3)]}
        self.write_review()

    def observation(self, index):
        refs = self.capture['rows'][index]['camera_raw_sources']
        return {'carla_frame': 100 + index, 'officer_actor_id': 3,
                'direction_frame_source': refs['approach']['raw_source'],
                'authority_frame_source': refs['overview']['raw_source'],
                'control_frame_source': refs['driver_reference']['raw_source'],
                'officer_direction_observed': 'go',
                'police_authority_observed': True,
                'traffic_control_observed': True}

    def write_capture(self):
        self.capture_path.write_text(json.dumps(self.capture, sort_keys=True) + '\n')

    def write_review(self):
        self.review_path.write_text(json.dumps(self.review, sort_keys=True) + '\n')

    def test_review_binds_source_and_keeps_program_separate(self):
        result = REVIEW.validate(self.capture_path, self.review_path, self.cameras)
        self.assertTrue(result['police_control_verified'])
        self.assertEqual(result['reviewed_frames'][2]['officer_direction_observed'], 'go')
        self.assertNotIn('programmed_direction', result['reviewed_frames'][2])

    def test_changed_camera_and_stale_review_rejected(self):
        self.cameras['approach'].write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'camera bytes differ'):
            REVIEW.validate(self.capture_path, self.review_path, self.cameras)
        self.cameras['approach'].write_bytes(self.original_approach)
        self.review['frames'][1]['carla_frame'] = 999
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'observation differs'):
            REVIEW.validate(self.capture_path, self.review_path, self.cameras)

    def test_program_does_not_supply_authority_or_control(self):
        self.review['frames'][0]['police_authority_observed'] = False
        self.write_review()
        result = REVIEW.validate(self.capture_path, self.review_path, self.cameras)
        self.assertFalse(result['police_control_verified'])
        self.review['frames'][0].pop('control_frame_source')
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'observation differs'):
            REVIEW.validate(self.capture_path, self.review_path, self.cameras)

    def test_changed_codec_with_matching_hash_is_rejected(self):
        path = self.cameras['overview']
        path.unlink()
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=gray:s=16x16:r=20', '-frames:v', '3',
                        '-c:v', 'mpeg4', str(path)], check=True,
                       capture_output=True)
        self.review['camera_sha256']['overview'] = sha(path)
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'decode or frame count'):
            REVIEW.validate(self.capture_path, self.review_path, self.cameras)


if __name__ == '__main__':
    unittest.main()
