import io
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_camera_capture import CAMERAS, capture_with_cameras
from saved_camera_audit import audit
import test_event_capture


def png():
    stream = io.BytesIO()
    Image.new("RGB", (3, 2), (10, 20, 30)).save(stream, format="PNG")
    return stream.getvalue()


class SavedCameraTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_event_capture.EventCaptureTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.temp.cleanup)
        self.dims = {name: (3, 2) for name in CAMERAS}

    def step(self, i):
        aspect, event = self.fixture.step(i)
        images = {name: {"frame": aspect["frame"], "png_bytes": png()}
                  for name in CAMERAS}
        return aspect, event, images

    def test_900_original_frames_four_camera_decode_and_tamper(self):
        receipt = capture_with_cameras(self.fixture.site, self.fixture.root,
                                       self.step, diagnostic=True,
                                       dimensions=self.dims)
        self.assertEqual(self.fixture.calls, list(range(900)))
        self.assertEqual(receipt["frame_count"], 900)
        checked = audit(self.fixture.site, self.fixture.root,
                        diagnostic=True, dimensions=self.dims)
        self.assertEqual(checked["decoded_images"], 3600)
        self.assertFalse(checked["physical_acceptance"])
        archive = self.fixture.root / "overview.png.zip"
        original = archive.read_bytes()
        archive.write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "camera source hash"):
            audit(self.fixture.site, self.fixture.root,
                  diagnostic=True, dimensions=self.dims)

    def test_mismatched_camera_frame_cleans_archives(self):
        def wrong(i):
            aspect, event, images = self.step(i)
            if i == 13:
                images["approach"]["frame"] += 1
            return aspect, event, images
        with self.assertRaisesRegex(ValueError, "camera frame mismatch"):
            capture_with_cameras(self.fixture.site, self.fixture.root,
                                 wrong, diagnostic=True, dimensions=self.dims)
        self.assertFalse(any(self.fixture.root.glob("*.png.zip")))
        self.assertFalse((self.fixture.root / "arrow-camera-receipt.json").exists())
