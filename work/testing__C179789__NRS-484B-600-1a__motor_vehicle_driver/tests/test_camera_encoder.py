import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('camera_encoder',ROOT/'camera_encoder.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class CameraEncoderTests(unittest.TestCase):
    def test_lossless_source_encoder_closes_and_rejects_wrong_frame_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.mkv'
            with MODULE.FFV1Writer(path,2,2) as writer:
                with self.assertRaisesRegex(ValueError,'BGRA frame size mismatch'):
                    writer.write(b'bad')
                writer.write(bytes([0,0,255,255])*4)
            self.assertEqual(writer.exit_code,0)
            self.assertEqual(writer.frames,1)
            self.assertGreater(path.stat().st_size,0)
            with self.assertRaisesRegex(ValueError,'Fresh path'):
                MODULE.FFV1Writer(path,2,2)


if __name__=='__main__':unittest.main()
