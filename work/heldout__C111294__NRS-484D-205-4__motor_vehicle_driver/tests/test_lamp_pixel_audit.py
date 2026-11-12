from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lamp_pixel_audit import CAMERAS, audit


class LampPixelAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = {name: root / (name + '.mkv') for name in CAMERAS}
        for name, path in self.paths.items():
            path.write_bytes(('original source ' + name).encode())
        self.observation = {
            'installed_backup_lamps': ['left'], 'forward_frames': [20, 21],
            'observations': [
                {'frame': 20, 'forward_motion_observed': True, 'native_backup_lamp_bit': False},
                {'frame': 21, 'forward_motion_observed': True, 'native_backup_lamp_bit': True},
            ],
        }
        self.review = {
            'reviewer': 'independent reviewer', 'source_kind': 'original_camera_pixels',
            'camera_sha256': {n: sha256(p.read_bytes()).hexdigest() for n, p in self.paths.items()},
            'lamp_view': 'reference_corner', 'lamp_view_role': 'rear_lamp_detail',
            'decoded_frame_count': 2,
            'forward_frame_reviews': [
                {'frame': 20, 'visible_lamp_emission': False, 'pixel_observation': 'rear lamps dark'},
                {'frame': 21, 'visible_lamp_emission': True, 'pixel_observation': 'rear left lamp bright'},
            ],
        }
        self.decode_receipt = {'camera_sha256': self.review['camera_sha256'].copy(),
                               'full_decode': True, 'frame_counts': {n: 2 for n in CAMERAS}}

    def test_binds_pixels_independently_of_native_bit(self):
        value = audit(self.observation, self.review, self.paths, self.decode_receipt)
        self.assertEqual(value['emission_observed_on_forward_frames'], [21])
        self.assertTrue(value['pixel_review_complete'])
        self.assertFalse(value['physical_acceptance_claimed'])
        self.assertIsNone(value['legal_result'])

    def test_rejects_stale_camera_and_missing_frame(self):
        self.paths['reference_corner'].write_bytes(b'changed original')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            audit(self.observation, self.review, self.paths, self.decode_receipt)
        self.review['camera_sha256']['reference_corner'] = sha256(self.paths['reference_corner'].read_bytes()).hexdigest()
        self.decode_receipt['camera_sha256']['reference_corner'] = self.review['camera_sha256']['reference_corner']
        self.review['forward_frame_reviews'].pop()
        with self.assertRaisesRegex(ValueError, 'Every original forward frame'):
            audit(self.observation, self.review, self.paths, self.decode_receipt)

    def test_rejects_equipment_conflict_and_missing_view(self):
        self.observation['installed_backup_lamps'] = []
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            audit(self.observation, self.review, self.paths, self.decode_receipt)
        self.observation['installed_backup_lamps'] = ['left']
        self.review['lamp_view_role'] = 'overview'
        with self.assertRaisesRegex(ValueError, 'Rear lamp detail'):
            audit(self.observation, self.review, self.paths, self.decode_receipt)

    def test_rejects_incomplete_decode(self):
        self.decode_receipt['frame_counts']['approach'] = 1
        with self.assertRaisesRegex(ValueError, 'frame counts differ'):
            audit(self.observation, self.review, self.paths, self.decode_receipt)


if __name__ == '__main__':
    unittest.main()
