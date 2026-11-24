import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pixel_audit
from test_saved_finalizer import CASE, SavedFinalizerTests


class OriginalPixelTests(unittest.TestCase):
    def setUp(self):
        self.source = SavedFinalizerTests()
        self.source.setUp()
        self.folder = self.source.folder
        image = Image.new("RGB", (8, 8), (10, 20, 30))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        png = stream.getvalue()
        manifest = {"case_id": CASE, "cameras": {}}
        trace_path = self.folder / "camera_trace.jsonl"
        traces = [json.loads(line) for line in trace_path.read_text().splitlines()]
        for camera in pixel_audit.CAMERAS:
            archive_path = self.folder / (camera + ".zip")
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                for tick in range(900):
                    name = f"{101 + tick}.png"
                    archive.writestr(name, png)
                    traces[tick]["sources"][camera] = camera + ".zip#" + name
            manifest["cameras"][camera] = {
                "path": camera + ".zip",
                "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}
        self.source.write_source("camera_trace", traces, "jsonl")
        self.source.save_receipt()
        manifest["capture_receipt_sha256"] = hashlib.sha256(
            (self.folder / "capture_receipt.json").read_bytes()).hexdigest()
        (self.folder / "camera_media.json").write_text(json.dumps(manifest) + "\n")

    def tearDown(self):
        self.source.tearDown()

    def test_all_3600_original_pixels_decode(self):
        result = pixel_audit.audit_pixels(self.folder, case_id=CASE)
        self.assertEqual(result["decoded_original_pixels"], 3600)
        self.assertEqual(result["physical_visibility"], "requires_independent_review")

    def test_rebound_camera_source_rejected(self):
        traces = [json.loads(line) for line in (self.folder / "camera_trace.jsonl").read_text().splitlines()]
        traces[40]["sources"]["front"] = "rear.zip#141.png"
        self.source.write_source("camera_trace", traces, "jsonl")
        self.source.save_receipt()
        manifest_path = self.folder / "camera_media.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["capture_receipt_sha256"] = hashlib.sha256(
            (self.folder / "capture_receipt.json").read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest) + "\n")
        with self.assertRaisesRegex(ValueError, "source reference mismatch"):
            pixel_audit.audit_pixels(self.folder, case_id=CASE)

    def test_tampered_camera_archive_rejected(self):
        with (self.folder / "front.zip").open("ab") as handle:
            handle.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            pixel_audit.audit_pixels(self.folder, case_id=CASE)


if __name__ == "__main__":
    unittest.main()
