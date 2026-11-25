"""Saved processing must bind all original freight source and media bytes."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_audit import audit
from freight_contract import SourceError


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    case_id = "case"

    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c149555-delivery-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / "attempt"
        self.attempt.mkdir()
        (self.attempt / "source.json").write_text("{}\n")
        (self.attempt / "raw.jsonl").write_text("{}\n")
        (self.attempt / "overview.mkv").write_bytes(b"video")
        self.canonical_path = self.attempt / "result.json"
        write_json(self.canonical_path, {"case_id": self.case_id, "diagnostic_fixture": False})
        self.manifest_path = self.attempt / "freight-delivery-manifest.json"
        self.manifest = {"case_id": self.case_id, "native_result_sha256": "native",
                         "canonical_result_sha256": sha(self.canonical_path),
                         "diagnostic_fixture": False,
                         "sources": {"native_result": {"path": "source.json", "sha256": sha(self.attempt / "source.json")}},
                         "raw_sources": {"motion": {"path": "raw.jsonl", "sha256": sha(self.attempt / "raw.jsonl")}},
                         "media": {"overview": {"path": "overview.mkv", "sha256": sha(self.attempt / "overview.mkv")}}}
        write_json(self.manifest_path, self.manifest)
        self.result_path = self.root / "result.json"
        write_json(self.result_path, {"case_id": self.case_id, "diagnostic_fixture": False})
        self.processing_path = self.root / "processing.json"
        self.processing = {"format": "worker-saved-processing", "case_id": self.case_id,
                           "passed": True, "originals_preserved": True,
                           "original_source_hashes": {p.name: sha(p) for p in self.attempt.iterdir()},
                           "result": str(self.result_path), "result_sha256": sha(self.result_path)}
        write_json(self.processing_path, self.processing)
        self.review_path = self.root / "review.json"
        write_json(self.review_path, {"case_id": self.case_id})

    def run_audit(self):
        with patch("delivery_audit.audit_delivery", return_value={
                "physical_case_completion": True, "full_video_decode": True,
                "all_participants": True, "time_join": True}), \
             patch("delivery_audit.audit_pixels", return_value={"actual_pixels_reviewed": True}):
            return audit(self.attempt, self.processing_path, self.review_path)

    def test_complete_saved_binding(self):
        self.assertTrue(self.run_audit()["passed"])

    def test_rejects_omitted_original_media(self):
        del self.processing["original_source_hashes"]["overview.mkv"]
        write_json(self.processing_path, self.processing)
        with self.assertRaises(SourceError):
            self.run_audit()

    def test_rejects_changed_original_source(self):
        (self.attempt / "raw.jsonl").write_text("changed\n")
        with self.assertRaises(SourceError):
            self.run_audit()

    def test_rejects_diagnostic_result(self):
        write_json(self.result_path, {"case_id": self.case_id, "diagnostic_fixture": True})
        self.processing["result_sha256"] = sha(self.result_path)
        write_json(self.processing_path, self.processing)
        with self.assertRaises(SourceError):
            self.run_audit()

    def test_rejects_changed_canonical_native_result(self):
        write_json(self.canonical_path, {"case_id": self.case_id, "diagnostic_fixture": True})
        with self.assertRaisesRegex(SourceError, "canonical Native result changed"):
            self.run_audit()

    def test_rejects_missing_original_participant(self):
        with patch("delivery_audit.audit_delivery", return_value={
                "physical_case_completion": True, "full_video_decode": True,
                "all_participants": False, "time_join": True}), \
             patch("delivery_audit.audit_pixels", return_value={"actual_pixels_reviewed": True}):
            with self.assertRaisesRegex(SourceError, "participants"):
                audit(self.attempt, self.processing_path, self.review_path)

    def test_rejects_missing_time_join(self):
        with patch("delivery_audit.audit_delivery", return_value={
                "physical_case_completion": True, "full_video_decode": True,
                "all_participants": True, "time_join": False}), \
             patch("delivery_audit.audit_pixels", return_value={"actual_pixels_reviewed": True}):
            with self.assertRaisesRegex(SourceError, "time join"):
                audit(self.attempt, self.processing_path, self.review_path)


if __name__ == "__main__":
    unittest.main()
