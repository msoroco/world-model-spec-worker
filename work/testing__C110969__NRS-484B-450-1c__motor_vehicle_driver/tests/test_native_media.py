import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import acquire
from native_media import CAMERAS, NativeMediaWriter, audit_saved_acquisition
from test_native_acquisition import Actor, BOUNDARY, CASE, Controller, Observer, World


def png_bytes(size):
    out = io.BytesIO()
    Image.new("RGB", size, (15, 25, 35)).save(out, format="PNG")
    return out.getvalue()


class Cameras:
    def __init__(self):
        self.images = {key: png_bytes(size) for key, size in CAMERAS.items()}
        self.corrupt = None
        self.offset = 0

    def capture(self, snapshot, actor):
        values = {key: {"frame": snapshot.frame + self.offset,
                        "source": "original_native_camera_callback", "png": value}
                  for key, value in self.images.items()}
        if self.corrupt:
            values[self.corrupt]["png"] = b"not-a-png"
        return values


class MediaTests(unittest.TestCase):
    def test_four_camera_saved_decode_and_trace_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    "run-media", root, 3, NativeMediaWriter(root, Cameras()))
            receipt = audit_saved_acquisition(root)
            self.assertEqual(receipt["decoded_camera_frames"], 12)
            self.assertFalse(receipt["physical_visibility_reviewed"])
            trace = json.loads((root / "trace.json").read_text())
            self.assertEqual([sample["frame"] for sample in trace["samples"]], [1, 2, 3])

    def test_reject_wrong_frame_or_corrupt_png(self):
        for fault in ("offset", "corrupt"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cameras = Cameras()
                if fault == "offset":
                    cameras.offset = 1
                else:
                    cameras.corrupt = "approach"
                with self.assertRaisesRegex(ValueError, "camera callback frame/source mismatch|camera PNG decode failed"):
                    acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                            "run-media", root, 3, NativeMediaWriter(root, cameras))
                self.assertFalse((root / "media-manifest.json").exists())

    def test_reject_tamper_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    "run-media", root, 3, NativeMediaWriter(root, Cameras()))
            archive = root / "overview.zip"
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "archive seal differs"):
                audit_saved_acquisition(root)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    "run-media", root, 3, NativeMediaWriter(root, Cameras()))
            (root / "approach.zip").unlink()
            with self.assertRaisesRegex(ValueError, "archive seal differs"):
                audit_saved_acquisition(root)

    def test_reject_rebound_trace_even_with_valid_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    "run-media", root, 3, NativeMediaWriter(root, Cameras()))
            trace = root / "trace.json"
            trace.write_bytes(trace.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "source manifest seal differs"):
                audit_saved_acquisition(root)


if __name__ == "__main__":
    unittest.main()
