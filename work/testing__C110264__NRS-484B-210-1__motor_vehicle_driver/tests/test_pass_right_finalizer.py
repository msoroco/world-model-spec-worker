"""Source-shaped saved finalization tests; no physical acceptance is inferred."""
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_finalizer import finalize
from test_pass_right_audit import attempt


class SavedRightPassFinalizerTests(unittest.TestCase):
    def test_all_four_decodes_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = attempt(root, 'left_signal')
            buffer = io.BytesIO()
            Image.new('RGB', (8, 4), (12, 34, 56)).save(buffer, format='PNG')
            for name in ('front', 'rear', 'left', 'right'):
                path = root / (name + '.zip')
                with ZipFile(path, 'w') as archive:
                    for index in range(900):
                        archive.writestr(f'{index:06d}.png', buffer.getvalue())
                manifest['cameras'][name] = {
                    'path': path.name,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            profile = {name: (8, 4) for name in manifest['cameras']}
            case = manifest['case_id']
            result = finalize(root, manifest, selected_case=case,
                              diagnostic_profile=profile)
            self.assertTrue(result['right_pass_observed'])
            self.assertTrue(result['observed_target_left_signal'])
            self.assertFalse(result['observed_target_left_turn'])
            self.assertFalse(result['production_camera_profile_verified'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(set(result['camera_pixel_sha256']), set(profile))
            with self.assertRaisesRegex(ValueError, 'selected exact right-pass case differs'):
                finalize(root, manifest, selected_case=case + '-wrong',
                         diagnostic_profile=profile)
            (root / 'trace.json').unlink()
            with self.assertRaisesRegex(ValueError, 'trace source outside saved attempt or missing'):
                finalize(root, manifest, selected_case=case,
                         diagnostic_profile=profile)


if __name__ == '__main__':
    unittest.main()
