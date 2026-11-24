import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lamp_photometry import compare_pixels, measure


def fixture(root, lamp_value=150):
    roi = {'format': 'parked-headlamp-photometry-roi-v1',
           'source_kind': 'reviewed_original_camera_roi',
           'source_ref': 'fixture-review-only', 'camera_view': 'approach',
           'dimensions': [8, 4], 'lamp_polygon_xy': [[0, 0], [2, 0], [2, 2], [0, 2]],
           'background_polygon_xy': [[5, 0], [7, 0], [7, 2], [5, 2]]}
    roi_path = root / 'roi.json'
    roi_path.write_text(json.dumps(roi) + '\n')
    path = root / 'approach.zip'
    with ZipFile(path, 'w') as archive:
        for frame in (100, 101, 102):
            image = Image.new('RGB', (8, 4), (30, 30, 30))
            for x in range(3):
                for y in range(3):
                    image.putpixel((x, y), (lamp_value, lamp_value, lamp_value))
            output = io.BytesIO()
            image.save(output, format='PNG')
            archive.writestr(f'{frame}.png', output.getvalue())
    media = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'source_frame_count': 3}
    rows = [{'frame': frame, 'approach_source_frame': frame} for frame in (100, 101, 102)]
    return roi_path, hashlib.sha256(roi_path.read_bytes()).hexdigest(), media, rows


class SavedLampPhotometryTests(unittest.TestCase):
    def test_controlled_pixel_difference_uses_same_roi_and_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_dir, second_dir = root / 'first', root / 'second'
            first_dir.mkdir(); second_dir.mkdir()
            roi, digest, media, rows = fixture(first_dir, lamp_value=70)
            first = measure(first_dir, roi, digest, media, rows,
                            expected_frames=3, expected_dimensions=(8, 4))
            roi, digest, media, rows = fixture(second_dir, lamp_value=150)
            second = measure(second_dir, roi, digest, media, rows,
                             expected_frames=3, expected_dimensions=(8, 4))
            comparison = compare_pixels(first, second)
            self.assertEqual(comparison['mean_second_minus_first_8bit'], 80.0)
            self.assertFalse(comparison['physical_acceptance_claimed'])
            second['roi_sha256'] = 'changed'
            with self.assertRaisesRegex(ValueError, 'fixed camera ROI'):
                compare_pixels(first, second)

    def test_measures_original_pixel_difference_without_legal_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roi, digest, media, rows = fixture(root)
            out = measure(root, roi, digest, media, rows, expected_frames=3,
                          expected_dimensions=(8, 4))
            self.assertEqual(out['frame_count'], 3)
            self.assertEqual([r['lamp_minus_background_8bit'] for r in out['frames']], [120.0] * 3)
            self.assertFalse(out['emitted_intensity_reviewed'])
            self.assertFalse(out['beam_aim_reviewed'])

    def test_rejects_changed_roi_media_and_frame_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roi, digest, media, rows = fixture(root)
            bad = json.loads(roi.read_text()); bad['lamp_polygon_xy'][0] = [1, 0]
            roi.write_text(json.dumps(bad) + '\n')
            with self.assertRaisesRegex(ValueError, 'ROI source hash'):
                measure(root, roi, digest, media, rows, expected_frames=3,
                        expected_dimensions=(8, 4))
            digest = hashlib.sha256(roi.read_bytes()).hexdigest()
            bad['background_polygon_xy'] = bad['lamp_polygon_xy']
            roi.write_text(json.dumps(bad) + '\n')
            with self.assertRaisesRegex(ValueError, 'pixels overlap'):
                measure(root, roi, hashlib.sha256(roi.read_bytes()).hexdigest(), media,
                        rows, expected_frames=3, expected_dimensions=(8, 4))
            roi, digest, media, rows = fixture(root)
            rows[1]['approach_source_frame'] += 1
            with self.assertRaisesRegex(ValueError, 'frame join'):
                measure(root, roi, digest, media, rows, expected_frames=3,
                        expected_dimensions=(8, 4))
            rows[1]['approach_source_frame'] -= 1
            (root / 'approach.zip').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError, 'camera hash'):
                measure(root, roi, digest, media, rows, expected_frames=3,
                        expected_dimensions=(8, 4))


if __name__ == '__main__':
    unittest.main()
