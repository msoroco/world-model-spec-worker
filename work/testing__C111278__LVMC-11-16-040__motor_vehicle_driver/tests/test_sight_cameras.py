import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import CAMERAS, CaptureError, capture
from saved_sight import SavedSightError, verify
from test_native_sight_capture import Ego, World, rays, route
from test_saved_sight import CASE
from test_sight import site


class SightCameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images = {}
        for name, size in CAMERAS.items():
            image = Image.new("RGB", size, (30, 90, 150))
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            cls.images[name] = stream.getvalue()

    def reader(self, frame, snapshot):
        return {name: (frame, raw) for name, raw in self.images.items()}

    def test_original_four_camera_full_decode_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "attempt"
            receipt = capture("blocked_at", site(), World(), Ego(), route, rays,
                              lambda ego: None, output, self.reader)
            self.assertEqual(receipt["camera_capture"], "original_four_camera_png")
            result = verify(output, CASE)
            self.assertEqual(result["camera_capture"]["camera_images_decoded"], 3600)
            rows = json.loads((output / "native-camera-map.json").read_text())
            self.assertEqual([row["frame"] for row in rows], list(range(1, 901)))
            image_path = output / rows[0]["sources"]["overview"]["path"]
            image_path.write_bytes(b"not the original image")
            with self.assertRaisesRegex(SavedSightError, "image changed"):
                verify(output, CASE)

    def test_camera_frame_mismatch_rejected_and_brake_applied(self):
        with tempfile.TemporaryDirectory() as root:
            brakes = []
            def wrong(frame, snapshot):
                result = self.reader(frame, snapshot)
                result["approach"] = (frame + 1, result["approach"][1])
                return result
            with self.assertRaisesRegex(CaptureError, "camera frame identity"):
                capture("blocked_at", site(), World(), Ego(), route, rays,
                        lambda ego: brakes.append(ego), Path(root) / "attempt", wrong)
            self.assertEqual(len(brakes), 1)

    def test_missing_camera_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(CaptureError, "four original camera"):
                capture("blocked_at", site(), World(), Ego(), route, rays,
                        lambda ego: None, Path(root) / "attempt",
                        lambda frame, snapshot: {"overview": (frame, self.images["overview"])})


if __name__ == "__main__": unittest.main()
