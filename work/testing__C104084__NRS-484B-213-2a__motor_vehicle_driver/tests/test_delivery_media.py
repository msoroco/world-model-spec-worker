import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('delivery_media', ROOT / 'delivery_media.py')
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def fixture(directory):
    source = directory / 'overview.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=32x24:r=20', '-frames:v', '20',
                    '-c:v', 'mpeg4', '-y', str(source)], check=True)
    for camera in media.CAMERAS[1:]:
        shutil.copyfile(source, directory / f'{camera}.mkv')
    return {f'{camera}.mkv': hashlib.sha256(
        (directory / f'{camera}.mkv').read_bytes()).hexdigest()
        for camera in media.CAMERAS}


class MediaAuditTests(unittest.TestCase):
    def test_full_decode_four_original_camera_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            receipt = media.audit(attempt, hashes, expected_frames=20,
                                  expected_dimensions={c: (32, 24) for c in media.CAMERAS})
            self.assertEqual(set(receipt['cameras']), set(media.CAMERAS))
            self.assertTrue(all(row['frames_decoded'] == 20 for row in receipt['cameras'].values()))
            self.assertFalse(receipt['origin_verified'])
            self.assertFalse(receipt['physical_visibility_reviewed'])

    def test_rejects_changed_and_missing_original(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            source = attempt / 'approach.mkv'
            source.write_bytes(source.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'original changed'):
                media.audit(attempt, hashes, expected_frames=20)
            source.unlink()
            with self.assertRaisesRegex(ValueError, 'original missing'):
                media.audit(attempt, hashes, expected_frames=20)

    def test_rejects_count_and_corrupt_video(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            with self.assertRaisesRegex(ValueError, 'frame count mismatch'):
                media.audit(attempt, hashes, expected_frames=21)
            source = attempt / 'overview.mkv'
            source.write_bytes(b'not a video')
            hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'media decode failed'):
                media.audit(attempt, hashes, expected_frames=20)

    def test_rejects_delayed_frame_with_nominal_rate_and_count(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            source = attempt / 'approach.mkv'
            source.unlink()
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=blue:s=32x24:r=20', '-frames:v', '20',
                            '-vf', r'setpts=PTS+0.05/TB*gte(N\,10)',
                            '-fps_mode', 'vfr', '-c:v', 'mpeg4', str(source)],
                           check=True)
            hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'presentation timing mismatch'):
                media.audit(attempt, hashes, expected_frames=20)


if __name__ == '__main__':
    unittest.main()
