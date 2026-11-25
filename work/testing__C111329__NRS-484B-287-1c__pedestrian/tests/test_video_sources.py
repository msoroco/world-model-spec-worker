from io import BytesIO
import json
import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_observation import CAMERAS, capture_observation
from video_sources import encode_original_cameras
import test_native_observation


class OriginalCameraEncodingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_observation.ObservationTests("test_original_capture_and_saved_crossing")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        image = BytesIO()
        Image.new("RGB", (8, 6), (30, 60, 90)).save(image, format="PNG")
        payload = image.getvalue()
        readers = {name: lambda frame, payload=payload: {"frame": frame,
                   "png_bytes": payload} for name in CAMERAS}
        capture_observation(self.fixture.world, self.fixture.walker, self.fixture.packet,
            "case-one", self.fixture.path, self.fixture.read_device, ticks=5,
            camera_readers=readers, camera_dimensions={name: (8, 6) for name in CAMERAS})

    def test_four_lossless_20hz_sources_from_original_frames(self):
        result = encode_original_cameras(self.fixture.path)
        self.assertEqual(set(result), set(CAMERAS))
        self.assertTrue(all(row["frame_count"] == 5 and row["fps"] == 20
                            for row in result.values()))
        self.assertTrue(all(Path(row["path"]).is_file() for row in result.values()))
        self.assertEqual(list(self.fixture.path.parent.glob("camera-encode-*")), [])

    def test_original_frame_hash_drift_rejected_before_encoding(self):
        document = json.loads(self.fixture.path.read_text())
        document["frames"][0]["camera_frames"]["overview"]["sha256"] = "0" * 64
        self.fixture.path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "frame hash differs"):
            encode_original_cameras(self.fixture.path)
        self.assertEqual(list(self.fixture.path.parent.glob("camera-encode-*")), [])


if __name__ == "__main__":
    unittest.main()
