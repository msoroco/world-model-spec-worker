import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c111748_site_review", ROOT / "site_review.py")
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)

CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source_hashes = {}
        sources = {}
        for name in reviewer.REQUIRED:
            path = self.root / (name + ".txt")
            path.write_text("Original reviewed " + name + " record\n")
            source_hashes[name] = sha(path)
            sources[name] = {"path": path.name, "sha256": sha(path),
                             "review_note": "Compared to case and original placement"}
        self.site = self.root / "site.json"
        self.site.write_text(json.dumps({"case_id": CASE,
            "highway_status": {"source_sha256": source_hashes["highway"]},
            "device": {"authority_source_sha256": source_hashes["placement_authority"],
                       "legal_consistency_source_sha256": source_hashes["legal_consistency"],
                       "display_source_sha256": source_hashes["display_direction"]}}))
        self.review = self.root / "review.json"
        self.packet = {"case_id": CASE, "site_sha256": sha(self.site),
            "source_kind": "original_reviewed_native_site", "diagnostic_fixture": False,
            "reviewer": "independent local reviewer", "reviewed_at": "2026-11-25T00:00:00Z",
            "governed_approach_reviewed": True, "route_envelope_reviewed": True,
            "sources": sources}
        self.write_review()

    def write_review(self):
        self.review.write_text(json.dumps(self.packet))

    def verify(self):
        return reviewer.verify(self.site, sha(self.site), CASE, self.review, self.root)

    def test_source_binding(self):
        receipt = self.verify()
        self.assertEqual(set(receipt["verified_sources"]), set(reviewer.REQUIRED))
        self.assertEqual(receipt["physical_visibility"], "requires original pixel review")

    def test_missing_or_changed_source_rejected(self):
        (self.root / "display_direction.txt").write_text("different original\n")
        with self.assertRaisesRegex(reviewer.ReviewError, "hash mismatch: display_direction"):
            self.verify()

    def test_unreviewed_or_diagnostic_packet_rejected(self):
        self.packet["diagnostic_fixture"] = True
        self.write_review()
        with self.assertRaisesRegex(reviewer.ReviewError, "original reviewed"):
            self.verify()

    def test_wrong_case_and_route_review_rejected(self):
        self.packet["case_id"] = "other"
        self.write_review()
        with self.assertRaisesRegex(reviewer.ReviewError, "case mismatch"):
            self.verify()
        self.packet["case_id"] = CASE
        self.packet["route_envelope_reviewed"] = False
        self.write_review()
        with self.assertRaisesRegex(reviewer.ReviewError, "route review"):
            self.verify()

    def test_escaped_source_rejected(self):
        self.packet["sources"]["highway"]["path"] = "../outside.txt"
        self.write_review()
        with self.assertRaisesRegex(reviewer.ReviewError, "escaped"):
            self.verify()
