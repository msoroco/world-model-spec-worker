"""Small CPU checks for post-capture FFV1 encoding and full decode."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from rail_media_finalize import encode_camera, finalize
from rail_native_capture import CAMERAS


class RailMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2].parent / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "original-cameras" / "overview"
        self.folder.mkdir(parents=True)
        for frame in range(100, 103):
            Image.new("RGB", (64, 36), (frame, 30, 20)).save(
                self.folder / f"{frame:08d}.png", "PNG")

    def test_original_sequence_encodes_and_fully_decodes_ffv1(self):
        output = self.root / "overview.mkv"
        result = encode_camera(self.root, "overview", 100, 3, (64, 36), output)
        self.assertTrue(output.is_file())
        self.assertEqual(result["frames"], 3)
        self.assertEqual(result["codec"], "ffv1")
        self.assertTrue(result["full_decode"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_missing_original_frame_refuses_encoding(self):
        (self.folder / "00000101.png").unlink()
        with self.assertRaisesRegex(ValueError, "sequence incomplete"):
            encode_camera(self.root, "overview", 100, 3, (64, 36),
                          self.root / "overview.mkv")
        self.assertFalse((self.root / "overview.mkv").exists())

    def test_encoded_profile_mismatch_removes_output(self):
        output = self.root / "overview.mkv"
        with self.assertRaisesRegex(ValueError, "media profile differs"):
            encode_camera(self.root, "overview", 100, 3, (128, 72), output)
        self.assertFalse(output.exists())

    def test_full_900_frame_source_map_finalizes_original_media(self):
        raw = (self.folder / "00000100.png").read_bytes()
        rows = []
        frames = []
        for index in range(900):
            number = 100 + index
            relative = f"original-cameras/overview/{number:08d}.png"
            if number >= 101:
                (self.root / relative).write_bytes(raw)
            rows.append({"original_frame": number, "sources": {"overview": {
                "path": relative, "sha256": hashlib.sha256(raw).hexdigest()}}})
            frames.append({"original_frame": number})

        def source(name, value):
            path = self.root / name
            path.write_text(json.dumps(value) + "\n")
            return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

        packet = {"assignment_id": HERE.name}
        receipt = {"case_id": HERE.name + "__obscured_14mph",
                   "capture_kind": "original_native", "fps": 20,
                   "frame_count": 900, "packet": source("reviewed-rail-packet.json", packet),
                   "camera_map": source("camera-map.json", rows),
                   "frames": source("frames.json", frames)}
        (self.root / "native-rail-receipt.json").write_text(json.dumps(receipt) + "\n")
        with patch.dict(CAMERAS, {"overview": (64, 36)}, clear=True):
            result = finalize(self.root, packet, receipt["case_id"])
        self.assertEqual(result["original_frame_count"], 900)
        self.assertEqual(result["media"]["overview"]["frames"], 900)
        self.assertTrue((self.root / "rail-media-receipt.json").is_file())
        self.assertFalse(result["physical_completion_confirmed"])


if __name__ == "__main__":
    unittest.main()
