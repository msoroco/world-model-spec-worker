import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import _digest, _sha, audit, decode_video, verify_seal
from saved_entry import CAMERAS, build_report
from test_saved_entry import make_attempt


def native_attempt(root):
    make_attempt(root)
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
    (root / "construction.json").write_text("{}\n")
    (root / "runner.py").write_text("# original runner\n")
    (root / "trace.jsonl").write_text('{"frame": 1}\n')
    sources = {path.name: _sha(path) for path in root.iterdir() if path.is_file()}
    seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": False, "frames": 3,
            "restoration": {"restored": True},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "encoder_exit_codes": {name: 0 for name in CAMERAS},
            "sources": sources, "source_digest": _digest(sources),
            "native_revision": {"construction_sha256": sources["construction.json"],
                                "runner_sha256": sources["runner.py"]}}
    (root / "capture-seal.json").write_text(json.dumps(seal) + "\n")


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.root = Path(self.temp.name)
        native_attempt(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_seal_and_saved_native_report_verify_original_sources(self):
        self.assertEqual(verify_seal(self.root), 3)
        report = build_report(self.root)
        self.assertEqual(report["measurement"]["first_entry"]["frame"], 2)
        self.assertFalse(report["actual_pixels_verified"])

    def test_changed_packet_and_fake_marker_cannot_bypass_seal(self):
        path = self.root / "acquisition-provenance.json"
        path.write_text(json.dumps({"provenance_kind": "native", "diagnostic_fixture": False,
                                    "native_capture_sealed": True}) + "\n")
        with self.assertRaisesRegex(ValueError, "sealed source hash changed"):
            build_report(self.root)

    def test_missing_revision_and_failed_encoder_rejected(self):
        path = self.root / "capture-seal.json"
        seal = json.loads(path.read_text())
        seal["native_revision"]["runner_sha256"] = "0" * 64
        path.write_text(json.dumps(seal) + "\n")
        with self.assertRaisesRegex(ValueError, "revision differs"):
            verify_seal(self.root)
        seal["native_revision"]["runner_sha256"] = seal["sources"]["runner.py"]
        seal["encoder_exit_codes"]["overview"] = 1
        path.write_text(json.dumps(seal) + "\n")
        with self.assertRaisesRegex(ValueError, "successful original encoders"):
            verify_seal(self.root)

    def test_audit_keeps_pixel_and_physical_claims_false(self):
        with patch("delivery_audit.decode_video", return_value={"full_decode_passed": True}):
            result = audit(self.root)
        self.assertEqual(result["synchronized_frame_count"], 3)
        self.assertEqual(set(result["videos"]), set(CAMERAS))
        self.assertFalse(result["actual_pixels_verified"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_real_ffv1_probe_and_full_decode(self):
        video = self.root / "tiny.mkv"
        completed = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
                                    "-i", "color=red:size=16x16:rate=20", "-frames:v", "3",
                                    "-c:v", "ffv1", str(video)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        measured = decode_video(video, frames=3, size=(16, 16))
        self.assertTrue(measured["full_decode_passed"])
        with self.assertRaisesRegex(ValueError, "frame count differs"):
            decode_video(video, frames=4, size=(16, 16))


if __name__ == "__main__":
    unittest.main()
