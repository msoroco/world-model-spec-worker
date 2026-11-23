"""Only observed encoder exits may be used in the Native capture seal."""
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_cameras import CameraCapture


class Process:
    def __init__(self, code):
        self.stdin = io.BytesIO()
        self.code = code

    def wait(self, timeout):
        return self.code


class EncoderClosureTests(unittest.TestCase):
    def test_success_codes_are_observed(self):
        camera = CameraCapture.__new__(CameraCapture)
        camera.sensors = []
        camera.processes = {"overview": Process(0), "approach": Process(0)}
        camera.exit_codes = {}
        camera.closed = False
        camera.close()
        self.assertEqual(camera.exit_codes, {"overview": 0, "approach": 0})

    def test_failure_code_is_retained(self):
        camera = CameraCapture.__new__(CameraCapture)
        camera.sensors = []
        camera.processes = {"overview": Process(7)}
        camera.exit_codes = {}
        camera.closed = False
        with self.assertRaisesRegex(RuntimeError, "encoder failed"):
            camera.close()
        self.assertEqual(camera.exit_codes, {"overview": 7})


if __name__ == "__main__":
    unittest.main()
