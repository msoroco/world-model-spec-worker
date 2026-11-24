"""CARLA-free frame alignment and overflow checks for original camera capture."""
import io
from pathlib import Path
import queue
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, CameraCapture


def capture_with_frames(frame_lists):
    capture = CameraCapture.__new__(CameraCapture)
    capture.overflow = False
    capture.queues = {}
    capture.encoders = {}
    for name in CAMERAS:
        capture.queues[name] = queue.Queue()
        capture.encoders[name] = SimpleNamespace(stdin=io.BytesIO())
        for frame in frame_lists[name]:
            capture.queues[name].put(SimpleNamespace(frame=frame, raw_data=bytes([frame])))
    return capture


class NativeCameraSyncTests(unittest.TestCase):
    def test_exact_world_frame_is_encoded_from_all_cameras(self):
        capture = capture_with_frames({name: [9, 10] for name in CAMERAS})
        capture.append(10)
        for name in CAMERAS:
            self.assertEqual(capture.encoders[name].stdin.getvalue(), b"\x0a")

    def test_future_frame_rejects_instead_of_mislabeling_video(self):
        capture = capture_with_frames({name: [11] for name in CAMERAS})
        with self.assertRaisesRegex(RuntimeError, "camera/world frame mismatch"):
            capture.append(10)

    def test_overflow_rejects_unsealed_capture(self):
        capture = capture_with_frames({name: [10] for name in CAMERAS})
        capture.overflow = True
        with self.assertRaisesRegex(RuntimeError, "camera queue overflow"):
            capture.append(10)
        self.assertEqual(capture.encoders[CAMERAS[0]].stdin.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
