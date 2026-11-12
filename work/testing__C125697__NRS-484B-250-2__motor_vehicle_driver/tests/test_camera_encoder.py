import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c125697_camera_encoder', ROOT / 'camera_encoder.py')
encoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(encoder)


class EncoderTests(unittest.TestCase):
    def test_ffv1_source_frames_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'overview.mkv'
            with encoder.FFV1Writer(path, 2, 2) as writer:
                writer.write(bytes([0, 0, 255, 255] * 4))
                writer.write(bytes([0, 255, 0, 255] * 4))
            self.assertEqual(writer.exit_code, 0)
            self.assertEqual(writer.frames, 2)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=codec_name,width,height,nb_read_frames',
                                    '-of', 'json', str(path)], check=True,
                                   capture_output=True, text=True)
            stream = json.loads(probe.stdout)['streams'][0]
            self.assertEqual((stream['codec_name'], stream['width'],
                              stream['height'], stream['nb_read_frames']),
                             ('ffv1', 2, 2, '2'))

    def test_bad_frame_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'approach.mkv'
            with encoder.FFV1Writer(path, 2, 2) as writer:
                with self.assertRaisesRegex(ValueError, 'frame size mismatch'):
                    writer.write(b'wrong')
                writer.write(bytes([0, 0, 0, 255] * 4))


if __name__ == '__main__':
    unittest.main()
