import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture
from source_audit import audit
from saved_export import export
from test_native_capture import Session
from test_native_site import SITE


CASE = {"case_id": "a__short80", "target": {"weather_request": "clear",
        "signal_continuity_request": "continuous"}}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def make_attempt(root):
    site_raw = (json.dumps(SITE, sort_keys=True) + "\n").encode()
    (root / "original-site.json").write_bytes(site_raw)
    site_hash = sha(site_raw)
    result = capture(Session(), SITE, site_hash, CASE, root, frames=3)
    receipt = {"format": "original-turn-signal-acquisition", "case_id": CASE["case_id"],
               "physical_acceptance": False, "legal_assessment": "unresolved",
               "site_sha256": site_hash, "trace_sha256": result["trace_sha256"],
               "frame_count": 3, "camera_archives": result["camera_archives"]}
    (root / "original-acquisition-receipt.json").write_text(json.dumps(receipt) + "\n")


class SourceAuditTests(unittest.TestCase):
    def test_fake_sources_decode_but_cannot_claim_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            result = audit(root, CASE["case_id"], allow_diagnostic=True)
            self.assertTrue(result["source_decode_passed"])
            self.assertTrue(result["diagnostic_fixture"])
            self.assertEqual(len(result["camera_archive_sha256"]), 4)
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                audit(root, CASE["case_id"])

    def test_changed_archive_and_missing_camera_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            archive = root / "approach.png.zip"
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "camera archive hash differs"):
                audit(root, CASE["case_id"], allow_diagnostic=True)
            archive.unlink()
            with self.assertRaises(FileNotFoundError):
                audit(root, CASE["case_id"], allow_diagnostic=True)

    def test_changed_site_and_trace_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            trace = root / "original-turn-signal.json"
            trace.write_bytes(trace.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "original trace hash differs"):
                audit(root, CASE["case_id"], allow_diagnostic=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            site = root / "original-site.json"
            site.write_bytes(site.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "original site hash differs"):
                audit(root, CASE["case_id"], allow_diagnostic=True)

    def test_saved_projection_encodes_four_original_camera_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            (root / "trace.jsonl").write_text("{}\n")
            (root / "road.xodr").write_text("diagnostic road\n")
            (root / "carla_recorder.log").write_text("diagnostic recorder\n")
            result = export(root, CASE["case_id"], allow_diagnostic=True)
            self.assertEqual(len(result["four_video_sha256"]), 4)
            self.assertEqual(len((root / "video_frames.jsonl").read_text().splitlines()), 3)
            self.assertTrue((root / "approach.mkv").stat().st_size > 0)
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                audit(root, CASE["case_id"])


if __name__ == "__main__":
    unittest.main()
