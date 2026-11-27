"""Independent delivery audit CPU positive and negative source tests."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from delivery_audit import audit
from test_analysis import CASE, TEMP_ROOT
from test_beam_publication import _finish_fixture

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="delivery-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _finish_fixture(self.root)
        receipt_path = self.root / "native-source-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        for view in VIEWS:
            path = self.root / (view + ".mkv")
            path.unlink()
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-f", "lavfi", "-i", "color=c=gray:s=16x12:r=20",
                            "-frames:v", "9", "-c:v", "ffv1", str(path)],
                           check=True, stdout=subprocess.DEVNULL)
            receipt["camera_movies"][view]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt) + "\n")

    def test_complete_diagnostic_sources_decode(self):
        report = audit(self.root, CASE["case_id"], diagnostic=True, expected_frames=9)
        self.assertEqual(report["format"], "worker-delivery-audit")
        self.assertEqual(set(report["decoded_frames"]), set(VIEWS))
        self.assertEqual(set(report["decoded_frames"].values()), {9})
        self.assertFalse(report["checks"]["native_source"])

    def test_missing_original_roi_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing required source: roi-frames.jsonl"):
            audit(self.root, CASE["case_id"], diagnostic=True,
                  negative_remove="roi-frames.jsonl", expected_frames=9)

    def test_stale_original_movie_rejected(self):
        (self.root / "overview.mkv").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "movie hash differs"):
            audit(self.root, CASE["case_id"], diagnostic=True, expected_frames=9)


if __name__ == "__main__":
    unittest.main()
