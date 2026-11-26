"""CPU structure checks only; these are not original physical observations."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import OBSERVATIONS, audit_original
from native_capture import capture
from test_native_capture import FakeAdapter, fixture
from yield_view import CASES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = CASES[0]
        source = self.root / "source"
        source.mkdir()
        packet = fixture(source, self.case)
        self.attempt = self.root / "attempt"
        self.seal = capture(FakeAdapter(self.case), packet, source, self.attempt,
                            self.case, diagnostic=True)
        self.site_sha = sha(packet)
        review_dir = self.root / "independent_review"
        review_dir.mkdir()
        first_pixel_sha = json.loads((self.attempt / "camera-index.json").read_text())[
            "overview"][0]["sha256"]
        observations = {}
        for name in OBSERVATIONS:
            evidence = review_dir / (name + ".json")
            evidence.write_text(json.dumps({"diagnostic_structure": name}) + "\n")
            observations[name] = {
                "observed": True, "reviewer_note": "CPU shape test only",
                "frame": 300, "camera": "overview", "evidence_path": evidence.name,
                "source_sha256": sha(evidence), "pixel_sha256": first_pixel_sha,
            }
        self.review = review_dir / "review.json"
        self.packet = {
            "format": "c157964-original-physical-review-v1",
            "case_id": self.case.case_id,
            "native_seal_sha256": sha(self.attempt / "seal.json"),
            "site_packet_sha256": self.site_sha,
            "diagnostic_fixture": False, "source_kind": "original_native_capture",
            "reviewer": "CPU structure fixture", "reviewed_at": "fixture-time",
            "observations": observations, "physical_completion": True,
            "legal_judgment": None,
        }
        self._write_review()

    def _write_review(self):
        self.review.write_text(json.dumps(self.packet, sort_keys=True) + "\n")

    def _shape(self, **kwargs):
        with patch("delivery_audit.audit_saved", return_value={
                "diagnostic_fixture": False,
                "native_seal_sha256": sha(self.attempt / "seal.json"),
                "decoded_camera_frames": 3600}):
            return audit_original(self.attempt, self.review, self.case,
                                  expected_site_packet_sha256=self.site_sha,
                                  expected_review_packet_sha256=sha(self.review),
                                  **kwargs)

    def test_review_packet_structure_and_binding(self):
        report = self._shape()
        self.assertEqual(report["decoded_camera_frames"], 3600)
        self.assertTrue(report["physical_completion"])
        self.assertIsNone(report["legal_judgment"])

    def test_real_saved_auditor_rejects_diagnostic_attempt(self):
        with self.assertRaisesRegex(ValueError, "diagnostic attempt cannot be original delivery"):
            audit_original(self.attempt, self.review, self.case,
                           expected_site_packet_sha256=self.site_sha,
                           expected_review_packet_sha256=sha(self.review))

    def test_review_rejects_missing_or_stale_sources(self):
        with patch("delivery_audit.audit_saved", return_value={
                "diagnostic_fixture": False,
                "native_seal_sha256": sha(self.attempt / "seal.json"),
                "decoded_camera_frames": 3600}):
            with self.assertRaisesRegex(ValueError, "independent review packet hash differs"):
                audit_original(self.attempt, self.review, self.case,
                               expected_site_packet_sha256=self.site_sha,
                               expected_review_packet_sha256="0" * 64)
        self.packet["observations"].pop("camera_visibility")
        self._write_review()
        with self.assertRaisesRegex(ValueError, "physical review observations incomplete"):
            self._shape()

    def test_review_rejects_wrong_frame_and_changed_evidence(self):
        self.packet["observations"]["ego_motion"]["frame"] = 9999
        self._write_review()
        with self.assertRaisesRegex(ValueError, "original physical observation missing"):
            self._shape()
        self.packet["observations"]["ego_motion"]["frame"] = 300
        self._write_review()
        evidence = self.review.parent / "ego_motion.json"
        evidence.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "review evidence bytes changed"):
            self._shape()

    def test_review_rejects_wrong_pixel_hash(self):
        self.packet["observations"]["camera_visibility"]["pixel_sha256"] = "0" * 64
        self._write_review()
        with self.assertRaisesRegex(ValueError, "review camera/frame/pixel join missing"):
            self._shape()


if __name__ == "__main__":
    unittest.main()
