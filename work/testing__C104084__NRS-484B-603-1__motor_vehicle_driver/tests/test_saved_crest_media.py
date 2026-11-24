import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_crest_media import audit_media
from test_saved_crest_audit import fixture


def video(root, camera, frames=900):
    path = root / f'{camera}.mkv'
    path.unlink(missing_ok=True)
    command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
               f'color=c={camera_color(camera)}:s=32x24:r=20',
               '-frames:v', str(frames), '-c:v', 'ffv1', str(path)]
    subprocess.run(command, check=True, capture_output=True)
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def camera_color(camera):
    return {'front': 'red', 'left': 'green', 'right': 'blue', 'rear': 'white'}[camera]


def media_fixture(root):
    manifest = fixture(root)
    manifest['camera_sources'] = {camera: video(root, camera)
                                  for camera in ('front', 'left', 'right', 'rear')}
    manifest['camera_dimensions'] = {camera: [32, 24]
                                     for camera in manifest['camera_sources']}
    return manifest


class SavedCrestMediaTests(unittest.TestCase):
    def test_four_source_bound_full_decodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = audit_media(root, media_fixture(root))
            self.assertTrue(proof['checks']['actual_pixels'])
            self.assertFalse(proof['checks']['physical_completion'])
            self.assertEqual(set(proof['camera_decodes']), {'front', 'left', 'right', 'rear'})
            self.assertTrue(all(v['frame_count'] == 900 for v in proof['camera_decodes'].values()))
            self.assertEqual(len({v['decoded_rgb24_sha256'] for v in proof['camera_decodes'].values()}), 4)

    def test_rejects_short_or_changed_video_and_wrong_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = media_fixture(root)
            manifest['camera_dimensions']['front'] = [33, 24]
            with self.assertRaisesRegex(ValueError, 'dimensions'):
                audit_media(root, manifest)
            manifest['camera_dimensions']['front'] = [32, 24]
            manifest['camera_sources']['rear'] = video(root, 'rear', 899)
            with self.assertRaisesRegex(ValueError, '900-frame'):
                audit_media(root, manifest)
            manifest['camera_sources']['rear'] = video(root, 'rear', 900)
            (root / 'left.mkv').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash'):
                audit_media(root, manifest)


if __name__ == '__main__':
    unittest.main()
